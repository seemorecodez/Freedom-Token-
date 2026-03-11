"""
Backtester - Historical Strategy Testing Framework

A comprehensive backtesting engine for trading strategy evaluation with
performance metrics, walk-forward analysis, and strategy comparison.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Tuple, Union, Any
from enum import Enum
import json
import numpy as np
import pandas as pd
from collections import defaultdict


class TradeSide(Enum):
    """Trade direction."""
    BUY = "buy"
    SELL = "sell"


class TradeStatus(Enum):
    """Trade execution status."""
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Trade:
    """Represents a single trade."""
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    side: TradeSide = TradeSide.BUY
    size: float = 0.0
    symbol: str = ""
    status: TradeStatus = TradeStatus.OPEN
    pnl: float = 0.0
    pnl_pct: float = 0.0
    fees: float = 0.0
    
    def close(self, exit_time: datetime, exit_price: float, fees: float = 0.0):
        """Close the trade and calculate P&L."""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.fees = fees
        self.status = TradeStatus.CLOSED
        
        if self.side == TradeSide.BUY:
            self.pnl = (exit_price - self.entry_price) * self.size - fees
            self.pnl_pct = (exit_price / self.entry_price - 1) * 100 if self.entry_price != 0 else 0
        else:
            self.pnl = (self.entry_price - exit_price) * self.size - fees
            self.pnl_pct = (self.entry_price / exit_price - 1) * 100 if exit_price != 0 else 0
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Return trade duration."""
        if self.exit_time:
            return self.exit_time - self.entry_time
        return None


@dataclass
class BacktestConfig:
    """Configuration for backtest run."""
    start_date: datetime
    end_date: datetime
    initial_capital: float = 100000.0
    commission_rate: float = 0.001  # 0.1% per trade
    slippage: float = 0.0  # Price slippage
    max_position_size: float = 1.0  # Max position as fraction of capital
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    symbols: List[str] = field(default_factory=list)
    timeframe: str = "1d"
    allow_short: bool = False
    
    def __post_init__(self):
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    config: BacktestConfig
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series())
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Calculated metrics
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0
    volatility: float = 0.0
    calmar_ratio: float = 0.0
    sortino_ratio: float = 0.0
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now()


