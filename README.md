# FreeMCHost 自动续期脚本使用说明

本项目通过 GitHub Actions 自动登录 FreeMCHost，进入指定服务器的 Manage 页面，尝试点击免费的 **Discord Boosted renewal**，获取到期倒计时，并将结果和截图发送到 Telegram。

## 需要配置的 GitHub Secrets

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

## 代理说明

工作流会通过以下远程脚本启动 sing-box：

```bash
bash <(wget -qO- https://main.ssss.nyc.mn/setup_proxy.sh)
```
## 未到续期时间时的行为

如果 **Discord Boosted renewal** 暂时不可点击，脚本将其视为尚未到续期时间：

- 不判定为任务失败
- 关闭续期弹窗
- 截取当前页面
- 读取到期倒计时
- 发送 Telegram 状态通知
- GitHub Actions 正常结束

## Telegram 通知

脚本会发送以下类型的通知：

- 登录成功
- 代理设置失败
- 登录失败
- 续期失败
- 任务完成及截图
- 尚未到续期时间及倒计时

通知和 GitHub Actions 日志不会输出完整服务器链接。截图只保存在 Runner 的临时目录，发送 Telegram 后自动删除，不上传 GitHub Actions Artifact。



