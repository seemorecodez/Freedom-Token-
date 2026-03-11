"""
Unit tests for the Decoy Generator skill
"""

import unittest
import time
import random
from typing import List, Dict, Any

from decoy_generator import (
    DecoyGenerator,
    DecoyConfig,
    DecoyTransaction,
    DecoyType,
    DecoyStatus,
    DecoyLifecycleManager,
    FrequencyPattern,
    SizeStrategy,
    create_trade_decoy,
    create_transfer_decoy,
    create_approval_decoy
)


class TestDecoyConfig(unittest.TestCase):
    """Test DecoyConfig dataclass"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = DecoyConfig()
        self.assertEqual(config.ratio, 1.0)
        self.assertEqual(config.size_range, (0.05, 2.0))
        self.assertEqual(config.frequency, FrequencyPattern.RANDOM)
        self.assertEqual(config.decoy_types, [DecoyType.TRADE])
        self.assertEqual(config.size_strategy, SizeStrategy.PROPORTIONAL)
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = DecoyConfig(
            ratio=3.0,
            size_range=(0.1, 5.0),
            decoy_types=[DecoyType.TRADE, DecoyType.TRANSFER],
            size_strategy=SizeStrategy.VOLUME_MIMIC
        )
        self.assertEqual(config.ratio, 3.0)
        self.assertEqual(config.size_range, (0.1, 5.0))
        self.assertEqual(len(config.decoy_types), 2)
        self.assertEqual(config.size_strategy, SizeStrategy.VOLUME_MIMIC)


class TestDecoyTransaction(unittest.TestCase):
    """Test DecoyTransaction dataclass"""
    
    def test_transaction_creation(self):
        """Test creating a decoy transaction"""
        tx = DecoyTransaction(
            decoy_id="test_123",
            decoy_type=DecoyType.TRADE,
            amount=1000.0,
            symbol="BTC-USD"
        )
        self.assertEqual(tx.decoy_id, "test_123")
        self.assertEqual(tx.decoy_type, DecoyType.TRADE)
        self.assertEqual(tx.amount, 1000.0)
        self.assertEqual(tx.symbol, "BTC-USD")
        self.assertEqual(tx.status, DecoyStatus.CREATED)
    
    def test_transaction_to_dict(self):
        """Test conversion to dictionary"""
        tx = DecoyTransaction(
            decoy_id="test_456",
            decoy_type=DecoyType.TRANSFER,
            amount=500.0,
            symbol="ETH",
            related_real_tx="real_123"
        )
        d = tx.to_dict()
        self.assertEqual(d["decoy_id"], "test_456")
        self.assertEqual(d["decoy_type"], "transfer")
        self.assertEqual(d["amount"], 500.0)
        self.assertEqual(d["related_real_tx"], "real_123")


class TestDecoyLifecycleManager(unittest.TestCase):
    """Test DecoyLifecycleManager"""
    
    def setUp(self):
        self.config = DecoyConfig()
        self.manager = DecoyLifecycleManager(self.config)
        self.sample_decoy = DecoyTransaction(
            decoy_id="test_lifecycle",
            decoy_type=DecoyType.TRADE,
            amount=100.0,
            symbol="ETH-USD"
        )
    
    def test_create_decoy(self):
        """Test creating/decoy registration"""
        result = self.manager.create(self.sample_decoy)
        self.assertEqual(result.status, DecoyStatus.CREATED)
        self.assertIn("test_lifecycle", self.manager.active_decoys)
    
    def test_queue_decoy(self):
        """Test queuing a decoy"""
        self.manager.create(self.sample_decoy)
        execute_time = time.time() + 100
        result = self.manager.queue("test_lifecycle", execute_time)
        self.assertEqual(result.status, DecoyStatus.QUEUED)
        self.assertEqual(result.execute_at, execute_time)
    
    def test_execute_decoy_success(self):
        """Test successful decoy execution"""
        self.manager.create(self.sample_decoy)
        self.manager.queue("test_lifecycle")
        result = self.manager.execute("test_lifecycle")
        self.assertEqual(result["status"], "success")
        self.assertIn("tx_hash", result)
        self.assertEqual(self.sample_decoy.status, DecoyStatus.EXECUTED)
    
    def test_execute_decoy_failure_simulation(self):
        """Test simulated decoy failure"""
        config = DecoyConfig(include_failures=True, failure_rate=1.0)  # Always fail
        manager = DecoyLifecycleManager(config)
        decoy = DecoyTransaction(
            decoy_id="fail_test",
            decoy_type=DecoyType.TRADE,
            amount=100.0,
            symbol="ETH"
        )
        manager.create(decoy)
        manager.queue("fail_test")
        result = manager.execute("fail_test")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(decoy.status, DecoyStatus.FAILED)
    
    def test_retire_decoy(self):
        """Test decoy retirement"""
        self.manager.create(self.sample_decoy)
        result = self.manager.retire("test_lifecycle")
        self.assertEqual(result.status, DecoyStatus.RETIRED)
        self.assertNotIn("test_lifecycle", self.manager.active_decoys)
        self.assertIn(result, self.manager.decoy_history)
    
    def test_retire_expired(self):
        """Test auto-retirement of expired decoys"""
        config = DecoyConfig(retire_after=0)  # Immediate expiration
        manager = DecoyLifecycleManager(config)
        decoy = DecoyTransaction(
            decoy_id="expired_test",
            decoy_type=DecoyType.TRADE,
            amount=100.0,
            symbol="ETH"
        )
        manager.create(decoy)
        time.sleep(0.01)  # Small delay to ensure expiration
        retired = manager.retire_expired()
        self.assertEqual(len(retired), 1)
        self.assertEqual(retired[0].decoy_id, "expired_test")
    
    def test_get_stats(self):
        """Test statistics gathering"""
        self.manager.create(self.sample_decoy)
        stats = self.manager.get_stats()
        self.assertEqual(stats["active_count"], 1)
        self.assertEqual(stats["by_status"]["CREATED"], 1)
    
    def test_invalid_decoy_operations(self):
        """Test operations on non-existent decoys"""
        with self.assertRaises(ValueError):
            self.manager.queue("nonexistent")
        with self.assertRaises(ValueError):
            self.manager.execute("nonexistent")
        with self.assertRaises(ValueError):
            self.manager.retire("nonexistent")


class TestCalculateDecoySize(unittest.TestCase):
    """Test size calculation strategies"""
    
    def test_proportional_strategy(self):
        """Test proportional size calculation"""
        config = DecoyConfig(
            size_strategy=SizeStrategy.PROPORTIONAL,
            size_range=(0.5, 1.5)
        )
        generator = DecoyGenerator(config)
        reference = 1000.0
        
        # Test multiple times due to randomness
        for _ in range(10):
            size = generator.calculate_decoy_size(reference)
            self.assertGreaterEqual(size, reference * 0.5)
            self.assertLessEqual(size, reference * 1.5)
    
    def test_fixed_range_strategy(self):
        """Test fixed range size calculation"""
        config = DecoyConfig(
            size_strategy=SizeStrategy.FIXED_RANGE,
            absolute_range=(100.0, 500.0)
        )
        generator = DecoyGenerator(config)
        
        for _ in range(10):
            size = generator.calculate_decoy_size(10000.0)  # Reference ignored
            self.assertGreaterEqual(size, 100.0)
            self.assertLessEqual(size, 500.0)
    
    def test_volume_mimic_strategy(self):
        """Test volume mimic size calculation"""
        config = DecoyConfig(size_strategy=SizeStrategy.VOLUME_MIMIC)
        generator = DecoyGenerator(config)
        
        sizes = [generator.calculate_decoy_size(1000.0) for _ in range(100)]
        # Should have some variation
        self.assertGreater(max(sizes), min(sizes))
        # All should be positive
        self.assertTrue(all(s > 0 for s in sizes))
    
    def test_noise_floor_strategy(self):
        """Test noise floor size calculation"""
        config = DecoyConfig(size_strategy=SizeStrategy.NOISE_FLOOR)
        generator = DecoyGenerator(config)
        
        size = generator.calculate_decoy_size(1000.0)
        # Should be at least 1% of reference or $10
        self.assertGreaterEqual(size, 10.0)
    
    def test_approval_type_adjustment(self):
        """Test approval type specific size adjustment"""
        config = DecoyConfig()
        generator = DecoyGenerator(config)
        
        # Approvals should sometimes be 0 (revoke) or max
        revoke_count = 0
        max_count = 0
        for _ in range(100):
            size = generator.calculate_decoy_size(1000.0, DecoyType.APPROVAL)
            if size == 0:
                revoke_count += 1
            elif size > 2**200:  # Close to max uint256
                max_count += 1
        
        # Should have seen at least some special values
        self.assertGreater(revoke_count + max_count, 0)


class TestGenerateDecoyTransaction(unittest.TestCase):
    """Test single decoy generation"""
    
    def setUp(self):
        self.config = DecoyConfig(decoy_types=list(DecoyType))
        self.generator = DecoyGenerator(self.config)
    
    def test_generate_trade_decoy(self):
        """Test generating a trade decoy"""
        decoy = self.generator.generate_decoy_transaction(
            reference_amount=1000.0,
            decoy_type=DecoyType.TRADE,
            symbol="BTC-USD"
        )
        self.assertEqual(decoy.decoy_type, DecoyType.TRADE)
        self.assertEqual(decoy.symbol, "BTC-USD")
        self.assertIn("side", decoy.metadata)
        self.assertIn(decoy.metadata["side"], ["buy", "sell"])
    
    def test_generate_transfer_decoy(self):
        """Test generating a transfer decoy"""
        decoy = self.generator.generate_decoy_transaction(
            reference_amount=500.0,
            decoy_type=DecoyType.TRANSFER,
            symbol="ETH"
        )
        self.assertEqual(decoy.decoy_type, DecoyType.TRANSFER)
        self.assertIn("to_address", decoy.metadata)
        self.assertTrue(decoy.metadata["to_address"].startswith("0x"))
    
    def test_generate_approval_decoy(self):
        """Test generating an approval decoy"""
        decoy = self.generator.generate_decoy_transaction(
            reference_amount=1000.0,
            decoy_type=DecoyType.APPROVAL,
            symbol="USDC"
        )
        self.assertEqual(decoy.decoy_type, DecoyType.APPROVAL)
        self.assertIn("spender", decoy.metadata)
    
    def test_generate_swap_decoy(self):
        """Test generating a swap decoy"""
        decoy = self.generator.generate_decoy_transaction(
            reference_amount=1000.0,
            decoy_type=DecoyType.SWAP,
            symbol="ETH-USDC"
        )
        self.assertEqual(decoy.decoy_type, DecoyType.SWAP)
        self.assertIn("pool_fee", decoy.metadata)
        self.assertIn(decoy.metadata["pool_fee"], [100, 500, 3000, 10000])
    
    def test_generate_bridge_decoy(self):
        """Test generating a bridge decoy"""
        decoy = self.generator.generate_decoy_transaction(
            reference_amount=1000.0,
            decoy_type=DecoyType.BRIDGE,
            symbol="ETH-ARB"
        )
        self.assertEqual(decoy.decoy_type, DecoyType.BRIDGE)
        self.assertIn("source_chain", decoy.metadata)
        self.assertIn("dest_chain", decoy.metadata)
    
    def test_generate_random_decoy_type(self):
        """Test generating decoy with random type"""
        decoy = self.generator.generate_decoy_transaction(reference_amount=1000.0)
        self.assertIn(decoy.decoy_type, list(DecoyType))
    
    def test_generate_with_related_real_tx(self):
        """Test linking decoy to real transaction"""
        decoy = self.generator.generate_decoy_transaction(
            reference_amount=1000.0,
            related_real_tx="real_tx_123"
        )
        self.assertEqual(decoy.related_real_tx, "real_tx_123")
    
    def test_decoy_id_format(self):
        """Test decoy ID format"""
        decoy = self.generator.generate_decoy_transaction()
        self.assertTrue(decoy.decoy_id.startswith("decoy_"))
        self.assertEqual(len(decoy.decoy_id), 26)  # "decoy_" + 20 hex chars
    
    def test_decoy_auto_registered(self):
        """Test that generated decoys are auto-registered"""
        decoy = self.generator.generate_decoy_transaction()
        self.assertIn(decoy.decoy_id, self.generator.lifecycle.active_decoys)


class TestGenerateDecoyBatch(unittest.TestCase):
    """Test batch decoy generation"""
    
    def setUp(self):
        self.config = DecoyConfig(ratio=2.0)
        self.generator = DecoyGenerator(self.config)
        self.real_transactions = [
            {"tx_id": f"real_{i}", "amount": 1000.0 * (i + 1), "symbol": "ETH-USD"}
            for i in range(5)
        ]
    
    def test_batch_size_based_on_ratio(self):
        """Test batch size calculated from ratio"""
        decoys = self.generator.generate_decoy_batch(self.real_transactions)
        expected = int(len(self.real_transactions) * self.config.ratio)
        self.assertEqual(len(decoys), expected)
    
    def test_batch_size_override(self):
        """Test explicit batch size override"""
        decoys = self.generator.generate_decoy_batch(self.real_transactions, batch_size=10)
        self.assertEqual(len(decoys), 10)
    
    def test_batch_empty_real_transactions(self):
        """Test batch generation with no real transactions"""
        decoys = self.generator.generate_decoy_batch([], batch_size=3)
        self.assertEqual(len(decoys), 3)
    
    def test_batch_decoys_reference_real(self):
        """Test that batch decoys reference real transactions"""
        decoys = self.generator.generate_decoy_batch(self.real_transactions)
        related_ids = [d.related_real_tx for d in decoys if d.related_real_tx]
        real_ids = {tx["tx_id"] for tx in self.real_transactions}
        # At least some should be linked to real transactions
        self.assertTrue(any(rid in real_ids for rid in related_ids))


class TestMixDecoysWithReal(unittest.TestCase):
    """Test mixing decoys with real transactions"""
    
    def setUp(self):
        self.config = DecoyConfig(ratio=1.0)
        self.generator = DecoyGenerator(self.config)
        self.real_transactions = [
            {"tx_id": f"real_{i}", "amount": 1000.0, "symbol": "ETH-USD"}
            for i in range(3)
        ]
        self.decoys = [
            DecoyTransaction(
                decoy_id=f"decoy_{i}",
                decoy_type=DecoyType.TRADE,
                amount=500.0,
                symbol="ETH-USD"
            )
            for i in range(3)
        ]
    
    def test_mix_count(self):
        """Test correct count in mixed result"""
        mixed = self.generator.mix_decoys_with_real(self.real_transactions, self.decoys)
        self.assertEqual(len(mixed), 6)  # 3 real + 3 decoys
    
    def test_mix_identifies_decoys(self):
        """Test that decoys are marked in mixed result"""
        mixed = self.generator.mix_decoys_with_real(self.real_transactions, self.decoys)
        decoy_count = sum(1 for tx in mixed if tx.get("is_decoy"))
        self.assertEqual(decoy_count, 3)
    
    def test_mix_no_shuffle_preserves_order(self):
        """Test that no shuffle preserves real order"""
        mixed = self.generator.mix_decoys_with_real(
            self.real_transactions,
            self.decoys,
            shuffle=False
        )
        # Real transactions should appear first (before decoys appended)
        real_first = mixed[:len(self.real_transactions)]
        for i, tx in enumerate(real_first):
            self.assertEqual(tx["tx_id"], f"real_{i}")
    
    def test_mix_auto_generates_decoys(self):
        """Test that decoys are auto-generated if not provided"""
        mixed = self.generator.mix_decoys_with_real(self.real_transactions)
        decoy_count = sum(1 for tx in mixed if tx.get("is_decoy"))
        self.assertGreater(decoy_count, 0)
    
    def test_mix_adds_scheduled_time(self):
        """Test that mixed transactions have scheduled times"""
        mixed = self.generator.mix_decoys_with_real(self.real_transactions, self.decoys)
        for tx in mixed:
            self.assertIn("scheduled_time", tx)


class TestTimingPatterns(unittest.TestCase):
    """Test timing pattern distributions"""
    
    def test_random_pattern(self):
        """Test random timing pattern"""
        config = DecoyConfig(frequency=FrequencyPattern.RANDOM, jitter_range=(10, 100))
        generator = DecoyGenerator(config)
        
        txs = [{"id": i} for i in range(10)]
        result = generator._apply_timing_pattern(txs)
        
        times = [tx["scheduled_time"] for tx in result]
        self.assertEqual(len(times), 10)
        # Most times should be different (allowing for rare collisions)
        self.assertGreaterEqual(len(set(times)), 8)
    
    def test_uniform_pattern(self):
        """Test uniform timing pattern"""
        config = DecoyConfig(frequency=FrequencyPattern.UNIFORM, jitter_range=(0, 90))
        generator = DecoyGenerator(config)
        
        txs = [{"id": i} for i in range(10)]
        result = generator._apply_timing_pattern(txs)
        
        times = [tx["scheduled_time"] for tx in result]
        # Should be roughly evenly spaced
        intervals = [times[i+1] - times[i] for i in range(len(times)-1)]
        # All intervals should be similar (within factor of 2)
        self.assertLess(max(intervals), min(intervals) * 2.1)
    
    def test_burst_pattern(self):
        """Test burst timing pattern"""
        config = DecoyConfig(frequency=FrequencyPattern.BURST)
        generator = DecoyGenerator(config)
        
        txs = [{"id": i} for i in range(9)]
        result = generator._apply_timing_pattern(txs)
        
        times = [tx["scheduled_time"] for tx in result]
        # Should have some clustering (bursts)
        # First 3 should be close together
        self.assertLess(times[2] - times[0], 20)
    
    def test_poisson_pattern(self):
        """Test poisson timing pattern"""
        config = DecoyConfig(frequency=FrequencyPattern.POISSON)
        generator = DecoyGenerator(config)
        
        txs = [{"id": i} for i in range(50)]
        result = generator._apply_timing_pattern(txs)
        
        times = [tx["scheduled_time"] for tx in result]
        # Times should be monotonically increasing
        self.assertEqual(times, sorted(times))


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience factory functions"""
    
    def test_create_trade_decoy(self):
        """Test trade decoy factory"""
        decoy = create_trade_decoy(1000.0, "BTC-USD")
        self.assertEqual(decoy.decoy_type, DecoyType.TRADE)
        self.assertEqual(decoy.symbol, "BTC-USD")
    
    def test_create_transfer_decoy(self):
        """Test transfer decoy factory"""
        decoy = create_transfer_decoy(500.0, "USDC")
        self.assertEqual(decoy.decoy_type, DecoyType.TRANSFER)
        self.assertEqual(decoy.symbol, "USDC")
    
    def test_create_approval_decoy(self):
        """Test approval decoy factory"""
        decoy = create_approval_decoy("DAI")
        self.assertEqual(decoy.decoy_type, DecoyType.APPROVAL)
        self.assertEqual(decoy.symbol, "DAI")


