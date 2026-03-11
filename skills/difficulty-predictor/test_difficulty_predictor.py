"""
Unit tests for the Difficulty Predictor skill.
"""

import unittest
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import json

# Import the module under test
from difficulty_predictor import (
    DifficultyPredictor,
    PredictorConfig,
    CoinType,
    ModelType,
    DataFetchError,
    InsufficientDataError,
    ModelTrainingError,
    PredictionError,
    predict_all_coins
)


class TestPredictorConfig(unittest.TestCase):
    """Tests for PredictorConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = PredictorConfig()
        self.assertEqual(config.coin, "BTC")
        self.assertEqual(config.model_type, "linear")
        self.assertEqual(config.prediction_horizon, 1)
        self.assertEqual(config.lookback_periods, 10)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = PredictorConfig(
            coin="LTC",
            model_type="linear",
            prediction_horizon=2,
            lookback_periods=15
        )
        self.assertEqual(config.coin, "LTC")
        self.assertEqual(config.model_type, "linear")
        self.assertEqual(config.prediction_horizon, 2)
        self.assertEqual(config.lookback_periods, 15)
    
    def test_case_normalization(self):
        """Test that coin and model_type are normalized."""
        config = PredictorConfig(coin="btc", model_type="linear")
        self.assertEqual(config.coin, "BTC")
        self.assertEqual(config.model_type, "linear")
    
    def test_invalid_coin(self):
        """Test that invalid coin raises ValueError."""
        with self.assertRaises(ValueError):
            PredictorConfig(coin="ETH")
    
    def test_invalid_model_type(self):
        """Test that invalid model_type raises ValueError."""
        with self.assertRaises(ValueError):
            PredictorConfig(model_type="random_forest")
    
    def test_lstm_fallback_without_tensorflow(self):
        """Test that LSTM falls back to linear when TensorFlow unavailable."""
        # When TensorFlow is not available, config accepts LSTM but warns
        # The actual fallback happens during training
        import difficulty_predictor as dp
        original_tf_available = dp.TENSORFLOW_AVAILABLE
        try:
            dp.TENSORFLOW_AVAILABLE = False
            config = PredictorConfig(model_type="lstm")
            # Config stores the requested type
            self.assertEqual(config.model_type, "lstm")
        finally:
            dp.TENSORFLOW_AVAILABLE = original_tf_available


class TestDifficultyPredictorInitialization(unittest.TestCase):
    """Tests for DifficultyPredictor initialization."""
    
    def test_init_with_config(self):
        """Test initialization with valid config."""
        config = PredictorConfig(coin="BTC")
        predictor = DifficultyPredictor(config)
        
        self.assertEqual(predictor.config, config)
        self.assertIsNone(predictor.data)
        self.assertIsNone(predictor.model)
        self.assertIsNone(predictor.scaler)
    
    def test_difficulty_params_exist(self):
        """Test that difficulty parameters exist for all coins."""
        for coin in ["BTC", "BCH", "LTC"]:
            config = PredictorConfig(coin=coin)
            predictor = DifficultyPredictor(config)
            
            self.assertIn(coin, predictor.DIFFICULTY_PARAMS)
            params = predictor.DIFFICULTY_PARAMS[coin]
            
            self.assertIn("interval_blocks", params)
            self.assertIn("target_time", params)
            self.assertIn("max_adjustment", params)


class TestDataFetching(unittest.TestCase):
    """Tests for data fetching functionality."""
    
    def setUp(self):
        self.config = PredictorConfig(coin="BTC")
        self.predictor = DifficultyPredictor(self.config)
    
    @patch('difficulty_predictor.requests.get')
    def test_fetch_btc_data_success(self, mock_get):
        """Test successful BTC data fetch from blockchain.info."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "values": [
                {"x": int((datetime.now() - timedelta(days=14)).timestamp()), "y": 80e15},
                {"x": int((datetime.now() - timedelta(days=7)).timestamp()), "y": 82e15},
                {"x": int(datetime.now().timestamp()), "y": 85e15}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        data = self.predictor.fetch_historical_difficulty(days=30)
        
        self.assertIsInstance(data, pd.DataFrame)
        self.assertEqual(len(data), 3)
        self.assertIn("timestamp", data.columns)
        self.assertIn("difficulty", data.columns)
        self.assertEqual(data["difficulty"].iloc[-1], 85e15)
    
    @patch('difficulty_predictor.requests.get')
    def test_fetch_btc_fallback_mempool(self, mock_get):
        """Test BTC data fetch fallback to mempool.space."""
        # First call fails
        mock_get.side_effect = [
            Exception("blockchain.info failed"),
            Mock(
                json=Mock(return_value={
                    "adjustments": [
                        {"timestamp": int((datetime.now() - timedelta(days=14)).timestamp()), 
                         "difficulty": 80e15, "height": 800000},
                        {"timestamp": int(datetime.now().timestamp()), 
                         "difficulty": 85e15, "height": 802016}
                    ]
                }),
                raise_for_status=Mock()
            )
        ]
        
        data = self.predictor.fetch_historical_difficulty(days=30)
        
        self.assertEqual(len(data), 2)
        self.assertEqual(mock_get.call_count, 2)
    
    @patch('difficulty_predictor.requests.get')
    def test_fetch_data_error(self, mock_get):
        """Test data fetch error handling."""
        mock_get.side_effect = Exception("Network error")
        
        with self.assertRaises(DataFetchError):
            self.predictor.fetch_historical_difficulty()
    
    @patch('difficulty_predictor.requests.get')
    def test_fetch_bch_data(self, mock_get):
        """Test BCH data fetch."""
        config = PredictorConfig(coin="BCH")
        predictor = DifficultyPredictor(config)
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"date": (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d"), 
                 "difficulty": 300e12, "id": 800000},
                {"date": datetime.now().strftime("%Y-%m-%d"), 
                 "difficulty": 310e12, "id": 802016}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        data = predictor.fetch_historical_difficulty(days=30)
        
        self.assertEqual(len(data), 2)
        self.assertEqual(data["difficulty"].iloc[-1], 310e12)
    
    @patch('difficulty_predictor.requests.get')
    def test_fetch_ltc_data(self, mock_get):
        """Test LTC data fetch."""
        config = PredictorConfig(coin="LTC")
        predictor = DifficultyPredictor(config)
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": {"difficulty": 100e6}
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        data = predictor.fetch_historical_difficulty(days=30)
        
        self.assertIsInstance(data, pd.DataFrame)
        self.assertGreater(len(data), 0)


