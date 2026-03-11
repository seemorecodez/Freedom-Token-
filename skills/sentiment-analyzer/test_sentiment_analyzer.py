"""
Unit tests for the Sentiment Analyzer skill.
"""

import unittest
import time
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Import the modules under test
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sentiment_analyzer import (
    SentimentAnalyzer, SentimentConfig, SentimentResult, SocialPost,
    TradingSignal, TrendResult, RateLimiter, APIKeyManager, Cache,
    DataSource, SentimentSignal, create_analyzer
)


class TestSentimentConfig(unittest.TestCase):
    """Tests for SentimentConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = SentimentConfig()
        self.assertEqual(config.threshold, 0.0)
        self.assertEqual(config.bullish_threshold, 0.2)
        self.assertEqual(config.bearish_threshold, -0.2)
        self.assertEqual(config.window_hours, 24)
        self.assertEqual(config.min_mentions, 10)
        self.assertEqual(config.cache_duration, 300)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = SentimentConfig(
            keywords=["BTC", "ETH"],
            bullish_threshold=0.3,
            window_hours=12
        )
        self.assertEqual(config.keywords, ["BTC", "ETH"])
        self.assertEqual(config.bullish_threshold, 0.3)
        self.assertEqual(config.window_hours, 12)
    
    def test_all_source_expansion(self):
        """Test that ALL source expands to individual sources."""
        config = SentimentConfig(sources=[DataSource.ALL])
        self.assertIn(DataSource.TWITTER, config.sources)
        self.assertIn(DataSource.REDDIT, config.sources)
        self.assertIn(DataSource.NEWS, config.sources)
        self.assertNotIn(DataSource.ALL, config.sources)
    
    def test_api_keys_config(self):
        """Test API keys configuration."""
        keys = {"twitter": "key1", "newsapi": "key2"}
        config = SentimentConfig(api_keys=keys)
        self.assertEqual(config.api_keys["twitter"], "key1")
        self.assertEqual(config.api_keys["newsapi"], "key2")


class TestSocialPost(unittest.TestCase):
    """Tests for SocialPost dataclass."""
    
    def test_post_creation(self):
        """Test creating a social post."""
        post = SocialPost(
            source=DataSource.TWITTER,
            content="Bitcoin is going to the moon!",
            timestamp=datetime.now(),
            author="crypto_user",
            engagement=100
        )
        self.assertEqual(post.source, DataSource.TWITTER)
        self.assertEqual(post.author, "crypto_user")
        self.assertEqual(post.engagement, 100)
    
    def test_sentiment_weight_no_engagement(self):
        """Test sentiment weight with no engagement."""
        post = SocialPost(
            source=DataSource.REDDIT,
            content="Test post",
            timestamp=datetime.now(),
            engagement=0
        )
        self.assertEqual(post.sentiment_weight, 1.0)
    
    def test_sentiment_weight_with_engagement(self):
        """Test sentiment weight with engagement."""
        post = SocialPost(
            source=DataSource.TWITTER,
            content="Test post",
            timestamp=datetime.now(),
            engagement=100
        )
        # Weight should be > 1.0 with engagement
        self.assertGreater(post.sentiment_weight, 1.0)
    
    def test_sentiment_weight_high_engagement(self):
        """Test sentiment weight caps at reasonable value."""
        post = SocialPost(
            source=DataSource.TWITTER,
            content="Test post",
            timestamp=datetime.now(),
            engagement=1000000
        )
        # Should be capped reasonably
        self.assertLess(post.sentiment_weight, 10.0)


class TestRateLimiter(unittest.TestCase):
    """Tests for RateLimiter class."""
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(calls=50, period=600)
        self.assertEqual(limiter.calls, 50)
        self.assertEqual(limiter.period, 600)
        self.assertEqual(limiter.tokens, 50)
    
    def test_acquire_token(self):
        """Test acquiring a token."""
        limiter = RateLimiter(calls=10, period=60)
        result = limiter.acquire(blocking=False)
        self.assertTrue(result)
        self.assertEqual(limiter.tokens, 9)
    
    def test_acquire_no_tokens(self):
        """Test acquiring when no tokens available."""
        limiter = RateLimiter(calls=1, period=60)
        limiter.acquire(blocking=False)  # Use the only token
        result = limiter.acquire(blocking=False)
        self.assertFalse(result)
    
    def test_token_refill(self):
        """Test token refill over time."""
        limiter = RateLimiter(calls=10, period=1)  # 10 tokens per second
        limiter.tokens = 0  # Empty the bucket
        time.sleep(0.2)  # Wait a bit
        limiter.acquire(blocking=False)  # Trigger refill calculation
        self.assertGreater(limiter.tokens, 0)
    
    def test_get_stats(self):
        """Test getting rate limiter stats."""
        limiter = RateLimiter(calls=100, period=900)
        stats = limiter.get_stats()
        self.assertIn("tokens_available", stats)
        self.assertIn("max_tokens", stats)
        self.assertIn("wait_time_seconds", stats)
        self.assertEqual(stats["max_tokens"], 100)


class TestAPIKeyManager(unittest.TestCase):
    """Tests for APIKeyManager class."""
    
    def test_get_key_from_config(self):
        """Test getting key from configuration."""
        manager = APIKeyManager({"twitter": "my_key"})
        key = manager.get_key("twitter")
        self.assertEqual(key, "my_key")
    
    @patch.dict(os.environ, {"TWITTER_API_KEY": "env_key"})
    def test_get_key_from_env(self):
        """Test getting key from environment variable."""
        manager = APIKeyManager()
        key = manager.get_key("twitter")
        self.assertEqual(key, "env_key")
    
    def test_get_key_not_found(self):
        """Test getting non-existent key."""
        manager = APIKeyManager()
        key = manager.get_key("nonexistent")
        self.assertIsNone(key)
    
    def test_set_key(self):
        """Test setting an API key."""
        manager = APIKeyManager()
        manager.set_key("reddit", "new_key")
        self.assertEqual(manager.get_key("reddit"), "new_key")
    
    def test_has_key(self):
        """Test checking if key exists."""
        manager = APIKeyManager({"twitter": "key"})
        self.assertTrue(manager.has_key("twitter"))
        self.assertFalse(manager.has_key("reddit"))
    
    def test_record_usage(self):
        """Test recording API usage."""
        manager = APIKeyManager()
        manager.record_usage("twitter")
        manager.record_usage("twitter")
        self.assertEqual(manager.get_usage("twitter"), 2)


class TestCache(unittest.TestCase):
    """Tests for Cache class."""
    
    def test_cache_set_and_get(self):
        """Test setting and getting cached value."""
        cache = Cache(default_ttl=60)
        cache.set("value", 300, "key1", "arg2")
        result = cache.get("key1", "arg2")
        self.assertEqual(result, "value")
    
    def test_cache_expiration(self):
        """Test cache expiration."""
        cache = Cache(default_ttl=0)  # Immediate expiration
        cache.set("value", 0, "key")
        time.sleep(0.1)
        result = cache.get("key")
        self.assertIsNone(result)
    
    def test_cache_miss(self):
        """Test cache miss."""
        cache = Cache()
        result = cache.get("nonexistent")
        self.assertIsNone(result)
    
    def test_cache_clear(self):
        """Test clearing cache."""
        cache = Cache()
        cache.set("value1", 300, "key1")
        cache.set("value2", 300, "key2")
        cache.clear()
        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))
    
    def test_get_stats(self):
        """Test getting cache stats."""
        cache = Cache()
        cache.set("value", 300, "key")
        stats = cache.get_stats()
        self.assertIn("total_entries", stats)
        self.assertIn("valid_entries", stats)


class TestSentimentAnalyzer(unittest.TestCase):
    """Tests for SentimentAnalyzer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = SentimentConfig(
            keywords=["BTC", "Bitcoin"],
            sources=[DataSource.TWITTER],
            window_hours=24
        )
        self.analyzer = SentimentAnalyzer(self.config)
    
    def test_initialization(self):
        """Test analyzer initialization."""
        self.assertEqual(self.analyzer.config.keywords, ["BTC", "Bitcoin"])
        self.assertEqual(len(self.analyzer.config.sources), 1)
    
    def test_default_initialization(self):
        """Test analyzer with default config."""
        analyzer = SentimentAnalyzer()
        self.assertIsNotNone(analyzer.config)
        self.assertIsNotNone(analyzer.cache)
        self.assertIsNotNone(analyzer.api_keys)
    
    def test_heuristic_sentiment_positive(self):
        """Test positive sentiment detection."""
        text = "Bitcoin is amazing and going to the moon! Bullish!"
        polarity, subjectivity = self.analyzer._heuristic_sentiment(text)
        self.assertGreater(polarity, 0)
    
    def test_heuristic_sentiment_negative(self):
        """Test negative sentiment detection."""
        text = "Bitcoin is crashing badly. Bearish market."
        polarity, subjectivity = self.analyzer._heuristic_sentiment(text)
        self.assertLess(polarity, 0)
    
    def test_heuristic_sentiment_neutral(self):
        """Test neutral sentiment detection."""
        text = "The sky is blue."
        polarity, subjectivity = self.analyzer._heuristic_sentiment(text)
        self.assertEqual(polarity, 0.0)
    
    def test_analyze_single_post(self):
        """Test analyzing a single post."""
        post = SocialPost(
            source=DataSource.TWITTER,
            content="Bitcoin is looking great today!",
            timestamp=datetime.now(),
            engagement=50
        )
        result = self.analyzer._analyze_single_post(post)
        self.assertIsInstance(result, SentimentResult)
        self.assertEqual(result.post, post)
        self.assertIn("BTC", result.keywords_found)
    
    def test_analyze_sentiment_empty(self):
        """Test analyzing empty post list."""
        results = self.analyzer.analyze_sentiment([])
        self.assertEqual(results, [])
    
    def test_generate_mock_data(self):
        """Test mock data generation."""
        posts = self.analyzer._generate_mock_data(
            DataSource.TWITTER, ["BTC"], 10
        )
        self.assertEqual(len(posts), 10)
        for post in posts:
            self.assertEqual(post.source, DataSource.TWITTER)
            self.assertIsNotNone(post.content)
    
    def test_detect_trends_empty(self):
        """Test trend detection with no data."""
        trend = self.analyzer.detect_trends()
        self.assertEqual(trend.mention_count, 0)
        self.assertEqual(trend.trend_direction, "neutral")
    
    def test_detect_trends_with_data(self):
        """Test trend detection with sample data."""
        # Add some results to history
        for i in range(5):
            post = SocialPost(
                source=DataSource.TWITTER,
                content=f"Post {i}",
                timestamp=datetime.now() - timedelta(hours=i)
            )
            result = SentimentResult(
                post=post,
                polarity=0.1 * i,
                subjectivity=0.5,
                confidence=0.8
            )
            self.analyzer.results_history.append(result)
        
        trend = self.analyzer.detect_trends()
        self.assertEqual(trend.mention_count, 5)
        self.assertIsNotNone(trend.momentum)
    
    def test_generate_signals_insufficient_data(self):
        """Test signal generation with insufficient data."""
        signals = self.analyzer.generate_signals()
        self.assertEqual(signals, [])  # Should return empty due to min_mentions
    
    def test_generate_signals_bullish(self):
        """Test bullish signal generation."""
        # Add positive sentiment results
        for i in range(15):
            post = SocialPost(
                source=DataSource.TWITTER,
                content="Bitcoin is amazing!",
                timestamp=datetime.now() - timedelta(minutes=i*10),
                engagement=100
            )
            result = SentimentResult(
                post=post,
                polarity=0.6,  # Positive
                subjectivity=0.7,
                confidence=0.9,
                keywords_found=["BTC"]
            )
            self.analyzer.results_history.append(result)
        
        signals = self.analyzer.generate_signals()
        self.assertGreater(len(signals), 0)
        self.assertEqual(signals[0].signal, SentimentSignal.STRONGLY_BULLISH)
        self.assertEqual(signals[0].recommended_action, "STRONG BUY")
    
    def test_generate_signals_bearish(self):
        """Test bearish signal generation."""
        # Add negative sentiment results
        for i in range(15):
            post = SocialPost(
                source=DataSource.REDDIT,
                content="Bitcoin is crashing!",
                timestamp=datetime.now() - timedelta(minutes=i*10),
                engagement=50
            )
            result = SentimentResult(
                post=post,
                polarity=-0.6,  # Negative
                subjectivity=0.7,
                confidence=0.9,
                keywords_found=["BTC"]
            )
            self.analyzer.results_history.append(result)
        
        signals = self.analyzer.generate_signals()
        self.assertGreater(len(signals), 0)
        self.assertEqual(signals[0].signal, SentimentSignal.STRONGLY_BEARISH)
        self.assertEqual(signals[0].recommended_action, "STRONG SELL")
    
    def test_clear_history(self):
        """Test clearing history."""
        # Add some data
        self.analyzer.posts_history.append(Mock())
        self.analyzer.results_history.append(Mock())
        self.analyzer.cache.set("value", 300, "key")
        
        self.analyzer.clear_history()
        
        self.assertEqual(len(self.analyzer.posts_history), 0)
        self.assertEqual(len(self.analyzer.results_history), 0)
    
    def test_get_summary(self):
        """Test getting analyzer summary."""
        summary = self.analyzer.get_summary()
        self.assertIn("config", summary)
        self.assertIn("history", summary)
        self.assertIn("rate_limits", summary)
        self.assertIn("cache", summary)


