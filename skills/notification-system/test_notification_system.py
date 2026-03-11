"""
Unit tests for the notification system.
"""

import unittest
import time
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Import the notification system
import sys
sys.path.insert(0, '/root/.openclaw/skills/notification-system')

from notification_system import (
    Priority,
    Notification,
    NotificationConfig,
    RateLimiter,
    NotificationHistory,
    ConsoleAdapter,
    WebhookAdapter,
    DiscordAdapter,
    TelegramAdapter,
    EmailAdapter,
    send_notification,
    notify_trade,
    notify_error,
    notify_opportunity,
    get_notification_history,
    clear_notification_history,
    get_notification_stats,
    configure,
    register_channel_adapter,
    BaseChannelAdapter,
    generate_notification_id,
    _channel_adapters
)


class TestPriority(unittest.TestCase):
    """Test priority enum."""
    
    def test_priority_values(self):
        """Test priority enum values."""
        self.assertEqual(Priority.CRITICAL.value, "CRITICAL")
        self.assertEqual(Priority.HIGH.value, "HIGH")
        self.assertEqual(Priority.MEDIUM.value, "MEDIUM")
        self.assertEqual(Priority.LOW.value, "LOW")
    
    def test_priority_ordering(self):
        """Test that priorities exist."""
        priorities = list(Priority)
        self.assertEqual(len(priorities), 4)
        self.assertIn(Priority.CRITICAL, priorities)
        self.assertIn(Priority.LOW, priorities)


class TestNotification(unittest.TestCase):
    """Test Notification dataclass."""
    
    def test_notification_creation(self):
        """Test creating a notification."""
        notif = Notification(
            id="test-123",
            timestamp=datetime.utcnow(),
            title="Test",
            message="Test message",
            priority=Priority.HIGH,
            category="test",
            data={"key": "value"}
        )
        
        self.assertEqual(notif.id, "test-123")
        self.assertEqual(notif.title, "Test")
        self.assertEqual(notif.priority, Priority.HIGH)
        self.assertEqual(notif.data, {"key": "value"})


class TestNotificationConfig(unittest.TestCase):
    """Test NotificationConfig class."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = NotificationConfig()
        
        self.assertEqual(config.channels, [])
        self.assertTrue(config.history_enabled)
        self.assertEqual(config.history_max_size, 1000)
        self.assertIsNotNone(config.templates)
        
        # Check default templates exist
        self.assertIn("default", config.templates)
        self.assertIn("trade", config.templates)
        self.assertIn("error", config.templates)
        self.assertIn("opportunity", config.templates)
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = NotificationConfig(
            channels=[{"type": "console", "enabled": True}],
            templates={"custom": "Custom: {title}"},
            history_enabled=False,
            history_max_size=100
        )
        
        self.assertEqual(len(config.channels), 1)
        self.assertFalse(config.history_enabled)
        self.assertEqual(config.history_max_size, 100)
        self.assertIn("custom", config.templates)
        self.assertIn("default", config.templates)  # Default templates still added


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter class."""
    
    def test_rate_limit_enabled(self):
        """Test rate limiting when enabled."""
        config = {
            "enabled": True,
            "window_seconds": 60,
            "max_per_priority": {
                "CRITICAL": 5,
                "HIGH": 3,
                "MEDIUM": 2,
                "LOW": 1
            }
        }
        limiter = RateLimiter(config)
        
        # Should allow up to limit
        for _ in range(3):
            self.assertTrue(limiter.is_allowed(Priority.HIGH))
        
        # Should block after limit
        self.assertFalse(limiter.is_allowed(Priority.HIGH))
    
    def test_rate_limit_disabled(self):
        """Test rate limiting when disabled."""
        limiter = RateLimiter({"enabled": False})
        
        # Should always allow
        for _ in range(100):
            self.assertTrue(limiter.is_allowed(Priority.HIGH))
    
    def test_rate_limit_per_priority(self):
        """Test that rate limits are per priority."""
        config = {
            "enabled": True,
            "max_per_priority": {
                "CRITICAL": 100,
                "HIGH": 1
            }
        }
        limiter = RateLimiter(config)
        
        # Exhaust HIGH limit
        self.assertTrue(limiter.is_allowed(Priority.HIGH))
        self.assertFalse(limiter.is_allowed(Priority.HIGH))
        
        # CRITICAL should still work
        for _ in range(10):
            self.assertTrue(limiter.is_allowed(Priority.CRITICAL))
    
    def test_rate_limit_window(self):
        """Test rate limit window expiration."""
        config = {
            "enabled": True,
            "window_seconds": 0.1,  # 100ms window for testing
            "max_per_priority": {"HIGH": 1}
        }
        limiter = RateLimiter(config)
        
        # Use the one allowed notification
        self.assertTrue(limiter.is_allowed(Priority.HIGH))
        self.assertFalse(limiter.is_allowed(Priority.HIGH))
        
        # Wait for window to expire
        time.sleep(0.15)
        
        # Should allow again
        self.assertTrue(limiter.is_allowed(Priority.HIGH))
    
    def test_get_remaining(self):
        """Test getting remaining quota."""
        config = {
            "enabled": True,
            "max_per_priority": {"HIGH": 5}
        }
        limiter = RateLimiter(config)
        
        self.assertEqual(limiter.get_remaining(Priority.HIGH), 5)
        limiter.is_allowed(Priority.HIGH)
        self.assertEqual(limiter.get_remaining(Priority.HIGH), 4)


