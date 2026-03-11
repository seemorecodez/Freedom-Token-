"""
Profit Switcher - Real-time PoW mining profitability comparison with automatic switching.

This module provides tools to compare cryptocurrency mining profitability across
different algorithms and automatically switch to the most profitable option.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SwitchReason(Enum):
    """Reasons for switching coins."""
    PROFIT_THRESHOLD = "profit_threshold"
    COOLDOWN_EXPIRED = "cooldown_expired"
    NO_SWITCH = "no_switch"
    ERROR = "error"


@dataclass
class MiningData:
    """Represents mining data for a specific coin."""
    coin: str
    difficulty: float
    price: float
    block_reward: float
    network_hashrate: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "coin": self.coin,
            "difficulty": self.difficulty,
            "price": self.price,
            "block_reward": self.block_reward,
            "network_hashrate": self.network_hashrate,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MiningData":
        """Create from dictionary."""
        return cls(
            coin=data["coin"],
            difficulty=data["difficulty"],
            price=data["price"],
            block_reward=data["block_reward"],
            network_hashrate=data.get("network_hashrate"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now()
        )


@dataclass
class ProfitResult:
    """Represents profitability calculation result for a coin."""
    coin: str
    algorithm: str
    revenue_per_day: float
    cost_per_day: float
    profit_per_day: float
    profit_per_mh: float
    hashrate_mh: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "coin": self.coin,
            "algorithm": self.algorithm,
            "revenue_per_day": self.revenue_per_day,
            "cost_per_day": self.cost_per_day,
            "profit_per_day": self.profit_per_day,
            "profit_per_mh": self.profit_per_mh,
            "hashrate_mh": self.hashrate_mh,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfitResult":
        """Create from dictionary."""
        return cls(
            coin=data["coin"],
            algorithm=data["algorithm"],
            revenue_per_day=data["revenue_per_day"],
            cost_per_day=data["cost_per_day"],
            profit_per_day=data["profit_per_day"],
            profit_per_mh=data["profit_per_mh"],
            hashrate_mh=data["hashrate_mh"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now()
        )


@dataclass
class SwitchEvent:
    """Represents a coin switch event."""
    from_coin: str
    to_coin: str
    reason: str
    profit_before: float
    profit_after: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "from_coin": self.from_coin,
            "to_coin": self.to_coin,
            "reason": self.reason,
            "profit_before": self.profit_before,
            "profit_after": self.profit_after,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ProfitConfig:
    """Configuration for profit switching."""
    coins: List[Dict[str, Any]] = field(default_factory=list)
    electricity_cost_per_kwh: float = 0.10
    pool_fee_percent: float = 2.0
    miner_power_watts: float = 1000.0
    switch_threshold_percent: float = 5.0
    cooldown_minutes: int = 10
    min_profit_duration_minutes: int = 2
    dry_run: bool = True  # Safety: default to dry-run mode
    
    def __post_init__(self):
        """Validate configuration."""
        if not self.coins:
            logger.warning("No coins configured")
        if self.electricity_cost_per_kwh < 0:
            raise ValueError("Electricity cost cannot be negative")
        if self.pool_fee_percent < 0 or self.pool_fee_percent > 100:
            raise ValueError("Pool fee must be between 0 and 100")
        if self.miner_power_watts <= 0:
            raise ValueError("Miner power must be positive")


class ProfitHistory:
    """Tracks historical profitability data and switch events."""
    
    def __init__(self, max_entries: int = 10000):
        self.entries: List[ProfitResult] = []
        self.switches: List[SwitchEvent] = []
        self.max_entries = max_entries
        self._coin_profit_start: Dict[str, datetime] = {}
        self._last_switch_time: Optional[datetime] = None
    
    def add_entry(self, result: ProfitResult):
        """Add a profit result entry."""
        self.entries.append(result)
        
        # Trim old entries
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
    
    def add_switch(self, event: SwitchEvent):
        """Record a switch event."""
        self.switches.append(event)
        self._last_switch_time = event.timestamp
        logger.info(f"Switch recorded: {event.from_coin} -> {event.to_coin} ({event.reason})")
    
    def get_entries_for_coin(self, coin: str, hours: int = 24) -> List[ProfitResult]:
        """Get profit entries for a specific coin within time window."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [e for e in self.entries if e.coin == coin and e.timestamp >= cutoff]
    
    def get_average_profit(self, coin: str, hours: int = 24) -> float:
        """Calculate average profit for a coin over time period."""
        entries = self.get_entries_for_coin(coin, hours)
        if not entries:
            return 0.0
        return sum(e.profit_per_day for e in entries) / len(entries)
    
    def get_best_performing(self, hours: int = 24) -> Optional[str]:
        """Get the best performing coin over time period."""
        cutoff = datetime.now() - timedelta(hours=hours)
        coin_profits: Dict[str, List[float]] = {}
        
        for entry in self.entries:
            if entry.timestamp >= cutoff:
                if entry.coin not in coin_profits:
                    coin_profits[entry.coin] = []
                coin_profits[entry.coin].append(entry.profit_per_day)
        
        if not coin_profits:
            return None
        
        avg_profits = {
            coin: sum(profits) / len(profits)
            for coin, profits in coin_profits.items()
        }
        
        return max(avg_profits, key=avg_profits.get)
    
    def get_time_since_last_switch(self) -> Optional[timedelta]:
        """Get time elapsed since last switch."""
        if self._last_switch_time is None:
            return None
        return datetime.now() - self._last_switch_time
    
    def is_in_cooldown(self, cooldown_minutes: int) -> bool:
        """Check if currently in cooldown period."""
        time_since = self.get_time_since_last_switch()
        if time_since is None:
            return False
        return time_since < timedelta(minutes=cooldown_minutes)
    
    def update_coin_lead_time(self, coin: str):
        """Update when a coin started being most profitable."""
        if coin not in self._coin_profit_start:
            self._coin_profit_start[coin] = datetime.now()
    
    def reset_coin_lead_time(self, coin: str):
        """Reset lead time for a coin."""
        self._coin_profit_start.pop(coin, None)
    
    def get_coin_lead_duration(self, coin: str) -> Optional[timedelta]:
        """Get how long a coin has been leading."""
        if coin not in self._coin_profit_start:
            return None
        return datetime.now() - self._coin_profit_start[coin]
    
    def has_met_min_duration(self, coin: str, min_minutes: int) -> bool:
        """Check if coin has been leading for minimum duration."""
        duration = self.get_coin_lead_duration(coin)
        if duration is None:
            return False
        return duration >= timedelta(minutes=min_minutes)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entries": [e.to_dict() for e in self.entries[-100:]],  # Last 100 entries
            "switches": [s.to_dict() for s in self.switches[-50:]],  # Last 50 switches
            "last_switch_time": self._last_switch_time.isoformat() if self._last_switch_time else None
        }
    
    def save_to_file(self, filepath: str):
        """Save history to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> "ProfitHistory":
        """Load history from JSON file."""
        history = cls()
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                # Restore entries and switches as needed
                if "last_switch_time" in data and data["last_switch_time"]:
                    history._last_switch_time = datetime.fromisoformat(data["last_switch_time"])
        except FileNotFoundError:
            pass
        return history


# Simulated mining data for demo/testing
# In production, these would call actual APIs
_MINING_DATA_CACHE: Dict[str, MiningData] = {}
_CACHE_TIMESTAMP: Optional[datetime] = None
_CACHE_TTL_SECONDS = 60


async def fetch_mining_data(coins: List[Dict[str, Any]]) -> Dict[str, MiningData]:
    """
    Fetch real-time mining data for all configured coins.
    
    In production, this would query APIs like:
    - CoinGecko for prices
    - WhatToMine for difficulty and profitability
    - Block explorers for block rewards
    
    Args:
        coins: List of coin configurations with symbol, algorithm, etc.
        
    Returns:
        Dictionary mapping coin symbols to MiningData
    """
    global _MINING_DATA_CACHE, _CACHE_TIMESTAMP
    
    # Check cache
    now = datetime.now()
    if (_CACHE_TIMESTAMP and 
        (now - _CACHE_TIMESTAMP).seconds < _CACHE_TTL_SECONDS and
        _MINING_DATA_CACHE):
        return _MINING_DATA_CACHE
    
    result: Dict[str, MiningData] = {}
    
    for coin_config in coins:
        symbol = coin_config["symbol"]
        algorithm = coin_config.get("algorithm", "unknown")
        
        # Simulated data - replace with actual API calls
        # These would come from actual mining data APIs
        simulated_data = _get_simulated_mining_data(symbol, algorithm)
        result[symbol] = simulated_data
    
    # Update cache
    _MINING_DATA_CACHE = result
    _CACHE_TIMESTAMP = now
    
    logger.debug(f"Fetched mining data for {len(result)} coins")
    return result


def _get_simulated_mining_data(symbol: str, algorithm: str) -> MiningData:
    """Generate simulated mining data for testing/demo purposes."""
    import random
    
    # Base values that approximate real-world data
    base_data = {
        "BTC": {"difficulty": 83_000_000_000_000, "price": 65000, "reward": 3.125, "nethash": 500e18},
        "LTC": {"difficulty": 95_000_000, "price": 75, "reward": 6.25, "nethash": 600e12},
        "ETH": {"difficulty": 1, "price": 3500, "reward": 2.0, "nethash": 1e15},  # Post-merge, for reference
        "XMR": {"difficulty": 250_000_000_000, "price": 150, "reward": 0.6, "nethash": 2e9},
        "RVN": {"difficulty": 150_000, "price": 0.025, "reward": 2500, "nethash": 5e12},
        "ERGO": {"difficulty": 15_000_000_000_000, "price": 1.5, "reward": 67.5, "nethash": 20e15},
    }
    
    base = base_data.get(symbol, {
        "difficulty": 1_000_000,
        "price": 1.0,
        "reward": 10.0,
        "nethash": 1e9
    })
    
    # Add small random variation to simulate market movement
    variation = lambda x: x * (1 + random.uniform(-0.05, 0.05))
    
    return MiningData(
        coin=symbol,
        difficulty=variation(base["difficulty"]),
        price=variation(base["price"]),
        block_reward=base["reward"],
        network_hashrate=base["nethash"],
        timestamp=datetime.now()
    )


def calculate_profit_per_coin(
    mining_data: Dict[str, MiningData],
    config: ProfitConfig
) -> Dict[str, ProfitResult]:
    """
    Calculate profit per coin (revenue - costs).
    
    Args:
        mining_data: Dictionary of mining data per coin
        config: Profit configuration
        
    Returns:
        Dictionary mapping coin symbols to ProfitResult
    """
    results: Dict[str, ProfitResult] = {}
    
    for coin_config in config.coins:
        symbol = coin_config["symbol"]
        algorithm = coin_config.get("algorithm", "unknown")
        hashrate_mh = coin_config.get("hashrate_mh", 1000)  # MH/s
        
        if symbol not in mining_data:
            logger.warning(f"No mining data for {symbol}")
            continue
        
        data = mining_data[symbol]
        
        # Calculate daily revenue
        revenue = _calculate_daily_revenue(
            data, hashrate_mh, algorithm, config.pool_fee_percent
        )
        
        # Calculate daily electricity cost
        cost = _calculate_daily_electricity_cost(config.miner_power_watts, config.electricity_cost_per_kwh)
        
        # Calculate profit
        profit = revenue - cost
        
        # Calculate normalized profit per MH/s for comparison
        profit_per_mh = profit / hashrate_mh if hashrate_mh > 0 else 0
        
        results[symbol] = ProfitResult(
            coin=symbol,
            algorithm=algorithm,
            revenue_per_day=revenue,
            cost_per_day=cost,
            profit_per_day=profit,
            profit_per_mh=profit_per_mh,
            hashrate_mh=hashrate_mh,
            timestamp=datetime.now()
        )
    
    return results


def _calculate_daily_revenue(
    data: MiningData,
    hashrate_mh: float,
    algorithm: str,
    pool_fee_percent: float
) -> float:
    """
    Calculate expected daily revenue in USD.
    
    Uses the formula:
    Revenue = (Hashrate / Network Difficulty) * Block Reward * Blocks Per Day * Price
    """
    # Blocks per day for most PoW coins (average block time ~10 min = 144 blocks/day)
    # Adjust based on algorithm if needed
    blocks_per_day = 144
    
    # Convert hashrate to appropriate units based on algorithm
    # This is a simplified calculation - real implementations need algorithm-specific logic
    effective_hashrate = hashrate_mh * 1e6  # Convert MH/s to H/s
    
    # Expected blocks mined per day
    if data.difficulty > 0:
        expected_blocks = (effective_hashrate * 86400) / (data.difficulty * 2**32)
    else:
        expected_blocks = 0
    
    # Gross revenue in coins
    coins_per_day = expected_blocks * data.block_reward
    
    # Revenue in USD
    gross_revenue = coins_per_day * data.price
    
    # Apply pool fee
    net_revenue = gross_revenue * (1 - pool_fee_percent / 100)
    
    return net_revenue


def _calculate_daily_electricity_cost(power_watts: float, cost_per_kwh: float) -> float:
    """Calculate daily electricity cost in USD."""
    # kWh per day * cost per kWh
    kwh_per_day = (power_watts * 24) / 1000
    return kwh_per_day * cost_per_kwh


def compare_profits(profits: Dict[str, ProfitResult]) -> List[ProfitResult]:
    """
    Rank coins by profitability (highest first).
    
    Args:
        profits: Dictionary of profit results per coin
        
    Returns:
        List of ProfitResult sorted by profit_per_day (descending)
    """
    sorted_profits = sorted(
        profits.values(),
        key=lambda x: x.profit_per_day,
        reverse=True
    )
    return sorted_profits


def should_switch(
    current_coin: str,
    profits: Dict[str, ProfitResult],
    config: ProfitConfig,
    history: ProfitHistory
) -> Tuple[bool, str, str]:
    """
    Determine if a switch should occur based on profitability and hysteresis.
    
    Hysteresis criteria:
    1. New coin must be more profitable by at least switch_threshold_percent
    2. Must not be in cooldown period
    3. New coin must have been most profitable for min_profit_duration_minutes
    
    Args:
        current_coin: Currently mined coin symbol
        profits: Dictionary of profit results
        config: Profit configuration
        history: Profit history tracker
        
    Returns:
        Tuple of (should_switch: bool, new_coin: str, reason: str)
    """
    if current_coin not in profits:
        return True, _get_best_coin(profits), "Current coin not in profit data"
    
    # Get sorted profits
    ranked = compare_profits(profits)
    if not ranked:
        return False, current_coin, "No profit data available"
    
    best_coin = ranked[0].coin
    current_profit = profits[current_coin].profit_per_day
    best_profit = ranked[0].profit_per_day
    
    # Update lead times
    if best_coin == current_coin:
        # Current coin is best, reset all lead times
        for coin in profits:
            if coin != current_coin:
                history.reset_coin_lead_time(coin)
        history.update_coin_lead_time(current_coin)
        return False, current_coin, "Current coin is most profitable"
    else:
        # Different coin is best, update its lead time
        history.update_coin_lead_time(best_coin)
    
    # Check cooldown
    if history.is_in_cooldown(config.cooldown_minutes):
        time_left = config.cooldown_minutes - (history.get_time_since_last_switch().total_seconds() / 60)
        return False, current_coin, f"In cooldown period ({time_left:.1f} min remaining)"
    
    # Check minimum profit duration
    if not history.has_met_min_duration(best_coin, config.min_profit_duration_minutes):
        duration = history.get_coin_lead_duration(best_coin)
        duration_str = f"{duration.total_seconds()/60:.1f}" if duration else "0"
        return False, current_coin, f"{best_coin} leading for {duration_str} min (need {config.min_profit_duration_minutes})"
    
    # Check profit threshold
    if current_profit <= 0:
        profit_diff_percent = float('inf') if best_profit > 0 else 0
    else:
        profit_diff_percent = ((best_profit - current_profit) / abs(current_profit)) * 100
    
    if profit_diff_percent < config.switch_threshold_percent:
        return False, current_coin, f"Profit difference ({profit_diff_percent:.1f}%) below threshold ({config.switch_threshold_percent}%)"
    
    # All criteria met - should switch
    reason = (f"{best_coin} is {profit_diff_percent:.1f}% more profitable "
              f"(${best_profit:.2f}/day vs ${current_profit:.2f}/day)")
    
    return True, best_coin, reason


def _get_best_coin(profits: Dict[str, ProfitResult]) -> str:
    """Get the symbol of the most profitable coin."""
    if not profits:
        return ""
    return max(profits.items(), key=lambda x: x[1].profit_per_day)[0]


def execute_switch(
    from_coin: str,
    to_coin: str,
    config: ProfitConfig,
    profits: Optional[Dict[str, ProfitResult]] = None
) -> bool:
    """
    Execute the mining algorithm/coin switch.
    
    In production, this would:
    - Stop current miner process
    - Update miner configuration
    - Start new miner with different algorithm/pool
    
    Args:
        from_coin: Current coin being mined
        to_coin: Target coin to switch to
        config: Profit configuration
        profits: Optional profit data for logging
        
    Returns:
        True if switch was successful, False otherwise
    """
    if config.dry_run:
        logger.info(f"[DRY RUN] Would switch from {from_coin} to {to_coin}")
        return True
    
    try:
        # Find coin configurations
        from_config = next((c for c in config.coins if c["symbol"] == from_coin), None)
        to_config = next((c for c in config.coins if c["symbol"] == to_coin), None)
        
        if not to_config:
            logger.error(f"Configuration not found for {to_coin}")
            return False
        
        logger.info(f"Executing switch: {from_coin} -> {to_coin}")
        logger.info(f"  Algorithm: {to_config.get('algorithm', 'unknown')}")
        logger.info(f"  Pool: {to_config.get('pool_url', 'not configured')}")
        
        # In production, implement actual miner control here:
        # 1. Stop current miner process
        # 2. Save new configuration
        # 3. Start miner with new pool/algorithm
        # 4. Verify hashrate on new pool
        
        # Simulate switch delay
        time.sleep(0.5)
        
        logger.info(f"Successfully switched to {to_coin}")
        return True
        
    except Exception as e:
        logger.error(f"Switch failed: {e}")
        return False


class ProfitSwitcher:
    """
    Main class for managing profit switching operations.
    
    Provides a high-level interface for continuous monitoring and switching.
    """
    
    def __init__(self, config: ProfitConfig, history: Optional[ProfitHistory] = None):
        self.config = config
        self.history = history or ProfitHistory()
        self.current_coin: Optional[str] = None
        self._running = False
        self._check_interval_seconds = 60
    
    async def initialize(self, default_coin: Optional[str] = None):
        """Initialize the switcher with a starting coin."""
        if default_coin and default_coin in [c["symbol"] for c in self.config.coins]:
            self.current_coin = default_coin
        elif self.config.coins:
            self.current_coin = self.config.coins[0]["symbol"]
        
        logger.info(f"Profit switcher initialized. Current coin: {self.current_coin}")
    
    async def run_once(self) -> Tuple[bool, str, str]:
        """
        Run a single profit check and switch if needed.
        
        Returns:
            Tuple of (switched: bool, current_coin: str, message: str)
        """
        if not self.current_coin:
            await self.initialize()
        
        # Fetch data
        mining_data = await fetch_mining_data(self.config.coins)
        
        # Calculate profits
        profits = calculate_profit_per_coin(mining_data, self.config)
        
        # Track in history
        for result in profits.values():
            self.history.add_entry(result)
        
        # Check if we should switch
        should_switch_flag, new_coin, reason = should_switch(
            self.current_coin, profits, self.config, self.history
        )
        
        if should_switch_flag:
            # Execute switch
            success = execute_switch(
                self.current_coin, new_coin, self.config, profits
            )
            
            if success:
                # Record the switch
                old_profit = profits.get(self.current_coin, ProfitResult(
                    coin=self.current_coin, algorithm="", revenue_per_day=0,
                    cost_per_day=0, profit_per_day=0, profit_per_mh=0, hashrate_mh=0
                )).profit_per_day
                new_profit = profits.get(new_coin, ProfitResult(
                    coin=new_coin, algorithm="", revenue_per_day=0,
                    cost_per_day=0, profit_per_day=0, profit_per_mh=0, hashrate_mh=0
                )).profit_per_day
                
                self.history.add_switch(SwitchEvent(
                    from_coin=self.current_coin,
                    to_coin=new_coin,
                    reason=reason,
                    profit_before=old_profit,
                    profit_after=new_profit
                ))
                
                self.current_coin = new_coin
                return True, new_coin, f"Switched to {new_coin}: {reason}"
            else:
                return False, self.current_coin, f"Switch failed: {reason}"
        
        return False, self.current_coin, reason
    
    async def run_continuous(self):
        """Run continuous monitoring loop."""
        self._running = True
        logger.info("Starting continuous profit monitoring...")
        
        while self._running:
            try:
                switched, coin, message = await self.run_once()
                
                if switched:
                    logger.info(message)
                else:
                    logger.debug(message)
                
                await asyncio.sleep(self._check_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self._check_interval_seconds)
    
    def stop(self):
        """Stop the continuous monitoring loop."""
        self._running = False
        logger.info("Profit monitoring stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status summary."""
        return {
            "current_coin": self.current_coin,
            "running": self._running,
            "check_interval_seconds": self._check_interval_seconds,
            "total_switches": len(self.history.switches),
            "history_entries": len(self.history.entries),
            "config": {
                "coins": [c["symbol"] for c in self.config.coins],
                "dry_run": self.config.dry_run,
                "switch_threshold_percent": self.config.switch_threshold_percent,
                "cooldown_minutes": self.config.cooldown_minutes
            }
        }


