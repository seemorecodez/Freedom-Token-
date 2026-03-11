"""
Unit tests for the Stealth Trader skill
"""

import unittest
from stealth_trader import (
    StealthTrader, StealthConfig, StealthLevel,
    OrderChunker, TemporalJitter, DecoyGenerator,
    RouteObfuscator, WalletRotator, TradeChunk
)


class TestOrderChunker(unittest.TestCase):
    """Test order chunking functionality"""
    
    def setUp(self):
        self.config = StealthConfig(level=StealthLevel.MEDIUM)
        self.chunker = OrderChunker(self.config)
    
    def test_chunk_count_range(self):
        """Test that chunks are within expected range"""
        chunks = self.chunker.chunk_order(10000, "BTC-USD")
        self.assertGreaterEqual(len(chunks), 3)
        self.assertLessEqual(len(chunks), 5)
    
    def test_chunk_sum_equals_total(self):
        """Test that chunks sum to total amount"""
        total = 5000
        chunks = self.chunker.chunk_order(total, "BTC-USD")
        chunk_sum = sum(c.amount for c in chunks)
        self.assertAlmostEqual(chunk_sum, total, places=2)
    
    def test_chunk_ids_unique(self):
        """Test that chunk IDs are unique"""
        chunks = self.chunker.chunk_order(10000, "BTC-USD")
        ids = [c.chunk_id for c in chunks]
        self.assertEqual(len(ids), len(set(ids)))


class TestTemporalJitter(unittest.TestCase):
    """Test temporal jitter functionality"""
    
    def setUp(self):
        self.config = StealthConfig(level=StealthLevel.MEDIUM)
        self.jitter = TemporalJitter(self.config)
    
    def test_first_chunk_no_delay(self):
        """Test first chunk has no delay"""
        chunks = [
            TradeChunk("test1", 100, 0, False, ["BTC-USD"]),
            TradeChunk("test2", 100, 0, False, ["BTC-USD"])
        ]
        result = self.jitter.apply_jitter(chunks)
        self.assertEqual(result[0].delay_before, 0)
    
    def test_subsequent_chunks_have_delay(self):
        """Test subsequent chunks have delays"""
        chunks = [
            TradeChunk("test1", 100, 0, False, ["BTC-USD"]),
            TradeChunk("test2", 100, 0, False, ["BTC-USD"])
        ]
        result = self.jitter.apply_jitter(chunks)
        self.assertGreater(result[1].delay_before, 0)


class TestDecoyGenerator(unittest.TestCase):
    """Test decoy generation functionality"""
    
    def test_decoy_count_low_level(self):
        """Test no decoys at low level"""
        config = StealthConfig(level=StealthLevel.LOW)
        decoy_gen = DecoyGenerator(config)
        real_chunks = [TradeChunk("test", 100, 0, False, ["BTC"]) for _ in range(3)]
        result = decoy_gen.generate_decoys(real_chunks, "BTC-USD")
        decoys = [r for r in result if r.is_decoy]
        self.assertEqual(len(decoys), 0)
    
    def test_decoy_count_medium_level(self):
        """Test 1:1 decoy ratio at medium level"""
        config = StealthConfig(level=StealthLevel.MEDIUM)
        decoy_gen = DecoyGenerator(config)
        real_chunks = [TradeChunk("test", 100, 0, False, ["BTC"]) for _ in range(3)]
        result = decoy_gen.generate_decoys(real_chunks, "BTC-USD")
        decoys = [r for r in result if r.is_decoy]
        self.assertEqual(len(decoys), 3)


class TestRouteObfuscator(unittest.TestCase):
    """Test route obfuscation functionality"""
    
    def test_routes_assigned(self):
        """Test that routes are assigned"""
        config = StealthConfig(level=StealthLevel.HIGH, use_multi_hop=True)
        router = RouteObfuscator(config)
        chunks = [TradeChunk("test", 100, 0, False, ["BTC"])]
        result = router.obfuscate_route(chunks, "BTC-USD")
        self.assertGreater(len(result[0].route), 0)


class TestStealthTrader(unittest.TestCase):
    """Integration tests for StealthTrader"""
    
    def test_execute_stealth_trade(self):
        """Test full stealth trade execution"""
        config = StealthConfig(level=StealthLevel.LOW)
        trader = StealthTrader(config)
        
        result = trader.execute_stealth_trade(
            symbol="BTC-USD",
            side="buy",
            amount=1000
        )
        
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["symbol"], "BTC-USD")
        self.assertEqual(result["side"], "buy")
        self.assertEqual(result["total_amount"], 1000)
    
    def test_stealth_levels(self):
        """Test different stealth levels"""
        for level in StealthLevel:
            config = StealthConfig(level=level)
            trader = StealthTrader(config)
            result = trader.execute_stealth_trade(
                symbol="ETH-USD",
                side="sell",
                amount=5000
            )
            self.assertEqual(result["stealth_level"], level.value)


if __name__ == "__main__":
    unittest.main()
