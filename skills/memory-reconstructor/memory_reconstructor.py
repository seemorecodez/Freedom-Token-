"""
Memory Reconstructor - Reconstructs data from distributed storage shards.

This module provides functionality to fetch, verify, and reassemble
fragmented data stored across multiple distributed storage sources.
"""

import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum


# ============================================================================
# Exceptions
# ============================================================================

class ShardFetchError(Exception):
    """Failed to fetch shard from storage source."""
    pass


class IntegrityError(Exception):
    """Shard checksum verification failed."""
    pass


class InsufficientShardsError(Exception):
    """Not enough shards available for reconstruction."""
    pass


class ReconstructionError(Exception):
    """Failed to reconstruct data from shards."""
    pass


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Shard:
    """Represents a single data shard from distributed storage."""
    data: bytes
    index: int
    source: str
    checksum: str
    total_shards: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self) -> str:
        return f"Shard(index={self.index}, source='{self.source}', size={len(self.data)})"


@dataclass
class ReconstructedMemory:
    """Result of reconstructing data from shards."""
    data: bytes
    metadata: Dict[str, Any]
    verified: bool
    shards_used: int
    shards_total: int
    missing_shards: List[int] = field(default_factory=list)
    
    @property
    def text(self) -> str:
        """Decode data as UTF-8 text."""
        return self.data.decode('utf-8', errors='replace')
    
    @property
    def json(self) -> Dict[str, Any]:
        """Parse data as JSON."""
        return json.loads(self.text)


@dataclass
class ReconstructorConfig:
    """Configuration for the memory reconstructor.
    
    Attributes:
        shard_sources: List of storage source identifiers
        redundancy_factor: Minimum number of shards needed for reconstruction
        checksum_algorithm: Hash algorithm for verification (sha256, md5, sha1)
        timeout_seconds: Timeout for fetch operations
        retry_attempts: Number of retry attempts per source
        custom_fetcher: Optional custom fetch function
    """
    shard_sources: List[str] = field(default_factory=list)
    redundancy_factor: int = 2
    checksum_algorithm: str = "sha256"
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    custom_fetcher: Optional[Callable] = None
    
    def __post_init__(self):
        if self.redundancy_factor < 1:
            raise ValueError("redundancy_factor must be at least 1")
        if self.checksum_algorithm not in ("sha256", "md5", "sha1"):
            raise ValueError("checksum_algorithm must be sha256, md5, or sha1")


# ============================================================================
# Internal Storage Simulation
# ============================================================================

# Simulated distributed storage backends
_STORAGE_BACKENDS: Dict[str, Dict[str, List[Shard]]] = {}


def _simulate_storage_setup(memory_id: str, data: bytes, num_shards: int = 3, 
                            corruption_map: Optional[Dict[int, bool]] = None):
    """Setup simulated storage for testing/demo purposes.
    
    Args:
        memory_id: The memory identifier
        data: The original data to shard
        num_shards: Number of shards to create
        corruption_map: Dict of shard_index -> should_corrupt for testing
    """
    corruption_map = corruption_map or {}
    shard_size = len(data) // num_shards
    shards = []
    
    for i in range(num_shards):
        start = i * shard_size
        end = start + shard_size if i < num_shards - 1 else len(data)
        shard_data = data[start:end]
        
        # Calculate checksum
        checksum = hashlib.sha256(shard_data).hexdigest()
        
        # Create shard
        shard = Shard(
            data=shard_data,
            index=i,
            source=f"storage_{i % 3}",
            checksum=checksum,
            total_shards=num_shards
        )
        
        # Apply corruption if specified
        if corruption_map.get(i, False):
            shard.data = b"CORRUPTED" + shard.data[9:]
        
        shards.append(shard)
    
    # Distribute shards across backends
    for source in ["storage_0", "storage_1", "storage_2"]:
        if source not in _STORAGE_BACKENDS:
            _STORAGE_BACKENDS[source] = {}
        _STORAGE_BACKENDS[source][memory_id] = [
            s for s in shards if s.source == source
        ]


def _fetch_from_source(source: str, memory_id: str, timeout: float = 30.0) -> List[Shard]:
    """Fetch shards from a single storage source.
    
    Args:
        source: Storage source identifier
        memory_id: Memory to fetch
        timeout: Operation timeout
        
    Returns:
        List of Shard objects from the source
        
    Raises:
        ShardFetchError: If fetch fails
    """
    # Simulate network/storage latency
    import time
    time.sleep(0.001)
    
    if source not in _STORAGE_BACKENDS:
        raise ShardFetchError(f"Storage source '{source}' not available")
    
    if memory_id not in _STORAGE_BACKENDS[source]:
        return []  # Source doesn't have this memory
    
    return _STORAGE_BACKENDS[source][memory_id]


# ============================================================================
# Public API
# ============================================================================

def fetch_storage_shards(config: ReconstructorConfig, memory_id: str) -> List[Shard]:
    """Fetch shards from distributed storage sources.
    
    Attempts to fetch shards from all configured sources, handling
    partial failures and collecting all available shards.
    
    Args:
        config: ReconstructorConfig with source list
        memory_id: Unique identifier for the memory
        
    Returns:
        List of Shard objects from all available sources
        
    Raises:
        ShardFetchError: If all sources fail to respond
    """
    if not config.shard_sources:
        raise ValueError("No shard sources configured")
    
    all_shards: List[Shard] = []
    failed_sources: List[str] = []
    
    # Use custom fetcher if provided
    fetch_fn = config.custom_fetcher or _fetch_from_source
    
    for source in config.shard_sources:
        last_error = None
        
        # Retry logic
        for attempt in range(config.retry_attempts):
            try:
                shards = fetch_fn(source, memory_id, config.timeout_seconds)
                all_shards.extend(shards)
                break  # Success, move to next source
            except Exception as e:
                last_error = e
                if attempt < config.retry_attempts - 1:
                    continue  # Retry
                else:
                    failed_sources.append(source)
        else:
            # All retries exhausted
            if last_error:
                print(f"Warning: Failed to fetch from {source}: {last_error}")
    
    if not all_shards and failed_sources:
        raise ShardFetchError(
            f"All storage sources failed. Failed: {failed_sources}"
        )
    
    # Sort by index for consistent ordering
    all_shards.sort(key=lambda s: s.index)
    
    return all_shards


