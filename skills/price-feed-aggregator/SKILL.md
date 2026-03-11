# Price Feed Aggregator

A robust multi-source cryptocurrency price aggregation system with outlier detection and confidence scoring. Don't trust one exchange — aggregate across many.

## Overview

The price feed aggregator fetches cryptocurrency prices from multiple exchanges simultaneously, applies statistical outlier detection, and computes aggregate prices using configurable strategies. This reduces the risk of relying on any single compromised or malfunctioning data source.

## Core Philosophy

**Don't trust, verify.** Single exchange failures, API errors, or market manipulation on one venue can lead to significant losses. By aggregating across multiple independent sources and detecting anomalies, we achieve:

- **Resilience**: No single point of failure
- **Accuracy**: Outlier prices are filtered out
- **Confidence**: Transparent scoring of data quality

## Aggregation Strategies

### 1. Weighted Average
```
price = Σ(price_i × weight_i) / Σ(weights)
```
- Default strategy when weights are configured
- Weights should reflect exchange reliability/volume
- Automatically excludes sources that failed to respond

### 2. Median
```
price = middle_value(sorted(prices))
```
- Highly resistant to outliers
- Best when you want robust central tendency
- Ignores the influence of extreme values entirely

### 3. Trimmed Mean (Winsorized)
```
price = mean(prices after removing top/bottom N%)
```
- Balance between mean and median
- Removes extreme outliers while using more data than median
- Default: trim 10% from each end (20% total)

## Outlier Detection

The system uses the **Modified Z-Score** method based on Median Absolute Deviation (MAD):

```
MAD = median(|price_i - median|)
Modified Z-Score = 0.6745 × (price - median) / MAD
```

**Thresholds:**
- `|z-score| > 3.5` → Flagged as outlier
- Suitable for non-normal distributions common in crypto
- More robust than standard z-score for small samples

### Alternative: IQR Method

```
IQR = Q3 - Q1
Lower Bound = Q1 - 1.5 × IQR
Upper Bound = Q3 + 1.5 × IQR
```

## Confidence Scoring

Each aggregated price includes a confidence score (0.0 - 1.0):

| Factor | Weight | Description |
|--------|--------|-------------|
| Response Rate | 25% | % of sources that responded |
| Outlier Ratio | 25% | % of prices that are outliers |
| Price Spread | 25% | Coefficient of variation |
| Source Diversity | 25% | Number of unique exchanges |

```
Confidence = 0.25 × response_rate + 0.25 × (1 - outlier_ratio) 
           + 0.25 × spread_score + 0.25 × diversity_score
```

## Supported Sources

| Exchange | API Type | Notes |
|----------|----------|-------|
| **Kraken** | REST | Reliable, good for EUR pairs |
| **Coinbase** | REST | US-focused, high liquidity |
| **Binance** | REST | Global volume leader |
| **Chainlink** | Oracle | Decentralized price feeds |

## Configuration

```python
from price_feed_aggregator import PriceFeedConfig

config = PriceFeedConfig(
    sources=["kraken", "coinbase", "binance", "chainlink"],
    weights={"kraken": 0.25, "coinbase": 0.30, "binance": 0.30, "chainlink": 0.15},
    refresh_interval=30,  # seconds
    outlier_threshold=3.5,
    aggregation_method="weighted_average",  # or "median", "trimmed_mean"
    cache_ttl=60,  # seconds
    max_retries=3,
    timeout=5  # seconds per source
)
```

## Usage Examples

### Basic Usage

```python
from price_feed_aggregator import PriceFeedAggregator

aggregator = PriceFeedAggregator()

# Fetch and aggregate BTC/USD
result = await aggregator.get_price("BTC", "USD")
print(f"Price: ${result.price:,.2f}")
print(f"Confidence: {result.confidence:.1%}")
print(f"Sources used: {result.sources_used}")
```

### Custom Configuration

```python
config = PriceFeedConfig(
    sources=["kraken", "coinbase"],
    aggregation_method="median",
    outlier_threshold=2.5
)
aggregator = PriceFeedAggregator(config)
result = await aggregator.get_price("ETH", "USD")
```

### Manual Aggregation

```python
prices = {
    "kraken": 45231.50,
    "coinbase": 45228.00,
    "binance": 45235.25,
    "chainlink": 45230.00
}

# Detect outliers
outliers = detect_outliers(prices, threshold=3.5)
# Returns: {} or {"binance": 45235.25} if it were an outlier

# Aggregate with trimmed mean
price = aggregate_price(prices, method="trimmed_mean", trim_percent=0.1)
```

## Cache Behavior

- In-memory cache with configurable TTL
- Cache key: `{base}_{quote}_{aggregation_method}`
- Background refresh option available
- Cache statistics tracked for monitoring

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Source timeout | Log warning, exclude from aggregation |
| All sources fail | Raise `PriceFeedException` |
| Single outlier | Exclude, continue with remaining |
| All prices are outliers | Return median with low confidence |
| Rate limited | Backoff retry with jitter |

## Rate Limiting & Best Practices

1. **Respect API limits**: Default 30s refresh is conservative
2. **Use caching**: Avoid redundant API calls
3. **Monitor confidence**: Low confidence indicates data issues
4. **Set alerts**: On outlier spikes or source failures
5. **Fallback sources**: Always have backup exchanges

## Architecture

```
┌─────────────────┐
│  Price Request  │
└────────┬────────┘
         ▼
┌─────────────────┐     ┌─────────────┐
│   Check Cache   │────▶│  Return     │
└────────┬────────┘     │  Cached     │
         │ Miss        └─────────────┘
         ▼
┌─────────────────┐
│ Fetch All Sources│ (Concurrent)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Detect Outliers │
└────────┬────────┘
         ▼
┌─────────────────┐
│    Aggregate    │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Score Confidence│
└────────┬────────┘
         ▼
┌─────────────────┐
│ Update Cache    │
│ Return Result   │
└─────────────────┘
```

## Testing

Run unit tests:
```bash
python -m pytest test_price_feed_aggregator.py -v
```

Test coverage includes:
- All aggregation methods
- Outlier detection scenarios
- Cache behavior
- Error handling
- Source API mocking

## Security Considerations

- No API keys required for public price endpoints
- Input validation on all parameters
- Timeout enforcement on all external calls
- No sensitive data logged

## Future Enhancements

- [ ] WebSocket support for real-time feeds
- [ ] More sources (Bitfinex, OKX, Bybit)
- [ ] Historical aggregation
- [ ] On-chain oracle verification
- [ ] Machine learning outlier detection
