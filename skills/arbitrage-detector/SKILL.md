# Arbitrage Detector Skill

Detect cryptocurrency price differences across exchanges for profit opportunities.

## Overview

This skill identifies arbitrage opportunities by comparing prices across multiple exchanges. It supports both simple arbitrage (buy low on one exchange, sell high on another) and triangular arbitrage (exploiting price discrepancies between three trading pairs).

## Features

- **Simple Arbitrage**: Compare prices across exchanges for the same trading pair
- **Triangular Arbitrage**: Find opportunities across three trading pairs
- **Profit Calculation**: Account for trading fees and slippage
- **Simulation Mode**: Test strategies without real API calls
- **Configurable**: Set minimum spread thresholds and exchange preferences

## Quick Start

```python
from arbitrage_detector import ArbitrageDetector, ArbitrageConfig

# Configure detector
config = ArbitrageConfig(
    pairs=["BTC/USDT", "ETH/USDT", "ETH/BTC"],
    min_spread_percent=0.5,  # Minimum 0.5% spread to trigger alert
    exchanges=["binance", "coinbase", "kraken"],
    trading_fees={"binance": 0.001, "coinbase": 0.005, "kraken": 0.0026},
    simulate=True  # Start with simulation mode
)

# Initialize detector
detector = ArbitrageDetector(config)

# Run detection
opportunities = detector.find_opportunities()
for opp in opportunities:
    print(f"Found {opp['type']} arbitrage: {opp['profit_percent']:.2f}% profit")
```

## Configuration

### ArbitrageConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pairs` | List[str] | [] | Trading pairs to monitor (e.g., "BTC/USDT") |
| `min_spread_percent` | float | 0.5 | Minimum spread percentage to consider |
| `exchanges` | List[str] | [] | Exchange IDs to monitor |
| `trading_fees` | Dict[str, float] | {} | Trading fee percentages per exchange |
| `withdrawal_fees` | Dict[str, Dict] | {} | Withdrawal fees per asset per exchange |
| `slippage_percent` | float | 0.1 | Expected slippage percentage |
| `min_profit_usd` | float | 10.0 | Minimum profit in USD to report |
| `simulate` | bool | True | Use simulated data instead of real APIs |

## API Reference

### ArbitrageConfig

Configuration class for the arbitrage detector.

```python
@dataclass
class ArbitrageConfig:
    pairs: List[str]
    min_spread_percent: float = 0.5
    exchanges: List[str] = None
    trading_fees: Dict[str, float] = None
    withdrawal_fees: Dict[str, Dict] = None
    slippage_percent: float = 0.1
    min_profit_usd: float = 10.0
    simulate: bool = True
```

### ArbitrageDetector

Main detector class.

#### Methods

##### `fetch_prices_multi_exchange() -> Dict`
Fetch current prices from all configured exchanges.

Returns:
```python
{
    "BTC/USDT": {
        "binance": {"bid": 50000.0, "ask": 50010.0, "last": 50005.0},
        "coinbase": {"bid": 50020.0, "ask": 50030.0, "last": 50025.0}
    }
}
```

##### `find_opportunities() -> List[Dict]`
Find all arbitrage opportunities across exchanges.

Returns list of opportunity dictionaries:
```python
{
    "type": "simple",  # or "triangular"
    "pair": "BTC/USDT",
    "buy_exchange": "binance",
    "sell_exchange": "coinbase",
    "buy_price": 50010.0,
    "sell_price": 50020.0,
    "spread_percent": 0.02,
    "profit_percent": 0.015,  # After fees
    "profit_usd": 150.0,
    "timestamp": "2024-01-15T10:30:00Z"
}
```

##### `calculate_profit(buy_price, sell_price, volume, buy_exchange, sell_exchange) -> Dict`
Calculate net profit after all fees and slippage.

Parameters:
- `buy_price`: Price to buy at
- `sell_price`: Price to sell at
- `volume`: Trading volume
- `buy_exchange`: Exchange to buy on
- `sell_exchange`: Exchange to sell on

Returns:
```python
{
    "gross_profit": 1000.0,
    "trading_fees": 50.0,
    "withdrawal_fees": 10.0,
    "slippage_cost": 25.0,
    "net_profit": 915.0,
    "net_profit_percent": 1.83,
    "is_profitable": True
}
```

##### `find_triangular_opportunities(base_asset: str = "USDT") -> List[Dict]`
Find triangular arbitrage opportunities.

Example path: USDT → BTC → ETH → USDT

## Simulation Mode

When `simulate=True`, the detector generates realistic price data with controlled spreads for testing:

```python
config = ArbitrageConfig(
    pairs=["BTC/USDT", "ETH/USDT"],
    simulate=True,
    simulate_volatility=0.02  # 2% price variance between exchanges
)
```

## Real API Integration

To use real exchange APIs, set `simulate=False` and configure API credentials:

```python
config = ArbitrageConfig(
    pairs=["BTC/USDT"],
    exchanges=["binance", "coinbase"],
    simulate=False,
    api_keys={
        "binance": {"api_key": "...", "secret": "..."},
        "coinbase": {"api_key": "...", "secret": "..."}
    }
)
```

## Example Use Cases

### Basic Price Monitoring

```python
config = ArbitrageConfig(
    pairs=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    exchanges=["binance", "coinbase", "kraken"],
    min_spread_percent=0.3,
    simulate=True
)

detector = ArbitrageDetector(config)
prices = detector.fetch_prices_multi_exchange()
detector.print_price_table(prices)
```

### Opportunity Alerting

```python
import time

config = ArbitrageConfig(min_spread_percent=0.5, simulate=True)
detector = ArbitrageDetector(config)

while True:
    opportunities = detector.find_opportunities()
    for opp in opportunities:
        if opp["profit_usd"] > 100:
            print(f"🚨 HIGH PROFIT: {opp['pair']} - ${opp['profit_usd']:.2f}")
    time.sleep(30)
```

### Triangular Arbitrage

```python
config = ArbitrageConfig(
    pairs=["BTC/USDT", "ETH/USDT", "ETH/BTC"],
    simulate=True
)

detector = ArbitrageDetector(config)
tri_opps = detector.find_triangular_opportunities(base_asset="USDT")
```

## Testing

Run the test suite:

```bash
python -m pytest test_arbitrage_detector.py -v
```

## Notes

- Always start with `simulate=True` to test your configuration
- Real arbitrage requires fast execution and sufficient capital
- Consider withdrawal times and network congestion
- Fees can significantly impact profitability
- Past opportunities don't guarantee future profits
