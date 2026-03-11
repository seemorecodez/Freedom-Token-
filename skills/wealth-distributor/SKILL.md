# WEALTH DISTRIBUTOR SKILL

Automated treasury management and payout distribution system.

## Overview

The Wealth Distributor manages automated fund distribution from a treasury to multiple recipients using configurable strategies. It supports scheduled payouts, auto-reinvestment, and comprehensive tracking.

## Components

1. **DistributionConfig** - Configuration for payouts (percentages, thresholds, schedules)
2. **DistributionCalculator** - Determines payouts per recipient based on strategy
3. **AutoReinvestment** - Handles compounding logic for treasury growth
4. **Scheduler** - Cron-like scheduling for automated distributions
5. **RecipientManager** - Add, remove, and update recipients
6. **DistributionTracker** - Track history, pending, and completed distributions

## Distribution Strategies

- **equal**: Equal split among all recipients
- **weighted**: Proportional distribution based on recipient weights
- **performance**: Dynamic allocation based on performance metrics

## Usage

```python
from wealth_distributor import WealthDistributor, DistributionConfig

# Configure distribution
config = DistributionConfig(
    strategy="weighted",
    threshold=100.0,  # Minimum treasury balance before distribution
    interval="0 0 * * *",  # Daily at midnight
    auto_reinvest_percent=10.0  # Reinvest 10% back to treasury
)

# Initialize distributor
distributor = WealthDistributor(config)

# Add recipients
distributor.add_recipient("alice", weight=50.0, address="0x123...")
distributor.add_recipient("bob", weight=30.0, address="0x456...")
distributor.add_recipient("charlie", weight=20.0, address="0x789...")

# Calculate and execute distribution
result = distributor.distribute(treasury_balance=10000.0)
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| strategy | str | "equal" | Distribution strategy (equal/weighted/performance) |
| threshold | float | 0.0 | Minimum balance to trigger distribution |
| interval | str | "0 0 * * *" | Cron expression for scheduled runs |
| auto_reinvest_percent | float | 0.0 | Percentage to compound back to treasury |
| max_payout | float | None | Maximum amount per recipient |
| min_payout | float | 0.01 | Minimum amount to include in distribution |

## Scheduler Format

Uses cron-like syntax:
- `"0 0 * * *"` - Daily at midnight
- `"0 0 * * 0"` - Weekly on Sunday
- `"0 0 1 * *"` - Monthly on 1st
- `"*/5 * * * *"` - Every 5 minutes (testing)

## Tracking

All distributions are tracked with:
- Timestamp
- Amount per recipient
- Distribution status (pending/completed/failed)
- Transaction hash (if applicable)
- Remaining treasury balance