class PriceData:
    """Container for historical price data."""
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize with OHLCV DataFrame.
        
        Expected columns: open, high, low, close, volume
        Index should be datetime
        """
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in data.columns:
                raise ValueError(f"Missing required column: {col}")
        
        self.data = data.copy()
        self.data.sort_index(inplace=True)
    
    @property
    def returns(self) -> pd.Series:
        """Calculate returns series."""
        return self.data['close'].pct_change().dropna()
    
    def get_slice(self, start: datetime, end: datetime) -> 'PriceData':
        """Get subset of data by date range."""
        mask = (self.data.index >= start) & (self.data.index <= end)
        return PriceData(self.data[mask])
    
    @property
    def start_date(self) -> datetime:
        return self.data.index[0]
    
    @property
    def end_date(self) -> datetime:
        return self.data.index[-1]


def load_historical_data(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    source: str = "yfinance",
    **kwargs
) -> PriceData:
    """
    Fetch historical price data from various sources.
    
    Args:
        symbol: Asset symbol (e.g., 'AAPL', 'BTC-USD')
        start_date: Start of data range
        end_date: End of data range
        source: Data source ('yfinance', 'csv', 'synthetic')
        **kwargs: Additional source-specific parameters
    
    Returns:
        PriceData object containing OHLCV data
    """
    if source == "yfinance":
        try:
            import yfinance as yf
            df = yf.download(symbol, start=start_date, end=end_date, progress=False)
            if df.empty:
                raise ValueError(f"No data returned for {symbol}")
            # Flatten multi-index columns if present
            df.columns = [col[0].lower() if isinstance(col, tuple) else col.lower() 
                         for col in df.columns]
            # Rename common variations
            col_map = {'adj close': 'close', 'adj_close': 'close'}
            df.rename(columns=col_map, inplace=True)
            return PriceData(df)
        except ImportError:
            raise ImportError("yfinance required. Install with: pip install yfinance")
    
    elif source == "csv":
        filepath = kwargs.get('filepath')
        if not filepath:
            raise ValueError("filepath required for CSV source")
        df = pd.read_csv(filepath, parse_dates=True, index_col=0)
        df.columns = [col.lower() for col in df.columns]
        # Filter by date
        mask = (df.index >= start_date) & (df.index <= end_date)
        df = df[mask]
        return PriceData(df)
    
    elif source == "synthetic":
        # Generate synthetic price data for testing
        np.random.seed(kwargs.get('seed', 42))
        days = (end_date - start_date).days
        dates = pd.date_range(start=start_date, periods=days, freq='D')
        
        trend = kwargs.get('trend', 0.0001)
        volatility = kwargs.get('volatility', 0.02)
        
        returns = np.random.normal(trend, volatility, len(dates))
        prices = 100 * np.exp(np.cumsum(returns))
        
        # Generate OHLC from close
        df = pd.DataFrame({
            'close': prices,
            'open': prices * (1 + np.random.normal(0, volatility/4, len(dates))),
            'high': prices * (1 + abs(np.random.normal(0, volatility/2, len(dates)))),
            'low': prices * (1 - abs(np.random.normal(0, volatility/2, len(dates)))),
            'volume': np.random.randint(1000000, 10000000, len(dates))
        }, index=dates)
        
        return PriceData(df)
    
    else:
        raise ValueError(f"Unknown data source: {source}")


class Backtester:
    """Main backtesting engine."""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.data: Dict[str, PriceData] = {}
        self.current_capital: float = config.initial_capital
        self.equity_history: List[Tuple[datetime, float]] = []
        self.trades: List[Trade] = []
        self.open_positions: Dict[str, Trade] = {}
    
    def load_data(self, symbol: str, data: PriceData):
        """Load price data for a symbol."""
        self.data[symbol] = data
    
    def run_backtest(
        self,
        strategy: Callable[[pd.DataFrame, Dict], Dict[str, Any]],
        strategy_params: Optional[Dict] = None
    ) -> BacktestResult:
        """
        Run a backtest with the given strategy.
        
        Args:
            strategy: Strategy function that takes (data, params) and returns signals
                     Signals format: {'action': 'buy'/'sell'/'hold', 'size': float}
            strategy_params: Parameters to pass to strategy
        
        Returns:
            BacktestResult with performance metrics
        """
        if strategy_params is None:
            strategy_params = {}
        
        self.current_capital = self.config.initial_capital
        self.equity_history = []
        self.trades = []
        self.open_positions = {}
        
        result = BacktestResult(config=self.config)
        result.start_time = datetime.now()
        
        # Process each symbol
        for symbol, price_data in self.data.items():
            df = price_data.data
            
            for i, (timestamp, row) in enumerate(df.iterrows()):
                # Record equity
                equity = self._calculate_equity(timestamp, row['close'])
                self.equity_history.append((timestamp, equity))
                
                # Get strategy signal
                signal = strategy(df.iloc[:i+1], strategy_params)
                
                # Execute trades
                self._process_signal(symbol, timestamp, row, signal)
                
                # Check stop loss / take profit
                self._check_exits(symbol, timestamp, row)
        
        # Close any remaining positions
        for symbol in list(self.open_positions.keys()):
            last_price = self.data[symbol].data['close'].iloc[-1]
            last_time = self.data[symbol].data.index[-1]
            self._close_position(symbol, last_time, last_price)
        
        result.end_time = datetime.now()
        result.trades = self.trades
        result.equity_curve = pd.Series(
            [e[1] for e in self.equity_history],
            index=[e[0] for e in self.equity_history]
        )
        
        # Calculate all metrics
        self._calculate_all_metrics(result)
        
        return result
    
    def _calculate_equity(self, timestamp: datetime, current_price: float) -> float:
        """Calculate current equity including open positions."""
        equity = self.current_capital
        for symbol, trade in self.open_positions.items():
            if trade.side == TradeSide.BUY:
                unrealized = (current_price - trade.entry_price) * trade.size
            else:
                unrealized = (trade.entry_price - current_price) * trade.size
            equity += unrealized
        return equity
    
    def _process_signal(
        self,
        symbol: str,
        timestamp: datetime,
        row: pd.Series,
        signal: Dict[str, Any]
    ):
        """Process trading signal."""
        action = signal.get('action', 'hold')
        
        if action == 'buy' and symbol not in self.open_positions:
            size = signal.get('size', self.config.max_position_size)
            position_value = self.current_capital * size
            shares = position_value / row['close']
            
            trade = Trade(
                entry_time=timestamp,
                entry_price=row['close'] + self.config.slippage,
                side=TradeSide.BUY,
                size=shares,
                symbol=symbol
            )
            self.open_positions[symbol] = trade
            
        elif action == 'sell' and symbol in self.open_positions:
            self._close_position(symbol, timestamp, row['close'] - self.config.slippage)
            
        elif action == 'short' and self.config.allow_short and symbol not in self.open_positions:
            size = signal.get('size', self.config.max_position_size)
            position_value = self.current_capital * size
            shares = position_value / row['close']
            
            trade = Trade(
                entry_time=timestamp,
                entry_price=row['close'] - self.config.slippage,
                side=TradeSide.SELL,
                size=shares,
                symbol=symbol
            )
            self.open_positions[symbol] = trade
    
    def _check_exits(self, symbol: str, timestamp: datetime, row: pd.Series):
        """Check stop loss and take profit conditions."""
        if symbol not in self.open_positions:
            return
        
        trade = self.open_positions[symbol]
        current_price = row['close']
        
        # Check stop loss
        if self.config.stop_loss_pct:
            if trade.side == TradeSide.BUY:
                stop_price = trade.entry_price * (1 - self.config.stop_loss_pct)
                if row['low'] <= stop_price:
                    self._close_position(symbol, timestamp, stop_price)
                    return
            else:
                stop_price = trade.entry_price * (1 + self.config.stop_loss_pct)
                if row['high'] >= stop_price:
                    self._close_position(symbol, timestamp, stop_price)
                    return
        
        # Check take profit
        if self.config.take_profit_pct:
            if trade.side == TradeSide.BUY:
                tp_price = trade.entry_price * (1 + self.config.take_profit_pct)
                if row['high'] >= tp_price:
                    self._close_position(symbol, timestamp, tp_price)
                    return
            else:
                tp_price = trade.entry_price * (1 - self.config.take_profit_pct)
                if row['low'] <= tp_price:
                    self._close_position(symbol, timestamp, tp_price)
                    return
    
    def _close_position(self, symbol: str, timestamp: datetime, exit_price: float):
        """Close an open position."""
        if symbol not in self.open_positions:
            return
        
        trade = self.open_positions.pop(symbol)
        fees = (trade.entry_price + exit_price) * trade.size * self.config.commission_rate
        trade.close(timestamp, exit_price, fees)
        
        self.current_capital += trade.pnl
        self.trades.append(trade)
    
    def _calculate_all_metrics(self, result: BacktestResult):
        """Calculate all performance metrics."""
        calculate_metrics(result)


def calculate_metrics(result: BacktestResult) -> Dict[str, float]:
    """
    Calculate comprehensive performance metrics.
    
    Updates the result object in-place and returns metrics dict.
    """
    equity = result.equity_curve
    
    if len(equity) == 0:
        return {}
    
    # Basic returns
    result.total_return = (equity.iloc[-1] / result.config.initial_capital - 1) * 100
    
    # Equity returns
    equity_returns = equity.pct_change().dropna()
    
    if len(equity_returns) > 0:
        # Sharpe ratio (assuming risk-free rate = 0)
        result.volatility = equity_returns.std() * np.sqrt(252) * 100  # Annualized
        if result.volatility != 0:
            result.sharpe_ratio = (equity_returns.mean() / equity_returns.std()) * np.sqrt(252)
        
        # Sortino ratio
        downside_returns = equity_returns[equity_returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() != 0:
            downside_std = downside_returns.std() * np.sqrt(252)
            result.sortino_ratio = (equity_returns.mean() * 252) / downside_std
        
        # Max drawdown
        rolling_max = equity.cummax()
        drawdown = (equity - rolling_max) / rolling_max
        result.max_drawdown = drawdown.min() * 100
        
        # Max drawdown duration
        peak_idx = rolling_max.idxmax()
        in_drawdown = drawdown < 0
        max_duration = 0
        current_duration = 0
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0
        result.max_drawdown_duration = max_duration
        
        # Calmar ratio
        if result.max_drawdown != 0:
            annual_return = equity_returns.mean() * 252 * 100
            result.calmar_ratio = annual_return / abs(result.max_drawdown)
    
    # Trade-based metrics
    if result.trades:
        winning_trades = [t for t in result.trades if t.pnl > 0]
        losing_trades = [t for t in result.trades if t.pnl <= 0]
        
        result.win_rate = len(winning_trades) / len(result.trades) * 100
        
        total_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
        total_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 1
        result.profit_factor = total_profit / total_loss if total_loss != 0 else float('inf')
        
        result.avg_trade_return = np.mean([t.pnl_pct for t in result.trades])
    
    return {
        'total_return': result.total_return,
        'sharpe_ratio': result.sharpe_ratio,
        'max_drawdown': result.max_drawdown,
        'max_drawdown_duration': result.max_drawdown_duration,
        'win_rate': result.win_rate,
        'profit_factor': result.profit_factor,
        'avg_trade_return': result.avg_trade_return,
        'volatility': result.volatility,
        'calmar_ratio': result.calmar_ratio,
        'sortino_ratio': result.sortino_ratio,
        'num_trades': len(result.trades)
    }


def compare_strategies(
    results: List[BacktestResult],
    result_names: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Compare multiple strategy backtest results.
    
    Args:
        results: List of BacktestResult objects
        result_names: Optional names for each result
    
    Returns:
        DataFrame with comparison metrics
    """
    if result_names is None:
        result_names = [f"Strategy {i+1}" for i in range(len(results))]
    
    metrics = []
    for name, result in zip(result_names, results):
        metric = {
            'Strategy': name,
            'Total Return (%)': result.total_return,
            'Sharpe Ratio': result.sharpe_ratio,
            'Max Drawdown (%)': result.max_drawdown,
            'Win Rate (%)': result.win_rate,
            'Profit Factor': result.profit_factor,
            'Volatility (%)': result.volatility,
            'Calmar Ratio': result.calmar_ratio,
            'Sortino Ratio': result.sortino_ratio,
            'Num Trades': len(result.trades),
            'Avg Trade Return (%)': result.avg_trade_return
        }
        metrics.append(metric)
    
    return pd.DataFrame(metrics)


