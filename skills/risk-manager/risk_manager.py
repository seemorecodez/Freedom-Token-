"""
Risk Manager - Trading Safety and Position Sizing

This module provides comprehensive risk management for trading including:
- Position sizing (Fixed Fractional, Kelly Criterion)
- Stop loss monitoring
- Daily loss limits
- Drawdown tracking
- Trade validation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Literal
from datetime import datetime, date
from enum import Enum
import math


class RiskAction(Enum):
    """Actions returned by risk checks."""
    HOLD = "hold"
    STOP_TRIGGERED = "stop_triggered"
    TARGET_HIT = "target_hit"
    TRAIL_STOP = "trail_stop"
    CLOSE_POSITION = "close_position"


@dataclass
class RiskConfig:
    """Configuration for risk management parameters."""
    
    # Position sizing limits
    max_position_pct: float = 0.20  # Max 20% of account in single position
    max_positions: int = 10  # Maximum number of concurrent positions
    
    # Stop loss / Take profit
    stop_loss_pct: float = 0.02  # Default 2% stop
    take_profit_pct: float = 0.06  # Default 6% target (3:1 ratio)
    trailing_stop_pct: Optional[float] = None  # Optional trailing stop
    
    # Daily limits
    daily_loss_limit_pct: float = 0.05  # 5% daily loss limit
    max_trades_per_day: int = 10  # Prevent overtrading
    max_consecutive_losses: int = 3  # Pause after N losses
    
    # Kelly criterion settings
    kelly_fraction: float = 0.25  # Conservative Kelly (1/4 Kelly)
    
    # Drawdown protection
    max_drawdown_pct: float = 0.20  # Stop trading at 20% drawdown
    warning_drawdown_pct: float = 0.10  # Warning at 10% drawdown
    
    # Correlation limits
    correlation_limit: float = 0.70  # Max correlation between positions
    
    # Minimum values
    min_position_size: float = 1.0  # Minimum position size
    min_risk_reward_ratio: float = 1.5  # Minimum R/R ratio


@dataclass
class Position:
    """Represents a trading position."""
    symbol: str
    side: Literal['long', 'short']
    entry_price: float
    stop_price: float
    target_price: Optional[float] = None
    size: float = 0.0
    entry_time: datetime = field(default_factory=datetime.now)
    highest_price: float = 0.0  # For trailing stops
    lowest_price: float = float('inf')
    
    def __post_init__(self):
        if self.highest_price == 0.0:
            self.highest_price = self.entry_price
        if self.lowest_price == float('inf'):
            self.lowest_price = self.entry_price


@dataclass
class TradeResult:
    """Result of a completed trade."""
    symbol: str
    pnl: float
    pnl_pct: float
    exit_price: float
    exit_time: datetime
    exit_reason: str


def calculate_position_size(
    account_value: float,
    method: Literal['fixed_fractional', 'kelly'] = 'fixed_fractional',
    # Fixed fractional params
    risk_per_trade_pct: float = 0.01,
    entry_price: float = 0.0,
    stop_price: float = 0.0,
    # Kelly params
    win_rate: float = 0.0,
    avg_win: float = 0.0,
    avg_loss: float = 0.0,
    kelly_fraction: float = 0.25,
    # Constraints
    max_position_pct: float = 0.20,
    min_position_size: float = 1.0
) -> Dict:
    """
    Calculate optimal position size using specified method.
    
    Args:
        account_value: Current account value
        method: 'fixed_fractional' or 'kelly'
        risk_per_trade_pct: Risk per trade (for fixed fractional)
        entry_price: Entry price per share/unit
        stop_price: Stop loss price
        win_rate: Historical win rate (for Kelly)
        avg_win: Average winning trade amount (for Kelly)
        avg_loss: Average losing trade amount (for Kelly)
        kelly_fraction: Kelly fraction (e.g., 0.25 for 1/4 Kelly)
        max_position_pct: Maximum position size as % of account
        min_position_size: Minimum position size
        
    Returns:
        Dict with position_size, risk_amount, position_value, and metadata
    """
    result = {
        'position_size': 0.0,
        'risk_amount': 0.0,
        'position_value': 0.0,
        'risk_pct': 0.0,
        'method': method,
        'valid': False,
        'reason': ''
    }
    
    if account_value <= 0:
        result['reason'] = 'Invalid account value'
        return result
    
    if method == 'fixed_fractional':
        if entry_price <= 0 or stop_price <= 0:
            result['reason'] = 'Invalid entry/stop prices'
            return result
            
        risk_amount = account_value * risk_per_trade_pct
        risk_per_share = abs(entry_price - stop_price)
        
        if risk_per_share == 0:
            result['reason'] = 'Entry and stop prices are equal'
            return result
            
        position_size = risk_amount / risk_per_share
        position_value = position_size * entry_price
        
        # Apply max position limit
        max_position_value = account_value * max_position_pct
        if position_value > max_position_value:
            position_size = max_position_value / entry_price
            position_value = max_position_value
            risk_amount = position_size * risk_per_share
        
        # Apply minimum size
        if position_size < min_position_size:
            result['reason'] = f'Position size {position_size:.2f} below minimum {min_position_size}'
            return result
            
        result.update({
            'position_size': position_size,
            'risk_amount': risk_amount,
            'position_value': position_value,
            'risk_pct': risk_amount / account_value,
            'valid': True
        })
        
    elif method == 'kelly':
        if not (0 < win_rate < 1):
            result['reason'] = 'Win rate must be between 0 and 1'
            return result
        if avg_loss <= 0:
            result['reason'] = 'Average loss must be positive'
            return result
            
        # Kelly formula: f* = (p*b - q) / b
        # where p = win rate, q = loss rate, b = avg_win/avg_loss
        loss_rate = 1 - win_rate
        b = avg_win / avg_loss
        
        kelly_pct = (win_rate * b - loss_rate) / b
        
        if kelly_pct <= 0:
            result['reason'] = 'Kelly criterion suggests no position (negative expectancy)'
            return result
            
        # Apply Kelly fraction for safety
        adjusted_kelly = kelly_pct * kelly_fraction
        
        # Cap at max position
        final_pct = min(adjusted_kelly, max_position_pct)
        
        position_value = account_value * final_pct
        risk_amount = position_value * 0.02  # Assume 2% risk within position
        
        if entry_price > 0:
            position_size = position_value / entry_price
        else:
            position_size = 0
            
        result.update({
            'position_size': position_size,
            'risk_amount': risk_amount,
            'position_value': position_value,
            'risk_pct': final_pct,
            'kelly_pct': kelly_pct,
            'adjusted_kelly_pct': adjusted_kelly,
            'valid': True
        })
    
    return result


def check_stop_loss(
    entry_price: float,
    current_price: float,
    stop_price: float,
    target_price: Optional[float] = None,
    position_side: Literal['long', 'short'] = 'long',
    trailing_stop_pct: Optional[float] = None,
    highest_price: float = 0.0,
    lowest_price: float = float('inf')
) -> Dict:
    """
    Check if stop loss or target has been hit.
    
    Args:
        entry_price: Entry price of position
        current_price: Current market price
        stop_price: Stop loss price
        target_price: Take profit target
        position_side: 'long' or 'short'
        trailing_stop_pct: Optional trailing stop percentage
        highest_price: Highest price since entry (for trailing stops)
        lowest_price: Lowest price since entry (for trailing stops)
        
    Returns:
        Dict with action, reason, and updated prices
    """
    result = {
        'action': RiskAction.HOLD.value,
        'reason': '',
        'exit_price': None,
        'updated_highest': max(highest_price, current_price),
        'updated_lowest': min(lowest_price, current_price)
    }
    
    # Check hard stop loss
    if position_side == 'long':
        if current_price <= stop_price:
            result['action'] = RiskAction.STOP_TRIGGERED.value
            result['reason'] = f'Stop loss hit: {current_price} <= {stop_price}'
            result['exit_price'] = current_price
            return result
            
        # Check target
        if target_price and current_price >= target_price:
            result['action'] = RiskAction.TARGET_HIT.value
            result['reason'] = f'Target hit: {current_price} >= {target_price}'
            result['exit_price'] = current_price
            return result
            
        # Check trailing stop
        if trailing_stop_pct and highest_price > 0:
            trail_price = highest_price * (1 - trailing_stop_pct)
            if current_price <= trail_price:
                result['action'] = RiskAction.TRAIL_STOP.value
                result['reason'] = f'Trailing stop hit: {current_price} <= {trail_price:.2f}'
                result['exit_price'] = current_price
                return result
                
    else:  # short position
        if current_price >= stop_price:
            result['action'] = RiskAction.STOP_TRIGGERED.value
            result['reason'] = f'Stop loss hit: {current_price} >= {stop_price}'
            result['exit_price'] = current_price
            return result
            
        if target_price and current_price <= target_price:
            result['action'] = RiskAction.TARGET_HIT.value
            result['reason'] = f'Target hit: {current_price} <= {target_price}'
            result['exit_price'] = current_price
            return result
            
        if trailing_stop_pct and lowest_price < float('inf'):
            trail_price = lowest_price * (1 + trailing_stop_pct)
            if current_price >= trail_price:
                result['action'] = RiskAction.TRAIL_STOP.value
                result['reason'] = f'Trailing stop hit: {current_price} >= {trail_price:.2f}'
                result['exit_price'] = current_price
                return result
    
    return result


def check_daily_limit(
    daily_pnl: float,
    account_value: float,
    daily_loss_limit_pct: float,
    trades_today: int = 0,
    max_trades_per_day: int = 10,
    consecutive_losses: int = 0,
    max_consecutive_losses: int = 3
) -> Dict:
    """
    Check if daily trading limits have been exceeded.
    
    Args:
        daily_pnl: Current daily P&L
        account_value: Current account value
        daily_loss_limit_pct: Maximum daily loss as percentage
        trades_today: Number of trades executed today
        max_trades_per_day: Maximum trades allowed per day
        consecutive_losses: Current consecutive loss count
        max_consecutive_losses: Max losses before pausing
        
    Returns:
        Dict with allowed status and reason
    """
    result = {
        'allowed': True,
        'reason': '',
        'limits': []
    }
    
    daily_loss_limit = account_value * daily_loss_limit_pct
    
    # Check daily loss limit
    if daily_pnl <= -daily_loss_limit:
        result['allowed'] = False
        result['reason'] = f'Daily loss limit exceeded: {daily_pnl:.2f} <= {-daily_loss_limit:.2f}'
        result['limits'].append('daily_loss')
        return result
    
    # Check max trades
    if trades_today >= max_trades_per_day:
        result['allowed'] = False
        result['reason'] = f'Max trades per day reached: {trades_today}'
        result['limits'].append('max_trades')
        return result
    
    # Check consecutive losses
    if consecutive_losses >= max_consecutive_losses:
        result['allowed'] = False
        result['reason'] = f'Max consecutive losses reached: {consecutive_losses}'
        result['limits'].append('consecutive_losses')
        return result
    
    return result


def calculate_drawdown(
    current_equity: float,
    peak_equity: float
) -> Dict:
    """
    Calculate current drawdown from peak equity.
    
    Args:
        current_equity: Current account equity
        peak_equity: Peak equity value
        
    Returns:
        Dict with drawdown metrics
    """
    if peak_equity <= 0:
        return {
            'drawdown_pct': 0.0,
            'drawdown_amount': 0.0,
            'in_drawdown': False,
            'peak_equity': peak_equity,
            'current_equity': current_equity
        }
    
    drawdown_amount = peak_equity - current_equity
    drawdown_pct = drawdown_amount / peak_equity if peak_equity > 0 else 0.0
    
    return {
        'drawdown_pct': drawdown_pct,
        'drawdown_amount': drawdown_amount,
        'in_drawdown': drawdown_pct > 0.01,  # >1% considered in drawdown
        'peak_equity': peak_equity,
        'current_equity': current_equity
    }


def calculate_risk_reward_ratio(
    entry_price: float,
    stop_price: float,
    target_price: float,
    position_side: Literal['long', 'short'] = 'long'
) -> float:
    """Calculate risk/reward ratio for a trade."""
    risk = abs(entry_price - stop_price)
    reward = abs(target_price - entry_price)
    
    if risk == 0:
        return 0.0
    
    return reward / risk


def calculate_expectancy(
    win_rate: float,
    avg_win: float,
    avg_loss: float
) -> float:
    """
    Calculate trading system expectancy.
    
    Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
    Positive expectancy = profitable system
    """
    loss_rate = 1 - win_rate
    return (win_rate * avg_win) - (loss_rate * abs(avg_loss))


class RiskManager:
    """
    Main risk manager class that orchestrates all risk checks.
    """
    
    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[TradeResult] = []
        self.daily_stats = {
            'date': date.today(),
            'trades': 0,
            'pnl': 0.0,
            'consecutive_losses': 0,
            'wins': 0,
            'losses': 0
        }
        self.peak_equity = 0.0
        self.current_equity = 0.0
        self.correlation_matrix: Dict[str, Dict[str, float]] = {}
    
    def validate_trade(self, trade: Dict) -> Dict:
        """
        Validate a potential trade against all risk rules.
        
        Args:
            trade: Dict with symbol, entry_price, stop_price, target_price, 
                   side, account_value, optional: correlation_with
                   
        Returns:
            Dict with allowed status, position size, and reason
        """
        result = {
            'allowed': False,
            'reason': '',
            'position_size': 0.0,
            'risk_amount': 0.0,
            'risk_reward_ratio': 0.0,
            'checks': {}
        }
        
        symbol = trade.get('symbol')
        entry_price = trade.get('entry_price', 0)
        stop_price = trade.get('stop_price', 0)
        target_price = trade.get('target_price')
        side = trade.get('side', 'long')
        account_value = trade.get('account_value', 0)
        
        # Reset daily stats if new day
        self._check_date_reset()
        
        # Check daily limits
        daily_check = check_daily_limit(
            daily_pnl=self.daily_stats['pnl'],
            account_value=account_value,
            daily_loss_limit_pct=self.config.daily_loss_limit_pct,
            trades_today=self.daily_stats['trades'],
            max_trades_per_day=self.config.max_trades_per_day,
            consecutive_losses=self.daily_stats['consecutive_losses'],
            max_consecutive_losses=self.config.max_consecutive_losses
        )
        result['checks']['daily_limit'] = daily_check
        
        if not daily_check['allowed']:
            result['reason'] = daily_check['reason']
            return result
        
        # Check max positions
        if len(self.positions) >= self.config.max_positions:
            result['reason'] = f'Max positions reached: {len(self.positions)}'
            return result
        
        # Check if symbol already in positions
        if symbol in self.positions:
            result['reason'] = f'Position already exists for {symbol}'
            return result
        
        # Calculate risk/reward
        if target_price:
            rr = calculate_risk_reward_ratio(entry_price, stop_price, target_price, side)
            result['risk_reward_ratio'] = rr
            
            if rr < self.config.min_risk_reward_ratio:
                result['reason'] = f'Risk/reward ratio {rr:.2f} below minimum {self.config.min_risk_reward_ratio}'
                return result
        
        # Check drawdown
        if self.current_equity > 0:
            dd = calculate_drawdown(self.current_equity, self.peak_equity)
            if dd['drawdown_pct'] >= self.config.max_drawdown_pct:
                result['reason'] = f'Max drawdown exceeded: {dd["drawdown_pct"]:.2%}'
                return result
        
        # Check correlation
        correlated_symbols = trade.get('correlation_with', [])
        for sym in correlated_symbols:
            corr = self.correlation_matrix.get(symbol, {}).get(sym, 0)
            if abs(corr) > self.config.correlation_limit:
                result['reason'] = f'High correlation with {sym}: {corr:.2f}'
                return result
        
        # Calculate position size
        sizing = calculate_position_size(
            account_value=account_value,
            method='fixed_fractional',
            risk_per_trade_pct=self.config.stop_loss_pct,
            entry_price=entry_price,
            stop_price=stop_price,
            max_position_pct=self.config.max_position_pct,
            min_position_size=self.config.min_position_size
        )
        result['checks']['position_sizing'] = sizing
        
        if not sizing['valid']:
            result['reason'] = sizing.get('reason', 'Position sizing failed')
            return result
        
        # All checks passed
        result['allowed'] = True
        result['position_size'] = sizing['position_size']
        result['risk_amount'] = sizing['risk_amount']
        
        return result
    
    def enter_position(self, position: Position) -> Dict:
        """Record a new position."""
        self.positions[position.symbol] = position
        self.daily_stats['trades'] += 1
        
        return {
            'success': True,
            'symbol': position.symbol,
            'position_count': len(self.positions)
        }
    
    def update_position(self, symbol: str, current_price: float) -> Dict:
        """
        Update position with current price and check for stops.
        
        Returns:
            Dict with action and exit details if triggered
        """
        if symbol not in self.positions:
            return {'action': RiskAction.HOLD.value, 'reason': 'No position found'}
        
        pos = self.positions[symbol]
        
        # Update high/low prices
        pos.highest_price = max(pos.highest_price, current_price)
        pos.lowest_price = min(pos.lowest_price, current_price)
        
        # Check stops
        stop_check = check_stop_loss(
            entry_price=pos.entry_price,
            current_price=current_price,
            stop_price=pos.stop_price,
            target_price=pos.target_price,
            position_side=pos.side,
            trailing_stop_pct=self.config.trailing_stop_pct,
            highest_price=pos.highest_price,
            lowest_price=pos.lowest_price
        )
        
        if stop_check['action'] != RiskAction.HOLD.value:
            # Calculate P&L
            if pos.side == 'long':
                pnl = (stop_check['exit_price'] - pos.entry_price) * pos.size
            else:
                pnl = (pos.entry_price - stop_check['exit_price']) * pos.size
            
            stop_check['pnl'] = pnl
            stop_check['position'] = pos
            
            # Close position
            self.close_position(symbol, stop_check['exit_price'], stop_check['reason'])
        
        return stop_check
    
    def close_position(self, symbol: str, exit_price: float, reason: str = 'manual') -> Dict:
        """Close a position and record the result."""
        if symbol not in self.positions:
            return {'success': False, 'reason': 'Position not found'}
        
        pos = self.positions[symbol]
        
        # Calculate P&L
        if pos.side == 'long':
            pnl = (exit_price - pos.entry_price) * pos.size
        else:
            pnl = (pos.entry_price - exit_price) * pos.size
            
        pnl_pct = pnl / (pos.entry_price * pos.size) if pos.entry_price > 0 else 0
        
        # Record trade
        trade = TradeResult(
            symbol=symbol,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_price=exit_price,
            exit_time=datetime.now(),
            exit_reason=reason
        )
        self.trade_history.append(trade)
        
        # Update daily stats
        self.daily_stats['pnl'] += pnl
        if pnl > 0:
            self.daily_stats['wins'] += 1
            self.daily_stats['consecutive_losses'] = 0
        else:
            self.daily_stats['losses'] += 1
            self.daily_stats['consecutive_losses'] += 1
        
        # Update equity
        self.current_equity += pnl
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity
        
        # Remove position
        del self.positions[symbol]
        
        return {
            'success': True,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        }
    
    def update_equity(self, equity: float):
        """Update current equity and track peak."""
        self.current_equity = equity
        if equity > self.peak_equity:
            self.peak_equity = equity
    
    def get_drawdown_status(self) -> Dict:
        """Get current drawdown status."""
        dd = calculate_drawdown(self.current_equity, self.peak_equity)
        
        # Add warning level
        if dd['drawdown_pct'] >= self.config.max_drawdown_pct:
            dd['level'] = 'critical'
            dd['action'] = 'halt_trading'
        elif dd['drawdown_pct'] >= self.config.warning_drawdown_pct:
            dd['level'] = 'warning'
            dd['action'] = 'reduce_size'
        else:
            dd['level'] = 'normal'
            dd['action'] = 'continue'
            
        return dd
    
    def get_statistics(self) -> Dict:
        """Get trading statistics."""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_pnl': 0.0,
                'total_pnl': 0.0
            }
        
        wins = sum(1 for t in self.trade_history if t.pnl > 0)
        total = len(self.trade_history)
        win_rate = wins / total if total > 0 else 0
        
        avg_win = sum(t.pnl for t in self.trade_history if t.pnl > 0) / wins if wins > 0 else 0
        losses = total - wins
        avg_loss = sum(t.pnl for t in self.trade_history if t.pnl < 0) / losses if losses > 0 else 0
        
        total_pnl = sum(t.pnl for t in self.trade_history)
        avg_pnl = total_pnl / total
        
        expectancy = calculate_expectancy(win_rate, avg_win, avg_loss)
        
        return {
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_pnl': total_pnl,
            'expectancy': expectancy,
            'profit_factor': abs(sum(t.pnl for t in self.trade_history if t.pnl > 0) / 
                                sum(t.pnl for t in self.trade_history if t.pnl < 0)) if any(t.pnl < 0 for t in self.trade_history) else float('inf')
        }
    
    def reset_daily_stats(self):
        """Reset daily statistics (call at end of day or start of new day)."""
        self.daily_stats = {
            'date': date.today(),
            'trades': 0,
            'pnl': 0.0,
            'consecutive_losses': 0,
            'wins': 0,
            'losses': 0
        }
    
    def _check_date_reset(self):
        """Check if we need to reset daily stats for new day."""
        if date.today() != self.daily_stats['date']:
            self.reset_daily_stats()
    
    def get_portfolio_heat(self) -> Dict:
        """
        Calculate total portfolio risk (heat).
        
        Returns:
            Dict with total heat metrics
        """
        total_risk = 0.0
        position_risks = []
        
        for symbol, pos in self.positions.items():
            risk_per_share = abs(pos.entry_price - pos.stop_price)
            position_risk = risk_per_share * pos.size
            total_risk += position_risk
            position_risks.append({
                'symbol': symbol,
                'risk': position_risk,
                'risk_pct': position_risk / self.current_equity if self.current_equity > 0 else 0
            })
        
        heat_pct = total_risk / self.current_equity if self.current_equity > 0 else 0
        
        return {
            'total_risk': total_risk,
            'heat_pct': heat_pct,
            'position_risks': position_risks,
            'status': 'hot' if heat_pct > 0.10 else 'warm' if heat_pct > 0.05 else 'cool'
        }
    
    def set_correlation(self, symbol1: str, symbol2: str, correlation: float):
        """Set correlation between two symbols."""
        if symbol1 not in self.correlation_matrix:
            self.correlation_matrix[symbol1] = {}
        if symbol2 not in self.correlation_matrix:
            self.correlation_matrix[symbol2] = {}
            
        self.correlation_matrix[symbol1][symbol2] = correlation
        self.correlation_matrix[symbol2][symbol1] = correlation
