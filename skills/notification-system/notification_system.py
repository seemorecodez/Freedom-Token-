"""
Notification System - Multi-channel alerts for trades, errors, and opportunities.

This module provides a flexible notification system supporting multiple channels
with rate limiting, templates, and history tracking.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import json
import logging
import threading
import time
import traceback

# Optional imports for specific channels
try:
    import requests
except ImportError:
    requests = None

try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
except ImportError:
    smtplib = None

# Configure logging
logger = logging.getLogger(__name__)


class Priority(Enum):
    """Notification priority levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Default rate limits per priority
DEFAULT_RATE_LIMITS = {
    Priority.CRITICAL: 100,
    Priority.HIGH: 10,
    Priority.MEDIUM: 5,
    Priority.LOW: 2
}

# Discord color mapping by priority
DISCORD_COLORS = {
    Priority.CRITICAL: 0xFF0000,  # Red
    Priority.HIGH: 0xFFA500,      # Orange
    Priority.MEDIUM: 0xFFFF00,    # Yellow
    Priority.LOW: 0x0000FF        # Blue
}


@dataclass
class Notification:
    """Represents a single notification."""
    id: str
    timestamp: datetime
    title: str
    message: str
    priority: Priority
    category: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    template_vars: Optional[Dict[str, Any]] = None


class BaseChannelAdapter(ABC):
    """Abstract base class for channel adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)
    
    @abstractmethod
    def send(self, notification: Notification) -> bool:
        """Send notification through this channel. Returns success status."""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if this channel is properly configured."""
        pass
    
    def format_message(self, notification: Notification, template: Optional[str] = None) -> str:
        """Format notification message using template."""
        if template:
            template_vars = {
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority.value,
                "timestamp": notification.timestamp.isoformat(),
                "category": notification.category or "default",
                **(notification.template_vars or {})
            }
            try:
                return template.format(**template_vars)
            except KeyError as e:
                logger.warning(f"Template variable missing: {e}")
                return f"{notification.title}\n{notification.message}"
        
        return f"{notification.title}\n{notification.message}"


class ConsoleAdapter(BaseChannelAdapter):
    """Console output adapter."""
    
    def is_configured(self) -> bool:
        return True
    
    def send(self, notification: Notification) -> bool:
        try:
            priority_emoji = {
                Priority.CRITICAL: "🔴",
                Priority.HIGH: "🟠",
                Priority.MEDIUM: "🟡",
                Priority.LOW: "🔵"
            }.get(notification.priority, "⚪")
            
            output = f"""
{'='*60}
{priority_emoji} [{notification.priority.value}] {notification.title}
{'='*60}
{notification.message}
Time: {notification.timestamp.isoformat()}
Category: {notification.category or 'N/A'}
{'='*60}
"""
            print(output)
            
            if notification.data:
                print(f"Data: {json.dumps(notification.data, indent=2)}")
            
            return True
        except Exception as e:
            logger.error(f"Console adapter error: {e}")
            return False


class WebhookAdapter(BaseChannelAdapter):
    """Generic webhook adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get("url")
        self.headers = config.get("headers", {})
        self.timeout = config.get("timeout", 10)
    
    def is_configured(self) -> bool:
        return self.url is not None and requests is not None
    
    def send(self, notification: Notification) -> bool:
        if not self.is_configured():
            logger.warning("Webhook not configured")
            return False
        
        try:
            payload = {
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority.value,
                "timestamp": notification.timestamp.isoformat(),
                "category": notification.category,
                "data": notification.data
            }
            
            response = requests.post(
                self.url,
                json=payload,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Webhook adapter error: {e}")
            return False


class DiscordAdapter(BaseChannelAdapter):
    """Discord webhook adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get("webhook_url")
        self.timeout = config.get("timeout", 10)
    
    def is_configured(self) -> bool:
        return self.webhook_url is not None and requests is not None
    
    def send(self, notification: Notification) -> bool:
        if not self.is_configured():
            logger.warning("Discord not configured")
            return False
        
        try:
            color = DISCORD_COLORS.get(notification.priority, 0x808080)
            
            embed = {
                "title": notification.title,
                "description": notification.message,
                "color": color,
                "timestamp": notification.timestamp.isoformat(),
                "footer": {
                    "text": f"Priority: {notification.priority.value}"
                }
            }
            
            if notification.data:
                fields = []
                for key, value in notification.data.items():
                    fields.append({
                        "name": str(key),
                        "value": str(value)[:1024],  # Discord limit
                        "inline": True
                    })
                if fields:
                    embed["fields"] = fields[:25]  # Discord limit
            
            payload = {"embeds": [embed]}
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Discord adapter error: {e}")
            return False