def walk_forward_analysis(
    data: PriceData,
    strategy: Callable,
    strategy_params_list: List[Dict],
    train_size: int,
    test_size: int,
    step_size: Optional[int] = None,
    metric: str = 'sharpe_ratio'
) -> Dict[str, Any]:
    """
    Perform walk-forward analysis for out-of-sample testing.
    
    Args:
        data: Historical price data
        strategy: Strategy function
        strategy_params_list: List of parameter sets to optimize
        train_size: Number of periods for in-sample training
        test_size: Number of periods for out-of-sample testing
        step_size: Step between windows (default = test_size)
        metric: Metric to optimize during training
    
    Returns:
        Dict with optimization results and out-of-sample performance
    """
    if step_size is None:
        step_size = test_size
    
    df = data.data
    n_samples = len(df)
    
    windows = []
    start = 0
    
    while start + train_size + test_size <= n_samples:
        train_end = start + train_size
        test_end = train_end + test_size
        
        windows.append({
            'train_start': start,
            'train_end': train_end,
            'test_start': train_end,
            'test_end': test_end
        })
        start += step_size
    
    oos_results = []
    optimal_params_history = []
    
    for i, window in enumerate(windows):
        # In-sample optimization
        train_data = PriceData(df.iloc[window['train_start']:window['train_end']])
        
        best_metric = -np.inf
        best_params = None
        
        for params in strategy_params_list:
            config = BacktestConfig(
                start_date=train_data.start_date,
                end_date=train_data.end_date,
                initial_capital=100000
            )
            backtester = Backtester(config)
            backtester.load_data('SYM', train_data)
            result = backtester.run_backtest(strategy, params)
            
            current_metric = getattr(result, metric, 0)
            if current_metric > best_metric:
                best_metric = current_metric
                best_params = params
        
        optimal_params_history.append({
            'window': i,
            'params': best_params,
            'in_sample_metric': best_metric
        })
        
        # Out-of-sample test
        test_data = PriceData(df.iloc[window['test_start']:window['test_end']])
        config = BacktestConfig(
            start_date=test_data.start_date,
            end_date=test_data.end_date,
            initial_capital=100000
        )
        backtester = Backtester(config)
        backtester.load_data('SYM', test_data)
        oos_result = backtester.run_backtest(strategy, best_params)
        oos_results.append(oos_result)
    
    # Aggregate out-of-sample metrics
    avg_metrics = {
        'avg_total_return': np.mean([r.total_return for r in oos_results]),
        'avg_sharpe': np.mean([r.sharpe_ratio for r in oos_results]),
        'avg_max_drawdown': np.mean([r.max_drawdown for r in oos_results]),
        'avg_win_rate': np.mean([r.win_rate for r in oos_results]),
        'total_oos_return': sum(r.total_return for r in oos_results),
        'num_windows': len(windows)
    }
    
    return {
        'windows': windows,
        'optimal_params_history': optimal_params_history,
        'oos_results': oos_results,
        'aggregated_metrics': avg_metrics
    }


