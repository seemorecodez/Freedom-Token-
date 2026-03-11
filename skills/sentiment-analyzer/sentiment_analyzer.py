"""
Sentiment Analyzer for Trading Signals

Analyzes social media and news sentiment to generate trading signals.
Supports Twitter, Reddit, and News sources with configurable NLP scoring.
"""

import os
import time
import json
import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import threading
import logging

# Optional dependencies - will use fallbacks if not available
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SentimentSignal(Enum):
    """Trading signal types based on sentiment analysis."""
    STRONGLY_BULLISH = 2
    BULLISH = 1
    NEUTRAL = 0
    BEARISH = -1
    STRONGLY_BEARISH = -2


class DataSource(Enum):
    """Supported data sources for sentiment analysis."""
    TWITTER = "twitter"
    REDDIT = "reddit"
    NEWS = "news"
    ALL = "all"


@dataclass
class SentimentConfig:
    """Configuration for sentiment analysis.
    
    Attributes:
        sources: List of data sources to analyze
        keywords: Keywords to track (e.g., ['BTC', 'Bitcoin', 'ETH'])
        threshold: Sentiment threshold for signal generation (-1.0 to 1.0)
        bullish_threshold: Minimum score for bullish signal (default: 0.2)
        bearish_threshold: Maximum score for bearish signal (default: -0.2)
        strongly_bullish_threshold: Minimum for strong bullish (default: 0.5)
        strongly_bearish_threshold: Maximum for strong bearish (default: -0.5)
        window_hours: Time window for trend detection (default: 24)
        min_mentions: Minimum mentions required for reliable signal (default: 10)
        cache_duration: Cache duration in seconds (default: 300)
        api_keys: Dictionary of API keys for various sources
        rate_limits: Rate limiting configuration
    """
    sources: List[DataSource] = field(default_factory=lambda: [DataSource.ALL])
    keywords: List[str] = field(default_factory=list)
    threshold: float = 0.0
    bullish_threshold: float = 0.2
    bearish_threshold: float = -0.2
    strongly_bullish_threshold: float = 0.5
    strongly_bearish_threshold: float = -0.5
    window_hours: int = 24
    min_mentions: int = 10
    cache_duration: int = 300
    api_keys: Dict[str, str] = field(default_factory=dict)
    rate_limits: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if DataSource.ALL in self.sources:
            self.sources = [DataSource.TWITTER, DataSource.REDDIT, DataSource.NEWS]


@dataclass
class SocialPost:
    """Represents a social media post or news article."""
    source: DataSource
    content: str
    timestamp: datetime
    author: Optional[str] = None
    engagement: int = 0  # likes, shares, comments, etc.
    url: Optional[str] = None
    raw_data: Dict = field(default_factory=dict)
    
    @property
    def sentiment_weight(self) -> float:
        """Calculate weight based on engagement."""
        # Logarithmic scaling for engagement to prevent outliers
        import math
        if self.engagement <= 0:
            return 1.0
        return 1.0 + math.log10(min(self.engagement, 100000) + 1) * 0.5


@dataclass
class SentimentResult:
    """Result of sentiment analysis for a single post."""
    post: SocialPost
    polarity: float  # -1.0 to 1.0
    subjectivity: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    keywords_found: List[str] = field(default_factory=list)


@dataclass
class TrendResult:
    """Represents sentiment trend over time."""
    start_time: datetime
    end_time: datetime
    sentiment_scores: List[float] = field(default_factory=list)
    momentum: float = 0.0  # Rate of change
    volatility: float = 0.0  # Standard deviation
    trend_direction: str = "neutral"  # "rising", "falling", "neutral"
    mention_count: int = 0


@dataclass
class TradingSignal:
    """Generated trading signal from sentiment analysis."""
    signal: SentimentSignal
    confidence: float
    timestamp: datetime
    summary: str
    sources_analyzed: List[DataSource]
    average_sentiment: float
    mention_count: int
    trend_momentum: float
    recommended_action: str
    metadata: Dict = field(default_factory=dict)


