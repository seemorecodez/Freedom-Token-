# Fork Detection System

A blockchain fork detection skill that monitors chain states, identifies divergent instances, and alerts on fork events.

## Overview

This system monitors multiple blockchain nodes or chain sources to detect when the chain diverges into multiple branches (forks). It provides:

- **Chain Monitoring**: Continuously watches block hashes from multiple sources
- **Fork Detection**: Identifies when chain splits occur
- **Consensus Resolution**: Determines the main chain based on length/weight
- **Event Alerting**: Notifies when forks are detected

## Classes

### ForkConfig

Configuration class for fork detection parameters.

```python
from fork_detection_system import ForkConfig

config = ForkConfig(
    sources=["node1:8545", "node2:8545", "node3:8545"],
    check_interval=10.0,           # Seconds between checks
    confirmation_blocks=6,          # Blocks needed for confirmation
    alert_callback=on_fork_alert,   # Function called on fork detection
    history_size=1000              # Blocks to keep in memory
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| sources | list[str] | [] | List of blockchain node endpoints |
| check_interval | float | 10.0 | Seconds between chain checks |
| confirmation_blocks | int | 6 | Blocks required to consider fork confirmed |
| alert_callback | Callable | None | Function called on fork events |
| history_size | int | 1000 | Maximum blocks to track per source |
| consensus_threshold | float | 0.67 | Percentage agreement for consensus |

## Functions

### monitor_chain(config: ForkConfig)

Starts continuous monitoring of blockchain sources.

```python
import asyncio
from fork_detection_system import monitor_chain, ForkConfig

async def main():
    config = ForkConfig(sources=["http://node1:8545"])
    await monitor_chain(config)

asyncio.run(main())
```

### detect_fork(blocks_by_source: dict) -> Optional[ForkEvent]

Analyzes block data from multiple sources to detect forks.

```python
from fork_detection_system import detect_fork

# blocks_by_source format:
# { "source1": [(height, hash), ...], "source2": [...] }
fork = detect_fork(blocks_by_source)
if fork:
    print(f"Fork at height {fork.height}: {fork.branches}")
```

Returns `ForkEvent` with:
- `height`: Block height where fork occurred
- `parent_hash`: Hash of common parent block
- `branches`: List of divergent branch hashes
- `sources_by_branch`: Map of branch hash to source list
- `timestamp`: When fork was detected

### get_consensus(blocks_by_source: dict, height: int) -> Optional[str]

Determines the main chain hash at a given height based on majority consensus.

```python
from fork_detection_system import get_consensus

main_hash = get_consensus(blocks_by_source, height=100)
if main_hash:
    print(f"Consensus hash at height 100: {main_hash}")
```

## Alert System

Define an alert callback to handle fork events:

```python
def on_fork_alert(fork_event: ForkEvent, severity: str):
    """
    severity: 'warning' | 'critical' | 'resolved'
    """
    print(f"[FORK ALERT - {severity.upper()}]")
    print(f"  Height: {fork_event.height}")
    print(f"  Branches: {len(fork_event.branches)}")
    print(f"  Affected sources: {fork_event.affected_sources}")
    
    # Send to alerting system (PagerDuty, Slack, etc.)
    send_alert(fork_event)

config = ForkConfig(
    sources=[...],
    alert_callback=on_fork_alert
)
```

## Usage Example

```python
import asyncio
from fork_detection_system import (
    ForkConfig, monitor_chain, detect_fork, get_consensus, ForkEvent
)

async def alert_handler(event: ForkEvent, severity: str):
    print(f"🚨 FORK DETECTED at height {event.height}")
    print(f"   Branches: {event.branches}")
    print(f"   Severity: {severity}")

async def main():
    config = ForkConfig(
        sources=[
            "https://eth-mainnet.g.alchemy.com/v2/KEY1",
            "https://mainnet.infura.io/v3/KEY2",
            "https://cloudflare-eth.com"
        ],
        check_interval=15.0,
        confirmation_blocks=12,
        alert_callback=alert_handler
    )
    
    # Start monitoring
    await monitor_chain(config)

if __name__ == "__main__":
    asyncio.run(main())
```

## Fork Resolution

The system handles fork resolution automatically:

1. **Detection**: Identifies when sources report different hashes at same height
2. **Confirmation**: Waits for `confirmation_blocks` to avoid false positives
3. **Consensus**: Determines main chain by majority vote
4. **Resolution**: Marks fork as resolved when all sources converge
5. **Alerting**: Sends 'resolved' alert when fork ends

## Testing

Run the test suite:

```bash
python -m pytest test_fork_detection_system.py -v
```

## Dependencies

- Python 3.8+
- asyncio
- dataclasses
- typing

## License

MIT
