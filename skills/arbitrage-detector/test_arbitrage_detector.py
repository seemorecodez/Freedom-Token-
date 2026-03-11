"""
Unit tests for the arbitrage detector module.
"""

import unittest
from unittest.mock import Mock, patch
from decimal import Decimal

from arbitrage_detector import ArbitrageConfig, ArbitrageDetector


class TestArbitrageConfig(unittest.TestCase):
    """Tests for the ArbitrageConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ArbitrageConfig()
        
        self.assertEqual(config.pairs, [])
        self.assertEqual(config.min_spread_percent, 0.5)
        self.assertEqual(config.exchanges, ["binance", "coinbase", "kraken"])
        self.assertEqual(config.slippage_percent, 0.1)
        self.assertEqual(config.min_profit_usd, 10.0)
        self.assertTrue(config.simulate)
        self.assertEqual(config.simulate_volatility, 0.02)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ArbitrageConfig(
            pairs=["BTC/USDT", "ETH/USDT"],
            min_spread_percent=1.0,
            exchanges=["binance", "kraken"],
            simulate=False
        )
        
        self.assertEqual(config.pairs, ["BTC/USDT", "ETH/USDT"])
        self.assertEqual(config.min_spread_percent, 1.0)
        self.assertEqual(config.exchanges, ["binance", "kraken"])
        self.assertFalse(config.simulate)
    
    def test_trading_fees(self):
        """Test trading fees configuration."""
        config = ArbitrageConfig()
        
        self.assertIn("binance", config.trading_fees)
        self.assertIn("coinbase", config.trading_fees)
        self.assertEqual(config.trading_fees["binance"], 0.001)
        self.assertEqual(config.trading_fees["coinbase"], 0.005)


class TestArbitrageDetectorSimulation(unittest.TestCase):
    """Tests for arbitrage detection in simulation mode."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ArbitrageConfig(
            pairs=["BTC/USDT", "ETH/USDT", "ETH/BTC"],
            min_spread_percent=0.1,
            exchanges=["binance", "coinbase"],
            simulate=True,
            simulate_volatility=0.02
        )
        self.detector = ArbitrageDetector(self.config)
    
    def test_fetch_simulated_prices(self):
        """Test fetching simulated prices."""
        prices = self.detector.fetch_prices_multi_exchange()
        
        # Check structure
        self.assertIn("BTC/USDT", prices)
        self.assertIn("ETH/USDT", prices)
        self.assertIn("binance", prices["BTC/USDT"])
        self.assertIn("coinbase", prices["BTC/USDT"])
        
        # Check price data structure
        btc_data = prices["BTC/USDT"]["binance"]
        self.assertIn("bid", btc_data)
        self.assertIn("ask", btc_data)
        self.assertIn("last", btc_data)
        
        # Bid should be less than ask
        self.assertLess(btc_data["bid"], btc_data["ask"])
    
    def test_simulated_prices_consistency(self):
        """Test that simulated prices are consistent across calls."""
        prices1 = self.detector.fetch_prices_multi_exchange()
        prices2 = self.detector.fetch_prices_multi_exchange()
        
        # Should get same structure
        self.assertEqual(set(prices1.keys()), set(prices2.keys()))
    
    def test_find_opportunities_structure(self):
        """Test the structure of found opportunities."""
        opportunities = self.detector.find_opportunities()
        
        # Should return a list
        self.assertIsInstance(opportunities, list)
        
        # If opportunities found, check structure
        for opp in opportunities:
            self.assertIn("type", opp)
            self.assertEqual(opp["type"], "simple")
            self.assertIn("pair", opp)
            self.assertIn("buy_exchange", opp)
            self.assertIn("sell_exchange", opp)
            self.assertIn("buy_price", opp)
            self.assertIn("sell_price", opp)
            self.assertIn("spread_percent", opp)
            self.assertIn("profit_percent", opp)
            self.assertIn("profit_usd", opp)
            self.assertIn("timestamp", opp)
            self.assertIn("details", opp)
    
    def test_find_opportunities_spread_filter(self):
        """Test that opportunities respect minimum spread filter."""
        # Use high minimum spread to limit opportunities
        config = ArbitrageConfig(
            pairs=["BTC/USDT"],
            min_spread_percent=10.0,  # Very high threshold
            exchanges=["binance", "coinbase"],
            simulate=True
        )
        detector = ArbitrageDetector(config)
        
        opportunities = detector.find_opportunities()
        
        # All opportunities should have spread >= min_spread_percent
        for opp in opportunities:
            self.assertGreaterEqual(opp["spread_percent"], config.min_spread_percent)
    
    def test_calculate_profit(self):
        """Test profit calculation with fees."""
        result = self.detector.calculate_profit(
            buy_price=50000.0,
            sell_price=50500.0,
            volume=1.0,
            buy_exchange="binance",
            sell_exchange="coinbase"
        )
        
        # Check structure
        self.assertIn("gross_profit", result)
        self.assertIn("total_trading_fees", result)
        self.assertIn("net_profit", result)
        self.assertIn("net_profit_percent", result)
        self.assertIn("is_profitable", result)
        
        # Check calculations
        self.assertEqual(result["gross_profit"], 500.0)
        self.assertTrue(result["total_trading_fees"] > 0)
        self.assertIsInstance(result["is_profitable"], bool)
    
    def test_calculate_profit_unprofitable(self):
        """Test profit calculation for unprofitable trade."""
        result = self.detector.calculate_profit(
            buy_price=50500.0,
            sell_price=50000.0,
            volume=1.0,
            buy_exchange="binance",
            sell_exchange="coinbase"
        )
        
        # Should not be profitable
        self.assertFalse(result["is_profitable"])
        self.assertLess(result["net_profit"], 0)
    
    def test_calculate_profit_with_fees(self):
        """Test that fees are properly deducted."""
        result = self.detector.calculate_profit(
            buy_price=10000.0,
            sell_price=10050.0,
            volume=1.0,
            buy_exchange="binance",
            sell_exchange="coinbase"
        )
        
        # Binance fee: 0.1%, Coinbase fee: 0.5%
        # Buy fee: 10000 * 0.001 = 10
        # Sell fee: 10050 * 0.005 = 50.25
        # Total fees: ~60
        # Gross profit: 50, so net should be negative
        self.assertFalse(result["is_profitable"])
    
    def test_get_best_prices(self):
        """Test getting best prices across exchanges."""
        best = self.detector.get_best_prices("BTC/USDT")
        
        self.assertIn("pair", best)
        self.assertEqual(best["pair"], "BTC/USDT")
        self.assertIn("best_bid", best)
        self.assertIn("best_bid_exchange", best)
        self.assertIn("best_ask", best)
        self.assertIn("best_ask_exchange", best)
        self.assertIn("spread", best)
        self.assertIn("spread_percent", best)
        
        # Best bid should be >= best ask for valid arbitrage
        # But due to simulation, they might not be
        self.assertIsInstance(best["best_bid"], float)
        self.assertIsInstance(best["best_ask"], float)
    
    def test_get_best_prices_invalid_pair(self):
        """Test getting best prices for non-existent pair."""
        best = self.detector.get_best_prices("INVALID/PAIR")
        
        self.assertIn("error", best)


