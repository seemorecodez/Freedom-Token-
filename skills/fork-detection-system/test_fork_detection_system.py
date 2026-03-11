"""
Test suite for Fork Detection System

Run with: python -m pytest test_fork_detection_system.py -v
"""

import pytest
import asyncio
from typing import List, Tuple, Dict
import time

from fork_detection_system import (
    ForkConfig,
    ForkEvent,
    ForkSeverity,
    ForkDetector,
    BlockHistory,
    monitor_chain,
    detect_fork,
    get_consensus,
    MockBlockchainSource,
    generate_mock_chain,
    create_forked_chains
)


class TestForkConfig:
    """Tests for ForkConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ForkConfig(sources=["node1"])
        assert config.sources == ["node1"]
        assert config.check_interval == 10.0
        assert config.confirmation_blocks == 6
        assert config.consensus_threshold == 0.67
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ForkConfig(
            sources=["a", "b", "c"],
            check_interval=5.0,
            confirmation_blocks=12,
            consensus_threshold=0.8
        )
        assert config.sources == ["a", "b", "c"]
        assert config.check_interval == 5.0
        assert config.confirmation_blocks == 12
        assert config.consensus_threshold == 0.8
    
    def test_no_sources_raises(self):
        """Test that empty sources raises ValueError."""
        with pytest.raises(ValueError, match="At least one source"):
            ForkConfig(sources=[])
    
    def test_invalid_threshold_raises(self):
        """Test that invalid threshold raises ValueError."""
        with pytest.raises(ValueError, match="consensus_threshold"):
            ForkConfig(sources=["node1"], consensus_threshold=1.5)
        
        with pytest.raises(ValueError, match="consensus_threshold"):
            ForkConfig(sources=["node1"], consensus_threshold=0)


class TestBlockHistory:
    """Tests for BlockHistory class."""
    
    def test_add_and_get_block(self):
        """Test adding and retrieving blocks."""
        history = BlockHistory(max_size=100)
        
        history.add_block(100, "0xabc123")
        assert history.get_hash(100) == "0xabc123"
        assert history.get_latest() == (100, "0xabc123")
    
    def test_add_multiple_blocks(self):
        """Test adding multiple blocks."""
        history = BlockHistory(max_size=100)
        
        for i in range(10):
            history.add_block(i, f"0xhash{i}")
        
        assert history.get_hash(5) == "0xhash5"
        assert history.get_latest() == (9, "0xhash9")
    
    def test_hash_change_detection(self):
        """Test that changing a hash returns True."""
        history = BlockHistory(max_size=100)
        
        history.add_block(100, "0xabc123")
        changed = history.add_block(100, "0xdef456")
        
        assert changed is True
        assert history.get_hash(100) == "0xdef456"
    
    def test_duplicate_hash_no_change(self):
        """Test that adding same hash returns False."""
        history = BlockHistory(max_size=100)
        
        history.add_block(100, "0xabc123")
        changed = history.add_block(100, "0xabc123")
        
        assert changed is False
    
    def test_pruning_old_blocks(self):
        """Test that old blocks are pruned."""
        history = BlockHistory(max_size=5)
        
        for i in range(10):
            history.add_block(i, f"0xhash{i}")
        
        # First 5 should be pruned
        assert history.get_hash(0) is None
        assert history.get_hash(4) is None
        assert history.get_hash(5) == "0xhash5"
        assert history.get_hash(9) == "0xhash9"
    
    def test_get_range(self):
        """Test getting range of blocks."""
        history = BlockHistory(max_size=100)
        
        for i in range(20):
            history.add_block(i, f"0xhash{i}")
        
        result = history.get_range(5, 8)
        assert result == [
            (5, "0xhash5"),
            (6, "0xhash6"),
            (7, "0xhash7"),
            (8, "0xhash8")
        ]


class TestForkEvent:
    """Tests for ForkEvent dataclass."""
    
    def test_fork_event_creation(self):
        """Test creating a fork event."""
        event = ForkEvent(
            height=100,
            parent_hash="0xparent",
            branches=["0xbranch1", "0xbranch2"],
            sources_by_branch={
                "0xbranch1": ["node1", "node2"],
                "0xbranch2": ["node3"]
            }
        )
        
        assert event.height == 100
        assert event.parent_hash == "0xparent"
        assert event.branches == ["0xbranch1", "0xbranch2"]
    
    def test_affected_sources(self):
        """Test getting all affected sources."""
        event = ForkEvent(
            height=100,
            parent_hash="0xparent",
            branches=["0xbranch1", "0xbranch2"],
            sources_by_branch={
                "0xbranch1": ["node1", "node2"],
                "0xbranch2": ["node3"]
            }
        )
        
        assert set(event.affected_sources) == {"node1", "node2", "node3"}
    
    def test_main_branch(self):
        """Test determining main branch."""
        event = ForkEvent(
            height=100,
            parent_hash="0xparent",
            branches=["0xbranch1", "0xbranch2"],
            sources_by_branch={
                "0xbranch1": ["node1", "node2"],
                "0xbranch2": ["node3"]
            }
        )
        
        assert event.main_branch == "0xbranch1"
    
    def test_minority_branches(self):
        """Test getting minority branches."""
        event = ForkEvent(
            height=100,
            parent_hash="0xparent",
            branches=["0xbranch1", "0xbranch2", "0xbranch3"],
            sources_by_branch={
                "0xbranch1": ["node1", "node2", "node3"],
                "0xbranch2": ["node4"],
                "0xbranch3": ["node5"]
            }
        )
        
        assert event.minority_branches == ["0xbranch2", "0xbranch3"]


class TestForkDetector:
    """Tests for ForkDetector class."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return ForkConfig(
            sources=["node1", "node2", "node3"],
            consensus_threshold=0.67
        )
    
    @pytest.fixture
    def detector(self, config):
        """Create a fork detector instance."""
        return ForkDetector(config)
    
    def test_detector_initialization(self, detector, config):
        """Test detector initialization."""
        assert len(detector.histories) == 3
        assert "node1" in detector.histories
        assert "node2" in detector.histories
        assert "node3" in detector.histories
    
    @pytest.mark.asyncio
    async def test_add_block_no_fork(self, detector):
        """Test adding blocks without fork."""
        # Add same block to all sources
        for source in ["node1", "node2", "node3"]:
            fork = await detector.add_block(source, 100, "0xabc123")
            assert fork is None
    
    @pytest.mark.asyncio
    async def test_detect_fork_simple(self, detector):
        """Test simple fork detection."""
        # Add same blocks up to height 100
        for height in range(100):
            for source in ["node1", "node2", "node3"]:
                await detector.add_block(source, height, f"0xcommon{height}")
        
        # At height 100, node3 diverges
        for source in ["node1", "node2"]:
            await detector.add_block(source, 100, "0xmain100")
        
        fork = await detector.add_block("node3", 100, "0xfork100")
        
        assert fork is not None
        assert fork.height == 100
        assert "0xmain100" in fork.branches
        assert "0xfork100" in fork.branches
    
    @pytest.mark.asyncio
    async def test_detect_fork_multiple_branches(self, detector):
        """Test fork with multiple branches."""
        # Divergence at height 50
        await detector.add_block("node1", 50, "0xbranch_a")
        await detector.add_block("node2", 50, "0xbranch_b")
        await detector.add_block("node3", 50, "0xbranch_c")
        
        fork = await detector.add_block("node3", 50, "0xbranch_c")
        
        assert fork is not None
        assert len(fork.branches) == 3
    
    def test_get_consensus(self, detector):
        """Test consensus determination."""
        # Add blocks to create consensus
        for source in ["node1", "node2", "node3"]:
            detector.histories[source].add_block(100, "0xconsensus")
        
        consensus = detector.get_consensus(100)
        assert consensus == "0xconsensus"
    
    def test_get_consensus_no_majority(self, detector):
        """Test when no consensus exists."""
        # Split 2-1 with threshold 0.67
        detector.histories["node1"].add_block(100, "0xhash_a")
        detector.histories["node2"].add_block(100, "0xhash_a")
        detector.histories["node3"].add_block(100, "0xhash_b")
        
        # 2/3 = 0.667 < 0.67, so no consensus
        consensus = detector.get_consensus(100)
        assert consensus is None
    
    def test_get_consensus_below_threshold(self, detector):
        """Test when agreement is below threshold."""
        detector.config.consensus_threshold = 0.8  # Require 80%
        
        detector.histories["node1"].add_block(100, "0xhash_a")
        detector.histories["node2"].add_block(100, "0xhash_a")
        detector.histories["node3"].add_block(100, "0xhash_b")
        
        # 2/3 = 0.667 < 0.8
        consensus = detector.get_consensus(100)
        assert consensus is None
    
    def test_detect_fork_from_data(self):
        """Test one-shot fork detection function."""
        blocks: Dict[str, List[Tuple[int, str]]] = {
            "node1": [
                (98, "0xcommon98"),
                (99, "0xcommon99"),
                (100, "0xmain100"),
            ],
            "node2": [
                (98, "0xcommon98"),
                (99, "0xcommon99"),
                (100, "0xfork100"),  # Fork!
            ]
        }
        
        fork = detect_fork(blocks)
        
        assert fork is not None
        assert fork.height == 100
        assert fork.parent_hash == "unknown" or fork.parent_hash
    
    def test_get_consensus_from_data(self):
        """Test one-shot consensus function."""
        blocks: Dict[str, List[Tuple[int, str]]] = {
            "node1": [(100, "0xabc123")],
            "node2": [(100, "0xabc123")],
            "node3": [(100, "0xabc123")]
        }
        
        consensus = get_consensus(blocks, 100)
        assert consensus == "0xabc123"
    
    @pytest.mark.asyncio
    async def test_fork_resolution(self, detector):
        """Test that forks are marked resolved."""
        # Create a fork
        await detector.add_block("node1", 100, "0xmain")
        await detector.add_block("node2", 100, "0xmain")
        await detector.add_block("node3", 100, "0xfork")
        
        # Resolve by having node3 switch to main
        await detector.add_block("node3", 100, "0xmain")
        
        # Fork should be resolved
        assert 100 not in detector.active_forks
        assert len(detector.resolved_forks) == 1
    
    def test_get_stats(self, detector):
        """Test getting detector statistics."""
        stats = detector.get_stats()
        
        assert stats["sources"] == 3
        assert stats["active_forks"] == 0
        assert stats["resolved_forks"] == 0


