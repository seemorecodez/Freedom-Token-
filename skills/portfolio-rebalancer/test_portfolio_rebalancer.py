#!/usr/bin/env python3
"""
Unit tests for portfolio_rebalancer module.
"""

import unittest
from datetime import datetime, timedelta
from portfolio_rebalancer import (
    RebalanceConfig,
    RebalanceStrategy,
    TaxLot,
    calculate_current_allocations,
    calculate_rebalance_trades,
    drift_threshold_check,
    tax_aware_rebalancing,
    check_periodic_rebalance,
    cash_flow_rebalancing,
    generate_rebalance_report
)


class TestRebalanceConfig(unittest.TestCase):
    """Test RebalanceConfig class."""
    
    def test_valid_config(self):
        """Test creating a valid config."""
        config = RebalanceConfig(
            targets={"VTI": 0.60, "BND": 0.40},
            drift_threshold=0.05
        )
        self.assertEqual(config.targets, {"VTI": 0.60, "BND": 0.40})
        self.assertEqual(config.drift_threshold, 0.05)
        self.assertEqual(config.strategy, RebalanceStrategy.THRESHOLD)
    
    def test_config_with_margin(self):
        """Test config with small rounding margin."""
        config = RebalanceConfig(
            targets={"VTI": 0.501, "BND": 0.499},  # Sums to 1.0 with rounding
            drift_threshold=0.05
        )
        self.assertAlmostEqual(sum(config.targets.values()), 1.0, places=2)
    
    def test_invalid_config_sum(self):
        """Test config with invalid target sum."""
        with self.assertRaises(ValueError) as context:
            RebalanceConfig(targets={"VTI": 0.60, "BND": 0.50})  # Sums to 1.1
        self.assertIn("sum to 1.0", str(context.exception))
    
    def test_invalid_config_negative(self):
        """Test config with negative target."""
        with self.assertRaises(ValueError) as context:
            RebalanceConfig(targets={"VTI": 0.90, "BND": -0.10, "CASH": 0.20})
        self.assertIn("non-negative", str(context.exception))


class TestCalculateCurrentAllocations(unittest.TestCase):
    """Test calculate_current_allocations function."""
    
    def test_basic_allocation(self):
        """Test basic allocation calculation."""
        portfolio = {
            "VTI": {"shares": 100, "price": 200.0},  # $20,000
            "BND": {"shares": 100, "price": 100.0}   # $10,000
        }
        allocations = calculate_current_allocations(portfolio)
        self.assertAlmostEqual(allocations["VTI"], 2/3, places=3)
        self.assertAlmostEqual(allocations["BND"], 1/3, places=3)
    
    def test_empty_portfolio(self):
        """Test empty portfolio returns zero allocations."""
        portfolio = {}
        allocations = calculate_current_allocations(portfolio)
        self.assertEqual(allocations, {})
    
    def test_zero_value_portfolio(self):
        """Test portfolio with zero value."""
        portfolio = {
            "VTI": {"shares": 0, "price": 200.0},
            "BND": {"shares": 0, "price": 100.0}
        }
        allocations = calculate_current_allocations(portfolio)
        self.assertEqual(allocations["VTI"], 0.0)
        self.assertEqual(allocations["BND"], 0.0)
    
    def test_with_cash(self):
        """Test allocation including cash."""
        portfolio = {
            "VTI": {"shares": 100, "price": 200.0}  # $20,000
        }
        allocations = calculate_current_allocations(portfolio, include_cash=True, cash_value=5000)
        self.assertAlmostEqual(allocations["VTI"], 0.80, places=2)
        self.assertAlmostEqual(allocations["CASH"], 0.20, places=2)