class TestIntegration(unittest.TestCase):
    """Integration tests for full workflows"""
    
    def test_full_lifecycle(self):
        """Test complete decoy lifecycle"""
        config = DecoyConfig(include_failures=True, failure_rate=0.0)
        generator = DecoyGenerator(config)
        
        # Generate decoys
        real_txs = [{"tx_id": f"r{i}", "amount": 1000.0, "symbol": "ETH"} for i in range(3)]
        decoys = generator.generate_decoy_batch(real_txs)
        
        # Queue all
        for decoy in decoys:
            generator.lifecycle.queue(decoy.decoy_id)
        
        # Execute all
        results = []
        for decoy in decoys:
            result = generator.execute_decoy(decoy.decoy_id)
            results.append(result)
        
        # Verify
        self.assertEqual(len(results), len(decoys))
        self.assertTrue(all(r["status"] == "success" for r in results))
    
    def test_end_to_end_mixing(self):
        """Test end-to-end mixing workflow"""
        config = DecoyConfig(
            ratio=1.5,
            size_range=(0.5, 1.5),
            decoy_types=[DecoyType.TRADE, DecoyType.TRANSFER],
            frequency=FrequencyPattern.RANDOM
        )
        generator = DecoyGenerator(config)
        
        # Real transactions
        real_txs = [
            {"tx_id": f"trade_{i}", "amount": random.uniform(100, 10000), "symbol": "ETH-USD"}
            for i in range(5)
        ]
        
        # Mix with decoys
        mixed = generator.mix_decoys_with_real(real_txs)
        
        # Verify structure
        self.assertGreater(len(mixed), len(real_txs))
        decoy_count = sum(1 for tx in mixed if tx.get("is_decoy"))
        real_count = sum(1 for tx in mixed if not tx.get("is_decoy"))
        self.assertEqual(real_count, len(real_txs))
        self.assertGreater(decoy_count, 0)
    
    def test_statistics(self):
        """Test statistics gathering"""
        generator = DecoyGenerator(DecoyConfig(ratio=2.0))
        
        # Generate some decoys
        real_txs = [{"tx_id": f"r{i}", "amount": 1000.0} for i in range(5)]
        generator.generate_decoy_batch(real_txs)
        
        # Get stats
        stats = generator.get_statistics()
        self.assertEqual(stats["active_count"], 10)  # 5 * 2.0 = 10
        self.assertEqual(stats["config"]["ratio"], 2.0)


if __name__ == "__main__":
    unittest.main()
