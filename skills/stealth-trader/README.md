# STEALTH TRADER SKILL

Implements the proprietary "Stealth Algorithm" for undetectable trading.

## Components

1. **Order Chunker** - Splits large orders into randomized smaller pieces
2. **Temporal Jitter** - Adds random delays between executions
3. **Decoy Generator** - Creates synthetic transactions to mask real ones
4. **Route Obfuscator** - Multi-hop routing through liquidity pools
5. **Wallet Rotator** - Uses temporary addresses for transactions

## Usage

```python
from stealth_trader import StealthTrader

trader = StealthTrader(config)
result = trader.execute_stealth_trade(
    symbol="BTC-USD",
    side="buy",
    amount=10000,  # USD
    stealth_level="high"  # low/medium/high/paranoid
)
```

## Stealth Levels

- **low**: 2-3 chunks, 10-30s delays
- **medium**: 3-5 chunks, 30-120s delays, 1 decoy per real trade
- **high**: 5-10 chunks, 30-300s delays, 2 decoys per trade, multi-hop
- **paranoid**: 10-20 chunks, random 1-600s delays, 3+ decoys, max obfuscation

## Integration

Works with existing Kraken trading bots via wrapper pattern.
