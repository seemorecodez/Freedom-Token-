"""
Fork Detection System for Blockchain Networks

Monitors multiple blockchain sources to detect chain divergences (forks)
and determine consensus on the main chain.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Tuple, Set
from collections import defaultdict
from enum import Enum
import hashlib
import json


class ForkSeverity(Enum):
    """Severity levels for fork events."""
    WARNING = "warning"      # Minor divergence, may resolve quickly
    CRITICAL = "critical"    # Significant fork requiring attention
    RESOLVED = "resolved"    # Fork has been resolved, chain converged


@dataclass
class ForkEvent:
    """
    Represents a detected fork event.
    
    Attributes:
        height: Block height where fork occurred
        parent_hash: Hash of the common parent block
        branches: List of divergent block hashes
        sources_by_branch: Mapping of branch hash to list of sources
        timestamp: Unix timestamp when fork was detected
        duration: Duration in seconds (updated when resolved)
        severity: Severity level of the fork
    """
    height: int
    parent_hash: str
    branches: List[str]
    sources_by_branch: Dict[str, List[str]] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration: Optional[float] = None
    severity: ForkSeverity = ForkSeverity.WARNING
    
    @property
    def affected_sources(self) -> List[str]:
        """Returns all sources affected by this fork."""
        sources = []
        for src_list in self.sources_by_branch.values():
            sources.extend(src_list)
        return sources
    
    @property
    def main_branch(self) -> Optional[str]:
        """Returns the branch with most source consensus."""
        if not self.sources_by_branch:
            return None
        return max(self.sources_by_branch.keys(), 
                   key=lambda k: len(self.sources_by_branch[k]))
    
    @property
    def minority_branches(self) -> List[str]:
        """Returns branches with minority consensus."""
        main = self.main_branch
        return [b for b in self.branches if b != main]


@dataclass
class ForkConfig:
    """
    Configuration for fork detection system.
    
    Attributes:
        sources: List of blockchain node endpoints to monitor
        check_interval: Seconds between chain checks
        confirmation_blocks: Blocks needed to confirm a fork
        alert_callback: Function called when fork is detected/resolved
        history_size: Maximum blocks to keep in memory per source
        consensus_threshold: Percentage of sources needed for consensus (0-1)
        max_fork_age: Maximum age in seconds to track unresolved forks
    """
    sources: List[str] = field(default_factory=list)
    check_interval: float = 10.0
    confirmation_blocks: int = 6
    alert_callback: Optional[Callable[[ForkEvent, str], None]] = None
    history_size: int = 1000
    consensus_threshold: float = 0.67
    max_fork_age: float = 3600.0  # 1 hour
    
    def __post_init__(self):
        if not self.sources:
            raise ValueError("At least one source must be specified")
        if not 0 < self.consensus_threshold <= 1:
            raise ValueError("consensus_threshold must be between 0 and 1")


class BlockHistory:
    """Manages block history for a single source."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.blocks: Dict[int, str] = {}  # height -> hash
        self.heights: List[int] = []  # ordered list of heights
    
    def add_block(self, height: int, block_hash: str) -> bool:
        """
        Adds a block to history. Returns True if new block added.
        """
        if height in self.blocks:
            # Check for reorg at this height
            if self.blocks[height] != block_hash:
                self.blocks[height] = block_hash
                return True  # Hash changed, potential fork
            return False  # Same hash, no change
        
        self.blocks[height] = block_hash
        self.heights.append(height)
        
        # Prune old blocks
        if len(self.heights) > self.max_size:
            oldest = self.heights.pop(0)
            del self.blocks[oldest]
        
        return True
    
    def get_hash(self, height: int) -> Optional[str]:
        """Returns block hash at given height."""
        return self.blocks.get(height)
    
    def get_range(self, start: int, end: int) -> List[Tuple[int, str]]:
        """Returns blocks in height range [start, end]."""
        return [(h, self.blocks[h]) for h in self.heights 
                if start <= h <= end and h in self.blocks]
    
    def get_latest(self) -> Optional[Tuple[int, str]]:
        """Returns the latest (height, hash) pair."""
        if not self.heights:
            return None
        height = max(self.heights)
        return (height, self.blocks.get(height))


