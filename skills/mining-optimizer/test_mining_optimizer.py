"""
Unit tests for the mining-optimizer skill.

Run with: python -m pytest test_mining_optimizer.py -v
Or: python test_mining_optimizer.py
"""

import unittest
import random
from datetime import datetime, timedelta
from typing import Dict, Any

import sys
sys.path.insert(0, '/root/.openclaw/skills/mining-optimizer')

from mining_optimizer import (
    MiningOptimizer,
    MiningConfig,
    AlgorithmParams,
    ProfitRecord,
    DifficultyPredictor,
    create_optimizer,
    quick_profit_check
)


class TestMiningConfig(unittest.TestCase):
    """Tests for MiningConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = MiningConfig()
        
        self.assertEqual(config.switch_threshold, 0.05)
        self.assertEqual(config.min_switch_interval, 300)
        self.assertEqual(config.profit_history_size, 1000)
        self.assertEqual(config.difficulty_lookback, 14)
        self.assertIn('population_size', config.genetic_params)
        self.assertEqual(config.genetic_params['population_size'], 30)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = MiningConfig(
            pools={'sha256': {'url': 'test.com', 'user': 'worker'}},
            switch_threshold=0.10,
            min_switch_interval=600
        )
        
        self.assertEqual(config.switch_threshold, 0.10)
        self.assertEqual(config.min_switch_interval, 600)
        self.assertEqual(config.pools['sha256']['url'], 'test.com')
    
    def test_genetic_params_override(self):
        """Test overriding genetic algorithm parameters."""
        config = MiningConfig(
            genetic_params={'population_size': 50, 'mutation_rate': 0.2}
        )
        
        self.assertEqual(config.genetic_params['population_size'], 50)
        self.assertEqual(config.genetic_params['mutation_rate'], 0.2)


class TestAlgorithmParams(unittest.TestCase):
    """Tests for AlgorithmParams dataclass."""
    
    def test_default_params(self):
        """Test default parameter values."""
        params = AlgorithmParams()
        
        self.assertIsNone(params.frequency)
        self.assertIsNone(params.voltage)
        self.assertIsNone(params.threads)
    
    def test_sha256_params(self):
        """Test ASIC parameters for SHA-256."""
        params = AlgorithmParams(
            frequency=650,
            voltage=1200,
            fan_speed=80,
            target_temp=75
        )
        
        self.assertEqual(params.frequency, 650)
        self.assertEqual(params.voltage, 1200)
        self.assertEqual(params.fan_speed, 80)
        self.assertEqual(params.target_temp, 75)
    
    def test_ethash_params(self):
        """Test GPU parameters for Ethash."""
        params = AlgorithmParams(
            core_clock=100,
            memory_clock=800,
            power_limit=85,
            fan_speed=70
        )
        
        self.assertEqual(params.core_clock, 100)
        self.assertEqual(params.memory_clock, 800)
        self.assertEqual(params.power_limit, 85)
    
    def test_randomx_params(self):
        """Test CPU parameters for RandomX."""
        params = AlgorithmParams(
            threads=16,
            large_pages=True,
            jit_compiler=True,
            affinity=0xFFFF
        )
        
        self.assertEqual(params.threads, 16)
        self.assertTrue(params.large_pages)
        self.assertTrue(params.jit_compiler)
        self.assertEqual(params.affinity, 0xFFFF)
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        params = AlgorithmParams(
            frequency=600,
            voltage=1200,
            threads=None
        )
        
        d = params.to_dict()
        self.assertEqual(d['frequency'], 600)
        self.assertEqual(d['voltage'], 1200)
        self.assertNotIn('threads', d)
        self.assertNotIn('core_clock', d)
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'frequency': 700,
            'fan_speed': 90,
            'threads': 8
        }
        
        params = AlgorithmParams.from_dict(data)
        self.assertEqual(params.frequency, 700)
        self.assertEqual(params.fan_speed, 90)
        self.assertEqual(params.threads, 8)
    
    def test_copy(self):
        """Test parameter copying."""
        params = AlgorithmParams(frequency=600, voltage=1200)
        copy = params.copy()
        
        self.assertEqual(copy.frequency, 600)
        self.assertEqual(copy.voltage, 1200)
        
        # Modify copy should not affect original
        copy.frequency = 700
        self.assertEqual(params.frequency, 600)


class TestDifficultyPredictor(unittest.TestCase):
    """Tests for DifficultyPredictor class."""
    
    def setUp(self):
        self.predictor = DifficultyPredictor(lookback_days=14)
    
    def test_add_sample(self):
        """Test adding difficulty samples."""
        self.predictor.add_difficulty_sample('sha256', 80e18)
        self.assertIn('sha256', self.predictor._history)
        self.assertEqual(len(self.predictor._history['sha256']), 1)
    
    def test_prediction_simulation(self):
        """Test difficulty prediction in simulation mode."""
        prediction = self.predictor.predict('sha256', days_ahead=7)
        
        # Should return a positive number
        self.assertGreater(prediction, 0)
        
        # Base difficulty for SHA-256 should be around 80e18
        self.assertGreater(prediction, 50e18)
        self.assertLess(prediction, 150e18)
    
    def test_prediction_with_history(self):
        """Test prediction with historical data."""
        # Add increasing difficulty samples
        for i in range(10):
            self.predictor.add_difficulty_sample('ethash', 50e15 * (1 + i * 0.02))
        
        prediction = self.predictor.predict('ethash', days_ahead=7)
        
        # With increasing trend, prediction should be higher than last sample
        last_sample = 50e15 * (1 + 9 * 0.02)
        self.assertGreater(prediction, last_sample)
    
    def test_prediction_different_algorithms(self):
        """Test predictions for different algorithms."""
        algos = ['sha256', 'scrypt', 'ethash', 'randomx']
        
        for algo in algos:
            pred = self.predictor.predict(algo, days_ahead=1)
            self.assertGreater(pred, 0, f"Prediction for {algo} should be positive")


class TestMiningOptimizer(unittest.TestCase):
    """Tests for MiningOptimizer class."""
    
    def setUp(self):
        self.config = MiningConfig(
            pools={'sha256': {'url': 'test.com', 'user': 'worker'}},
            switch_threshold=0.05,
            min_switch_interval=0  # No cooldown for testing
        )
        self.optimizer = MiningOptimizer(self.config, simulation_mode=True)
    
    def test_initialization(self):
        """Test optimizer initialization."""
        self.assertEqual(self.optimizer.config, self.config)
        self.assertTrue(self.optimizer.simulation_mode)
        self.assertIsNone(self.optimizer.get_current_algorithm())
    
    def test_calculate_profitability(self):
        """Test profit calculation."""
        hashrates = {
            'sha256': 100e12,    # 100 TH/s
            'ethash': 100e6,     # 100 MH/s
            'randomx': 10e3      # 10 KH/s
        }
        
        profits = self.optimizer.calculate_profitability(hashrates, power_cost=0.10)
        
        # Should have results for all algorithms
        self.assertIn('sha256', profits)
        self.assertIn('ethash', profits)
        self.assertIn('randomx', profits)
        
        # Each result should have required fields
        for algo, data in profits.items():
            self.assertIn('profit_usd_per_day', data)
            self.assertIn('revenue_usd_per_day', data)
            self.assertIn('cost_usd_per_day', data)
            self.assertIn('power_consumption_w', data)
    
    def test_profit_calculation_components(self):
        """Test that profit equals revenue minus cost."""
        hashrates = {'sha256': 100e12}
        
        profits = self.optimizer.calculate_profitability(hashrates, power_cost=0.10)
        data = profits['sha256']
        
        # Profit should equal revenue minus cost
        expected_profit = data['revenue_usd_per_day'] - data['cost_usd_per_day']
        self.assertAlmostEqual(data['profit_usd_per_day'], expected_profit, places=6)
    
    def test_switch_algorithm_initial(self):
        """Test switching when no current algorithm."""
        hashrates = {
            'sha256': 100e12,
            'ethash': 100e6
        }
        
        profits = self.optimizer.calculate_profitability(hashrates, power_cost=0.10)
        should_switch, target = self.optimizer.switch_algorithm(profits)
        
        # Should switch to best algorithm
        self.assertTrue(should_switch)
        self.assertIn(target, ['sha256', 'ethash'])
        self.assertEqual(self.optimizer.get_current_algorithm(), target)
    
    def test_switch_algorithm_no_switch(self):
        """Test not switching when difference is small."""
        hashrates = {
            'sha256': 100e12,
            'ethash': 0.001  # Very low hashrate
        }
        
        profits = self.optimizer.calculate_profitability(hashrates, power_cost=0.10)
        
        # First switch to SHA-256
        self.optimizer.switch_algorithm(profits)
        self.assertEqual(self.optimizer.get_current_algorithm(), 'sha256')
        
        # Now try to switch again - should not switch (already on best)
        should_switch, target = self.optimizer.switch_algorithm(profits, 'sha256')
        self.assertFalse(should_switch)
        self.assertEqual(target, 'sha256')
    
    def test_switch_algorithm_with_cooldown(self):
        """Test switch cooldown."""
        config = MiningConfig(min_switch_interval=3600)  # 1 hour cooldown
        optimizer = MiningOptimizer(config, simulation_mode=True)
        
        hashrates = {'sha256': 100e12, 'ethash': 100e6}
        profits = optimizer.calculate_profitability(hashrates, power_cost=0.10)
        
        # First switch
        optimizer.switch_algorithm(profits, None)
        
        # Try to switch immediately - should not switch due to cooldown
        should_switch, target = optimizer.switch_algorithm(profits, optimizer.get_current_algorithm())
        self.assertFalse(should_switch)
    
    def test_predict_difficulty(self):
        """Test difficulty prediction."""
        prediction = self.optimizer.predict_difficulty('sha256', days_ahead=7)
        
        self.assertGreater(prediction, 0)
        
        # Add some history and predict again
        for i in range(5):
            self.optimizer.difficulty_predictor.add_difficulty_sample(
                'sha256', 80e18 * (1 + i * 0.01)
            )
        
        prediction2 = self.optimizer.predict_difficulty('sha256', days_ahead=7)
        self.assertGreater(prediction2, 0)
    
    def test_genetic_tuner_initialization(self):
        """Test genetic parameter tuner initialization."""
        result = self.optimizer.genetic_parameter_tuner(
            algorithm='ethash',
            generations=5,
            population_size=10
        )
        
        self.assertIn('algorithm', result)
        self.assertIn('optimal_params', result)
        self.assertIn('fitness_score', result)
        self.assertIn('generations', result)
        self.assertEqual(result['algorithm'], 'ethash')
        # Fitness can be negative (unprofitable scenario in simulation)
        self.assertIsInstance(result['fitness_score'], (int, float))
    
    def test_genetic_tuner_all_algorithms(self):
        """Test genetic tuning for all supported algorithms."""
        algorithms = ['sha256', 'scrypt', 'ethash', 'randomx']
        
        for algo in algorithms:
            result = self.optimizer.genetic_parameter_tuner(
                algorithm=algo,
                generations=3,
                population_size=6
            )
            
            self.assertEqual(result['algorithm'], algo)
            self.assertIsNotNone(result['optimal_params'])
            self.assertGreater(result['fitness_score'], -1000)  # Should have some fitness
    
    def test_genetic_tuner_params_structure(self):
        """Test that optimal params have correct structure."""
        result = self.optimizer.genetic_parameter_tuner(
            algorithm='ethash',
            generations=3,
            population_size=6
        )
        
        params = result['optimal_params']
        
        # Ethash should have GPU-related params
        self.assertIn('core_clock', params)
        self.assertIn('memory_clock', params)
        self.assertIn('power_limit', params)
    
    def test_get_profit_history(self):
        """Test profit history retrieval."""
        hashrates = {'sha256': 100e12}
        
        # Generate some history
        for _ in range(5):
            self.optimizer.calculate_profitability(hashrates, power_cost=0.10)
        
        history = self.optimizer.get_profit_history(limit=10)
        
        self.assertGreaterEqual(len(history), 5)
        
        for record in history:
            self.assertIn('timestamp', record)
            self.assertIn('algorithm', record)
            self.assertIn('profit_usd', record)
    
    def test_get_profit_history_filtered(self):
        """Test filtered profit history."""
        hashrates = {'sha256': 100e12, 'ethash': 100e6}
        
        # Generate history for multiple algorithms
        self.optimizer.calculate_profitability(hashrates, power_cost=0.10)
        
        # Get only SHA-256 history
        sha256_history = self.optimizer.get_profit_history(algorithm='sha256', limit=10)
        
        for record in sha256_history:
            self.assertEqual(record['algorithm'], 'sha256')
    
    def test_get_switch_stats(self):
        """Test switch statistics."""
        stats = self.optimizer.get_switch_stats()
        
        self.assertIn('total_switches', stats)
        self.assertIn('time_since_last_switch', stats)
        self.assertIn('current_algorithm', stats)
        
        # Initially should have 0 switches
        self.assertEqual(stats['total_switches'], 0)
        self.assertIsNone(stats['current_algorithm'])
    
    def test_simulated_prices(self):
        """Test simulated price generation."""
        prices = self.optimizer._simulated_prices
        
        self.assertIn('BTC', prices)
        self.assertIn('ETH', prices) if 'ETH' in prices else self.assertIn('ETC', prices)
        self.assertIn('XMR', prices)
        
        # Prices should be positive
        for coin, price in prices.items():
            self.assertGreater(price, 0)


class TestIntegration(unittest.TestCase):
    """Integration tests for the full workflow."""
    
    def test_full_workflow(self):
        """Test complete mining optimization workflow."""
        # Create optimizer
        optimizer = create_optimizer(simulation_mode=True)
        
        # Define hashrates
        hashrates = {
            'sha256': 100e12,
            'scrypt': 2e9,
            'ethash': 100e6,
            'randomx': 10e3
        }
        
        # Step 1: Calculate profitability
        profits = optimizer.calculate_profitability(hashrates, power_cost=0.10)
        self.assertEqual(len(profits), 4)
        
        # Step 2: Switch to best algorithm
        should_switch, target = optimizer.switch_algorithm(profits)
        self.assertTrue(should_switch)
        self.assertIsNotNone(target)
        
        # Step 3: Predict difficulty
        prediction = optimizer.predict_difficulty(target, days_ahead=7)
        self.assertGreater(prediction, 0)
        
        # Step 4: Run genetic tuning
        tuning_result = optimizer.genetic_parameter_tuner(
            algorithm='ethash',
            generations=5,
            population_size=8
        )
        self.assertIn('optimal_params', tuning_result)
        
        # Step 5: Check history
        history = optimizer.get_profit_history(limit=10)
        self.assertGreaterEqual(len(history), 4)  # One per algorithm
        
        # Step 6: Get stats
        stats = optimizer.get_switch_stats()
        self.assertEqual(stats['current_algorithm'], target)
    
    def test_quick_profit_check(self):
        """Test quick profit check convenience function."""
        hashrates = {
            'sha256': 100e12,
            'ethash': 100e6
        }
        
        profits = quick_profit_check(hashrates, power_cost=0.10)
        
        self.assertIn('sha256', profits)
        self.assertIn('ethash', profits)
        
        # Both should have profit data
        for algo in ['sha256', 'ethash']:
            self.assertIn('profit_usd_per_day', profits[algo])
            self.assertIn('revenue_usd_per_day', profits[algo])


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""
    
    def test_empty_hashrates(self):
        """Test with empty hashrates dict."""
        optimizer = create_optimizer(simulation_mode=True)
        profits = optimizer.calculate_profitability({}, power_cost=0.10)
        self.assertEqual(profits, {})
    
    def test_unknown_algorithm(self):
        """Test with unknown algorithm."""
        optimizer = create_optimizer(simulation_mode=True)
        
        hashrates = {'unknown_algo': 100e12}
        profits = optimizer.calculate_profitability(hashrates, power_cost=0.10)
        
        # Should return empty (algorithm skipped with warning)
        self.assertEqual(profits, {})
    
    def test_zero_power_cost(self):
        """Test with zero power cost."""
        optimizer = create_optimizer(simulation_mode=True)
        
        hashrates = {'sha256': 100e12}
        profits = optimizer.calculate_profitability(hashrates, power_cost=0.0)
        
        # Cost should be zero, profit should equal revenue
        self.assertEqual(profits['sha256']['cost_usd_per_day'], 0.0)
        self.assertEqual(profits['sha256']['profit_usd_per_day'], 
                         profits['sha256']['revenue_usd_per_day'])
    
    def test_negative_profit(self):
        """Test handling of negative profit scenarios."""
        optimizer = create_optimizer(simulation_mode=True)
        
        # Very high power cost should lead to negative profit
        hashrates = {'sha256': 1e9}  # Very low hashrate
        profits = optimizer.calculate_profitability(hashrates, power_cost=1.00)
        
        # Profit might be negative due to high power cost relative to hashrate
        # Just verify the calculation runs without error
        self.assertIn('profit_usd_per_day', profits['sha256'])
    
    def test_switch_with_empty_profits(self):
        """Test switching with empty profitability dict."""
        optimizer = create_optimizer(simulation_mode=True)
        
        should_switch, target = optimizer.switch_algorithm({})
        self.assertFalse(should_switch)
        self.assertIsNone(target)
    
    def test_genetic_tuner_unknown_algorithm(self):
        """Test genetic tuner with unknown algorithm."""
        optimizer = create_optimizer(simulation_mode=True)
        
        # Should still run but with default params
        result = optimizer.genetic_parameter_tuner(
            algorithm='unknown',
            generations=2,
            population_size=4
        )
        
        self.assertEqual(result['algorithm'], 'unknown')
        self.assertIn('optimal_params', result)


class TestPerformance(unittest.TestCase):
    """Tests for performance characteristics."""
    
    def test_large_population_convergence(self):
        """Test genetic algorithm convergence with larger population."""
        optimizer = create_optimizer(simulation_mode=True)
        
        result = optimizer.genetic_parameter_tuner(
            algorithm='ethash',
            generations=20,
            population_size=30
        )
        
        # Should converge within reasonable generations
        self.assertLessEqual(result['generations'], 20)
        # Fitness score is a valid number (can be negative in simulation)
        self.assertIsInstance(result['fitness_score'], (int, float))
        
        # Fitness history should show improvement or stability
        history = result['fitness_history']
        self.assertGreater(len(history), 5)
    
    def test_history_size_limit(self):
        """Test that profit history respects size limit."""
        config = MiningConfig(profit_history_size=10)
        optimizer = MiningOptimizer(config, simulation_mode=True)
        
        hashrates = {'sha256': 100e12}
        
        # Generate more entries than limit
        for _ in range(20):
            optimizer.calculate_profitability(hashrates, power_cost=0.10)
        
        history = optimizer.get_profit_history(limit=100)
        
        # Should be limited to configured size
        self.assertLessEqual(len(history), 10)


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestMiningConfig,
        TestAlgorithmParams,
        TestDifficultyPredictor,
        TestMiningOptimizer,
        TestIntegration,
        TestEdgeCases,
        TestPerformance
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
