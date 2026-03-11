"""
Trade Execution AI Skill

ML-powered trade execution using RandomForestRegressor + Technical Analysis + Reinforcement Learning.
Provides optimal entry/exit timing predictions with confidence scoring.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from enum import Enum
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import json
import pickle
import warnings
warnings.filterwarnings('ignore')


class SignalType(Enum):
    """Trade signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class ModelType(Enum):
    """Supported model types."""
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"


@dataclass
class AIConfig:
    """Configuration for the Trade Execution AI.
    
    Attributes:
        model_type: Type of ML model to use
        features: List of feature names to use for training
        confidence_threshold: Minimum confidence score to trigger a trade (0-1)
        lookback_window: Number of historical periods to consider
        prediction_horizon: Number of periods ahead to predict
        n_estimators: Number of trees in RandomForest
        max_depth: Maximum depth of trees
        random_state: Random seed for reproducibility
        rsi_period: Period for RSI calculation
        macd_fast: Fast period for MACD
        macd_slow: Slow period for MACD
        macd_signal: Signal period for MACD
        bb_period: Period for Bollinger Bands
        bb_std: Standard deviation multiplier for Bollinger Bands
        rl_learning_rate: Learning rate for RL component
        rl_discount_factor: Discount factor for RL
        rl_exploration_rate: Initial exploration rate for RL
    """
    model_type: ModelType = ModelType.RANDOM_FOREST
    features: List[str] = field(default_factory=lambda: [
        'returns', 'volatility', 'rsi', 'macd', 'macd_signal',
        'bb_position', 'volume_change', 'price_momentum'
    ])
    confidence_threshold: float = 0.7
    lookback_window: int = 20
    prediction_horizon: int = 5
    n_estimators: int = 100
    max_depth: int = 10
    random_state: int = 42
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    rl_learning_rate: float = 0.01
    rl_discount_factor: float = 0.95
    rl_exploration_rate: float = 0.1


