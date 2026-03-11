"""
Mining Optimizer - Profit switching and genetic parameter tuning for cryptocurrency mining.

This module provides intelligent algorithm switching and parameter optimization
for cryptocurrency mining operations. Supports SHA-256, Scrypt, Ethash, and RandomX.
"""

import random
import math
import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Callable, Any
from datetime import datetime, timedelta
from collections import deque
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MiningConfig:
    """Configuration for mining optimizer.
    
    Attributes:
        pools: Dict mapping algorithm names to pool configurations
        switch_threshold: Minimum profit difference to trigger switch (0.05 = 5%)
        min_switch_interval: Minimum seconds between algorithm switches
        profit_history_size: Number of profit data points to retain
        difficulty_lookback: Days of historical difficulty data for prediction
        genetic_params: Genetic algorithm hyperparameters
    """
    pools: Dict[str, Dict[str, str]] = field(default_factory=dict)
    switch_threshold: float = 0.05
    min_switch_interval: int = 300  # 5 minutes
    profit_history_size: int = 1000
    difficulty_lookback: int = 14
    genetic_params: Dict[str, Any] = field(default_factory=lambda: {
        'population_size': 30,
        'mutation_rate': 0.1,
        'crossover_rate': 0.8,
        'elitism_ratio': 0.1,
        'max_generations': 100,
        'convergence_threshold': 0.01
    })


@dataclass
class AlgorithmParams:
    """Algorithm-specific mining parameters."""
    # SHA-256 / Scrypt (ASIC)
    frequency: Optional[int] = None  # MHz
    voltage: Optional[int] = None    # mV
    fan_speed: Optional[int] = None  # 0-100
    target_temp: Optional[int] = None  # °C
    
    # Ethash (GPU)
    core_clock: Optional[int] = None   # MHz offset
    memory_clock: Optional[int] = None  # MHz offset
    power_limit: Optional[int] = None   # 0-100
    
    # RandomX (CPU)
    threads: Optional[int] = None
    affinity: Optional[int] = None
    large_pages: Optional[bool] = None
    jit_compiler: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlgorithmParams':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def copy(self) -> 'AlgorithmParams':
        """Create a copy of parameters."""
        return AlgorithmParams(**self.to_dict())


@dataclass
class ProfitRecord:
    """Record of profit at a point in time."""
    timestamp: datetime
    algorithm: str
    profit_usd: float
    revenue_usd: float
    cost_usd: float
    hashrate: float
    difficulty: float
    coin_price: float


class DifficultyPredictor:
    """Predicts future difficulty based on historical data."""
    
    def __init__(self, lookback_days: int = 14):
        self.lookback_days = lookback_days
        self._history: Dict[str, deque] = {}
        self._simulation_mode = True
    
    def add_difficulty_sample(self, algorithm: str, difficulty: float, timestamp: Optional[datetime] = None):
        """Add a difficulty sample to history."""
        if algorithm not in self._history:
            self._history[algorithm] = deque(maxlen=self.lookback_days * 24)  # hourly samples
        
        self._history[algorithm].append({
            'timestamp': timestamp or datetime.now(),
            'difficulty': difficulty
        })
    
    def predict(self, algorithm: str, days_ahead: int = 7) -> float:
        """Predict difficulty using simple trend analysis or simulation."""
        if algorithm not in self._history or len(self._history[algorithm]) < 2:
            # Simulation mode: generate synthetic difficulty
            return self._simulate_difficulty(algorithm, days_ahead)
        
        history = list(self._history[algorithm])
        
        # Calculate trend using linear regression
        n = len(history)
        if n < 2:
            return history[-1]['difficulty'] if history else self._simulate_difficulty(algorithm, days_ahead)
        
        # Simple trend: average change per day
        x = list(range(n))
        y = [h['difficulty'] for h in history]
        
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        # Calculate slope
        numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        denominator = sum((xi - x_mean) ** 2 for xi in x)
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        # Project forward
        current = y[-1]
        prediction = current + slope * days_ahead * (n / self.lookback_days)
        
        return max(prediction, current * 0.5)  # Don't predict less than 50% drop
    
    def _simulate_difficulty(self, algorithm: str, days_ahead: int) -> float:
        """Generate synthetic difficulty for simulation mode."""
        base_difficulty = {
            'sha256': 80e18,      # Bitcoin network difficulty
            'scrypt': 20e12,      # Litecoin network difficulty
            'ethash': 50e15,      # Ethereum Classic difficulty
            'randomx': 300e9      # Monero difficulty
        }.get(algorithm, 1e12)
        
        # Add some trend and noise
        trend = 1 + (days_ahead * 0.02)  # 2% increase per day
        noise = random.uniform(0.95, 1.05)
        
        return base_difficulty * trend * noise


