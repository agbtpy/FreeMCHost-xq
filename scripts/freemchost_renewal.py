#!/usr/bin/env python3
"""Renew a FreeMCHost server through the free Discord-boosted option.
Required environment variables: EMAIL, PASSWORD, TG_BOT_TOKEN, TG_CHAT_ID, NODE_LINK
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from seleniumbase import SB

OUTPUT = Path(os.getenv("OUTPUT_DIR", "output/screenshots"))
OUTPUT.mkdir(parents=True, exist_ok=True)
SCREENSHOT = OUTPUT / "freemchost-manage.png"


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def visible_text(sb: SB) -> str:
    """Return the page's rendered text, for failure diagnostics."""
    try:
        return str(sb.execute_script("return document.body.innerText;"))
    except Exception:
        try:
            text = re.sub(r"<[^>]+>", " ", sb.get_page_source())
            return re.sub(r"\s+", " ", text)
        except Exception:
            return ""


def sanitize(text: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[已隐藏]")
    return text


def click_text(sb: SB, text: str, timeout: int = 20) -> None:
    """Click a visible button/link/tab by its rendered text without XPath.
    通过 JavaScript 原生 click() 触发，等效于 Playwright 的 force=True，
    绕过 backdrop 遮罩层拦截。
    """
    script = """
    (() => {
        const wanted = %s.toLowerCase();
        const nodes = [...document.querySelectorAll('button, a, [role="button"], [role="tab"], [type="button"], [type="submit"]')];
        const node = nodes.find(el => {
            const label = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            return label.includes(wanted) && el.getClientRects().length > 0;
        });
        if (!node) return false;
        node.click();
        return true;
    })()
    """ % json.dumps(text)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if sb.execute_script(script):
            return
        sb.sleep(0.5)
    raise RuntimeError(f"页面中未找到可点击的按钮：{text}")


def dismiss_optional(sb: SB, text: str) -> None:
    """尝试关闭弹窗，不存在也不报错。"""
    try:
        click_text(sb, text, timeout=3)
    except Exception:
        pass


def dismiss_all_dialogs(sb: SB) -> None:
    """关闭页面上所有弹窗，确保截图干净。"""
    for _ in range(8):
        count = sb.execute_script("return document.querySelectorAll('[role=\"dialog\"]').length;") or 0
        if count == 0:
            break
        for btn_text in ["Maybe later", "Close", "Close toast", "Reject all"]:
            try:
                click_text(sb, btn_text, timeout=2)
                sb.sleep(0.5)
                break
            except Exception:
                continue
        else:
            sb.execute_script("""
                document.querySelectorAll('[role="dialog"]').forEach(d => d.remove());
            """)


def selected_tab(sb: SB) -> str:
    """Return the text of the currently selected tab, for verification."""
    script = """
    (() => {
        const tab = document.querySelector('[role="tab"][aria-selected="true"]');
        return tab ? (tab.innerText || tab.textContent || '').replace(/\\s+/g, ' ').trim() : '';
    })()
    """
    try:
        return str(sb.execute_script(script) or "")
    except Exception:
        return ""


def click_tab(sb: SB, name: str, timeout: int = 30) -> None:
    """Click a tab and verify it actually became the selected tab."""
    click_text(sb, name, timeout=timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if name.lower() in selected_tab(sb).lower():
            return
        sb.sleep(0.5)
    raise RuntimeError(
        f"点击了 {name} 但标签未激活（当前激活标签：'{selected_tab(sb) or '无'}'）"
    )


def try_click_text(sb: SB, text: str, timeout: int = 8) -> bool:
    """Click text if it is available; return False when it is not clickable."""
    try:
        click_text(sb, text, timeout=timeout)
        return True
    except Exception:
        return False


def extract_countdown(body: str) -> str:
    """从页面 HTML 中提取到期倒计时。
    优先匹配 TIME UNTIL EXPIRY 后的 timer，再匹配通用 D/H/M/S 模式。
    """
    patterns = [
        r"(?:TIME UNTIL EXPIRY|Time until expiry).*?(\d{1,3})\s*[Dd].*?(\d{1,2})\s*[Hh].*?(\d{1,2})\s*[Mm].*?(\d{1,2})\s*[Ss]",
        r"(\d{1,3})\s*[Dd]\s*(\d{1,2})\s*[Hh]\s*(\d{1,2})\s*[Mm]\s*(\d{1,2})\s*[Ss]",
        r"(\d{1,3})[dD]\s*(\d{1,2})[hH]\s*(\d{1,2})[mM]\s*(\d{1,2})[sS]",
    ]
    for pattern in patterns:
        match = re.search(pattern, body, flags=re.I | re.S)
        if match:
            d, h, m, s = match.groups()
            return f"{d}d {h}h {m}m {s}s"
    return "未识别到到期倒计时"


def telegram_message(token: str, chat_id: str, text: str) -> None:
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text},
        timeout=30,
    )
    response.raise_for_status()
    if not response.json().get("ok"):
        raise RuntimeError(f"Telegram API error: {response.text}")


