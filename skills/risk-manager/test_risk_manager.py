"""
Unit tests for the Risk Manager module.

Run with: python -m pytest test_risk_manager.py -v
"""

import pytest
from datetime import datetime, date
from risk_manager import (
    RiskConfig, RiskManager, Position, TradeResult,
    calculate_position_size, check_stop_loss, check_daily_limit,
    calculate_drawdown, calculate_risk_reward_ratio, calculate_expectancy,
    RiskAction
)


class TestRiskConfig:
    """Tests for RiskConfig dataclass."""
    
    def test_default_config(self):
        config = RiskConfig()
        assert config.max_position_pct == 0.20
        assert config.stop_loss_pct == 0.02
        assert config.take_profit_pct == 0.06
        assert config.daily_loss_limit_pct == 0.05
        assert config.max_trades_per_day == 10
        assert config.kelly_fraction == 0.25
    
    def test_custom_config(self):
        config = RiskConfig(
            max_position_pct=0.10,
            stop_loss_pct=0.05,
            daily_loss_limit_pct=0.03,
            max_trades_per_day=5
        )
        assert config.max_position_pct == 0.10
        assert config.stop_loss_pct == 0.05
        assert config.daily_loss_limit_pct == 0.03
        assert config.max_trades_per_day == 5


class TestCalculatePositionSize:
    """Tests for position sizing calculations."""
    
    def test_fixed_fractional_basic(self):
        result = calculate_position_size(
            account_value=100000,
            method='fixed_fractional',
            risk_per_trade_pct=0.01,
            entry_price=100,
            stop_price=98,
            max_position_pct=1.0  # Allow full position for this test
        )
        assert result['valid'] is True
        assert result['position_size'] == 500.0  # $1000 risk / $2 per share
        assert result['risk_amount'] == 1000.0
        assert result['risk_pct'] == 0.01
    
    def test_fixed_fractional_max_position_limit(self):
        result = calculate_position_size(
            account_value=100000,
            method='fixed_fractional',
            risk_per_trade_pct=0.10,  # 10% risk
            entry_price=100,
            stop_price=99,  # $1 stop
            max_position_pct=0.20  # But max 20% position
        )
        assert result['valid'] is True
        # Should be capped at 20% of account = $20,000 = 200 shares
        assert result['position_value'] == 20000.0
        assert result['position_size'] == 200.0
    
    def test_fixed_fractional_below_minimum(self):
        result = calculate_position_size(
            account_value=10000,
            method='fixed_fractional',
            risk_per_trade_pct=0.001,  # Very small risk
            entry_price=1000,
            stop_price=999.99,  # Tiny stop
            min_position_size=10.0
        )
        assert result['valid'] is False
        assert 'below minimum' in result['reason']
    
    def test_fixed_fractional_zero_risk_per_share(self):
        result = calculate_position_size(
            account_value=100000,
            method='fixed_fractional',
            risk_per_trade_pct=0.01,
            entry_price=100,
            stop_price=100  # Same as entry
        )
        assert result['valid'] is False
        assert 'equal' in result['reason']
    
    def test_kelly_criterion_basic(self):
        result = calculate_position_size(
            account_value=100000,
            method='kelly',
            win_rate=0.55,
            avg_win=300,
            avg_loss=100,
            kelly_fraction=0.25
        )
        assert result['valid'] is True
        # Kelly = (0.55 * 3 - 0.45) / 3 = 0.4
        # 1/4 Kelly = 0.1 = 10%
        assert abs(result['risk_pct'] - 0.10) < 1e-10
        assert abs(result['position_value'] - 10000.0) < 1e-6
    
    def test_kelly_negative_expectancy(self):
        result = calculate_position_size(
            account_value=100000,
            method='kelly',
            win_rate=0.40,  # Low win rate
            avg_win=100,
            avg_loss=200,   # Big losses
            kelly_fraction=0.25
        )
        assert result['valid'] is False
        assert 'no position' in result['reason']
    
    def test_kelly_invalid_win_rate(self):
        result = calculate_position_size(
            account_value=100000,
            method='kelly',
            win_rate=1.5,  # Invalid
            avg_win=100,
            avg_loss=100
        )
        assert result['valid'] is False
        assert 'Win rate' in result['reason']
    
    def test_invalid_account_value(self):
        result = calculate_position_size(
            account_value=0,
            method='fixed_fractional',
            risk_per_trade_pct=0.01,
            entry_price=100,
            stop_price=98
        )
        assert result['valid'] is False
        assert 'Invalid account' in result['reason']


