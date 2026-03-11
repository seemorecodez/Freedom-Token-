"""
Unit tests for the backtester module.
"""

import unittest
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtester import (
    BacktestConfig, Backtester, BacktestResult,
    PriceData, Trade, TradeSide, TradeStatus,
    load_historical_data, calculate_metrics,
    compare_strategies, walk_forward_analysis,
    generate_trade_log, generate_equity_curve,
    example_sma_strategy, example_rsi_strategy
)


class TestBacktestConfig(unittest.TestCase):
    """Test BacktestConfig class."""
    
    def test_valid_config(self):
        """Test creating valid config."""
        config = BacktestConfig(
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2020, 12, 31),
            initial_capital=100000,
            commission_rate=0.001
        )
        self.assertEqual(config.initial_capital, 100000)
        self.assertEqual(config.commission_rate, 0.001)
    
    def test_invalid_dates(self):
        """Test that invalid date range raises error."""
        with self.assertRaises(ValueError):
            BacktestConfig(
                start_date=datetime(2020, 12, 31),
                end_date=datetime(2020, 1, 1),
                initial_capital=100000
            )
    
    def test_invalid_capital(self):
        """Test that non-positive capital raises error."""
        with self.assertRaises(ValueError):
            BacktestConfig(
                start_date=datetime(2020, 1, 1),
                end_date=datetime(2020, 12, 31),
                initial_capital=0
            )


class TestTrade(unittest.TestCase):
    """Test Trade class."""
    
    def test_trade_creation(self):
        """Test trade creation."""
        trade = Trade(
            entry_time=datetime(2020, 1, 1),
            entry_price=100,
            side=TradeSide.BUY,
            size=10,
            symbol="TEST"
        )
        self.assertEqual(trade.status, TradeStatus.OPEN)
        self.assertIsNone(trade.duration)
    
    def test_trade_close_buy(self):
        """Test closing a buy trade."""
        trade = Trade(
            entry_time=datetime(2020, 1, 1),
            entry_price=100,
            side=TradeSide.BUY,
            size=10,
            symbol="TEST"
        )
        trade.close(datetime(2020, 1, 2), 110, fees=1)
        
        self.assertEqual(trade.status, TradeStatus.CLOSED)
        self.assertEqual(trade.pnl, 99)  # (110-100)*10 - 1
        self.assertAlmostEqual(trade.pnl_pct, 10.0, places=5)
        self.assertIsNotNone(trade.duration)
    
    def test_trade_close_sell(self):
        """Test closing a short trade."""
        trade = Trade(
            entry_time=datetime(2020, 1, 1),
            entry_price=100,
            side=TradeSide.SELL,
            size=10,
            symbol="TEST"
        )
        trade.close(datetime(2020, 1, 2), 90, fees=1)
        
        self.assertEqual(trade.pnl, 99)  # (100-90)*10 - 1
        self.assertAlmostEqual(trade.pnl_pct, 11.11111111111111, places=5)