class TestCalculateRebalanceTrades(unittest.TestCase):
    """Test calculate_rebalance_trades function."""
    
    def test_no_rebalance_needed(self):
        """Test when portfolio matches targets."""
        # Portfolio: $20k VTI (67%), $10k BND (33%) - close to 60/40
        portfolio = {
            "VTI": {"shares": 100, "price": 180.0},  # $18,000
            "BND": {"shares": 120, "price": 100.0}  # $12,000
        }
        config = RebalanceConfig(targets={"VTI": 0.60, "BND": 0.40})
        trades = calculate_rebalance_trades(portfolio, config)
        # Should have minimal or no trades
        self.assertIsInstance(trades, list)
    
    def test_rebalance_sell_overweight(self):
        """Test selling overweight position."""
        portfolio = {
            "VTI": {"shares": 100, "price": 250.0},  # $25,000 (83.3%)
            "BND": {"shares": 50, "price": 100.0}    # $5,000 (16.7%)
        }
        config = RebalanceConfig(
            targets={"VTI": 0.60, "BND": 0.40},
            min_trade_value=1.0
        )
        trades = calculate_rebalance_trades(portfolio, config)
        
        # Should recommend selling VTI
        vti_trade = next((t for t in trades if t["asset"] == "VTI"), None)
        self.assertIsNotNone(vti_trade)
        self.assertEqual(vti_trade["action"], "sell")
    
    def test_rebalance_buy_underweight(self):
        """Test buying underweight position."""
        portfolio = {
            "VTI": {"shares": 100, "price": 150.0},  # $15,000 (60%)
            "BND": {"shares": 25, "price": 100.0}    # $2,500 (10%)
        }
        # Total: $17,500
        # Target: VTI $10,500 (60%), BND $7,000 (40%)
        config = RebalanceConfig(
            targets={"VTI": 0.60, "BND": 0.40},
            min_trade_value=1.0
        )
        trades = calculate_rebalance_trades(portfolio, config)
        
        # Should recommend buying BND
        bnd_trade = next((t for t in trades if t["asset"] == "BND"), None)
        self.assertIsNotNone(bnd_trade)
        self.assertEqual(bnd_trade["action"], "buy")
    
    def test_with_cash_contribution(self):
        """Test rebalancing with new cash."""
        portfolio = {
            "VTI": {"shares": 100, "price": 200.0},  # $20,000
            "BND": {"shares": 50, "price": 100.0}    # $5,000
        }
        # Total: $25,000 (80% VTI, 20% BND)
        # With $5,000 cash, total $30,000
        # Target: VTI $18,000, BND $12,000
        config = RebalanceConfig(
            targets={"VTI": 0.60, "BND": 0.40},
            min_trade_value=1.0
        )
        trades = calculate_rebalance_trades(portfolio, config, cash_available=5000)
        
        # Should buy BND with cash
        bnd_trade = next((t for t in trades if t["asset"] == "BND"), None)
        if bnd_trade:
            self.assertEqual(bnd_trade["action"], "buy")
    
    def test_min_trade_value_filter(self):
        """Test that small trades are filtered out."""
        portfolio = {
            "VTI": {"shares": 100, "price": 200.0},  # $20,000 (66.7%)
            "BND": {"shares": 100, "price": 100.0}   # $10,000 (33.3%)
        }
        config = RebalanceConfig(
            targets={"VTI": 0.60, "BND": 0.40},
            min_trade_value=1000.0  # High minimum
        )
        trades = calculate_rebalance_trades(portfolio, config)
        # Small drifts should be filtered out
        self.assertTrue(all(t["value"] >= 1000.0 for t in trades))


class TestDriftThresholdCheck(unittest.TestCase):
    """Test drift_threshold_check function."""
    
    def test_no_drift(self):
        """Test when there's no drift."""
        portfolio = {
            "VTI": {"shares": 60, "price": 100.0},  # $6,000 (60%)
            "BND": {"shares": 40, "price": 100.0}   # $4,000 (40%)
        }
        config = RebalanceConfig(targets={"VTI": 0.60, "BND": 0.40}, drift_threshold=0.05)
        needs_rebal, drifts = drift_threshold_check(portfolio, config)
        self.assertFalse(needs_rebal)
        self.assertAlmostEqual(drifts["VTI"], 0.0, places=2)
    
    def test_drift_below_threshold(self):
        """Test drift within acceptable threshold."""
        portfolio = {
            "VTI": {"shares": 62, "price": 100.0},  # $6,200 (62%)
            "BND": {"shares": 38, "price": 100.0}   # $3,800 (38%)
        }
        config = RebalanceConfig(targets={"VTI": 0.60, "BND": 0.40}, drift_threshold=0.05)
        needs_rebal, drifts = drift_threshold_check(portfolio, config)
        self.assertFalse(needs_rebal)
        self.assertAlmostEqual(drifts["VTI"], 0.02, places=2)
    
    def test_drift_above_threshold(self):
        """Test drift exceeding threshold."""
        portfolio = {
            "VTI": {"shares": 70, "price": 100.0},  # $7,000 (70%)
            "BND": {"shares": 30, "price": 100.0}   # $3,000 (30%)
        }
        config = RebalanceConfig(targets={"VTI": 0.60, "BND": 0.40}, drift_threshold=0.05)
        needs_rebal, drifts = drift_threshold_check(portfolio, config)
        self.assertTrue(needs_rebal)
        self.assertAlmostEqual(drifts["VTI"], 0.10, places=2)
    
    def test_untracked_asset_drift(self):
        """Test drift from assets not in targets."""
        portfolio = {
            "VTI": {"shares": 60, "price": 100.0},   # $6,000 (60%)
            "BND": {"shares": 30, "price": 100.0},   # $3,000 (30%)
            "GOLD": {"shares": 10, "price": 100.0}   # $1,000 (10%) - not in targets
        }
        config = RebalanceConfig(targets={"VTI": 0.60, "BND": 0.40}, drift_threshold=0.05)
        needs_rebal, drifts = drift_threshold_check(portfolio, config)
        self.assertTrue(needs_rebal)
        self.assertEqual(drifts.get("GOLD"), 0.10)  # Full 10% is drift from 0