class TestTriangularArbitrage(unittest.TestCase):
    """Tests for triangular arbitrage detection."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ArbitrageConfig(
            pairs=["BTC/USDT", "ETH/USDT", "ETH/BTC"],
            min_spread_percent=0.01,  # Low threshold for testing
            exchanges=["binance"],
            simulate=True,
            simulate_volatility=0.05  # Higher volatility for more opportunities
        )
        self.detector = ArbitrageDetector(self.config)
    
    def test_find_triangular_opportunities_structure(self):
        """Test structure of triangular opportunities."""
        opportunities = self.detector.find_triangular_opportunities(base_asset="USDT")
        
        # Should return a list
        self.assertIsInstance(opportunities, list)
        
        # Check structure if any opportunities found
        for opp in opportunities:
            self.assertIn("type", opp)
            self.assertEqual(opp["type"], "triangular")
            self.assertIn("exchange", opp)
            self.assertIn("path", opp)
            self.assertIn("pairs", opp)
            self.assertIn("start_amount", opp)
            self.assertIn("final_amount", opp)
            self.assertIn("net_profit", opp)
            self.assertIn("net_profit_percent", opp)
            self.assertIn("steps", opp)
            
            # Steps should have 3 entries
            self.assertEqual(len(opp["steps"]), 3)
    
    def test_triangular_path_format(self):
        """Test that triangular path is formatted correctly."""
        opportunities = self.detector.find_triangular_opportunities(base_asset="USDT")
        
        for opp in opportunities:
            # Path should contain arrows
            self.assertIn("→", opp["path"])
            # Path should start and end with base asset
            self.assertTrue(opp["path"].startswith("USDT"))
            self.assertTrue(opp["path"].endswith("USDT"))


class TestPriceTable(unittest.TestCase):
    """Tests for price table display."""
    
    def setUp(self):
        self.config = ArbitrageConfig(
            pairs=["BTC/USDT"],
            exchanges=["binance"],
            simulate=True
        )
        self.detector = ArbitrageDetector(self.config)
    
    @patch('builtins.print')
    def test_print_price_table(self, mock_print):
        """Test that price table prints without errors."""
        prices = self.detector.fetch_prices_multi_exchange()
        self.detector.print_price_table(prices)
        
        # Should have printed something
        self.assertTrue(mock_print.called)
    
    def test_print_price_table_with_fetch(self):
        """Test printing price table with auto-fetch."""
        # Should not raise
        try:
            self.detector.print_price_table()
        except Exception as e:
            self.fail(f"print_price_table raised {e}")


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""
    
    def test_empty_pairs(self):
        """Test detector with no pairs configured."""
        config = ArbitrageConfig(pairs=[], simulate=True)
        detector = ArbitrageDetector(config)
        
        prices = detector.fetch_prices_multi_exchange()
        self.assertEqual(prices, {})
        
        opportunities = detector.find_opportunities()
        self.assertEqual(opportunities, [])
    
    def test_empty_exchanges(self):
        """Test detector with no exchanges configured."""
        config = ArbitrageConfig(
            pairs=["BTC/USDT"],
            exchanges=[],
            simulate=True
        )
        detector = ArbitrageDetector(config)
        
        prices = detector.fetch_prices_multi_exchange()
        # Should have pair but no exchange data
        self.assertIn("BTC/USDT", prices)
        self.assertEqual(prices["BTC/USDT"], {})
    
    def test_zero_volume_profit(self):
        """Test profit calculation with zero volume."""
        config = ArbitrageConfig(simulate=True)
        detector = ArbitrageDetector(config)
        
        result = detector.calculate_profit(
            buy_price=50000.0,
            sell_price=50500.0,
            volume=0.0,
            buy_exchange="binance",
            sell_exchange="coinbase"
        )
        
        self.assertEqual(result["net_profit"], 0.0)
        self.assertFalse(result["is_profitable"])
    
    def test_same_exchange_arbitrage(self):
        """Test that same exchange is not considered for arbitrage."""
        config = ArbitrageConfig(
            pairs=["BTC/USDT"],
            exchanges=["binance"],
            simulate=True
        )
        detector = ArbitrageDetector(config)
        
        opportunities = detector.find_opportunities()
        
        # Should not find opportunities with same buy/sell exchange
        for opp in opportunities:
            self.assertNotEqual(opp["buy_exchange"], opp["sell_exchange"])


class TestRealPriceFetching(unittest.TestCase):
    """Tests for real price fetching (placeholder)."""
    
    def test_real_prices_not_implemented(self):
        """Test that real price fetching raises NotImplementedError."""
        config = ArbitrageConfig(simulate=False)
        detector = ArbitrageDetector(config)
        
        with self.assertRaises(NotImplementedError):
            detector.fetch_prices_multi_exchange()


class TestProfitAccuracy(unittest.TestCase):
    """Tests for profit calculation accuracy."""
    
    def setUp(self):
        self.config = ArbitrageConfig(
            trading_fees={"exchange_a": 0.001, "exchange_b": 0.002},
            slippage_percent=0.0  # No slippage for precise calculation
        )
        self.detector = ArbitrageDetector(self.config)
    
    def test_exact_profit_calculation(self):
        """Test exact profit calculation without slippage."""
        result = self.detector.calculate_profit(
            buy_price=1000.0,
            sell_price=1100.0,
            volume=1.0,
            buy_exchange="exchange_a",  # 0.1% fee
            sell_exchange="exchange_b",  # 0.2% fee
            include_withdrawal=False
        )
        
        # Gross profit: 1100 - 1000 = 100
        # Buy fee: 1000 * 0.001 = 1
        # Sell fee: 1100 * 0.002 = 2.2
        # Net profit: 100 - 1 - 2.2 = 96.8
        self.assertAlmostEqual(result["gross_profit"], 100.0, places=1)
        self.assertAlmostEqual(result["total_trading_fees"], 3.2, places=1)
        self.assertAlmostEqual(result["net_profit"], 96.8, places=1)
        self.assertTrue(result["is_profitable"])


def run_tests():
    """Run all tests with verbosity."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestArbitrageConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestArbitrageDetectorSimulation))
    suite.addTests(loader.loadTestsFromTestCase(TestTriangularArbitrage))
    suite.addTests(loader.loadTestsFromTestCase(TestPriceTable))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestRealPriceFetching))
    suite.addTests(loader.loadTestsFromTestCase(TestProfitAccuracy))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