class TestSentimentSignals(unittest.TestCase):
    """Tests for signal generation logic."""
    
    def test_signal_values(self):
        """Test signal enum values."""
        self.assertEqual(SentimentSignal.STRONGLY_BULLISH.value, 2)
        self.assertEqual(SentimentSignal.BULLISH.value, 1)
        self.assertEqual(SentimentSignal.NEUTRAL.value, 0)
        self.assertEqual(SentimentSignal.BEARISH.value, -1)
        self.assertEqual(SentimentSignal.STRONGLY_BEARISH.value, -2)


class TestDataSources(unittest.TestCase):
    """Tests for data source enum."""
    
    def test_source_values(self):
        """Test data source enum values."""
        self.assertEqual(DataSource.TWITTER.value, "twitter")
        self.assertEqual(DataSource.REDDIT.value, "reddit")
        self.assertEqual(DataSource.NEWS.value, "news")
        self.assertEqual(DataSource.ALL.value, "all")


class TestCreateAnalyzer(unittest.TestCase):
    """Tests for create_analyzer convenience function."""
    
    def test_create_analyzer_basic(self):
        """Test creating analyzer with basic config."""
        analyzer = create_analyzer(
            keywords=["ETH", "Ethereum"],
            bullish_threshold=0.3
        )
        self.assertIsInstance(analyzer, SentimentAnalyzer)
        self.assertEqual(analyzer.config.keywords, ["ETH", "Ethereum"])
        self.assertEqual(analyzer.config.bullish_threshold, 0.3)
    
    def test_create_analyzer_with_api_keys(self):
        """Test creating analyzer with API keys."""
        keys = {"twitter": "key1", "newsapi": "key2"}
        analyzer = create_analyzer(
            keywords=["BTC"],
            api_keys=keys
        )
        self.assertTrue(analyzer.api_keys.has_key("twitter"))
        self.assertTrue(analyzer.api_keys.has_key("newsapi"))


