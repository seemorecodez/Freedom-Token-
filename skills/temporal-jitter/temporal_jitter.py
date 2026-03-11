"""
Temporal Jitter - Random Delay Generation for Stealth Trading

Adds unpredictable delays between trade executions to mask patterns
and prevent detection by market surveillance systems.
"""

import random
import math
import time
import logging
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TemporalJitter")


class DistributionType(Enum):
    """Statistical distribution types for delay generation"""
    UNIFORM = "uniform"       # Equal probability across range
    EXPONENTIAL = "exponential"  # Skewed toward shorter delays
    GAUSSIAN = "gaussian"     # Bell curve (normal distribution)


class StealthLevel(Enum):
    """Pre-configured stealth levels with delay ranges"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PARANOID = "paranoid"


# Pre-configured delay ranges for each stealth level
STEALTH_DELAYS = {
    StealthLevel.LOW: (10.0, 30.0),
    StealthLevel.MEDIUM: (30.0, 120.0),
    StealthLevel.HIGH: (30.0, 300.0),
    StealthLevel.PARANOID: (1.0, 600.0)
}


@dataclass
class JitterConfig:
    """
    Configuration for temporal jitter behavior
    
    Attributes:
        min_delay: Minimum delay in seconds
        max_delay: Maximum delay in seconds
        distribution: Statistical distribution type
        stealth_level: Optional preset to auto-configure delays
    """
    min_delay: float = 1.0
    max_delay: float = 60.0
    distribution: DistributionType = DistributionType.UNIFORM
    stealth_level: Optional[StealthLevel] = None
    
    def __post_init__(self):
        """Apply stealth level presets if specified"""
        if self.stealth_level is not None:
            self.min_delay, self.max_delay = STEALTH_DELAYS[self.stealth_level]
            logger.debug(f"Applied {self.stealth_level.value} stealth: "
                        f"{self.min_delay}s - {self.max_delay}s")


def apply_jitter(config: JitterConfig) -> float:
    """
    Generate a single random delay based on configuration
    
    Args:
        config: JitterConfig specifying delay range and distribution
        
    Returns:
        Random delay in seconds (float)
        
    Raises:
        ValueError: If min_delay > max_delay or invalid distribution
        
    Example:
        >>> config = JitterConfig(min_delay=5.0, max_delay=15.0)
        >>> delay = apply_jitter(config)
        >>> print(f"Delaying for {delay:.2f} seconds")
    """
    if config.min_delay > config.max_delay:
        raise ValueError(f"min_delay ({config.min_delay}) must be <= max_delay ({config.max_delay})")
    
    min_d = config.min_delay
    max_d = config.max_delay
    mean = (min_d + max_d) / 2
    
    if config.distribution == DistributionType.UNIFORM:
        # Equal probability across the range
        delay = random.uniform(min_d, max_d)
        
    elif config.distribution == DistributionType.EXPONENTIAL:
        # Skewed toward shorter delays
        # Lambda = 1/mean for exponential distribution
        # We shift by min_d and scale to fit range
        mean_offset = mean - min_d
        if mean_offset <= 0:
            delay = min_d
        else:
            # Generate exponential and clamp to max
            delay = min_d + random.expovariate(1.0 / mean_offset)
            delay = min(delay, max_d)
            
    elif config.distribution == DistributionType.GAUSSIAN:
        # Bell curve centered on mean
        # Standard deviation = (max - min) / 6 (99.7% within 3 sigma)
        std_dev = (max_d - min_d) / 6.0
        
        # Sample until we get a value within bounds
        attempts = 0
        max_attempts = 100
        while attempts < max_attempts:
            delay = random.gauss(mean, std_dev)
            if min_d <= delay <= max_d:
                break
            attempts += 1
        else:
            # Fallback to uniform if sampling fails
            delay = random.uniform(min_d, max_d)
            
    else:
        raise ValueError(f"Unknown distribution: {config.distribution}")
    
    logger.debug(f"Generated {config.distribution.value} delay: {delay:.2f}s "
                f"(range: {min_d}s - {max_d}s)")
    
    return delay


def apply_jitter_sequence(
    num_delays: int,
    config: JitterConfig,
    first_immediate: bool = True
) -> List[float]:
    """
    Generate a sequence of random delays
    
    Args:
        num_delays: Number of delays to generate
        config: JitterConfig specifying delay range and distribution
        first_immediate: If True, first delay is 0 (no wait before first action)
        
    Returns:
        List of delays in seconds
        
    Raises:
        ValueError: If num_delays < 0
        
    Example:
        >>> config = JitterConfig(stealth_level=StealthLevel.MEDIUM)
        >>> delays = apply_jitter_sequence(5, config)
        >>> # Use delays between trade chunks
        >>> for i, delay in enumerate(delays):
        ...     time.sleep(delay)
        ...     execute_chunk(chunks[i])
    """
    if num_delays < 0:
        raise ValueError(f"num_delays must be non-negative, got {num_delays}")
    
    if num_delays == 0:
        return []
    
    delays = []
    
    for i in range(num_delays):
        if first_immediate and i == 0:
            # First operation executes immediately
            delay = 0.0
        else:
            delay = apply_jitter(config)
        delays.append(delay)
    
    total_delay = sum(delays)
    logger.info(f"Generated {num_delays} delays ({config.distribution.value}), "
                f"total: {total_delay:.1f}s")
    
    return delays


def sleep_with_jitter(config: JitterConfig) -> float:
    """
    Generate and immediately apply a random delay
    
    Args:
        config: JitterConfig specifying delay range and distribution
        
    Returns:
        The actual delay applied in seconds
        
    Example:
        >>> config = JitterConfig(stealth_level=StealthLevel.HIGH)
        >>> # Execute first chunk
        >>> result = execute_chunk(chunk1)
        >>> # Delay before next chunk
        >>> sleep_with_jitter(config)
        >>> result = execute_chunk(chunk2)
    """
    delay = apply_jitter(config)
    logger.info(f"Sleeping for {delay:.2f}s (jitter)")
    time.sleep(delay)
    return delay


def calculate_total_time(
    num_operations: int,
    config: JitterConfig,
    first_immediate: bool = True
) -> dict:
    """
    Calculate expected timing statistics for a sequence
    
    Args:
        num_operations: Number of operations in sequence
        config: JitterConfig for delay generation
        first_immediate: Whether first operation has no delay
        
    Returns:
        Dictionary with timing statistics
        
    Example:
        >>> config = JitterConfig(min_delay=10, max_delay=60)
        >>> stats = calculate_total_time(5, config)
        >>> print(f"Expected duration: {stats['expected_seconds']:.0f}s")
    """
    min_d = config.min_delay
    max_d = config.max_delay
    mean = (min_d + max_d) / 2
    
    if first_immediate:
        num_delays = num_operations - 1
    else:
        num_delays = num_operations
    
    num_delays = max(0, num_delays)
    
    return {
        "num_operations": num_operations,
        "num_delays": num_delays,
        "min_seconds": num_delays * min_d,
        "max_seconds": num_delays * max_d,
        "expected_seconds": num_delays * mean,
        "distribution": config.distribution.value,
        "stealth_level": config.stealth_level.value if config.stealth_level else None
    }


# Convenience functions for quick usage

def quick_jitter(seconds_range: tuple, distribution: str = "uniform") -> float:
    """
    Quick jitter with minimal configuration
    
    Args:
        seconds_range: (min, max) tuple
        distribution: "uniform", "exponential", or "gaussian"
        
    Returns:
        Random delay in seconds
        
    Example:
        >>> delay = quick_jitter((10, 30), "gaussian")
        >>> time.sleep(delay)
    """
    dist_map = {
        "uniform": DistributionType.UNIFORM,
        "exponential": DistributionType.EXPONENTIAL,
        "gaussian": DistributionType.GAUSSIAN
    }
    
    config = JitterConfig(
        min_delay=seconds_range[0],
        max_delay=seconds_range[1],
        distribution=dist_map.get(distribution, DistributionType.UNIFORM)
    )
    return apply_jitter(config)


def stealth_jitter(level: str) -> float:
    """
    Quick jitter using stealth level presets
    
    Args:
        level: "low", "medium", "high", or "paranoid"
        
    Returns:
        Random delay in seconds
        
    Example:
        >>> delay = stealth_jitter("high")
        >>> time.sleep(delay)
    """
    level_map = {
        "low": StealthLevel.LOW,
        "medium": StealthLevel.MEDIUM,
        "high": StealthLevel.HIGH,
        "paranoid": StealthLevel.PARANOID
    }
    
    stealth = level_map.get(level.lower(), StealthLevel.MEDIUM)
    config = JitterConfig(stealth_level=stealth)
    return apply_jitter(config)


# Example usage
if __name__ == "__main__":
    print("=== Temporal Jitter Demo ===\n")
    
    # Demo 1: Basic uniform jitter
    print("1. Uniform distribution (1-5s):")
    config = JitterConfig(min_delay=1.0, max_delay=5.0, distribution=DistributionType.UNIFORM)
    for i in range(5):
        delay = apply_jitter(config)
        print(f"   Delay {i+1}: {delay:.2f}s")
    
    # Demo 2: Stealth level preset
    print("\n2. HIGH stealth level (30-300s):")
    config = JitterConfig(stealth_level=StealthLevel.HIGH)
    delays = apply_jitter_sequence(5, config, first_immediate=True)
    for i, d in enumerate(delays):
        print(f"   Chunk {i+1} delay: {d:.1f}s")
    
    # Demo 3: Different distributions
    print("\n3. Distribution comparison (10-60s):")
    for dist in DistributionType:
        config = JitterConfig(min_delay=10.0, max_delay=60.0, distribution=dist)
        delays = apply_jitter_sequence(10, config, first_immediate=False)
        avg = sum(delays) / len(delays)
        print(f"   {dist.value:12s}: avg={avg:.1f}s, min={min(delays):.1f}s, max={max(delays):.1f}s")
    
    # Demo 4: Expected timing stats
    print("\n4. Timing statistics for 10 chunks (MEDIUM stealth):")
    config = JitterConfig(stealth_level=StealthLevel.MEDIUM)
    stats = calculate_total_time(10, config, first_immediate=True)
    print(f"   Expected duration: {stats['expected_seconds']:.0f}s")
    print(f"   Min/Max range: {stats['min_seconds']:.0f}s - {stats['max_seconds']:.0f}s")
