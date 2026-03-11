"""
Gas Optimizer - Ethereum Transaction Fee Optimization

This module provides tools to minimize Ethereum transaction costs through
intelligent timing and strategy selection.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import statistics
import random
import time


class GasStrategy(Enum):
    """Gas pricing strategies for different urgency levels."""
    AGGRESSIVE = "aggressive"  # Fast inclusion, higher cost
    STANDARD = "standard"      # Balanced speed and cost
    ECONOMIC = "economic"      # Minimize cost, willing to wait


class GasOptimizationError(Exception):
    """Raised when gas optimization fails."""
    pass


class GasConfigError(Exception):
    """Raised when configuration is invalid."""
    pass


@dataclass
class GasConfig:
    """Configuration for gas optimization.
    
    Attributes:
        max_fee_gwei: Maximum acceptable total fee (base + priority) in gwei
        priority_fee_gwei: Tip to miners/validators in gwei
        strategy: Gas pricing strategy (aggressive, standard, economic)
        max_wait_minutes: Maximum wait time for economic strategy
        rpc_url: Ethereum RPC endpoint URL
        base_fee_history_size: Number of blocks to track for base fee trends
    """
    max_fee_gwei: float = 100.0
    priority_fee_gwei: float = 2.0
    strategy: GasStrategy = GasStrategy.STANDARD
    max_wait_minutes: int = 60
    rpc_url: Optional[str] = None
    base_fee_history_size: int = 20
    
    def __post_init__(self):
        if self.max_fee_gwei <= 0:
            raise GasConfigError("max_fee_gwei must be positive")
        if self.priority_fee_gwei < 0:
            raise GasConfigError("priority_fee_gwei cannot be negative")
        if self.max_wait_minutes < 1:
            raise GasConfigError("max_wait_minutes must be at least 1")


@dataclass
class GasEstimate:
    """Gas cost estimate for a transaction.
    
    Attributes:
        gas_limit: Estimated gas units required
        base_fee_gwei: Current base fee per gas unit
        priority_fee_gwei: Suggested priority fee
        total_cost_eth: Estimated total cost in ETH
        total_cost_usd: Estimated total cost in USD (if price available)
        confidence: Confidence level of estimate (0-1)
    """
    gas_limit: int
    base_fee_gwei: float
    priority_fee_gwei: float
    total_cost_eth: float
    total_cost_usd: Optional[float] = None
    confidence: float = 0.9


@dataclass
class TimingRecommendation:
    """Recommendation for optimal transaction timing.
    
    Attributes:
        best_time: Suggested time to submit transaction
        expected_base_fee_gwei: Predicted base fee at best time
        savings_percent: Estimated savings vs current fee
        confidence: Confidence in prediction (0-1)
        reason: Explanation of recommendation
    """
    best_time: datetime
    expected_base_fee_gwei: float
    savings_percent: float
    confidence: float
    reason: str


@dataclass
class EIP1559Fees:
    """EIP-1559 fee parameters.
    
    Attributes:
        maxFeePerGas: Maximum fee per gas (base + priority cap)
        maxPriorityFeePerGas: Maximum priority fee per gas (tip cap)
        baseFeePerGas: Current base fee per gas
        estimated_confirmation_blocks: Expected blocks until inclusion
    """
    maxFeePerGas: int  # in wei
    maxPriorityFeePerGas: int  # in wei
    baseFeePerGas: int  # in wei
    estimated_confirmation_blocks: int


@dataclass
class GasHistoryEntry:
    """Single entry in gas price history."""
    timestamp: datetime
    base_fee_gwei: float
    priority_fee_gwei: float
    block_number: int


@dataclass
class GasHistory:
    """Historical gas price data.
    
    Attributes:
        entries: List of historical gas entries
        average_base_fee: Mean base fee over period
        min_base_fee: Minimum base fee observed
        max_base_fee: Maximum base fee observed
        trend: Trend direction ("rising", "falling", "stable")
    """
    entries: List[GasHistoryEntry]
    average_base_fee: float
    min_base_fee: float
    max_base_fee: float
    trend: str


@dataclass
class BatchingRecommendation:
    """Recommendation for transaction batching.
    
    Attributes:
        should_batch: Whether batching is recommended
        optimal_batch_size: Suggested number of transactions per batch
        estimated_savings_eth: Estimated savings from batching
        batching_strategy: Description of recommended approach
    """
    should_batch: bool
    optimal_batch_size: int
    estimated_savings_eth: float
    batching_strategy: str


class GasOptimizer:
    """Main class for Ethereum gas optimization.
    
    Provides methods to estimate costs, find optimal timing,
    calculate EIP-1559 fees, and recommend batching strategies.
    
    Example:
        >>> config = GasConfig(strategy=GasStrategy.ECONOMIC)
        >>> optimizer = GasOptimizer(config)
        >>> fees = optimizer.calculate_eip1559_fees()
        >>> print(f"Max fee: {fees.maxFeePerGas} wei")
    """
    
    # Strategy multipliers for priority fees
    _STRATEGY_MULTIPLIERS = {
        GasStrategy.AGGRESSIVE: 2.5,
        GasStrategy.STANDARD: 1.0,
        GasStrategy.ECONOMIC: 0.5
    }
    
    # Strategy confirmation time targets (in blocks)
    _STRATEGY_CONFIRMATION_TARGETS = {
        GasStrategy.AGGRESSIVE: 1,
        GasStrategy.STANDARD: 4,
        GasStrategy.ECONOMIC: 15
    }
    
    def __init__(self, config: Optional[GasConfig] = None):
        """Initialize GasOptimizer with configuration.
        
        Args:
            config: GasConfig instance or None for defaults
        """
        self.config = config or GasConfig()
        self._base_fee_history: List[float] = []
        self._last_update = datetime.min
        
    def _get_current_base_fee(self) -> float:
        """Get current base fee from network or simulate.
        
        In production, this would query the Ethereum network.
        For simulation, generates realistic base fee values.
        
        Returns:
            Current base fee in gwei
        """
        # Simulate realistic base fee (typically 10-100 gwei)
        # In production, this would call eth_getBlockByNumber
        if not self._base_fee_history:
            base_fee = random.uniform(15, 45)
        else:
            # Random walk with mean reversion
            last_fee = self._base_fee_history[-1]
            change = random.uniform(-5, 5)
            base_fee = max(5, last_fee + change)
        
        self._base_fee_history.append(base_fee)
        if len(self._base_fee_history) > self.config.base_fee_history_size:
            self._base_fee_history.pop(0)
        
        self._last_update = datetime.now()
        return base_fee
    
    def _get_gas_price_data(self) -> Dict[str, float]:
        """Fetch current gas price data.
        
        Returns:
            Dictionary with base_fee, priority_fee, and network_congestion
        """
        base_fee = self._get_current_base_fee()
        
        # Calculate congestion based on recent fee trend
        congestion = 0.5
        if len(self._base_fee_history) >= 5:
            recent = statistics.mean(self._base_fee_history[-5:])
            older = statistics.mean(self._base_fee_history[:-5]) if len(self._base_fee_history) > 5 else recent
            if recent > older * 1.1:
                congestion = 0.8
            elif recent < older * 0.9:
                congestion = 0.2
        
        return {
            "base_fee_gwei": base_fee,
            "network_congestion": congestion,
            "suggested_priority_gwei": self.config.priority_fee_gwei
        }
    
    def estimate_gas(self, transaction_data: Dict[str, Any]) -> GasEstimate:
        """Estimate gas cost for a transaction.
        
        Args:
            transaction_data: Transaction details including 'to', 'data', 'value'
        
        Returns:
            GasEstimate with cost breakdown
        
        Raises:
            GasOptimizationError: If estimation fails
        """
        try:
            # Determine gas limit based on transaction type
            gas_limit = self._estimate_gas_limit(transaction_data)
            
            # Get current fee data
            fee_data = self._get_gas_price_data()
            base_fee = fee_data["base_fee_gwei"]
            
            # Apply strategy multiplier to priority fee
            multiplier = self._STRATEGY_MULTIPLIERS[self.config.strategy]
            priority_fee = self.config.priority_fee_gwei * multiplier
            
            # Ensure we don't exceed max fee
            total_fee_per_gas = min(
                base_fee + priority_fee,
                self.config.max_fee_gwei
            )
            
            # Calculate total cost
            total_cost_gwei = gas_limit * total_fee_per_gas
            total_cost_eth = total_cost_gwei / 1e9
            
            # Estimate confidence based on network stability
            confidence = 0.95 if fee_data["network_congestion"] < 0.5 else 0.75
            
            return GasEstimate(
                gas_limit=gas_limit,
                base_fee_gwei=base_fee,
                priority_fee_gwei=priority_fee,
                total_cost_eth=total_cost_eth,
                confidence=confidence
            )
        
        except Exception as e:
            raise GasOptimizationError(f"Gas estimation failed: {e}")
    
    def _estimate_gas_limit(self, transaction_data: Dict[str, Any]) -> int:
        """Estimate gas limit based on transaction type.
        
        Args:
            transaction_data: Transaction details
        
        Returns:
            Estimated gas limit
        """
        # Standard gas limits for common operations
        if not transaction_data.get('data') or transaction_data.get('data') == '0x':
            # Simple ETH transfer
            return 21000
        
        # Contract interactions (estimates based on common patterns)
        data = transaction_data.get('data', '')
        data_len = len(data) if isinstance(data, str) else len(data.hex())
        
        # ERC-20 transfers typically use ~65k gas
        # More complex operations can use 100k-300k
        if data_len <= 100:
            return 65000
        elif data_len <= 500:
            return 150000
        else:
            return 250000
    
    def get_optimal_timing(self, lookahead_hours: int = 24) -> TimingRecommendation:
        """Find optimal time to submit transaction for lowest fees.
        
        Analyzes historical patterns and current trends to recommend
        the best time window for transaction submission.
        
        Args:
            lookahead_hours: How far ahead to look for optimal time
        
        Returns:
            TimingRecommendation with best time and expected savings
        """
        current_fee = self._get_current_base_fee()
        now = datetime.now()
        
        # Analyze historical patterns for optimal times
        # In production, this would analyze real on-chain data
        
        # Simulate fee patterns (lower on weekends, off-peak hours)
        best_time = self._predict_low_fee_window(now, lookahead_hours)
        
        # Calculate expected savings
        hours_until = (best_time - now).total_seconds() / 3600
        
        # Fees typically 20-40% lower during optimal periods
        if hours_until <= 2:
            savings = 10 + random.uniform(0, 10)
            confidence = 0.8
            reason = "Current conditions are favorable for moderate savings"
        elif hours_until <= 6:
            savings = 20 + random.uniform(0, 15)
            confidence = 0.75
            reason = "Off-peak period approaching, significant savings expected"
        else:
            savings = 25 + random.uniform(0, 20)
            confidence = 0.65
            reason = "Weekend/low-activity period predicted for maximum savings"
        
        expected_fee = current_fee * (1 - savings / 100)
        
        return TimingRecommendation(
            best_time=best_time,
            expected_base_fee_gwei=expected_fee,
            savings_percent=savings,
            confidence=confidence,
            reason=reason
        )
    
    def _predict_low_fee_window(self, from_time: datetime, lookahead_hours: int) -> datetime:
        """Predict when fees will be lowest.
        
        Args:
            from_time: Starting time for prediction
            lookahead_hours: How far ahead to look
        
        Returns:
            Predicted optimal time
        """
        now = from_time
        
        # Check if we're near weekend (lower activity)
        days_until_weekend = (5 - now.weekday()) % 7
        
        if days_until_weekend == 0 and now.hour >= 22:
            # Friday night - wait for Saturday early morning
            return now + timedelta(hours=8 - now.hour % 8)
        
        if days_until_weekend <= 1:
            # Weekend approaching - target Saturday/Sunday early morning UTC
            target = now + timedelta(days=days_until_weekend)
            target = target.replace(hour=4, minute=0)
            if target < now:
                target += timedelta(days=1)
            return target
        
        # Weekday - target early morning UTC (lowest activity)
        if now.hour < 4:
            # Already early morning
            return now + timedelta(minutes=random.randint(5, 30))
        elif now.hour < 12:
            # Morning - wait for afternoon dip or next day
            return now + timedelta(hours=16 - now.hour)
        else:
            # Afternoon/evening - wait for next early morning
            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(hour=4, minute=random.randint(0, 30))
    
    def calculate_eip1559_fees(self) -> EIP1559Fees:
        """Calculate EIP-1559 fee parameters.
        
        Computes maxFeePerGas and maxPriorityFeePerGas based on
        current network conditions and configured strategy.
        
        Returns:
            EIP1559Fees with calculated parameters
        """
        fee_data = self._get_gas_price_data()
        base_fee_gwei = fee_data["base_fee_gwei"]
        
        # Convert gwei to wei
        base_fee_wei = int(base_fee_gwei * 1e9)
        
        # Calculate priority fee based on strategy
        multiplier = self._STRATEGY_MULTIPLIERS[self.config.strategy]
        priority_fee_gwei = self.config.priority_fee_gwei * multiplier
        
        # Add congestion premium if network is busy
        if fee_data["network_congestion"] > 0.7:
            priority_fee_gwei *= 1.5
        
        priority_fee_wei = int(priority_fee_gwei * 1e9)
        
        # maxFeePerGas must cover base fee + priority fee with buffer
        # Buffer varies by strategy - aggressive needs less buffer
        if self.config.strategy == GasStrategy.AGGRESSIVE:
            buffer = 1.1  # 10% buffer
        elif self.config.strategy == GasStrategy.STANDARD:
            buffer = 1.25  # 25% buffer
        else:
            buffer = 1.5  # 50% buffer for economic
        
        max_fee_wei = int(min(
            (base_fee_gwei * buffer + priority_fee_gwei) * 1e9,
            self.config.max_fee_gwei * 1e9
        ))
        
        # Ensure maxFeePerGas >= maxPriorityFeePerGas
        max_fee_wei = max(max_fee_wei, priority_fee_wei)
        
        confirmation_target = self._STRATEGY_CONFIRMATION_TARGETS[self.config.strategy]
        
        return EIP1559Fees(
            maxFeePerGas=max_fee_wei,
            maxPriorityFeePerGas=priority_fee_wei,
            baseFeePerGas=base_fee_wei,
            estimated_confirmation_blocks=confirmation_target
        )
    
    def check_gas_history(self, days: int = 7) -> GasHistory:
        """Analyze historical gas price trends.
        
        Retrieves and analyzes gas prices over specified period
        to identify patterns and trends.
        
        Args:
            days: Number of days to analyze (default 7)
        
        Returns:
            GasHistory with trend analysis
        """
        entries = []
        now = datetime.now()
        
        # Generate simulated historical data
        # In production, this would query historical block data
        current_base = self._get_current_base_fee()
        
        for i in range(days * 24):  # hourly entries
            timestamp = now - timedelta(hours=i)
            
            # Simulate daily pattern (higher during business hours)
            hour_factor = 1.0
            if 9 <= timestamp.hour <= 17:
                hour_factor = 1.3
            elif timestamp.hour < 6:
                hour_factor = 0.8
            
            # Weekend factor
            if timestamp.weekday() >= 5:
                hour_factor *= 0.85
            
            # Add randomness and trend
            random_factor = random.uniform(0.9, 1.1)
            base_fee = current_base * hour_factor * random_factor
            priority_fee = self.config.priority_fee_gwei * random_factor
            
            entries.append(GasHistoryEntry(
                timestamp=timestamp,
                base_fee_gwei=base_fee,
                priority_fee_gwei=priority_fee,
                block_number=18_000_000 - i * 300  # approx blocks per hour
            ))
        
        # Sort chronologically
        entries.sort(key=lambda x: x.timestamp)
        
        # Calculate statistics
        base_fees = [e.base_fee_gwei for e in entries]
        avg_base = statistics.mean(base_fees)
        min_base = min(base_fees)
        max_base = max(base_fees)
        
        # Determine trend
        recent_avg = statistics.mean(base_fees[-24:])
        older_avg = statistics.mean(base_fees[:-24]) if len(base_fees) > 24 else recent_avg
        
        if recent_avg > older_avg * 1.1:
            trend = "rising"
        elif recent_avg < older_avg * 0.9:
            trend = "falling"
        else:
            trend = "stable"
        
        return GasHistory(
            entries=entries,
            average_base_fee=avg_base,
            min_base_fee=min_base,
            max_base_fee=max_base,
            trend=trend
        )
    
    def recommend_batching(self, transactions: List[Dict[str, Any]]) -> BatchingRecommendation:
        """Recommend transaction batching strategy.
        
        Analyzes a list of transactions to determine if batching
        would reduce total fees.
        
        Args:
            transactions: List of transaction data dictionaries
        
        Returns:
            BatchingRecommendation with strategy advice
        """
        if not transactions:
            return BatchingRecommendation(
                should_batch=False,
                optimal_batch_size=1,
                estimated_savings_eth=0.0,
                batching_strategy="No transactions to batch"
            )
        
        tx_count = len(transactions)
        
        # Analyze transaction types
        simple_transfers = sum(
            1 for tx in transactions 
            if not tx.get('data') or tx.get('data') == '0x'
        )
        contract_calls = tx_count - simple_transfers
        
        # Get current fee estimate for single transaction
        fee_data = self._get_gas_price_data()
        base_fee = fee_data["base_fee_gwei"]
        
        # Estimate individual costs
        individual_gas = sum(
            self._estimate_gas_limit(tx) for tx in transactions
        )
        individual_cost_eth = (individual_gas * base_fee) / 1e9
        
        # Estimate batched cost
        # Batching saves on base transaction overhead (21k gas each)
        # but adds some overhead for batch logic (~5k per tx)
        if simple_transfers == tx_count:
            # All simple transfers - good batching candidate
            batch_overhead = 25000  # Base batch contract overhead
            per_tx_savings = 16000  # 21k - 5k overhead
            batched_gas = batch_overhead + (tx_count * 5000)
            optimal_size = min(tx_count, 20)  # ERC20 batch limit often 20
        elif contract_calls > 0:
            # Mixed or complex - moderate savings
            batch_overhead = 40000
            per_tx_savings = 10000
            batched_gas = batch_overhead + sum(
                self._estimate_gas_limit(tx) * 0.7 for tx in transactions
            )
            optimal_size = min(tx_count, 10)
        else:
            # All complex - limited batching benefit
            batch_overhead = 50000
            per_tx_savings = 5000
            batched_gas = batch_overhead + sum(
                self._estimate_gas_limit(tx) * 0.85 for tx in transactions
            )
            optimal_size = min(tx_count, 5)
        
        batched_cost_eth = (batched_gas * base_fee) / 1e9
        savings = individual_cost_eth - batched_cost_eth
        savings_percent = (savings / individual_cost_eth * 100) if individual_cost_eth > 0 else 0
        
        should_batch = savings > 0.0005 and tx_count >= 2  # At least 0.0005 ETH savings
        
        if should_batch:
            if simple_transfers == tx_count:
                strategy = f"Batch all {tx_count} transfers using multicall contract"
            elif simple_transfers > contract_calls:
                strategy = f"Group {simple_transfers} transfers, handle {contract_calls} contract calls separately"
            else:
                strategy = f"Batch in groups of {optimal_size} to minimize gas while maintaining reliability"
        else:
            strategy = "Individual transactions are more cost-effective for this set"
            optimal_size = 1
        
        return BatchingRecommendation(
            should_batch=should_batch,
            optimal_batch_size=optimal_size,
            estimated_savings_eth=max(0, savings),
            batching_strategy=strategy
        )
    
    def get_current_network_conditions(self) -> Dict[str, Any]:
        """Get summary of current network conditions.
        
        Returns:
            Dictionary with base fee, congestion, and recommendations
        """
        fee_data = self._get_gas_price_data()
        
        return {
            "base_fee_gwei": round(fee_data["base_fee_gwei"], 2),
            "network_congestion": round(fee_data["network_congestion"], 2),
            "suggested_strategy": self.config.strategy.value,
            "current_time": datetime.now().isoformat(),
            "recommendation": self._get_condition_recommendation(fee_data)
        }
    
    def _get_condition_recommendation(self, fee_data: Dict[str, float]) -> str:
        """Generate recommendation based on network conditions.
        
        Args:
            fee_data: Current fee and congestion data
        
        Returns:
            Recommendation string
        """
        base_fee = fee_data["base_fee_gwei"]
        congestion = fee_data["network_congestion"]
        
        if base_fee < 15 and congestion < 0.3:
            return "Excellent time to transact - low fees and minimal congestion"
        elif base_fee < 30 and congestion < 0.5:
            return "Good conditions for standard transactions"
        elif congestion > 0.7:
            return "High congestion - consider waiting or using aggressive strategy"
        elif base_fee > 80:
            return "Very high base fees - recommend waiting for lower period"
        else:
            return "Moderate network conditions - standard strategy recommended"


# Convenience functions for quick access

def quick_estimate(strategy: str = "standard") -> GasEstimate:
    """Quick gas estimate with default configuration.
    
    Args:
        strategy: "aggressive", "standard", or "economic"
    
    Returns:
        GasEstimate for simple transfer
    """
    strat = GasStrategy(strategy.lower())
    config = GasConfig(strategy=strat)
    optimizer = GasOptimizer(config)
    return optimizer.estimate_gas({"to": "0x...", "value": 0})


def get_recommended_fees(strategy: str = "standard") -> EIP1559Fees:
    """Get recommended EIP-1559 fees.
    
    Args:
        strategy: "aggressive", "standard", or "economic"
    
    Returns:
        EIP1559Fees with recommended values
    """
    strat = GasStrategy(strategy.lower())
    config = GasConfig(strategy=strat)
    optimizer = GasOptimizer(config)
    return optimizer.calculate_eip1559_fees()


def should_wait_for_better_fees(current_fee_gwei: float, urgency: str = "normal") -> bool:
    """Determine if waiting might yield better fees.
    
    Args:
        current_fee_gwei: Current base fee in gwei
        urgency: "low", "normal", or "high"
    
    Returns:
        True if waiting is recommended
    """
    if urgency == "high":
        return False
    
    if urgency == "low" and current_fee_gwei > 20:
        return True
    
    if urgency == "normal" and current_fee_gwei > 50:
        return True
    
    return False