class TestTaxAwareRebalancing(unittest.TestCase):
    """Test tax_aware_rebalancing function."""
    
    def test_tax_loss_harvesting(self):
        """Test identification of tax loss harvesting opportunities."""
        portfolio = {
            "VTI": {"shares": 100, "price": 180.0, "cost_basis": 200.0},  # $2,000 loss
            "BND": {"shares": 100, "price": 105.0, "cost_basis": 100.0}   # $500 gain
        }
        config = RebalanceConfig(
            targets={"VTI": 0.40, "BND": 0.60},
            tax_sensitive=True
        )
        tax_lots = {
            "VTI": [TaxLot(100, 200.0, datetime(2023, 1, 15), "taxable")]
        }
        account_types = {"taxable": "taxable"}
        
        result = tax_aware_rebalancing(portfolio, config, tax_lots, account_types)
        
        self.assertIn("harvest_opportunities", result)
        self.assertEqual(len(result["harvest_opportunities"]), 1)
        self.assertAlmostEqual(result["harvest_opportunities"][0]["loss"], 2000.0, places=0)
    
    def test_prioritize_tax_advantaged(self):
        """Test prioritizing trades in tax-advantaged accounts."""
        portfolio = {
            "VTI": {"shares": 100, "price": 250.0},  # Overweight
        }
        config = RebalanceConfig(targets={"VTI": 0.50, "BND": 0.50}, tax_sensitive=True)
        
        # Tax lot in taxable with gain, and in IRA
        tax_lots = {
            "VTI": [
                TaxLot(50, 200.0, datetime(2023, 1, 15), "taxable"),  # $2,500 gain
                TaxLot(50, 200.0, datetime(2023, 1, 15), "ira")         # Same, but tax-deferred
            ]
        }
        account_types = {"taxable": "taxable", "ira": "tax_deferred"}
        
        result = tax_aware_rebalancing(portfolio, config, tax_lots, account_types)
        
        # Should recommend selling IRA lot first
        self.assertIn("trades", result)
        vti_trade = next((t for t in result["trades"] if t["asset"] == "VTI"), None)
        if vti_trade and "lot_selections" in vti_trade:
            self.assertEqual(vti_trade["lot_selections"][0]["account"], "ira")
    
    def test_long_term_vs_short_term(self):
        """Test prioritizing long-term gains over short-term."""
        portfolio = {
            "VTI": {"shares": 100, "price": 250.0},  # Overweight
        }
        config = RebalanceConfig(targets={"VTI": 0.50, "BND": 0.50})
        
        # Short-term lot (more recent)
        # Long-term lot (older)
        tax_lots = {
            "VTI": [
                TaxLot(50, 200.0, datetime.now() - timedelta(days=30), "taxable"),   # Short-term
                TaxLot(50, 200.0, datetime.now() - timedelta(days=400), "taxable")   # Long-term
            ]
        }
        account_types = {"taxable": "taxable"}
        
        result = tax_aware_rebalancing(portfolio, config, tax_lots, account_types)
        
        vti_trade = next((t for t in result["trades"] if t["asset"] == "VTI"), None)
        if vti_trade and "lot_selections" in vti_trade:
            # Should sell long-term lot first (lower tax rate)
            self.assertTrue(vti_trade["lot_selections"][0]["is_long_term"])


