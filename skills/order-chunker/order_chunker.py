"""
Order Chunker - Splits large orders into randomized smaller pieces

This module provides order chunking functionality to avoid detection
and MEV extraction by breaking large trades into smaller, randomized pieces.
"""

import random
import hashlib
import secrets
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OrderChunker")


class DistributionStrategy(Enum):
    """Strategy for distributing chunk sizes"""
    RANDOM = "random"          # Random sizes between min/max
    WEIGHTED = "weighted"      # Weighted distribution (front-loaded or back-loaded)
    GEOMETRIC = "geometric"    # Geometric progression of sizes


class StealthLevel(Enum):
    """Stealth level presets for chunk configuration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PARANOID = "paranoid"


@dataclass
class ChunkConfig:
    """
    Configuration for order chunking
    
    Attributes:
        min_chunk: Minimum chunk size (in base currency units)
        max_chunk: Maximum chunk size
        strategy: How to distribute chunk sizes
        stealth_level: Preset configuration level
        weight_direction: For WEIGHTED strategy: "front" (larger first) or "back" (smaller first)
        geometric_ratio: For GEOMETRIC strategy: percentage of remaining per chunk
    """
    min_chunk: float = 100.0
    max_chunk: float = 1000.0
    strategy: DistributionStrategy = DistributionStrategy.RANDOM
    stealth_level: StealthLevel = StealthLevel.MEDIUM
    weight_direction: str = "front"  # "front" = larger chunks first, "back" = smaller first
    geometric_ratio: float = 0.3     # 30% of remaining per chunk for geometric
    
    # Stealth level presets
    _STEALTH_PRESETS = {
        StealthLevel.LOW: {
            "chunk_range": (2, 3),
            "min_chunk": 500.0,
            "max_chunk": 2000.0,
        },
        StealthLevel.MEDIUM: {
            "chunk_range": (3, 5),
            "min_chunk": 100.0,
            "max_chunk": 1000.0,
        },
        StealthLevel.HIGH: {
            "chunk_range": (5, 10),
            "min_chunk": 50.0,
            "max_chunk": 500.0,
        },
        StealthLevel.PARANOID: {
            "chunk_range": (10, 20),
            "min_chunk": 10.0,
            "max_chunk": 200.0,
        }
    }
    
    @classmethod
    def from_stealth_level(cls, level: str) -> "ChunkConfig":
        """
        Create a ChunkConfig from a stealth level string
        
        Args:
            level: One of "low", "medium", "high", "paranoid"
            
        Returns:
            ChunkConfig with preset values
        """
        stealth = StealthLevel(level.lower())
        preset = cls._STEALTH_PRESETS[stealth]
        
        return cls(
            min_chunk=preset["min_chunk"],
            max_chunk=preset["max_chunk"],
            strategy=DistributionStrategy.RANDOM,
            stealth_level=stealth
        )
    
    def get_chunk_range(self) -> Tuple[int, int]:
        """Get the min/max number of chunks for this stealth level"""
        return self._STEALTH_PRESETS[self.stealth_level]["chunk_range"]


@dataclass
class Chunk:
    """
    A single chunk of a larger order
    
    Attributes:
        chunk_id: Unique identifier for this chunk
        amount: Size of this chunk
        sequence: Execution order (0-indexed)
        symbol: Trading pair symbol
        remaining: Amount remaining after this chunk executes
        metadata: Additional chunk information
    """
    chunk_id: str
    amount: float
    sequence: int
    symbol: str
    remaining: float
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert chunk to dictionary representation"""
        return {
            "chunk_id": self.chunk_id,
            "amount": round(self.amount, 8),
            "sequence": self.sequence,
            "symbol": self.symbol,
            "remaining": round(self.remaining, 8),
            "metadata": self.metadata
        }


def generate_chunk_id(symbol: str, sequence: int, nonce: Optional[str] = None) -> str:
    """
    Generate a unique chunk identifier
    
    Args:
        symbol: Trading pair symbol
        sequence: Chunk sequence number
        nonce: Optional nonce for additional randomness
        
    Returns:
        Unique chunk ID (first 16 chars of SHA-256 hash)
    """
    timestamp = str(time.time())
    nonce = nonce or secrets.token_hex(8)
    data = f"{symbol}:{sequence}:{timestamp}:{nonce}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def calculate_chunk_sizes(
    total_amount: float,
    num_chunks: int,
    config: ChunkConfig
) -> List[float]:
    """
    Calculate chunk sizes based on the configured strategy
    
    Args:
        total_amount: Total order amount to split
        num_chunks: Target number of chunks
        config: ChunkConfig with strategy settings
        
    Returns:
        List of chunk sizes that sum to total_amount
    """
    if total_amount <= 0:
        raise ValueError("total_amount must be positive")
    if num_chunks < 1:
        raise ValueError("num_chunks must be at least 1")
    
    sizes = []
    remaining = total_amount
    
    if config.strategy == DistributionStrategy.RANDOM:
        # Random sizes between min_chunk and max_chunk
        for i in range(num_chunks):
            if i == num_chunks - 1:
                # Last chunk gets remainder
                chunk_size = remaining
            else:
                # Random size within bounds
                max_for_this = min(remaining, config.max_chunk)
                min_for_this = min(config.min_chunk, max_for_this)
                
                if min_for_this >= max_for_this:
                    chunk_size = remaining
                else:
                    chunk_size = random.uniform(min_for_this, max_for_this)
            
            sizes.append(chunk_size)
            remaining -= chunk_size
            remaining = max(0, remaining)
    
    elif config.strategy == DistributionStrategy.WEIGHTED:
        # Weighted distribution - chunks get progressively smaller or larger
        base_size = total_amount / num_chunks
        
        for i in range(num_chunks):
            if i == num_chunks - 1:
                chunk_size = remaining
            else:
                # Calculate weight based on position
                if config.weight_direction == "front":
                    # Larger chunks first
                    weight = 1.5 - (i / num_chunks)
                else:
                    # Smaller chunks first
                    weight = 0.5 + (i / num_chunks)
                
                chunk_size = base_size * weight
                
                # Clamp to min/max bounds
                chunk_size = max(config.min_chunk, min(chunk_size, config.max_chunk))
                chunk_size = min(chunk_size, remaining)
            
            sizes.append(chunk_size)
            remaining -= chunk_size
            remaining = max(0, remaining)
    
    elif config.strategy == DistributionStrategy.GEOMETRIC:
        # Geometric progression - each chunk is a percentage of remaining
        for i in range(num_chunks):
            if i == num_chunks - 1:
                chunk_size = remaining
            else:
                chunk_size = remaining * config.geometric_ratio
                
                # Apply min/max bounds
                chunk_size = max(config.min_chunk, min(chunk_size, config.max_chunk))
                chunk_size = min(chunk_size, remaining)
            
            sizes.append(chunk_size)
            remaining -= chunk_size
            remaining = max(0, remaining)
    
    # Normalize to ensure exact total
    if sizes and abs(sum(sizes) - total_amount) > 0.01:
        # Adjust last chunk to account for rounding
        sizes[-1] += (total_amount - sum(sizes))
    
    # Round all sizes
    sizes = [round(s, 8) for s in sizes]
    
    return sizes