class MiningOptimizer:
    """Main optimizer class for mining operations."""
    
    # Algorithm specifications
    ALGORITHMS = {
        'sha256': {
            'coins': ['BTC', 'BCH'],
            'block_reward': 6.25,
            'block_time': 600,
            'efficiency_j_th': 0.03,  # J/TH
        },
        'scrypt': {
            'coins': ['LTC', 'DOGE'],
            'block_reward': 12.5,
            'block_time': 150,
            'efficiency_j_mh': 0.1,   # J/MH
        },
        'ethash': {
            'coins': ['ETC', 'UBQ'],
            'block_reward': 2.56,
            'block_time': 15,
            'efficiency_j_mh': 0.8,   # J/MH
        },
        'randomx': {
            'coins': ['XMR'],
            'block_reward': 0.6,
            'block_time': 120,
            'efficiency_j_h': 5000,   # J/H
        }
    }
    
    def __init__(self, config: MiningConfig, simulation_mode: bool = False):
        self.config = config
        self.simulation_mode = simulation_mode
        self.difficulty_predictor = DifficultyPredictor(config.difficulty_lookback)
        self._profit_history: deque = deque(maxlen=config.profit_history_size)
        self._current_algorithm: Optional[str] = None
        self._last_switch_time: Optional[datetime] = None
        self._simulated_prices: Dict[str, float] = {}
        
        # Initialize simulated prices
        self._init_simulated_prices()
        
        logger.info(f"MiningOptimizer initialized (simulation_mode={simulation_mode})")
    
    def _init_simulated_prices(self):
        """Initialize simulated coin prices for testing."""
        self._simulated_prices = {
            'BTC': random.uniform(40000, 70000),
            'BCH': random.uniform(200, 500),
            'LTC': random.uniform(60, 150),
            'DOGE': random.uniform(0.05, 0.20),
            'ETC': random.uniform(15, 35),
            'UBQ': random.uniform(0.50, 2.00),
            'XMR': random.uniform(120, 200)
        }
    
    def _get_coin_price(self, coin: str) -> float:
        """Get current price for a coin (simulated or from API)."""
        if self.simulation_mode:
            # Add some volatility to simulated prices
            base = self._simulated_prices.get(coin, 100)
            volatility = random.uniform(0.98, 1.02)
            return base * volatility
        
        # In real mode, would fetch from API
        # For now, return simulated
        return self._get_coin_price(coin)
    
    def _get_network_hashrate(self, algorithm: str) -> float:
        """Get current network hashrate (simulated or from API)."""
        base_rates = {
            'sha256': 500e18,   # 500 EH/s
            'scrypt': 1e15,     # 1 PH/s
            'ethash': 100e12,   # 100 TH/s
            'randomx': 2e9      # 2 GH/s
        }
        
        if self.simulation_mode:
            base = base_rates.get(algorithm, 1e12)
            noise = random.uniform(0.95, 1.05)
            return base * noise
        
        return base_rates.get(algorithm, 1e12)
    
    def _get_difficulty(self, algorithm: str) -> float:
        """Get current difficulty for algorithm."""
        # Use predictor's simulation or fetch real data
        diff = self.difficulty_predictor._simulate_difficulty(algorithm, 0)
        
        # Add to predictor history
        self.difficulty_predictor.add_difficulty_sample(algorithm, diff)
        
        return diff
    
    def calculate_profitability(
        self,
        hashrates: Dict[str, float],
        power_cost: float,
        coin_prices: Optional[Dict[str, float]] = None
    ) -> Dict[str, Dict[str, float]]:
        """Calculate profitability for each algorithm.
        
        Args:
            hashrates: Dict mapping algorithm to hashrate in H/s
            power_cost: Power cost in $/kWh
            coin_prices: Optional override for coin prices
            
        Returns:
            Dict with profit details per algorithm
        """
        results = {}
        
        for algo, hashrate in hashrates.items():
            if algo not in self.ALGORITHMS:
                logger.warning(f"Unknown algorithm: {algo}")
                continue
            
            spec = self.ALGORITHMS[algo]
            
            # Get coin price (use override or fetch)
            primary_coin = spec['coins'][0]
            price = coin_prices.get(primary_coin, self._get_coin_price(primary_coin)) if coin_prices else self._get_coin_price(primary_coin)
            
            # Get network stats
            network_hashrate = self._get_network_hashrate(algo)
            difficulty = self._get_difficulty(algo)
            
            # Calculate daily blocks
            seconds_per_day = 86400
            blocks_per_day = seconds_per_day / spec['block_time']
            
            # Calculate revenue
            # Revenue = (my_hashrate / network_hashrate) * block_reward * blocks_per_day * price
            if network_hashrate > 0:
                daily_coins = (hashrate / network_hashrate) * spec['block_reward'] * blocks_per_day
            else:
                daily_coins = 0
            
            revenue_usd = daily_coins * price
            
            # Calculate power consumption
            if algo == 'sha256':
                # TH/s to W
                power_w = (hashrate / 1e12) * spec['efficiency_j_th'] * 1e12 / 1e9
            elif algo in ['scrypt', 'ethash']:
                # MH/s or H/s to W
                power_w = (hashrate / 1e6) * spec.get('efficiency_j_mh', 1)
            elif algo == 'randomx':
                # H/s to W
                power_w = hashrate * spec['efficiency_j_h'] / 1e6
            else:
                power_w = 100  # Default
            
            power_kw = power_w / 1000
            daily_kwh = power_kw * 24
            cost_usd = daily_kwh * power_cost
            
            # Calculate profit
            profit_usd = revenue_usd - cost_usd
            
            results[algo] = {
                'profit_usd_per_day': profit_usd,
                'revenue_usd_per_day': revenue_usd,
                'cost_usd_per_day': cost_usd,
                'power_consumption_w': power_w,
                'daily_coins': daily_coins,
                'coin_price': price,
                'network_hashrate': network_hashrate,
                'difficulty': difficulty,
                'efficiency': (profit_usd / power_w * 1000) if power_w > 0 else 0  # Profit per kW
            }
            
            # Record profit history
            self._profit_history.append(ProfitRecord(
                timestamp=datetime.now(),
                algorithm=algo,
                profit_usd=profit_usd,
                revenue_usd=revenue_usd,
                cost_usd=cost_usd,
                hashrate=hashrate,
                difficulty=difficulty,
                coin_price=price
            ))
        
        return results
    
    def switch_algorithm(
        self,
        profitability: Dict[str, Dict[str, float]],
        current_algorithm: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Determine if algorithm switch should occur.
        
        Args:
            profitability: Output from calculate_profitability()
            current_algorithm: Currently active algorithm
            
        Returns:
            Tuple of (should_switch: bool, target_algorithm: str or None)
        """
        if not profitability:
            return False, current_algorithm
        
        # Find most profitable algorithm
        best_algo = max(profitability.keys(), key=lambda a: profitability[a]['profit_usd_per_day'])
        best_profit = profitability[best_algo]['profit_usd_per_day']
        
        current = current_algorithm or self._current_algorithm
        
        # If not currently mining anything, switch to best
        if current is None:
            self._current_algorithm = best_algo
            self._last_switch_time = datetime.now()
            logger.info(f"Starting mining with algorithm: {best_algo} (${best_profit:.2f}/day)")
            return True, best_algo
        
        # Check if current is in profitability results
        if current not in profitability:
            logger.warning(f"Current algorithm {current} not in profitability results")
            return False, current
        
        current_profit = profitability[current]['profit_usd_per_day']
        
        # Check minimum switch interval
        if self._last_switch_time:
            elapsed = (datetime.now() - self._last_switch_time).total_seconds()
            if elapsed < self.config.min_switch_interval:
                logger.debug(f"Switch cooldown: {elapsed:.0f}s remaining")
                return False, current
        
        # Check if profit difference exceeds threshold
        if current_profit > 0:
            profit_diff_ratio = (best_profit - current_profit) / abs(current_profit)
        else:
            profit_diff_ratio = float('inf') if best_profit > 0 else 0
        
        if profit_diff_ratio >= self.config.switch_threshold:
            logger.info(f"Switching from {current} to {best_algo}: "
                       f"${current_profit:.2f} -> ${best_profit:.2f}/day "
                       f"(+{profit_diff_ratio*100:.1f}%)")
            self._current_algorithm = best_algo
            self._last_switch_time = datetime.now()
            return True, best_algo
        
        logger.debug(f"No switch needed: {current}=${current_profit:.2f}/day, "
                    f"best={best_algo}=${best_profit:.2f}/day")
        return False, current
    
    def predict_difficulty(self, algorithm: str, days_ahead: int = 7) -> float:
        """Predict future difficulty for an algorithm.
        
        Args:
            algorithm: Target algorithm
            days_ahead: Days to predict forward
            
        Returns:
            Predicted difficulty value
        """
        return self.difficulty_predictor.predict(algorithm, days_ahead)
    
    def genetic_parameter_tuner(
        self,
        algorithm: str,
        fitness_fn: Optional[Callable[[AlgorithmParams], float]] = None,
        generations: Optional[int] = None,
        population_size: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Evolve optimal mining parameters using genetic algorithm.
        
        Args:
            algorithm: Target algorithm ('sha256', 'scrypt', 'ethash', 'randomx')
            fitness_fn: Custom fitness function (params -> fitness score)
            generations: Number of generations to run (overrides config)
            population_size: Population size (overrides config)
            
        Returns:
            Dict with optimal parameters and fitness score
        """
        # Get parameters from config or kwargs
        genetic_params = self.config.genetic_params.copy()
        genetic_params.update(kwargs)
        
        pop_size = population_size or genetic_params['population_size']
        max_gen = generations or genetic_params['max_generations']
        mutation_rate = genetic_params['mutation_rate']
        crossover_rate = genetic_params['crossover_rate']
        elitism_ratio = genetic_params['elitism_ratio']
        convergence_threshold = genetic_params['convergence_threshold']
        
        # Use default fitness function if not provided
        if fitness_fn is None:
            fitness_fn = self._default_fitness_function(algorithm)
        
        # Initialize population
        population = self._initialize_population(algorithm, pop_size)
        
        best_fitness_history = []
        
        for generation in range(max_gen):
            # Evaluate fitness
            fitness_scores = [(params, fitness_fn(params)) for params in population]
            fitness_scores.sort(key=lambda x: x[1], reverse=True)
            
            best_params, best_fitness = fitness_scores[0]
            best_fitness_history.append(best_fitness)
            
            logger.debug(f"Generation {generation + 1}/{max_gen}: Best fitness = {best_fitness:.4f}")
            
            # Check convergence
            if len(best_fitness_history) >= 10:
                recent_improvement = (best_fitness_history[-1] - best_fitness_history[-10]) / abs(best_fitness_history[-10] + 1e-10)
                if recent_improvement < convergence_threshold:
                    logger.info(f"Converged at generation {generation + 1}")
                    break
            
            # Elitism: keep top performers
            elite_count = max(1, int(pop_size * elitism_ratio))
            new_population = [params.copy() for params, _ in fitness_scores[:elite_count]]
            
            # Generate offspring
            while len(new_population) < pop_size:
                parent1 = self._select_parent(fitness_scores)
                parent2 = self._select_parent(fitness_scores)
                
                if random.random() < crossover_rate:
                    offspring = self._crossover(parent1, parent2)
                else:
                    offspring = parent1.copy()
                
                if random.random() < mutation_rate:
                    offspring = self._mutate(offspring, algorithm)
                
                new_population.append(offspring)
            
            population = new_population
        
        # Return best parameters
        final_fitness_scores = [(params, fitness_fn(params)) for params in population]
        final_fitness_scores.sort(key=lambda x: x[1], reverse=True)
        best_params, best_fitness = final_fitness_scores[0]
        
        return {
            'algorithm': algorithm,
            'optimal_params': best_params.to_dict(),
            'fitness_score': best_fitness,
            'generations': len(best_fitness_history),
            'fitness_history': best_fitness_history
        }
    
    def _initialize_population(self, algorithm: str, size: int) -> List[AlgorithmParams]:
        """Create initial random population of parameters."""
        population = []
        
        for _ in range(size):
            params = self._random_params(algorithm)
            population.append(params)
        
        return population
    
    def _random_params(self, algorithm: str) -> AlgorithmParams:
        """Generate random parameters for an algorithm."""
        params = AlgorithmParams()
        
        if algorithm in ['sha256', 'scrypt']:
            # ASIC parameters
            params.frequency = random.randint(400, 800)
            params.voltage = random.randint(1000, 1400)
            params.fan_speed = random.randint(40, 100)
            params.target_temp = random.randint(60, 85)
        
        elif algorithm == 'ethash':
            # GPU parameters
            params.core_clock = random.randint(-200, 150)
            params.memory_clock = random.randint(-500, 1500)
            params.power_limit = random.randint(50, 100)
            params.fan_speed = random.randint(40, 100)
        
        elif algorithm == 'randomx':
            # CPU parameters
            params.threads = random.randint(1, 32)
            params.large_pages = random.choice([True, False])
            params.jit_compiler = random.choice([True, False])
            params.affinity = random.randint(0, 2**16 - 1)
        
        return params
    
    def _default_fitness_function(self, algorithm: str) -> Callable[[AlgorithmParams], float]:
        """Create default fitness function for an algorithm."""
        def fitness(params: AlgorithmParams) -> float:
            # Simulate hashrate based on parameters
            base_hashrate = {
                'sha256': 100e12,  # 100 TH/s
                'scrypt': 2e9,     # 2 GH/s
                'ethash': 100e6,   # 100 MH/s
                'randomx': 10e3    # 10 KH/s
            }.get(algorithm, 1e9)
            
            # Adjust hashrate based on parameters
            hashrate = base_hashrate
            power_w = 1000
            
            if algorithm in ['sha256', 'scrypt']:
                # Higher frequency = more hashrate, more power
                freq_factor = (params.frequency or 600) / 600
                volt_factor = ((params.voltage or 1200) / 1200) ** 2
                hashrate *= freq_factor
                power_w *= volt_factor * freq_factor
                
                # Penalize high temps
                temp_penalty = max(0, (params.target_temp or 75) - 80) * 0.01
            
            elif algorithm == 'ethash':
                # Memory clock matters more for Ethash
                mem_factor = 1 + ((params.memory_clock or 0) / 1000) * 0.2
                core_factor = 1 + ((params.core_clock or 0) / 100) * 0.1
                hashrate *= mem_factor * core_factor
                power_w *= (params.power_limit or 100) / 100
            
            elif algorithm == 'randomx':
                # Thread count matters
                thread_factor = min((params.threads or 8) / 8, 4)
                hashrate *= thread_factor
                
                # Large pages bonus
                if params.large_pages:
                    hashrate *= 1.2
                
                # JIT bonus
                if params.jit_compiler:
                    hashrate *= 1.1
            
            # Calculate simulated profit
            power_cost = 0.10  # $/kWh
            daily_kwh = (power_w / 1000) * 24
            cost = daily_kwh * power_cost
            
            # Simulate revenue (simplified)
            revenue = hashrate * 1e-12  # Simplified revenue model
            
            profit = revenue - cost
            
            # Efficiency bonus
            efficiency = profit / (power_w / 1000)
            
            return profit + efficiency * 0.1
        
        return fitness
    
    def _select_parent(self, fitness_scores: List[Tuple[AlgorithmParams, float]]) -> AlgorithmParams:
        """Select parent using tournament selection."""
        tournament_size = 3
        tournament = random.sample(fitness_scores, min(tournament_size, len(fitness_scores)))
        tournament.sort(key=lambda x: x[1], reverse=True)
        return tournament[0][0].copy()
    
    def _crossover(self, parent1: AlgorithmParams, parent2: AlgorithmParams) -> AlgorithmParams:
        """Perform crossover between two parents."""
        child = AlgorithmParams()
        
        # Average numeric values, randomly select booleans
        for attr in ['frequency', 'voltage', 'fan_speed', 'target_temp',
                     'core_clock', 'memory_clock', 'power_limit', 'threads', 'affinity']:
            v1 = getattr(parent1, attr)
            v2 = getattr(parent2, attr)
            
            if v1 is not None and v2 is not None:
                if random.random() < 0.5:
                    setattr(child, attr, int((v1 + v2) / 2))
                else:
                    setattr(child, attr, random.choice([v1, v2]))
            elif v1 is not None:
                setattr(child, attr, v1)
            elif v2 is not None:
                setattr(child, attr, v2)
        
        for attr in ['large_pages', 'jit_compiler']:
            v1 = getattr(parent1, attr)
            v2 = getattr(parent2, attr)
            
            if v1 is not None and v2 is not None:
                setattr(child, attr, random.choice([v1, v2]))
            elif v1 is not None:
                setattr(child, attr, v1)
            elif v2 is not None:
                setattr(child, attr, v2)
        
        return child
    
    def _mutate(self, params: AlgorithmParams, algorithm: str) -> AlgorithmParams:
        """Mutate parameters."""
        mutated = params.copy()
        
        if algorithm in ['sha256', 'scrypt']:
            if random.random() < 0.3 and mutated.frequency:
                mutated.frequency = max(300, min(900, mutated.frequency + random.randint(-50, 50)))
            if random.random() < 0.3 and mutated.voltage:
                mutated.voltage = max(900, min(1500, mutated.voltage + random.randint(-50, 50)))
            if random.random() < 0.3 and mutated.fan_speed:
                mutated.fan_speed = max(20, min(100, mutated.fan_speed + random.randint(-10, 10)))
        
        elif algorithm == 'ethash':
            if random.random() < 0.3 and mutated.memory_clock:
                mutated.memory_clock = max(-1000, min(2000, mutated.memory_clock + random.randint(-100, 100)))
            if random.random() < 0.3 and mutated.core_clock:
                mutated.core_clock = max(-300, min(200, mutated.core_clock + random.randint(-25, 25)))
            if random.random() < 0.3 and mutated.power_limit:
                mutated.power_limit = max(40, min(100, mutated.power_limit + random.randint(-5, 5)))
        
        elif algorithm == 'randomx':
            if random.random() < 0.3 and mutated.threads:
                mutated.threads = max(1, min(64, mutated.threads + random.randint(-2, 2)))
            if random.random() < 0.3:
                mutated.large_pages = not mutated.large_pages if mutated.large_pages is not None else True
            if random.random() < 0.3:
                mutated.jit_compiler = not mutated.jit_compiler if mutated.jit_compiler is not None else True
        
        return mutated
    
    def get_profit_history(self, algorithm: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve historical profit data.
        
        Args:
            algorithm: Filter by algorithm (None for all)
            limit: Maximum records to return
            
        Returns:
            List of profit history records
        """
        records = list(self._profit_history)
        
        if algorithm:
            records = [r for r in records if r.algorithm == algorithm]
        
        records = records[-limit:]
        
        return [
            {
                'timestamp': r.timestamp.isoformat(),
                'algorithm': r.algorithm,
                'profit_usd': r.profit_usd,
                'revenue_usd': r.revenue_usd,
                'cost_usd': r.cost_usd,
                'hashrate': r.hashrate,
                'difficulty': r.difficulty,
                'coin_price': r.coin_price
            }
            for r in records
        ]
    
    def get_current_algorithm(self) -> Optional[str]:
        """Get currently active algorithm."""
        return self._current_algorithm
    
    def get_switch_stats(self) -> Dict[str, Any]:
        """Get algorithm switching statistics."""
        records = list(self._profit_history)
        
        time_since = None
        if self._last_switch_time:
            time_since = (datetime.now() - self._last_switch_time).total_seconds()
        
        if not records:
            return {
                'total_switches': 0,
                'time_since_last_switch': time_since,
                'current_algorithm': self._current_algorithm,
                'last_switch_time': self._last_switch_time.isoformat() if self._last_switch_time else None
            }
        
        # Count switches
        switches = 0
        last_algo = None
        for r in records:
            if last_algo is not None and r.algorithm != last_algo:
                switches += 1
            last_algo = r.algorithm
        
        return {
            'total_switches': switches,
            'time_since_last_switch': time_since,
            'current_algorithm': self._current_algorithm,
            'last_switch_time': self._last_switch_time.isoformat() if self._last_switch_time else None
        }


# Convenience functions for quick usage
def create_optimizer(
    pools: Optional[Dict[str, Dict[str, str]]] = None,
    switch_threshold: float = 0.05,
    simulation_mode: bool = False
) -> MiningOptimizer:
    """Create a MiningOptimizer with default configuration.
    
    Args:
        pools: Pool configurations per algorithm
        switch_threshold: Minimum profit difference to switch
        simulation_mode: Enable simulation mode
        
    Returns:
        Configured MiningOptimizer instance
    """
    config = MiningConfig(
        pools=pools or {},
        switch_threshold=switch_threshold
    )
    return MiningOptimizer(config, simulation_mode=simulation_mode)


def quick_profit_check(
    hashrates: Dict[str, float],
    power_cost: float = 0.10,
    simulation_mode: bool = True
) -> Dict[str, Dict[str, float]]:
    """Quick profitability check without full configuration.
    
    Args:
        hashrates: Dict mapping algorithm to hashrate in H/s
        power_cost: Power cost in $/kWh
        simulation_mode: Use simulation mode
        
    Returns:
        Profitability results per algorithm
    """
    optimizer = create_optimizer(simulation_mode=simulation_mode)
    return optimizer.calculate_profitability(hashrates, power_cost)


if __name__ == '__main__':
    # Demo usage
    print("=" * 60)
    print("Mining Optimizer Demo")
    print("=" * 60)
    
    # Create optimizer in simulation mode
    optimizer = create_optimizer(simulation_mode=True)
    
    # Define hashrates for different algorithms
    hashrates = {
        'sha256': 100e12,    # 100 TH/s
        'scrypt': 2e9,       # 2 GH/s
        'ethash': 100e6,     # 100 MH/s
        'randomx': 10e3      # 10 KH/s
    }
    
    # Calculate profitability
    print("\n1. Calculating Profitability:")
    print("-" * 40)
    profits = optimizer.calculate_profitability(hashrates, power_cost=0.10)
    
    for algo, data in sorted(profits.items(), key=lambda x: x[1]['profit_usd_per_day'], reverse=True):
        print(f"\n{algo.upper()}:")
        print(f"  Profit: ${data['profit_usd_per_day']:.2f}/day")
        print(f"  Revenue: ${data['revenue_usd_per_day']:.2f}/day")
        print(f"  Cost: ${data['cost_usd_per_day']:.2f}/day")
        print(f"  Efficiency: {data['efficiency']:.4f} profit/kW")
    
    # Check switching
    print("\n2. Algorithm Switching:")
    print("-" * 40)
    should_switch, target = optimizer.switch_algorithm(profits)
    print(f"Should switch: {should_switch}")
    print(f"Target algorithm: {target}")
    
    # Predict difficulty
    print("\n3. Difficulty Prediction:")
    print("-" * 40)
    for algo in ['sha256', 'ethash', 'randomx']:
        current = optimizer._get_difficulty(algo)
        predicted = optimizer.predict_difficulty(algo, days_ahead=7)
        change = (predicted - current) / current * 100
        print(f"{algo}: Current={current:.2e}, Predicted (7d)={predicted:.2e} ({change:+.1f}%)")
    
    # Genetic tuning
    print("\n4. Genetic Parameter Tuning:")
    print("-" * 40)
    result = optimizer.genetic_parameter_tuner(
        algorithm='ethash',
        generations=20,
        population_size=20
    )
    print(f"Algorithm: {result['algorithm']}")
    print(f"Generations: {result['generations']}")
    print(f"Fitness: {result['fitness_score']:.4f}")
    print("Optimal parameters:")
    for param, value in result['optimal_params'].items():
        print(f"  {param}: {value}")
    
    # Profit history
    print("\n5. Profit History:")
    print("-" * 40)
    history = optimizer.get_profit_history(limit=5)
    for record in history:
        print(f"{record['algorithm']}: ${record['profit_usd']:.2f} @ {record['timestamp']}")
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