# Convenience functions for simple usage

async def quick_check(config: ProfitConfig) -> List[ProfitResult]:
    """
    Quick profitability check for all configured coins.
    
    Args:
        config: Profit configuration
        
    Returns:
        List of profit results sorted by profitability
    """
    mining_data = await fetch_mining_data(config.coins)
    profits = calculate_profit_per_coin(mining_data, config)
    return compare_profits(profits)


def format_profit_report(results: List[ProfitResult]) -> str:
    """Format profit results as a readable report."""
    lines = ["\n=== Mining Profitability Report ===\n"]
    lines.append(f"{'Coin':<8} {'Algorithm':<12} {'Revenue/day':>12} {'Cost/day':>10} {'Profit/day':>12} {'$/MH':>10}")
    lines.append("-" * 70)
    
    for r in results:
        lines.append(
            f"{r.coin:<8} {r.algorithm:<12} "
            f"${r.revenue_per_day:>10.2f} ${r.cost_per_day:>8.2f} "
            f"${r.profit_per_day:>10.2f} ${r.profit_per_mh:>8.6f}"
        )
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    async def demo():
        config = ProfitConfig(
            coins=[
                {"symbol": "BTC", "algorithm": "SHA256", "hashrate_mh": 100_000_000},
                {"symbol": "LTC", "algorithm": "Scrypt", "hashrate_mh": 5_000},
                {"symbol": "RVN", "algorithm": "KawPow", "hashrate_mh": 100},
            ],
            electricity_cost_per_kwh=0.12,
            pool_fee_percent=2.0,
            miner_power_watts=3000,
            switch_threshold_percent=5.0,
            cooldown_minutes=5,
            dry_run=True
        )
        
        # Quick check
        results = await quick_check(config)
        print(format_profit_report(results))
        
        # Run switcher once
        switcher = ProfitSwitcher(config)
        await switcher.initialize("BTC")
        switched, coin, message = await switcher.run_once()
        print(f"\nSwitch check: {message}")
    
    asyncio.run(demo())
