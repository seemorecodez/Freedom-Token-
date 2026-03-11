"""
Unit tests for Temporal Jitter skill

Tests the delay generation algorithms and configuration options.
"""

import unittest
import time
from temporal_jitter import (
    JitterConfig,
    DistributionType,
    StealthLevel,
    apply_jitter,
    apply_jitter_sequence,
    sleep_with_jitter,
    calculate_total_time,
    quick_jitter,
    stealth_jitter,
    STEALTH_DELAYS
)


class TestJitterConfig(unittest.TestCase):
    """Test JitterConfig dataclass"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = JitterConfig()
        self.assertEqual(config.min_delay, 1.0)
        self.assertEqual(config.max_delay, 60.0)
        self.assertEqual(config.distribution, DistributionType.UNIFORM)
        self.assertIsNone(config.stealth_level)
    
    def test_custom_config(self):
        """Test custom configuration values"""
        config = JitterConfig(
            min_delay=5.0,
            max_delay=30.0,
            distribution=DistributionType.GAUSSIAN
        )
        self.assertEqual(config.min_delay, 5.0)
        self.assertEqual(config.max_delay, 30.0)
        self.assertEqual(config.distribution, DistributionType.GAUSSIAN)
    
    def test_stealth_level_low(self):
        """Test LOW stealth level preset"""
        config = JitterConfig(stealth_level=StealthLevel.LOW)
        self.assertEqual(config.min_delay, 10.0)
        self.assertEqual(config.max_delay, 30.0)
    
    def test_stealth_level_medium(self):
        """Test MEDIUM stealth level preset"""
        config = JitterConfig(stealth_level=StealthLevel.MEDIUM)
        self.assertEqual(config.min_delay, 30.0)
        self.assertEqual(config.max_delay, 120.0)
    
    def test_stealth_level_high(self):
        """Test HIGH stealth level preset"""
        config = JitterConfig(stealth_level=StealthLevel.HIGH)
        self.assertEqual(config.min_delay, 30.0)
        self.assertEqual(config.max_delay, 300.0)
    
    def test_stealth_level_paranoid(self):
        """Test PARANOID stealth level preset"""
        config = JitterConfig(stealth_level=StealthLevel.PARANOID)
        self.assertEqual(config.min_delay, 1.0)
        self.assertEqual(config.max_delay, 600.0)
    
    def test_all_stealth_levels_defined(self):
        """Test that all stealth levels have delay ranges"""
        for level in StealthLevel:
            self.assertIn(level, STEALTH_DELAYS)
            min_d, max_d = STEALTH_DELAYS[level]
            self.assertLess(min_d, max_d)


class TestApplyJitter(unittest.TestCase):
    """Test apply_jitter function"""
    
    def test_uniform_distribution_range(self):
        """Test uniform distribution stays within bounds"""
        config = JitterConfig(
            min_delay=10.0,
            max_delay=20.0,
            distribution=DistributionType.UNIFORM
        )
        
        # Sample many times to check bounds
        for _ in range(100):
            delay = apply_jitter(config)
            self.assertGreaterEqual(delay, 10.0)
            self.assertLessEqual(delay, 20.0)
    
    def test_exponential_distribution_range(self):
        """Test exponential distribution stays within bounds"""
        config = JitterConfig(
            min_delay=5.0,
            max_delay=15.0,
            distribution=DistributionType.EXPONENTIAL
        )
        
        for _ in range(100):
            delay = apply_jitter(config)
            self.assertGreaterEqual(delay, 5.0)
            self.assertLessEqual(delay, 15.0)
    
    def test_gaussian_distribution_range(self):
        """Test gaussian distribution stays within bounds"""
        config = JitterConfig(
            min_delay=10.0,
            max_delay=30.0,
            distribution=DistributionType.GAUSSIAN
        )
        
        for _ in range(100):
            delay = apply_jitter(config)
            self.assertGreaterEqual(delay, 10.0)
            self.assertLessEqual(delay, 30.0)
    
    def test_invalid_range(self):
        """Test that min > max raises error"""
        config = JitterConfig(min_delay=50.0, max_delay=10.0)
        with self.assertRaises(ValueError):
            apply_jitter(config)
    
    def test_zero_range(self):
        """Test that min == max returns that value"""
        config = JitterConfig(min_delay=5.0, max_delay=5.0)
        for _ in range(10):
            delay = apply_jitter(config)
            self.assertEqual(delay, 5.0)
    
    def test_all_distributions_produce_float(self):
        """Test all distributions return float values"""
        for dist in DistributionType:
            config = JitterConfig(
                min_delay=1.0,
                max_delay=10.0,
                distribution=dist
            )
            delay = apply_jitter(config)
            self.assertIsInstance(delay, float)


class TestApplyJitterSequence(unittest.TestCase):
    """Test apply_jitter_sequence function"""
    
    def test_sequence_length(self):
        """Test sequence has correct length"""
        config = JitterConfig(min_delay=1.0, max_delay=5.0)
        
        delays = apply_jitter_sequence(5, config)
        self.assertEqual(len(delays), 5)
        
        delays = apply_jitter_sequence(0, config)
        self.assertEqual(len(delays), 0)
    
    def test_first_immediate(self):
        """Test first delay is 0 when first_immediate=True"""
        config = JitterConfig(min_delay=5.0, max_delay=10.0)
        delays = apply_jitter_sequence(5, config, first_immediate=True)
        
        self.assertEqual(delays[0], 0.0)
        # Others should be non-zero
        for d in delays[1:]:
            self.assertGreater(d, 0)
    
    def test_first_not_immediate(self):
        """Test first delay is non-zero when first_immediate=False"""
        config = JitterConfig(min_delay=5.0, max_delay=10.0)
        delays = apply_jitter_sequence(5, config, first_immediate=False)
        
        for d in delays:
            self.assertGreater(d, 0)
    
    def test_negative_num_delays(self):
        """Test negative num_delays raises error"""
        config = JitterConfig()
        with self.assertRaises(ValueError):
            apply_jitter_sequence(-1, config)
    
    def test_single_delay(self):
        """Test sequence with single delay"""
        config = JitterConfig(min_delay=5.0, max_delay=10.0)
        
        # With first_immediate, single delay is 0
        delays = apply_jitter_sequence(1, config, first_immediate=True)
        self.assertEqual(len(delays), 1)
        self.assertEqual(delays[0], 0.0)
        
        # Without first_immediate, single delay is non-zero
        delays = apply_jitter_sequence(1, config, first_immediate=False)
        self.assertEqual(len(delays), 1)
        self.assertGreater(delays[0], 0)


class TestCalculateTotalTime(unittest.TestCase):
    """Test calculate_total_time function"""
    
    def test_basic_calculation(self):
        """Test basic timing calculation"""
        config = JitterConfig(min_delay=10.0, max_delay=20.0)
        stats = calculate_total_time(5, config, first_immediate=True)
        
        self.assertEqual(stats["num_operations"], 5)
        self.assertEqual(stats["num_delays"], 4)  # 5 ops, first immediate
        self.assertEqual(stats["min_seconds"], 40.0)  # 4 * 10
        self.assertEqual(stats["max_seconds"], 80.0)  # 4 * 20
        self.assertEqual(stats["expected_seconds"], 60.0)  # 4 * 15
    
    def test_no_first_immediate(self):
        """Test calculation without first_immediate"""
        config = JitterConfig(min_delay=10.0, max_delay=20.0)
        stats = calculate_total_time(3, config, first_immediate=False)
        
        self.assertEqual(stats["num_delays"], 3)
        self.assertEqual(stats["min_seconds"], 30.0)
    
    def test_stealth_level_in_stats(self):
        """Test stats include stealth level info"""
        config = JitterConfig(stealth_level=StealthLevel.HIGH)
        stats = calculate_total_time(10, config)
        
        self.assertEqual(stats["stealth_level"], "high")
        self.assertEqual(stats["distribution"], "uniform")


class TestQuickJitter(unittest.TestCase):
    """Test quick_jitter convenience function"""
    
    def test_uniform_quick(self):
        """Test quick uniform jitter"""
        for _ in range(20):
            delay = quick_jitter((10.0, 20.0), "uniform")
            self.assertGreaterEqual(delay, 10.0)
            self.assertLessEqual(delay, 20.0)
    
    def test_gaussian_quick(self):
        """Test quick gaussian jitter"""
        for _ in range(20):
            delay = quick_jitter((5.0, 15.0), "gaussian")
            self.assertGreaterEqual(delay, 5.0)
            self.assertLessEqual(delay, 15.0)
    
    def test_exponential_quick(self):
        """Test quick exponential jitter"""
        for _ in range(20):
            delay = quick_jitter((1.0, 10.0), "exponential")
            self.assertGreaterEqual(delay, 1.0)
            self.assertLessEqual(delay, 10.0)
    
    def test_invalid_distribution_defaults_uniform(self):
        """Test invalid distribution defaults to uniform"""
        delay = quick_jitter((5.0, 10.0), "invalid")
        self.assertGreaterEqual(delay, 5.0)
        self.assertLessEqual(delay, 10.0)


class TestStealthJitter(unittest.TestCase):
    """Test stealth_jitter convenience function"""
    
    def test_low_stealth(self):
        """Test low stealth level"""
        for _ in range(20):
            delay = stealth_jitter("low")
            self.assertGreaterEqual(delay, 10.0)
            self.assertLessEqual(delay, 30.0)
    
    def test_medium_stealth(self):
        """Test medium stealth level"""
        for _ in range(20):
            delay = stealth_jitter("medium")
            self.assertGreaterEqual(delay, 30.0)
            self.assertLessEqual(delay, 120.0)
    
    def test_high_stealth(self):
        """Test high stealth level"""
        for _ in range(20):
            delay = stealth_jitter("high")
            self.assertGreaterEqual(delay, 30.0)
            self.assertLessEqual(delay, 300.0)
    
    def test_paranoid_stealth(self):
        """Test paranoid stealth level"""
        for _ in range(20):
            delay = stealth_jitter("paranoid")
            self.assertGreaterEqual(delay, 1.0)
            self.assertLessEqual(delay, 600.0)
    
    def test_invalid_level_defaults_medium(self):
        """Test invalid level defaults to medium"""
        for _ in range(20):
            delay = stealth_jitter("invalid")
            self.assertGreaterEqual(delay, 30.0)
            self.assertLessEqual(delay, 120.0)
    
    def test_case_insensitive(self):
        """Test level names are case insensitive"""
        delay1 = stealth_jitter("HIGH")
        delay2 = stealth_jitter("high")
        # Both should be in HIGH range
        self.assertGreaterEqual(delay1, 30.0)
        self.assertLessEqual(delay1, 300.0)
        self.assertGreaterEqual(delay2, 30.0)
        self.assertLessEqual(delay2, 300.0)


class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def test_stealth_trader_use_case(self):
        """Test the typical stealth trader use case"""
        # Simulate chunking a trade and applying delays
        num_chunks = 5
        config = JitterConfig(stealth_level=StealthLevel.MEDIUM)
        
        # Get delays between chunks
        delays = apply_jitter_sequence(num_chunks, config, first_immediate=True)
        
        # First chunk immediate, rest have delays
        self.assertEqual(delays[0], 0.0)
        for d in delays[1:]:
            self.assertGreaterEqual(d, 30.0)
            self.assertLessEqual(d, 120.0)
        
        # Total expected time
        stats = calculate_total_time(num_chunks, config, first_immediate=True)
        self.assertGreater(stats["expected_seconds"], 0)
    
    def test_all_distributions_with_all_stealth_levels(self):
        """Test all distribution/stealth combinations work"""
        for stealth in StealthLevel:
            for dist in DistributionType:
                config = JitterConfig(
                    stealth_level=stealth,
                    distribution=dist
                )
                delays = apply_jitter_sequence(3, config)
                self.assertEqual(len(delays), 3)
                
                min_expected, max_expected = STEALTH_DELAYS[stealth]
                for d in delays[1:]:  # Skip first (may be 0)
                    self.assertGreaterEqual(d, min_expected)
                    self.assertLessEqual(d, max_expected)


class TestSleepWithJitter(unittest.TestCase):
    """Test sleep_with_jitter function"""
    
    def test_actual_sleep(self):
        """Test that sleep_with_jitter actually sleeps"""
        config = JitterConfig(min_delay=0.1, max_delay=0.2)
        
        start = time.time()
        delay = sleep_with_jitter(config)
        elapsed = time.time() - start
        
        # Should have slept approximately the delay
        self.assertGreaterEqual(elapsed, 0.09)  # Allow small margin
        self.assertGreaterEqual(delay, 0.1)
        self.assertLessEqual(delay, 0.2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
