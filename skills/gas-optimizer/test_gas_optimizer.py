"""
Unit tests for Gas Optimizer skill.

Run with: python -m pytest test_gas_optimizer.py -v
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from gas_optimizer import (
    GasOptimizer,
    GasConfig,
    GasStrategy,
    GasEstimate,
    TimingRecommendation,
    EIP1559Fees,
    GasHistory,
    BatchingRecommendation,
    GasOptimizationError,
    GasConfigError,
    quick_estimate,
    get_recommended_fees,
    should_wait_for_better_fees,
)


class TestGasConfig:
    """Tests for GasConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = GasConfig()
        assert config.max_fee_gwei == 100.0
        assert config.priority_fee_gwei == 2.0
        assert config.strategy == GasStrategy.STANDARD
        assert config.max_wait_minutes == 60
        assert config.rpc_url is None
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = GasConfig(
            max_fee_gwei=200.0,
            priority_fee_gwei=5.0,
            strategy=GasStrategy.AGGRESSIVE,
            max_wait_minutes=120,
            rpc_url="https://mainnet.infura.io/v3/test"
        )
        assert config.max_fee_gwei == 200.0
        assert config.priority_fee_gwei == 5.0
        assert config.strategy == GasStrategy.AGGRESSIVE
        assert config.max_wait_minutes == 120
        assert config.rpc_url == "https://mainnet.infura.io/v3/test"
    
    def test_invalid_max_fee(self):
        """Test validation of negative max fee."""
        with pytest.raises(GasConfigError, match="max_fee_gwei must be positive"):
            GasConfig(max_fee_gwei=0)
        
        with pytest.raises(GasConfigError, match="max_fee_gwei must be positive"):
            GasConfig(max_fee_gwei=-10)
    
    def test_invalid_priority_fee(self):
        """Test validation of negative priority fee."""
        with pytest.raises(GasConfigError, match="priority_fee_gwei cannot be negative"):
            GasConfig(priority_fee_gwei=-1)
    
    def test_invalid_wait_time(self):
        """Test validation of wait time."""
        with pytest.raises(GasConfigError, match="max_wait_minutes must be at least 1"):
            GasConfig(max_wait_minutes=0)


class TestGasOptimizerInitialization:
    """Tests for GasOptimizer initialization."""
    
    def test_default_initialization(self):
        """Test initialization with default config."""
        optimizer = GasOptimizer()
        assert optimizer.config is not None
        assert optimizer.config.strategy == GasStrategy.STANDARD
    
    def test_custom_initialization(self):
        """Test initialization with custom config."""
        config = GasConfig(strategy=GasStrategy.ECONOMIC)
        optimizer = GasOptimizer(config)
        assert optimizer.config == config
        assert optimizer.config.strategy == GasStrategy.ECONOMIC


class TestEstimateGas:
    """Tests for gas estimation functionality."""
    
    def test_simple_transfer_estimate(self):
        """Test gas estimation for simple ETH transfer."""
        optimizer = GasOptimizer()
        tx_data = {"to": "0x1234567890123456789012345678901234567890", "value": 1000}
        
        estimate = optimizer.estimate_gas(tx_data)
        
        assert isinstance(estimate, GasEstimate)
        assert estimate.gas_limit == 21000  # Standard transfer gas
        assert estimate.total_cost_eth > 0
        assert 0 <= estimate.confidence <= 1
    
    def test_contract_interaction_estimate(self):
        """Test gas estimation for contract interaction."""
        optimizer = GasOptimizer()
        tx_data = {
            "to": "0x1234567890123456789012345678901234567890",
            "data": "0xa9059cbb" + "00" * 100,  # ERC20 transfer with padding
            "value": 0
        }
        
        estimate = optimizer.estimate_gas(tx_data)
        
        assert isinstance(estimate, GasEstimate)
        assert estimate.gas_limit > 21000  # Contract calls use more gas
        assert estimate.total_cost_eth > 0
    
    def test_strategy_affects_priority_fee(self):
        """Test that strategy affects priority fee in estimate."""
        tx_data = {"to": "0x1234567890123456789012345678901234567890", "value": 1000}
        
        aggressive_config = GasConfig(strategy=GasStrategy.AGGRESSIVE, priority_fee_gwei=2.0)
        economic_config = GasConfig(strategy=GasStrategy.ECONOMIC, priority_fee_gwei=2.0)
        
        aggressive_optimizer = GasOptimizer(aggressive_config)
        economic_optimizer = GasOptimizer(economic_config)
        
        aggressive_estimate = aggressive_optimizer.estimate_gas(tx_data)
        economic_estimate = economic_optimizer.estimate_gas(tx_data)
        
        # Aggressive should have higher priority fee
        assert aggressive_estimate.priority_fee_gwei > economic_estimate.priority_fee_gwei
    
    def test_estimate_with_different_strategies(self):
        """Test estimates for all strategy types."""
        tx_data = {"to": "0x1234567890123456789012345678901234567890", "value": 1000}
        
        for strategy in GasStrategy:
            config = GasConfig(strategy=strategy)
            optimizer = GasOptimizer(config)
            estimate = optimizer.estimate_gas(tx_data)
            
            assert isinstance(estimate, GasEstimate)
            assert estimate.gas_limit > 0
            assert estimate.total_cost_eth >= 0


