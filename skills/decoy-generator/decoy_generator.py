"""
Decoy Generator - Creates synthetic transactions to mask real trading activity.

This module provides tools for generating realistic decoy transactions that can be
mixed with real trades to obfuscate trading patterns, confuse MEV bots, and
provide plausible deniability.
"""

import random
import time
import uuid
import hashlib
import secrets
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DecoyGenerator")


class DecoyType(Enum):
    """Types of decoy transactions supported"""
    TRADE = "trade"
    TRANSFER = "transfer"
    APPROVAL = "approval"
    SWAP = "swap"
    BRIDGE = "bridge"


class DecoyStatus(Enum):
    """Lifecycle status of a decoy transaction"""
    CREATED = auto()
    QUEUED = auto()
    EXECUTING = auto()
    EXECUTED = auto()
    FAILED = auto()
    RETIRED = auto()


class FrequencyPattern(Enum):
    """Distribution patterns for decoy timing"""
    RANDOM = "random"
    UNIFORM = "uniform"
    BURST = "burst"
    POISSON = "poisson"


class SizeStrategy(Enum):
    """Strategies for calculating decoy transaction sizes"""
    PROPORTIONAL = "proportional"      # Based on reference amount
    FIXED_RANGE = "fixed_range"        # Within absolute bounds
    VOLUME_MIMIC = "volume_mimic"      # Match market patterns
    NOISE_FLOOR = "noise_floor"        # Minimum viable size


@dataclass
class DecoyConfig:
    """Configuration for decoy generation parameters
    
    Attributes:
        ratio: Number of decoys per real transaction (e.g., 2.0 = 2:1)
        size_range: Min/max multiplier relative to reference transaction
        absolute_range: Min/max absolute values (optional, overrides proportional)
        frequency: Timing distribution pattern
        decoy_types: List of decoy types to generate
        size_strategy: How to calculate decoy sizes
        jitter_range: Min/max delay in seconds before execution
        retire_after: Auto-retire decoys after this many seconds
        gas_price_range: Min/max gas price multiplier
        include_failures: Whether to simulate some failed transactions
        failure_rate: Probability of simulated failure (0.0-1.0)
    """
    ratio: float = 1.0
    size_range: Tuple[float, float] = (0.05, 2.0)
    absolute_range: Optional[Tuple[float, float]] = None
    frequency: FrequencyPattern = FrequencyPattern.RANDOM
    decoy_types: List[DecoyType] = field(default_factory=lambda: [DecoyType.TRADE])
    size_strategy: SizeStrategy = SizeStrategy.PROPORTIONAL
    jitter_range: Tuple[int, int] = (1, 300)
    retire_after: int = 86400  # 24 hours
    gas_price_range: Tuple[float, float] = (0.8, 1.5)
    include_failures: bool = False
    failure_rate: float = 0.05


