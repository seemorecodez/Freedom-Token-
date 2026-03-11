# Liquidity Analyzer Skill

Analyze pool depth and slippage before large trades across DeFi venues.

## Overview

This skill provides real-time liquidity analysis for decentralized exchanges (DEXs) including Uniswap, Curve, and SushiSwap. It helps traders and protocols estimate price impact before executing large trades.

## Features

- **Multi-venue support**: Uniswap V2/V3, Curve, SushiSwap
- **Pool depth analysis**: Calculate available liquidity at various price levels
- **Slippage estimation**: Predict price impact for given trade sizes
- **Smart routing**: Find the best venue for your trade
- **Real-time monitoring**: Continuous liquidity tracking

## Quick Start

```python
from liquidity_analyzer import LiquidityAnalyzer, LiquidityConfig

# Configure analyzer
config = LiquidityConfig(
    venues=["uniswap_v3", "curve", "sushiswap"],
    min_depth_eth=100,  # Minimum 100 ETH depth required
)

# Initialize analyzer
analyzer = LiquidityAnalyzer(config)

# Analyze pool depth
pool = await analyzer.analyze_pool_depth(
    token_in="WETH",
    token_out="USDC",
    amount_in=50  # ETH
)

# Calculate slippage
slippage = await analyzer.calculate_slippage(
    token_in="WETH",
    token_out="USDC",
    amount_in=50
)

# Find best venue
best = await analyzer.find_best_venue(
    token_in="WETH",
    token_out="USDC",
    amount_in=50
)
```

## Classes

### LiquidityConfig

Configuration for liquidity analysis.

```python
LiquidityConfig(
    venues: List[str],           # Supported: "uniswap_v2", "uniswap_v3", "curve", "sushiswap"
    min_depth_eth: float = 50,   # Minimum liquidity threshold in ETH
    max_slippage: float = 0.02,  # Max acceptable slippage (2%)
    update_interval: int = 30,    # Seconds between updates
)
```

### LiquidityAnalyzer

Main analyzer class for pool operations.

#### Methods

| Method | Description |
|--------|-------------|
| `analyze_pool_depth(token_in, token_out)` | Returns pool liquidity at various price levels |
| `calculate_slippage(token_in, token_out, amount_in)` | Estimates price impact for trade |
| `find_best_venue(token_in, token_out, amount_in)` | Routes to venue with deepest liquidity |
| `start_monitoring()` | Begins real-time liquidity tracking |
| `stop_monitoring()` | Stops the monitoring loop |

## Response Format

### Pool Depth Analysis

```python
{
    "venue": "uniswap_v3",
    "token_in": "WETH",
    "token_out": "USDC",
    "total_liquidity_usd": 12500000,
    "depth_at_1pct": 150000,      # USD liquidity within 1% of spot
    "depth_at_5pct": 850000,      # USD liquidity within 5% of spot
    "spot_price": 1850.50,
    "timestamp": 1710000000
}
```

### Slippage Calculation

```python
{
    "token_in": "WETH",
    "token_out": "USDC",
    "amount_in": 50,
    "expected_out": 92525.0,
    "price_impact": 0.015,        # 1.5%
    "minimum_out": 91123.75,      # With slippage buffer
    "venue": "uniswap_v3"
}
```

### Best Venue Result

```python
{
    "venue": "curve",
    "reason": "highest_liquidity",
    "liquidity_score": 95,
    "estimated_slippage": 0.008,
    "alternatives": ["uniswap_v3", "sushiswap"]
}
```

## Venue-Specific Notes

### Uniswap V3
- Uses concentrated liquidity positions
- More capital efficient for stable pairs
- Requires fetching tick data

### Curve
- Optimized for stablecoins and correlated assets
- Lower slippage for large stable trades
- Uses bonding curve math

### SushiSwap
- Fork of Uniswap V2
- Good for long-tail assets
- Standard AMM model

## Error Handling

All methods raise `LiquidityError` for:
- Insufficient liquidity
- Invalid token pairs
- Network/connection issues
- Unsupported venues

## Testing

```bash
python -m pytest test_liquidity_analyzer.py -v
```

## Dependencies

- `web3.py` - Ethereum node interaction
- `aiohttp` - Async HTTP requests
- `pytest` - Testing framework

## Configuration Examples

### Conservative (Low Slippage)
```python
config = LiquidityConfig(
    venues=["uniswap_v3", "curve"],
    min_depth_eth=500,
    max_slippage=0.005
)
```

### Aggressive (All Venues)
```python
config = LiquidityConfig(
    venues=["uniswap_v2", "uniswap_v3", "curve", "sushiswap"],
    min_depth_eth=10,
    max_slippage=0.05
)
```
