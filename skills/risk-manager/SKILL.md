# Risk Manager Skill

## Overview

The risk-manager skill provides essential trading safety mechanisms including position sizing, stop-loss management, and drawdown protection. Proper risk management is the foundation of sustainable trading.

## Core Principles

### 1. Capital Preservation
- Never risk more than you can afford to lose
- Protect your trading capital above all else
- Small, consistent wins compound over time

### 2. Position Sizing
- Size positions based on account risk, not profit potential
- Use fixed fractional or Kelly criterion methods
- Never exceed maximum position limits

### 3. Stop Losses
- Always set stop losses before entering trades
- Stops should be based on technical levels, not arbitrary percentages
- Never move stops to increase risk

### 4. Daily Limits
- Set maximum daily loss limits
- Stop trading when limits are hit
- Prevent emotional revenge trading

## API Reference

### RiskConfig

Configuration class for risk parameters:

```python
RiskConfig(
    max_position_pct=0.20,      # Max 20% in single position
    stop_loss_pct=0.02,         # 2% stop loss
    take_profit_pct=0.06,       # 6% take profit (3:1 R/R)
    daily_loss_limit_pct=0.05,  # 5% daily loss limit
    max_trades_per_day=10,      # Prevent overtrading
    kelly_fraction=0.25,        # Conservative Kelly (1/4 Kelly)
    correlation_limit=0.70      # Max correlation between positions
)
```

### calculate_position_size()

Calculate optimal position size using fixed fractional or Kelly criterion:

```python
# Fixed fractional
size = calculate_position_size(
    account_value=100000,
    risk_per_trade_pct=0.01,  # Risk 1% per trade
    entry_price=100,
    stop_price=98,
    method='fixed_fractional'
)

# Kelly criterion
size = calculate_position_size(
    account_value=100000,
    win_rate=0.55,
    avg_win=300,
    avg_loss=100,
    method='kelly',
    kelly_fraction=0.25
)
```

### check_stop_loss()

Monitor positions and trigger stop losses:

```python
action = check_stop_loss(
    entry_price=100,
    current_price=97,
    stop_price=98,
    position_side='long'
)
# Returns: 'stop_triggered' or 'hold'
```

### check_daily_limit()

Check if daily loss limit has been exceeded:

```python
status = check_daily_limit(
    daily_pnl=-5000,
    account_value=100000,
    daily_loss_limit_pct=0.05
)
# Returns: {'allowed': False, 'reason': 'daily_limit_exceeded'}
```

### calculate_drawdown()

Track portfolio drawdown from peak:

```python
drawdown = calculate_drawdown(
    current_equity=95000,
    peak_equity=100000
)
# Returns: {'drawdown_pct': 0.05, 'in_drawdown': True}
```

### RiskManager

Orchestrates all risk management functions:

```python
risk_mgr = RiskManager(config)

# Before entering a trade
result = risk_mgr.validate_trade({
    'symbol': 'AAPL',
    'entry_price': 150,
    'stop_price': 145,
    'target_price': 165,
    'side': 'long'
})

# On price update
result = risk_mgr.update_position('AAPL', current_price=144)

# End of day
risk_mgr.reset_daily_stats()
```

## Best Practices

### Position Sizing Rules

1. **1-2% Rule**: Risk no more than 1-2% of account per trade
2. **Volatility Adjustment**: Reduce size in high volatility periods
3. **Correlation Awareness**: Reduce size when holding correlated positions
4. **Scaling In**: Add to winners, never average down losers

### Stop Loss Guidelines

| Market Type | Recommended Stop |
|------------|------------------|
| Stocks (swing) | 5-8% or ATR-based |
| Stocks (day) | 1-2% or support/resistance |
| Forex | 1-2 ATR |
| Crypto | 3-5% or key technical levels |

### Drawdown Limits

| Drawdown Level | Action Required |
|---------------|-----------------|
| 5% | Warning - review trades |
| 10% | Reduce position sizes by 50% |
| 20% | Stop trading, review strategy |
| 30% | Mandatory trading halt |

### Daily Limits

- **Daily Loss Limit**: 3-5% of account
- **Max Trades**: Limit to prevent overtrading
- **Consecutive Losses**: Pause after 3-5 losses

## Risk Metrics

### Win Rate
- Percentage of winning trades
- Higher win rate = more confidence in Kelly sizing

### Risk/Reward Ratio
- Minimum 1:2 (risk $1 to make $2)
- Higher ratios allow lower win rates

### Expectancy
```
Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
```
- Positive expectancy = profitable system
- Negative expectancy = unprofitable regardless of win rate

### Sharpe Ratio
- Risk-adjusted returns
- >1.0 is good, >2.0 is excellent

## Example Usage

```python
from risk_manager import RiskManager, RiskConfig

# Configure risk parameters
config = RiskConfig(
    max_position_pct=0.15,
    stop_loss_pct=0.03,
    take_profit_pct=0.09,
    daily_loss_limit_pct=0.04
)

risk_mgr = RiskManager(config)

# Pre-trade validation
trade = {
    'symbol': 'TSLA',
    'entry_price': 200,
    'stop_price': 194,
    'target_price': 218,
    'side': 'long',
    'account_value': 50000
}

validation = risk_mgr.validate_trade(trade)
if validation['allowed']:
    print(f"Position size: {validation['position_size']} shares")
else:
    print(f"Trade rejected: {validation['reason']}")

# Monitor during trade
update = risk_mgr.update_position('TSLA', current_price=193)
if update['action'] == 'stop_triggered':
    print("Stop loss hit - exit position")
```

## Integration with Trading Systems

1. **Before Entry**: Validate trade against all risk rules
2. **On Entry**: Record position and set stops
3. **During Trade**: Monitor for stop/target hits
4. **On Exit**: Update statistics and daily P&L
5. **End of Day**: Reset daily counters, review metrics

## Common Mistakes to Avoid

1. ❌ No stop losses
2. ❌ Moving stops to avoid losses
3. ❌ Risking too much per trade (>5%)
4. ❌ Overtrading after losses
5. ❌ Ignoring correlation between positions
6. ❌ Averaging down on losing trades
7. ❌ Trading without daily loss limits

## References

- "Trade Your Way to Financial Freedom" - Van K. Tharp
- "The Kelly Capital Growth Investment Criterion" - MacLean, Thorp, Ziemba
- "Position Sizing" - Van K. Tharp
