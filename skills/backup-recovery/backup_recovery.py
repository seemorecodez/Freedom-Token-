#!/usr/bin/env python3
"""
Backup Recovery Skill
Automated state backup and recovery for trading systems and configurations.
"""

import os
import json
import gzip
import shutil
import hashlib
import tarfile
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Callable
from contextlib import contextmanager
import threading
import logging

# Optional imports with graceful fallback
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================

class BackupError(Exception):
    """General backup operation failure."""
    pass


class RestoreError(Exception):
    """Restore operation failure."""
    pass


class IntegrityError(Exception):
    """Backup integrity verification failure."""
    pass


class ConfigError(Exception):
    """Invalid configuration."""
    pass


class DestinationError(Exception):
    """Destination storage operation failure."""
    pass


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class BackupConfig:
    """Configuration for backup behavior.
    
    Attributes:
        frequency_hours: How often to run automatic backups
        retention_days: How long to keep backups before cleanup
        destinations: List of storage destinations ('local', 's3')
        compress: Whether to gzip compress backups
        encrypt: Whether to encrypt backup contents
        encryption_key: Optional encryption key (auto-generated if None)
        local_path: Local directory for backup storage
        s3_bucket: S3 bucket name for cloud storage
        s3_prefix: Prefix/path within S3 bucket
        s3_region: AWS region for S3 bucket
        s3_access_key: AWS access key (optional, uses default chain if not set)
        s3_secret_key: AWS secret key (optional)
    """
    frequency_hours: int = 6
    retention_days: int = 30
    destinations: List[str] = field(default_factory=lambda: ['local'])
    compress: bool = True
    encrypt: bool = False
    encryption_key: Optional[str] = None
    local_path: str = './backups'
    s3_bucket: Optional[str] = None
    s3_prefix: str = 'backups/'
    s3_region: str = 'us-east-1'
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    
    def __post_init__(self):
        if self.encrypt and not CRYPTO_AVAILABLE:
            raise ConfigError("Encryption requested but 'cryptography' package not installed")
        if 's3' in self.destinations:
            if not S3_AVAILABLE:
                raise ConfigError("S3 destination requested but 'boto3' package not installed")
            if not self.s3_bucket:
                raise ConfigError("S3 destination requires s3_bucket to be set")
        # Validate destination names
        valid_destinations = {'local', 's3'}
        for dest in self.destinations:
            if dest not in valid_destinations:
                raise ConfigError(f"Unknown destination: {dest}")
        if self.frequency_hours < 1:
            raise ConfigError("frequency_hours must be at least 1")
        if self.retention_days < 1:
            raise ConfigError("retention_days must be at least 1")


# =============================================================================
# Encryption Handler
# =============================================================================

class EncryptionHandler:
    """Handles AES-256 encryption/decryption of backup data."""
    
    def __init__(self, key: Optional[str] = None):
        if not CRYPTO_AVAILABLE:
            raise BackupError("Encryption requested but 'cryptography' not installed")
        
        if key:
            self.key = key.encode() if isinstance(key, str) else key
            self.fernet = Fernet(base64.urlsafe_b64encode(self.key[:32].ljust(32, b'0')))
        else:
            self.fernet = Fernet(Fernet.generate_key())
    
    @staticmethod
    def generate_key(password: str, salt: Optional[bytes] = None) -> tuple:
        """Generate encryption key from password using PBKDF2."""
        if salt is None:
            salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data."""
        return self.fernet.encrypt(data)
    
    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data."""
        return self.fernet.decrypt(data)


# =============================================================================
# Destinations
# =============================================================================