class TestCheckStopLoss:
    """Tests for stop loss monitoring."""
    
    def test_long_stop_triggered(self):
        result = check_stop_loss(
            entry_price=100,
            current_price=97,
            stop_price=98,
            position_side='long'
        )
        assert result['action'] == RiskAction.STOP_TRIGGERED.value
        assert 'Stop loss hit' in result['reason']
        assert result['exit_price'] == 97
    
    def test_long_stop_not_triggered(self):
        result = check_stop_loss(
            entry_price=100,
            current_price=99,
            stop_price=98,
            position_side='long'
        )
        assert result['action'] == RiskAction.HOLD.value
        assert result['exit_price'] is None
    
    def test_short_stop_triggered(self):
        result = check_stop_loss(
            entry_price=100,
            current_price=103,
            stop_price=102,
            position_side='short'
        )
        assert result['action'] == RiskAction.STOP_TRIGGERED.value
        assert result['exit_price'] == 103
    
    def test_target_hit_long(self):
        result = check_stop_loss(
            entry_price=100,
            current_price=106,
            stop_price=98,
            target_price=106,
            position_side='long'
        )
        assert result['action'] == RiskAction.TARGET_HIT.value
        assert result['exit_price'] == 106
    
    def test_trailing_stop_long(self):
        result = check_stop_loss(
            entry_price=100,
            current_price=104,  # Dropped from 110
            stop_price=98,
            position_side='long',
            trailing_stop_pct=0.05,  # 5% trailing
            highest_price=110  # Peak was 110
        )
        # Trailing stop = 110 * 0.95 = 104.5
        # Current 104 < 104.5, should trigger
        assert result['action'] == RiskAction.TRAIL_STOP.value
    
    def test_trailing_stop_not_triggered(self):
        result = check_stop_loss(
            entry_price=100,
            current_price=105,  # Still above trailing stop
            stop_price=98,
            position_side='long',
            trailing_stop_pct=0.05,
            highest_price=110  # Trailing stop at 104.5
        )
        assert result['action'] == RiskAction.HOLD.value
    
    def test_price_tracking(self):
        result = check_stop_loss(
            entry_price=100,
            current_price=105,
            stop_price=98,
            position_side='long',
            highest_price=103,
            lowest_price=99
        )
        assert result['updated_highest'] == 105
        assert result['updated_lowest'] == 99


class TestCheckDailyLimit:
    """Tests for daily trading limits."""
    
    def test_daily_loss_limit_not_exceeded(self):
        result = check_daily_limit(
            daily_pnl=-1000,
            account_value=100000,
            daily_loss_limit_pct=0.05  # $5000 limit
        )
        assert result['allowed'] is True
        assert result['reason'] == ''
    
    def test_daily_loss_limit_exceeded(self):
        result = check_daily_limit(
            daily_pnl=-6000,
            account_value=100000,
            daily_loss_limit_pct=0.05  # $5000 limit
        )
        assert result['allowed'] is False
        assert 'Daily loss limit exceeded' in result['reason']
        assert 'daily_loss' in result['limits']
    
    def test_max_trades_reached(self):
        result = check_daily_limit(
            daily_pnl=0,
            account_value=100000,
            daily_loss_limit_pct=0.05,
            trades_today=10,
            max_trades_per_day=10
        )
        assert result['allowed'] is False
        assert 'Max trades' in result['reason']
    
    def test_consecutive_losses_exceeded(self):
        result = check_daily_limit(
            daily_pnl=-1000,
            account_value=100000,
            daily_loss_limit_pct=0.05,
            consecutive_losses=3,
            max_consecutive_losses=3
        )
        assert result['allowed'] is False
        assert 'consecutive losses' in result['reason']
    
    def test_exactly_at_limit(self):
        result = check_daily_limit(
            daily_pnl=-5000,  # Exactly at limit
            account_value=100000,
            daily_loss_limit_pct=0.05
        )
        assert result['allowed'] is False
        assert 'exceeded' in result['reason']