class TestCalculateEIP1559Fees:
    """Tests for EIP-1559 fee calculation."""
    
    def test_fee_structure(self):
        """Test that EIP-1559 fees have correct structure."""
        optimizer = GasOptimizer()
        fees = optimizer.calculate_eip1559_fees()
        
        assert isinstance(fees, EIP1559Fees)
        assert fees.maxFeePerGas > 0
        assert fees.maxPriorityFeePerGas > 0
        assert fees.baseFeePerGas > 0
        assert fees.maxFeePerGas >= fees.maxPriorityFeePerGas
        assert fees.estimated_confirmation_blocks > 0
    
    def test_aggressive_strategy_fees(self):
        """Test that aggressive strategy yields higher fees."""
        aggressive_config = GasConfig(strategy=GasStrategy.AGGRESSIVE, priority_fee_gwei=2.0)
        economic_config = GasConfig(strategy=GasStrategy.ECONOMIC, priority_fee_gwei=2.0)
        
        aggressive_optimizer = GasOptimizer(aggressive_config)
        economic_optimizer = GasOptimizer(economic_config)
        
        aggressive_fees = aggressive_optimizer.calculate_eip1559_fees()
        economic_fees = economic_optimizer.calculate_eip1559_fees()
        
        # Aggressive should have higher priority fee
        assert aggressive_fees.maxPriorityFeePerGas > economic_fees.maxPriorityFeePerGas
        # Aggressive should confirm faster
        assert aggressive_fees.estimated_confirmation_blocks <= economic_fees.estimated_confirmation_blocks
    
    def test_max_fee_cap(self):
        """Test that max fee respects configuration cap."""
        config = GasConfig(max_fee_gwei=50.0)
        optimizer = GasOptimizer(config)
        
        fees = optimizer.calculate_eip1559_fees()
        
        max_fee_gwei = fees.maxFeePerGas / 1e9
        assert max_fee_gwei <= 50.0


class TestGetOptimalTiming:
    """Tests for optimal timing recommendations."""
    
    def test_timing_recommendation_structure(self):
        """Test that timing recommendation has correct structure."""
        optimizer = GasOptimizer()
        recommendation = optimizer.get_optimal_timing()
        
        assert isinstance(recommendation, TimingRecommendation)
        assert isinstance(recommendation.best_time, datetime)
        assert recommendation.expected_base_fee_gwei > 0
        assert 0 <= recommendation.savings_percent <= 100
        assert 0 <= recommendation.confidence <= 1
        assert len(recommendation.reason) > 0
    
    def test_future_time(self):
        """Test that recommended time is in the future."""
        optimizer = GasOptimizer()
        recommendation = optimizer.get_optimal_timing()
        
        now = datetime.now()
        assert recommendation.best_time >= now - timedelta(minutes=1)  # Allow small tolerance
    
    def test_lookahead_respected(self):
        """Test that lookahead parameter is respected."""
        optimizer = GasOptimizer()
        
        short_lookahead = optimizer.get_optimal_timing(lookahead_hours=1)
        long_lookahead = optimizer.get_optimal_timing(lookahead_hours=48)
        
        now = datetime.now()
        assert short_lookahead.best_time <= now + timedelta(hours=2)


class TestCheckGasHistory:
    """Tests for gas history analysis."""
    
    def test_history_structure(self):
        """Test that gas history has correct structure."""
        optimizer = GasOptimizer()
        history = optimizer.check_gas_history(days=7)
        
        assert isinstance(history, GasHistory)
        assert len(history.entries) == 7 * 24  # Hourly entries
        assert history.average_base_fee > 0
        assert history.min_base_fee > 0
        assert history.max_base_fee > 0
        assert history.min_base_fee <= history.average_base_fee <= history.max_base_fee
        assert history.trend in ["rising", "falling", "stable"]
    
    def test_different_periods(self):
        """Test history for different time periods."""
        optimizer = GasOptimizer()
        
        week_history = optimizer.check_gas_history(days=7)
        day_history = optimizer.check_gas_history(days=1)
        
        assert len(week_history.entries) == 7 * 24
        assert len(day_history.entries) == 1 * 24
    
    def test_entry_structure(self):
        """Test that history entries have correct structure."""
        optimizer = GasOptimizer()
        history = optimizer.check_gas_history(days=1)
        
        for entry in history.entries:
            assert isinstance(entry.timestamp, datetime)
            assert entry.base_fee_gwei > 0
            assert entry.priority_fee_gwei >= 0
            assert entry.block_number > 0