def generate_trade_log(result: BacktestResult, filepath: Optional[str] = None) -> pd.DataFrame:
    """
    Generate detailed trade log from backtest result.
    
    Args:
        result: BacktestResult object
        filepath: Optional path to save CSV
    
    Returns:
        DataFrame with trade details
    """
    if not result.trades:
        return pd.DataFrame()
    
    records = []
    for trade in result.trades:
        records.append({
            'Symbol': trade.symbol,
            'Entry Time': trade.entry_time,
            'Exit Time': trade.exit_time,
            'Side': trade.side.value,
            'Entry Price': trade.entry_price,
            'Exit Price': trade.exit_price,
            'Size': trade.size,
            'P&L ($)': trade.pnl,
            'P&L (%)': trade.pnl_pct,
            'Fees': trade.fees,
            'Duration': trade.duration
        })
    
    df = pd.DataFrame(records)
    
    if filepath:
        df.to_csv(filepath, index=False)
    
    return df


def generate_equity_curve(result: BacktestResult, filepath: Optional[str] = None) -> pd.DataFrame:
    """
    Generate equity curve data with drawdown analysis.
    
    Args:
        result: BacktestResult object
        filepath: Optional path to save CSV
    
    Returns:
        DataFrame with equity curve data
    """
    equity = result.equity_curve
    
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max * 100
    
    df = pd.DataFrame({
        'Timestamp': equity.index,
        'Equity': equity.values,
        'Peak': rolling_max.values,
        'Drawdown (%)': drawdown.values
    })
    
    if filepath:
        df.to_csv(filepath, index=False)
    
    return df