class TestFeaturePreparation(unittest.TestCase):
    """Tests for feature preparation."""
    
    def setUp(self):
        self.config = PredictorConfig(lookback_periods=3)
        self.predictor = DifficultyPredictor(self.config)
        
        # Create synthetic data
        dates = [datetime.now() - timedelta(days=i*14) for i in range(10, 0, -1)]
        difficulties = [80e15 * (1.02 ** i) for i in range(10)]
        
        self.predictor.data = pd.DataFrame({
            "timestamp": dates,
            "difficulty": difficulties,
            "block_height": range(1000, 1100, 10)
        })
    
    def test_prepare_features_success(self):
        """Test successful feature preparation."""
        X, y = self.predictor._prepare_features()
        
        self.assertIsInstance(X, np.ndarray)
        self.assertIsInstance(y, np.ndarray)
        self.assertEqual(X.shape[0], y.shape[0])
        self.assertEqual(X.shape[1], self.config.lookback_periods + 4)  # seq + 4 features
    
    def test_prepare_features_insufficient_data(self):
        """Test feature preparation with insufficient data."""
        self.predictor.data = pd.DataFrame({
            "timestamp": [datetime.now()],
            "difficulty": [80e15],
            "block_height": [1000]
        })
        
        with self.assertRaises(InsufficientDataError):
            self.predictor._prepare_features()
    
    def test_prepare_features_no_data(self):
        """Test feature preparation with no data."""
        self.predictor.data = None
        
        with self.assertRaises(InsufficientDataError):
            self.predictor._prepare_features()


class TestModelTraining(unittest.TestCase):
    """Tests for model training."""
    
    def setUp(self):
        self.config = PredictorConfig(model_type="linear", lookback_periods=3)
        self.predictor = DifficultyPredictor(self.config)
        
        # Create synthetic data with clear trend
        np.random.seed(42)
        dates = [datetime.now() - timedelta(days=i*14) for i in range(20, 0, -1)]
        difficulties = [80e15 * (1.01 ** i) + np.random.normal(0, 1e12) for i in range(20)]
        
        self.predictor.data = pd.DataFrame({
            "timestamp": dates,
            "difficulty": difficulties,
            "block_height": range(1000, 1200, 10)
        })
    
    def test_train_linear_model(self):
        """Test linear model training."""
        metrics = self.predictor.train_model()
        
        self.assertIsNotNone(self.predictor.model)
        self.assertIsNotNone(self.predictor.scaler)
        self.assertIn("mae", metrics)
        self.assertIn("r2", metrics)
    
    def test_train_without_data(self):
        """Test training without data raises error."""
        predictor = DifficultyPredictor(self.config)
        
        with self.assertRaises(ModelTrainingError):
            predictor.train_model()
    
    @patch('difficulty_predictor.TENSORFLOW_AVAILABLE', True)
    def test_train_lstm_model(self):
        """Test LSTM model training with mocked TensorFlow."""
        # Mock the keras module completely
        mock_keras = Mock()
        mock_model = Mock()
        mock_model.fit.return_value = Mock(history={'loss': [0.1, 0.05, 0.01]})
        mock_model.predict.return_value = np.array([[0.02], [0.03]])
        mock_keras.models.Sequential.return_value = mock_model
        
        with patch.dict('sys.modules', {'tensorflow': mock_keras, 'tensorflow.keras': mock_keras, 
                                        'tensorflow.keras.models': mock_keras.models, 
                                        'tensorflow.keras.layers': mock_keras.layers}):
            with patch('difficulty_predictor.keras', mock_keras):
                config = PredictorConfig(model_type="lstm", lookback_periods=3, lstm_epochs=3)
                predictor = DifficultyPredictor(config)
                
                dates = [datetime.now() - timedelta(days=i*7) for i in range(30, 0, -1)]
                difficulties = [80e15 * (1.005 ** i) + np.random.normal(0, 1e12) for i in range(30)]
                predictor.data = pd.DataFrame({
                    "timestamp": dates,
                    "difficulty": difficulties,
                    "block_height": range(1000, 1300, 10)
                })
                
                # Force TensorFlow available for this test
                import difficulty_predictor as dp
                original = dp.TENSORFLOW_AVAILABLE
                dp.TENSORFLOW_AVAILABLE = True
                try:
                    metrics = predictor.train_model()
                    self.assertIn("final_loss", metrics)
                finally:
                    dp.TENSORFLOW_AVAILABLE = original