def chunk_order(
    total_amount: float,
    symbol: str,
    config: Optional[ChunkConfig] = None,
    target_chunks: Optional[int] = None
) -> List[Chunk]:
    """
    Split a large order into randomized chunks
    
    Args:
        total_amount: Total amount to split (in base currency units)
        symbol: Trading pair symbol (e.g., "BTC-USD")
        config: ChunkConfig with chunking parameters (uses default if None)
        target_chunks: Override the number of chunks (uses stealth level default if None)
        
    Returns:
        List of Chunk objects representing the split order
        
    Example:
        >>> config = ChunkConfig.from_stealth_level("medium")
        >>> chunks = chunk_order(10000, "BTC-USD", config)
        >>> for c in chunks:
        ...     print(f"Chunk {c.sequence}: ${c.amount}")
    """
    config = config or ChunkConfig()
    
    # Determine number of chunks
    if target_chunks is None:
        min_chunks, max_chunks = config.get_chunk_range()
        num_chunks = random.randint(min_chunks, max_chunks)
    else:
        num_chunks = target_chunks
    
    # Calculate chunk sizes
    sizes = calculate_chunk_sizes(total_amount, num_chunks, config)
    
    # Create chunk objects
    chunks = []
    remaining = total_amount
    
    for sequence, size in enumerate(sizes):
        remaining -= size
        remaining = round(remaining, 8)
        
        chunk = Chunk(
            chunk_id=generate_chunk_id(symbol, sequence),
            amount=size,
            sequence=sequence,
            symbol=symbol,
            remaining=max(0, remaining),
            metadata={
                "total_chunks": num_chunks,
                "strategy": config.strategy.value,
                "stealth_level": config.stealth_level.value
            }
        )
        chunks.append(chunk)
    
    logger.info(
        f"Chunked {symbol} order: ${total_amount} into {len(chunks)} pieces "
        f"(strategy={config.strategy.value}, level={config.stealth_level.value})"
    )
    
    return chunks


def get_chunk_summary(chunks: List[Chunk]) -> Dict:
    """
    Get a summary of chunked order
    
    Args:
        chunks: List of chunks from chunk_order()
        
    Returns:
        Dictionary with summary statistics
    """
    if not chunks:
        return {"error": "No chunks provided"}
    
    amounts = [c.amount for c in chunks]
    total = sum(amounts)
    
    return {
        "total_amount": round(total, 8),
        "num_chunks": len(chunks),
        "average_chunk": round(total / len(chunks), 8),
        "min_chunk": round(min(amounts), 8),
        "max_chunk": round(max(amounts), 8),
        "symbol": chunks[0].symbol,
        "strategy": chunks[0].metadata.get("strategy", "unknown"),
        "stealth_level": chunks[0].metadata.get("stealth_level", "unknown")
    }


# For standalone testing
if __name__ == "__main__":
    # Test different strategies
    print("=== Order Chunker Tests ===\n")
    
    test_amount = 10000
    symbol = "BTC-USD"
    
    for level in ["low", "medium", "high", "paranoid"]:
        config = ChunkConfig.from_stealth_level(level)
        chunks = chunk_order(test_amount, symbol, config)
        summary = get_chunk_summary(chunks)
        
        print(f"\n{level.upper()} Level:")
        print(f"  Chunks: {summary['num_chunks']}")
        print(f"  Average: ${summary['average_chunk']}")
        print(f"  Range: ${summary['min_chunk']} - ${summary['max_chunk']}")
        print(f"  Chunk amounts: {[round(c.amount, 2) for c in chunks]}")
    
    # Test different strategies
    print("\n\n=== Strategy Comparison ===")
    for strategy in DistributionStrategy:
        config = ChunkConfig(
            min_chunk=100,
            max_chunk=1000,
            strategy=strategy,
            stealth_level=StealthLevel.MEDIUM
        )
        chunks = chunk_order(5000, "ETH-USD", config, target_chunks=5)
        amounts = [round(c.amount, 2) for c in chunks]
        print(f"\n{strategy.value}: {amounts}")