class TelegramAdapter(BaseChannelAdapter):
    """Telegram Bot API adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config.get("bot_token")
        self.chat_id = config.get("chat_id")
        self.parse_mode = config.get("parse_mode", "Markdown")
        self.timeout = config.get("timeout", 10)
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
    
    def is_configured(self) -> bool:
        return (
            self.bot_token is not None and
            self.chat_id is not None and
            requests is not None
        )
    
    def send(self, notification: Notification) -> bool:
        if not self.is_configured():
            logger.warning("Telegram not configured")
            return False
        
        try:
            priority_emoji = {
                Priority.CRITICAL: "🔴",
                Priority.HIGH: "🟠",
                Priority.MEDIUM: "🟡",
                Priority.LOW: "🔵"
            }.get(notification.priority, "⚪")
            
            text = f"{priority_emoji} *{notification.priority.value}*\n\n"
            text += f"*{notification.title}*\n\n"
            text += f"{notification.message}\n\n"
            text += f"_Time: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}_"
            
            if notification.data:
                text += "\n\n*Details:*\n"
                for key, value in notification.data.items():
                    text += f"• {key}: `{value}`\n"
            
            url = f"{self.api_base}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": self.parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Telegram adapter error: {e}")
            return False


class EmailAdapter(BaseChannelAdapter):
    """SMTP email adapter."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_host = config.get("smtp_host")
        self.smtp_port = config.get("smtp_port", 587)
        self.username = config.get("username")
        self.password = config.get("password")
        self.from_addr = config.get("from_addr")
        self.to_addrs = config.get("to_addrs", [])
        self.use_tls = config.get("use_tls", True)
        self.timeout = config.get("timeout", 10)
    
    def is_configured(self) -> bool:
        return (
            self.smtp_host is not None and
            self.from_addr is not None and
            self.to_addrs and
            smtplib is not None
        )
    
    def send(self, notification: Notification) -> bool:
        if not self.is_configured():
            logger.warning("Email not configured")
            return False
        
        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)
            msg["Subject"] = f"[{notification.priority.value}] {notification.title}"
            
            body = f"""Priority: {notification.priority.value}
Title: {notification.title}
Time: {notification.timestamp.isoformat()}
Category: {notification.category or 'N/A'}

{notification.message}
"""
            
            if notification.data:
                body += f"\n\nData:\n{json.dumps(notification.data, indent=2)}"
            
            msg.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            logger.error(f"Email adapter error: {e}")
            return False


# Registry of channel adapters
_channel_adapters: Dict[str, type] = {
    "console": ConsoleAdapter,
    "webhook": WebhookAdapter,
    "discord": DiscordAdapter,
    "telegram": TelegramAdapter,
    "email": EmailAdapter
}


def register_channel_adapter(name: str, adapter_class: type):
    """Register a custom channel adapter."""
    if not issubclass(adapter_class, BaseChannelAdapter):
        raise ValueError("Adapter must inherit from BaseChannelAdapter")
    _channel_adapters[name] = adapter_class


def get_channel_adapter(name: str, config: Dict[str, Any]) -> Optional[BaseChannelAdapter]:
    """Get a channel adapter by name."""
    adapter_class = _channel_adapters.get(name)
    if adapter_class:
        return adapter_class(config)
    return None