class ForkDetector:
    """Main class for detecting and tracking blockchain forks."""
    
    def __init__(self, config: ForkConfig):
        self.config = config
        self.histories: Dict[str, BlockHistory] = {
            source: BlockHistory(config.history_size) 
            for source in config.sources
        }
        self.active_forks: Dict[int, ForkEvent] = {}  # height -> ForkEvent
        self.resolved_forks: List[ForkEvent] = []
        self._running = False
        self._lock = asyncio.Lock()
    
    async def add_block(self, source: str, height: int, block_hash: str) -> Optional[ForkEvent]:
        """
        Adds a block from a source and checks for forks.
        Returns ForkEvent if a fork is detected.
        """
        if source not in self.histories:
            raise ValueError(f"Unknown source: {source}")
        
        async with self._lock:
            history = self.histories[source]
            changed = history.add_block(height, block_hash)
            
            # Check for fork at this height (even if block wasn't new)
            # This handles cases where we're adding the divergent block
            return await self._check_height(height)
        
        return None
    
    async def _check_height(self, height: int) -> Optional[ForkEvent]:
        """Checks for fork at specific height across all sources."""
        hashes_at_height: Dict[str, List[str]] = defaultdict(list)
        
        for source, history in self.histories.items():
            block_hash = history.get_hash(height)
            if block_hash:
                hashes_at_height[block_hash].append(source)
        
        # If only one unique hash, no fork
        if len(hashes_at_height) <= 1:
            # Check if existing fork at this height is now resolved
            if height in self.active_forks:
                await self._resolve_fork(height)
            return None
        
        # Multiple hashes detected - fork found
        branches = list(hashes_at_height.keys())
        sources_by_branch = dict(hashes_at_height)
        
        # Find parent hash
        parent_hash = await self._find_common_parent(height, branches)
        
        # Determine severity
        total_sources = sum(len(srcs) for srcs in hashes_at_height.values())
        max_agreement = max(len(srcs) for srcs in hashes_at_height.values())
        agreement_ratio = max_agreement / total_sources if total_sources > 0 else 0
        
        if agreement_ratio <= 0.5:
            severity = ForkSeverity.CRITICAL
        else:
            severity = ForkSeverity.WARNING
        
        fork_event = ForkEvent(
            height=height,
            parent_hash=parent_hash or "unknown",
            branches=branches,
            sources_by_branch=sources_by_branch,
            severity=severity
        )
        
        # Store or update active fork
        if height not in self.active_forks:
            self.active_forks[height] = fork_event
            if self.config.alert_callback:
                await self._call_alert(fork_event, severity.value)
        else:
            # Update existing fork with new branches/sources
            existing = self.active_forks[height]
            existing.branches = branches
            existing.sources_by_branch = sources_by_branch
            existing.severity = severity
        
        return fork_event
    
    async def _find_common_parent(self, fork_height: int, branches: List[str]) -> Optional[str]:
        """Finds the common parent hash before the fork."""
        parent_height = fork_height - 1
        if parent_height < 0:
            return None
        
        # Get parent hashes from all sources
        parent_hashes: Dict[str, List[str]] = defaultdict(list)
        for source, history in self.histories.items():
            parent = history.get_hash(parent_height)
            if parent:
                parent_hashes[parent].append(source)
        
        # Return the most common parent
        if parent_hashes:
            return max(parent_hashes.keys(), key=lambda k: len(parent_hashes[k]))
        return None
    
    async def _resolve_fork(self, height: int):
        """Marks a fork as resolved."""
        if height not in self.active_forks:
            return
        
        fork = self.active_forks.pop(height)
        fork.duration = time.time() - fork.timestamp
        fork.severity = ForkSeverity.RESOLVED
        self.resolved_forks.append(fork)
        
        if self.config.alert_callback:
            await self._call_alert(fork, "resolved")
    
    async def _call_alert(self, fork: ForkEvent, severity: str):
        """Calls the alert callback safely."""
        try:
            if asyncio.iscoroutinefunction(self.config.alert_callback):
                await self.config.alert_callback(fork, severity)
            else:
                self.config.alert_callback(fork, severity)
        except Exception as e:
            print(f"Alert callback error: {e}")
    
    def get_consensus(self, height: int) -> Optional[str]:
        """
        Determines the main chain hash at a given height based on consensus.
        Returns None if no consensus can be reached.
        """
        hash_votes: Dict[str, int] = defaultdict(int)
        total_sources = 0
        
        for source, history in self.histories.items():
            block_hash = history.get_hash(height)
            if block_hash:
                hash_votes[block_hash] += 1
                total_sources += 1
        
        if not hash_votes:
            return None
        
        # Find hash with most votes
        best_hash = max(hash_votes.keys(), key=lambda k: hash_votes[k])
        best_votes = hash_votes[best_hash]
        
        # Check if it meets threshold
        if total_sources > 0 and best_votes / total_sources >= self.config.consensus_threshold:
            return best_hash
        
        return None
    
    def detect_fork(self, blocks_by_source: Dict[str, List[Tuple[int, str]]]) -> Optional[ForkEvent]:
        """
        Analyzes block data from multiple sources to detect forks.
        
        Args:
            blocks_by_source: Dict mapping source name to list of (height, hash) tuples
        
        Returns:
            ForkEvent if fork detected, None otherwise
        """
        # Load all blocks into histories
        for source, blocks in blocks_by_source.items():
            if source not in self.histories:
                self.histories[source] = BlockHistory(self.config.history_size)
            for height, block_hash in blocks:
                self.histories[source].add_block(height, block_hash)
        
        # Find common height range
        all_heights: Set[int] = set()
        for history in self.histories.values():
            all_heights.update(history.heights)
        
        if not all_heights:
            return None
        
        # Check each height for forks
        for height in sorted(all_heights):
            hashes_at_height: Dict[str, List[str]] = defaultdict(list)
            for source, history in self.histories.items():
                h = history.get_hash(height)
                if h:
                    hashes_at_height[h].append(source)
            
            if len(hashes_at_height) > 1:
                # Fork detected
                branches = list(hashes_at_height.keys())
                sources_by_branch = dict(hashes_at_height)
                
                return ForkEvent(
                    height=height,
                    parent_hash="unknown",  # Would need to trace back
                    branches=branches,
                    sources_by_branch=sources_by_branch
                )
        
        return None
    
    async def cleanup_old_forks(self):
        """Removes forks that have exceeded max_fork_age."""
        current_time = time.time()
        to_resolve = []
        
        for height, fork in self.active_forks.items():
            if current_time - fork.timestamp > self.config.max_fork_age:
                to_resolve.append(height)
        
        for height in to_resolve:
            await self._resolve_fork(height)
    
    def get_stats(self) -> Dict:
        """Returns statistics about the detector state."""
        return {
            "sources": len(self.histories),
            "active_forks": len(self.active_forks),
            "resolved_forks": len(self.resolved_forks),
            "latest_heights": {
                source: hist.get_latest() 
                for source, hist in self.histories.items()
            }
        }


