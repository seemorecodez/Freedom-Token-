# Mining Optimizer Skill

Profit switching and genetic parameter tuning for cryptocurrency mining.

## Overview

The mining-optimizer skill provides intelligent algorithm switching and parameter optimization for cryptocurrency mining operations. It supports profit-based switching between algorithms and uses genetic algorithms to evolve optimal mining parameters.

## Features

- **Profit Switching**: Automatically switch between mining algorithms based on real-time profitability
- **Genetic Parameter Tuning**: Evolve optimal mining settings using genetic algorithms
- **Difficulty Prediction**: Integrate difficulty forecasting for better profit estimation
- **Multi-Algorithm Support**: SHA-256, Scrypt, Ethash, RandomX
- **Profit Tracking**: Historical profit tracking per algorithm

## Supported Algorithms

| Algorithm | Coins | Typical Hardware |
|-----------|-------|------------------|
| SHA-256 | Bitcoin (BTC), Bitcoin Cash (BCH) | ASIC miners |
| Scrypt | Litecoin (LTC), Dogecoin (DOGE) | ASIC miners |
| Ethash | Ethereum Classic (ETC), Ubiq | GPUs |
| RandomX | Monero (XMR) | CPUs (ASIC-resistant) |

## Quick Start

```python
from mining_optimizer import MiningOptimizer, MiningConfig

# Configure mining pools and algorithms
config = MiningConfig(
    pools={
        'sha256': {'url': 'stratum+tcp://pool.example:3333', 'user': 'worker.1'},
        'scrypt': {'url': 'stratum+tcp://pool.example:3433', 'user': 'worker.1'},
        'ethash': {'url': 'stratum+tcp://pool.example:4444', 'user': 'worker.1'},
        'randomx': {'url': 'stratum+tcp://pool.example:5555', 'user': 'worker.1'}
    },
    switch_threshold=0.05,  # 5% profit difference to switch
    min_switch_interval=300  # Minimum 5 minutes between switches
)

# Initialize optimizer
optimizer = MiningOptimizer(config)

# Calculate current profitability
profits = optimizer.calculate_profitability(
    hashrates={'sha256': 100e12, 'scrypt': 2e9, 'ethash': 100e6, 'randomx': 10e3},
    power_cost=0.10  # $/kWh
)

# Switch to most profitable algorithm
best_algo = optimizer.switch_algorithm(profits)

# Run genetic tuning for optimal parameters
optimal_params = optimizer.genetic_parameter_tuner(
    algorithm='ethash',
    generations=50,
    population_size=30
)
```

## Configuration

### MiningConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pools` | dict | required | Pool configurations per algorithm |
| `switch_threshold` | float | 0.05 | Minimum profit difference to trigger switch (0.05 = 5%) |
| `min_switch_interval` | int | 300 | Minimum seconds between algorithm switches |
| `profit_history_size` | int | 1000 | Number of profit data points to retain |
| `difficulty_lookback` | int | 14 | Days of historical difficulty data for prediction |
| `genetic_params` | dict | see below | Genetic algorithm hyperparameters |

### Genetic Algorithm Parameters

```python
genetic_params = {
    'population_size': 30,      # Number of parameter sets per generation
    'mutation_rate': 0.1,       # Probability of parameter mutation
    'crossover_rate': 0.8,      # Probability of crossover
    'elitism_ratio': 0.1,       # Top % to preserve unchanged
    'max_generations': 100,     # Stopping condition
    'convergence_threshold': 0.01  # Stop when improvement < 1%
}
```

## API Reference

### MiningOptimizer

#### `calculate_profitability(hashrates, power_cost, coin_prices=None)`

Calculate profitability for each supported algorithm.

**Parameters:**
- `hashrates` (dict): Hashrate per algorithm in H/s
- `power_cost` (float): Power cost in $/kWh
- `coin_prices` (dict, optional): Override prices for coins

**Returns:** dict with profit per algorithm in USD/day

#### `switch_algorithm(profitability, current_algorithm=None)`

Determine if algorithm switch should occur.

**Parameters:**
- `profitability` (dict): Output from calculate_profitability()
- `current_algorithm` (str, optional): Currently active algorithm

**Returns:** tuple (should_switch: bool, target_algorithm: str)

#### `genetic_parameter_tuner(algorithm, fitness_fn=None, **kwargs)`