class TestPriceData(unittest.TestCase):
    """Test PriceData class."""
    
    def setUp(self):
        """Create test data."""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        self.df = pd.DataFrame({
            'open': np.random.randn(100).cumsum() + 100,
            'high': np.random.randn(100).cumsum() + 102,
            'low': np.random.randn(100).cumsum() + 98,
            'close': np.random.randn(100).cumsum() + 100,
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)
    
    def test_valid_data(self):
        """Test valid price data creation."""
        data = PriceData(self.df)
        self.assertEqual(len(data.data), 100)
    
    def test_missing_columns(self):
        """Test that missing columns raise error."""
        bad_df = self.df.drop('close', axis=1)
        with self.assertRaises(ValueError):
            PriceData(bad_df)
    
    def test_returns_calculation(self):
        """Test returns calculation."""
        data = PriceData(self.df)
        returns = data.returns
        self.assertEqual(len(returns), 99)  # First value is NaN
    
    def test_data_slicing(self):
        """Test data slicing by date."""
        data = PriceData(self.df)
        sliced = data.get_slice(datetime(2020, 1, 10), datetime(2020, 1, 20))
        self.assertTrue(len(sliced.data) > 0)


class TestLoadHistoricalData(unittest.TestCase):
    """Test data loading functions."""
    
    def test_synthetic_data(self):
        """Test synthetic data generation."""
        start = datetime(2020, 1, 1)
        end = datetime(2020, 12, 31)
        
        data = load_historical_data(
            "TEST",
            start,
            end,
            source="synthetic",
            trend=0.0001,
            volatility=0.02
        )
        
        self.assertIsInstance(data, PriceData)
        self.assertTrue(len(data.data) > 0)
        self.assertIn('open', data.data.columns)
        self.assertIn('close', data.data.columns)
    
    def test_synthetic_with_seed(self):
        """Test that seed produces reproducible results."""
        start = datetime(2020, 1, 1)
        end = datetime(2020, 6, 1)
        
        data1 = load_historical_data("TEST", start, end, source="synthetic", seed=42)
        data2 = load_historical_data("TEST", start, end, source="synthetic", seed=42)
        
        pd.testing.assert_frame_equal(data1.data, data2.data)
    
    def test_invalid_source(self):
        """Test that invalid source raises error."""
        with self.assertRaises(ValueError):
            load_historical_data(
                "TEST",
                datetime(2020, 1, 1),
                datetime(2020, 12, 31),
                source="invalid"
            )
    
    def test_csv_without_filepath(self):
        """Test that CSV source requires filepath."""
        with self.assertRaises(ValueError):
            load_historical_data(
                "TEST",
                datetime(2020, 1, 1),
                datetime(2020, 12, 31),
                source="csv"
            )


class TestBacktester(unittest.TestCase):
    """Test Backtester engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.start = datetime(2020, 1, 1)
        self.end = datetime(2020, 6, 30)
        self.data = load_historical_data(
            "TEST", self.start, self.end,
            source="synthetic", seed=42
        )
        self.config = BacktestConfig(
            start_date=self.start,
            end_date=self.end,
            initial_capital=100000,
            commission_rate=0.001
        )
    
    def test_backtester_initialization(self):
        """Test backtester initialization."""
        bt = Backtester(self.config)
        self.assertEqual(bt.current_capital, 100000)
        self.assertEqual(len(bt.trades), 0)
    
    def test_load_data(self):
        """Test loading data into backtester."""
        bt = Backtester(self.config)
        bt.load_data("TEST", self.data)
        self.assertIn("TEST", bt.data)
    
    def test_run_backtest(self):
        """Test running a complete backtest."""
        bt = Backtester(self.config)
        bt.load_data("TEST", self.data)
        
        result = bt.run_backtest(
            example_sma_strategy,
            {'fast_period': 5, 'slow_period': 20}
        )
        
        self.assertIsInstance(result, BacktestResult)
        self.assertIsNotNone(result.total_return)
        self.assertIsNotNone(result.sharpe_ratio)
    
    def test_equity_curve_generated(self):
        """Test that equity curve is generated."""
        bt = Backtester(self.config)
        bt.load_data("TEST", self.data)
        
        result = bt.run_backtest(
            example_sma_strategy,
            {'fast_period': 10, 'slow_period': 30}
        )
        
        self.assertTrue(len(result.equity_curve) > 0)
        self.assertEqual(result.equity_curve.iloc[0], 100000)
    
    def test_stop_loss(self):
        """Test stop loss execution."""
        config = BacktestConfig(
            start_date=self.start,
            end_date=self.end,
            initial_capital=100000,
            stop_loss_pct=0.02  # 2% stop loss
        )
        
        bt = Backtester(config)
        bt.load_data("TEST", self.data)
        
        result = bt.run_backtest(
            example_sma_strategy,
            {'fast_period': 5, 'slow_period': 10}
        )
        
        # Check that stop losses were potentially triggered
        self.assertIsInstance(result, BacktestResult)


class TestCalculateMetrics(unittest.TestCase):
    """Test metrics calculation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.start = datetime(2020, 1, 1)
        self.end = datetime(2020, 6, 30)
        self.config = BacktestConfig(
            start_date=self.start,
            end_date=self.end,
            initial_capital=100000
        )
    
    def test_empty_result(self):
        """Test metrics on empty result."""
        result = BacktestResult(config=self.config)
        metrics = calculate_metrics(result)
        self.assertEqual(metrics, {})
    
    def test_basic_metrics(self):
        """Test basic metrics calculation."""
        # Create simple equity curve
        dates = pd.date_range(start=self.start, periods=100, freq='D')
        equity = pd.Series(100000 * (1 + np.linspace(0, 0.1, 100)), index=dates)
        
        result = BacktestResult(
            config=self.config,
            equity_curve=equity,
            trades=[]
        )
        
        metrics = calculate_metrics(result)
        
        self.assertAlmostEqual(result.total_return, 10.0, places=1)
        self.assertIsNotNone(result.sharpe_ratio)
        self.assertIsNotNone(result.volatility)
    
    def test_with_trades(self):
        """Test metrics with trades."""
        dates = pd.date_range(start=self.start, periods=100, freq='D')
        equity = pd.Series(100000 * np.ones(100), index=dates)
        
        trades = [
            Trade(
                entry_time=datetime(2020, 1, 1),
                entry_price=100,
                exit_time=datetime(2020, 1, 15),
                exit_price=110,
                side=TradeSide.BUY,
                size=10,
                symbol="TEST",
                status=TradeStatus.CLOSED,
                pnl=100,
                pnl_pct=10.0
            ),
            Trade(
                entry_time=datetime(2020, 2, 1),
                entry_price=110,
                exit_time=datetime(2020, 2, 15),
                exit_price=105,
                side=TradeSide.BUY,
                size=10,
                symbol="TEST",
                status=TradeStatus.CLOSED,
                pnl=-50,
                pnl_pct=-4.55
            )
        ]
        
        result = BacktestResult(
            config=self.config,
            equity_curve=equity,
            trades=trades
        )
        
        metrics = calculate_metrics(result)
        
        self.assertEqual(result.win_rate, 50.0)  # 1 win, 1 loss
        self.assertEqual(result.profit_factor, 2.0)  # 100 / 50


class TestCompareStrategies(unittest.TestCase):
    """Test strategy comparison."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.start = datetime(2020, 1, 1)
        self.end = datetime(2020, 6, 30)
        self.config = BacktestConfig(
            start_date=self.start,
            end_date=self.end,
            initial_capital=100000
        )
    
    def test_compare_multiple(self):
        """Test comparing multiple strategies."""
        dates = pd.date_range(start=self.start, periods=50, freq='D')
        
        result1 = BacktestResult(
            config=self.config,
            equity_curve=pd.Series(100000 * (1 + np.linspace(0, 0.1, 50)), index=dates),
            total_return=10.0,
            sharpe_ratio=1.5,
            max_drawdown=-5.0
        )
        
        result2 = BacktestResult(
            config=self.config,
            equity_curve=pd.Series(100000 * (1 + np.linspace(0, 0.05, 50)), index=dates),
            total_return=5.0,
            sharpe_ratio=1.0,
            max_drawdown=-3.0
        )
        
        comparison = compare_strategies(
            [result1, result2],
            ["Strategy A", "Strategy B"]
        )
        
        self.assertEqual(len(comparison), 2)
        self.assertIn("Strategy", comparison.columns)
        self.assertIn("Total Return (%)", comparison.columns)
    
    def test_default_names(self):
        """Test comparison with default names."""
        dates = pd.date_range(start=self.start, periods=50, freq='D')
        
        result1 = BacktestResult(
            config=self.config,
            equity_curve=pd.Series(np.ones(50) * 100000, index=dates)
        )
        result2 = BacktestResult(
            config=self.config,
            equity_curve=pd.Series(np.ones(50) * 100000, index=dates)
        )
        
        comparison = compare_strategies([result1, result2])
        
        self.assertEqual(comparison.iloc[0]['Strategy'], "Strategy 1")
        self.assertEqual(comparison.iloc[1]['Strategy'], "Strategy 2")


class TestWalkForwardAnalysis(unittest.TestCase):
    """Test walk-forward analysis."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.start = datetime(2020, 1, 1)
        self.end = datetime(2021, 1, 1)
        self.data = load_historical_data(
            "TEST", self.start, self.end,
            source="synthetic", seed=42
        )
    
    def test_walk_forward(self):
        """Test basic walk-forward analysis."""
        param_grid = [
            {'fast_period': 5, 'slow_period': 20},
            {'fast_period': 10, 'slow_period': 30}
        ]
        
        results = walk_forward_analysis(
            data=self.data,
            strategy=example_sma_strategy,
            strategy_params_list=param_grid,
            train_size=100,
            test_size=50,
            step_size=50
        )
        
        self.assertIn('windows', results)
        self.assertIn('oos_results', results)
        self.assertIn('aggregated_metrics', results)
        self.assertIn('optimal_params_history', results)
    
    def test_aggregated_metrics(self):
        """Test aggregated metrics calculation."""
        param_grid = [
            {'fast_period': 5, 'slow_period': 20}
        ]
        
        results = walk_forward_analysis(
            data=self.data,
            strategy=example_sma_strategy,
            strategy_params_list=param_grid,
            train_size=100,
            test_size=50
        )
        
        metrics = results['aggregated_metrics']
        self.assertIn('avg_total_return', metrics)
        self.assertIn('avg_sharpe', metrics)
        self.assertIn('num_windows', metrics)


class TestGenerateReports(unittest.TestCase):
    """Test report generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.start = datetime(2020, 1, 1)
        self.end = datetime(2020, 3, 1)
        self.config = BacktestConfig(
            start_date=self.start,
            end_date=self.end,
            initial_capital=100000
        )
    
    def test_generate_trade_log(self):
        """Test trade log generation."""
        trades = [
            Trade(
                entry_time=datetime(2020, 1, 1),
                entry_price=100,
                exit_time=datetime(2020, 1, 15),
                exit_price=110,
                side=TradeSide.BUY,
                size=10,
                symbol="TEST",
                status=TradeStatus.CLOSED,
                pnl=100,
                pnl_pct=10.0
            )
        ]
        
        result = BacktestResult(
            config=self.config,
            trades=trades
        )
        
        log = generate_trade_log(result)
        
        self.assertEqual(len(log), 1)
        self.assertIn('Symbol', log.columns)
        self.assertIn('P&L ($)', log.columns)
    
    def test_empty_trade_log(self):
        """Test trade log with no trades."""
        result = BacktestResult(
            config=self.config,
            trades=[]
        )
        
        log = generate_trade_log(result)
        self.assertTrue(log.empty)
    
    def test_generate_equity_curve(self):
        """Test equity curve generation."""
        dates = pd.date_range(start=self.start, periods=50, freq='D')
        equity = pd.Series(100000 * (1 + np.linspace(0, 0.1, 50)), index=dates)
        
        result = BacktestResult(
            config=self.config,
            equity_curve=equity
        )
        
        curve = generate_equity_curve(result)
        
        self.assertIn('Timestamp', curve.columns)
        self.assertIn('Equity', curve.columns)
        self.assertIn('Drawdown (%)', curve.columns)


class TestExampleStrategies(unittest.TestCase):
    """Test example strategies."""
    
    def setUp(self):
        """Set up test data."""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
        self.data = pd.DataFrame({
            'open': prices,
            'high': prices + 1,
            'low': prices - 1,
            'close': prices,
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)
    
    def test_sma_strategy_signals(self):
        """Test SMA strategy generates signals."""
        # Test with insufficient data
        signal = example_sma_strategy(self.data.iloc[:5], {'fast_period': 10, 'slow_period': 30})
        self.assertEqual(signal['action'], 'hold')
        
        # Test with sufficient data
        signal = example_sma_strategy(self.data, {'fast_period': 10, 'slow_period': 30})
        self.assertIn(signal['action'], ['buy', 'sell', 'hold'])
    
    def test_rsi_strategy_signals(self):
        """Test RSI strategy generates signals."""
        # Test with insufficient data
        signal = example_rsi_strategy(self.data.iloc[:5], {'period': 14})
        self.assertEqual(signal['action'], 'hold')
        
        # Test with sufficient data
        signal = example_rsi_strategy(self.data, {'period': 14, 'oversold': 30, 'overbought': 70})
        self.assertIn(signal['action'], ['buy', 'sell', 'hold'])
    
    def test_rsi_oversold_signal(self):
        """Test RSI generates buy on oversold."""
        # Create data that will trigger oversold condition
        dates = pd.date_range(start='2020-01-01', periods=50, freq='D')
        # Declining prices to push RSI low
        prices = 100 - np.linspace(0, 30, 50)
        data = pd.DataFrame({
            'open': prices,
            'high': prices + 1,
            'low': prices - 1,
            'close': prices,
            'volume': np.ones(50) * 1000
        }, index=dates)
        
        signal = example_rsi_strategy(data, {'period': 14, 'oversold': 30, 'overbought': 70})
        # Should either buy (if crossed into oversold) or hold
        self.assertIn(signal['action'], ['buy', 'hold'])


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_full_backtest_pipeline(self):
        """Test complete backtest pipeline."""
        # Setup
        start = datetime(2020, 1, 1)
        end = datetime(2020, 6, 30)
        
        # Load data
        data = load_historical_data("TEST", start, end, source="synthetic", seed=42)
        
        # Configure
        config = BacktestConfig(
            start_date=start,
            end_date=end,
            initial_capital=100000,
            commission_rate=0.001
        )
        
        # Run backtest
        bt = Backtester(config)
        bt.load_data("TEST", data)
        result = bt.run_backtest(
            example_sma_strategy,
            {'fast_period': 10, 'slow_period': 30}
        )
        
        # Calculate metrics
        metrics = calculate_metrics(result)
        
        # Verify results
        self.assertIsNotNone(result.equity_curve)
        self.assertIsInstance(metrics, dict)
        self.assertIn('total_return', metrics)
        
        # Generate reports
        trade_log = generate_trade_log(result)
        equity_df = generate_equity_curve(result)
        
        self.assertIsInstance(trade_log, pd.DataFrame)
        self.assertIsInstance(equity_df, pd.DataFrame)
    
    def test_strategy_comparison_pipeline(self):
        """Test strategy comparison pipeline."""
        start = datetime(2020, 1, 1)
        end = datetime(2020, 6, 30)
        
        data = load_historical_data("TEST", start, end, source="synthetic", seed=42)
        
        config = BacktestConfig(start_date=start, end_date=end, initial_capital=100000)
        
        # Run multiple strategies
        results = []
        for fast, slow in [(5, 20), (10, 30)]:
            bt = Backtester(config)
            bt.load_data("TEST", data)
            result = bt.run_backtest(
                example_sma_strategy,
                {'fast_period': fast, 'slow_period': slow}
            )
            results.append(result)
        
        # Compare
        comparison = compare_strategies(results, ["Fast", "Slow"])
        
        self.assertEqual(len(comparison), 2)
        self.assertEqual(list(comparison['Strategy']), ["Fast", "Slow"])


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
