# DECOY GENERATOR SKILL

Creates synthetic transactions to mask real trading activity from detection, MEV extraction, and transaction analysis.

## Overview

The Decoy Generator creates realistic-looking synthetic transactions that are indistinguishable from genuine trading activity. These decoys:

- Mask the true volume and pattern of real trades
- Confuse MEV bots and sandwich attackers
- Obfuscate wallet ownership and trading strategies
- Create plausible deniability for trading activity

## Components

1. **DecoyConfig** - Configuration for decoy generation parameters
2. **DecoyGenerator** - Core engine for creating synthetic transactions
3. **Decoy Types** - Support for trades, transfers, and approvals
4. **Lifecycle Manager** - Create, execute, and retire decoys
5. **Size Calculator** - Natural-looking randomized amounts

## Usage

```python
from decoy_generator import DecoyGenerator, DecoyConfig

# Configure decoy generation
config = DecoyConfig(
    ratio=2.0,              # 2 decoys per real transaction
    size_range=(0.1, 5.0),  # Size range as % of real transaction
    frequency="random",     # Distribution pattern
    decoy_types=["trade", "transfer"]
)

# Create generator
generator = DecoyGenerator(config)

# Generate a single decoy
decoy = generator.generate_decoy_transaction(
    reference_amount=1000.0,
    decoy_type="trade",
    symbol="BTC-USD"
)

# Generate a batch of decoys
decoys = generator.generate_decoy_batch(
    real_transactions=real_trades,
    batch_size=10
)

# Mix decoys with real transactions
mixed = generator.mix_decoys_with_real(
    real_transactions=real_trades,
    decoy_transactions=decoys
)
```

## Decoy Types

### Trade Decoys
- Simulate buy/sell orders on DEXs/CEXs
- Mimic real trading patterns and price impacts
- Include realistic slippage and fees

### Transfer Decoys
- Fake wallet-to-wallet movements
- Multi-hop transfers to obscure trail
- Cross-chain bridge simulations

### Approval Decoys
- Token approval transactions
- Spending limit updates
- Revocation simulations

## Decoy Lifecycle

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐
│  CREATE │───▶│  QUEUE   │───▶│ EXECUTE  │───▶│ RETIRE  │
│         │    │          │    │          │    │         │
└─────────┘    └──────────┘    └──────────┘    └─────────┘
    │               │               │               │
    ▼               ▼               ▼               ▼
Generate ID    Add jitter    Broadcast to    Archive/
Calculate size    Delay        network      cleanup
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `ratio` | float | 1.0 | Decoys per real transaction |
| `size_range` | tuple | (0.05, 2.0) | Min/max size multiplier |
| `frequency` | str | "random" | Distribution: random, uniform, burst |
| `decoy_types` | list | ["trade"] | Types of decoys to generate |
| `jitter_range` | tuple | (1, 300) | Delay range in seconds |
| `retire_after` | int | 86400 | Auto-retire after seconds |

## Size Calculation Strategies

- **Proportional**: Decoy size based on reference transaction
- **Fixed Range**: Random within configured bounds
- **Volume Mimic**: Match typical market volume patterns
- **Noise Floor**: Minimum viable transaction sizes

## Integration

Works standalone or as part of the Stealth Trader system:

```python
# As standalone
generator = DecoyGenerator(config)
decoys = generator.generate_decoy_batch(real_trades)

# With Stealth Trader
from stealth_trader import StealthTrader
trader = StealthTrader(config)
result = trader.execute_stealth_trade(..., use_decoys=True)
```

## Security Notes

- Decoys should be economically viable (enough gas/fees to be real)
- Avoid patterns that could fingerprint the generator
- Rotate decoy destinations to avoid clustering
- Never reuse decoy addresses with real funds