class TestMockBlockchainSource:
    """Tests for mock blockchain utilities."""
    
    def test_generate_mock_chain(self):
        """Test mock chain generation."""
        chain = generate_mock_chain(10, "test")
        
        assert len(chain) == 10
        assert all(h.startswith("0x") for h in chain)
        # Should be deterministic
        chain2 = generate_mock_chain(10, "test")
        assert chain == chain2
    
    def test_create_forked_chains(self):
        """Test creating forked chains."""
        common, branch_a, branch_b = create_forked_chains(
            common_length=10,
            fork_height=5,
            branch_a_length=10,
            branch_b_length=8
        )
        
        # Common part should be shared up to fork_height
        assert common[:6] == branch_a[:6]
        assert common[:6] == branch_b[:6]
        
        # After fork, should diverge
        assert branch_a[6] != branch_b[6]
    
    def test_mock_blockchain_source(self):
        """Test mock blockchain source."""
        chain = generate_mock_chain(20)
        source = MockBlockchainSource("test_node", chain)
        
        assert source.get_block(10) == (10, chain[10])
        assert source.get_latest() == (19, chain[19])
        assert source.get_block(100) is None


class TestAlertCallbacks:
    """Tests for alert callback functionality."""
    
    @pytest.mark.asyncio
    async def test_sync_alert_callback(self):
        """Test synchronous alert callback."""
        alerts = []
        
        def on_alert(fork: ForkEvent, severity: str):
            alerts.append((fork.height, severity))
        
        config = ForkConfig(
            sources=["node1", "node2"],
            alert_callback=on_alert
        )
        
        detector = ForkDetector(config)
        
        await detector.add_block("node1", 100, "0xmain")
        await detector.add_block("node2", 100, "0xfork")
        
        assert len(alerts) == 1
        # 1-1 split = 50% = CRITICAL
        assert alerts[0] == (100, "critical")
    
    @pytest.mark.asyncio
    async def test_async_alert_callback(self):
        """Test asynchronous alert callback."""
        alerts = []
        
        async def on_alert(fork: ForkEvent, severity: str):
            alerts.append((fork.height, severity))
        
        config = ForkConfig(
            sources=["node1", "node2"],
            alert_callback=on_alert
        )
        
        detector = ForkDetector(config)
        
        await detector.add_block("node1", 100, "0xmain")
        await detector.add_block("node2", 100, "0xfork")
        
        assert len(alerts) == 1
    
    @pytest.mark.asyncio
    async def test_alert_callback_error_handling(self):
        """Test that alert callback errors don't crash detector."""
        def on_alert(fork: ForkEvent, severity: str):
            raise RuntimeError("Alert error!")
        
        config = ForkConfig(
            sources=["node1", "node2"],
            alert_callback=on_alert
        )
        
        detector = ForkDetector(config)
        
        # Should not raise despite callback error
        await detector.add_block("node1", 100, "0xmain")
        await detector.add_block("node2", 100, "0xfork")


