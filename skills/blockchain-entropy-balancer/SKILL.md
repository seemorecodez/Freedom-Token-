# blockchain-entropy-balancer

A Python skill for blockchain hash-based masking and decoy generation. Provides entropy balancing, hash masking, and synthetic blockchain data generation for Bitcoin and Ethereum.

## Purpose

This skill provides cryptographic utilities to:
- **Mask blockchain hashes** using configurable entropy masks
- **Balance hash distribution** across multiple outputs for privacy/anonymization
- **Generate decoy blockchain data** for testing and privacy-preserving applications
- Support both **Bitcoin** and **Ethereum** hash formats

## Installation

```bash
# Copy the skill to your project
cp -r blockchain-entropy-balancer/ /path/to/your/project/

# Import the module
from blockchain_entropy_balancer import (
    EntropyConfig,
    generate_hash_mask,
    balance_entropy,
    decoy_generation
)
```

## Quick Start

```python
from blockchain_entropy_balancer import (
    EntropyConfig,
    generate_hash_mask,
    balance_entropy,
    decoy_generation
)

# Configure entropy settings
config = EntropyConfig(
    mask_strength=128,
    output_count=4,
    decoy_count=10
)

# Generate a hash mask
mask = generate_hash_mask(config, "bitcoin")

# Balance entropy across multiple outputs
bitcoin_hash = "0000000000000000000b2e9b5a4c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4"
balanced = balance_entropy(bitcoin_hash, config)

# Generate decoy data
decoys = decoy_generation("ethereum", config)
```

## API Reference

### EntropyConfig

Configuration class for entropy balancing operations.

```python
EntropyConfig(
    mask_strength: int = 128,      # Bits of entropy for masks (64, 128, 256)
    output_count: int = 4,         # Number of balanced outputs to generate
    decoy_count: int = 10,         # Number of decoy entries to generate
    salt: Optional[bytes] = None   # Optional salt for deterministic masking
)
```

### generate_hash_mask(config, hash_type)

Generates an entropy mask for the specified blockchain hash type.

**Parameters:**
- `config` (EntropyConfig): Configuration object
- `hash_type` (str): Type of hash - `"bitcoin"` or `"ethereum"`

**Returns:**
- `dict`: Mask metadata including mask bytes, strength, and hash type

**Example:**
```python
mask = generate_hash_mask(config, "bitcoin")
# Returns: {
#     "mask": b'...',
#     "strength": 128,
#     "hash_type": "bitcoin",
#     "algorithm": "sha256"
# }
```

### balance_entropy(hash_input, config)

Distributes a hash across multiple balanced outputs using entropy masking.

**Parameters:**
- `hash_input` (str): Blockchain hash (hex string)
- `config` (EntropyConfig): Configuration object

**Returns:**
- `list`: List of balanced hash outputs with metadata

**Example:**
```python
balanced = balance_entropy(bitcoin_hash, config)
# Returns list of dicts with "output", "mask", "index"
```

### decoy_generation(hash_type, config)

Generates synthetic blockchain data for decoy purposes.

**Parameters:**
- `hash_type` (str): Type of hash - `"bitcoin"` or `"ethereum"`
- `config` (EntropyConfig): Configuration object

**Returns:**
- `list`: List of synthetic blockchain entries

**Example:**
```python
decoys = decoy_generation("ethereum", config)
# Returns list of dicts with "hash", "type", "timestamp", "synthetic": True
```

## Supported Hash Types

| Type | Format | Length | Algorithm |
|------|--------|--------|-----------|
| bitcoin | Hex | 64 chars (256-bit) | Double SHA-256 |
| ethereum | Hex with 0x prefix | 66 chars (256-bit) | Keccak-256 |

## Privacy Considerations

- Masks are cryptographically random by default
- Use `salt` parameter for reproducible masking (same input → same mask)
- Decoy data is marked with `"synthetic": True` to prevent confusion
- No real blockchain data is transmitted or stored

## Testing

```bash
cd /root/.openclaw/skills/blockchain-entropy-balancer
python -m pytest test_blockchain_entropy_balancer.py -v
```

## License

MIT - Use freely in your blockchain privacy projects.
