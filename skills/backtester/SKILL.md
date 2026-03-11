# Backtester Skill

A comprehensive historical strategy testing framework for trading strategy evaluation with performance metrics, walk-forward analysis, and strategy comparison.

## Overview

The backtester provides a complete engine for simulating trading strategies on historical data, calculating performance metrics, and validating strategies through walk-forward analysis.

## Features

- **Flexible Data Loading**: Load from Yahoo Finance, CSV files, or synthetic data
- **Strategy Engine**: Execute custom trading strategies with configurable parameters
- **Performance Metrics**: Sharpe ratio, drawdown analysis, win rate, and more
- **Strategy Comparison**: A/B test multiple strategies side-by-side
- **Walk-Forward Analysis**: Out-of-sample testing to prevent overfitting
- **Trade Logging**: Detailed trade records and equity curve generation

## Quick Start

```python
from datetime import datetime, timedelta
from backtester import (
    BacktestConfig, Backtester,
    load_historical_data, example_sma_strategy
)

# Configure backtest
config = BacktestConfig(
    start_date=datetime(2020, 1, 1),
    end_date=datetime(2023, 1, 1),
    initial_capital=100000,
    commission_rate=0.001
)

# Load historical data
data = load_historical_data(
    "AAPL",
    config.start_date,
    config.end_date,
    source="yfinance"
)

# Run backtest
backtester = Backtester(config)
backtester.load_data("AAPL", data)
result = backtester.run_backtest(
    example_sma_strategy,
    {'fast_period': 10, 'slow_period': 30}
)

# View results
print(f"Total Return: {result.total_return:.2f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.2f}%")
```

## Core Classes

### BacktestConfig

Configuration for a backtest run.

```python
config = BacktestConfig(
    start_date=datetime(2020, 1, 1),
    end_date=datetime(2023, 1, 1),
    initial_capital=100000.0,      # Starting capital
    commission_rate=0.001,          # Per-trade commission (0.1%)
    slippage=0.0,                   # Price slippage
    max_position_size=1.0,          # Max position as fraction
    stop_loss_pct=0.05,            # Stop loss (5%)
    take_profit_pct=0.10,          # Take profit (10%)
    symbols=["AAPL"],              # Symbols to trade
    timeframe="1d",                # Data frequency
    allow_short=False              # Allow short selling
)
```

### Backtester

Main backtesting engine.

```python
backtester = Backtester(config)
backtester.load_data("AAPL", price_data)
result = backtester.run_backtest(strategy_function, strategy_params)
```

### BacktestResult

Contains all results from a backtest.

| Attribute | Description |
|-----------|-------------|
| `total_return` | Total return percentage |
| `sharpe_ratio` | Risk-adjusted return metric |
| `max_drawdown` | Maximum peak-to-trough decline |
| `max_drawdown_duration` | Longest drawdown period |
| `win_rate` | Percentage of winning trades |
| `profit_factor` | Gross profit / gross loss |
| `volatility` | Annualized return volatility |
| `calmar_ratio` | Return / max drawdown |
| `sortino_ratio` | Sharpe with downside deviation |
| `trades` | List of Trade objects |
| `equity_curve` | Pandas Series of equity over time |

## Data Loading

### Yahoo Finance

```python
data = load_historical_data(
    "BTC-USD",
    start_date,
    end_date,
    source="yfinance"
)
```

### CSV File

```python
data = load_historical_data(
    "CUSTOM",
    start_date,
    end_date,
    source="csv",
    filepath="/path/to/data.csv"
)
```

CSV format should have columns: `open`, `high`, `low`, `close`, `volume`

### Synthetic Data

```python
data = load_historical_data(
    "TEST",
    start_date,
    end_date,
    source="synthetic",
    trend=0.0001,        # Daily drift
    volatility=0.02,     # Daily volatility
    seed=42              # Random seed
)
```

## Writing Strategies

A strategy is a function that receives data and parameters, returns signals.

```python
def my_strategy(data: pd.DataFrame, params: dict) -> dict:
    """
    Strategy function signature.
    
    Args:
        data: Historical OHLCV data up to current bar
        params: Strategy parameters
    
    Returns:
        Dict with 'action' and optional 'size'
        action: 'buy', 'sell', 'short', or 'hold'
        size: Position size (0.0 to 1.0)
    """
    # Calculate indicators
    sma_fast = data['close'].rolling(params['fast']).mean().iloc[-1]
    sma_slow = data['close'].rolling(params['slow']).mean().iloc[-1]
    
    # Generate signal
    if sma_fast > sma_slow:
        return {'action': 'buy', 'size': 1.0}
    elif sma_fast < sma_slow:
        return {'action': 'sell', 'size': 1.0}
    
    return {'action': 'hold'}
```

