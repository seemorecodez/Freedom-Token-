# Backup Recovery Skill

Automated state backup and recovery for trading systems and configurations.

## Overview

This skill provides comprehensive backup and recovery capabilities for trading systems, including:
- State snapshots (positions, orders, balances)
- Configuration backups (strategies, API keys, settings)
- Database backups (market data, trade history)
- Multiple destinations (local, cloud, encrypted)
- Compression and integrity verification

## Quick Start

```python
from backup_recovery import BackupManager, BackupConfig

# Configure backup settings
config = BackupConfig(
    frequency_hours=6,
    retention_days=30,
    destinations=['local', 's3'],
    compress=True,
    encrypt=True
)

# Initialize manager
manager = BackupManager(config)

# Create a backup
backup_id = manager.create_backup(
    name='daily-backup',
    include_state=True,
    include_configs=True,
    include_database=True
)

# List available backups
backups = manager.list_backups()

# Restore from backup
manager.restore_from_backup(backup_id, verify_integrity=True)
```

## BackupConfig Class

Configuration for backup behavior:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `frequency_hours` | int | 6 | Backup frequency in hours |
| `retention_days` | int | 30 | How long to keep backups |
| `destinations` | List[str] | ['local'] | Where to store backups |
| `compress` | bool | True | Enable gzip compression |
| `encrypt` | bool | False | Enable AES-256 encryption |
| `encryption_key` | Optional[str] | None | Key for encryption (auto-generated if None) |
| `local_path` | str | './backups' | Local backup directory |
| `s3_bucket` | Optional[str] | None | S3 bucket name |
| `s3_prefix` | str | 'backups/' | S3 key prefix |

## Destinations

### Local Storage
- Stores backups in local filesystem
- Configurable path via `local_path`
- Automatic directory creation

### S3 Cloud Storage
- Requires `boto3` package
- Configure bucket via `s3_bucket`
- Optional prefix for organization

### Encryption
- AES-256-GCM encryption
- Auto-generated key stored securely
- Separate encryption key per backup

## Backup Types

### State Backup
Captures runtime state:
- Open positions
- Pending orders
- Account balances
- PnL snapshots

### Configuration Backup
Captures system configuration:
- Strategy parameters
- API credentials (encrypted)
- Risk settings
- System preferences

### Database Backup
Captures persistent data:
- Market data (OHLCV)
- Trade history
- Order history
- System logs

## Integrity Verification

All backups include:
- SHA-256 checksums for each component
- Manifest file with metadata
- Version compatibility info
- Timestamp and backup ID

## Recovery

### Full Restore
```python
manager.restore_from_backup(backup_id)
```

### Selective Restore
```python
manager.restore_from_backup(
    backup_id,
    restore_state=True,
    restore_configs=False,
    restore_database=True
)
```

## Command Line Interface

```bash
# Create backup
python -m backup_recovery create --name daily --all

# List backups
python -m backup_recovery list

# Restore backup
python -m backup_recovery restore --id <backup-id>

# Verify backup integrity
python -m backup_recovery verify --id <backup-id>

# Clean old backups
python -m backup_recovery cleanup --retention 30
```

## Backup Retention

Automatic cleanup removes:
- Backups older than `retention_days`
- Failed/incomplete backups
- Orphaned manifest files

Manual cleanup:
```python
manager.cleanup_old_backups(retention_days=30)
```

## Error Handling

The skill provides specific exceptions:
- `BackupError` - General backup failure
- `RestoreError` - Recovery failure
- `IntegrityError` - Checksum verification failure
- `ConfigError` - Invalid configuration

## Best Practices

1. **Frequency**: Back up every 4-6 hours during trading
2. **Retention**: Keep 30 days of backups minimum
3. **Encryption**: Always encrypt backups containing API keys
4. **Testing**: Regularly test restore procedures
5. **Monitoring**: Alert on backup failures
6. **Offsite**: Use cloud storage for disaster recovery

## Dependencies

- `cryptography` - For AES encryption
- `boto3` - For S3 storage (optional)
- `pytest` - For testing

## Architecture

```
┌─────────────────┐
│  BackupManager  │
├─────────────────┤
│ - config        │
│ - destinations  │
├─────────────────┤
│ + create()      │
│ + list()        │
│ + restore()     │
│ + verify()      │
└────────┬────────┘
         │
    ┌────┴────┬──────────┐
    ▼         ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│ Local  │ │  S3    │ │Encrypt │
│Storage │ │Storage │ │ Handler│
└────────┘ └────────┘ └────────┘
```
