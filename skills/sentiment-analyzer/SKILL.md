# Sentiment Analyzer Skill

Social media and news sentiment analysis for trading signal generation.

## Overview

The `sentiment-analyzer` skill fetches and analyzes social media posts and news articles to generate trading signals based on sentiment trends.

## Features

- **Multi-Source Support**: Twitter, Reddit, News APIs
- **NLP Sentiment Analysis**: Uses TextBlob or heuristic fallback
- **Trend Detection**: Tracks sentiment momentum over time
- **Trading Signals**: Generates BUY/SELL/HOLD recommendations
- **Rate Limiting**: Built-in rate limiting for API compliance
- **Caching**: Configurable result caching for performance

## Installation

### Dependencies

```bash
# Core (no external dependencies required)
# Works out of the box with heuristic sentiment

# Optional: For better NLP sentiment
pip install textblob

# Optional: For API access
pip install requests

# Optional: For Twitter API
pip install tweepy
```

### API Keys (Optional)

Set environment variables or pass to config:

```bash
export TWITTER_API_KEY="your_key"
export REDDIT_API_KEY="your_key"
export NEWSAPI_API_KEY="your_key"
```

## Usage

### Basic Usage

```python
from sentiment_analyzer import create_analyzer

# Create analyzer
analyzer = create_analyzer(
    keywords=["BTC", "Bitcoin"],
    bullish_threshold=0.2,
    bearish_threshold=-0.2
)

# Fetch data
posts = analyzer.fetch_social_data(max_results=100)

# Analyze sentiment
results = analyzer.analyze_sentiment(posts)

# Generate signals
trend = analyzer.detect_trends()
signals = analyzer.generate_signals(results, trend)

for signal in signals:
    print(f"{signal.signal.name}: {signal.recommended_action}")
```

### Advanced Configuration

```python
from sentiment_analyzer import SentimentAnalyzer, SentimentConfig, DataSource

config = SentimentConfig(
    sources=[DataSource.TWITTER, DataSource.REDDIT],
    keywords=["ETH", "Ethereum", "DeFi"],
    bullish_threshold=0.25,
    bearish_threshold=-0.25,
    strongly_bullish_threshold=0.6,
    strongly_bearish_threshold=-0.6,
    window_hours=6,
    min_mentions=20,
    cache_duration=600,
    api_keys={
        "twitter": "your_key",
        "newsapi": "your_key"
    },
    rate_limits={
        "twitter": {"calls": 100, "period": 900},
        "reddit": {"calls": 60, "period": 600}
    }
)

analyzer = SentimentAnalyzer(config)
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `sources` | List[DataSource] | [ALL] | Data sources to analyze |
| `keywords` | List[str] | [] | Keywords to track |
| `bullish_threshold` | float | 0.2 | Min score for bullish signal |
| `bearish_threshold` | float | -0.2 | Max score for bearish signal |
| `strongly_bullish_threshold` | float | 0.5 | Min for strong bullish |
| `strongly_bearish_threshold` | float | -0.5 | Max for strong bearish |
| `window_hours` | int | 24 | Time window for trends |
| `min_mentions` | int | 10 | Min mentions for reliable signal |
| `cache_duration` | int | 300 | Cache TTL in seconds |
| `api_keys` | Dict | {} | API keys by service |
| `rate_limits` | Dict | {} | Rate limiting config |

## Signal Types

| Signal | Value | Action |
|--------|-------|--------|
| STRONGLY_BULLISH | 2 | STRONG BUY |
| BULLISH | 1 | BUY |
| NEUTRAL | 0 | HOLD |
| BEARISH | -1 | SELL |
| STRONGLY_BEARISH | -2 | STRONG SELL |

## Data Sources

### Twitter
- Requires API key (Bearer token)
- Rate limit: 100 req/15min (default)
- Returns recent tweets matching keywords

### Reddit
- Public API (no key required, limited)
- Rate limit: 60 req/10min (default)
- Searches posts across subreddits

### News
- Requires NewsAPI key
- Rate limit: 100 req/day (free tier)
- Returns recent news articles

## Mock Data

When API keys are not available, the analyzer generates mock data for testing:

```python
# No API keys needed - uses mock data
analyzer = create_analyzer(keywords=["BTC"])
posts = analyzer.fetch_social_data()  # Returns mock posts
```

## Classes

### SentimentAnalyzer
Main class for sentiment analysis.

```python
analyzer = SentimentAnalyzer(config)

# Methods
.fetch_social_data(keywords, sources, max_results) -> List[SocialPost]
.analyze_sentiment(posts, use_cache) -> List[SentimentResult]
.detect_trends(hours, results) -> TrendResult
.generate_signals(results, trend) -> List[TradingSignal]
.get_summary() -> Dict
.clear_history()
```

### SentimentConfig
Configuration dataclass.

```python
config = SentimentConfig(
    sources=[DataSource.TWITTER],
    keywords=["crypto"],
    bullish_threshold=0.3
)
```

### RateLimiter
Token bucket rate limiter.

```python
limiter = RateLimiter(calls=100, period=900)
limiter.acquire(blocking=True)
stats = limiter.get_stats()
```

### APIKeyManager
API key management.

```python
manager = APIKeyManager({"twitter": "key"})
key = manager.get_key("twitter")
manager.record_usage("twitter")
```

## Error Handling

The analyzer handles errors gracefully:

```python
# API errors are logged, mock data used as fallback
# Rate limits are respected with automatic waiting
# Invalid responses are skipped
```

## Testing

Run tests:

```bash
python -m pytest test_sentiment_analyzer.py -v
```

## Limitations

- Free API tiers have rate limits
- Sentiment analysis is heuristic-based without TextBlob
- Mock data used when APIs unavailable
- Historical data limited to in-memory storage

## Future Enhancements

- [ ] Machine learning sentiment model
- [ ] Persistent database storage
- [ ] Real-time streaming support
- [ ] More data sources (Discord, Telegram)
- [ ] Sentiment correlation with price data