class TestPrediction(unittest.TestCase):
    """Tests for prediction functionality."""
    
    def setUp(self):
        self.config = PredictorConfig(model_type="linear", lookback_periods=3)
        self.predictor = DifficultyPredictor(self.config)
        
        # Create and train on synthetic data
        np.random.seed(42)
        dates = [datetime.now() - timedelta(days=i*14) for i in range(20, 0, -1)]
        difficulties = [80e15 * (1.01 ** i) for i in range(20)]
        
        self.predictor.data = pd.DataFrame({
            "timestamp": dates,
            "difficulty": difficulties,
            "block_height": range(1000, 1200, 10)
        })
        
        self.predictor.train_model()
    
    def test_predict_next_adjustment(self):
        """Test next adjustment prediction."""
        result = self.predictor.predict_next_adjustment()
        
        self.assertIn("current_difficulty", result)
        self.assertIn("predicted_difficulty", result)
        self.assertIn("predicted_change_percent", result)
        self.assertIn("confidence", result)
        self.assertIn("estimated_adjustment_time", result)
        self.assertIn("blocks_until_adjustment", result)
        
        self.assertGreater(result["current_difficulty"], 0)
        self.assertGreater(result["predicted_difficulty"], 0)
        self.assertGreaterEqual(result["confidence"], 0)
        self.assertLessEqual(result["confidence"], 1)
    
    def test_predict_without_training(self):
        """Test prediction without training raises error."""
        predictor = DifficultyPredictor(self.config)
        predictor.data = self.predictor.data
        
        with self.assertRaises(PredictionError):
            predictor.predict_next_adjustment()
    
    def test_predict_change_bounds(self):
        """Test that predicted change is within protocol bounds."""
        result = self.predictor.predict_next_adjustment()
        
        # Bitcoin max adjustment is 4x, meaning -75% to +300%
        self.assertGreaterEqual(result["predicted_change_percent"], -75)
        self.assertLessEqual(result["predicted_change_percent"], 300)


class TestConfidenceCalculation(unittest.TestCase):
    """Tests for confidence calculation."""
    
    def setUp(self):
        self.config = PredictorConfig()
        self.predictor = DifficultyPredictor(self.config)
        self.predictor.training_metrics = {
            "r2": 0.8,
            "mae": 0.05
        }
    
    def test_calculate_confidence(self):
        """Test confidence calculation."""
        predictions = np.array([0.02, 0.025, 0.018])
        confidence = self.predictor.calculate_confidence(predictions)
        
        self.assertGreaterEqual(confidence, 0)
        self.assertLessEqual(confidence, 1)
    
    def test_confidence_with_good_metrics(self):
        """Test confidence with good model metrics."""
        self.predictor.training_metrics = {
            "r2": 0.9,
            "mae": 0.01
        }
        
        confidence = self.predictor.calculate_confidence(np.array([0.02]))
        self.assertGreater(confidence, 0.5)
    
    def test_confidence_with_poor_metrics(self):
        """Test confidence with poor model metrics."""
        self.predictor.training_metrics = {
            "r2": -0.5,
            "mae": 0.5
        }
        
        confidence = self.predictor.calculate_confidence(np.array([0.5, -0.3, 0.8]))
        self.assertLess(confidence, 0.8)


