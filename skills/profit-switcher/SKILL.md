# Profit Switcher Skill

Real-time comparison of PoW (Proof of Work) algorithm profitability with automatic switching logic for cryptocurrency mining operations.

## Overview

This skill enables miners to automatically switch between different coins/algorithms based on real-time profitability calculations, maximizing returns by always mining the most profitable option.

## Features

- **Real-time Profitability Tracking**: Fetches live data (difficulty, price, block reward) for multiple coins
- **Automatic Switching**: Intelligently switches mining algorithms when profitability changes
- **Hysteresis Protection**: Prevents rapid switching with configurable thresholds and cooldown periods
- **Profit History**: Tracks historical profitability for analysis and optimization
- **Cost Accounting**: Accounts for electricity costs and pool fees in profit calculations

## Configuration

### ProfitConfig

```python
from profit_switcher import ProfitConfig

config = ProfitConfig(
    coins=[
        {
            "symbol": "BTC",
            "algorithm": "SHA256",
            "pool_url": "stratum+tcp://pool.example:3333",
            "wallet": "your_btc_address"
        },
        {
            "symbol": "LTC",
            "algorithm": "Scrypt",
            "pool_url": "stratum+tcp://ltc.pool.example:3333",
            "wallet": "your_ltc_address"
        }
    ],
    electricity_cost_per_kwh=0.12,  # USD per kWh
    pool_fee_percent=2.0,           # Pool fee percentage
    miner_power_watts=1200,         # Power consumption in watts
    switch_threshold_percent=5.0,   # Min profit difference to trigger switch
    cooldown_minutes=10,            # Min time between switches
    min_profit_duration_minutes=2   # Time profitable coin must lead before switch
)
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `coins` | List[Dict] | [] | List of coin configurations |
| `electricity_cost_per_kwh` | float | 0.10 | Electricity cost in USD per kWh |
| `pool_fee_percent` | float | 2.0 | Mining pool fee percentage |
| `miner_power_watts` | float | 1000 | Miner power consumption in watts |
| `switch_threshold_percent` | float | 5.0 | Minimum profit advantage to trigger switch (%) |
| `cooldown_minutes` | int | 10 | Minimum time between switches |
| `min_profit_duration_minutes` | int | 2 | Time a coin must be most profitable before switching |

## API Reference

### Core Functions

#### fetch_mining_data(coins: List[Dict]) -> Dict[str, MiningData]

Fetches real-time mining data for all configured coins.

**Returns:**
```python
{
    "BTC": MiningData(
        difficulty=85000000000000,
        price=65000.00,
        block_reward=3.125,
        network_hashrate=500000000000000000000
    ),
    ...
}
```

#### calculate_profit_per_coin(mining_data: Dict, config: ProfitConfig) -> Dict[str, ProfitResult]

Calculates profit per coin considering revenue minus costs.

**Returns:**
```python
{
    "BTC": ProfitResult(
        coin="BTC",
        revenue_per_day=25.50,
        cost_per_day=3.45,
        profit_per_day=22.05,
        profit_per_mh=0.000045
    ),
    ...
}
```

#### compare_profits(profits: Dict[str, ProfitResult]) -> List[ProfitResult]

Ranks coins by profitability (highest first).

**Returns:** Sorted list of ProfitResult objects

#### should_switch(current_coin: str, profits: Dict, config: ProfitConfig, history: ProfitHistory) -> Tuple[bool, str, str]

Determines if a switch should occur based on profitability and hysteresis.

**Returns:** `(should_switch: bool, new_coin: str, reason: str)`

#### execute_switch(from_coin: str, to_coin: str, config: ProfitConfig) -> bool

Executes the mining algorithm/coin switch.

**Returns:** `True` if successful, `False` otherwise

### Classes

#### MiningData

```python
@dataclass
class MiningData:
    difficulty: float          # Network difficulty
    price: float               # Coin price in USD
    block_reward: float        # Block reward in coins
    network_hashrate: float    # Network hashrate (optional)
    timestamp: datetime        # Data timestamp
```

#### ProfitResult

```python
@dataclass
class ProfitResult:
    coin: str                  # Coin symbol
    revenue_per_day: float     # Daily revenue in USD
    cost_per_day: float        # Daily electricity cost in USD
    profit_per_day: float      # Daily profit in USD
    profit_per_mh: float       # Profit per MH/s (normalized)
    timestamp: datetime        # Calculation timestamp
```

#### ProfitHistory

```python
@dataclass
class ProfitHistory:
    entries: List[ProfitResult]
    switches: List[SwitchEvent]
    
    def add_entry(self, result: ProfitResult)
    def get_best_performing(self, hours: int = 24) -> str
    def get_average_profit(self, coin: str, hours: int = 24) -> float
```

## Usage Example

```python
import asyncio
from profit_switcher import (
    ProfitConfig, ProfitHistory, 
    fetch_mining_data, calculate_profit_per_coin,
    compare_profits, should_switch, execute_switch
)

async def main():
    # Configure
    config = ProfitConfig(
        coins=[
            {"symbol": "BTC", "algorithm": "SHA256", "hashrate_mh": 100000},
            {"symbol": "LTC", "algorithm": "Scrypt", "hashrate_mh": 5000},
        ],
        electricity_cost_per_kwh=0.12,
        miner_power_watts=1200
    )
    
    history = ProfitHistory()
    current_coin = "BTC"
    
    while True:
        # Fetch data
        mining_data = await fetch_mining_data(config.coins)
        
        # Calculate profits
        profits = calculate_profit_per_coin(mining_data, config)
        
        # Track history
        for result in profits.values():
            history.add_entry(result)
        
        # Check if we should switch
        should_switch_flag, new_coin, reason = should_switch(
            current_coin, profits, config, history
        )
        
        if should_switch_flag:
            success = execute_switch(current_coin, new_coin, config)
            if success:
                print(f"Switched from {current_coin} to {new_coin}: {reason}")
                current_coin = new_coin
        
        # Wait before next check
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
```

## Data Sources

The skill uses the following APIs for mining data:

- **CoinGecko**: Coin prices
- **WhatToMine / CoinWarz**: Mining difficulty and profitability
- **Blockchair / Blockchain.info**: Block rewards and network stats

## Hysteresis Logic

To prevent excessive switching:

1. **Threshold**: New coin must be at least `switch_threshold_percent` more profitable
2. **Cooldown**: Minimum `cooldown_minutes` between switches
3. **Duration**: New coin must be most profitable for `min_profit_duration_minutes`
4. **Volatility**: Avoid switching during high price volatility periods

## Testing

Run tests with:

```bash
python -m pytest test_profit_switcher.py -v
```

## Notes

- Always test switching logic in dry-run mode before enabling live switching
- Monitor switch frequency - excessive switching reduces profits due to downtime
- Consider transaction fees when switching to coins that require immediate selling
- Keep API keys secure and implement rate limiting
