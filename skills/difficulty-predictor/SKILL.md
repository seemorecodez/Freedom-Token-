# Difficulty Predictor Skill

Machine learning models for predicting cryptocurrency network difficulty adjustments.

## Overview

This skill provides tools to predict the next difficulty adjustment for Proof-of-Work cryptocurrencies including Bitcoin (BTC), Bitcoin Cash (BCH), and Litecoin (LTC).

## Features

- **Multi-Coin Support**: BTC, BCH, LTC
- **Multiple Model Types**: Linear Regression and LSTM neural networks
- **Historical Data Fetching**: Automatic retrieval from public APIs
- **Confidence Scoring**: Statistical certainty metrics for predictions
- **Adjustment Timing**: Predicts when the next adjustment will occur

## Quick Start

```python
from difficulty_predictor import DifficultyPredictor, PredictorConfig

# Configure predictor
config = PredictorConfig(
    coin="BTC",
    model_type="lstm",  # or "linear"
    prediction_horizon=1
)

# Initialize and train
predictor = DifficultyPredictor(config)
predictor.fetch_historical_difficulty(days=90)
predictor.train_model()

# Predict next adjustment
prediction = predictor.predict_next_adjustment()
print(f"Predicted difficulty change: {prediction['predicted_change_percent']:.2f}%")
print(f"Confidence: {prediction['confidence']:.2f}")
```

## Configuration

### PredictorConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `coin` | str | "BTC" | Cryptocurrency to predict (BTC, BCH, LTC) |
| `model_type` | str | "linear" | Model type: "linear" or "lstm" |
| `prediction_horizon` | int | 1 | Number of adjustments ahead to predict |
| `lookback_periods` | int | 10 | Historical periods to use for training |

## API Reference

### DifficultyPredictor

#### `fetch_historical_difficulty(days: int = 90) -> pd.DataFrame`
Fetch historical difficulty data from public APIs.

**Parameters:**
- `days`: Number of days of history to fetch

**Returns:** DataFrame with columns: `timestamp`, `difficulty`, `block_height`

#### `train_model() -> None`
Train the prediction model on fetched historical data.

#### `predict_next_adjustment() -> dict`
Predict the next difficulty adjustment.

**Returns:**
```python
{
    "current_difficulty": float,
    "predicted_difficulty": float,
    "predicted_change_percent": float,
    "confidence": float,  # 0.0 to 1.0
    "estimated_adjustment_time": datetime,
    "blocks_until_adjustment": int,
    "model_accuracy": float
}
```

#### `calculate_confidence(predictions: np.ndarray) -> float`
Calculate prediction confidence based on model variance and historical accuracy.

#### `get_adjustment_timing() -> dict`
Get timing information for the next difficulty adjustment.

**Returns:**
```python
{
    "blocks_remaining": int,
    "estimated_time": datetime,
    "progress_percent": float  # Progress through current difficulty period
}
```

## Model Details

### Linear Regression Model
- Uses historical difficulty changes as features
- Predicts next difficulty based on trend analysis
- Fast training and inference
- Good for short-term predictions

### LSTM Model
- Deep learning approach using Keras/TensorFlow
- Captures complex temporal patterns
- Better for longer sequences
- Requires more training data

## Data Sources

- **BTC**: blockchain.info, mempool.space
- **BCH**: api.blockchair.com
- **LTC**: chain.so, litecoinspace.org

## Difficulty Adjustment Mechanics

### Bitcoin (BTC)
- Adjustment every 2016 blocks (~2 weeks)
- Target: 10 minutes per block
- Max adjustment: 4x up or down

### Bitcoin Cash (BCH)
- Same as BTC: 2016 block intervals
- Additional ASERT DAA for intra-period adjustments

### Litecoin (LTC)
- Adjustment every 2016 blocks (~3.5 days)
- Target: 2.5 minutes per block

## Example Usage

### Basic Prediction
```python
from difficulty_predictor import DifficultyPredictor, PredictorConfig

config = PredictorConfig(coin="BTC", model_type="linear")
predictor = DifficultyPredictor(config)

# Fetch and train
predictor.fetch_historical_difficulty(days=180)
predictor.train_model()

# Get prediction
result = predictor.predict_next_adjustment()
print(f"Next adjustment in ~{result['blocks_until_adjustment']} blocks")
print(f"Expected change: {result['predicted_change_percent']:.2f}%")
```

### Compare Models
```python
for model_type in ["linear", "lstm"]:
    config = PredictorConfig(coin="BTC", model_type=model_type)
    predictor = DifficultyPredictor(config)
    predictor.fetch_historical_difficulty(days=90)
    predictor.train_model()
    
    result = predictor.predict_next_adjustment()
    print(f"{model_type}: {result['predicted_change_percent']:.2f}% (confidence: {result['confidence']:.2f})")
```

### Batch Multiple Coins
```python
coins = ["BTC", "BCH", "LTC"]
results = {}

for coin in coins:
    config = PredictorConfig(coin=coin, model_type="linear")
    predictor = DifficultyPredictor(config)
    predictor.fetch_historical_difficulty(days=90)
    predictor.train_model()
    results[coin] = predictor.predict_next_adjustment()

# Print summary
for coin, result in results.items():
    print(f"{coin}: {result['predicted_change_percent']:+.2f}% (confidence: {result['confidence']:.1%})")
```

## Error Handling

The predictor raises specific exceptions:

- `DataFetchError`: Failed to fetch historical data
- `InsufficientDataError`: Not enough data for training
- `ModelTrainingError`: Model training failed
- `PredictionError`: Prediction computation failed

```python
from difficulty_predictor import DifficultyPredictor, PredictorConfig, DataFetchError

try:
    predictor = DifficultyPredictor(config)
    predictor.fetch_historical_difficulty()
except DataFetchError as e:
    print(f"Failed to fetch data: {e}")
```

## Dependencies

- `pandas`: Data manipulation
- `numpy`: Numerical computations
- `scikit-learn`: Linear regression models
- `tensorflow` (optional): LSTM models
- `requests`: API calls

## Notes

- Predictions are probabilistic and not financial advice
- Network difficulty depends on miner behavior which can be unpredictable
- LSTM models require TensorFlow installation: `pip install tensorflow`
- API rate limits apply; implement caching for production use