class TestNotificationHistory(unittest.TestCase):
    """Test NotificationHistory class."""
    
    def setUp(self):
        """Clear history before each test."""
        clear_notification_history()
    
    def test_add_and_get(self):
        """Test adding and retrieving history."""
        history = NotificationHistory()
        
        notif = Notification(
            id="test-1",
            timestamp=datetime.utcnow(),
            title="Test",
            message="Message",
            priority=Priority.MEDIUM
        )
        
        history.add(notif, {"console": True})
        entries = history.get()
        
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Test")
        self.assertTrue(entries[0]["success"])
    
    def test_get_limit(self):
        """Test getting limited history."""
        history = NotificationHistory()
        
        for i in range(10):
            notif = Notification(
                id=f"test-{i}",
                timestamp=datetime.utcnow(),
                title=f"Test {i}",
                message="Message",
                priority=Priority.MEDIUM
            )
            history.add(notif, {"console": True})
        
        entries = history.get(limit=5)
        self.assertEqual(len(entries), 5)
    
    def test_max_size(self):
        """Test history max size enforcement."""
        history = NotificationHistory(max_size=5)
        
        for i in range(10):
            notif = Notification(
                id=f"test-{i}",
                timestamp=datetime.utcnow(),
                title=f"Test {i}",
                message="Message",
                priority=Priority.MEDIUM
            )
            history.add(notif, {"console": True})
        
        entries = history.get()
        self.assertEqual(len(entries), 5)
        self.assertEqual(entries[0]["title"], "Test 5")  # Oldest should be Test 5
    
    def test_clear(self):
        """Test clearing history."""
        history = NotificationHistory()
        
        notif = Notification(
            id="test-1",
            timestamp=datetime.utcnow(),
            title="Test",
            message="Message",
            priority=Priority.MEDIUM
        )
        history.add(notif, {"console": True})
        
        history.clear()
        self.assertEqual(len(history.get()), 0)
    
    def test_get_stats(self):
        """Test history statistics."""
        history = NotificationHistory()
        
        # Add successful notification
        notif1 = Notification(
            id="test-1",
            timestamp=datetime.utcnow(),
            title="Test 1",
            message="Message",
            priority=Priority.HIGH
        )
        history.add(notif1, {"console": True, "discord": True})
        
        # Add failed notification
        notif2 = Notification(
            id="test-2",
            timestamp=datetime.utcnow(),
            title="Test 2",
            message="Message",
            priority=Priority.CRITICAL
        )
        history.add(notif2, {"console": True, "discord": False})
        
        stats = history.get_stats()
        
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["successful"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["by_priority"]["HIGH"], 1)
        self.assertEqual(stats["by_priority"]["CRITICAL"], 1)
        self.assertEqual(stats["by_channel"]["console"]["sent"], 2)
        self.assertEqual(stats["by_channel"]["discord"]["sent"], 1)
        self.assertEqual(stats["by_channel"]["discord"]["failed"], 1)


