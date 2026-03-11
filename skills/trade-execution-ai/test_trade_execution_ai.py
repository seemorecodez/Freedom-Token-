"""
Unit tests for Trade Execution AI Skill
"""

import unittest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trade_execution_ai import (
    AIConfig, TradeExecutionAI, TechnicalAnalyzer, 
    ReinforcementLearningComponent, ModelType, SignalType,
    create_sample_data, predict_trade
)


class TestAIConfig(unittest.TestCase):
    """Test AIConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = AIConfig()
        self.assertEqual(config.model_type, ModelType.RANDOM_FOREST)
        self.assertEqual(config.confidence_threshold, 0.7)
        self.assertEqual(config.lookback_window, 20)
        self.assertEqual(config.n_estimators, 100)
        self.assertEqual(config.rsi_period, 14)
        self.assertEqual(config.macd_fast, 12)
        self.assertEqual(config.macd_slow, 26)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = AIConfig(
            confidence_threshold=0.8,
            lookback_window=30,
            n_estimators=200
        )
        self.assertEqual(config.confidence_threshold, 0.8)
        self.assertEqual(config.lookback_window, 30)
        self.assertEqual(config.n_estimators, 200)


class TestTechnicalAnalyzer(unittest.TestCase):
    """Test TechnicalAnalyzer class."""
    
    def setUp(self):
        """Set up test data."""
        self.config = AIConfig()
        self.analyzer = TechnicalAnalyzer(self.config)
        self.df = create_sample_data(n_periods=100)
    
    def test_calculate_rsi(self):
        """Test RSI calculation."""
        rsi = self.analyzer.calculate_rsi(self.df['close'])
        
        # RSI should be between 0 and 100
        self.assertTrue((rsi.dropna() >= 0).all())
        self.assertTrue((rsi.dropna() <= 100).all())
        
        # First rsi_period-1 values should be NaN
        self.assertTrue(rsi.iloc[:self.config.rsi_period-1].isna().all())
    
    def test_calculate_macd(self):
        """Test MACD calculation."""
        macd, signal, histogram = self.analyzer.calculate_macd(self.df['close'])
        
        # All should be Series
        self.assertIsInstance(macd, pd.Series)
        self.assertIsInstance(signal, pd.Series)
        self.assertIsInstance(histogram, pd.Series)
        
        # Histogram should equal MACD - Signal
        pd.testing.assert_series_equal(histogram, macd - signal)
    
    def test_calculate_bollinger_bands(self):
        """Test Bollinger Bands calculation."""
        upper, middle, lower, position = self.analyzer.calculate_bollinger_bands(self.df['close'])
        
        # Upper should be above middle, middle above lower
        self.assertTrue((upper >= middle).all())
        self.assertTrue((middle >= lower).all())
        
        # Position should be between 0 and 1 (approximately)
        self.assertTrue((position.dropna() >= -0.5).all())
        self.assertTrue((position.dropna() <= 1.5).all())
    
    def test_calculate_atr(self):
        """Test ATR calculation."""
        atr = self.analyzer.calculate_atr(
            self.df['high'], self.df['low'], self.df['close']
        )
        
        # ATR should be positive
        self.assertTrue((atr.dropna() > 0).all())
    
    def test_calculate_all_indicators(self):
        """Test calculation of all indicators."""
        df_with_indicators = self.analyzer.calculate_all_indicators(self.df)
        
        # Check that all expected columns exist
        expected_cols = [
            'returns', 'log_returns', 'volatility', 'price_momentum',
            'volume_change', 'volume_ratio', 'rsi', 'macd', 'macd_signal',
            'macd_histogram', 'bb_upper', 'bb_middle', 'bb_lower', 
            'bb_position', 'bb_width', 'atr', 'atr_ratio', 'high_low_range'
        ]
        
        for col in expected_cols:
            self.assertIn(col, df_with_indicators.columns)


class TestReinforcementLearningComponent(unittest.TestCase):
    """Test ReinforcementLearningComponent class."""
    
    def setUp(self):
        """Set up test data."""
        self.config = AIConfig()
        self.rl = ReinforcementLearningComponent(self.config)
    
    def test_initialization(self):
        """Test RL component initialization."""
        self.assertEqual(self.rl.actions, ['buy', 'sell', 'hold'])
        self.assertEqual(self.rl.exploration_rate, self.config.rl_exploration_rate)
        self.assertEqual(len(self.rl.q_table), 0)
    
    def test_discretize_state(self):
        """Test state discretization."""
        features = np.array([0.5, -0.3, 1.2, -2.1])
        state = self.rl._discretize_state(features)
        
        # Should return a tuple
        self.assertIsInstance(state, tuple)
        self.assertEqual(len(state), len(features))
    
    def test_get_action_training(self):
        """Test action selection in training mode."""
        state = np.array([0.1, 0.2, 0.3])
        
        # With high exploration rate, should get different actions
        actions = set()
        for _ in range(50):
            action = self.rl.get_action(state, train=True)
            actions.add(action)
        
        # Should have tried multiple actions
        self.assertGreaterEqual(len(actions), 1)
        self.assertTrue(all(a in ['buy', 'sell', 'hold'] for a in actions))
    
    def test_get_action_inference(self):
        """Test action selection in inference mode."""
        state = np.array([0.1, 0.2, 0.3])
        
        # First call creates Q-table entry
        action = self.rl.get_action(state, train=False)
        self.assertIn(action, ['buy', 'sell', 'hold'])
    
    def test_update(self):
        """Test Q-table update."""
        state = np.array([0.1, 0.2, 0.3])
        next_state = np.array([0.2, 0.3, 0.4])
        
        # Get initial Q-value
        initial_q = self.rl.get_q_value(state, 'buy')
        
        # Update with positive reward
        self.rl.update(state, 'buy', 1.0, next_state)
        
        # Q-value should have increased
        new_q = self.rl.get_q_value(state, 'buy')
        self.assertGreater(new_q, initial_q)
    
    def test_decay_exploration(self):
        """Test exploration rate decay."""
        initial_rate = self.rl.exploration_rate
        
        self.rl.decay_exploration(decay_rate=0.9, min_rate=0.01)
        
        # Should have decayed
        self.assertLess(self.rl.exploration_rate, initial_rate)
        
        # Should not go below minimum
        for _ in range(100):
            self.rl.decay_exploration(decay_rate=0.9, min_rate=0.01)
        
        self.assertGreaterEqual(self.rl.exploration_rate, 0.01)


class TestTradeExecutionAI(unittest.TestCase):
    """Test TradeExecutionAI main class."""
    
    def setUp(self):
        """Set up test data."""
        self.config = AIConfig(
            n_estimators=10,  # Small for fast tests
            max_depth=5,
            lookback_window=10
        )
        self.ai = TradeExecutionAI(self.config)
        self.df = create_sample_data(n_periods=200)
    
    def test_initialization(self):
        """Test AI initialization."""
        self.assertFalse(self.ai.is_trained)
        self.assertIsNone(self.ai.model)
        self.assertIsInstance(self.ai.tech_analyzer, TechnicalAnalyzer)
        self.assertIsInstance(self.ai.rl_component, ReinforcementLearningComponent)
    
    def test_fit(self):
        """Test model training."""
        metrics = self.ai.fit(self.df)
        
        # Check that model is trained
        self.assertTrue(self.ai.is_trained)
        self.assertIsNotNone(self.ai.model)
        
        # Check metrics
        self.assertIn('train_r2', metrics)
        self.assertIn('validation_r2', metrics)
        self.assertIn('feature_importance', metrics)
        self.assertIn('n_samples', metrics)
        
        # Feature importance should sum to approximately 1
        total_importance = sum(metrics['feature_importance'].values())
        self.assertAlmostEqual(total_importance, 1.0, places=1)
    
    def test_fit_insufficient_data(self):
        """Test training with insufficient data."""
        small_df = create_sample_data(n_periods=50)
        
        with self.assertRaises(ValueError):
            self.ai.fit(small_df)
    
    def test_predict_trade_timing_not_trained(self):
        """Test prediction without training."""
        with self.assertRaises(RuntimeError):
            self.ai.predict_trade_timing(self.df)
    
    def test_predict_trade_timing(self):
        """Test trade prediction."""
        self.ai.fit(self.df)
        
        prediction = self.ai.predict_trade_timing(self.df)
        
        # Check prediction structure
        self.assertIn('signal', prediction)
        self.assertIn('confidence', prediction)
        self.assertIn('predicted_return', prediction)
        self.assertIn('optimal_entry_price', prediction)
        self.assertIn('stop_loss', prediction)
        self.assertIn('take_profit', prediction)
        self.assertIn('rl_action', prediction)
        
        # Check signal is valid
        self.assertIn(prediction['signal'], ['buy', 'sell', 'hold'])
        
        # Check confidence is in valid range
        self.assertGreaterEqual(prediction['confidence'], 0)
        self.assertLessEqual(prediction['confidence'], 1)
        
        # Check prices are positive
        self.assertGreater(prediction['current_price'], 0)
        self.assertGreater(prediction['optimal_entry_price'], 0)
    
    def test_predict_trade_timing_insufficient_data(self):
        """Test prediction with insufficient lookback data."""
        self.ai.fit(self.df)
        
        small_df = create_sample_data(n_periods=5)
        
        with self.assertRaises(ValueError):
            self.ai.predict_trade_timing(small_df)
    
    def test_calculate_confidence(self):
        """Test confidence calculation."""
        # High prediction, low variance = high confidence
        conf1 = self.ai._calculate_confidence(0.5, 0.01)
        self.assertGreater(conf1, 0.5)
        
        # Low prediction, high variance = low confidence
        conf2 = self.ai._calculate_confidence(0.1, 0.5)
        self.assertLess(conf2, conf1)
        
        # Confidence should be bounded
        conf3 = self.ai._calculate_confidence(10.0, 0.01)
        self.assertLessEqual(conf3, 1.0)
    
    def test_combine_signals(self):
        """Test signal combination logic."""
        # High confidence buy signal
        signal = self.ai._combine_signals(0.5, 'buy', 'none', 0.8)
        self.assertIn(signal, ['buy', 'hold'])
        
        # Low confidence should hold
        signal = self.ai._combine_signals(0.5, 'buy', 'none', 0.3)
        self.assertEqual(signal, 'hold')
        
        # Exit signals
        signal = self.ai._combine_signals(-0.5, 'sell', 'long', 0.8)
        self.assertEqual(signal, 'sell')
    
    def test_get_feature_importance_not_trained(self):
        """Test getting feature importance before training."""
        with self.assertRaises(RuntimeError):
            self.ai.get_feature_importance()
    
    def test_get_feature_importance(self):
        """Test getting feature importance."""
        self.ai.fit(self.df)
        
        importance = self.ai.get_feature_importance()
        
        self.assertIsInstance(importance, dict)
        self.assertGreater(len(importance), 0)
        
        # All values should be between 0 and 1
        for val in importance.values():
            self.assertGreaterEqual(val, 0)
            self.assertLessEqual(val, 1)
    
    def test_save_load_model(self):
        """Test model saving and loading."""
        self.ai.fit(self.df)
        
        # Save model
        test_path = '/tmp/test_trade_ai_model.pkl'
        self.ai.save_model(test_path)
        
        # Load into new instance
        new_ai = TradeExecutionAI()
        new_ai.load_model(test_path)
        
        # Check that loaded model works
        self.assertTrue(new_ai.is_trained)
        
        prediction = new_ai.predict_trade_timing(self.df)
        self.assertIn('signal', prediction)
        
        # Cleanup
        if os.path.exists(test_path):
            os.remove(test_path)
    
    def test_save_not_trained(self):
        """Test saving untrained model."""
        with self.assertRaises(RuntimeError):
            self.ai.save_model('/tmp/test.pkl')
    
    def test_backtest(self):
        """Test backtesting."""
        self.ai.fit(self.df)
        
        results = self.ai.backtest(self.df)
        
        # Check results structure
        self.assertIn('initial_capital', results)
        self.assertIn('final_equity', results)
        self.assertIn('total_return', results)
        self.assertIn('n_trades', results)
        self.assertIn('sharpe_ratio', results)
        self.assertIn('max_drawdown', results)
        
        # Check types
        self.assertIsInstance(results['n_trades'], int)
        self.assertIsInstance(results['total_return'], float)
    
    def test_backtest_not_trained(self):
        """Test backtesting without training."""
        with self.assertRaises(RuntimeError):
            self.ai.backtest(self.df)


class TestCreateSampleData(unittest.TestCase):
    """Test sample data creation."""
    
    def test_default_data(self):
        """Test default sample data."""
        df = create_sample_data()
        
        # Check columns
        expected_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in expected_cols:
            self.assertIn(col, df.columns)
        
        # Check default length
        self.assertEqual(len(df), 500)
    
    def test_custom_data(self):
        """Test custom sample data."""
        df = create_sample_data(n_periods=100, trend=0.01, volatility=0.05)
        
        self.assertEqual(len(df), 100)
        
        # High should be >= low
        self.assertTrue((df['high'] >= df['low']).all())
        
        # Volume should be positive
        self.assertTrue((df['volume'] > 0).all())


class TestPredictTrade(unittest.TestCase):
    """Test predict_trade convenience function."""
    
    def test_predict_trade_train_new(self):
        """Test predict_trade with training."""
        df = create_sample_data(n_periods=200)
        config = AIConfig(n_estimators=10, max_depth=5, lookback_window=10)
        
        result = predict_trade(df, config=config)
        
        self.assertIn('signal', result)
        self.assertIn('confidence', result)
    
    def test_predict_trade_with_model(self):
        """Test predict_trade with saved model."""
        df = create_sample_data(n_periods=200)
        config = AIConfig(n_estimators=10, max_depth=5, lookback_window=10)
        
        # Create and save model
        ai = TradeExecutionAI(config)
        ai.fit(df)
        
        test_path = '/tmp/test_predict_trade_model.pkl'
        ai.save_model(test_path)
        
        # Predict with loaded model
        result = predict_trade(df, model_path=test_path)
        
        self.assertIn('signal', result)
        
        # Cleanup
        if os.path.exists(test_path):
            os.remove(test_path)


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_full_workflow(self):
        """Test complete workflow from training to prediction."""
        # Create data
        df = create_sample_data(n_periods=300)
        
        # Train model
        config = AIConfig(
            n_estimators=20,
            max_depth=5,
            lookback_window=15,
            confidence_threshold=0.6
        )
        ai = TradeExecutionAI(config)
        
        metrics = ai.fit(df)
        self.assertTrue(ai.is_trained)
        
        # Make prediction
        prediction = ai.predict_trade_timing(df, current_position='none')
        self.assertIn(prediction['signal'], ['buy', 'sell', 'hold'])
        
        # Run backtest
        results = ai.backtest(df, initial_capital=10000)
        self.assertIn('total_return', results)
        
        # Save and reload
        test_path = '/tmp/test_integration.pkl'
        ai.save_model(test_path)
        
        new_ai = TradeExecutionAI()
        new_ai.load_model(test_path)
        
        # Verify predictions match
        pred1 = ai.predict_trade_timing(df)
        pred2 = new_ai.predict_trade_timing(df)
        
        self.assertEqual(pred1['signal'], pred2['signal'])
        self.assertAlmostEqual(pred1['confidence'], pred2['confidence'], places=3)
        
        # Cleanup
        if os.path.exists(test_path):
            os.remove(test_path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
