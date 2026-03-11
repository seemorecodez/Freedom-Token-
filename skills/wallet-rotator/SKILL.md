# WALLET ROTATOR SKILL

Implements wallet rotation for enhanced privacy in cryptocurrency transactions.

## Overview

Wallet rotation is a privacy technique that uses temporary, single-use addresses for transactions instead of reusing the same wallet address repeatedly. This prevents:

- Address clustering analysis by blockchain surveillance
- Balance tracking across multiple transactions
- Transaction pattern analysis
- Linkability of payments

## Components

1. **WalletRotator** - Core class managing wallet lifecycle
2. **Temporary Wallet Generation** - Creates single-use addresses per chain
3. **Active Wallet Rotation** - Switches between wallets automatically
4. **Lifecycle Tracking** - Monitors creation, usage, and retirement
5. **Multi-Chain Support** - ETH, BTC, SOL address generation

## Usage

```python
from wallet_rotator import WalletRotator, Chain

# Initialize rotator
rotator = WalletRotator(default_chain=Chain.ETHEREUM)

# Generate a single-use wallet
wallet = rotator.generate_temp_wallet(chain=Chain.ETHEREUM)
print(wallet.address)  # 0x...

# Get current active wallet (auto-rotates if needed)
active = rotator.get_active_wallet()

# Mark wallet as used (triggers rotation)
rotator.mark_used(wallet.address)

# Get fresh wallet for new transaction
fresh = rotator.rotate_wallet()

# Track wallet lifecycle
lifecycle = rotator.track_wallet_lifecycle(wallet.address)
```

## Supported Chains

| Chain | Address Format | Example |
|-------|---------------|---------|
| ETH | 0x + 40 hex | 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb |
| BTC | Base58/bech32 | bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh |
| SOL | Base58 (32 bytes) | 7EcDhS1...zJdY |

## Wallet Lifecycle

```
CREATED → ACTIVE → USED → RETIRED
   ↑        ↓       ↓        ↓
  mint   receive  spend   archive
```

- **CREATED**: Wallet generated, not yet used
- **ACTIVE**: Currently receiving address
- **USED**: Has received funds, pending spend
- **RETIRED**: Funds moved, address no longer used

## Privacy Best Practices

1. **Never reuse** addresses across different counterparties
2. **Rotate after each receive** for maximum privacy
3. **Batch retirement** to save on fees
4. **Use fresh wallets** for each DEX interaction
5. **Monitor** usage counts to prevent address exhaustion

## Configuration

```python
from wallet_rotator import WalletRotatorConfig

config = WalletRotatorConfig(
    max_usage_per_wallet=1,      # Single-use by default
    auto_rotate=True,            # Auto-switch on usage
    retirement_threshold=10,     # Retire after N uses
    track_lifecycle=True,        # Enable metadata tracking
    generate_backup=True         # Pre-generate backup wallets
)

rotator = WalletRotator(config=config)
```

## Integration

Works standalone or as part of the Stealth Trading suite:

```python
from stealth_trader import StealthTrader
from wallet_rotator import WalletRotator

# Wallet rotator used automatically by StealthTrader
trader = StealthTrader(
    config=StealthConfig(wallet_rotation=True)
)

# Or use standalone
rotator = WalletRotator()
address = rotator.generate_temp_wallet(chain=Chain.BITCOIN)
```

## Security Notes

- Generated addresses are **deterministic** (derived from seed)
- **Never expose** private keys in logs or memory dumps
- **Backup** your seed phrase - addresses can be re-derived
- **Test** address generation on testnets first