class TestCalculateDrawdown:
    """Tests for drawdown calculations."""
    
    def test_no_drawdown(self):
        result = calculate_drawdown(
            current_equity=100000,
            peak_equity=100000
        )
        assert result['drawdown_pct'] == 0.0
        assert result['drawdown_amount'] == 0.0
        assert result['in_drawdown'] is False
    
    def test_drawdown_detected(self):
        result = calculate_drawdown(
            current_equity=95000,
            peak_equity=100000
        )
        assert result['drawdown_pct'] == 0.05
        assert result['drawdown_amount'] == 5000.0
        assert result['in_drawdown'] is True
    
    def test_small_drawdown_not_counted(self):
        result = calculate_drawdown(
            current_equity=99500,
            peak_equity=100000
        )
        assert result['drawdown_pct'] == 0.005  # 0.5%
        # Less than 1% threshold, but still flagged due to > 0.01 check
        # Actually, 0.005 < 0.01, so in_drawdown should be False
        # Wait, let me check the code... it uses > 0.01 (1%)
        # 0.005 is 0.5%, which is less than 1%
        assert result['in_drawdown'] is False
    
    def test_invalid_peak_equity(self):
        result = calculate_drawdown(
            current_equity=100000,
            peak_equity=0
        )
        assert result['drawdown_pct'] == 0.0


class TestCalculateRiskRewardRatio:
    """Tests for risk/reward ratio calculations."""
    
    def test_long_position(self):
        rr = calculate_risk_reward_ratio(
            entry_price=100,
            stop_price=98,
            target_price=106,
            position_side='long'
        )
        assert rr == 3.0  # Risk $2, Reward $6
    
    def test_short_position(self):
        rr = calculate_risk_reward_ratio(
            entry_price=100,
            stop_price=103,
            target_price=94,
            position_side='short'
        )
        assert rr == 2.0  # Risk $3, Reward $6
    
    def test_zero_risk(self):
        rr = calculate_risk_reward_ratio(
            entry_price=100,
            stop_price=100,
            target_price=110,
            position_side='long'
        )
        assert rr == 0.0


class TestCalculateExpectancy:
    """Tests for expectancy calculations."""
    
    def test_positive_expectancy(self):
        # 50% win rate, avg win $200, avg loss $100
        # Expectancy = (0.5 * 200) - (0.5 * 100) = 50
        exp = calculate_expectancy(0.50, 200, 100)
        assert exp == 50.0
    
    def test_negative_expectancy(self):
        # 40% win rate, avg win $100, avg loss $100
        # Expectancy = (0.4 * 100) - (0.6 * 100) = -20
        exp = calculate_expectancy(0.40, 100, 100)
        assert exp == -20.0
    
    def test_zero_expectancy(self):
        # 50% win rate, equal wins and losses
        exp = calculate_expectancy(0.50, 100, 100)
        assert exp == 0.0


