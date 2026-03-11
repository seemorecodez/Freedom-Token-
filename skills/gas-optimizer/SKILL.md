# Gas Optimizer Skill

Optimize Ethereum transaction fees through intelligent timing and strategy selection.

## Overview

This skill provides tools to minimize transaction costs on Ethereum by:
- Estimating gas costs before submitting transactions
- Identifying optimal timing for low-fee periods
- Calculating EIP-1559 fee parameters (maxFeePerGas, maxPriorityFeePerGas)
- Analyzing historical gas trends
- Recommending transaction batching strategies

## Quick Start

```python
from gas_optimizer import GasOptimizer, GasConfig, GasStrategy

# Initialize with your preferred strategy
config = GasConfig(
    max_fee_gwei=50,
    priority_fee_gwei=2,
    strategy=GasStrategy.STANDARD
)

optimizer = GasOptimizer(config)

# Check optimal timing
best_time = optimizer.get_optimal_timing()
print(f"Best time to transact: {best_time}")

# Calculate EIP-1559 fees
fees = optimizer.calculate_eip1559_fees()
print(f"maxFeePerGas: {fees['maxFeePerGas']} gwei")
print(f"maxPriorityFeePerGas: {fees['maxPriorityFeePerGas']} gwei")
```

## Gas Strategies

### Aggressive
- High priority fees for fast inclusion
- Use when: Time-sensitive transactions, MEV opportunities, urgent operations
- Typical inclusion: Within 1-2 blocks

### Standard (Default)
- Balanced fees for reasonable confirmation times
- Use when: Regular transactions, non-urgent operations
- Typical inclusion: Within 3-6 blocks

### Economic
- Minimized fees, willing to wait
- Use when: Non-urgent transfers, batch operations, low-priority transactions
- Typical inclusion: Within 10-30 blocks

## API Reference

### GasConfig

Configuration class for gas optimization parameters.

```python
class GasConfig:
    max_fee_gwei: float          # Maximum acceptable base + priority fee
    priority_fee_gwei: float     # Tip to miners/validators
    strategy: GasStrategy        # AGGRESSIVE, STANDARD, or ECONOMIC
    max_wait_minutes: int        # Maximum wait time for economic strategy
    rpc_url: Optional[str]       # Ethereum RPC endpoint
```

### GasOptimizer

Main class for gas optimization operations.

#### Methods

**estimate_gas(transaction_data: dict) -> GasEstimate**
Predicts transaction cost based on current network conditions.

**get_optimal_timing() -> TimingRecommendation**
Returns the best time window for low-fee transactions based on historical data.

**calculate_eip1559_fees() -> EIP1559Fees**
Calculates maxFeePerGas and maxPriorityFeePerGas based on current base fee and strategy.

**check_gas_history(days: int = 7) -> GasHistory**
Analyzes fee trends over specified period.

**recommend_batching(transactions: List[dict]) -> BatchingRecommendation**
Suggests optimal batching strategy to minimize total fees.

## Gas Optimization Tips

1. **Time Your Transactions**: Gas is typically cheapest on weekends and during off-peak hours (UTC early morning)

2. **Use EIP-1559**: Legacy transactions often overpay. Use type-2 transactions with proper maxFeePerGas

3. **Batch Operations**: Combine multiple transfers or interactions into single transactions when possible

4. **Monitor Base Fee Trends**: If base fee is trending down, consider waiting a few blocks

5. **Set Reasonable Limits**: Don't set maxFeePerGas too high - it caps your exposure but unused gas is refunded

## Fee Components

### EIP-1559 Fee Structure

```
Total Fee = (Base Fee + Priority Fee) × Gas Used
```

- **Base Fee**: Determined by network, burned (removed from circulation)
- **Priority Fee**: Tip to validators, incentivizes inclusion
- **Max Fee**: Maximum you're willing to pay (base + priority)
- **Max Priority Fee**: Maximum tip you're willing to pay

### Calculation Example

```
Current Base Fee: 20 gwei
Priority Fee: 2 gwei
Gas Limit: 21,000 (simple transfer)

Total Cost = (20 + 2) × 21,000 = 462,000 gwei = 0.000462 ETH
```

## Data Sources

By default, uses public RPC endpoints. For production:
1. Set up your own Ethereum node, or
2. Use reliable RPC providers (Alchemy, Infura, QuickNode)

## Error Handling

All methods raise `GasOptimizationError` for recoverable issues and `GasConfigError` for configuration problems.

## Testing

Run tests with:
```bash
python -m pytest test_gas_optimizer.py -v
```

## References

- [EIP-1559 Specification](https://eips.ethereum.org/EIPS/eip-1559)
- [Ethereum Gas Documentation](https://ethereum.org/en/developers/docs/gas/)
- [Gas Price Oracles](https://etherscan.io/gastracker)
