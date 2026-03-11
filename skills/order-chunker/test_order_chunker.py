"""
Unit tests for the order_chunker module
"""

import unittest
from order_chunker import (
    ChunkConfig,
    Chunk,
    DistributionStrategy,
    StealthLevel,
    chunk_order,
    calculate_chunk_sizes,
    generate_chunk_id,
    get_chunk_summary
)


class TestChunkConfig(unittest.TestCase):
    """Test ChunkConfig dataclass and factory methods"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = ChunkConfig()
        self.assertEqual(config.min_chunk, 100.0)
        self.assertEqual(config.max_chunk, 1000.0)
        self.assertEqual(config.strategy, DistributionStrategy.RANDOM)
        self.assertEqual(config.stealth_level, StealthLevel.MEDIUM)
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = ChunkConfig(
            min_chunk=50.0,
            max_chunk=500.0,
            strategy=DistributionStrategy.GEOMETRIC,
            stealth_level=StealthLevel.HIGH
        )
        self.assertEqual(config.min_chunk, 50.0)
        self.assertEqual(config.max_chunk, 500.0)
        self.assertEqual(config.strategy, DistributionStrategy.GEOMETRIC)
        self.assertEqual(config.stealth_level, StealthLevel.HIGH)
    
    def test_from_stealth_level_low(self):
        """Test creating config from low stealth level"""
        config = ChunkConfig.from_stealth_level("low")
        self.assertEqual(config.stealth_level, StealthLevel.LOW)
        self.assertEqual(config.min_chunk, 500.0)
        self.assertEqual(config.max_chunk, 2000.0)
        
        chunk_range = config.get_chunk_range()
        self.assertEqual(chunk_range, (2, 3))
    
    def test_from_stealth_level_medium(self):
        """Test creating config from medium stealth level"""
        config = ChunkConfig.from_stealth_level("medium")
        self.assertEqual(config.stealth_level, StealthLevel.MEDIUM)
        self.assertEqual(config.min_chunk, 100.0)
        self.assertEqual(config.max_chunk, 1000.0)
        
        chunk_range = config.get_chunk_range()
        self.assertEqual(chunk_range, (3, 5))
    
    def test_from_stealth_level_high(self):
        """Test creating config from high stealth level"""
        config = ChunkConfig.from_stealth_level("high")
        self.assertEqual(config.stealth_level, StealthLevel.HIGH)
        self.assertEqual(config.min_chunk, 50.0)
        self.assertEqual(config.max_chunk, 500.0)
        
        chunk_range = config.get_chunk_range()
        self.assertEqual(chunk_range, (5, 10))
    
    def test_from_stealth_level_paranoid(self):
        """Test creating config from paranoid stealth level"""
        config = ChunkConfig.from_stealth_level("paranoid")
        self.assertEqual(config.stealth_level, StealthLevel.PARANOID)
        self.assertEqual(config.min_chunk, 10.0)
        self.assertEqual(config.max_chunk, 200.0)
        
        chunk_range = config.get_chunk_range()
        self.assertEqual(chunk_range, (10, 20))
    
    def test_from_stealth_level_case_insensitive(self):
        """Test that stealth level string is case insensitive"""
        config_lower = ChunkConfig.from_stealth_level("high")
        config_upper = ChunkConfig.from_stealth_level("HIGH")
        self.assertEqual(config_lower.stealth_level, config_upper.stealth_level)


class TestCalculateChunkSizes(unittest.TestCase):
    """Test chunk size calculation with different strategies"""
    
    def test_random_strategy(self):
        """Test random distribution strategy"""
        config = ChunkConfig(
            min_chunk=100,
            max_chunk=500,
            strategy=DistributionStrategy.RANDOM
        )
        sizes = calculate_chunk_sizes(1000, 4, config)
        
        self.assertEqual(len(sizes), 4)
        self.assertAlmostEqual(sum(sizes), 1000, places=5)
        
        # Each size should be within bounds (except possibly last)
        for i, size in enumerate(sizes[:-1]):
            self.assertGreaterEqual(size, config.min_chunk)
            self.assertLessEqual(size, config.max_chunk)
    
    def test_weighted_strategy_front(self):
        """Test weighted strategy with front loading"""
        config = ChunkConfig(
            min_chunk=50,
            max_chunk=1000,
            strategy=DistributionStrategy.WEIGHTED,
            weight_direction="front"
        )
        sizes = calculate_chunk_sizes(1000, 5, config)
        
        self.assertEqual(len(sizes), 5)
        self.assertAlmostEqual(sum(sizes), 1000, places=5)
        # First chunk should generally be larger with front weighting
        self.assertGreater(sizes[0], sizes[-1])
    
    def test_weighted_strategy_back(self):
        """Test weighted strategy with back loading"""
        config = ChunkConfig(
            min_chunk=50,
            max_chunk=1000,
            strategy=DistributionStrategy.WEIGHTED,
            weight_direction="back"
        )
        sizes = calculate_chunk_sizes(1000, 5, config)
        
        self.assertEqual(len(sizes), 5)
        self.assertAlmostEqual(sum(sizes), 1000, places=5)
        # Last chunk should generally be larger with back weighting
        self.assertGreater(sizes[-1], sizes[0])
    
    def test_geometric_strategy(self):
        """Test geometric distribution strategy"""
        config = ChunkConfig(
            min_chunk=10,
            max_chunk=1000,
            strategy=DistributionStrategy.GEOMETRIC,
            geometric_ratio=0.3
        )
        sizes = calculate_chunk_sizes(1000, 5, config)
        
        self.assertEqual(len(sizes), 5)
        self.assertAlmostEqual(sum(sizes), 1000, places=5)
    
    def test_single_chunk(self):
        """Test with single chunk"""
        config = ChunkConfig()
        sizes = calculate_chunk_sizes(500, 1, config)
        
        self.assertEqual(len(sizes), 1)
        self.assertEqual(sizes[0], 500)
    
    def test_invalid_total_amount(self):
        """Test that negative total amount raises error"""
        config = ChunkConfig()
        with self.assertRaises(ValueError):
            calculate_chunk_sizes(-100, 3, config)
        
        with self.assertRaises(ValueError):
            calculate_chunk_sizes(0, 3, config)
    
    def test_invalid_num_chunks(self):
        """Test that invalid num_chunks raises error"""
        config = ChunkConfig()
        with self.assertRaises(ValueError):
            calculate_chunk_sizes(1000, 0, config)
        
        with self.assertRaises(ValueError):
            calculate_chunk_sizes(1000, -1, config)


class TestChunkOrder(unittest.TestCase):
    """Test the main chunk_order function"""
    
    def test_basic_chunking(self):
        """Test basic order chunking"""
        config = ChunkConfig(
            min_chunk=100,
            max_chunk=500,
            strategy=DistributionStrategy.RANDOM,
            stealth_level=StealthLevel.MEDIUM
        )
        chunks = chunk_order(1000, "BTC-USD", config, target_chunks=5)
        
        self.assertEqual(len(chunks), 5)
        
        # Check total
        total = sum(c.amount for c in chunks)
        self.assertAlmostEqual(total, 1000, places=5)
        
        # Check all chunks
        for i, chunk in enumerate(chunks):
            self.assertIsInstance(chunk, Chunk)
            self.assertEqual(chunk.symbol, "BTC-USD")
            self.assertEqual(chunk.sequence, i)
            self.assertIsNotNone(chunk.chunk_id)
            self.assertEqual(len(chunk.chunk_id), 16)  # SHA-256 truncated
            
            # Check metadata
            self.assertEqual(chunk.metadata["total_chunks"], 5)
            self.assertEqual(chunk.metadata["strategy"], "random")
            self.assertEqual(chunk.metadata["stealth_level"], "medium")
    
    def test_chunk_remaining(self):
        """Test that remaining amount is tracked correctly"""
        config = ChunkConfig()
        chunks = chunk_order(1000, "ETH-USD", config, target_chunks=4)
        
        # Remaining should decrease
        self.assertAlmostEqual(chunks[0].remaining, 1000 - chunks[0].amount, places=5)
        self.assertEqual(chunks[-1].remaining, 0)
        
        # Verify: amount + remaining should equal original total
        for chunk in chunks:
            after_this = sum(c.amount for c in chunks[chunk.sequence + 1:])
            self.assertAlmostEqual(chunk.remaining, after_this, places=5)
    
    def test_stealth_level_low(self):
        """Test chunking with low stealth level"""
        config = ChunkConfig.from_stealth_level("low")
        chunks = chunk_order(5000, "BTC-USD", config)
        
        # Should have 2-3 chunks
        self.assertGreaterEqual(len(chunks), 2)
        self.assertLessEqual(len(chunks), 3)
    
    def test_stealth_level_paranoid(self):
        """Test chunking with paranoid stealth level"""
        config = ChunkConfig.from_stealth_level("paranoid")
        chunks = chunk_order(5000, "BTC-USD", config)
        
        # Should have 10-20 chunks
        self.assertGreaterEqual(len(chunks), 10)
        self.assertLessEqual(len(chunks), 20)
    
    def test_default_config(self):
        """Test chunking with default config"""
        chunks = chunk_order(1000, "SOL-USD")
        
        self.assertGreater(len(chunks), 0)
        total = sum(c.amount for c in chunks)
        self.assertAlmostEqual(total, 1000, places=5)
    
    def test_target_chunks_override(self):
        """Test that target_chunks overrides stealth level default"""
        config = ChunkConfig.from_stealth_level("low")  # Would normally be 2-3 chunks
        chunks = chunk_order(1000, "BTC-USD", config, target_chunks=10)
        
        self.assertEqual(len(chunks), 10)


class TestGenerateChunkId(unittest.TestCase):
    """Test chunk ID generation"""
    
    def test_id_format(self):
        """Test that IDs are correct format"""
        chunk_id = generate_chunk_id("BTC-USD", 0)
        self.assertEqual(len(chunk_id), 16)
        self.assertTrue(all(c in '0123456789abcdef' for c in chunk_id))
    
    def test_id_uniqueness(self):
        """Test that IDs are unique"""
        ids = [generate_chunk_id("BTC-USD", i) for i in range(100)]
        self.assertEqual(len(set(ids)), 100)
    
    def test_different_symbols(self):
        """Test that different symbols produce different IDs"""
        id1 = generate_chunk_id("BTC-USD", 0, nonce="abc123")
        id2 = generate_chunk_id("ETH-USD", 0, nonce="abc123")
        self.assertNotEqual(id1, id2)


class TestGetChunkSummary(unittest.TestCase):
    """Test chunk summary generation"""
    
    def test_summary(self):
        """Test summary statistics"""
        config = ChunkConfig.from_stealth_level("medium")
        chunks = chunk_order(1000, "BTC-USD", config, target_chunks=5)
        summary = get_chunk_summary(chunks)
        
        self.assertAlmostEqual(summary["total_amount"], 1000, places=5)
        self.assertEqual(summary["num_chunks"], 5)
        self.assertEqual(summary["symbol"], "BTC-USD")
        self.assertEqual(summary["average_chunk"], 200.0)
        
        amounts = [c.amount for c in chunks]
        self.assertEqual(summary["min_chunk"], min(amounts))
        self.assertEqual(summary["max_chunk"], max(amounts))
    
    def test_empty_chunks(self):
        """Test summary with empty chunk list"""
        summary = get_chunk_summary([])
        self.assertIn("error", summary)


class TestIntegration(unittest.TestCase):
    """Integration tests combining multiple features"""
    
    def test_full_workflow(self):
        """Test a complete chunking workflow"""
        # Create config for high stealth
        config = ChunkConfig.from_stealth_level("high")
        
        # Chunk a large order
        total_amount = 50000
        chunks = chunk_order(total_amount, "BTC-USD", config)
        
        # Get summary
        summary = get_chunk_summary(chunks)
        
        # Verify
        self.assertGreaterEqual(summary["num_chunks"], 5)
        self.assertLessEqual(summary["num_chunks"], 10)
        self.assertAlmostEqual(summary["total_amount"], total_amount, places=5)
        
        # All chunks should have unique IDs
        ids = [c.chunk_id for c in chunks]
        self.assertEqual(len(set(ids)), len(ids))
        
        # Verify sequence continuity
        sequences = [c.sequence for c in chunks]
        self.assertEqual(sequences, list(range(len(chunks))))
    
    def test_all_strategies(self):
        """Test all distribution strategies work correctly"""
        total = 10000
        
        for strategy in DistributionStrategy:
            config = ChunkConfig(
                min_chunk=100,
                max_chunk=1000,
                strategy=strategy,
                stealth_level=StealthLevel.MEDIUM
            )
            chunks = chunk_order(total, "ETH-USD", config, target_chunks=8)
            
            self.assertEqual(len(chunks), 8)
            actual_total = sum(c.amount for c in chunks)
            self.assertAlmostEqual(actual_total, total, places=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