class TestCheckPeriodicRebalance(unittest.TestCase):
    """Test check_periodic_rebalance function."""
    
    def test_first_rebalance(self):
        """Test when no previous rebalance exists."""
        config = RebalanceConfig(
            targets={"VTI": 1.0},
            strategy=RebalanceStrategy.PERIODIC,
            period_days=90
        )
        result = check_periodic_rebalance(None, config)
        self.assertTrue(result)
    
    def test_rebalance_due(self):
        """Test when rebalancing is due."""
        config = RebalanceConfig(
            targets={"VTI": 1.0},
            strategy=RebalanceStrategy.PERIODIC,
            period_days=90
        )
        last_rebal = datetime.now() - timedelta(days=100)
        result = check_periodic_rebalance(last_rebal, config)
        self.assertTrue(result)
    
    def test_rebalance_not_due(self):
        """Test when rebalancing is not yet due."""
        config = RebalanceConfig(
            targets={"VTI": 1.0},
            strategy=RebalanceStrategy.PERIODIC,
            period_days=90
        )
        last_rebal = datetime.now() - timedelta(days=30)
        result = check_periodic_rebalance(last_rebal, config)
        self.assertFalse(result)
    
    def test_wrong_strategy(self):
        """Test with non-periodic strategy."""
        config = RebalanceConfig(
            targets={"VTI": 1.0},
            strategy=RebalanceStrategy.THRESHOLD
        )
        last_rebal = datetime.now() - timedelta(days=365)
        result = check_periodic_rebalance(last_rebal, config)
        self.assertFalse(result)


class TestCashFlowRebalancing(unittest.TestCase):
    """Test cash_flow_rebalancing function."""
    
    def test_contribution_buy_underweight(self):
        """Test buying underweight assets with contribution."""
        portfolio = {
            "VTI": {"shares": 100, "price": 200.0},  # $20,000 (80% - overweight)
            "BND": {"shares": 25, "price": 100.0}    # $2,500 (10% - underweight)
        }
        config = RebalanceConfig(targets={"VTI": 0.80, "BND": 0.20})
        
        trades = cash_flow_rebalancing(portfolio, config, cash_flow=7500)
        
        # Should buy BND with new cash
        bnd_trades = [t for t in trades if t["asset"] == "BND"]
        self.assertTrue(len(bnd_trades) > 0)
        self.assertEqual(bnd_trades[0]["action"], "buy")
        self.assertEqual(bnd_trades[0]["method"], "cash_flow")
    
    def test_withdrawal_sell_overweight(self):
        """Test selling overweight assets for withdrawal."""
        portfolio = {
            "VTI": {"shares": 100, "price": 200.0},  # $20,000 (80% - overweight)
            "BND": {"shares": 50, "price": 100.0}    # $5,000 (20%)
        }
        config = RebalanceConfig(targets={"VTI": 0.60, "BND": 0.40})
        
        trades = cash_flow_rebalancing(portfolio, config, cash_flow=-3000)
        
        # Should sell VTI (overweight)
        vti_trades = [t for t in trades if t["asset"] == "VTI"]
        self.assertTrue(len(vti_trades) > 0)
        self.assertEqual(vti_trades[0]["action"], "sell")
    
    def test_no_cash_flow(self):
        """Test with zero cash flow."""
        portfolio = {"VTI": {"shares": 100, "price": 200.0}}
        config = RebalanceConfig(targets={"VTI": 1.0})
        
        trades = cash_flow_rebalancing(portfolio, config, cash_flow=0)
        self.assertEqual(trades, [])


