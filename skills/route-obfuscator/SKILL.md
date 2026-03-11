# Route Obfuscator

A privacy-preserving routing system for cryptocurrency transactions that obscures the origin and destination of funds through strategic multi-hop routing across liquidity pools.

## Overview

Route obfuscation breaks the on-chain linkability between sender and recipient by routing transactions through multiple intermediate hops across different venues (DEXs, CEXs, bridges). This makes it significantly harder for blockchain analytics to trace the flow of funds.

## Key Concepts

### Privacy Through Multi-Hop Routing

Instead of executing a direct transfer:
```
Sender → Recipient
```

Route obfuscation creates a chain of transactions:
```
Sender → Hop 1 → Hop 2 → Hop 3 → Recipient
```

Each hop can use different:
- **Venues**: Uniswap, Curve, Jupiter, Binance, cross-chain bridges
- **Assets**: ETH, USDC, USDT, SOL, BTC, intermediate tokens
- **Chains**: Ethereum, Solana, Bitcoin, layer-2s

### Obfuscation Strategies

1. **Randomized Hop Count**: Variable number of hops (2-8) to avoid pattern detection
2. **Venue Diversification**: Mix of DEXs, CEXs, and bridges
3. **Asset Swapping**: Temporary conversion to different assets mid-route
4. **Cross-Chain Hops**: Bridge to different chains and back
5. **Time Delays**: Optional staggered execution between hops

## Usage

```python
from route_obfuscator import RouteConfig, RouteObfuscator

# Configure obfuscation parameters
config = RouteConfig(
    min_hops=3,
    max_hops=6,
    venues=['uniswap', 'curve', 'binance', 'wormhole'],
    chains=['ethereum', 'solana'],
    randomize=True
)

# Initialize obfuscator
obfuscator = RouteObfuscator(config)

# Find and execute obfuscated route
route = obfuscator.obfuscate_route(
    source_chain='ethereum',
    source_asset='ETH',
    target_chain='solana',
    target_asset='SOL',
    amount=1.0
)

# Execute the route
for hop in route.hops:
    result = hop.execute()
```

## Configuration

### RouteConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_hops` | int | 2 | Minimum number of intermediate hops |
| `max_hops` | int | 5 | Maximum number of intermediate hops |
| `venues` | list | ['uniswap'] | Allowed venues for routing |
| `chains` | list | ['ethereum'] | Supported blockchain networks |
| `selection_strategy` | str | 'random' | Hop selection: 'random', 'cost_optimized', 'privacy_maximized' |
| `allow_bridges` | bool | True | Enable cross-chain bridging |
| `time_delay_range` | tuple | (0, 0) | Min/max seconds between hops |
| `asset_pool` | list | [...] | Assets available for intermediate swaps |

### Supported Venues

**DEXs (Decentralized Exchanges)**
- `uniswap` - Ethereum AMM
- `curve` - Stablecoin-focused DEX
- `jupiter` - Solana aggregator
- `raydium` - Solana AMM
- `pancakeswap` - BSC DEX

**CEXs (Centralized Exchanges)**
- `binance` - Major CEX with wide asset support
- `coinbase` - US-regulated exchange
- `kraken` - Security-focused CEX

**Bridges**
- `wormhole` - Cross-chain messaging
- `layerzero` - Omnichain interoperability
- `stargate` - Cross-chain liquidity
- `thorchain` - Native cross-chain swaps
- `across` - Fast Ethereum L2 bridge

### Supported Chains

- `ethereum` - Primary smart contract platform
- `solana` - High-throughput L1
- `bitcoin` - Original cryptocurrency (via wrapped versions)
- `arbitrum` - Ethereum L2 rollup
- `optimism` - Ethereum L2 optimistic rollup
- `base` - Coinbase L2
- `polygon` - Ethereum sidechain

## Privacy Considerations

### Threat Model

Route obfuscation protects against:
- **Casual observers**: Standard blockchain explorers
- **Basic analytics**: Simple heuristics and clustering
- **Timing analysis**: Correlation by time proximity

Limitations:
- **Advanced adversaries**: State-level actors with full network visibility
- **Volume analysis**: Large unique amounts may still be traceable
- **Endpoint analysis**: Known sender/recipient addresses

### Best Practices

1. **Use standard amounts**: Round numbers blend better
2. **Vary timing**: Avoid predictable patterns
3. **Mix venue types**: Combine DEXs, CEXs, and bridges
4. **Include cross-chain hops**: Break single-chain analysis
5. **Time delays**: Add random delays between hops when possible

## Security Warnings

⚠️ **CEX KYC**: Centralized exchanges require identity verification
⚠️ **Bridge Risk**: Cross-chain bridges have smart contract risks
⚠️ **Slippage**: Multi-hop routes accumulate trading fees and slippage
⚠️ **MEV**: On-chain transactions may be vulnerable to MEV extraction
⚠️ **Regulatory**: Understand legal implications in your jurisdiction

## API Reference

### RouteConfig

Configuration class for route obfuscation behavior.

```python
RouteConfig(
    min_hops: int = 2,
    max_hops: int = 5,
    venues: Optional[List[str]] = None,
    chains: Optional[List[str]] = None,
    selection_strategy: str = 'random',
    allow_bridges: bool = True,
    time_delay_range: Tuple[int, int] = (0, 0),
    asset_pool: Optional[List[str]] = None,
    max_slippage_bps: int = 100
)
```

### RouteObfuscator

Main class for finding and executing obfuscated routes.

```python
# Methods
obfuscate_route(source_chain, source_asset, target_chain, target_asset, amount)
find_route(source_chain, source_asset, target_chain, target_asset, amount, num_hops)
estimate_cost(route)
estimate_time(route)
validate_route(route)
```

### Route and Hop Objects

```python
class Route:
    hops: List[Hop]
    total_cost_bps: int
    estimated_time_seconds: int
    privacy_score: float

class Hop:
    source_chain: str
    source_asset: str
    target_chain: str  
    target_asset: str
    venue: str
    amount: float
    time_delay_seconds: int
```

## Examples

### Basic Ethereum to Solana

```python
config = RouteConfig(min_hops=3, max_hops=5)
obfuscator = RouteObfuscator(config)

route = obfuscator.obfuscate_route(
    'ethereum', 'ETH',
    'solana', 'SOL',
    amount=5.0
)
```

### High Privacy Mode

```python
config = RouteConfig(
    min_hops=5,
    max_hops=8,
    venues=['uniswap', 'binance', 'wormhole'],
    chains=['ethereum', 'arbitrum', 'solana'],
    selection_strategy='privacy_maximized',
    time_delay_range=(60, 300)
)
```

### Cost-Optimized Privacy

```python
config = RouteConfig(
    min_hops=2,
    max_hops=4,
    selection_strategy='cost_optimized',
    allow_bridges=False,  # Bridges add cost
    max_slippage_bps=50
)
```

## Testing

Run the test suite:

```bash
python -m pytest test_route_obfuscator.py -v
```

## License

MIT - See root LICENSE file
