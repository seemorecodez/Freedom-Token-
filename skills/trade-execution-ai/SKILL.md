# Trade Execution AI Skill

ML-powered trade execution using RandomForestRegressor + Technical Analysis + Reinforcement Learning.

## Overview

This skill provides intelligent trade execution capabilities by combining:
- **RandomForest Regression** for return prediction
- **Technical Analysis** indicators (RSI, MACD, Bollinger Bands, ATR)
- **Reinforcement Learning** for optimal timing decisions

## Installation

```bash
pip install scikit-learn pandas numpy
```

## Quick Start

```python
from trade_execution_ai import TradeExecutionAI, AIConfig, create_sample_data

# Create sample data or load your own
 df = create_sample_data(n_periods=500)

# Initialize with default config
 ai = TradeExecutionAI()

# Train the model
metrics = ai.fit(df)
print(f"Training R²: {metrics['train_r2']:.3f}")

# Predict trade timing
prediction = ai.predict_trade_timing(df)
print(f"Signal: {prediction['signal']}")
print(f"Confidence: {prediction['confidence']:.2f}")
print(f"Entry: {prediction['optimal_entry_price']}")
print(f"Stop Loss: {prediction['stop_loss']}")
print(f"Take Profit: {prediction['take_profit']}")
```

## Configuration (AIConfig)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `model_type` | RANDOM_FOREST | Type of ML model |
| `features` | [...] | List of feature names to use |
| `confidence_threshold` | 0.7 | Minimum confidence to trade |
| `lookback_window` | 20 | Historical periods to consider |
| `prediction_horizon` | 5 | Periods ahead to predict |
| `n_estimators` | 100 | Trees in RandomForest |
| `max_depth` | 10 | Max tree depth |
| `rsi_period` | 14 | RSI calculation period |
| `macd_fast` | 12 | MACD fast EMA period |
| `macd_slow` | 26 | MACD slow EMA period |
| `macd_signal` | 9 | MACD signal period |
| `bb_period` | 20 | Bollinger Bands period |
| `bb_std` | 2.0 | BB standard deviation multiplier |
| `rl_learning_rate` | 0.01 | RL learning rate |
| `rl_discount_factor` | 0.95 | RL discount factor |
| `rl_exploration_rate` | 0.1 | Initial RL exploration rate |

## Features

### Technical Indicators
- **RSI** - Relative Strength Index (overbought/oversold)
- **MACD** - Moving Average Convergence Divergence (trend/momentum)
- **Bollinger Bands** - Volatility and price position
- **ATR** - Average True Range (volatility measure)
- **Price Momentum** - Returns and trend strength
- **Volume Analysis** - Volume changes and ratios

### ML Model
- RandomForestRegressor for return prediction
- Feature importance analysis
- Prediction confidence based on tree variance

### Reinforcement Learning
- Q-learning for timing optimization
- State discretization for tabular Q-learning
- Epsilon-greedy exploration policy
- Adaptive exploration decay

## API Reference

### TradeExecutionAI

#### `__init__(config=None)`
Initialize the AI with optional custom configuration.

#### `fit(df, validation_split=0.2)`
Train the model on historical OHLCV data.

**Parameters:**
- `df`: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
- `validation_split`: Fraction for validation set

**Returns:** Dictionary with training metrics

#### `predict_trade_timing(df, current_position='none')`
Predict optimal trade entry/exit timing.

**Parameters:**
- `df`: Recent OHLCV data (at least `lookback_window` periods)
- `current_position`: Current position ('none', 'long', 'short')

**Returns:** Dictionary with:
- `signal`: 'buy', 'sell', or 'hold'
- `confidence`: Score 0-1
- `predicted_return`: Expected return
- `optimal_entry_price`: Suggested entry
- `optimal_exit_price`: Suggested exit
- `stop_loss`: Stop loss price
- `take_profit`: Take profit price
- `features`: Current indicator values
- `rl_action`: RL recommendation

#### `backtest(df, initial_capital=10000, commission=0.001)`
Run walk-forward backtest on historical data.

**Returns:** Dictionary with performance metrics

#### `save_model(filepath)` / `load_model(filepath)`
Save/load trained models.

### Convenience Function

#### `predict_trade(df, model_path=None, config=None)`
Quick prediction function that trains or loads a model.

## Data Format

Input DataFrame should have OHLCV columns:
```python
df = pd.DataFrame({
    'open': [...],
    'high': [...],
    'low': [...],
    'close': [...],
    'volume': [...]
})
```

## Example Usage

### Basic Prediction
```python
from trade_execution_ai import TradeExecutionAI, create_sample_data

df = create_sample_data(n_periods=500)
ai = TradeExecutionAI()
metrics = ai.fit(df)

prediction = ai.predict_trade_timing(df)
if prediction['signal'] == 'buy' and prediction['confidence'] > 0.7:
    print(f"BUY at {prediction['optimal_entry_price']}")
    print(f"Stop: {prediction['stop_loss']}, Target: {prediction['take_profit']}")
```

### Custom Configuration
```python
config = AIConfig(
    confidence_threshold=0.8,
    lookback_window=30,
    n_estimators=200,
    rsi_period=21
)

ai = TradeExecutionAI(config)
```

### Backtesting
```python
ai.fit(training_data)
results = ai.backtest(test_data, initial_capital=10000)
print(f"Return: {results['total_return']}%")
print(f"Trades: {results['n_trades']}")
print(f"Sharpe: {results['sharpe_ratio']}")
```

### Save/Load Models
```python
# Train and save
ai.fit(df)
ai.save_model('my_model.pkl')

# Load later
ai = TradeExecutionAI()
ai.load_model('my_model.pkl')
prediction = ai.predict_trade_timing(new_data)
```

## Testing

Run the test suite:
```bash
cd /root/.openclaw/skills/trade-execution-ai
python -m pytest test_trade_execution_ai.py -v
```

Or with unittest:
```bash
python test_trade_execution_ai.py
```

## Architecture

```
┌─────────────────┐
│   OHLCV Data    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ TechnicalAnalyzer│
│  - RSI          │
│  - MACD         │
│  - Bollinger    │
│  - ATR          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│ Feature Matrix  │────▶│ RandomForest     │
└─────────────────┘     │ Regressor        │
                        └────────┬─────────┘
                                 │
                                 ▼
┌─────────────────┐     ┌──────────────────┐
│ RL Component    │◄────│ Predicted Return │
│ (Q-Learning)    │     └──────────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Signal Combine  │
│  - ML Signal    │
│  - RL Signal    │
│  - Confidence   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Trade Decision  │
│  - Entry/Exit   │
│  - Stop Loss    │
│  - Take Profit  │
└─────────────────┘
```

## License

MIT License - Use at your own risk. Trading involves substantial risk of loss.