class TestTrendDetection(unittest.TestCase):
    """Tests for trend detection functionality."""
    
    def setUp(self):
        self.config = SentimentConfig(
            keywords=["TEST"],
            window_hours=24
        )
        self.analyzer = SentimentAnalyzer(self.config)
    
    def test_rising_trend(self):
        """Test detecting rising sentiment trend."""
        # Create posts with increasing sentiment
        for i in range(10):
            post = SocialPost(
                source=DataSource.TWITTER,
                content=f"Post {i}",
                timestamp=datetime.now() - timedelta(hours=10-i)
            )
            result = SentimentResult(
                post=post,
                polarity=-0.5 + i * 0.1,  # Increasing from -0.5 to 0.4
                subjectivity=0.5,
                confidence=0.8
            )
            self.analyzer.results_history.append(result)
        
        trend = self.analyzer.detect_trends()
        self.assertEqual(trend.trend_direction, "rising")
        self.assertGreater(trend.momentum, 0)
    
    def test_falling_trend(self):
        """Test detecting falling sentiment trend."""
        # Create posts with decreasing sentiment
        for i in range(10):
            post = SocialPost(
                source=DataSource.TWITTER,
                content=f"Post {i}",
                timestamp=datetime.now() - timedelta(hours=10-i)
            )
            result = SentimentResult(
                post=post,
                polarity=0.5 - i * 0.1,  # Decreasing from 0.5 to -0.4
                subjectivity=0.5,
                confidence=0.8
            )
            self.analyzer.results_history.append(result)
        
        trend = self.analyzer.detect_trends()
        self.assertEqual(trend.trend_direction, "falling")
        self.assertLess(trend.momentum, 0)
    
    def test_neutral_trend(self):
        """Test detecting neutral sentiment trend."""
        # Create posts with stable sentiment
        for i in range(10):
            post = SocialPost(
                source=DataSource.TWITTER,
                content=f"Post {i}",
                timestamp=datetime.now() - timedelta(hours=10-i)
            )
            result = SentimentResult(
                post=post,
                polarity=0.1,  # Stable
                subjectivity=0.5,
                confidence=0.8
            )
            self.analyzer.results_history.append(result)
        
        trend = self.analyzer.detect_trends()
        self.assertEqual(trend.trend_direction, "neutral")
    
    def test_volatility_calculation(self):
        """Test volatility calculation."""
        # Create posts with high variance
        polarities = [0.8, -0.7, 0.9, -0.8, 0.7]
        for i, polarity in enumerate(polarities):
            post = SocialPost(
                source=DataSource.TWITTER,
                content=f"Post {i}",
                timestamp=datetime.now() - timedelta(hours=i)
            )
            result = SentimentResult(
                post=post,
                polarity=polarity,
                subjectivity=0.5,
                confidence=0.8
            )
            self.analyzer.results_history.append(result)
        
        trend = self.analyzer.detect_trends()
        self.assertGreater(trend.volatility, 0)