class TestRecommendBatching:
    """Tests for batching recommendations."""
    
    def test_empty_transactions(self):
        """Test batching with empty transaction list."""
        optimizer = GasOptimizer()
        recommendation = optimizer.recommend_batching([])
        
        assert isinstance(recommendation, BatchingRecommendation)
        assert recommendation.should_batch is False
        assert recommendation.optimal_batch_size == 1
        assert recommendation.estimated_savings_eth == 0.0
    
    def test_single_transaction(self):
        """Test batching with single transaction."""
        optimizer = GasOptimizer()
        transactions = [{"to": "0x123...", "value": 100}]
        
        recommendation = optimizer.recommend_batching(transactions)
        
        assert isinstance(recommendation, BatchingRecommendation)
        assert recommendation.should_batch is False  # Can't batch one tx
        assert recommendation.optimal_batch_size == 1
    
    def test_multiple_transfers(self):
        """Test batching with multiple simple transfers."""
        optimizer = GasOptimizer()
        transactions = [
            {"to": "0x123...", "value": 100},
            {"to": "0x456...", "value": 200},
            {"to": "0x789...", "value": 300},
        ]
        
        recommendation = optimizer.recommend_batching(transactions)
        
        assert isinstance(recommendation, BatchingRecommendation)
        assert recommendation.should_batch is True
        assert recommendation.optimal_batch_size > 1
        assert recommendation.estimated_savings_eth >= 0
    
    def test_mixed_transactions(self):
        """Test batching with mixed transaction types."""
        optimizer = GasOptimizer()
        transactions = [
            {"to": "0x123...", "value": 100},  # Simple transfer
            {"to": "0x456...", "data": "0xa9059cbb", "value": 0},  # Contract call
            {"to": "0x789...", "value": 300},  # Simple transfer
        ]
        
        recommendation = optimizer.recommend_batching(transactions)
        
        assert isinstance(recommendation, BatchingRecommendation)
        assert len(recommendation.batching_strategy) > 0


class TestNetworkConditions:
    """Tests for network condition reporting."""
    
    def test_conditions_structure(self):
        """Test that network conditions report has correct structure."""
        optimizer = GasOptimizer()
        conditions = optimizer.get_current_network_conditions()
        
        assert "base_fee_gwei" in conditions
        assert "network_congestion" in conditions
        assert "suggested_strategy" in conditions
        assert "current_time" in conditions
        assert "recommendation" in conditions
        
        assert isinstance(conditions["base_fee_gwei"], float)
        assert 0 <= conditions["network_congestion"] <= 1


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_quick_estimate(self):
        """Test quick estimate function."""
        estimate = quick_estimate("standard")
        
        assert isinstance(estimate, GasEstimate)
        assert estimate.gas_limit > 0
    
    def test_quick_estimate_all_strategies(self):
        """Test quick estimate with all strategies."""
        for strategy in ["aggressive", "standard", "economic"]:
            estimate = quick_estimate(strategy)
            assert isinstance(estimate, GasEstimate)
    
    def test_get_recommended_fees(self):
        """Test get recommended fees function."""
        fees = get_recommended_fees("standard")
        
        assert isinstance(fees, EIP1559Fees)
        assert fees.maxFeePerGas > 0
        assert fees.maxPriorityFeePerGas > 0
    
    def test_should_wait_low_urgency_high_fee(self):
        """Test waiting recommendation for low urgency with high fees."""
        assert should_wait_for_better_fees(50.0, "low") is True
        assert should_wait_for_better_fees(100.0, "low") is True
    
    def test_should_wait_normal_urgency_very_high_fee(self):
        """Test waiting recommendation for normal urgency with very high fees."""
        assert should_wait_for_better_fees(60.0, "normal") is True
        assert should_wait_for_better_fees(40.0, "normal") is False
    
    def test_should_not_wait_high_urgency(self):
        """Test that high urgency never recommends waiting."""
        assert should_wait_for_better_fees(100.0, "high") is False
        assert should_wait_for_better_fees(20.0, "high") is False
    
    def test_should_not_wait_low_fee(self):
        """Test that low fees don't recommend waiting."""
        assert should_wait_for_better_fees(10.0, "low") is False
        assert should_wait_for_better_fees(15.0, "normal") is False


class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_very_high_gas_limit_estimate(self):
        """Test estimation with very large data payload."""
        optimizer = GasOptimizer()
        tx_data = {
            "to": "0x123...",
            "data": "0x" + "00" * 2000,  # Very large data
            "value": 0
        }
        
        estimate = optimizer.estimate_gas(tx_data)
        assert estimate.gas_limit >= 250000  # Should use high gas estimate
    
    def test_max_fee_enforcement(self):
        """Test that configured max fee is always respected."""
        config = GasConfig(max_fee_gwei=10.0, strategy=GasStrategy.AGGRESSIVE)
        optimizer = GasOptimizer(config)
        
        fees = optimizer.calculate_eip1559_fees()
        max_fee_gwei = fees.maxFeePerGas / 1e9
        
        assert max_fee_gwei <= 10.0
    
    def test_gas_history_with_different_days(self):
        """Test gas history with various day parameters."""
        optimizer = GasOptimizer()
        
        for days in [1, 3, 7, 14, 30]:
            history = optimizer.check_gas_history(days=days)
            assert len(history.entries) == days * 24


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