class RateLimiter:
    """Rate limiter for API calls with token bucket algorithm."""
    
    def __init__(self, calls: int = 100, period: int = 900):
        """Initialize rate limiter.
        
        Args:
            calls: Maximum number of calls allowed
            period: Time period in seconds (default 15 minutes)
        """
        self.calls = calls
        self.period = period
        self.tokens = calls
        self.last_update = time.time()
        self.lock = threading.Lock()
        self.call_history: deque = deque(maxlen=calls)
    
    def _add_tokens(self):
        """Add tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        tokens_to_add = (elapsed / self.period) * self.calls
        self.tokens = min(self.calls, self.tokens + tokens_to_add)
        self.last_update = now
    
    def acquire(self, blocking: bool = True) -> bool:
        """Try to acquire a token for API call.
        
        Args:
            blocking: Whether to block until token available
            
        Returns:
            True if token acquired, False otherwise
        """
        with self.lock:
            self._add_tokens()
            
            if self.tokens >= 1:
                self.tokens -= 1
                self.call_history.append(time.time())
                return True
            
            if not blocking:
                return False
            
            # Calculate wait time
            wait_time = (1 - self.tokens) * (self.period / self.calls)
        
        if blocking:
            time.sleep(wait_time)
            return self.acquire(blocking=True)
        
        return False
    
    def get_wait_time(self) -> float:
        """Get estimated wait time for next token."""
        with self.lock:
            self._add_tokens()
            if self.tokens >= 1:
                return 0.0
            return (1 - self.tokens) * (self.period / self.calls)
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        with self.lock:
            return {
                "tokens_available": self.tokens,
                "max_tokens": self.calls,
                "period_seconds": self.period,
                "recent_calls": len(self.call_history),
                "wait_time_seconds": self.get_wait_time()
            }


class APIKeyManager:
    """Manages API keys with validation and rotation support."""
    
    def __init__(self, keys: Dict[str, str] = None):
        """Initialize with API keys.
        
        Args:
            keys: Dictionary of service_name -> api_key
        """
        self.keys: Dict[str, str] = keys or {}
        self._validated: Dict[str, bool] = {}
        self._usage_count: Dict[str, int] = {}
    
    def get_key(self, service: str) -> Optional[str]:
        """Get API key for a service.
        
        Args:
            service: Service name (twitter, reddit, newsapi, etc.)
            
        Returns:
            API key or None if not configured
        """
        # Check environment variables first
        env_key = os.getenv(f"{service.upper()}_API_KEY")
        if env_key:
            return env_key
        
        # Fall back to configured keys
        return self.keys.get(service)
    
    def set_key(self, service: str, key: str):
        """Set API key for a service."""
        self.keys[service] = key
        self._validated[service] = False
    
    def has_key(self, service: str) -> bool:
        """Check if API key is available for service."""
        return self.get_key(service) is not None
    
    def record_usage(self, service: str):
        """Record API call usage."""
        self._usage_count[service] = self._usage_count.get(service, 0) + 1
    
    def get_usage(self, service: str) -> int:
        """Get usage count for a service."""
        return self._usage_count.get(service, 0)


class Cache:
    """Simple in-memory cache with TTL."""
    
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._data: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()
    
    def _make_key(self, *args, **kwargs) -> str:
        """Create cache key from arguments."""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, *args, **kwargs) -> Optional[Any]:
        """Get cached value if not expired."""
        key = self._make_key(*args, **kwargs)
        with self._lock:
            if key in self._data:
                value, expiry = self._data[key]
                if time.time() < expiry:
                    return value
                del self._data[key]
        return None
    
    def set(self, value: Any, ttl: int = None, *args, **kwargs):
        """Cache value with TTL."""
        key = self._make_key(*args, **kwargs)
        ttl = ttl or self.default_ttl
        with self._lock:
            self._data[key] = (value, time.time() + ttl)
    
    def clear(self):
        """Clear all cached data."""
        with self._lock:
            self._data.clear()
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            now = time.time()
            valid = sum(1 for _, expiry in self._data.values() if expiry > now)
            return {
                "total_entries": len(self._data),
                "valid_entries": valid,
                "expired_entries": len(self._data) - valid
            }


class SentimentAnalyzer:
    """Main class for sentiment analysis and trading signal generation."""
    
    def __init__(self, config: Optional[SentimentConfig] = None):
        """Initialize sentiment analyzer.
        
        Args:
            config: Configuration for sentiment analysis
        """
        self.config = config or SentimentConfig()
        self.api_keys = APIKeyManager(self.config.api_keys)
        self.cache = Cache(self.config.cache_duration)
        
        # Initialize rate limiters for each source
        self.rate_limiters: Dict[DataSource, RateLimiter] = {}
        for source in self.config.sources:
            limit_config = self.config.rate_limits.get(source.value, {})
            self.rate_limiters[source] = RateLimiter(
                calls=limit_config.get("calls", 100),
                period=limit_config.get("period", 900)
            )
        
        # Data storage
        self.posts_history: List[SocialPost] = []
        self.results_history: List[SentimentResult] = []
        
        logger.info(f"SentimentAnalyzer initialized with sources: {[s.value for s in self.config.sources]}")
    
    def fetch_social_data(self, keywords: List[str] = None, 
                         sources: List[DataSource] = None,
                         max_results: int = 100) -> List[SocialPost]:
        """Fetch social media and news data.
        
        Args:
            keywords: Keywords to search for (uses config if not provided)
            sources: Sources to fetch from (uses config if not provided)
            max_results: Maximum results per source
            
        Returns:
            List of SocialPost objects
        """
        keywords = keywords or self.config.keywords
        sources = sources or self.config.sources
        all_posts: List[SocialPost] = []
        
        if not keywords:
            logger.warning("No keywords specified for social data fetch")
            return all_posts
        
        for source in sources:
            try:
                if source == DataSource.TWITTER:
                    posts = self._fetch_twitter(keywords, max_results)
                elif source == DataSource.REDDIT:
                    posts = self._fetch_reddit(keywords, max_results)
                elif source == DataSource.NEWS:
                    posts = self._fetch_news(keywords, max_results)
                else:
                    continue
                
                all_posts.extend(posts)
                logger.info(f"Fetched {len(posts)} posts from {source.value}")
                
            except Exception as e:
                logger.error(f"Error fetching from {source.value}: {e}")
        
        # Store in history
        self.posts_history.extend(all_posts)
        
        # Trim history to avoid memory issues
        max_history = 10000
        if len(self.posts_history) > max_history:
            self.posts_history = self.posts_history[-max_history:]
        
        return all_posts
    
    def _fetch_twitter(self, keywords: List[str], max_results: int) -> List[SocialPost]:
        """Fetch tweets matching keywords."""
        posts: List[SocialPost] = []
        
        # Check rate limit
        limiter = self.rate_limiters.get(DataSource.TWITTER)
        if limiter and not limiter.acquire(blocking=False):
            logger.warning("Twitter rate limit exceeded, skipping")
            return posts
        
        # Check for API key
        if not self.api_keys.has_key("twitter"):
            logger.debug("No Twitter API key, using mock data")
            return self._generate_mock_data(DataSource.TWITTER, keywords, max_results)
        
        if not HAS_REQUESTS:
            logger.warning("requests library not available for Twitter API")
            return posts
        
        try:
            # Twitter API v2 endpoint
            bearer_token = self.api_keys.get_key("twitter")
            headers = {"Authorization": f"Bearer {bearer_token}"}
            
            query = " OR ".join(keywords)
            url = "https://api.twitter.com/2/tweets/search/recent"
            params = {
                "query": query,
                "max_results": min(max_results, 100),
                "tweet.fields": "created_at,public_metrics,author_id"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            self.api_keys.record_usage("twitter")
            
            if response.status_code == 200:
                data = response.json()
                for tweet in data.get("data", []):
                    metrics = tweet.get("public_metrics", {})
                    post = SocialPost(
                        source=DataSource.TWITTER,
                        content=tweet.get("text", ""),
                        timestamp=datetime.fromisoformat(
                            tweet["created_at"].replace("Z", "+00:00")
                        ),
                        author=tweet.get("author_id"),
                        engagement=metrics.get("like_count", 0) + metrics.get("retweet_count", 0),
                        raw_data=tweet
                    )
                    posts.append(post)
            else:
                logger.error(f"Twitter API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Twitter fetch error: {e}")
        
        return posts
    
    def _fetch_reddit(self, keywords: List[str], max_results: int) -> List[SocialPost]:
        """Fetch Reddit posts matching keywords."""
        posts: List[SocialPost] = []
        
        # Check rate limit
        limiter = self.rate_limiters.get(DataSource.REDDIT)
        if limiter and not limiter.acquire(blocking=False):
            logger.warning("Reddit rate limit exceeded, skipping")
            return posts
        
        if not HAS_REQUESTS:
            logger.warning("requests library not available for Reddit API")
            return posts
        
        try:
            # Reddit search API (public, limited)
            headers = {"User-Agent": "SentimentAnalyzer/1.0"}
            
            for keyword in keywords[:3]:  # Limit to first 3 keywords
                url = f"https://www.reddit.com/search.json"
                params = {
                    "q": keyword,
                    "sort": "new",
                    "limit": min(max_results // len(keywords), 25)
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=30)
                self.api_keys.record_usage("reddit")
                
                if response.status_code == 200:
                    data = response.json()
                    for child in data.get("data", {}).get("children", []):
                        post_data = child.get("data", {})
                        post = SocialPost(
                            source=DataSource.REDDIT,
                            content=post_data.get("title", "") + " " + post_data.get("selftext", ""),
                            timestamp=datetime.fromtimestamp(post_data.get("created_utc", 0)),
                            author=post_data.get("author"),
                            engagement=post_data.get("ups", 0) + post_data.get("num_comments", 0),
                            url=f"https://reddit.com{post_data.get('permalink', '')}",
                            raw_data=post_data
                        )
                        posts.append(post)
                        
        except Exception as e:
            logger.error(f"Reddit fetch error: {e}")
        
        return posts
    
    def _fetch_news(self, keywords: List[str], max_results: int) -> List[SocialPost]:
        """Fetch news articles matching keywords."""
        posts: List[SocialPost] = []
        
        # Check rate limit
        limiter = self.rate_limiters.get(DataSource.NEWS)
        if limiter and not limiter.acquire(blocking=False):
            logger.warning("News rate limit exceeded, skipping")
            return posts
        
        # Check for API key
        if not self.api_keys.has_key("newsapi"):
            logger.debug("No NewsAPI key, using mock data")
            return self._generate_mock_data(DataSource.NEWS, keywords, max_results)
        
        if not HAS_REQUESTS:
            logger.warning("requests library not available for News API")
            return posts
        
        try:
            api_key = self.api_keys.get_key("newsapi")
            query = " OR ".join(keywords)
            
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "sortBy": "publishedAt",
                "pageSize": min(max_results, 100),
                "apiKey": api_key,
                "language": "en"
            }
            
            response = requests.get(url, params=params, timeout=30)
            self.api_keys.record_usage("newsapi")
            
            if response.status_code == 200:
                data = response.json()
                for article in data.get("articles", []):
                    post = SocialPost(
                        source=DataSource.NEWS,
                        content=article.get("title", "") + " " + article.get("description", ""),
                        timestamp=datetime.fromisoformat(
                            article["publishedAt"].replace("Z", "+00:00")
                        ),
                        author=article.get("author"),
                        engagement=0,  # News articles don't have engagement metrics
                        url=article.get("url"),
                        raw_data=article
                    )
                    posts.append(post)
            else:
                logger.error(f"NewsAPI error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"News fetch error: {e}")
        
        return posts
    
    def _generate_mock_data(self, source: DataSource, keywords: List[str], 
                           count: int) -> List[SocialPost]:
        """Generate mock data for testing when APIs unavailable."""
        posts: List[SocialPost] = []
        sentiments = [
            ("Bullish on", 0.8), ("Bearish on", -0.7), ("Excited about", 0.6),
            ("Concerned about", -0.5), ("Neutral on", 0.0), ("Optimistic about", 0.7),
            ("Pessimistic about", -0.6), ("Great news for", 0.9), ("Bad news for", -0.8)
        ]
        
        for i in range(min(count, 20)):
            keyword = keywords[i % len(keywords)] if keywords else "crypto"
            sentiment, score = sentiments[i % len(sentiments)]
            
            content = f"{sentiment} {keyword}! Market looking {'strong' if score > 0 else 'weak'}. #{keyword}"
            
            post = SocialPost(
                source=source,
                content=content,
                timestamp=datetime.now() - timedelta(hours=i),
                author=f"user_{i}",
                engagement=max(0, int(100 * abs(score)) - i * 5)
            )
            posts.append(post)
        
        return posts
    
    def analyze_sentiment(self, posts: List[SocialPost] = None,
                         use_cache: bool = True) -> List[SentimentResult]:
        """Analyze sentiment of social posts.
        
        Args:
            posts: Posts to analyze (fetches new data if None)
            use_cache: Whether to use cached results
            
        Returns:
            List of SentimentResult objects
        """
        if posts is None:
            cache_key = ("posts", tuple(self.config.keywords))
            if use_cache:
                cached = self.cache.get(*cache_key)
                if cached:
                    posts = cached
                else:
                    posts = self.fetch_social_data()
                    self.cache.set(posts, None, *cache_key)
            else:
                posts = self.fetch_social_data()
        
        results: List[SentimentResult] = []
        
        for post in posts:
            try:
                result = self._analyze_single_post(post)
                results.append(result)
            except Exception as e:
                logger.error(f"Error analyzing post: {e}")
        
        # Store in history
        self.results_history.extend(results)
        
        # Trim history
        max_history = 10000
        if len(self.results_history) > max_history:
            self.results_history = self.results_history[-max_history:]
        
        return results
    
    def _analyze_single_post(self, post: SocialPost) -> SentimentResult:
        """Analyze sentiment of a single post."""
        content = post.content.lower()
        
        # Find keywords in content
        keywords_found = [
            kw for kw in self.config.keywords 
            if kw.lower() in content
        ]
        
        # Use TextBlob if available, otherwise use simple heuristic
        if HAS_TEXTBLOB:
            blob = TextBlob(post.content)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
        else:
            polarity, subjectivity = self._heuristic_sentiment(post.content)
        
        # Calculate confidence based on subjectivity and content length
        confidence = min(1.0, subjectivity * 0.5 + len(post.content) / 500 * 0.5)
        
        # Weight by engagement
        weighted_polarity = polarity * post.sentiment_weight
        
        return SentimentResult(
            post=post,
            polarity=weighted_polarity,
            subjectivity=subjectivity,
            confidence=confidence,
            keywords_found=keywords_found
        )
    
    def _heuristic_sentiment(self, text: str) -> Tuple[float, float]:
        """Simple heuristic sentiment analysis as fallback."""
        text = text.lower()
        
        # Positive and negative word lists
        positive_words = {
            'good', 'great', 'excellent', 'amazing', 'awesome', 'bullish', 'moon',
            'pump', 'gain', 'profit', 'win', 'success', 'growth', 'surge', 'rally',
            'breakout', 'strong', 'buy', 'hodl', 'hold', 'support', 'resistance',
            ' ATH', ' all time high', 'mooning', 'rocket', 'explode', 'skyrocket'
        }
        
        negative_words = {
            'bad', 'terrible', 'awful', 'bearish', 'dump', 'crash', 'loss', 'lose',
            'fail', 'failure', 'decline', 'drop', 'fall', 'sell', 'short', 'panic',
            'fear', 'worry', 'concern', 'risk', 'danger', 'scam', 'rug', 'dumping',
            'tank', 'plunge', 'collapse', 'death', 'bear market', 'correction'
        }
        
        words = text.split()
        pos_count = sum(1 for w in words if any(pw in w for pw in positive_words))
        neg_count = sum(1 for w in words if any(nw in w for nw in negative_words))
        
        total = pos_count + neg_count
        if total == 0:
            return 0.0, 0.0
        
        polarity = (pos_count - neg_count) / total
        subjectivity = min(1.0, total / len(words) * 5) if words else 0.0
        
        return polarity, subjectivity
    
    def detect_trends(self, hours: int = None, 
                     results: List[SentimentResult] = None) -> TrendResult:
        """Detect sentiment trends over time.
        
        Args:
            hours: Time window in hours (uses config if None)
            results: Results to analyze (uses history if None)
            
        Returns:
            TrendResult with trend analysis
        """
        hours = hours or self.config.window_hours
        cutoff = datetime.now() - timedelta(hours=hours)
        
        if results is None:
            results = self.results_history
        
        # Filter results within time window
        recent_results = [
            r for r in results 
            if r.post.timestamp >= cutoff
        ]
        
        if not recent_results:
            return TrendResult(
                start_time=cutoff,
                end_time=datetime.now(),
                mention_count=0
            )
        
        # Sort by timestamp
        recent_results.sort(key=lambda r: r.post.timestamp)
        
        # Extract sentiment scores
        scores = [r.polarity for r in recent_results]
        timestamps = [r.post.timestamp for r in recent_results]
        
        # Calculate momentum (rate of change)
        if len(scores) >= 2:
            # Simple linear regression slope
            n = len(scores)
            x = list(range(n))
            x_mean = sum(x) / n
            y_mean = sum(scores) / n
            
            numerator = sum((x[i] - x_mean) * (scores[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
            
            momentum = numerator / denominator if denominator != 0 else 0.0
        else:
            momentum = 0.0
        
        # Calculate volatility (standard deviation)
        if len(scores) >= 2:
            mean_score = sum(scores) / len(scores)
            variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            volatility = variance ** 0.5
        else:
            volatility = 0.0
        
        # Determine trend direction
        if momentum > 0.05:
            trend_direction = "rising"
        elif momentum < -0.05:
            trend_direction = "falling"
        else:
            trend_direction = "neutral"
        
        return TrendResult(
            start_time=timestamps[0],
            end_time=timestamps[-1],
            sentiment_scores=scores,
            momentum=momentum,
            volatility=volatility,
            trend_direction=trend_direction,
            mention_count=len(recent_results)
        )
    
    def generate_signals(self, results: List[SentimentResult] = None,
                        trend: TrendResult = None) -> List[TradingSignal]:
        """Generate trading signals from sentiment analysis.
        
        Args:
            results: Sentiment results to analyze
            trend: Pre-calculated trend result
            
        Returns:
            List of TradingSignal objects
        """
        if results is None:
            results = self.results_history[-100:]  # Last 100 results
        
        if trend is None:
            trend = self.detect_trends(results=results)
        
        signals: List[TradingSignal] = []
        
        if not results or trend.mention_count < self.config.min_mentions:
            logger.warning(f"Insufficient data for signal generation ({trend.mention_count} mentions)")
            return signals
        
        # Calculate weighted average sentiment
        total_weight = sum(r.confidence * r.post.sentiment_weight for r in results)
        weighted_sentiment = sum(
            r.polarity * r.confidence * r.post.sentiment_weight 
            for r in results
        ) / total_weight if total_weight > 0 else 0
        
        # Count by source
        sources = list(set(r.post.source for r in results))
        
        # Determine signal type
        if weighted_sentiment >= self.config.strongly_bullish_threshold:
            signal = SentimentSignal.STRONGLY_BULLISH
            action = "STRONG BUY"
            summary = f"Extremely positive sentiment ({weighted_sentiment:.2f}) with {trend.mention_count} mentions"
        elif weighted_sentiment >= self.config.bullish_threshold:
            signal = SentimentSignal.BULLISH
            action = "BUY"
            summary = f"Positive sentiment ({weighted_sentiment:.2f}) with {trend.mention_count} mentions"
        elif weighted_sentiment <= self.config.strongly_bearish_threshold:
            signal = SentimentSignal.STRONGLY_BEARISH
            action = "STRONG SELL"
            summary = f"Extremely negative sentiment ({weighted_sentiment:.2f}) with {trend.mention_count} mentions"
        elif weighted_sentiment <= self.config.bearish_threshold:
            signal = SentimentSignal.BEARISH
            action = "SELL"
            summary = f"Negative sentiment ({weighted_sentiment:.2f}) with {trend.mention_count} mentions"
        else:
            signal = SentimentSignal.NEUTRAL
            action = "HOLD"
            summary = f"Neutral sentiment ({weighted_sentiment:.2f}) with {trend.mention_count} mentions"
        
        # Calculate confidence based on data quality
        confidence = min(1.0, (
            trend.mention_count / self.config.min_mentions * 0.3 +
            (1 - trend.volatility) * 0.3 +
            trend.momentum * 0.2 if trend.momentum > 0 else 0 +
            sum(r.confidence for r in results) / len(results) * 0.2
        ))
        
        # Create signal
        trading_signal = TradingSignal(
            signal=signal,
            confidence=confidence,
            timestamp=datetime.now(),
            summary=summary,
            sources_analyzed=sources,
            average_sentiment=weighted_sentiment,
            mention_count=trend.mention_count,
            trend_momentum=trend.momentum,
            recommended_action=action,
            metadata={
                "trend_direction": trend.trend_direction,
                "volatility": trend.volatility,
                "time_window_hours": self.config.window_hours
            }
        )
        
        signals.append(trading_signal)
        
        # Log signal
        logger.info(f"Generated signal: {signal.name} (confidence: {confidence:.2f})")
        
        return signals
    
    def get_summary(self) -> Dict:
        """Get summary statistics of the analyzer."""
        return {
            "config": {
                "sources": [s.value for s in self.config.sources],
                "keywords": self.config.keywords,
                "threshold": self.config.threshold
            },
            "history": {
                "posts": len(self.posts_history),
                "results": len(self.results_history)
            },
            "rate_limits": {
                source.value: limiter.get_stats() 
                for source, limiter in self.rate_limiters.items()
            },
            "cache": self.cache.get_stats(),
            "api_usage": {
                service: self.api_keys.get_usage(service)
                for service in ["twitter", "reddit", "newsapi"]
            }
        }
    
    def clear_history(self):
        """Clear all historical data."""
        self.posts_history.clear()
        self.results_history.clear()
        self.cache.clear()
        logger.info("History and cache cleared")


def create_analyzer(keywords: List[str], 
                   api_keys: Dict[str, str] = None,
                   **kwargs) -> SentimentAnalyzer:
    """Convenience function to create a configured analyzer.
    
    Args:
        keywords: Keywords to track
        api_keys: API keys for services
        **kwargs: Additional config options
        
    Returns:
        Configured SentimentAnalyzer
    """
    config = SentimentConfig(
        keywords=keywords,
        api_keys=api_keys or {},
        **kwargs
    )
    return SentimentAnalyzer(config)


# Example usage
if __name__ == "__main__":
    # Create analyzer for Bitcoin
    analyzer = create_analyzer(
        keywords=["BTC", "Bitcoin", "bitcoin"],
        bullish_threshold=0.2,
        bearish_threshold=-0.2,
        window_hours=12
    )
    
    # Fetch and analyze data
    posts = analyzer.fetch_social_data(max_results=50)
    results = analyzer.analyze_sentiment(posts)
    
    # Detect trends
    trend = analyzer.detect_trends()
    
    # Generate signals
    signals = analyzer.generate_signals(results, trend)
    
    # Print results
    for signal in signals:
        print(f"\nSignal: {signal.signal.name}")
        print(f"Action: {signal.recommended_action}")
        print(f"Confidence: {signal.confidence:.2%}")
        print(f"Summary: {signal.summary}")
        print(f"Trend: {trend.trend_direction} (momentum: {trend.momentum:.4f})")