class RateLimiter:
    """Rate limiter for notifications."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.window_seconds = self.config.get("window_seconds", 60)
        self.max_per_priority = self.config.get("max_per_priority", {})
        
        # Use defaults for missing priorities
        for priority in Priority:
            if priority.value not in self.max_per_priority:
                self.max_per_priority[priority.value] = DEFAULT_RATE_LIMITS[priority]
        
        # Track notification timestamps per priority
        self._history: Dict[str, List[float]] = {
            p.value: [] for p in Priority
        }
        self._lock = threading.Lock()
    
    def is_allowed(self, priority: Priority) -> bool:
        """Check if a notification with given priority is allowed."""
        if not self.enabled:
            return True
        
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            
            # Clean old entries
            self._history[priority.value] = [
                ts for ts in self._history[priority.value] if ts > cutoff
            ]
            
            # Check limit
            max_allowed = self.max_per_priority.get(priority.value, DEFAULT_RATE_LIMITS[priority])
            current_count = len(self._history[priority.value])
            
            if current_count >= max_allowed:
                return False
            
            # Record this notification
            self._history[priority.value].append(now)
            return True
    
    def get_remaining(self, priority: Priority) -> int:
        """Get remaining quota for priority."""
        if not self.enabled:
            return float('inf')
        
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            
            # Clean old entries
            self._history[priority.value] = [
                ts for ts in self._history[priority.value] if ts > cutoff
            ]
            
            max_allowed = self.max_per_priority.get(priority.value, DEFAULT_RATE_LIMITS[priority])
            return max(0, max_allowed - len(self._history[priority.value]))


@dataclass
class NotificationConfig:
    """Configuration for the notification system."""
    channels: List[Dict[str, Any]] = field(default_factory=list)
    rate_limit: Optional[Dict[str, Any]] = None
    templates: Optional[Dict[str, str]] = field(default_factory=dict)
    history_enabled: bool = True
    history_max_size: int = 1000
    
    def __post_init__(self):
        if self.templates is None:
            self.templates = {}
        
        # Default templates
        default_templates = {
            "default": "{title}\n{message}",
            "trade": "🔄 {title}\n{message}",
            "error": "❌ ERROR: {title}\n{message}",
            "opportunity": "💰 OPPORTUNITY: {title}\n{message}"
        }
        
        for key, value in default_templates.items():
            if key not in self.templates:
                self.templates[key] = value


class NotificationHistory:
    """Tracks notification history."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._counter = 0
    
    def add(self, notification: Notification, results: Dict[str, bool]):
        """Add a notification to history."""
        with self._lock:
            self._counter += 1
            entry = {
                "id": notification.id,
                "sequence": self._counter,
                "timestamp": notification.timestamp.isoformat(),
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority.value,
                "category": notification.category,
                "channels": results,
                "success": all(results.values()) if results else False,
                "data": notification.data
            }
            
            self._history.append(entry)
            
            # Trim if exceeds max size
            if len(self._history) > self.max_size:
                self._history = self._history[-self.max_size:]
    
    def get(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get notification history."""
        with self._lock:
            if limit:
                return self._history[-limit:]
            return self._history.copy()
    
    def clear(self):
        """Clear notification history."""
        with self._lock:
            self._history.clear()
            self._counter = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get history statistics."""
        with self._lock:
            total = len(self._history)
            successful = sum(1 for h in self._history if h["success"])
            
            by_priority = {}
            for h in self._history:
                p = h["priority"]
                by_priority[p] = by_priority.get(p, 0) + 1
            
            by_channel = {}
            for h in self._history:
                for channel, success in h["channels"].items():
                    if channel not in by_channel:
                        by_channel[channel] = {"sent": 0, "failed": 0}
                    if success:
                        by_channel[channel]["sent"] += 1
                    else:
                        by_channel[channel]["failed"] += 1
            
            return {
                "total": total,
                "successful": successful,
                "failed": total - successful,
                "by_priority": by_priority,
                "by_channel": by_channel
            }


# Global state
_default_config: Optional[NotificationConfig] = None
_default_history: NotificationHistory = NotificationHistory()
_default_rate_limiter: Optional[RateLimiter] = None
_state_lock = threading.Lock()


def configure(config: NotificationConfig):
    """Configure the global notification system."""
    global _default_config, _default_rate_limiter
    
    with _state_lock:
        _default_config = config
        _default_rate_limiter = RateLimiter(config.rate_limit)


def get_config() -> Optional[NotificationConfig]:
    """Get the current global configuration."""
    return _default_config


def get_notification_history(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get notification history."""
    return _default_history.get(limit)


def clear_notification_history():
    """Clear notification history."""
    _default_history.clear()


def get_notification_stats() -> Dict[str, Any]:
    """Get notification statistics."""
    return _default_history.get_stats()


def generate_notification_id() -> str:
    """Generate a unique notification ID."""
    import uuid
    return str(uuid.uuid4())[:8]


def send_notification(
    title: str,
    message: str,
    priority: str = "MEDIUM",
    category: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    template_vars: Optional[Dict[str, Any]] = None,
    config: Optional[NotificationConfig] = None,
    silent_fail: bool = True
) -> Dict[str, Any]:
    """
    Send a notification through all configured channels.
    
    Args:
        title: Notification title
        message: Notification message
        priority: Priority level (CRITICAL, HIGH, MEDIUM, LOW)
        category: Message category for template selection
        data: Additional data to include with notification
        template_vars: Variables for template formatting
        config: Optional config (uses global config if not provided)
        silent_fail: If True, don't raise exceptions on channel failures
    
    Returns:
        Dict with notification details and channel results
    """
    # Get configuration
    cfg = config or _default_config
    if cfg is None:
        cfg = NotificationConfig()  # Use defaults
    
    # Parse priority
    try:
        prio = Priority(priority.upper())
    except ValueError:
        prio = Priority.MEDIUM
    
    # Create notification object
    notification = Notification(
        id=generate_notification_id(),
        timestamp=datetime.utcnow(),
        title=title,
        message=message,
        priority=prio,
        category=category,
        data=data,
        template_vars=template_vars
    )
    
    # Get rate limiter
    rate_limiter = _default_rate_limiter
    if rate_limiter is None or (config is not None and config != _default_config):
        rate_limiter = RateLimiter(cfg.rate_limit)
    
    # Check rate limit
    if not rate_limiter.is_allowed(prio):
        remaining = rate_limiter.get_remaining(prio)
        warning_msg = f"Rate limit exceeded for {prio.value} priority ({remaining} remaining)"
        logger.warning(warning_msg)
        
        # Still log to console if available
        for channel_config in cfg.channels:
            if channel_config.get("type") == "console" and channel_config.get("enabled", True):
                adapter = ConsoleAdapter(channel_config)
                adapter.send(notification)
                break
        
        result = {
            "id": notification.id,
            "timestamp": notification.timestamp.isoformat(),
            "title": title,
            "priority": priority,
            "sent": False,
            "rate_limited": True,
            "channels": {},
            "warning": warning_msg
        }
        
        if cfg.history_enabled:
            _default_history.add(notification, {})
        
        return result
    
    # Send to all enabled channels
    results: Dict[str, bool] = {}
    errors: Dict[str, str] = {}
    
    # Get template for category
    template = cfg.templates.get(category) if category else None
    if not template:
        template = cfg.templates.get("default")
    
    for channel_config in cfg.channels:
        channel_type = channel_config.get("type")
        
        if not channel_config.get("enabled", True):
            continue
        
        try:
            adapter = get_channel_adapter(channel_type, channel_config)
            if adapter is None:
                logger.warning(f"Unknown channel type: {channel_type}")
                continue
            
            if not adapter.is_configured():
                logger.warning(f"Channel {channel_type} not properly configured")
                continue
            
            # Format message with template
            formatted_message = adapter.format_message(notification, template)
            
            # Create a copy with formatted message
            formatted_notification = Notification(
                id=notification.id,
                timestamp=notification.timestamp,
                title=notification.title,
                message=formatted_message,
                priority=notification.priority,
                category=notification.category,
                data=notification.data,
                template_vars=notification.template_vars
            )
            
            success = adapter.send(formatted_notification)
            results[channel_type] = success
            
            if not success:
                errors[channel_type] = "Send failed"
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Channel {channel_type} error: {error_msg}")
            logger.debug(traceback.format_exc())
            results[channel_type] = False
            errors[channel_type] = error_msg
            
            if not silent_fail:
                raise
    
    # Add to history
    if cfg.history_enabled:
        _default_history.add(notification, results)
    
    return {
        "id": notification.id,
        "timestamp": notification.timestamp.isoformat(),
        "title": title,
        "priority": priority,
        "sent": any(results.values()) if results else False,
        "rate_limited": False,
        "channels": results,
        "errors": errors if errors else None
    }


# Convenience functions for common notification types

def notify_trade(
    title: str,
    message: str,
    priority: str = "HIGH",
    **kwargs
) -> Dict[str, Any]:
    """Send a trade notification."""
    return send_notification(
        title=title,
        message=message,
        priority=priority,
        category="trade",
        **kwargs
    )


def notify_error(
    title: str,
    message: str,
    priority: str = "CRITICAL",
    **kwargs
) -> Dict[str, Any]:
    """Send an error notification."""
    return send_notification(
        title=title,
        message=message,
        priority=priority,
        category="error",
        **kwargs
    )


def notify_opportunity(
    title: str,
    message: str,
    priority: str = "HIGH",
    **kwargs
) -> Dict[str, Any]:
    """Send an opportunity notification."""
    return send_notification(
        title=title,
        message=message,
        priority=priority,
        category="opportunity",
        **kwargs
    )


if __name__ == "__main__":
    # Demo usage
    print("=" * 60)
    print("Notification System Demo")
    print("=" * 60)
    
    # Basic console notification
    result = send_notification(
        title="Test Alert",
        message="This is a test notification",
        priority="MEDIUM",
        category="default",
        config=NotificationConfig(channels=[{"type": "console", "enabled": True}])
    )
    print(f"\nResult: {json.dumps(result, indent=2)}")
    
    # Trade notification
    result = send_notification(
        title="BTC/USDT Buy Order Filled",
        message="Order executed successfully",
        priority="HIGH",
        category="trade",
        data={
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": 0.5,
            "price": 42500.00
        },
        config=NotificationConfig(channels=[{"type": "console", "enabled": True}])
    )
    
    # Show stats
    print(f"\nNotification Stats: {json.dumps(get_notification_stats(), indent=2)}")