async def monitor_chain(config: ForkConfig):
    """
    Continuously monitors blockchain sources for forks.
    
    This is a long-running coroutine that checks sources at configured intervals.
    In a real implementation, this would connect to actual blockchain nodes.
    
    Args:
        config: ForkConfig instance with monitoring parameters
    """
    detector = ForkDetector(config)
    
    print(f"🔍 Starting fork detection monitor...")
    print(f"   Sources: {len(config.sources)}")
    print(f"   Check interval: {config.check_interval}s")
    print(f"   Confirmation blocks: {config.confirmation_blocks}")
    
    try:
        while True:
            # In a real implementation, this would:
            # 1. Query each source for latest block
            # 2. Add blocks to detector
            # 3. Check for forks
            
            # Simulated monitoring loop
            for source in config.sources:
                # Placeholder: would fetch actual block data
                pass
            
            # Cleanup old forks
            await detector.cleanup_old_forks()
            
            await asyncio.sleep(config.check_interval)
            
    except asyncio.CancelledError:
        print("🛑 Fork detection monitor stopped")
        raise


def detect_fork(blocks_by_source: Dict[str, List[Tuple[int, str]]]) -> Optional[ForkEvent]:
    """
    One-shot fork detection from provided block data.
    
    Args:
        blocks_by_source: Dict mapping source name to list of (height, hash) tuples
        
    Returns:
        ForkEvent if fork detected, None otherwise
        
    Example:
        >>> blocks = {
        ...     "node1": [(100, "0xabc..."), (101, "0xdef...")],
        ...     "node2": [(100, "0xabc..."), (101, "0x123...")]  # Different at 101!
        ... }
        >>> fork = detect_fork(blocks)
        >>> if fork:
        ...     print(f"Fork at height {fork.height}")
    """
    detector = ForkDetector(ForkConfig(sources=list(blocks_by_source.keys())))
    return detector.detect_fork(blocks_by_source)