class TestConsoleAdapter(unittest.TestCase):
    """Test ConsoleAdapter."""
    
    def test_is_configured(self):
        """Test console adapter is always configured."""
        adapter = ConsoleAdapter({})
        self.assertTrue(adapter.is_configured())
    
    def test_send(self):
        """Test sending to console."""
        adapter = ConsoleAdapter({"enabled": True})
        
        notif = Notification(
            id="test-1",
            timestamp=datetime.utcnow(),
            title="Test Title",
            message="Test Message",
            priority=Priority.HIGH
        )
        
        # Should not raise
        result = adapter.send(notif)
        self.assertTrue(result)
    
    def test_format_message_with_template(self):
        """Test message formatting with template."""
        adapter = ConsoleAdapter({})
        
        notif = Notification(
            id="test-1",
            timestamp=datetime.utcnow(),
            title="Test",
            message="Message",
            priority=Priority.HIGH,
            template_vars={"custom": "value"}
        )
        
        template = "{title} - {message} - {custom}"
        formatted = adapter.format_message(notif, template)
        
        self.assertIn("Test", formatted)
        self.assertIn("Message", formatted)
        self.assertIn("value", formatted)


class TestWebhookAdapter(unittest.TestCase):
    """Test WebhookAdapter."""
    
    def test_is_configured_no_url(self):
        """Test webhook not configured without URL."""
        adapter = WebhookAdapter({})
        self.assertFalse(adapter.is_configured())
    
    def test_is_configured_with_url(self):
        """Test webhook configured with URL."""
        adapter = WebhookAdapter({"url": "http://example.com/webhook"})
        self.assertTrue(adapter.is_configured())
    
    @patch('notification_system.requests')
    def test_send_success(self, mock_requests):
        """Test successful webhook send."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_response
        
        adapter = WebhookAdapter({
            "url": "http://example.com/webhook",
            "headers": {"Authorization": "Bearer token"}
        })
        
        notif = Notification(
            id="test-1",
            timestamp=datetime.utcnow(),
            title="Test",
            message="Message",
            priority=Priority.HIGH
        )
        
        result = adapter.send(notif)
        self.assertTrue(result)
        mock_requests.post.assert_called_once()
    
    @patch('notification_system.requests')
    def test_send_failure(self, mock_requests):
        """Test failed webhook send."""
        mock_requests.post.side_effect = Exception("Connection error")
        
        adapter = WebhookAdapter({"url": "http://example.com/webhook"})
        
        notif = Notification(
            id="test-1",
            timestamp=datetime.utcnow(),
            title="Test",
            message="Message",
            priority=Priority.HIGH
        )
        
        result = adapter.send(notif)
        self.assertFalse(result)


class TestDiscordAdapter(unittest.TestCase):
    """Test DiscordAdapter."""
    
    def test_is_configured_no_webhook(self):
        """Test Discord not configured without webhook."""
        adapter = DiscordAdapter({})
        self.assertFalse(adapter.is_configured())
    
    def test_is_configured_with_webhook(self):
        """Test Discord configured with webhook."""
        adapter = DiscordAdapter({"webhook_url": "https://discord.com/api/webhooks/..."})
        self.assertTrue(adapter.is_configured())
    
    @patch('notification_system.requests')
    def test_send_success(self, mock_requests):
        """Test successful Discord send."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_response
        
        adapter = DiscordAdapter({"webhook_url": "https://discord.com/api/webhooks/..."})
        
        notif = Notification(
            id="test-1",
            timestamp=datetime.utcnow(),
            title="Test",
            message="Message",
            priority=Priority.CRITICAL,
            data={"field1": "value1"}
        )
        
        result = adapter.send(notif)
        self.assertTrue(result)
        mock_requests.post.assert_called_once()
        
        # Check embed color for CRITICAL priority
        call_args = mock_requests.post.call_args
        payload = call_args[1]["json"]
        self.assertEqual(payload["embeds"][0]["color"], 0xFF0000)  # Red