Evolve optimal mining parameters using genetic algorithm.

**Parameters:**
- `algorithm` (str): Target algorithm ('sha256', 'scrypt', 'ethash', 'randomx')
- `fitness_fn` (callable, optional): Custom fitness function
- `generations` (int): Number of generations to run
- `population_size` (int): Population size per generation

**Returns:** dict with optimal parameters and fitness score

#### `predict_difficulty(algorithm, days_ahead=7)`

Predict future difficulty using historical data and trend analysis.

**Parameters:**
- `algorithm` (str): Target algorithm
- `days_ahead` (int): Days to predict forward

**Returns:** Predicted difficulty value

#### `get_profit_history(algorithm=None, limit=100)`

Retrieve historical profit data.

**Parameters:**
- `algorithm` (str, optional): Filter by algorithm
- `limit` (int): Maximum records to return

**Returns:** List of profit history records

## Algorithm-Specific Parameters

### SHA-256 / Scrypt (ASIC)

- `frequency`: Chip frequency (MHz)
- `voltage`: Core voltage (mV)
- `fan_speed`: Fan speed percentage (0-100)
- `target_temp`: Target temperature (°C)

### Ethash (GPU)

- `core_clock`: GPU core clock offset (MHz)
- `memory_clock`: Memory clock offset (MHz)
- `power_limit`: Power limit percentage (0-100)
- `fan_curve`: Temperature-based fan curve

### RandomX (CPU)

- `threads`: Number of mining threads
- `affinity`: CPU core affinity mask
- `large_pages`: Use huge pages (True/False)
- `jit_compiler`: Enable JIT compilation

## Simulation Mode

When cloud APIs are unavailable, the optimizer runs in simulation mode using:
- Historical difficulty data patterns
- Synthetic market price generation
- Simulated hardware performance curves

Enable simulation mode explicitly:

```python
optimizer = MiningOptimizer(config, simulation_mode=True)
```

## Profit Calculation

Profit per algorithm is calculated as:

```
Revenue = (Hashrate / Network_Hashrate) * Block_Reward * Blocks_Per_Day * Coin_Price

Cost = Power_Consumption_kW * 24 * Power_Cost_Per_kWh

Profit = Revenue - Cost
```

Where:
- Network hashrate and block reward are fetched from blockchain APIs or simulated
- Power consumption is estimated based on hardware efficiency curves
- Coin prices are fetched from market APIs or simulated

## Genetic Algorithm Flow

1. **Initialize**: Create random population of parameter sets
2. **Evaluate**: Test each parameter set (mining simulation)
3. **Select**: Choose parents based on fitness (profitability)
4. **Crossover**: Combine parent parameters
5. **Mutate**: Randomly adjust some parameters
6. **Elitism**: Preserve top performers
7. **Repeat** until convergence or max generations

## Integration Examples

### With Mining Software

```python
# Hook into mining software
optimizer = MiningOptimizer(config)

def on_hashrate_update(hashrates):
    profits = optimizer.calculate_profitability(hashrates, power_cost=0.10)
    should_switch, new_algo = optimizer.switch_algorithm(profits, current_algo)
    
    if should_switch:
        mining_software.switch_algorithm(new_algo)
        current_algo = new_algo
```

### Automated Tuning Schedule

```python
# Run genetic tuning weekly
import schedule
import time

def weekly_tune():
    for algo in ['ethash', 'randomx']:
        params = optimizer.genetic_parameter_tuner(algo, generations=50)
        mining_software.apply_params(algo, params)

schedule.every().sunday.at("02:00").do(weekly_tune)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## Monitoring & Metrics

Track these key metrics:

- **Daily Profit**: USD/day per algorithm
- **Switch Frequency**: Algorithm changes per day
- **Switch Efficiency**: Profit gain per switch
- **Parameter Convergence**: GA improvement rate
- **Prediction Accuracy**: Difficulty prediction error

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Frequent switching | Increase `switch_threshold` or `min_switch_interval` |
| Slow GA convergence | Increase `population_size` or adjust `mutation_rate` |
| Inaccurate predictions | Increase `difficulty_lookback` days |
| API failures | Enable `simulation_mode=True` |

## Dependencies

- Python 3.8+
- numpy (for calculations)
- requests (for API calls)

Optional:
- scipy (for advanced prediction models)
- prometheus-client (for metrics export)

## License

MIT - See LICENSE file for details.