class TechnicalAnalyzer:
    """Technical Analysis component for calculating indicators."""
    
    def __init__(self, config: AIConfig):
        self.config = config
    
    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """Calculate Relative Strength Index (RSI).
        
        RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss
        
        Args:
            prices: Price series
            
        Returns:
            RSI values (0-100)
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.config.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.config.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD (Moving Average Convergence Divergence).
        
        MACD Line = EMA(fast) - EMA(slow)
        Signal Line = EMA(MACD Line, signal_period)
        Histogram = MACD Line - Signal Line
        
        Args:
            prices: Price series
            
        Returns:
            Tuple of (MACD line, Signal line, Histogram)
        """
        ema_fast = prices.ewm(span=self.config.macd_fast).mean()
        ema_slow = prices.ewm(span=self.config.macd_slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.config.macd_signal).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def calculate_bollinger_bands(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands.
        
        Middle Band = SMA(period)
        Upper Band = Middle Band + (std * std_multiplier)
        Lower Band = Middle Band - (std * std_multiplier)
        
        Args:
            prices: Price series
            
        Returns:
            Tuple of (Upper band, Middle band, Lower band, Band position)
        """
        middle = prices.rolling(window=self.config.bb_period).mean()
        std = prices.rolling(window=self.config.bb_period).std()
        upper = middle + (std * self.config.bb_std)
        lower = middle - (std * self.config.bb_std)
        # Band position: 0 = at lower band, 1 = at upper band, 0.5 = at middle
        band_position = (prices - lower) / (upper - lower)
        return upper, middle, lower, band_position
    
    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Average True Range (ATR).
        
        ATR = Average of True Range over period
        True Range = max(high-low, |high-previous_close|, |low-previous_close|)
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period
            
        Returns:
            ATR values
        """
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators.
        
        Args:
            df: DataFrame with 'open', 'high', 'low', 'close', 'volume' columns
            
        Returns:
            DataFrame with all indicators added
        """
        df = df.copy()
        
        # Price-based features
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        df['volatility'] = df['returns'].rolling(window=self.config.lookback_window).std()
        df['price_momentum'] = df['close'] / df['close'].shift(self.config.lookback_window) - 1
        
        # Volume features
        df['volume_change'] = df['volume'].pct_change()
        df['volume_ma'] = df['volume'].rolling(window=self.config.lookback_window).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # RSI
        df['rsi'] = self.calculate_rsi(df['close'])
        
        # MACD
        macd, macd_signal, macd_hist = self.calculate_macd(df['close'])
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_histogram'] = macd_hist
        
        # Bollinger Bands
        upper, middle, lower, bb_position = self.calculate_bollinger_bands(df['close'])
        df['bb_upper'] = upper
        df['bb_middle'] = middle
        df['bb_lower'] = lower
        df['bb_position'] = bb_position
        df['bb_width'] = (upper - lower) / middle
        
        # ATR
        df['atr'] = self.calculate_atr(df['high'], df['low'], df['close'])
        df['atr_ratio'] = df['atr'] / df['close']
        
        # Price position features
        df['high_low_range'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-10)
        
        return df


class ReinforcementLearningComponent:
    """Reinforcement Learning component for trade timing optimization."""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self.q_table: Dict[Tuple, Dict[str, float]] = {}
        self.exploration_rate = config.rl_exploration_rate
        self.learning_rate = config.rl_learning_rate
        self.discount_factor = config.rl_discount_factor
        self.actions = ['buy', 'sell', 'hold']
        
    def _discretize_state(self, features: np.ndarray) -> Tuple:
        """Convert continuous features to discrete state for Q-table.
        
        Args:
            features: Feature vector
            
        Returns:
            Discretized state tuple
        """
        # Simple binning approach
        bins = 5
        discretized = []
        for f in features:
            if np.isnan(f) or np.isinf(f):
                discretized.append(0)
            else:
                # Clip to reasonable range and bin
                clipped = np.clip(f, -3, 3)
                binned = int((clipped + 3) / 6 * (bins - 1))
                discretized.append(binned)
        return tuple(discretized)
    
    def get_action(self, state_features: np.ndarray, train: bool = False) -> str:
        """Get action from RL component.
        
        Args:
            state_features: Current state features
            train: Whether in training mode (allows exploration)
            
        Returns:
            Action: 'buy', 'sell', or 'hold'
        """
        state = self._discretize_state(state_features)
        
        # Initialize Q-values for new state
        if state not in self.q_table:
            self.q_table[state] = {a: 0.0 for a in self.actions}
        
        # Epsilon-greedy policy
        if train and np.random.random() < self.exploration_rate:
            return np.random.choice(self.actions)
        
        # Choose best action
        q_values = self.q_table[state]
        return max(q_values, key=q_values.get)
    
    def update(self, state_features: np.ndarray, action: str, reward: float, 
               next_state_features: np.ndarray, done: bool = False):
        """Update Q-table with experience.
        
        Args:
            state_features: Current state
            action: Action taken
            reward: Reward received
            next_state_features: Next state
            done: Whether episode is complete
        """
        state = self._discretize_state(state_features)
        next_state = self._discretize_state(next_state_features)
        
        if next_state not in self.q_table:
            self.q_table[next_state] = {a: 0.0 for a in self.actions}
        
        # Q-learning update
        current_q = self.q_table[state][action]
        next_max_q = max(self.q_table[next_state].values()) if not done else 0
        new_q = current_q + self.learning_rate * (reward + self.discount_factor * next_max_q - current_q)
        self.q_table[state][action] = new_q
    
    def decay_exploration(self, decay_rate: float = 0.995, min_rate: float = 0.01):
        """Decay exploration rate over time.
        
        Args:
            decay_rate: Multiplicative decay rate
            min_rate: Minimum exploration rate
        """
        self.exploration_rate = max(min_rate, self.exploration_rate * decay_rate)
    
    def get_q_value(self, state_features: np.ndarray, action: str) -> float:
        """Get Q-value for a state-action pair.
        
        Args:
            state_features: State features
            action: Action
            
        Returns:
            Q-value
        """
        state = self._discretize_state(state_features)
        if state not in self.q_table:
            return 0.0
        return self.q_table[state].get(action, 0.0)


class TradeExecutionAI:
    """Main Trade Execution AI class.
    
    Combines RandomForest regression with Technical Analysis and 
    Reinforcement Learning for optimal trade execution timing.
    """
    
    def __init__(self, config: Optional[AIConfig] = None):
        """Initialize the Trade Execution AI.
        
        Args:
            config: Configuration object. Uses defaults if None.
        """
        self.config = config or AIConfig()
        self.model: Optional[RandomForestRegressor] = None
        self.scaler = StandardScaler()
        self.tech_analyzer = TechnicalAnalyzer(self.config)
        self.rl_component = ReinforcementLearningComponent(self.config)
        self.is_trained = False
        self.feature_importance: Dict[str, float] = {}
        
    def _prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """Prepare feature matrix from DataFrame.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Feature matrix
        """
        # Calculate technical indicators
        df_with_indicators = self.tech_analyzer.calculate_all_indicators(df)
        
        # Select configured features
        available_features = []
        for feat in self.config.features:
            if feat in df_with_indicators.columns:
                available_features.append(feat)
        
        # Get feature matrix
        X = df_with_indicators[available_features].copy()
        
        # Fill NaN values
        X = X.ffill().bfill().fillna(0)
        
        return X.values, available_features
    
    def _calculate_target(self, df: pd.DataFrame) -> np.ndarray:
        """Calculate target variable (future returns).
        
        Args:
            df: DataFrame with price data
            
        Returns:
            Target values (future returns normalized)
        """
        # Calculate future returns
        future_returns = df['close'].shift(-self.config.prediction_horizon) / df['close'] - 1
        
        # Normalize to -1 to 1 range for regression
        # Positive returns = good for buying
        # Negative returns = good for selling
        y = np.clip(future_returns * 100, -1, 1)
        
        return y.values
    
    def fit(self, df: pd.DataFrame, validation_split: float = 0.2) -> Dict[str, Any]:
        """Train the Trade Execution AI model.
        
        Args:
            df: Training DataFrame with OHLCV data
            validation_split: Fraction for validation set
            
        Returns:
            Training metrics dictionary
        """
        # Prepare features and target
        X, feature_names = self._prepare_features(df)
        y = self._calculate_target(df)
        
        # Remove NaN targets
        valid_mask = ~np.isnan(y)
        X = X[valid_mask]
        y = y[valid_mask]
        
        if len(X) < 100:
            raise ValueError(f"Insufficient data: {len(X)} samples. Need at least 100.")
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_split, random_state=self.config.random_state
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        # Train RandomForest model
        self.model = RandomForestRegressor(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            random_state=self.config.random_state,
            n_jobs=-1
        )
        self.model.fit(X_train_scaled, y_train)
        
        # Calculate feature importance
        self.feature_importance = dict(zip(
            feature_names, 
            self.model.feature_importances_
        ))
        
        # Training metrics
        train_score = self.model.score(X_train_scaled, y_train)
        val_score = self.model.score(X_val_scaled, y_val)
        
        # Train RL component on historical data
        self._train_rl_component(X_train_scaled, y_train)
        
        self.is_trained = True
        
        return {
            'train_r2': train_score,
            'validation_r2': val_score,
            'n_samples': len(X),
            'n_features': len(feature_names),
            'feature_importance': self.feature_importance
        }
    
    def _train_rl_component(self, X: np.ndarray, y: np.ndarray, episodes: int = 100):
        """Train RL component on historical data.
        
        Args:
            X: Feature matrix
            y: Target values
            episodes: Number of training episodes
        """
        for episode in range(episodes):
            total_reward = 0
            
            for i in range(len(X) - 1):
                state = X[i]
                actual_return = y[i]
                
                # Get action from RL
                action = self.rl_component.get_action(state, train=True)
                
                # Calculate reward based on action and actual return
                if action == 'buy' and actual_return > 0:
                    reward = actual_return
                elif action == 'sell' and actual_return < 0:
                    reward = -actual_return  # Profit from short
                elif action == 'hold' and abs(actual_return) < 0.1:
                    reward = 0.1  # Small reward for avoiding volatility
                else:
                    reward = -abs(actual_return)  # Penalty for wrong action
                
                next_state = X[i + 1] if i + 1 < len(X) else state
                self.rl_component.update(state, action, reward, next_state)
                total_reward += reward
            
            # Decay exploration
            self.rl_component.decay_exploration()
    
    def predict_trade_timing(self, df: pd.DataFrame, 
                             current_position: str = 'none') -> Dict[str, Any]:
        """Predict optimal trade entry/exit timing.
        
        Args:
            df: DataFrame with recent OHLCV data (at least lookback_window periods)
            current_position: Current position ('none', 'long', 'short')
            
        Returns:
            Dictionary with prediction results:
            - signal: 'buy', 'sell', or 'hold'
            - confidence: Confidence score (0-1)
            - predicted_return: Expected return
            - optimal_entry_price: Suggested entry price
            - optimal_exit_price: Suggested exit price
            - stop_loss: Suggested stop loss price
            - take_profit: Suggested take profit price
            - features: Dict of current indicator values
            - rl_action: RL component recommendation
        """
        if not self.is_trained:
            raise RuntimeError("Model must be trained before prediction. Call fit() first.")
        
        if len(df) < self.config.lookback_window:
            raise ValueError(f"Need at least {self.config.lookback_window} periods of data")
        
        # Get latest data
        latest_df = df.tail(self.config.lookback_window)
        
        # Prepare features
        X, feature_names = self._prepare_features(latest_df)
        X_latest = X[-1:]
        X_scaled = self.scaler.transform(X_latest)
        
        # ML prediction
        predicted_return = self.model.predict(X_scaled)[0]
        
        # Get prediction confidence using tree variance
        predictions = np.array([tree.predict(X_scaled)[0] for tree in self.model.estimators_])
        prediction_std = np.std(predictions)
        confidence = self._calculate_confidence(predicted_return, prediction_std)
        
        # RL component action
        rl_action = self.rl_component.get_action(X_scaled[0], train=False)
        
        # Combine ML and RL signals
        signal = self._combine_signals(predicted_return, rl_action, current_position, confidence)
        
        # Calculate price levels
        current_price = df['close'].iloc[-1]
        atr = latest_df['atr'].iloc[-1] if 'atr' in latest_df.columns else current_price * 0.02
        
        # Dynamic price levels based on volatility
        stop_loss_distance = max(atr * 2, current_price * 0.02)
        take_profit_distance = stop_loss_distance * 2  # 2:1 reward/risk ratio
        
        if signal == 'buy':
            optimal_entry = current_price
            stop_loss = current_price - stop_loss_distance
            take_profit = current_price + take_profit_distance
        elif signal == 'sell':
            optimal_entry = current_price
            stop_loss = current_price + stop_loss_distance
            take_profit = current_price - take_profit_distance
        else:
            optimal_entry = current_price
            stop_loss = None
            take_profit = None
        
        # Get current indicator values
        features_dict = {feat: X[-1][i] for i, feat in enumerate(feature_names)}
        
        return {
            'signal': signal,
            'confidence': round(confidence, 4),
            'predicted_return': round(predicted_return, 6),
            'current_price': round(current_price, 6),
            'optimal_entry_price': round(optimal_entry, 6),
            'optimal_exit_price': round(take_profit, 6) if take_profit else None,
            'stop_loss': round(stop_loss, 6) if stop_loss else None,
            'take_profit': round(take_profit, 6) if take_profit else None,
            'features': {k: round(float(v), 6) for k, v in features_dict.items()},
            'rl_action': rl_action,
            'prediction_std': round(prediction_std, 6),
            'timestamp': pd.Timestamp.now().isoformat()
        }
    
    def _calculate_confidence(self, predicted_return: float, prediction_std: float) -> float:
        """Calculate confidence score based on prediction and uncertainty.
        
        Args:
            predicted_return: Predicted return value
            prediction_std: Standard deviation of predictions across trees
            
        Returns:
            Confidence score (0-1)
        """
        # Base confidence on prediction magnitude
        magnitude_confidence = min(abs(predicted_return) * 2, 1.0)
        
        # Reduce confidence if predictions vary a lot
        uncertainty_penalty = np.exp(-prediction_std * 5)
        
        # Combine factors
        confidence = magnitude_confidence * uncertainty_penalty
        
        return float(np.clip(confidence, 0, 1))
    
    def _combine_signals(self, predicted_return: float, rl_action: str,
                         current_position: str, confidence: float) -> str:
        """Combine ML and RL signals into final trade signal.
        
        Args:
            predicted_return: ML predicted return
            rl_action: RL recommended action
            current_position: Current position
            confidence: Confidence score
            
        Returns:
            Final signal: 'buy', 'sell', or 'hold'
        """
        # ML signal
        if predicted_return > 0.1:
            ml_signal = 'buy'
        elif predicted_return < -0.1:
            ml_signal = 'sell'
        else:
            ml_signal = 'hold'
        
        # Combine signals (voting)
        signals = [ml_signal, rl_action]
        
        # Require high confidence for trading
        if confidence < self.config.confidence_threshold:
            return 'hold'
        
        # Check position compatibility
        if current_position == 'long' and 'sell' in signals:
            return 'sell'  # Exit signal
        if current_position == 'short' and 'buy' in signals:
            return 'buy'  # Exit signal
        if current_position == 'none':
            # Both signals agree
            if ml_signal == rl_action and ml_signal != 'hold':
                return ml_signal
            # ML signal stronger
            if abs(predicted_return) > 0.2:
                return ml_signal
        
        return 'hold'
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores.
        
        Returns:
            Dictionary of feature names to importance scores
        """
        if not self.is_trained:
            raise RuntimeError("Model must be trained first")
        return self.feature_importance
    
    def save_model(self, filepath: str):
        """Save trained model to file.
        
        Args:
            filepath: Path to save model
        """
        if not self.is_trained:
            raise RuntimeError("Model must be trained before saving")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'config': self.config,
            'feature_importance': self.feature_importance,
            'q_table': self.rl_component.q_table,
            'exploration_rate': self.rl_component.exploration_rate
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
    
    def load_model(self, filepath: str):
        """Load trained model from file.
        
        Args:
            filepath: Path to load model from
        """
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.config = model_data['config']
        self.feature_importance = model_data['feature_importance']
        self.rl_component.q_table = model_data.get('q_table', {})
        self.rl_component.exploration_rate = model_data.get('exploration_rate', 0.01)
        self.is_trained = True
    
    def backtest(self, df: pd.DataFrame, initial_capital: float = 10000.0,
                 commission: float = 0.001) -> Dict[str, Any]:
        """Run backtest on historical data.
        
        Args:
            df: Historical OHLCV data
            initial_capital: Starting capital
            commission: Commission rate per trade
            
        Returns:
            Backtest results dictionary
        """
        if not self.is_trained:
            raise RuntimeError("Model must be trained before backtesting")
        
        capital = initial_capital
        position = 0  # 0 = none, positive = long, negative = short
        trades = []
        equity_curve = [initial_capital]
        
        # Walk-forward prediction
        for i in range(self.config.lookback_window, len(df) - self.config.prediction_horizon):
            window = df.iloc[i - self.config.lookback_window:i + 1]
            
            try:
                prediction = self.predict_trade_timing(
                    window,
                    current_position='long' if position > 0 else 'short' if position < 0 else 'none'
                )
                
                signal = prediction['signal']
                current_price = df['close'].iloc[i]
                
                # Execute trades
                if signal == 'buy' and position <= 0:
                    # Close short if exists, then buy
                    if position < 0:
                        capital += position * current_price * (1 - commission)
                        position = 0
                    # Open long
                    position = capital / current_price * (1 - commission)
                    capital = 0
                    trades.append({
                        'type': 'buy',
                        'price': current_price,
                        'timestamp': df.index[i] if hasattr(df, 'index') else i
                    })
                    
                elif signal == 'sell' and position >= 0:
                    # Close long if exists, then sell (short)
                    if position > 0:
                        capital = position * current_price * (1 - commission)
                        position = 0
                    # Open short
                    position = -capital / current_price * (1 - commission)
                    capital = 0
                    trades.append({
                        'type': 'sell',
                        'price': current_price,
                        'timestamp': df.index[i] if hasattr(df, 'index') else i
                    })
                
                # Calculate current equity
                if position > 0:
                    current_equity = position * current_price
                elif position < 0:
                    current_equity = -position * (2 * trades[-1]['price'] - current_price) if trades else initial_capital
                else:
                    current_equity = capital
                
                equity_curve.append(current_equity)
                
            except Exception:
                continue
        
        # Close final position
        final_price = df['close'].iloc[-1]
        if position > 0:
            capital = position * final_price * (1 - commission)
        elif position < 0:
            capital = -position * (2 * trades[-1]['price'] - final_price) * (1 - commission) if trades else initial_capital
        
        final_equity = capital if capital > 0 else equity_curve[-1]
        
        # Calculate metrics
        equity_curve = np.array(equity_curve)
        returns = np.diff(equity_curve) / equity_curve[:-1]
        
        total_return = (final_equity - initial_capital) / initial_capital
        
        return {
            'initial_capital': initial_capital,
            'final_equity': round(final_equity, 2),
            'total_return': round(total_return * 100, 2),
            'n_trades': len(trades),
            'win_rate': round(sum(1 for i, t in enumerate(trades) if i > 0 and 
                                  (t['type'] == 'sell' and trades[i-1]['type'] == 'buy' and 
                                   t['price'] > trades[i-1]['price']) or
                                  (t['type'] == 'buy' and trades[i-1]['type'] == 'sell' and 
                                   t['price'] < trades[i-1]['price'])) / max(1, len(trades)//2) * 100, 2),
            'sharpe_ratio': round(np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252), 2),
            'max_drawdown': round(np.max(np.maximum.accumulate(equity_curve) - equity_curve) / 
                                 np.maximum.accumulate(equity_curve).max() * 100, 2),
            'trades': trades[:50]  # Limit trades in output
        }


def create_sample_data(n_periods: int = 500, trend: float = 0.001,
                       volatility: float = 0.02) -> pd.DataFrame:
    """Create sample OHLCV data for testing.
    
    Args:
        n_periods: Number of periods to generate
        trend: Daily trend factor
        volatility: Daily volatility
        
    Returns:
        DataFrame with OHLCV columns
    """
    np.random.seed(42)
    
    # Generate price series
    returns = np.random.normal(trend, volatility, n_periods)
    prices = 100 * np.exp(np.cumsum(returns))
    
    # Generate OHLC from close prices
    noise = np.random.normal(0, volatility * 0.3, n_periods)
    high = prices * (1 + np.abs(noise))
    low = prices * (1 - np.abs(noise))
    open_price = prices * (1 + np.random.normal(0, volatility * 0.1, n_periods))
    
    # Generate volume
    volume = np.random.lognormal(10, 0.5, n_periods)
    
    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': prices,
        'volume': volume
    })
    
    return df


# Convenience function for quick usage
def predict_trade(df: pd.DataFrame, model_path: Optional[str] = None,
                  config: Optional[AIConfig] = None) -> Dict[str, Any]:
    """Quick prediction function.
    
    Args:
        df: OHLCV data
        model_path: Path to saved model (if None, trains new model)
        config: Configuration
        
    Returns:
        Prediction results
    """
    ai = TradeExecutionAI(config or AIConfig())
    
    if model_path:
        ai.load_model(model_path)
    else:
        ai.fit(df)
    
    return ai.predict_trade_timing(df)
