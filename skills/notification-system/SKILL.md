# Notification System Skill

Multi-channel notification system for trading alerts, errors, and opportunities.

## Overview

The notification system provides a flexible, extensible way to send alerts across multiple channels with support for:
- **Priority levels**: CRITICAL, HIGH, MEDIUM, LOW
- **Rate limiting**: Prevents spam and notification fatigue
- **Templates**: Consistent message formatting
- **Channel adapters**: Console, Webhook, Discord, Telegram, Email
- **History tracking**: Audit log of all notifications

## Quick Start

```python
from notification_system import NotificationConfig, send_notification

# Initialize with your channels
config = NotificationConfig(
    channels=[
        {"type": "console", "enabled": True},
        {"type": "discord", "webhook_url": "https://discord.com/api/webhooks/...", "enabled": True},
        {"type": "telegram", "bot_token": "YOUR_BOT_TOKEN", "chat_id": "YOUR_CHAT_ID", "enabled": True},
    ]
)

# Send a notification
send_notification(
    title="Trade Executed",
    message="BTC/USDT buy order filled at $42,500",
    priority="HIGH",
    category="trade",
    config=config
)
```

## Configuration

### NotificationConfig

The main configuration class for the notification system.

```python
from notification_system import NotificationConfig

config = NotificationConfig(
    channels=[
        # Console output (for debugging/logging)
        {"type": "console", "enabled": True},
        
        # Generic webhook
        {
            "type": "webhook",
            "url": "https://api.example.com/alerts",
            "headers": {"Authorization": "Bearer token"},
            "enabled": True
        },
        
        # Discord webhook
        {
            "type": "discord",
            "webhook_url": "https://discord.com/api/webhooks/...",
            "enabled": True
        },
        
        # Telegram bot
        {
            "type": "telegram",
            "bot_token": "YOUR_BOT_TOKEN",
            "chat_id": "YOUR_CHAT_ID",
            "enabled": True
        },
        
        # Email (SMTP)
        {
            "type": "email",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "your@email.com",
            "password": "your_password",
            "from_addr": "alerts@yourdomain.com",
            "to_addrs": ["admin@yourdomain.com"],
            "use_tls": True,
            "enabled": True
        }
    ],
    rate_limit={
        "enabled": True,
        "window_seconds": 60,
        "max_per_priority": {
            "CRITICAL": 100,
            "HIGH": 10,
            "MEDIUM": 5,
            "LOW": 2
        }
    },
    templates={
        "trade": "🔄 **{title}**\n{message}\nTime: {timestamp}",
        "error": "❌ **ERROR: {title}**\n{message}\nPriority: {priority}",
        "opportunity": "💰 **OPPORTUNITY: {title}**\n{message}"
    },
    history_enabled=True,
    history_max_size=1000
)
```

### Channel Configuration

#### Console Channel

Simple console output for local development and debugging.

```python
{"type": "console", "enabled": True}
```

#### Webhook Channel

Generic HTTP POST webhook for custom integrations.

```python
{
    "type": "webhook",
    "url": "https://api.example.com/alerts",
    "headers": {"Authorization": "Bearer token"},
    "timeout": 10,
    "enabled": True
}
```

#### Discord Channel

Discord webhook integration with rich embed support.

```python
{
    "type": "discord",
    "webhook_url": "https://discord.com/api/webhooks/...",
    "enabled": True
}
```