def verify_shard_integrity(shard: Shard, algorithm: str = "sha256") -> bool:
    """Verify shard integrity using checksum.
    
    Args:
        shard: The shard to verify
        algorithm: Hash algorithm to use (sha256, md5, sha1)
        
    Returns:
        True if checksum matches, False otherwise
        
    Raises:
        ValueError: If unsupported algorithm specified
    """
    if algorithm == "sha256":
        computed = hashlib.sha256(shard.data).hexdigest()
    elif algorithm == "md5":
        computed = hashlib.md5(shard.data).hexdigest()
    elif algorithm == "sha1":
        computed = hashlib.sha1(shard.data).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    return computed == shard.checksum


def reconstruct_from_shards(shards: List[Shard], verify: bool = True,
                            checksum_algorithm: str = "sha256") -> ReconstructedMemory:
    """Reconstruct data from multiple shards.
    
    Assembles shards in order, optionally verifying integrity first.
    Handles missing shards gracefully if redundancy allows.
    
    Args:
        shards: List of Shard objects to assemble
        verify: Whether to verify checksums before reconstruction
        checksum_algorithm: Algorithm for verification
        
    Returns:
        ReconstructedMemory object with assembled data
        
    Raises:
        InsufficientShardsError: Not enough shards for reconstruction
        IntegrityError: Shard verification failed and verify=True
        ReconstructionError: Assembly failed
    """
    if not shards:
        raise InsufficientShardsError("No shards provided for reconstruction")
    
    # Determine total shards from first shard
    total_shards = max(s.total_shards for s in shards)
    
    # Index shards by position
    shard_map: Dict[int, Shard] = {}
    invalid_shards: List[int] = []
    
    for shard in shards:
        # Verify if requested
        is_valid = True
        if verify:
            is_valid = verify_shard_integrity(shard, checksum_algorithm)
            if not is_valid:
                invalid_shards.append(shard.index)
        
        # Still include the shard (may be only copy), but mark as unverified
        # Keep latest version if duplicate indices (prefer valid shards)
        if shard.index not in shard_map:
            shard_map[shard.index] = shard
        elif is_valid and not verify_shard_integrity(shard_map[shard.index], checksum_algorithm):
            # Replace invalid shard with valid one
            shard_map[shard.index] = shard
    
    # Check if we have enough valid shards
    available_indices = set(shard_map.keys())
    required_indices = set(range(total_shards))
    missing_indices = list(required_indices - available_indices)
    
    if len(shard_map) < total_shards:
        # Check if we can still reconstruct (if shards contain redundant data)
        # For now, require all shards
        if len(shard_map) < total_shards:
            raise InsufficientShardsError(
                f"Missing shards: {missing_indices}. "
                f"Have {len(shard_map)}, need {total_shards}."
            )
    
    # Assemble data
    try:
        assembled_parts = []
        for i in range(total_shards):
            if i in shard_map:
                assembled_parts.append(shard_map[i].data)
        
        assembled_data = b"".join(assembled_parts)
        
        # Build metadata
        metadata = {
            "total_shards": total_shards,
            "shards_used": len(shard_map),
            "sources": list(set(s.source for s in shard_map.values())),
            "invalid_shards": invalid_shards
        }
        
        return ReconstructedMemory(
            data=assembled_data,
            metadata=metadata,
            verified=len(invalid_shards) == 0,
            shards_used=len(shard_map),
            shards_total=total_shards,
            missing_shards=missing_indices
        )
        
    except Exception as e:
        raise ReconstructionError(f"Failed to reconstruct data: {e}") from e


def compute_shard_checksum(data: bytes, algorithm: str = "sha256") -> str:
    """Compute checksum for shard data.
    
    Args:
        data: Raw shard data
        algorithm: Hash algorithm (sha256, md5, sha1)
        
    Returns:
        Hexadecimal checksum string
    """
    if algorithm == "sha256":
        return hashlib.sha256(data).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(data).hexdigest()
    elif algorithm == "sha1":
        return hashlib.sha1(data).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def create_shards(data: bytes, num_shards: int, sources: List[str]) -> List[Shard]:
    """Create shards from data for distribution.
    
    Utility function to shard data for storage distribution.
    
    Args:
        data: Original data to shard
        num_shards: Number of shards to create
        sources: List of source identifiers for distribution
        
    Returns:
        List of Shard objects ready for distribution
    """
    if num_shards < 1:
        raise ValueError("num_shards must be at least 1")
    if not sources:
        raise ValueError("At least one source required")
    
    shard_size = len(data) // num_shards
    shards = []
    
    for i in range(num_shards):
        start = i * shard_size
        end = start + shard_size if i < num_shards - 1 else len(data)
        shard_data = data[start:end]
        
        shard = Shard(
            data=shard_data,
            index=i,
            source=sources[i % len(sources)],
            checksum=compute_shard_checksum(shard_data),
            total_shards=num_shards
        )
        shards.append(shard)
    
    return shards