def get_consensus(blocks_by_source: Dict[str, List[Tuple[int, str]]], height: int) -> Optional[str]:
    """
    Determines the main chain hash at a given height based on consensus.
    
    Args:
        blocks_by_source: Dict mapping source name to list of (height, hash) tuples
        height: Block height to check consensus for
        
    Returns:
        The consensus block hash, or None if no consensus
        
    Example:
        >>> blocks = {
        ...     "node1": [(100, "0xabc...")],
        ...     "node2": [(100, "0xabc...")],
        ...     "node3": [(100, "0xabc...")]
        ... }
        >>> consensus = get_consensus(blocks, 100)
        >>> print(consensus)  # "0xabc..."
    """
    detector = ForkDetector(ForkConfig(sources=list(blocks_by_source.keys())))
    
    # Load blocks
    for source, blocks in blocks_by_source.items():
        for h, block_hash in blocks:
            detector.histories[source].add_block(h, block_hash)
    
    return detector.get_consensus(height)


class MockBlockchainSource:
    """Mock blockchain source for testing and demonstration."""
    
    def __init__(self, name: str, chain: List[str]):
        """
        Args:
            name: Source identifier
            chain: List of block hashes ordered by height (starting at 0)
        """
        self.name = name
        self.chain = chain
    
    def get_block(self, height: int) -> Optional[Tuple[int, str]]:
        """Returns (height, hash) for given height."""
        if 0 <= height < len(self.chain):
            return (height, self.chain[height])
        return None
    
    def get_latest(self) -> Tuple[int, str]:
        """Returns latest (height, hash)."""
        height = len(self.chain) - 1
        return (height, self.chain[height])


def generate_mock_chain(length: int, seed: str = "main") -> List[str]:
    """Generates a deterministic mock blockchain."""
    chain = []
    prev_hash = hashlib.sha256(seed.encode()).hexdigest()[:64]
    
    for i in range(length):
        data = f"{prev_hash}:{i}:{seed}"
        block_hash = hashlib.sha256(data.encode()).hexdigest()[:64]
        chain.append(f"0x{block_hash}")
        prev_hash = block_hash
    
    return chain


def create_forked_chains(
    common_length: int, 
    fork_height: int, 
    branch_a_length: int, 
    branch_b_length: int
) -> Tuple[List[str], List[str], List[str]]:
    """
    Creates mock chains with a fork for testing.
    
    Returns:
        Tuple of (common_chain, branch_a, branch_b)
    """
    common = generate_mock_chain(common_length, "common")
    
    # Branch A continues from fork point
    a_seed = f"branch_a:{common[fork_height]}"
    branch_a_suffix = generate_mock_chain(branch_a_length, a_seed)
    branch_a = common[:fork_height + 1] + branch_a_suffix[1:]
    
    # Branch B diverges at fork point
    b_seed = f"branch_b:{common[fork_height]}"
    branch_b_suffix = generate_mock_chain(branch_b_length, b_seed)
    branch_b = common[:fork_height + 1] + branch_b_suffix[1:]
    
    return common, branch_a, branch_b


# Export public API
__all__ = [
    'ForkConfig',
    'ForkEvent', 
    'ForkSeverity',
    'ForkDetector',
    'BlockHistory',
    'monitor_chain',
    'detect_fork',
    'get_consensus',
    'MockBlockchainSource',
    'generate_mock_chain',
    'create_forked_chains'
]
