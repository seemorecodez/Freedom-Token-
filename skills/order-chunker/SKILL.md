# ORDER CHUNKER SKILL

Splits large orders into randomized smaller pieces to avoid detection and MEV extraction.

## Purpose

Large orders on blockchain networks and exchanges are easily detected by:
- MEV bots looking for juicy targets
- Analytics platforms tracking whale movements
- Competitors monitoring order books

Order chunking breaks a large trade into many smaller, randomized pieces that blend in with normal market activity.

## Components

### ChunkConfig
Configuration class defining chunking parameters:
- `min_chunk`: Minimum chunk size (USD or token amount)
- `max_chunk`: Maximum chunk size
- `strategy`: Distribution strategy (random, weighted, geometric)
- `stealth_level`: Preset configurations (low/medium/high/paranoid)

### Chunk Distribution Strategies

**Random**: Chunks sized randomly between min/max bounds
**Weighted**: Larger chunks early, tapering to smaller ones (or vice versa)
**Geometric**: Each chunk is a percentage of remaining amount

## Usage

```python
from order_chunker import ChunkConfig, chunk_order, DistributionStrategy

# Basic usage with stealth level
config = ChunkConfig.from_stealth_level("high")
chunks = chunk_order(total_amount=10000, symbol="BTC-USD", config=config)

# Custom configuration
config = ChunkConfig(
    min_chunk=100,
    max_chunk=500,
    strategy=DistributionStrategy.WEIGHTED,
    stealth_level="medium"
)
chunks = chunk_order(total_amount=5000, symbol="ETH-USD", config=config)

# Process chunks
for chunk in chunks:
    print(f"Chunk {chunk.sequence}: ${chunk.amount}")
    execute_trade(chunk)
```

## Stealth Levels

| Level | Chunk Count | Chunk Size Range | Use Case |
|-------|-------------|------------------|----------|
| low | 2-3 chunks | $500-$2000 | Quick execution, minimal obfuscation |
| medium | 3-5 chunks | $100-$1000 | Balanced speed vs stealth |
| high | 5-10 chunks | $50-$500 | Strong obfuscation, longer execution |
| paranoid | 10-20 chunks | $10-$200 | Maximum stealth, very slow |

## Chunk Metadata

Each chunk includes:
- `chunk_id`: Unique identifier (SHA-256 hash)
- `amount`: Chunk size in base currency
- `sequence`: Execution order (0-indexed)
- `symbol`: Trading pair
- `remaining`: Amount left after this chunk

## Integration

Works standalone or as part of the StealthTrader ecosystem:

```python
from order_chunker import chunk_order, ChunkConfig
from stealth_trader import StealthTrader

# Standalone
chunks = chunk_order(10000, "BTC-USD", ChunkConfig.from_stealth_level("high"))

# As part of StealthTrader
trader = StealthTrader(config)
trader.chunker.chunk_order(10000, "BTC-USD")
```

## Testing

Run unit tests:
```bash
python -m pytest test_order_chunker.py -v
```