class TestRiskManager:
    """Integration tests for the RiskManager class."""
    
    def test_initialization(self):
        config = RiskConfig()
        manager = RiskManager(config)
        assert manager.config == config
        assert manager.positions == {}
        assert manager.trade_history == []
    
    def test_validate_trade_passes(self):
        manager = RiskManager()
        manager.update_equity(100000)
        
        trade = {
            'symbol': 'AAPL',
            'entry_price': 150,
            'stop_price': 145,
            'target_price': 165,
            'side': 'long',
            'account_value': 100000
        }
        
        result = manager.validate_trade(trade)
        assert result['allowed'] is True
        assert result['position_size'] > 0
        assert result['risk_reward_ratio'] == 3.0
    
    def test_validate_trade_fails_risk_reward(self):
        manager = RiskManager()
        manager.update_equity(100000)
        
        trade = {
            'symbol': 'AAPL',
            'entry_price': 150,
            'stop_price': 145,  # $5 risk
            'target_price': 152,  # $2 reward
            'side': 'long',
            'account_value': 100000
        }
        
        result = manager.validate_trade(trade)
        assert result['allowed'] is False
        assert 'Risk/reward ratio' in result['reason']
    
    def test_validate_trade_fails_daily_limit(self):
        config = RiskConfig(daily_loss_limit_pct=0.05)
        manager = RiskManager(config)
        manager.update_equity(100000)
        manager.daily_stats['pnl'] = -6000  # Exceeds 5% limit
        
        trade = {
            'symbol': 'AAPL',
            'entry_price': 150,
            'stop_price': 145,
            'target_price': 165,
            'side': 'long',
            'account_value': 100000
        }
        
        result = manager.validate_trade(trade)
        assert result['allowed'] is False
        assert 'Daily loss limit' in result['reason']
    
    def test_validate_trade_fails_max_positions(self):
        config = RiskConfig(max_positions=2)
        manager = RiskManager(config)
        manager.update_equity(100000)
        
        # Add two positions
        manager.positions['AAPL'] = Position('AAPL', 'long', 150, 145)
        manager.positions['TSLA'] = Position('TSLA', 'long', 200, 190)
        
        trade = {
            'symbol': 'MSFT',
            'entry_price': 300,
            'stop_price': 295,
            'side': 'long',
            'account_value': 100000
        }
        
        result = manager.validate_trade(trade)
        assert result['allowed'] is False
        assert 'Max positions' in result['reason']
    
    def test_validate_trade_duplicate_symbol(self):
        manager = RiskManager()
        manager.update_equity(100000)
        manager.positions['AAPL'] = Position('AAPL', 'long', 150, 145)
        
        trade = {
            'symbol': 'AAPL',
            'entry_price': 160,
            'stop_price': 155,
            'side': 'long',
            'account_value': 100000
        }
        
        result = manager.validate_trade(trade)
        assert result['allowed'] is False
        assert 'already exists' in result['reason']
    
    def test_enter_position(self):
        manager = RiskManager()
        position = Position('AAPL', 'long', 150, 145, size=100)
        
        result = manager.enter_position(position)
        assert result['success'] is True
        assert 'AAPL' in manager.positions
        assert manager.daily_stats['trades'] == 1
    
    def test_update_position_stop_triggered(self):
        manager = RiskManager()
        manager.update_equity(100000)
        position = Position('AAPL', 'long', 150, 145, size=100)
        manager.positions['AAPL'] = position
        
        result = manager.update_position('AAPL', current_price=144)
        assert result['action'] == RiskAction.STOP_TRIGGERED.value
        assert 'AAPL' not in manager.positions  # Position closed
    
    def test_update_position_target_hit(self):
        manager = RiskManager()
        manager.update_equity(100000)
        position = Position('AAPL', 'long', 150, 145, target_price=160, size=100)
        manager.positions['AAPL'] = position
        
        result = manager.update_position('AAPL', current_price=160)
        assert result['action'] == RiskAction.TARGET_HIT.value
        assert result['pnl'] == 1000.0  # (160 - 150) * 100
    
    def test_close_position(self):
        manager = RiskManager()
        manager.update_equity(100000)
        position = Position('AAPL', 'long', 150, 145, size=100)
        manager.positions['AAPL'] = position
        
        result = manager.close_position('AAPL', 155, 'manual')
        assert result['success'] is True
        assert result['pnl'] == 500.0  # (155 - 150) * 100
        assert result['pnl_pct'] == 500.0 / 15000.0
        assert 'AAPL' not in manager.positions
        assert len(manager.trade_history) == 1
    
    def test_close_position_not_found(self):
        manager = RiskManager()
        result = manager.close_position('AAPL', 150, 'manual')
        assert result['success'] is False
    
    def test_get_drawdown_status_normal(self):
        manager = RiskManager()
        manager.update_equity(100000)
        manager.peak_equity = 100000
        
        status = manager.get_drawdown_status()
        assert status['level'] == 'normal'
        assert status['action'] == 'continue'
    
    def test_get_drawdown_status_warning(self):
        manager = RiskManager()
        manager.current_equity = 90000  # 10% drawdown
        manager.peak_equity = 100000
        
        status = manager.get_drawdown_status()
        assert status['level'] == 'warning'
        assert status['action'] == 'reduce_size'
    
    def test_get_drawdown_status_critical(self):
        manager = RiskManager()
        manager.current_equity = 75000  # 25% drawdown
        manager.peak_equity = 100000
        
        status = manager.get_drawdown_status()
        assert status['level'] == 'critical'
        assert status['action'] == 'halt_trading'
    
    def test_get_statistics_empty(self):
        manager = RiskManager()
        stats = manager.get_statistics()
        assert stats['total_trades'] == 0
        assert stats['win_rate'] == 0.0
    
    def test_get_statistics_with_trades(self):
        manager = RiskManager()
        
        # Simulate some trades
        manager.trade_history = [
            TradeResult('AAPL', 100, 0.01, 151, datetime.now(), 'target'),
            TradeResult('TSLA', -50, -0.005, 199, datetime.now(), 'stop'),
            TradeResult('MSFT', 200, 0.02, 306, datetime.now(), 'target'),
        ]
        
        stats = manager.get_statistics()
        assert stats['total_trades'] == 3
        assert stats['wins'] == 2
        assert stats['losses'] == 1
        assert stats['win_rate'] == 2/3
        assert stats['total_pnl'] == 250
        assert stats['profit_factor'] == 300 / 50  # 6.0
    
    def test_reset_daily_stats(self):
        manager = RiskManager()
        manager.daily_stats['trades'] = 5
        manager.daily_stats['pnl'] = -1000
        
        manager.reset_daily_stats()
        assert manager.daily_stats['trades'] == 0
        assert manager.daily_stats['pnl'] == 0.0
        assert manager.daily_stats['date'] == date.today()
    
    def test_check_date_reset(self):
        manager = RiskManager()
        manager.daily_stats['trades'] = 5
        manager.daily_stats['date'] = date(2020, 1, 1)  # Old date
        
        manager._check_date_reset()
        assert manager.daily_stats['trades'] == 0
        assert manager.daily_stats['date'] == date.today()
    
    def test_get_portfolio_heat(self):
        manager = RiskManager()
        manager.update_equity(100000)
        
        # Add positions
        manager.positions['AAPL'] = Position('AAPL', 'long', 150, 145, size=100)
        manager.positions['TSLA'] = Position('TSLA', 'long', 200, 190, size=50)
        
        heat = manager.get_portfolio_heat()
        # AAPL: (150-145) * 100 = $500 risk
        # TSLA: (200-190) * 50 = $500 risk
        # Total: $1000 risk = 1% of account
        assert heat['total_risk'] == 1000.0
        assert heat['heat_pct'] == 0.01
        assert heat['status'] == 'cool'
    
    def test_set_correlation(self):
        manager = RiskManager()
        manager.set_correlation('AAPL', 'MSFT', 0.75)
        
        assert manager.correlation_matrix['AAPL']['MSFT'] == 0.75
        assert manager.correlation_matrix['MSFT']['AAPL'] == 0.75
    
    def test_correlation_check_in_validation(self):
        manager = RiskManager()
        manager.update_equity(100000)
        manager.set_correlation('AAPL', 'MSFT', 0.75)
        manager.positions['AAPL'] = Position('AAPL', 'long', 150, 145)
        
        trade = {
            'symbol': 'MSFT',
            'entry_price': 300,
            'stop_price': 295,
            'side': 'long',
            'account_value': 100000,
            'correlation_with': ['AAPL']
        }
        
        result = manager.validate_trade(trade)
        assert result['allowed'] is False
        assert 'correlation' in result['reason']


class TestPositionDataclass:
    """Tests for Position dataclass."""
    
    def test_position_creation(self):
        pos = Position('AAPL', 'long', 150, 145, target_price=160, size=100)
        assert pos.symbol == 'AAPL'
        assert pos.side == 'long'
        assert pos.entry_price == 150
        assert pos.stop_price == 145
        assert pos.target_price == 160
        assert pos.size == 100
        assert pos.highest_price == 150
        assert pos.lowest_price == 150
    
    def test_position_default_prices(self):
        pos = Position('TSLA', 'short', 200, 210)
        assert pos.highest_price == 200
        assert pos.lowest_price == 200


class TestTradeResultDataclass:
    """Tests for TradeResult dataclass."""
    
    def test_trade_result_creation(self):
        result = TradeResult('AAPL', 100, 0.01, 151, datetime.now(), 'target')
        assert result.symbol == 'AAPL'
        assert result.pnl == 100
        assert result.pnl_pct == 0.01
        assert result.exit_price == 151
        assert result.exit_reason == 'target'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