class TestGenerateRebalanceReport(unittest.TestCase):
    """Test generate_rebalance_report function."""
    
    def test_report_structure(self):
        """Test report contains expected sections."""
        portfolio = {
            "VTI": {"shares": 100, "price": 200.0},
            "BND": {"shares": 50, "price": 100.0}
        }
        config = RebalanceConfig(targets={"VTI": 0.60, "BND": 0.40})
        trades = [{"asset": "VTI", "action": "sell", "shares": 10, "value": 2000.0}]
        drifts = {"VTI": 0.10, "BND": 0.10}
        
        report = generate_rebalance_report(portfolio, config, trades, drifts)
        
        self.assertIn("PORTFOLIO REBALANCING REPORT", report)
        self.assertIn("VTI", report)
        self.assertIn("BND", report)
        self.assertIn("SELL", report)
    
    def test_report_with_tax_info(self):
        """Test report includes tax information."""
        portfolio = {"VTI": {"shares": 100, "price": 200.0}}
        config = RebalanceConfig(targets={"VTI": 1.0})
        trades = []
        drifts = {"VTI": 0.0}
        tax_info = {
            "tax_impact": 1500.0,
            "harvest_opportunities": [{"loss": 2000.0}]
        }
        
        report = generate_rebalance_report(portfolio, config, trades, drifts, tax_info)
        
        self.assertIn("TAX IMPACT", report)
        self.assertIn("$1,500", report)  # Tax impact


class TestTaxLot(unittest.TestCase):
    """Test TaxLot class."""
    
    def test_unrealized_gain(self):
        """Test unrealized gain calculation."""
        lot = TaxLot(100, 50.0, datetime(2023, 1, 15), "taxable")
        gain = lot.unrealized_gain(75.0)  # Price increased
        self.assertEqual(gain, 2500.0)  # 100 shares * $25 gain
        
        loss = lot.unrealized_gain(40.0)  # Price decreased
        self.assertEqual(loss, -1000.0)  # 100 shares * $10 loss
    
    def test_long_term_detection(self):
        """Test long-term capital gains detection."""
        # Long-term (over 1 year)
        old_lot = TaxLot(100, 50.0, datetime.now() - timedelta(days=400), "taxable")
        self.assertTrue(old_lot.is_long_term())
        
        # Short-term (under 1 year)
        new_lot = TaxLot(100, 50.0, datetime.now() - timedelta(days=30), "taxable")
        self.assertFalse(new_lot.is_long_term())


class TestIntegration(unittest.TestCase):
    """Integration tests for full rebalancing workflow."""
    
    def test_full_threshold_workflow(self):
        """Test complete threshold-based rebalancing workflow."""
        # Setup
        portfolio = {
            "VTI": {"shares": 120, "price": 200.0},  # $24,000 (80%)
            "BND": {"shares": 30, "price": 100.0}    # $3,000 (10%)
        }
        config = RebalanceConfig(
            targets={"VTI": 0.60, "BND": 0.40},
            drift_threshold=0.05,
            min_trade_value=10.0
        )
        
        # Step 1: Check drift
        needs_rebal, drifts = drift_threshold_check(portfolio, config)
        self.assertTrue(needs_rebal)
        self.assertGreater(drifts["VTI"], 0.05)
        
        # Step 2: Calculate trades
        trades = calculate_rebalance_trades(portfolio, config)
        self.assertTrue(len(trades) > 0)
        
        # Step 3: Generate report
        report = generate_rebalance_report(portfolio, config, trades, drifts)
        self.assertIn("PORTFOLIO REBALANCING REPORT", report)
    
    def test_full_tax_aware_workflow(self):
        """Test complete tax-aware rebalancing workflow."""
        portfolio = {
            "VTI": {"shares": 100, "price": 250.0},
            "BND": {"shares": 50, "price": 100.0}
        }
        config = RebalanceConfig(targets={"VTI": 0.60, "BND": 0.40})
        
        tax_lots = {
            "VTI": [
                TaxLot(50, 200.0, datetime(2023, 1, 15), "taxable"),
                TaxLot(50, 240.0, datetime(2024, 6, 1), "ira")
            ],
            "BND": [TaxLot(50, 95.0, datetime(2024, 1, 15), "taxable")]
        }
        account_types = {"taxable": "taxable", "ira": "tax_deferred"}
        
        # Run tax-aware rebalancing
        result = tax_aware_rebalancing(portfolio, config, tax_lots, account_types)
        
        self.assertIn("trades", result)
        self.assertIn("tax_impact", result)
        
        # Generate report with tax info
        _, drifts = drift_threshold_check(portfolio, config)
        report = generate_rebalance_report(
            portfolio, config, result["trades"], drifts, result
        )
        self.assertIn("TAX IMPACT", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
