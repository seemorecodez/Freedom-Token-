---
name: channels-setup
description: Guide to set up and configure IM channels(Telegram, Discord, Slack, Feishu(飞书), Dingtalk(钉钉), Weibo(微博) and Wecom AI Bot(企业微信智能机器人) for OpenClaw.
---

## Quick Start

Use openclaw CLI to enable and configure the channels you want.

After configuration, you should restart the gateway to apply changes:

```bash
openclaw gateway restart
```

Before restarting, you must explicitly inform the user that OpenClaw is about to restart.

If the restart doesn’t take effect, guide the user to:

1. Open KimiClaw Web
2. Click the settings button in the top-right corner
3. Manually restart Kimi Claw

### Telegram

```bash
openclaw config set channels.telegram.botToken "YOUR_BOT_TOKEN"
openclaw config set channels.telegram.dmPolicy "pairing"
openclaw config set channels.telegram.groups."*".requireMention true
openclaw config set channels.telegram.enabled true
```

### Discord

```bash
openclaw config set channels.discord.token "YOUR_BOT_TOKEN"
openclaw config set channels.discord.enabled true
```

### Slack

```bash
openclaw config set channels.slack.mode "socket"
openclaw config set channels.slack.appToken "xapp-..."
openclaw config set channels.slack.botToken "xoxb-..."
openclaw config set channels.slack.enabled true
```

### Feishu

```bash
openclaw config set channels.feishu.appId "YOUR_APP_ID"
openclaw config set channels.feishu.appSecret "YOUR_APP_SECRET"
openclaw config set channels.feishu.groupPolicy "open"
openclaw config set channels.feishu.enabled true
openclaw config set channels.feishu.dmPolicy "pairing"
openclaw config set channels.feishu.requireMention true
```

### Dingtalk

Edit the `channels` and `gateway` fields in `~/.openclaw/openclaw.json` as below:

```json
{
  "channels": {
    "dingtalk-connector": {
      "enabled": true,
      "clientId": "dingxxxxxxxxx",       // DingTalk AppKey
      "clientSecret": "your_secret_here", // DingTalk AppSecret
      "gatewayToken": "",                 // Optional: Gateway authentication token, the value of gateway.auth.token in openclaw.json
      "gatewayPassword": "",              // Optional: Gateway authentication password (choose either token or password)
      "sessionTimeout": 1800000           // Optional: Session timeout (ms), default is 30 minutes
    }
  },
  "gateway": {
    "http": {
      "endpoints": {
        "chatCompletions": {
          "enabled": true
        }
      }
    }
  }
}
```

### Weibo

When user wants to integrate Weibo, tell user the guide.

Config Weibo direct message channel:

1. Open Weibo App, send message `连接龙虾` to [@微博龙虾助手](https://weibo.com/u/6808810981);
2. `微博龙虾助手` will give user appid and appsecret, for example:

```
您的应用凭证信息如下：

AppId: your-app-id
AppSecret: your-app-secret
```

3. Config openclaw:

```
openclaw config set 'channels.weibo.appSecret' 'your-appSecret'
openclaw config set 'channels.weibo.appId' 'your-appId'
```

4. If user wants to reset the appid and appsecret, send `重置凭证` to `微博龙虾助手`.

> If `/root/.openclaw/extensions` don't have `weibo` directory, please install the plugin first:
> 
> ```bash
> git clone https://gitee.com/wecode-ai/openclaw-weibo.git
> cd openclaw-weibo
> openclaw plugins install .
> openclaw gateway restart
> ```

## Wecom AI Bot(企业微信智能机器人)

Ask the user to create Wecom AI Bot in [Wecom AI Bot Helper](https://work.weixin.qq.com/wework_admin/frame#/aiHelper/create), and provide the `BotId` and `Secret`.

```bash
openclaw config set channels.wecom.botId "YOUR_BOT_ID"
openclaw config set channels.wecom.secret "YOUR_SECRET"
openclaw config set channels.wecom.enabled true
```

> If `/root/.openclaw/extensions` don't have `wecom-openclaw-plugin` directory, please install the plugin first:
> 
> ```bash
> openclaw plugins install @wecom/wecom-openclaw-plugin
> ```

To update the plugin, you can run:

```bash
openclaw plugins update wecom-openclaw-plugin
```

## References

You can refer to the following documents for more detailed configuration instructions:

For Feishu channel detail setup, please refer to:

- [Feishu Channel Setup Guide](/root/.openclaw/extensions/feishu/README.md)

For Dingtalk channel detail setup, please refer to:

- [Dingtalk Channel Setup Guide](/root/.openclaw/extensions/dingtalk-connector/README.md)

For Weibo channel detail setup, please refer to:

- [Weibo Channel Setup Guide](/root/.openclaw/extensions/weibo/README.md)

For Wecom AI Bot channel detail setup, please refer to:

- [Wecom AI Bot Channel Setup Guide](/root/.openclaw/extensions/wecom-openclaw-plugin/README.md)

For Telegram, Slack, Discord or more channels setup, please refer to [OpenClaw Channel Setup Guide](https://docs.openclaw.ai/channels). Explore `https://docs.openclaw.ai/channels` to see all available channel setup guides.

If users are unsure how to configure channels, direct them to the Settings -> User Manual in KimiClaw Web for detailed instructions.