class TestTelegramAdapter(unittest.TestCase):
    """Test TelegramAdapter."""
    
    def test_is_configured_incomplete(self):
        """Test Telegram not configured without token and chat_id."""
        adapter = TelegramAdapter({"bot_token": "token"})
        self.assertFalse(adapter.is_configured())
        
        adapter = TelegramAdapter({"chat_id": "123"})
        self.assertFalse(adapter.is_configured())
    
    def test_is_configured_complete(self):
        """Test Telegram configured with token and chat_id."""
        adapter = TelegramAdapter({
            "bot_token": "token",
            "chat_id": "123"
        })
        self.assertTrue(adapter.is_configured())
    
    @patch('notification_system.requests')
    def test_send_success(self, mock_requests):
        """Test successful Telegram send."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_response
        
        adapter = TelegramAdapter({
            "bot_token": "test_token",
            "chat_id": "12345"
        })
        
        notif = Notification(
            id="test-1",
            timestamp=datetime.utcnow(),
            title="Test",
            message="Message",
            priority=Priority.HIGH
        )
        
        result = adapter.send(notif)
        self.assertTrue(result)
        mock_requests.post.assert_called_once()


class TestEmailAdapter(unittest.TestCase):
    """Test EmailAdapter."""
    
    def test_is_configured_incomplete(self):
        """Test email not configured without required fields."""
        adapter = EmailAdapter({"smtp_host": "smtp.example.com"})
        self.assertFalse(adapter.is_configured())
    
    def test_is_configured_complete(self):
        """Test email configured with all required fields."""
        adapter = EmailAdapter({
            "smtp_host": "smtp.example.com",
            "from_addr": "from@example.com",
            "to_addrs": ["to@example.com"]
        })
        self.assertTrue(adapter.is_configured())
    
    @patch('notification_system.smtplib')
    def test_send_success(self, mock_smtplib):
        """Test successful email send."""
        mock_server = MagicMock()
        mock_smtplib.SMTP.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtplib.SMTP.return_value.__exit__ = MagicMock(return_value=False)
        
        adapter = EmailAdapter({
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "user@gmail.com",
            "password": "pass",
            "from_addr": "from@gmail.com",
            "to_addrs": ["to@gmail.com"],
            "use_tls": True
        })
        
        notif = Notification(
            id="test-1",
            timestamp=datetime.utcnow(),
            title="Test Alert",
            message="Test message content",
            priority=Priority.HIGH
        )
        
        result = adapter.send(notif)
        self.assertTrue(result)


class TestSendNotification(unittest.TestCase):
    """Test send_notification function."""
    
    def setUp(self):
        """Clear history before each test."""
        clear_notification_history()
    
    def test_send_basic_notification(self):
        """Test sending basic notification."""
        config = NotificationConfig(channels=[{"type": "console", "enabled": True}])
        
        result = send_notification(
            title="Test",
            message="Message",
            priority="HIGH",
            config=config
        )
        
        self.assertTrue(result["sent"])
        self.assertIn("id", result)
        self.assertIn("timestamp", result)
        self.assertEqual(result["priority"], "HIGH")
    
    def test_send_with_invalid_priority(self):
        """Test sending with invalid priority defaults to MEDIUM."""
        config = NotificationConfig(channels=[{"type": "console", "enabled": True}])
        
        result = send_notification(
            title="Test",
            message="Message",
            priority="INVALID",
            config=config
        )
        
        self.assertTrue(result["sent"])
    
    def test_send_with_data(self):
        """Test sending notification with data."""
        config = NotificationConfig(channels=[{"type": "console", "enabled": True}])
        
        result = send_notification(
            title="Trade Executed",
            message="Order filled",
            priority="HIGH",
            category="trade",
            data={"symbol": "BTC/USDT", "price": 50000},
            config=config
        )
        
        self.assertTrue(result["sent"])
    
    def test_send_rate_limited(self):
        """Test rate limiting."""
        config = NotificationConfig(
            channels=[{"type": "console", "enabled": True}],
            rate_limit={
                "enabled": True,
                "window_seconds": 60,
                "max_per_priority": {"HIGH": 1}
            }
        )
        
        # Configure globally so rate limiter is shared
        configure(config)
        
        # First should succeed
        result1 = send_notification(
            title="Test 1",
            message="Message",
            priority="HIGH"
        )
        self.assertTrue(result1["sent"])
        
        # Second should be rate limited
        result2 = send_notification(
            title="Test 2",
            message="Message",
            priority="HIGH"
        )
        self.assertFalse(result2["sent"])
        self.assertTrue(result2["rate_limited"])
    
    def test_send_disabled_channel(self):
        """Test that disabled channels are skipped."""
        config = NotificationConfig(channels=[{"type": "console", "enabled": False}])
        
        result = send_notification(
            title="Test",
            message="Message",
            config=config
        )
        
        self.assertFalse(result["sent"])
    
    def test_send_unknown_channel(self):
        """Test handling of unknown channel types."""
        config = NotificationConfig(channels=[{"type": "unknown", "enabled": True}])
        
        result = send_notification(
            title="Test",
            message="Message",
            config=config
        )
        
        # Should not crash, just not send
        self.assertFalse(result["sent"])
    
    def test_convenience_functions(self):
        """Test convenience notification functions."""
        config = NotificationConfig(channels=[{"type": "console", "enabled": True}])
        
        # Test notify_trade
        result = notify_trade(
            title="Trade",
            message="Trade message",
            config=config
        )
        self.assertTrue(result["sent"])
        
        # Test notify_error
        result = notify_error(
            title="Error",
            message="Error message",
            config=config
        )
        self.assertTrue(result["sent"])
        self.assertEqual(result["priority"], "CRITICAL")  # Default for errors
        
        # Test notify_opportunity
        result = notify_opportunity(
            title="Opportunity",
            message="Opportunity message",
            config=config
        )
        self.assertTrue(result["sent"])
    
    def test_history_tracking(self):
        """Test that notifications are tracked in history."""
        config = NotificationConfig(
            channels=[{"type": "console", "enabled": True}],
            history_enabled=True
        )
        
        send_notification(
            title="Test",
            message="Message",
            config=config
        )
        
        history = get_notification_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["title"], "Test")
    
    def test_generate_notification_id(self):
        """Test notification ID generation."""
        id1 = generate_notification_id()
        id2 = generate_notification_id()
        
        self.assertIsNotNone(id1)
        self.assertIsNotNone(id2)
        self.assertNotEqual(id1, id2)
        self.assertEqual(len(id1), 8)


class TestCustomAdapter(unittest.TestCase):
    """Test custom adapter registration."""
    
    def test_register_adapter(self):
        """Test registering a custom adapter."""
        
        class CustomAdapter(BaseChannelAdapter):
            def is_configured(self):
                return True
            
            def send(self, notification):
                return True
        
        register_channel_adapter("custom", CustomAdapter)
        
        self.assertIn("custom", _channel_adapters)
    
    def test_register_invalid_adapter(self):
        """Test that non-BaseChannelAdapter classes are rejected."""
        
        class NotAnAdapter:
            pass
        
        with self.assertRaises(ValueError):
            register_channel_adapter("invalid", NotAnAdapter)


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def setUp(self):
        """Clear history before each test."""
        clear_notification_history()
    
    def test_full_workflow(self):
        """Test full notification workflow."""
        # Configure the system
        config = NotificationConfig(
            channels=[{"type": "console", "enabled": True}],
            templates={
                "test": "TEST: {title} - {message}"
            },
            rate_limit={
                "enabled": True,
                "max_per_priority": {"HIGH": 10}
            }
        )
        
        configure(config)
        
        # Send multiple notifications
        priorities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        for p in priorities:
            send_notification(
                title=f"Test {p}",
                message=f"Message with {p} priority",
                priority=p,
                category="test"
            )
        
        # Check history
        history = get_notification_history()
        self.assertEqual(len(history), 4)
        
        # Check stats
        stats = get_notification_stats()
        self.assertEqual(stats["total"], 4)
        self.assertEqual(len(stats["by_priority"]), 4)
    
    def test_global_config(self):
        """Test global configuration."""
        config = NotificationConfig(channels=[{"type": "console", "enabled": True}])
        configure(config)
        
        # Send without explicit config (uses global)
        result = send_notification(
            title="Global Test",
            message="Using global config"
        )
        
        self.assertTrue(result["sent"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