**Color Mapping by Priority:**
- CRITICAL: 🔴 Red (#FF0000)
- HIGH: 🟠 Orange (#FFA500)
- MEDIUM: 🟡 Yellow (#FFFF00)
- LOW: 🔵 Blue (#0000FF)

#### Telegram Channel

Telegram Bot API integration.

```python
{
    "type": "telegram",
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID",
    "parse_mode": "Markdown",
    "enabled": True
}
```

**Setup Instructions:**
1. Create a bot via [@BotFather](https://t.me/botfather)
2. Get your chat ID by messaging [@userinfobot](https://t.me/userinfobot)
3. Add the bot to your channel/group if needed

#### Email Channel

SMTP email notifications.

```python
{
    "type": "email",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your@gmail.com",
    "password": "app_specific_password",
    "from_addr": "alerts@yourdomain.com",
    "to_addrs": ["admin@yourdomain.com", "ops@yourdomain.com"],
    "use_tls": True,
    "enabled": True
}
```

## Usage

### Basic Notification

```python
from notification_system import send_notification

send_notification(
    title="Price Alert",
    message="Bitcoin broke above $50,000",
    priority="HIGH",
    category="opportunity"
)
```

### Custom Data

```python
send_notification(
    title="Trade Executed",
    message="Order filled",
    priority="MEDIUM",
    category="trade",
    data={
        "symbol": "BTC/USDT",
        "side": "buy",
        "amount": 0.5,
        "price": 42500.00,
        "order_id": "12345"
    }
)
```

### Template Usage

```python
config = NotificationConfig(
    templates={
        "arbitrage": "⚡ **ARBITRAGE OPPORTUNITY**\n"
                     "Buy: {buy_exchange} @ ${buy_price:,.2f}\n"
                     "Sell: {sell_exchange} @ ${sell_price:,.2f}\n"
                     "Profit: {profit_pct:.2f}%"
    }
)

send_notification(
    title="BTC Arbitrage",
    message="",
    priority="CRITICAL",
    category="arbitrage",
    template_vars={
        "buy_exchange": "Binance",
        "buy_price": 42500.00,
        "sell_exchange": "Coinbase",
        "sell_price": 42650.00,
        "profit_pct": 0.35
    },
    config=config
)
```

### Priority Levels

| Priority | Use Case | Default Rate Limit |
|----------|----------|-------------------|
| CRITICAL | System failures, critical trades, security alerts | 100/min |
| HIGH | Important trades, significant opportunities | 10/min |
| MEDIUM | Regular updates, non-urgent alerts | 5/min |
| LOW | Info logs, debug messages | 2/min |

### Silent Failures

By default, channel failures don't block other channels. To change this:

```python
send_notification(
    title="Important",
    message="Critical update",
    priority="CRITICAL",
    silent_fail=False  # Raises exception if any channel fails
)
```

## Rate Limiting

Rate limiting prevents notification spam and API quota exhaustion.

```python
config = NotificationConfig(
    rate_limit={
        "enabled": True,
        "window_seconds": 60,
        "max_per_priority": {
            "CRITICAL": 100,  # Never miss critical alerts
            "HIGH": 10,
            "MEDIUM": 5,
            "LOW": 2  # Aggressive limiting for low priority
        }
    }
)
```

When rate limited, notifications are:
1. Logged to console (if available)
2. Added to history (if enabled)
3. Skipped for other channels

## History Tracking

All notifications are tracked with metadata:

```python
from notification_system import get_notification_history

# Get recent notifications
history = get_notification_history(limit=10)

for notif in history:
    print(f"[{notif['timestamp']}] {notif['priority']}: {notif['title']}")
```

History entries include:
- `id`: Unique notification ID
- `timestamp`: ISO format timestamp
- `title`: Notification title
- `message`: Notification message
- `priority`: Priority level
- `category`: Message category/template
- `channels`: List of channels that received it
- `success`: Whether all channels succeeded
- `data`: Custom data payload

## Custom Channel Adapters

Extend the system with custom adapters:

```python
from notification_system import BaseChannelAdapter, register_channel_adapter

class SlackAdapter(BaseChannelAdapter):
    def __init__(self, config):
        self.webhook_url = config["webhook_url"]
    
    def send(self, notification):
        import requests
        payload = {
            "text": f"*{notification['title']}*\n{notification['message']}"
        }
        requests.post(self.webhook_url, json=payload)
    
    def is_configured(self):
        return bool(self.webhook_url)

# Register the adapter
register_channel_adapter("slack", SlackAdapter)

# Use in config
config = NotificationConfig(
    channels=[{"type": "slack", "webhook_url": "...", "enabled": True}]
)
```

## Environment Variables

Load configuration from environment:

```python
import os
from notification_system import NotificationConfig

config = NotificationConfig(
    channels=[
        {
            "type": "discord",
            "webhook_url": os.getenv("DISCORD_WEBHOOK_URL"),
            "enabled": bool(os.getenv("DISCORD_WEBHOOK_URL"))
        },
        {
            "type": "telegram",
            "bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
            "enabled": bool(os.getenv("TELEGRAM_BOT_TOKEN"))
        }
    ]
)
```

## Best Practices

1. **Use appropriate priorities**: Reserve CRITICAL for truly urgent matters
2. **Rate limit aggressively**: Prevent notification fatigue
3. **Template consistently**: Use templates for consistent formatting
4. **Enable multiple channels**: For critical alerts, use redundant channels
5. **Monitor history**: Check for notification delivery issues
6. **Secure credentials**: Store tokens/passwords in environment variables

## Testing

Run the test suite:

```bash
python -m pytest test_notification_system.py -v
```

Run with coverage:

```bash
python -m pytest test_notification_system.py --cov=notification_system --cov-report=html
```

## Troubleshooting

### Discord webhook fails
- Verify webhook URL is correct
- Check Discord rate limits (5 requests per 2 seconds)
- Ensure webhook has proper permissions

### Telegram bot not responding
- Verify bot token is correct
- Check bot is added to the chat/group
- Ensure chat_id is correct (use @userinfobot)

### Email not sending
- Verify SMTP credentials
- Check for app-specific passwords (Gmail)
- Ensure firewall allows SMTP ports

### Rate limiting too aggressive
- Adjust `max_per_priority` in rate_limit config
- Consider using different priorities for different message types
