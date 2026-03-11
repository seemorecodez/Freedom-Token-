# Price Feed Aggregator

Multi-source cryptocurrency price aggregation with outlier detection.

## Quick Start

```python
import asyncio
from price_feed_aggregator import PriceFeedAggregator, PriceFeedConfig

async def main():
    # Use default configuration
    aggregator = PriceFeedAggregator()
    
    # Get BTC/USD price
    result = await aggregator.get_price("BTC", "USD")
    print(f"Price: ${result.price:,.2f}")
    print(f"Confidence: {result.confidence:.1%}")
    print(f"Sources: {result.sources_used}")

asyncio.run(main())
```

## Configuration

```python
from price_feed_aggregator import PriceFeedConfig, AggregationMethod

config = PriceFeedConfig(
    sources=["kraken", "coinbase", "binance", "chainlink"],
    weights={"kraken": 0.25, "coinbase": 0.30, "binance": 0.30, "chainlink": 0.15},
    aggregation_method="trimmed_mean",
    outlier_threshold=3.5,
    cache_ttl=60,
    refresh_interval=30
)

aggregator = PriceFeedAggregator(config)
```

## Aggregation Methods

- **weighted_average**: Default, uses configured weights or equal weights
- **median**: Robust central tendency, ignores extreme values
- **trimmed_mean**: Removes top/bottom N% then takes mean

## Running Tests

```bash
pip install pytest pytest-asyncio aiohttp
python -m pytest test_price_feed_aggregator.py -v
```

## Files

- `SKILL.md` - Full documentation and architecture
- `price_feed_aggregator.py` - Core implementation
- `test_price_feed_aggregator.py` - Unit tests