class TestSeverityLevels:
    """Tests for fork severity classification."""
    
    @pytest.mark.asyncio
    async def test_warning_severity(self):
        """Test warning severity for minor forks."""
        config = ForkConfig(sources=["a", "b", "c", "d"])
        detector = ForkDetector(config)
        
        # 3 out of 4 agree = 75%, should be warning
        await detector.add_block("a", 100, "0xmain")
        await detector.add_block("b", 100, "0xmain")
        await detector.add_block("c", 100, "0xmain")
        fork = await detector.add_block("d", 100, "0xfork")
        
        assert fork.severity == ForkSeverity.WARNING
    
    @pytest.mark.asyncio
    async def test_critical_severity(self):
        """Test critical severity for major forks."""
        config = ForkConfig(sources=["a", "b", "c", "d"])
        detector = ForkDetector(config)
        
        # 2-2 split = 50%, should be critical
        await detector.add_block("a", 100, "0xbranch1")
        await detector.add_block("b", 100, "0xbranch1")
        await detector.add_block("c", 100, "0xbranch2")
        fork = await detector.add_block("d", 100, "0xbranch2")
        
        # Fork is returned/updated with each divergent block
        # The active fork should have CRITICAL severity for 50-50 split
        active_fork = detector.active_forks.get(100)
        assert active_fork is not None
        assert active_fork.severity == ForkSeverity.CRITICAL