def telegram_send(token: str, chat_id: str, caption: str, image: Path) -> None:
    with image.open("rb") as photo:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": (image.name, photo, "image/png")},
            timeout=30,
        )
    response.raise_for_status()
    if not response.json().get("ok"):
        raise RuntimeError(f"Telegram API error: {response.text}")


def main() -> int:
    email = required("EMAIL")
    password = required("PASSWORD")

    login_url = "https://freemchost.com/login"
    server_url = "https://freemchost.com/app/servers/1ff6673f-e48e-46a6-a9f8-9813e31ccd86"

    tg_token = required("TG_BOT_TOKEN")
    tg_chat_id = required("TG_CHAT_ID")

    # sing-box setup_proxy.sh 默认监听本机 SOCKS5 1080 端口
    proxy = "socks5://127.0.0.1:1080"
    chrome_args = [f"--proxy-server={proxy}"]

    countdown = "未获取"
    phase = "登录"

    try:
        with SB(headless=True, xvfb=True, uc=True, chromium_arg=" ".join(chrome_args)) as sb:
            # === 登录 ===
            sb.open(login_url)
            sb.sleep(3)
            sb.type('input[type="email"]', email)
            sb.type('input[type="password"]', password)
            sb.click('form button[type="submit"]')

            deadline = time.time() + 30
            while time.time() < deadline:
                if "/login" not in sb.get_current_url() and "/app" in sb.get_current_url():
                    break
                sb.sleep(1)
            else:
                raise RuntimeError("登录失败：登录后未进入管理页面")
            if "/login" in sb.get_current_url():
                raise RuntimeError("登录失败：仍停留在登录页面")

            # === 进入服务器页 ===
            phase = "续期"
            dismiss_optional(sb, "Reject all")
            dismiss_optional(sb, "Maybe later")

            sb.open(server_url)
            sb.sleep(3)
            dismiss_optional(sb, "Reject all")
            dismiss_optional(sb, "Maybe later")

            # === 点击 PLAN Billing 标签（文本包含 "Billing"） ===
            try:
                click_tab(sb, "Billing", timeout=30)
                click_text(sb, "Renew now", timeout=30)
            except RuntimeError as click_exc:
                sb.save_screenshot(str(SCREENSHOT))
                snippet = sanitize(visible_text(sb), email, server_url, password)
                snippet = re.sub(r"\s+", " ", snippet).strip()[:1200]
                telegram_send(
                    tg_token, tg_chat_id,
                    f"🔎 FreeMCHost 诊断：{click_exc}\n"
                    f"当前激活标签：'{selected_tab(sb) or '无'}'\n"
                    f"页面文字片段：\n{snippet}",
                    SCREENSHOT,
                )
                raise
            sb.sleep(1)

            # === 点击 Discord Boosted renewal（免费续期 60 hours）===
            # click_text 内部使用 JavaScript node.click()，等效于 force=True
            renewed = try_click_text(sb, "Discord Boosted renewal", timeout=8)
            if renewed:
                sb.sleep(3)
                renewal_status = "已点击 Discord Boosted renewal"
            else:
                # 该选项不可点击通常表示尚未进入可续期时间窗口，不视为失败
                renewal_status = "当前未到续期时间，Discord Boosted renewal 不可点击"

            # === 关闭所有弹窗，确保截图干净 ===
            dismiss_all_dialogs(sb)
            sb.sleep(1)

            # === 截图 + 提取倒计时 ===
            body = sb.get_page_source()
            text = re.sub(r"<[^>]+>", " ", body)
            text = re.sub(r"\s+", " ", text)
            countdown = extract_countdown(text)

            sb.save_screenshot(str(SCREENSHOT))

            caption = (
                "✅ FreeMCHost 任务完成\n"
                "服务器: 已配置服务器（链接已隐藏）\n"
                f"状态: {renewal_status}\n"
                f"到期倒计时: {countdown}"
            )
            telegram_send(tg_token, tg_chat_id, caption, SCREENSHOT)
            print(caption)
            print("截图已生成并发送（本地临时文件，未上传 Artifact）")
            return 0

    except Exception as exc:
        safe_error = str(exc).replace(server_url, "[服务器链接已隐藏]")
        error = f"❌ FreeMCHost {phase}失败：{safe_error}"
        try:
            telegram_message(tg_token, tg_chat_id, error)
        except Exception as notify_exc:
            print(f"Telegram failure notification failed: {notify_exc}", file=sys.stderr)
        print(error, file=sys.stderr)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
