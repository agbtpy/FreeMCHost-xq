#!/usr/bin/env python3
"""Renew a FreeMCHost server through the free Discord-boosted option.

Required environment variables:
  EMAIL, PASSWORD, TG_BOT_TOKEN, TG_CHAT_ID, NODE_LINK
"""
from __future__ import annotations

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


def click_text(sb: SB, text: str, timeout: int = 20) -> None:
    """Click the first visible button/link containing text."""
    xpath = (
        "//*[self::button or self::a or @role='button' or @role='tab']"
        f"[contains(normalize-space(.), {text!r})]"
    )
    selector = f"xpath={xpath}"
    sb.wait_for_element_visible(selector, timeout=timeout)
    sb.click(selector)


def dismiss_optional(sb: SB, text: str) -> None:
    try:
        click_text(sb, text, timeout=3)
    except Exception:
        pass


def try_click_text(sb: SB, text: str, timeout: int = 8) -> bool:
    """Click text if it is available; return False when it is not clickable."""
    try:
        click_text(sb, text, timeout=timeout)
        return True
    except Exception:
        return False


def extract_countdown(body: str) -> str:
    patterns = [
        r"(?:TIME UNTIL EXPIRY|Time until expiry).*?(\d{1,3})\s*[Dd].*?(\d{1,2})\s*[Hh].*?(\d{1,2})\s*[Mm].*?(\d{1,2})\s*[Ss]",
        r"(\d{1,3})\s*[Dd]\s*(\d{1,2})\s*[Hh]\s*(\d{1,2})\s*[Mm]\s*(\d{1,2})\s*[Ss]",
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
    # 登录页与服务器续期页分开；服务器链接固定在脚本中。
    login_url = "https://freemchost.com/login"
    server_url = "https://freemchost.com/app/servers/1ff6673f-e48e-46a6-a9f8-9813e31ccd86"
    tg_token = required("TG_BOT_TOKEN")
    tg_chat_id = required("TG_CHAT_ID")
    # sing-box setup_proxy.sh 默认监听本机 SOCKS5 1080 端口。
    proxy = "socks5://127.0.0.1:1080"
    chrome_args = [f"--proxy-server={proxy}"]

    countdown = "未获取"
    phase = "登录"
    try:
        with SB(headless=True, xvfb=True, uc=True, chromium_arg=" ".join(chrome_args)) as sb:
            # 先打开独立登录网址，再跳转到服务器续期网址。
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
            # 登录成功不单独发送 Telegram，最终结果统一通知。
            phase = "续期"

            dismiss_optional(sb, "Reject all")
            dismiss_optional(sb, "Maybe later")
            sb.open(server_url)
            sb.sleep(3)
            dismiss_optional(sb, "Reject all")
            dismiss_optional(sb, "Maybe later")
            click_text(sb, "Manage")
            sb.sleep(2)
            click_text(sb, "Renew now")
            sb.sleep(1)
            renewed = try_click_text(sb, "Discord Boosted renewal", timeout=8)
            if renewed:
                sb.sleep(3)
                renewal_status = "已点击 Discord Boosted renewal"
            else:
                # 该选项不可点击通常表示尚未进入可续期时间窗口，不视为失败。
                renewal_status = "当前未到续期时间，Discord Boosted renewal 不可点击"
            # 无论是否可续期，都关闭续期弹窗后再截图。
            dismiss_optional(sb, "Close")
            dismiss_optional(sb, "Maybe later")
            body = sb.get_page_source()
            text = re.sub(r"<[^>]+>", " ", body)
            text = re.sub(r"\s+", " ", text)
            countdown = extract_countdown(text)
            # 截图仅用于发送 Telegram，不上传到 GitHub Actions Artifact。
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
        # 错误详情也做脱敏，避免 Selenium 异常把完整 URL 写入 GitHub 日志。
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