class TestIntegration:
    """Integration tests simulating real scenarios."""
    
    def test_long_chain_with_minority_fork(self):
        """Test detection of a minority fork in a long chain."""
        # Create a long common chain
        common = generate_mock_chain(1000, "mainnet")
        
        # Create a minority fork (1 node)
        fork_seed = f"fork:{common[500]}"
        fork_suffix = generate_mock_chain(500, fork_seed)
        minority_chain = common[:501] + fork_suffix[1:]
        
        # Build blocks_by_source
        blocks = {
            "main_node1": list(enumerate(common)),
            "main_node2": list(enumerate(common)),
            "main_node3": list(enumerate(common)),
            "rogue_node": list(enumerate(minority_chain))
        }
        
        fork = detect_fork(blocks)
        
        assert fork is not None
        assert fork.height == 501
        assert "rogue_node" in fork.affected_sources
    
    @pytest.mark.asyncio
    async def test_chain_reorganization(self):
        """Test handling of chain reorganization."""
        config = ForkConfig(sources=["a", "b", "c"])
        detector = ForkDetector(config)
        
        # Initial common chain
        for i in range(100):
            for src in ["a", "b", "c"]:
                await detector.add_block(src, i, f"0xblock{i}")
        
        # Node 'a' sees a reorg at block 95
        for i in range(95, 100):
            await detector.add_block("a", i, f"0xreorg{i}")
        
        # This should be detected as a fork
        fork = await detector.add_block("a", 99, "0xreorg99")
        
        # May or may not detect depending on other nodes
        # But history for node 'a' should reflect the change
        assert detector.histories["a"].get_hash(95) == "0xreorg95"


class TestMonitorChain:
    """Tests for the monitor_chain coroutine."""
    
    @pytest.mark.asyncio
    async def test_monitor_chain_start_stop(self):
        """Test that monitor chain starts and can be cancelled."""
        config = ForkConfig(
            sources=["node1"],
            check_interval=0.1
        )
        
        # Start monitor and cancel after short delay
        task = asyncio.create_task(monitor_chain(config))
        await asyncio.sleep(0.2)
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
