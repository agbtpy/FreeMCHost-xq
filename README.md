# 64专用脚本说明
3个文件上传，改端口 uuid
ip输出节点手动改或直接脚本里改都可以

---------------------------------------------
# FreeMCHost 自动续期脚本使用说明

本项目通过 GitHub Actions 自动登录 FreeMCHost，进入指定服务器的 Manage 页面，尝试点击免费的 **Discord Boosted renewal**，获取到期倒计时，并将结果和截图发送到 Telegram。

# 需要配置的 GitHub Secrets

进入仓库：

`Settings → Secrets and variables → Actions → New repository secret`

配置以下 Secrets：

| Secret 名称 | 用途 |
|---|---|
| `EMAIL` | FreeMCHost 登录邮箱 |
| `PASSWORD` | FreeMCHost 登录密码 |
| `TG_BOT_TOKEN` | Telegram Bot Token |
| `TG_CHAT_ID` | 接收通知的 Telegram Chat ID |
| `NODE_LINK` |  代理节点 |

# 未到续期时间时的行为

如果 **Discord Boosted renewal** 暂时不可点击，脚本将其视为尚未到续期时间：

- 不判定为任务失败
- 关闭续期弹窗
- 截取当前页面
- 读取到期倒计时
- 发送 Telegram 状态通知
- GitHub Actions 正常结束

# Telegram 通知

脚本会发送以下类型的通知：

- 登录成功
- 代理设置失败
- 登录失败
- 续期失败
- 任务完成及截图
- 尚未到续期时间及倒计时