class BackupDestination:
    """Abstract base class for backup storage destinations."""
    
    def store(self, backup_id: str, data: bytes, metadata: Dict[str, Any]) -> str:
        """Store backup data. Returns URI/path."""
        raise NotImplementedError
    
    def retrieve(self, backup_id: str) -> tuple:
        """Retrieve backup data. Returns (data, metadata)."""
        raise NotImplementedError
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups."""
        raise NotImplementedError
    
    def delete(self, backup_id: str) -> bool:
        """Delete a backup."""
        raise NotImplementedError
    
    def exists(self, backup_id: str) -> bool:
        """Check if backup exists."""
        raise NotImplementedError


class LocalDestination(BackupDestination):
    """Local filesystem backup storage."""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_backup_dir(self, backup_id: str) -> Path:
        return self.base_path / backup_id
    
    def store(self, backup_id: str, data: bytes, metadata: Dict[str, Any]) -> str:
        backup_dir = self._get_backup_dir(backup_id)
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Store data
        data_path = backup_dir / 'backup.tar.gz'
        with open(data_path, 'wb') as f:
            f.write(data)
        
        # Store metadata
        meta_path = backup_dir / 'manifest.json'
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Stored backup {backup_id} at {backup_dir}")
        return str(backup_dir)
    
    def retrieve(self, backup_id: str) -> tuple:
        backup_dir = self._get_backup_dir(backup_id)
        if not backup_dir.exists():
            raise DestinationError(f"Backup {backup_id} not found at {backup_dir}")
        
        data_path = backup_dir / 'backup.tar.gz'
        meta_path = backup_dir / 'manifest.json'
        
        with open(data_path, 'rb') as f:
            data = f.read()
        
        with open(meta_path, 'r') as f:
            metadata = json.load(f)
        
        return data, metadata
    
    def list_backups(self) -> List[Dict[str, Any]]:
        backups = []
        if not self.base_path.exists():
            return backups
        
        for item in self.base_path.iterdir():
            if item.is_dir():
                meta_path = item / 'manifest.json'
                if meta_path.exists():
                    try:
                        with open(meta_path, 'r') as f:
                            metadata = json.load(f)
                            backups.append(metadata)
                    except Exception as e:
                        logger.warning(f"Failed to read metadata for {item}: {e}")
        
        return sorted(backups, key=lambda x: x.get('timestamp', ''), reverse=True)
    
    def delete(self, backup_id: str) -> bool:
        backup_dir = self._get_backup_dir(backup_id)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
            logger.info(f"Deleted backup {backup_id}")
            return True
        return False
    
    def exists(self, backup_id: str) -> bool:
        return self._get_backup_dir(backup_id).exists()


class S3Destination(BackupDestination):
    """AWS S3 backup storage."""
    
    def __init__(self, bucket: str, prefix: str = 'backups/', region: str = 'us-east-1',
                 access_key: Optional[str] = None, secret_key: Optional[str] = None):
        if not S3_AVAILABLE:
            raise BackupError("S3 destination requires 'boto3' package")
        
        self.bucket = bucket
        self.prefix = prefix.rstrip('/') + '/'
        self.region = region
        
        # Initialize S3 client
        config = {'region_name': region}
        if access_key and secret_key:
            config['aws_access_key_id'] = access_key
            config['aws_secret_access_key'] = secret_key
        
        self.s3 = boto3.client('s3', **config)
    
    def _get_key(self, backup_id: str, filename: str) -> str:
        return f"{self.prefix}{backup_id}/{filename}"
    
    def store(self, backup_id: str, data: bytes, metadata: Dict[str, Any]) -> str:
        try:
            # Store data
            data_key = self._get_key(backup_id, 'backup.tar.gz')
            self.s3.put_object(
                Bucket=self.bucket,
                Key=data_key,
                Body=data
            )
            
            # Store metadata
            meta_key = self._get_key(backup_id, 'manifest.json')
            self.s3.put_object(
                Bucket=self.bucket,
                Key=meta_key,
                Body=json.dumps(metadata, default=str).encode()
            )
            
            uri = f"s3://{self.bucket}/{data_key}"
            logger.info(f"Stored backup {backup_id} at {uri}")
            return uri
            
        except ClientError as e:
            raise DestinationError(f"Failed to store backup to S3: {e}")
    
    def retrieve(self, backup_id: str) -> tuple:
        try:
            data_key = self._get_key(backup_id, 'backup.tar.gz')
            meta_key = self._get_key(backup_id, 'manifest.json')
            
            data_obj = self.s3.get_object(Bucket=self.bucket, Key=data_key)
            data = data_obj['Body'].read()
            
            meta_obj = self.s3.get_object(Bucket=self.bucket, Key=meta_key)
            metadata = json.loads(meta_obj['Body'].read().decode())
            
            return data, metadata
            
        except ClientError as e:
            raise DestinationError(f"Failed to retrieve backup from S3: {e}")
    
    def list_backups(self) -> List[Dict[str, Any]]:
        backups = []
        try:
            paginator = self.s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket,
                Prefix=self.prefix
            )
            
            backup_ids = set()
            for page in pages:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    parts = key[len(self.prefix):].split('/')
                    if len(parts) >= 2:
                        backup_ids.add(parts[0])
            
            for backup_id in backup_ids:
                try:
                    meta_key = self._get_key(backup_id, 'manifest.json')
                    obj = self.s3.get_object(Bucket=self.bucket, Key=meta_key)
                    metadata = json.loads(obj['Body'].read().decode())
                    backups.append(metadata)
                except ClientError:
                    continue
            
            return sorted(backups, key=lambda x: x.get('timestamp', ''), reverse=True)
            
        except ClientError as e:
            raise DestinationError(f"Failed to list backups from S3: {e}")
    
    def delete(self, backup_id: str) -> bool:
        try:
            data_key = self._get_key(backup_id, 'backup.tar.gz')
            meta_key = self._get_key(backup_id, 'manifest.json')
            
            self.s3.delete_object(Bucket=self.bucket, Key=data_key)
            self.s3.delete_object(Bucket=self.bucket, Key=meta_key)
            
            logger.info(f"Deleted backup {backup_id} from S3")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete backup from S3: {e}")
            return False
    
    def exists(self, backup_id: str) -> bool:
        try:
            meta_key = self._get_key(backup_id, 'manifest.json')
            self.s3.head_object(Bucket=self.bucket, Key=meta_key)
            return True
        except ClientError:
            return False


# =============================================================================
# Backup Manager
# =============================================================================

class BackupManager:
    """Main class for managing backups and recovery."""
    
    def __init__(self, config: BackupConfig):
        self.config = config
        self.destinations: Dict[str, BackupDestination] = {}
        self.encryption: Optional[EncryptionHandler] = None
        self._lock = threading.RLock()
        
        # Initialize destinations
        for dest_name in config.destinations:
            if dest_name == 'local':
                self.destinations['local'] = LocalDestination(config.local_path)
            elif dest_name == 's3':
                self.destinations['s3'] = S3Destination(
                    bucket=config.s3_bucket,
                    prefix=config.s3_prefix,
                    region=config.s3_region,
                    access_key=config.s3_access_key,
                    secret_key=config.s3_secret_key
                )
            else:
                raise ConfigError(f"Unknown destination: {dest_name}")
        
        # Initialize encryption if requested
        if config.encrypt:
            self.encryption = EncryptionHandler(config.encryption_key)
    
    def _generate_backup_id(self) -> str:
        """Generate unique backup ID."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        random_suffix = hashlib.sha256(
            os.urandom(32) + timestamp.encode()
        ).hexdigest()[:8]
        return f"backup_{timestamp}_{random_suffix}"
    
    def _compute_checksum(self, data: bytes) -> str:
        """Compute SHA-256 checksum of data."""
        return hashlib.sha256(data).hexdigest()
    
    def _create_archive(self, sources: Dict[str, Any], work_dir: Path) -> Path:
        """Create tar.gz archive from sources."""
        archive_path = work_dir / 'backup.tar.gz'
        
        with tarfile.open(archive_path, 'w:gz') as tar:
            for name, content in sources.items():
                if isinstance(content, dict):
                    # JSON data
                    json_path = work_dir / f"{name}.json"
                    with open(json_path, 'w') as f:
                        json.dump(content, f, indent=2, default=str)
                    tar.add(json_path, arcname=f"{name}.json")
                    json_path.unlink()
                elif isinstance(content, (str, Path)):
                    # File or directory path
                    path = Path(content)
                    if path.exists():
                        tar.add(path, arcname=name)
                elif isinstance(content, bytes):
                    # Raw bytes
                    temp_path = work_dir / name
                    with open(temp_path, 'wb') as f:
                        f.write(content)
                    tar.add(temp_path, arcname=name)
                    temp_path.unlink()
        
        return archive_path
    
    def _extract_archive(self, archive_data: bytes, dest_dir: Path) -> Dict[str, Any]:
        """Extract tar.gz archive to directory."""
        archive_path = dest_dir / 'backup.tar.gz'
        with open(archive_path, 'wb') as f:
            f.write(archive_data)
        
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(dest_dir)
        
        archive_path.unlink()
        
        # Load extracted data
        result = {}
        for item in dest_dir.iterdir():
            if item.suffix == '.json':
                with open(item, 'r') as f:
                    result[item.stem] = json.load(f)
            else:
                result[item.name] = str(item)
        
        return result
    
    def create_backup(
        self,
        name: str = 'manual-backup',
        include_state: bool = True,
        include_configs: bool = True,
        include_database: bool = True,
        state_data: Optional[Dict[str, Any]] = None,
        config_data: Optional[Dict[str, Any]] = None,
        database_paths: Optional[List[str]] = None,
        custom_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new backup.
        
        Args:
            name: Human-readable backup name
            include_state: Whether to include runtime state
            include_configs: Whether to include configuration files
            include_database: Whether to include database files
            state_data: Runtime state to backup (positions, orders, etc.)
            config_data: Configuration data to backup
            database_paths: List of database file paths to backup
            custom_data: Additional custom data to include
            
        Returns:
            Backup ID string
            
        Raises:
            BackupError: If backup creation fails
        """
        with self._lock:
            backup_id = self._generate_backup_id()
            timestamp = datetime.utcnow().isoformat()
            
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    work_dir = Path(tmpdir)
                    sources = {}
                    
                    # Collect state data
                    if include_state and state_data:
                        sources['state'] = state_data
                    
                    # Collect config data
                    if include_configs and config_data:
                        sources['config'] = config_data
                    
                    # Collect database files
                    if include_database and database_paths:
                        for i, db_path in enumerate(database_paths):
                            if Path(db_path).exists():
                                sources[f'database_{i}'] = db_path
                    
                    # Add custom data
                    if custom_data:
                        sources['custom'] = custom_data
                    
                    if not sources:
                        raise BackupError("No data sources specified for backup")
                    
                    # Create archive
                    archive_path = self._create_archive(sources, work_dir)
                    
                    # Read archive data
                    with open(archive_path, 'rb') as f:
                        data = f.read()
                    
                    # Compress if requested (already compressed via tar.gz)
                    # Additional compression would be redundant
                    
                    # Encrypt if requested
                    if self.encryption:
                        data = self.encryption.encrypt(data)
                    
                    # Compute checksum
                    checksum = self._compute_checksum(data)
                    
                    # Build metadata
                    metadata = {
                        'backup_id': backup_id,
                        'name': name,
                        'timestamp': timestamp,
                        'size_bytes': len(data),
                        'checksum': checksum,
                        'checksum_algorithm': 'sha256',
                        'encrypted': self.encryption is not None,
                        'compressed': True,
                        'components': {
                            'state': include_state and state_data is not None,
                            'config': include_configs and config_data is not None,
                            'database': include_database and database_paths is not None,
                            'custom': custom_data is not None
                        },
                        'version': '1.0.0'
                    }
                    
                    # Store to all destinations
                    for dest_name, destination in self.destinations.items():
                        try:
                            uri = destination.store(backup_id, data, metadata)
                            logger.info(f"Backup {backup_id} stored to {dest_name}: {uri}")
                        except Exception as e:
                            logger.error(f"Failed to store backup to {dest_name}: {e}")
                            raise BackupError(f"Failed to store backup to {dest_name}: {e}")
                    
                    return backup_id
                    
            except Exception as e:
                if isinstance(e, BackupError):
                    raise
                raise BackupError(f"Backup creation failed: {e}")
    
    def list_backups(self, destination: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available backups.
        
        Args:
            destination: Specific destination to query (None = all)
            
        Returns:
            List of backup metadata dictionaries
        """
        if destination:
            if destination not in self.destinations:
                raise ConfigError(f"Unknown destination: {destination}")
            return self.destinations[destination].list_backups()
        
        # Aggregate from all destinations
        all_backups = {}
        for dest_name, dest in self.destinations.items():
            try:
                backups = dest.list_backups()
                for backup in backups:
                    bid = backup['backup_id']
                    if bid not in all_backups:
                        backup['destinations'] = [dest_name]
                        all_backups[bid] = backup
                    else:
                        all_backups[bid]['destinations'].append(dest_name)
            except Exception as e:
                logger.error(f"Failed to list backups from {dest_name}: {e}")
        
        return sorted(all_backups.values(), key=lambda x: x.get('timestamp', ''), reverse=True)
    
    def verify_backup(self, backup_id: str, destination: Optional[str] = None) -> bool:
        """Verify backup integrity.
        
        Args:
            backup_id: ID of backup to verify
            destination: Specific destination to verify (None = try all)
            
        Returns:
            True if backup is valid, False otherwise
            
        Raises:
            IntegrityError: If verification fails due to corruption
        """
        dests_to_check = ([destination] if destination 
                         else list(self.destinations.keys()))
        
        for dest_name in dests_to_check:
            if dest_name not in self.destinations:
                continue
            
            try:
                dest = self.destinations[dest_name]
                data, metadata = dest.retrieve(backup_id)
                
                # Verify checksum
                stored_checksum = metadata.get('checksum')
                computed_checksum = self._compute_checksum(data)
                
                if stored_checksum != computed_checksum:
                    raise IntegrityError(
                        f"Checksum mismatch for backup {backup_id} at {dest_name}: "
                        f"expected {stored_checksum}, got {computed_checksum}"
                    )
                
                # Try to decrypt if encrypted
                if metadata.get('encrypted') and self.encryption:
                    try:
                        decrypted = self.encryption.decrypt(data)
                    except Exception as e:
                        raise IntegrityError(f"Failed to decrypt backup {backup_id}: {e}")
                
                logger.info(f"Backup {backup_id} verified successfully at {dest_name}")
                return True
                
            except IntegrityError:
                raise
            except Exception as e:
                logger.error(f"Failed to verify backup at {dest_name}: {e}")
                continue
        
        return False
    
    def restore_from_backup(
        self,
        backup_id: str,
        destination: Optional[str] = None,
        restore_state: bool = True,
        restore_configs: bool = True,
        restore_database: bool = True,
        restore_custom: bool = True,
        verify_integrity: bool = True,
        extract_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Restore from a backup.
        
        Args:
            backup_id: ID of backup to restore
            destination: Specific destination to restore from (None = try all)
            restore_state: Whether to restore state data
            restore_configs: Whether to restore configuration
            restore_database: Whether to restore database files
            restore_custom: Whether to restore custom data
            verify_integrity: Whether to verify checksums before restore
            extract_path: Path to extract files to (None = temp directory)
            
        Returns:
            Dictionary containing restored data
            
        Raises:
            RestoreError: If restore operation fails
        """
        with self._lock:
            if verify_integrity:
                try:
                    if not self.verify_backup(backup_id, destination):
                        raise RestoreError(f"Backup {backup_id} integrity verification failed")
                except IntegrityError as e:
                    raise RestoreError(f"Backup integrity check failed: {e}")
            
            dests_to_try = ([destination] if destination 
                          else list(self.destinations.keys()))
            
            for dest_name in dests_to_try:
                if dest_name not in self.destinations:
                    continue
                
                try:
                    dest = self.destinations[dest_name]
                    data, metadata = dest.retrieve(backup_id)
                    
                    # Decrypt if encrypted
                    if metadata.get('encrypted') and self.encryption:
                        data = self.encryption.decrypt(data)
                    
                    # Extract archive
                    extract_dir = Path(extract_path) if extract_path else Path(tempfile.mkdtemp())
                    extract_dir.mkdir(parents=True, exist_ok=True)
                    
                    restored = self._extract_archive(data, extract_dir)
                    
                    # Filter based on restore options
                    result = {}
                    if restore_state and 'state' in restored:
                        result['state'] = restored['state']
                    if restore_configs and 'config' in restored:
                        result['config'] = restored['config']
                    if restore_database:
                        for key in restored:
                            if key.startswith('database_'):
                                result[key] = restored[key]
                    if restore_custom and 'custom' in restored:
                        result['custom'] = restored['custom']
                    
                    logger.info(f"Restored backup {backup_id} from {dest_name}")
                    return result
                    
                except RestoreError:
                    raise
                except Exception as e:
                    logger.error(f"Failed to restore from {dest_name}: {e}")
                    continue
            
            raise RestoreError(f"Failed to restore backup {backup_id} from any destination")
    
    def delete_backup(self, backup_id: str, destination: Optional[str] = None) -> bool:
        """Delete a backup.
        
        Args:
            backup_id: ID of backup to delete
            destination: Specific destination (None = all)
            
        Returns:
            True if deleted successfully
        """
        deleted = False
        dests = ([destination] if destination else list(self.destinations.keys()))
        
        for dest_name in dests:
            if dest_name in self.destinations:
                if self.destinations[dest_name].delete(backup_id):
                    deleted = True
        
        return deleted
    
    def cleanup_old_backups(self, retention_days: Optional[int] = None) -> int:
        """Clean up backups older than retention period.
        
        Args:
            retention_days: Override retention period (None = use config)
            
        Returns:
            Number of backups deleted
        """
        retention = retention_days or self.config.retention_days
        cutoff = datetime.utcnow() - timedelta(days=retention)
        
        deleted_count = 0
        
        for dest_name, dest in self.destinations.items():
            try:
                backups = dest.list_backups()
                for backup in backups:
                    try:
                        timestamp = datetime.fromisoformat(backup['timestamp'].replace('Z', '+00:00'))
                        if timestamp < cutoff:
                            backup_id = backup['backup_id']
                            if dest.delete(backup_id):
                                deleted_count += 1
                                logger.info(f"Cleaned up old backup {backup_id}")
                    except Exception as e:
                        logger.warning(f"Failed to parse timestamp for backup: {e}")
            except Exception as e:
                logger.error(f"Failed to cleanup backups at {dest_name}: {e}")
        
        return deleted_count
    
    def get_backup_info(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific backup."""
        for dest_name, dest in self.destinations.items():
            try:
                if dest.exists(backup_id):
                    data, metadata = dest.retrieve(backup_id)
                    metadata['available_at'] = dest_name
                    return metadata
            except Exception:
                continue
        return None


# =============================================================================
# Convenience Functions
# =============================================================================

def quick_backup(
    state_data: Dict[str, Any],
    config_data: Dict[str, Any],
    backup_dir: str = './backups',
    name: str = 'quick-backup'
) -> str:
    """Quick one-liner backup function.
    
    Args:
        state_data: Runtime state to backup
        config_data: Configuration to backup
        backup_dir: Directory to store backup
        name: Backup name
        
    Returns:
        Backup ID
    """
    config = BackupConfig(
        destinations=['local'],
        local_path=backup_dir
    )
    manager = BackupManager(config)
    return manager.create_backup(
        name=name,
        state_data=state_data,
        config_data=config_data
    )


def quick_restore(
    backup_id: str,
    backup_dir: str = './backups',
    destination: Optional[str] = None
) -> Dict[str, Any]:
    """Quick one-liner restore function.
    
    Args:
        backup_id: ID of backup to restore
        backup_dir: Directory containing backups
        destination: Specific destination to restore from
        
    Returns:
        Restored data dictionary
    """
    config = BackupConfig(
        destinations=['local'],
        local_path=backup_dir
    )
    manager = BackupManager(config)
    return manager.restore_from_backup(backup_id, destination=destination)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """Command-line interface for backup operations."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Backup Recovery Tool')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a backup')
    create_parser.add_argument('--name', default='cli-backup', help='Backup name')
    create_parser.add_argument('--config', help='Path to config JSON file')
    create_parser.add_argument('--state', help='Path to state JSON file')
    create_parser.add_argument('--output', '-o', default='./backups', help='Output directory')
    create_parser.add_argument('--encrypt', action='store_true', help='Encrypt backup')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List backups')
    list_parser.add_argument('--path', '-p', default='./backups', help='Backup directory')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from backup')
    restore_parser.add_argument('id', help='Backup ID')
    restore_parser.add_argument('--path', '-p', default='./backups', help='Backup directory')
    restore_parser.add_argument('--output', '-o', help='Extract to directory')
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify backup integrity')
    verify_parser.add_argument('id', help='Backup ID')
    verify_parser.add_argument('--path', '-p', default='./backups', help='Backup directory')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean old backups')
    cleanup_parser.add_argument('--retention', '-r', type=int, default=30, help='Retention days')
    cleanup_parser.add_argument('--path', '-p', default='./backups', help='Backup directory')
    
    args = parser.parse_args()
    
    if args.command == 'create':
        config = BackupConfig(
            destinations=['local'],
            local_path=args.output,
            encrypt=args.encrypt
        )
        manager = BackupManager(config)
        
        state_data = None
        config_data = None
        
        if args.state:
            with open(args.state, 'r') as f:
                state_data = json.load(f)
        if args.config:
            with open(args.config, 'r') as f:
                config_data = json.load(f)
        
        backup_id = manager.create_backup(
            name=args.name,
            state_data=state_data,
            config_data=config_data
        )
        print(f"Created backup: {backup_id}")
    
    elif args.command == 'list':
        config = BackupConfig(
            destinations=['local'],
            local_path=args.path
        )
        manager = BackupManager(config)
        backups = manager.list_backups()
        
        print(f"{'ID':<40} {'Name':<20} {'Timestamp':<25} {'Size'}")
        print("-" * 95)
        for b in backups:
            size = b.get('size_bytes', 0)
            size_str = f"{size / 1024 / 1024:.1f} MB" if size > 1024 * 1024 else f"{size / 1024:.1f} KB"
            print(f"{b['backup_id']:<40} {b['name']:<20} {b['timestamp']:<25} {size_str}")
    
    elif args.command == 'restore':
        config = BackupConfig(
            destinations=['local'],
            local_path=args.path
        )
        manager = BackupManager(config)
        result = manager.restore_from_backup(
            args.id,
            extract_path=args.output
        )
        print(f"Restored backup {args.id}")
        print(f"Components: {list(result.keys())}")
    
    elif args.command == 'verify':
        config = BackupConfig(
            destinations=['local'],
            local_path=args.path
        )
        manager = BackupManager(config)
        if manager.verify_backup(args.id):
            print(f"Backup {args.id} is valid")
        else:
            print(f"Backup {args.id} verification failed")
            exit(1)
    
    elif args.command == 'cleanup':
        config = BackupConfig(
            destinations=['local'],
            local_path=args.path,
            retention_days=args.retention
        )
        manager = BackupManager(config)
        count = manager.cleanup_old_backups()
        print(f"Cleaned up {count} old backups")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
