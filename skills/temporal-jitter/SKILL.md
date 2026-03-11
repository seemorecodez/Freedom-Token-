# Temporal Jitter Skill

Adds random delays between trade executions to mask trading patterns and prevent detection.

## Purpose

Temporal jitter introduces unpredictable delays between:
- Sequential trade chunks
- Order placement and cancellation
- Trade execution and settlement
- API requests to exchanges

This prevents:
- Pattern recognition by market surveillance
- MEV extraction by front-running bots
- Timing analysis by adversaries
- Rate limiting triggers

## Algorithm

The jitter algorithm uses statistical distributions to generate delays:

### Distribution Types

1. **Uniform** - Equal probability across delay range
   - Most basic, predictable randomness
   - Use for: General obfuscation

2. **Exponential** - Higher probability of shorter delays
   - Natural-looking burst patterns
   - Use for: Mimicking organic trading behavior

3. **Gaussian** (Normal) - Bell curve centered on mean
   - Most "natural" looking delays
   - Use for: High stealth scenarios

### Stealth Levels

Pre-configured delay ranges for different security needs:

| Level | Min Delay | Max Delay | Use Case |
|-------|-----------|-----------|----------|
| low | 10s | 30s | Quick execution, basic obfuscation |
| medium | 30s | 120s | Balanced stealth vs speed |
| high | 30s | 300s | Strong protection, slower execution |
| paranoid | 1s | 600s | Maximum unpredictability |

## Components

### JitterConfig

Configuration class for jitter behavior:

```python
@dataclass
class JitterConfig:
    min_delay: float = 1.0          # Minimum delay in seconds
    max_delay: float = 60.0         # Maximum delay in seconds
    distribution: DistributionType = DistributionType.UNIFORM
    stealth_level: Optional[StealthLevel] = None  # Override with presets
```

### apply_jitter()

Generate a single random delay:

```python
delay = apply_jitter(config)
# Returns: float (seconds to delay)
```

### apply_jitter_sequence()

Generate multiple delays for a sequence of operations:

```python
delays = apply_jitter_sequence(num_delays=5, config=config, first_immediate=True)
# Returns: List[float] - delays between each operation
```

## Usage

### Basic Usage

```python
from temporal_jitter import JitterConfig, apply_jitter, StealthLevel
import time

# Use preset stealth level
config = JitterConfig(stealth_level=StealthLevel.HIGH)
delay = apply_jitter(config)
time.sleep(delay)
```

### Custom Configuration

```python
from temporal_jitter import JitterConfig, DistributionType, apply_jitter_sequence

# Custom delay range with Gaussian distribution
config = JitterConfig(
    min_delay=5.0,
    max_delay=30.0,
    distribution=DistributionType.GAUSSIAN
)

# Generate delays for 5 trade chunks
delays = apply_jitter_sequence(num_delays=5, config=config)
# Returns: [0, 12.4, 8.7, 15.2, 9.1] (first is 0 if first_immediate=True)
```

### Integration with Trading

```python
from temporal_jitter import JitterConfig, StealthLevel, apply_jitter
import time

def execute_trade_chunk(chunk, stealth_level):
    config = JitterConfig(stealth_level=stealth_level)
    
    # Delay before execution
    delay = apply_jitter(config)
    time.sleep(delay)
    
    # Execute the trade
    result = place_order(chunk)
    return result
```

## Distribution Details

### Uniform Distribution
- Every value between min and max has equal probability
- Simple, fast, no external dependencies
- Formula: `delay = min + random() * (max - min)`

### Exponential Distribution
- Skewed toward shorter delays
- Decay rate calculated from mean delay
- Formula: `delay = min + exponential(mean)`
- Clamped to max_delay to prevent extreme outliers

### Gaussian Distribution
- Bell curve with mean at (min + max) / 2
- Standard deviation = (max - min) / 6 (99.7% within range)
- Formula: `delay = gaussian(mean, std_dev)`
- Re-sampled if outside [min, max] bounds

## Best Practices

1. **Use stealth levels** for consistent behavior across components
2. **First chunk immediate** - Don't delay the first operation
3. **Log delays** for debugging and auditing
4. **Combine with other stealth** - Jitter works best with order chunking and decoys
5. **Consider network latency** - Account for API round-trip times

## Integration

Works standalone or as part of the Stealth Trader system:

```python
from stealth_trader import StealthTrader
from temporal_jitter import StealthLevel

trader = StealthTrader()
trader.execute_trade(
    amount=10000,
    stealth_level=StealthLevel.HIGH
)
# Temporal jitter applied automatically between chunks
```
