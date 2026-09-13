# FreeMCHost 自动续期脚本使用说明

本项目通过 GitHub Actions 自动登录 FreeMCHost，进入指定服务器的 Manage 页面，尝试点击免费的 **Discord Boosted renewal**，获取到期倒计时，并将结果和截图发送到 Telegram。

## 一、需要配置的 GitHub Secrets

进入仓库：

`Settings → Secrets and variables → Actions → New repository secret`

配置以下 Secrets：

| Secret 名称 | 用途 |
|---|---|
| `EMAIL` | FreeMCHost 登录邮箱 |
| `PASSWORD` | FreeMCHost 登录密码 |
| `TG_BOT_TOKEN` | Telegram Bot Token |
| `TG_CHAT_ID` | 接收通知的 Telegram Chat ID |
| `NODE_LINK` | sing-box 代理节点或订阅链接 |

不要把邮箱、密码、Bot Token、Chat ID 或节点链接写入代码、工作流明文或提交记录。

## 二、代理说明

工作流会通过以下远程脚本启动 sing-box：

```bash
bash <(wget -qO- https://main.ssss.nyc.mn/setup_proxy.sh)
```

仓库中不需要新增本地 `.sh` 文件。

续期脚本固定使用 sing-box 默认本机 SOCKS5 代理：

```text
socks5://127.0.0.1:1080
```

因此不需要配置 `PROXY_SERVER`。如果远程代理脚本实际使用的端口不是 `1080`，需要同步修改 `scripts/freemchost_renewal.py` 中的代理地址。

## 三、运行方式

### 手动运行

进入 GitHub 仓库的：

`Actions → FreeMCHost 续期 → Run workflow`

选择分支后点击 **Run workflow**。

### 自动运行

当前计划任务为：

```yaml
- cron: '11 1 */2 * *'
```

即每两天 UTC 01:11 执行一次，约为北京时间 09:11。GitHub Actions 的定时任务可能会有延迟。

## 四、脚本执行流程

工作流文件：

```text
.github/workflows/freemchost-renewal.yml
```

Python 脚本：

```text
scripts/freemchost_renewal.py
```

执行顺序：

1. 安装 Python、ChromeDriver、Xvfb 和浏览器依赖
2. 使用 `NODE_LINK` 启动 sing-box 代理
3. 打开固定的 FreeMCHost 服务器页面
4. 使用 `EMAIL` 和 `PASSWORD` 登录
5. 进入服务器的 Manage 页面
6. 点击 Renew now
7. 尝试点击 Discord Boosted renewal
8. 获取到期倒计时
9. 截图并发送到 Telegram
10. 清理浏览器、sing-box、Xvfb 和临时截图

服务器链接已经固定写入 Python 脚本，不需要配置服务器 URL Secret。

## 五、未到续期时间时的行为

如果 **Discord Boosted renewal** 暂时不可点击，脚本将其视为尚未到续期时间：

- 不判定为任务失败
- 关闭续期弹窗
- 截取当前页面
- 读取到期倒计时
- 发送 Telegram 状态通知
- GitHub Actions 正常结束

## 六、Telegram 通知

脚本会发送以下类型的通知：

- 登录成功
- 代理设置失败
- 登录失败
- 续期失败
- 任务完成及截图
- 尚未到续期时间及倒计时

通知和 GitHub Actions 日志不会输出完整服务器链接。截图只保存在 Runner 的临时目录，发送 Telegram 后自动删除，不上传 GitHub Actions Artifact。

## 七、故障排查

1. 检查所有 GitHub Secrets 名称是否完全匹配。
2. 确认 `NODE_LINK` 有效且能启动 sing-box。
3. 确认代理默认监听 `127.0.0.1:1080`。
4. 在 Actions 运行记录中查看失败步骤，但不要公开日志中的敏感内容。
5. 如果网站页面结构发生变化，需要调整 `scripts/freemchost_renewal.py` 中的按钮定位文本。

## 八、代码检查

修改脚本后可在本地执行：

```bash
python -m py_compile scripts/freemchost_renewal.py
```

工作流文件应同时确认：

- 没有 `upload-artifact`
- 没有明文账号密码
- 没有明文 Telegram Token
- 没有明文节点链接
- 没有把完整服务器链接打印到日志