@dataclass
class DecoyTransaction:
    """Represents a single decoy transaction
    
    Attributes:
        decoy_id: Unique identifier for this decoy
        decoy_type: Type of transaction (trade, transfer, etc.)
        amount: Transaction amount in base currency
        symbol: Trading pair or token symbol
        status: Current lifecycle status
        created_at: Timestamp when decoy was created
        execute_at: Scheduled execution time
        gas_price: Simulated gas price
        metadata: Additional type-specific data
        related_real_tx: ID of the real transaction this masks
    """
    decoy_id: str
    decoy_type: DecoyType
    amount: float
    symbol: str
    status: DecoyStatus = DecoyStatus.CREATED
    created_at: float = field(default_factory=time.time)
    execute_at: Optional[float] = None
    gas_price: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    related_real_tx: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert decoy to dictionary representation"""
        return {
            "decoy_id": self.decoy_id,
            "decoy_type": self.decoy_type.value,
            "amount": self.amount,
            "symbol": self.symbol,
            "status": self.status.name,
            "created_at": self.created_at,
            "execute_at": self.execute_at,
            "gas_price": self.gas_price,
            "metadata": self.metadata,
            "related_real_tx": self.related_real_tx
        }


class DecoyLifecycleManager:
    """Manages the lifecycle of decoy transactions from creation to retirement"""
    
    def __init__(self, config: DecoyConfig):
        self.config = config
        self.active_decoys: Dict[str, DecoyTransaction] = {}
        self.decoy_history: List[DecoyTransaction] = []
        self._retired_count = 0
    
    def create(self, decoy: DecoyTransaction) -> DecoyTransaction:
        """Register a newly created decoy
        
        Args:
            decoy: The decoy transaction to register
            
        Returns:
            The registered decoy with updated status
        """
        decoy.status = DecoyStatus.CREATED
        self.active_decoys[decoy.decoy_id] = decoy
        logger.debug(f"Created decoy {decoy.decoy_id[:12]}... ({decoy.decoy_type.value})")
        return decoy
    
    def queue(self, decoy_id: str, execute_at: Optional[float] = None) -> DecoyTransaction:
        """Queue a decoy for execution
        
        Args:
            decoy_id: ID of the decoy to queue
            execute_at: Optional scheduled execution time
            
        Returns:
            The updated decoy transaction
        """
        if decoy_id not in self.active_decoys:
            raise ValueError(f"Decoy {decoy_id} not found")
        
        decoy = self.active_decoys[decoy_id]
        decoy.status = DecoyStatus.QUEUED
        decoy.execute_at = execute_at or (time.time() + random.randint(*self.config.jitter_range))
        logger.debug(f"Queued decoy {decoy_id[:12]}... for execution at {decoy.execute_at}")
        return decoy
    
    def execute(self, decoy_id: str) -> Dict[str, Any]:
        """Mark a decoy as executed
        
        Args:
            decoy_id: ID of the decoy being executed
            
        Returns:
            Execution result dictionary
        """
        if decoy_id not in self.active_decoys:
            raise ValueError(f"Decoy {decoy_id} not found")
        
        decoy = self.active_decoys[decoy_id]
        
        # Simulate potential failure
        if self.config.include_failures and random.random() < self.config.failure_rate:
            decoy.status = DecoyStatus.FAILED
            result = {
                "status": "failed",
                "decoy_id": decoy_id,
                "error": "simulated_failure",
                "timestamp": time.time()
            }
        else:
            decoy.status = DecoyStatus.EXECUTED
            result = {
                "status": "success",
                "decoy_id": decoy_id,
                "tx_hash": self._generate_fake_tx_hash(),
                "block_number": random.randint(1000000, 9999999),
                "timestamp": time.time(),
                "gas_used": random.randint(21000, 200000)
            }
        
        logger.debug(f"Executed decoy {decoy_id[:12]}... with status {result['status']}")
        return result
    
    def retire(self, decoy_id: str) -> DecoyTransaction:
        """Retire a decoy from active duty
        
        Args:
            decoy_id: ID of the decoy to retire
            
        Returns:
            The retired decoy transaction
        """
        if decoy_id not in self.active_decoys:
            raise ValueError(f"Decoy {decoy_id} not found")
        
        decoy = self.active_decoys.pop(decoy_id)
        decoy.status = DecoyStatus.RETIRED
        self.decoy_history.append(decoy)
        self._retired_count += 1
        
        # Limit history size
        if len(self.decoy_history) > 1000:
            self.decoy_history.pop(0)
        
        logger.debug(f"Retired decoy {decoy_id[:12]}...")
        return decoy
    
    def retire_expired(self) -> List[DecoyTransaction]:
        """Auto-retire decoys that have exceeded their lifetime
        
        Returns:
            List of retired decoy transactions
        """
        now = time.time()
        expired_ids = [
            did for did, d in self.active_decoys.items()
            if (now - d.created_at) > self.config.retire_after
        ]
        
        retired = []
        for did in expired_ids:
            retired.append(self.retire(did))
        
        if retired:
            logger.info(f"Auto-retired {len(retired)} expired decoys")
        return retired
    
    def get_stats(self) -> Dict[str, Any]:
        """Get lifecycle statistics
        
        Returns:
            Dictionary with decoy statistics
        """
        statuses = {}
        for d in self.active_decoys.values():
            statuses[d.status.name] = statuses.get(d.status.name, 0) + 1
        
        return {
            "active_count": len(self.active_decoys),
            "history_count": len(self.decoy_history),
            "total_retired": self._retired_count,
            "by_status": statuses
        }
    
    def _generate_fake_tx_hash(self) -> str:
        """Generate a realistic-looking transaction hash"""
        return "0x" + secrets.token_hex(32)


class DecoyGenerator:
    """Core engine for generating synthetic transactions"""
    
    def __init__(self, config: Optional[DecoyConfig] = None):
        self.config = config or DecoyConfig()
        self.lifecycle = DecoyLifecycleManager(self.config)
        
        # Common symbols for different decoy types
        self.symbols_by_type = {
            DecoyType.TRADE: ["BTC-USD", "ETH-USD", "SOL-USD", "ARB-USD", "OP-USD"],
            DecoyType.TRANSFER: ["ETH", "USDC", "USDT", "DAI", "WBTC"],
            DecoyType.APPROVAL: ["USDC", "USDT", "DAI", "WETH", "LINK"],
            DecoyType.SWAP: ["ETH-USDC", "WBTC-ETH", "USDC-DAI", "LINK-ETH"],
            DecoyType.BRIDGE: ["ETH-ARB", "ETH-OP", "ETH-POLY", "ETH-BASE"]
        }
    
    def generate_decoy_transaction(
        self,
        reference_amount: float = 1000.0,
        decoy_type: Optional[DecoyType] = None,
        symbol: Optional[str] = None,
        related_real_tx: Optional[str] = None
    ) -> DecoyTransaction:
        """Generate a single decoy transaction
        
        Args:
            reference_amount: The real transaction amount to base decoy size on
            decoy_type: Type of decoy (random if not specified)
            symbol: Trading pair or token symbol (random if not specified)
            related_real_tx: ID of the real transaction this decoy masks
            
        Returns:
            A new DecoyTransaction instance
        """
        # Select decoy type
        if decoy_type is None:
            decoy_type = random.choice(self.config.decoy_types)
        
        # Select symbol
        if symbol is None:
            symbol = random.choice(self.symbols_by_type.get(decoy_type, ["ETH"]))
        
        # Calculate amount
        amount = self.calculate_decoy_size(reference_amount, decoy_type)
        
        # Generate unique ID
        decoy_id = self._generate_decoy_id(decoy_type, symbol)
        
        # Generate metadata based on type
        metadata = self._generate_metadata(decoy_type, amount, symbol)
        
        # Create decoy
        decoy = DecoyTransaction(
            decoy_id=decoy_id,
            decoy_type=decoy_type,
            amount=amount,
            symbol=symbol,
            gas_price=random.uniform(*self.config.gas_price_range),
            metadata=metadata,
            related_real_tx=related_real_tx
        )
        
        # Register with lifecycle manager
        self.lifecycle.create(decoy)
        
        logger.info(f"Generated {decoy_type.value} decoy: {amount:.4f} {symbol}")
        return decoy
    
    def generate_decoy_batch(
        self,
        real_transactions: List[Dict[str, Any]],
        batch_size: Optional[int] = None
    ) -> List[DecoyTransaction]:
        """Generate a batch of decoy transactions
        
        Args:
            real_transactions: List of real transactions to generate decoys for
            batch_size: Override the number of decoys (default: based on ratio)
            
        Returns:
            List of generated DecoyTransaction instances
        """
        if batch_size is None:
            batch_size = int(len(real_transactions) * self.config.ratio)
        
        decoys = []
        for i in range(batch_size):
            # Pick a random real transaction as reference
            if real_transactions:
                ref_tx = random.choice(real_transactions)
                ref_amount = ref_tx.get("amount", 1000.0)
                ref_symbol = ref_tx.get("symbol", "ETH-USD")
                ref_id = ref_tx.get("tx_id") or ref_tx.get("id")
            else:
                ref_amount = 1000.0
                ref_symbol = None
                ref_id = None
            
            decoy = self.generate_decoy_transaction(
                reference_amount=ref_amount,
                symbol=ref_symbol,
                related_real_tx=ref_id
            )
            decoys.append(decoy)
        
        logger.info(f"Generated batch of {len(decoys)} decoys")
        return decoys
    
    def mix_decoys_with_real(
        self,
        real_transactions: List[Dict[str, Any]],
        decoy_transactions: Optional[List[DecoyTransaction]] = None,
        shuffle: bool = True
    ) -> List[Dict[str, Any]]:
        """Shuffle decoys into real transactions for obfuscation
        
        Args:
            real_transactions: List of real transaction dictionaries
            decoy_transactions: List of decoy transactions (generated if None)
            shuffle: Whether to randomize the order
            
        Returns:
            Mixed list of transactions (as dictionaries)
        """
        # Generate decoys if not provided
        if decoy_transactions is None:
            decoy_transactions = self.generate_decoy_batch(real_transactions)
        
        # Convert everything to dictionaries
        mixed = [tx for tx in real_transactions]
        for decoy in decoy_transactions:
            decoy_dict = decoy.to_dict()
            decoy_dict["is_decoy"] = True
            mixed.append(decoy_dict)
        
        # Apply timing jitter based on frequency pattern
        mixed = self._apply_timing_pattern(mixed)
        
        # Shuffle if requested
        if shuffle:
            random.shuffle(mixed)
        
        logger.info(f"Mixed {len(real_transactions)} real + {len(decoy_transactions)} decoy = {len(mixed)} total")
        return mixed
    
    def calculate_decoy_size(
        self,
        reference_amount: float,
        decoy_type: Optional[DecoyType] = None
    ) -> float:
        """Calculate a realistic decoy transaction size
        
        Args:
            reference_amount: The reference transaction amount
            decoy_type: Type of decoy (affects size calculation)
            
        Returns:
            Calculated decoy amount
        """
        strategy = self.config.size_strategy
        
        if strategy == SizeStrategy.PROPORTIONAL:
            min_mult, max_mult = self.config.size_range
            multiplier = random.uniform(min_mult, max_mult)
            amount = reference_amount * multiplier
            
        elif strategy == SizeStrategy.FIXED_RANGE:
            if self.config.absolute_range:
                min_val, max_val = self.config.absolute_range
            else:
                min_val, max_val = 10.0, 10000.0
            amount = random.uniform(min_val, max_val)
            
        elif strategy == SizeStrategy.VOLUME_MIMIC:
            # Simulate typical market volume distribution (log-normal-ish)
            log_mean = 7.0  # ~$1000
            log_std = 1.5
            amount = random.lognormvariate(log_mean, log_std)
            
        elif strategy == SizeStrategy.NOISE_FLOOR:
            # Minimum viable + small random component
            base = max(reference_amount * 0.01, 10.0)
            amount = base + random.uniform(0, base * 0.5)
            
        else:
            amount = reference_amount * random.uniform(0.5, 1.5)
        
        # Type-specific adjustments
        if decoy_type == DecoyType.APPROVAL:
            # Approvals often have specific values (max or 0)
            if random.random() < 0.3:
                amount = 0  # Revocation
            else:
                amount = 2**256 - 1  # Max approval (as float)
        
        elif decoy_type == DecoyType.TRANSFER:
            # Transfers often round numbers
            amount = round(amount, -int(len(str(int(amount))) - 2)) if amount > 100 else round(amount, 2)
        
        return max(0.0, round(amount, 6))
    
    def execute_decoy(self, decoy_id: str) -> Dict[str, Any]:
        """Execute a specific decoy transaction
        
        Args:
            decoy_id: ID of the decoy to execute
            
        Returns:
            Execution result dictionary
        """
        # Queue if not already
        decoy = self.lifecycle.active_decoys.get(decoy_id)
        if decoy and decoy.status == DecoyStatus.CREATED:
            self.lifecycle.queue(decoy_id)
        
        # Execute
        return self.lifecycle.execute(decoy_id)
    
    def execute_pending(self) -> List[Dict[str, Any]]:
        """Execute all pending (queued) decoys
        
        Returns:
            List of execution results
        """
        now = time.time()
        pending = [
            (did, d) for did, d in self.lifecycle.active_decoys.items()
            if d.status == DecoyStatus.QUEUED and d.execute_at and d.execute_at <= now
        ]
        
        results = []
        for did, decoy in pending:
            result = self.lifecycle.execute(did)
            results.append(result)
        
        if results:
            logger.info(f"Executed {len(results)} pending decoys")
        return results
    
    def cleanup(self) -> int:
        """Clean up retired and expired decoys
        
        Returns:
            Number of decoys cleaned up
        """
        retired = self.lifecycle.retire_expired()
        return len(retired)
    
    def _generate_decoy_id(self, decoy_type: DecoyType, symbol: str) -> str:
        """Generate a unique decoy identifier"""
        timestamp = str(time.time())
        nonce = secrets.token_hex(8)
        data = f"DECOY:{decoy_type.value}:{symbol}:{timestamp}:{nonce}"
        return f"decoy_{hashlib.sha256(data.encode()).hexdigest()[:20]}"
    
    def _generate_metadata(
        self,
        decoy_type: DecoyType,
        amount: float,
        symbol: str
    ) -> Dict[str, Any]:
        """Generate type-specific metadata for a decoy"""
        metadata = {
            "generated_at": datetime.now().astimezone().isoformat(),
            "version": "1.0"
        }
        
        if decoy_type == DecoyType.TRADE:
            metadata.update({
                "side": random.choice(["buy", "sell"]),
                "order_type": random.choice(["market", "limit"]),
                "slippage": round(random.uniform(0.001, 0.03), 4),
                "venue": random.choice(["uniswap", "sushiswap", "kraken", "coinbase"])
            })
            
        elif decoy_type == DecoyType.TRANSFER:
            metadata.update({
                "to_address": "0x" + secrets.token_hex(20),
                "memo": "decoy_transfer" if random.random() < 0.5 else "",
                "multi_hop": random.random() < 0.3
            })
            
        elif decoy_type == DecoyType.APPROVAL:
            metadata.update({
                "spender": "0x" + secrets.token_hex(20),
                "current_allowance": random.uniform(0, amount * 2) if amount < 2**200 else 0,
                "is_revoke": amount == 0
            })
            
        elif decoy_type == DecoyType.SWAP:
            metadata.update({
                "input_token": symbol.split("-")[0] if "-" in symbol else symbol,
                "output_token": symbol.split("-")[1] if "-" in symbol else "USDC",
                "pool_fee": random.choice([100, 500, 3000, 10000]),  # bps
                "min_out": amount * random.uniform(0.95, 0.99)
            })
            
        elif decoy_type == DecoyType.BRIDGE:
            metadata.update({
                "source_chain": symbol.split("-")[0] if "-" in symbol else "ETH",
                "dest_chain": symbol.split("-")[1] if "-" in symbol else "ARB",
                "bridge_provider": random.choice(["hop", "across", "stargate", "layerzero"]),
                "estimated_time": random.randint(300, 1800)  # seconds
            })
        
        return metadata
    
    def _apply_timing_pattern(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply the configured timing pattern to transactions"""
        pattern = self.config.frequency
        now = time.time()
        
        if pattern == FrequencyPattern.RANDOM:
            for tx in transactions:
                delay = random.randint(*self.config.jitter_range)
                tx["scheduled_time"] = now + delay
                
        elif pattern == FrequencyPattern.UNIFORM:
            interval = (self.config.jitter_range[1] - self.config.jitter_range[0]) / max(len(transactions), 1)
            for i, tx in enumerate(transactions):
                tx["scheduled_time"] = now + self.config.jitter_range[0] + (i * interval)
                
        elif pattern == FrequencyPattern.BURST:
            # Cluster transactions into groups
            burst_size = max(1, len(transactions) // 3)
            for i, tx in enumerate(transactions):
                burst_num = i // burst_size
                tx["scheduled_time"] = now + (burst_num * 60) + random.randint(0, 10)
                
        elif pattern == FrequencyPattern.POISSON:
            # Poisson-like distribution
            lambda_param = sum(self.config.jitter_range) / 2 / 60  # events per minute
            current_time = now
            for tx in transactions:
                # Exponential inter-arrival times
                inter_arrival = random.expovariate(lambda_param) * 60
                current_time += inter_arrival
                tx["scheduled_time"] = current_time
        
        return transactions
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive generator statistics"""
        lifecycle_stats = self.lifecycle.get_stats()
        
        return {
            **lifecycle_stats,
            "config": {
                "ratio": self.config.ratio,
                "size_strategy": self.config.size_strategy.value,
                "frequency": self.config.frequency.value,
                "decoy_types": [t.value for t in self.config.decoy_types]
            }
        }


# Convenience functions for quick usage
def create_trade_decoy(amount: float, symbol: str = "ETH-USD") -> DecoyTransaction:
    """Quick factory for trade decoys"""
    config = DecoyConfig(decoy_types=[DecoyType.TRADE])
    generator = DecoyGenerator(config)
    return generator.generate_decoy_transaction(
        reference_amount=amount,
        decoy_type=DecoyType.TRADE,
        symbol=symbol
    )


def create_transfer_decoy(amount: float, token: str = "ETH") -> DecoyTransaction:
    """Quick factory for transfer decoys"""
    config = DecoyConfig(decoy_types=[DecoyType.TRANSFER])
    generator = DecoyGenerator(config)
    return generator.generate_decoy_transaction(
        reference_amount=amount,
        decoy_type=DecoyType.TRANSFER,
        symbol=token
    )


def create_approval_decoy(token: str = "USDC") -> DecoyTransaction:
    """Quick factory for approval decoys"""
    config = DecoyConfig(decoy_types=[DecoyType.APPROVAL])
    generator = DecoyGenerator(config)
    return generator.generate_decoy_transaction(
        reference_amount=2**256,  # Max approval
        decoy_type=DecoyType.APPROVAL,
        symbol=token
    )


# Example usage
if __name__ == "__main__":
    # Demo the decoy generator
    print("=== DECOY GENERATOR DEMO ===\n")
    
    # Create generator with custom config
    config = DecoyConfig(
        ratio=2.0,
        size_range=(0.1, 1.5),
        decoy_types=[DecoyType.TRADE, DecoyType.TRANSFER],
        frequency=FrequencyPattern.RANDOM
    )
    generator = DecoyGenerator(config)
    
    # Simulate some real transactions
    real_trades = [
        {"tx_id": f"real_{i}", "amount": random.uniform(500, 5000), "symbol": "ETH-USD"}
        for i in range(3)
    ]
    print(f"Real transactions: {len(real_trades)}")
    for tx in real_trades:
        print(f"  - {tx['tx_id']}: ${tx['amount']:.2f} {tx['symbol']}")
    
    # Generate decoys
    print("\n--- Generating Decoys ---")
    decoys = generator.generate_decoy_batch(real_trades)
    for d in decoys:
        print(f"  - {d.decoy_id[:20]}...: {d.amount:.4f} {d.symbol} ({d.decoy_type.value})")
    
    # Mix with real
    print("\n--- Mixed Transactions ---")
    mixed = generator.mix_decoys_with_real(real_trades, decoys)
    for tx in mixed:
        is_decoy = tx.get("is_decoy", False)
        prefix = "[DECOY]" if is_decoy else "[REAL] "
        print(f"  {prefix} {tx.get('symbol', 'N/A')}: {tx.get('amount', 0):.4f}")
    
    # Show stats
    print("\n--- Statistics ---")
    stats = generator.get_statistics()
    print(f"Active decoys: {stats['active_count']}")
    print(f"Config ratio: {stats['config']['ratio']}")
    print(f"Size strategy: {stats['config']['size_strategy']}")