class TestIntegration(unittest.TestCase):
    """Integration tests for the full pipeline."""
    
    def test_full_pipeline(self):
        """Test the complete analysis pipeline."""
        analyzer = create_analyzer(
            keywords=["MOCK"],
            sources=[DataSource.TWITTER],
            min_mentions=5,
            window_hours=24
        )
        
        # Step 1: Fetch mock data
        posts = analyzer.fetch_social_data(max_results=20)
        self.assertGreater(len(posts), 0)
        
        # Step 2: Analyze sentiment
        results = analyzer.analyze_sentiment(posts)
        self.assertEqual(len(results), len(posts))
        
        # Step 3: Detect trends
        trend = analyzer.detect_trends()
        self.assertIsInstance(trend, TrendResult)
        
        # Step 4: Generate signals (may or may not have enough data)
        signals = analyzer.generate_signals(results, trend)
        # Either we have signals or not depending on mock data
        
        # Verify analyzer state
        summary = analyzer.get_summary()
        self.assertGreater(summary["history"]["posts"], 0)
        self.assertGreater(summary["history"]["results"], 0)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""
    
    def test_empty_keywords(self):
        """Test behavior with empty keywords."""
        config = SentimentConfig(keywords=[], sources=[DataSource.TWITTER])
        analyzer = SentimentAnalyzer(config)
        posts = analyzer.fetch_social_data()
        self.assertEqual(posts, [])  # Should return empty with no keywords
    
    def test_very_long_content(self):
        """Test handling very long content."""
        analyzer = create_analyzer(keywords=["TEST"])
        long_content = "BTC " * 10000
        post = SocialPost(
            source=DataSource.TWITTER,
            content=long_content,
            timestamp=datetime.now()
        )
        result = analyzer._analyze_single_post(post)
        self.assertIsInstance(result, SentimentResult)
    
    def test_special_characters(self):
        """Test handling special characters in content."""
        analyzer = create_analyzer(keywords=["BTC"])
        content = "Bitcoin 🚀🌙! BTC @ $50,000 #crypto $BTC"
        post = SocialPost(
            source=DataSource.TWITTER,
            content=content,
            timestamp=datetime.now()
        )
        result = analyzer._analyze_single_post(post)
        self.assertIn("BTC", result.keywords_found)
    
    def test_future_timestamp(self):
        """Test handling future timestamps."""
        analyzer = create_analyzer(keywords=["TEST"])
        post = SocialPost(
            source=DataSource.TWITTER,
            content="Test",
            timestamp=datetime.now() + timedelta(hours=1)
        )
        result = SentimentResult(
            post=post,
            polarity=0.5,
            subjectivity=0.5,
            confidence=0.8
        )
        analyzer.results_history.append(result)
        
        trend = analyzer.detect_trends()
        self.assertEqual(trend.mention_count, 0)  # Future posts excluded


if __name__ == "__main__":
    # Configure logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run all tests
    unittest.main(verbosity=2)