# Example strategies for testing
def example_sma_strategy(data: pd.DataFrame, params: Dict) -> Dict[str, Any]:
    """
    Simple moving average crossover strategy.
    
    Params:
        fast_period: Fast SMA period
        slow_period: Slow SMA period
    """
    fast_period = params.get('fast_period', 10)
    slow_period = params.get('slow_period', 30)
    
    if len(data) < slow_period:
        return {'action': 'hold'}
    
    fast_sma = data['close'].rolling(fast_period).mean().iloc[-1]
    slow_sma = data['close'].rolling(slow_period).mean().iloc[-1]
    prev_fast = data['close'].rolling(fast_period).mean().iloc[-2]
    prev_slow = data['close'].rolling(slow_period).mean().iloc[-2]
    
    if prev_fast <= prev_slow and fast_sma > slow_sma:
        return {'action': 'buy', 'size': 1.0}
    elif prev_fast >= prev_slow and fast_sma < slow_sma:
        return {'action': 'sell', 'size': 1.0}
    
    return {'action': 'hold'}


def example_rsi_strategy(data: pd.DataFrame, params: Dict) -> Dict[str, Any]:
    """
    RSI mean reversion strategy.
    
    Params:
        period: RSI period
        oversold: Oversold threshold
        overbought: Overbought threshold
    """
    period = params.get('period', 14)
    oversold = params.get('oversold', 30)
    overbought = params.get('overbought', 70)
    
    if len(data) < period + 1:
        return {'action': 'hold'}
    
    # Calculate RSI
    delta = data['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    current_rsi = rsi.iloc[-1]
    prev_rsi = rsi.iloc[-2]
    
    if prev_rsi > oversold and current_rsi <= oversold:
        return {'action': 'buy', 'size': 1.0}
    elif prev_rsi < overbought and current_rsi >= overbought:
        return {'action': 'sell', 'size': 1.0}
    
    return {'action': 'hold'}


if __name__ == "__main__":
    # Example usage
    print("Backtester Module - Example Usage")
    print("=" * 50)
    
    # Generate synthetic data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)
    
    data = load_historical_data(
        "TEST",
        start_date,
        end_date,
        source="synthetic",
        trend=0.0001,
        volatility=0.02
    )
    
    print(f"Loaded {len(data.data)} data points")
    
    # Configure backtest
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000,
        commission_rate=0.001,
        stop_loss_pct=0.05,
        take_profit_pct=0.10
    )
    
    # Run backtest
    backtester = Backtester(config)
    backtester.load_data("TEST", data)
    
    result = backtester.run_backtest(
        example_sma_strategy,
        {'fast_period': 10, 'slow_period': 30}
    )
    
    print(f"\nBacktest Results:")
    print(f"Total Return: {result.total_return:.2f}%")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {result.max_drawdown:.2f}%")
    print(f"Win Rate: {result.win_rate:.1f}%")
    print(f"Profit Factor: {result.profit_factor:.2f}")
    print(f"Number of Trades: {len(result.trades)}")
