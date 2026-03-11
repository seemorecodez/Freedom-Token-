# Cloud Mining Orchestrator

**Status:** Framework/Simulation Mode  
**Purpose:** Cloud mining deployment orchestration framework for educational and simulation purposes.

## Overview

This skill provides a framework for orchestrating cloud-based cryptocurrency mining operations. It includes:

- Cloud instance deployment abstraction
- Miner configuration management (XMRig-focused)
- Profitability monitoring
- Cost-based auto-termination

## IMPORTANT DISCLAIMER

**This is a SIMULATION FRAMEWORK.** It does not perform actual cryptocurrency mining or cloud deployment. It is designed for:

- Educational purposes
- Cost modeling and simulation
- Infrastructure planning
- Testing orchestration logic

Actual cloud mining involves:
- Real financial costs
- Complex legal/tax implications
- Security risks
- Environmental concerns

## Components

### OrchestratorConfig

Configuration dataclass for mining operations:

```python
config = OrchestratorConfig(
    provider="aws",           # Cloud provider (aws, gcp, azure)
    region="us-east-1",       # Deployment region
    instance_type="t3.medium", # VM instance type
    max_cost_hourly=0.50,     # Max $/hour before termination
    wallet_address="...",     # Mining wallet address
    pool_url="pool.example.com:3333"
)
```

### Core Methods

#### `deploy_instance(config)`
Simulates cloud instance provisioning with the specified configuration.

**Returns:** `InstanceState` with instance ID, IP, and status.

#### `configure_miner(instance, config)`
Generates XMRig configuration for deployment to the instance.

**Returns:** `MinerConfig` with connection details and settings.

#### `monitor_profitability(instance, duration_minutes=60)`
Tracks simulated mining metrics and calculates profitability.

**Returns:** `ProfitabilityReport` with earnings, costs, and net profit.

#### `auto_terminate(instances, config)`
Evaluates running instances against cost thresholds and marks unprofitable ones for termination.

**Returns:** List of instances marked for termination.

## Usage Example

```python
from cloud_mining_orchestrator import (
    OrchestratorConfig,
    deploy_instance,
    configure_miner,
    monitor_profitability,
    auto_terminate
)

# Configure
config = OrchestratorConfig(
    provider="aws",
    region="us-east-1",
    instance_type="c5.2xlarge",
    max_cost_hourly=0.34,
    wallet_address="44...",
    pool_url="xmrpool.eu:3333"
)

# Deploy
instance = deploy_instance(config)

# Configure miner
miner_config = configure_miner(instance, config)

# Monitor
report = monitor_profitability(instance, duration_minutes=120)
print(f"Net profit: ${report.net_profit:.4f}")

# Auto-terminate if unprofitable
instances_to_terminate = auto_terminate([instance], config)
```

## Architecture

```
┌─────────────────┐
│  Orchestrator   │
│    Config       │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐  ┌──────────┐
│Deploy │  │Configure │
│Instance│  │  Miner   │
└───┬───┘  └────┬─────┘
    │           │
    └─────┬─────┘
          ▼
   ┌──────────────┐
   │   Monitor    │
   │Profitability │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │Auto-Terminate│
   │  (if needed) │
   └──────────────┘
```

## Testing

Run tests:

```bash
python -m pytest test_cloud_mining_orchestrator.py -v
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| provider | str | "aws" | Cloud provider name |
| region | str | "us-east-1" | Deployment region |
| instance_type | str | "t3.medium" | VM instance type |
| max_cost_hourly | float | 0.50 | Cost threshold ($/hr) |
| wallet_address | str | "" | Mining wallet address |
| pool_url | str | "" | Mining pool URL:port |
| threads | int | 4 | CPU threads for mining |
| donate_level | int | 1 | XMRig donate level (%) |

## Future Enhancements

- [ ] Multi-provider support abstraction
- [ ] GPU instance support
- [ ] Historical profitability tracking
- [ ] Spot/preemptible instance support
- [ ] Auto-scaling logic
- [ ] Real API integrations (simulation mode only)

## License

Educational framework - Use responsibly and in accordance with cloud provider ToS.