class TestAdjustmentTiming(unittest.TestCase):
    """Tests for adjustment timing calculations."""
    
    def setUp(self):
        self.config = PredictorConfig(coin="BTC")
        self.predictor = DifficultyPredictor(self.config)
    
    @patch('difficulty_predictor.requests.get')
    def test_get_adjustment_timing_from_api(self, mock_get):
        """Test timing calculation from API block height."""
        mock_response = Mock()
        # BTC endpoint returns just the block height as a number
        mock_response.json.return_value = 802000
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        timing = self.predictor.get_adjustment_timing()
        
        self.assertIn("blocks_remaining", timing)
        self.assertIn("estimated_time", timing)
        self.assertIn("progress_percent", timing)
        
        # 802000 % 2016 = 1312 blocks into period
        # blocks_remaining = 2016 - 1312 = 704
        self.assertEqual(timing["blocks_remaining"], 704)
    
    def test_get_adjustment_timing_from_data(self):
        """Test timing calculation from historical data."""
        # Create data with recent adjustment
        self.predictor.data = pd.DataFrame({
            "timestamp": [datetime.now() - timedelta(days=7)],
            "difficulty": [80e15],
            "block_height": [800000]
        })
        
        timing = self.predictor.get_adjustment_timing()
        
        self.assertGreaterEqual(timing["blocks_remaining"], 0)
        self.assertGreater(timing["progress_percent"], 0)


class TestHistoricalStats(unittest.TestCase):
    """Tests for historical statistics."""
    
    def setUp(self):
        self.config = PredictorConfig()
        self.predictor = DifficultyPredictor(self.config)
    
    def test_get_historical_stats(self):
        """Test historical statistics calculation."""
        dates = [datetime.now() - timedelta(days=i*14) for i in range(10, 0, -1)]
        difficulties = [80e15 * (1.01 ** i) for i in range(10)]
        
        self.predictor.data = pd.DataFrame({
            "timestamp": dates,
            "difficulty": difficulties,
            "block_height": range(1000, 1100, 10)
        })
        
        stats = self.predictor.get_historical_stats()
        
        self.assertIn("total_adjustments", stats)
        self.assertIn("date_range", stats)
        self.assertIn("difficulty_range", stats)
        self.assertIn("average_change_percent", stats)
        self.assertIn("volatility", stats)
        
        self.assertEqual(stats["total_adjustments"], 10)
        self.assertGreater(stats["average_change_percent"], 0)
    
    def test_get_historical_stats_no_data(self):
        """Test stats with no data."""
        stats = self.predictor.get_historical_stats()
        self.assertEqual(stats, {})


class TestUtilityFunctions(unittest.TestCase):
    """Tests for utility functions."""
    
    @patch('difficulty_predictor.DifficultyPredictor')
    def test_predict_all_coins(self, mock_predictor_class):
        """Test batch prediction for all coins."""
        mock_instance = Mock()
        mock_instance.predict_next_adjustment.return_value = {
            "predicted_change_percent": 5.0,
            "confidence": 0.8
        }
        mock_predictor_class.return_value = mock_instance
        
        results = predict_all_coins(model_type="linear", days=90)
        
        self.assertIn("BTC", results)
        self.assertIn("BCH", results)
        self.assertIn("LTC", results)
        
        # Each should have been called
        self.assertEqual(mock_predictor_class.call_count, 3)


class TestIntegration(unittest.TestCase):
    """Integration tests with mocked external dependencies."""
    
    @patch('difficulty_predictor.requests.get')
    def test_full_pipeline_btc(self, mock_get):
        """Test full pipeline for BTC prediction."""
        # Create many data points to survive feature engineering
        # Need: lookback_periods + max_rolling_window + extra for NaN drops + train/test split
        # lookback=3, rolling=5, need at least 15-20 points
        num_points = 25
        dates = [datetime.now() - timedelta(days=i*7) for i in range(num_points, 0, -1)]
        
        # Mock API responses with enough data points
        mock_responses = [
            # blockchain.info difficulty data
            Mock(
                json=Mock(return_value={
                    "values": [
                        {"x": int(d.timestamp()), "y": 75e15 * (1.005 ** i)} 
                        for i, d in enumerate(dates)
                    ]
                }),
                raise_for_status=Mock()
            ),
            # block height API
            Mock(
                json=Mock(return_value=802000),
                raise_for_status=Mock()
            )
        ]
        mock_get.side_effect = mock_responses
        
        # Run full pipeline with smaller lookback to ensure enough data
        config = PredictorConfig(coin="BTC", model_type="linear", lookback_periods=3, test_size=0.2)
        predictor = DifficultyPredictor(config)
        
        data = predictor.fetch_historical_difficulty(days=180)
        self.assertGreaterEqual(len(data), 20)
        
        metrics = predictor.train_model()
        self.assertIn("mae", metrics)
        
        result = predictor.predict_next_adjustment()
        self.assertIn("predicted_change_percent", result)
        self.assertIn("confidence", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
