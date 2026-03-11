# Portfolio Rebalancer

Automatically rebalance investment portfolios based on target allocations.

## Overview

This skill provides intelligent portfolio rebalancing with multiple strategies, tax awareness, and drift detection.

## Features

- **Target Allocations**: Define target percentages for each asset/class
- **Drift Detection**: Monitor when allocations deviate from targets
- **Tax-Aware Rebalancing**: Minimize taxable events
- **Multiple Strategies**: Threshold, periodic, and cash-flow based rebalancing

## Usage

```python
from portfolio_rebalancer import (
    RebalanceConfig,
    calculate_current_allocations,
    calculate_rebalance_trades,
    drift_threshold_check,
    tax_aware_rebalancing
)

# Configure your targets
config = RebalanceConfig(
    targets={
        "VTI": 0.60,   # 60% US Total Market
        "VTIAX": 0.30, # 30% International
        "BND": 0.10    # 10% Bonds
    },
    drift_threshold=0.05,  # 5% drift triggers rebalance
    schedule="quarterly"
)

# Calculate current allocations
portfolio = {
    "VTI": {"shares": 100, "price": 220.50, "cost_basis": 180.00},
    "VTIAX": {"shares": 200, "price": 45.20, "cost_basis": 40.00},
    "BND": {"shares": 50, "price": 85.00, "cost_basis": 82.00}
}

allocations = calculate_current_allocations(portfolio)
# {"VTI": 0.62, "VTIAX": 0.30, "BND": 0.08}

# Check if rebalancing is needed
needs_rebalance, drifts = drift_threshold_check(portfolio, config)

# Calculate trades needed
trades = calculate_rebalance_trades(portfolio, config)
# [{"asset": "VTI", "action": "sell", "shares": 5.23, "value": 1153.56}, ...]

# Tax-aware rebalancing (prioritizes tax-advantaged accounts)
tax_optimized = tax_aware_rebalancing(
    portfolio,
    config,
    tax_lots={
        "VTI": [
            {"shares": 50, "cost_basis": 150.00, "date": "2023-01-15", "account": "taxable"},
            {"shares": 50, "cost_basis": 210.00, "date": "2024-06-20", "account": "ira"}
        ]
    },
    account_types={"taxable": "taxable", "ira": "tax_deferred"}
)
```

## Classes

### RebalanceConfig

Configuration for rebalancing operations.

```python
@dataclass
class RebalanceConfig:
    targets: Dict[str, float]              # Asset -> target allocation (0.0-1.0)
    drift_threshold: float = 0.05          # Max allowed drift before rebalance
    schedule: str = "threshold"            # "threshold", "periodic", "cash_flow"
    period_days: int = 90                  # For periodic rebalancing
    tax_sensitive: bool = True             # Consider tax implications
    min_trade_value: float = 100.0         # Minimum trade to execute
    max_turnover: float = 0.50             # Max annual turnover allowed
```

## Functions

### calculate_current_allocations(portfolio)

Calculate current allocation percentages from portfolio holdings.

**Parameters:**
- `portfolio`: Dict of asset -> {shares, price, cost_basis}

**Returns:**
- Dict of asset -> allocation percentage (0.0-1.0)

### drift_threshold_check(portfolio, config)

Check if portfolio drift exceeds threshold.

**Returns:**
- `(needs_rebalance: bool, drifts: Dict[str, float])`

### calculate_rebalance_trades(portfolio, config)

Calculate trades needed to reach target allocations.

**Returns:**
- List of trade dicts with asset, action, shares, value

### tax_aware_rebalancing(portfolio, config, tax_lots, account_types)

Generate tax-optimized rebalancing plan.

**Parameters:**
- `tax_lots`: Dict of asset -> list of tax lots
- `account_types`: Dict of account_name -> "taxable" | "tax_deferred" | "tax_free"

**Returns:**
- Dict with trades prioritized by tax efficiency

## Rebalancing Strategies

### 1. Threshold Rebalancing (Default)
Rebalance when any asset drifts beyond threshold.
- Good for: Minimizing trades while maintaining discipline
- Trigger: Drift > threshold

### 2. Periodic Rebalancing
Rebalance on a fixed schedule.
- Good for: Set-and-forget investors
- Trigger: Time-based (daily, monthly, quarterly, yearly)

### 3. Cash-Flow Rebalancing
Rebalance using new contributions/withdrawals only.
- Good for: Tax-sensitive accounts with regular contributions
- Trigger: New cash flows

## Tax Optimization Rules

1. **Harvest losses first** - Sell losing positions to offset gains
2. **Prioritize tax-advantaged accounts** - Rebalance in IRA/401k before taxable
3. **Long-term gains over short-term** - Prefer holdings > 1 year
4. **Use contributions intelligently** - Direct new money to underweight assets

## CLI Usage

```bash
# Check if portfolio needs rebalancing
python portfolio_rebalancer.py --check --portfolio portfolio.json --config config.json

# Generate rebalancing plan
python portfolio_rebalancer.py --plan --portfolio portfolio.json --config config.json

# Run with tax optimization
python portfolio_rebalancer.py --plan --tax-aware --portfolio portfolio.json --config config.json
```
