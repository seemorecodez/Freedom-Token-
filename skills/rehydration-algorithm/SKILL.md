# Rehydration Algorithm

A skill for restoring system state from seed files. Enables complete system reconstruction from serialized state data.

## Purpose

The rehydration algorithm rebuilds a running system from a seed file containing:
- System configuration
- Memory state
- Component states
- Relationships between entities

## Core Components

### RehydrationConfig

Configuration class for controlling the restoration process:

```python
config = RehydrationConfig(
    seed_path="/path/to/seed.json",
    strict_mode=True,           # Fail on any integrity issue
    backup_existing=True,       # Backup before restoration
    verify_after=True,          # Verify integrity after restore
    memory_reconstruction=True  # Rebuild memory from seed
)
```

### Key Functions

| Function | Purpose |
|----------|---------|
| `parse_seed_file(path)` | Read and validate seed data |
| `restore_state(seed_data, config)` | Rebuild system from seed |
| `verify_integrity(system_state)` | Check restoration completeness |

## Seed File Format

```json
{
  "version": "1.0.0",
  "timestamp": "2026-03-12T02:14:00Z",
  "system": {
    "name": "agent-system",
    "components": [...]
  },
  "memory": {
    "short_term": [...],
    "long_term": [...]
  },
  "state": {
    "variables": {...},
    "connections": [...]
  }
}
```

## Usage

```python
from rehydration_algorithm import RehydrationConfig, restore_state, parse_seed_file

# Parse seed
seed_data = parse_seed_file("system.seed")

# Configure restoration
config = RehydrationConfig(seed_path="system.seed")

# Restore system
result = restore_state(seed_data, config)

# Verify
if result.integrity_check.passed:
    print("System restored successfully")
```

## Error Handling

- `SeedFormatError` - Invalid seed file structure
- `IntegrityError` - Restoration verification failed
- `ComponentError` - Individual component restoration failed

## Testing

Run tests:
```bash
python -m pytest test_rehydration_algorithm.py -v
```