## Strategy Comparison

Compare multiple strategies:

```python
from backtester import compare_strategies

results = [result1, result2, result3]
names = ["SMA Cross", "RSI Mean Rev", "Momentum"]

comparison = compare_strategies(results, names)
print(comparison)
```

Output:
```
      Strategy  Total Return (%)  Sharpe Ratio  Max Drawdown (%)  Win Rate (%)
0    SMA Cross             45.2          1.23            -15.3          52.1
1  RSI Mean Rev             38.7          1.15            -12.8          48.5
2     Momentum             52.1          1.45            -18.2          55.3
```

## Walk-Forward Analysis

Prevent overfitting with out-of-sample testing:

```python
from backtester import walk_forward_analysis

# Define parameter grid
param_grid = [
    {'fast_period': 5, 'slow_period': 20},
    {'fast_period': 10, 'slow_period': 30},
    {'fast_period': 15, 'slow_period': 50}
]

# Run walk-forward analysis
wfa_results = walk_forward_analysis(
    data=data,
    strategy=example_sma_strategy,
    strategy_params_list=param_grid,
    train_size=252,      # 1 year training
    test_size=63,        # 3 months testing
    step_size=63,        # Step forward 3 months
    metric='sharpe_ratio'
)

print(f"Avg OOS Return: {wfa_results['aggregated_metrics']['avg_total_return']:.2f}%")
print(f"Avg OOS Sharpe: {wfa_results['aggregated_metrics']['avg_sharpe']:.2f}")
```

## Trade Log & Equity Curve

### Generate Trade Log

```python
from backtester import generate_trade_log

trade_df = generate_trade_log(result, filepath="trades.csv")
print(trade_df[['Entry Time', 'Exit Time', 'P&L ($)', 'P&L (%)']])
```

### Generate Equity Curve

```python
from backtester import generate_equity_curve

equity_df = generate_equity_curve(result, filepath="equity.csv")
# Columns: Timestamp, Equity, Peak, Drawdown (%)
```

## Example Strategies

### SMA Crossover

```python
from backtester import example_sma_strategy

result = backtester.run_backtest(
    example_sma_strategy,
    {'fast_period': 10, 'slow_period': 30}
)
```

### RSI Mean Reversion

```python
from backtester import example_rsi_strategy

result = backtester.run_backtest(
    example_rsi_strategy,
    {'period': 14, 'oversold': 30, 'overbought': 70}
)
```

## Performance Metrics Reference

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Sharpe Ratio** | (Return - Risk Free) / Volatility | >1.0 is good, >2.0 is excellent |
| **Sortino Ratio** | (Return - Risk Free) / Downside Dev | Sharpe using only downside risk |
| **Max Drawdown** | (Peak - Trough) / Peak | Largest peak-to-trough decline |
| **Calmar Ratio** | Annual Return / Max Drawdown | Return per unit of max risk |
| **Profit Factor** | Gross Profit / Gross Loss | >1.0 is profitable, >2.0 is good |
| **Win Rate** | Winning Trades / Total Trades | % of trades that are profitable |

## Installation

```bash
# Core dependencies
pip install pandas numpy

# For Yahoo Finance data
pip install yfinance
```

## Complete Example

```python
from datetime import datetime, timedelta
from backtester import *

# Setup
end = datetime.now()
start = end - timedelta(days=730)

# Load data
data = load_historical_data("AAPL", start, end, source="yfinance")

# Config
config = BacktestConfig(
    start_date=start,
    end_date=end,
    initial_capital=100000,
    commission_rate=0.001,
    stop_loss_pct=0.05
)

# Run backtest
backtester = Backtester(config)
backtester.load_data("AAPL", data)
result = backtester.run_backtest(
    example_sma_strategy,
    {'fast_period': 10, 'slow_period': 30}
)

# Print results
metrics = calculate_metrics(result)
for key, value in metrics.items():
    print(f"{key}: {value}")

# Export
generate_trade_log(result, "trades.csv")
generate_equity_curve(result, "equity.csv")
```

## API Reference

### Functions

- `load_historical_data(symbol, start, end, source, **kwargs)` - Fetch price data
- `calculate_metrics(result)` - Compute performance metrics
- `compare_strategies(results, names)` - Compare multiple strategies
- `walk_forward_analysis(data, strategy, params_list, train_size, test_size, ...)` - OOS testing
- `generate_trade_log(result, filepath)` - Export trade history
- `generate_equity_curve(result, filepath)` - Export equity data

### Classes

- `BacktestConfig` - Configuration dataclass
- `Backtester` - Main engine
- `BacktestResult` - Results container
- `PriceData` - Price data container
- `Trade` - Individual trade record

## License

MIT License - Part of OpenClaw Skills
