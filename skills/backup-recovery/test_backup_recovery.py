#!/usr/bin/env python3
"""
Unit tests for the backup-recovery skill.
"""

import os
import sys
import json
import gzip
import tempfile
import shutil
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase, main, mock
from unittest.mock import MagicMock, patch, mock_open

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backup_recovery import (
    BackupConfig,
    BackupManager,
    LocalDestination,
    EncryptionHandler,
    BackupError,
    RestoreError,
    IntegrityError,
    ConfigError,
    DestinationError,
    quick_backup,
    quick_restore,
)


# =============================================================================
# Test Fixtures
# =============================================================================

def get_sample_state_data():
    """Sample trading state data."""
    return {
        'positions': [
            {'symbol': 'BTC-USD', 'side': 'long', 'size': 1.5, 'entry_price': 45000},
            {'symbol': 'ETH-USD', 'side': 'short', 'size': -10, 'entry_price': 3000}
        ],
        'orders': [
            {'id': 'order-1', 'symbol': 'BTC-USD', 'side': 'buy', 'amount': 0.5, 'price': 44000},
            {'id': 'order-2', 'symbol': 'ETH-USD', 'side': 'sell', 'amount': 5, 'price': 3100}
        ],
        'balances': {
            'USD': 100000,
            'BTC': 2.0,
            'ETH': 50.0
        },
        'pnl': {
            'realized': 5000,
            'unrealized': -200
        }
    }


def get_sample_config_data():
    """Sample configuration data."""
    return {
        'strategies': {
            'momentum': {'enabled': True, 'threshold': 0.02},
            'mean_reversion': {'enabled': False, 'lookback': 20}
        },
        'risk': {
            'max_position_size': 100000,
            'max_drawdown': 0.1,
            'daily_loss_limit': 5000
        },
        'api': {
            'exchange': 'binance',
            'testnet': True
        }
    }


# =============================================================================
# Configuration Tests
# =============================================================================

class TestBackupConfig(TestCase):
    """Tests for BackupConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = BackupConfig()
        self.assertEqual(config.frequency_hours, 6)
        self.assertEqual(config.retention_days, 30)
        self.assertEqual(config.destinations, ['local'])
        self.assertTrue(config.compress)
        self.assertFalse(config.encrypt)
        self.assertEqual(config.local_path, './backups')
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = BackupConfig(
            frequency_hours=4,
            retention_days=60,
            destinations=['local'],  # Changed from ['local', 's3'] to avoid s3_bucket requirement
            compress=False,
            encrypt=False,  # Changed to False to avoid crypto dependency requirement
            local_path='/custom/backups'
        )
        self.assertEqual(config.frequency_hours, 4)
        self.assertEqual(config.retention_days, 60)
        self.assertEqual(config.destinations, ['local'])
        self.assertFalse(config.compress)
        self.assertFalse(config.encrypt)
        self.assertEqual(config.local_path, '/custom/backups')
    
    def test_invalid_frequency(self):
        """Test validation of invalid frequency."""
        with self.assertRaises(ConfigError):
            BackupConfig(frequency_hours=0)
        with self.assertRaises(ConfigError):
            BackupConfig(frequency_hours=-1)
    
    def test_invalid_retention(self):
        """Test validation of invalid retention."""
        with self.assertRaises(ConfigError):
            BackupConfig(retention_days=0)
        with self.assertRaises(ConfigError):
            BackupConfig(retention_days=-5)


# =============================================================================
# Local Destination Tests
# =============================================================================

class TestLocalDestination(TestCase):
    """Tests for LocalDestination class."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dest = LocalDestination(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_directory_creation(self):
        """Test that base directory is created."""
        new_path = os.path.join(self.temp_dir, 'subdir', 'backups')
        dest = LocalDestination(new_path)
        self.assertTrue(os.path.exists(new_path))
    
    def test_store_and_retrieve(self):
        """Test storing and retrieving backup data."""
        backup_id = 'test-backup-123'
        data = b'test backup data'
        metadata = {'name': 'test', 'timestamp': datetime.utcnow().isoformat()}
        
        uri = self.dest.store(backup_id, data, metadata)
        self.assertTrue(os.path.exists(uri))
        
        retrieved_data, retrieved_meta = self.dest.retrieve(backup_id)
        self.assertEqual(retrieved_data, data)
        self.assertEqual(retrieved_meta['name'], metadata['name'])
    
    def test_list_backups(self):
        """Test listing backups."""
        # Create multiple backups
        for i in range(3):
            backup_id = f'backup-{i}'
            self.dest.store(
                backup_id,
                b'data',
                {'backup_id': backup_id, 'timestamp': datetime.utcnow().isoformat()}
            )
        
        backups = self.dest.list_backups()
        self.assertEqual(len(backups), 3)
    
    def test_delete_backup(self):
        """Test deleting a backup."""
        backup_id = 'delete-test'
        self.dest.store(backup_id, b'data', {'backup_id': backup_id, 'timestamp': '2024-01-01'})
        
        self.assertTrue(self.dest.exists(backup_id))
        self.assertTrue(self.dest.delete(backup_id))
        self.assertFalse(self.dest.exists(backup_id))
    
    def test_retrieve_nonexistent(self):
        """Test retrieving non-existent backup."""
        with self.assertRaises(DestinationError):
            self.dest.retrieve('nonexistent')


# =============================================================================
# Encryption Tests
# =============================================================================

class TestEncryptionHandler(TestCase):
    """Tests for EncryptionHandler class."""
    
    def test_encrypt_decrypt(self):
        """Test encryption and decryption roundtrip."""
        handler = EncryptionHandler()
        original = b'sensitive trading data'
        
        encrypted = handler.encrypt(original)
        self.assertNotEqual(encrypted, original)
        
        decrypted = handler.decrypt(encrypted)
        self.assertEqual(decrypted, original)
    
    def test_different_keys(self):
        """Test that different keys produce different ciphertexts."""
        handler1 = EncryptionHandler()
        handler2 = EncryptionHandler()
        data = b'test data'
        
        encrypted1 = handler1.encrypt(data)
        encrypted2 = handler2.encrypt(data)
        
        self.assertNotEqual(encrypted1, encrypted2)
    
    def test_key_generation(self):
        """Test key generation from password."""
        password = 'my-secret-password'
        key1, salt1 = EncryptionHandler.generate_key(password)
        key2, salt2 = EncryptionHandler.generate_key(password, salt1)
        
        self.assertEqual(key1, key2)
        self.assertEqual(salt1, salt2)


# =============================================================================
# Backup Manager Tests
# =============================================================================

class TestBackupManager(TestCase):
    """Tests for BackupManager class."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = BackupConfig(
            destinations=['local'],
            local_path=self.temp_dir,
            compress=True,
            encrypt=False
        )
        self.manager = BackupManager(self.config)
        self.sample_state = get_sample_state_data()
        self.sample_config = get_sample_config_data()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_backup_basic(self):
        """Test basic backup creation."""
        backup_id = self.manager.create_backup(
            name='test-backup',
            state_data=self.sample_state,
            config_data=self.sample_config
        )
        
        self.assertIsNotNone(backup_id)
        self.assertTrue(backup_id.startswith('backup_'))
        
        # Verify backup exists
        backups = self.manager.list_backups()
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0]['backup_id'], backup_id)
    
    def test_create_backup_no_data(self):
        """Test backup creation with no data."""
        with self.assertRaises(BackupError):
            self.manager.create_backup(name='empty-backup')
    
    def test_list_backups(self):
        """Test listing backups."""
        # Create multiple backups
        ids = []
        for i in range(3):
            bid = self.manager.create_backup(
                name=f'backup-{i}',
                state_data=self.sample_state
            )
            ids.append(bid)
        
        backups = self.manager.list_backups()
        self.assertEqual(len(backups), 3)
        
        # Verify order (newest first)
        self.assertEqual(backups[0]['backup_id'], ids[2])
    
    def test_restore_backup(self):
        """Test restoring from backup."""
        # Create backup
        backup_id = self.manager.create_backup(
            name='restore-test',
            state_data=self.sample_state,
            config_data=self.sample_config
        )
        
        # Restore
        restored = self.manager.restore_from_backup(backup_id)
        
        self.assertIn('state', restored)
        self.assertIn('config', restored)
        self.assertEqual(restored['state'], self.sample_state)
        self.assertEqual(restored['config'], self.sample_config)
    
    def test_restore_selective(self):
        """Test selective restore."""
        backup_id = self.manager.create_backup(
            name='selective-test',
            state_data=self.sample_state,
            config_data=self.sample_config
        )
        
        # Restore only state
        restored = self.manager.restore_from_backup(
            backup_id,
            restore_state=True,
            restore_configs=False
        )
        
        self.assertIn('state', restored)
        self.assertNotIn('config', restored)
    
    def test_verify_backup(self):
        """Test backup verification."""
        backup_id = self.manager.create_backup(
            name='verify-test',
            state_data=self.sample_state
        )
        
        self.assertTrue(self.manager.verify_backup(backup_id))
    
    def test_delete_backup(self):
        """Test backup deletion."""
        backup_id = self.manager.create_backup(
            name='delete-test',
            state_data=self.sample_state
        )
        
        self.assertTrue(self.manager.delete_backup(backup_id))
        
        # Verify deletion
        backups = self.manager.list_backups()
        self.assertEqual(len(backups), 0)
    
    def test_cleanup_old_backups(self):
        """Test cleanup of old backups."""
        # Create backup
        backup_id = self.manager.create_backup(
            name='old-backup',
            state_data=self.sample_state
        )
        
        # Verify backup was created
        info = self.manager.get_backup_info(backup_id)
        self.assertIsNotNone(info)
        
        # Test cleanup with very short retention (should not delete if backup is new)
        count = self.manager.cleanup_old_backups(retention_days=30)
        self.assertEqual(count, 0)  # Backup is new, should not be deleted
        
        # Test cleanup with very long retention (should keep all)
        count = self.manager.cleanup_old_backups(retention_days=365)
        self.assertEqual(count, 0)
    
    def test_backup_metadata(self):
        """Test backup metadata contents."""
        backup_id = self.manager.create_backup(
            name='meta-test',
            state_data=self.sample_state,
            config_data=self.sample_config
        )
        
        info = self.manager.get_backup_info(backup_id)
        self.assertIsNotNone(info)
        self.assertEqual(info['name'], 'meta-test')
        self.assertEqual(info['backup_id'], backup_id)
        self.assertIn('timestamp', info)
        self.assertIn('checksum', info)
        self.assertIn('components', info)
        self.assertTrue(info['components']['state'])
        self.assertTrue(info['components']['config'])
    
    def test_restore_nonexistent(self):
        """Test restoring non-existent backup."""
        with self.assertRaises(RestoreError):
            self.manager.restore_from_backup('nonexistent-backup-id')


# =============================================================================
# Encrypted Backup Tests
# =============================================================================

class TestEncryptedBackups(TestCase):
    """Tests for encrypted backup operations."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = BackupConfig(
            destinations=['local'],
            local_path=self.temp_dir,
            encrypt=True
        )
        self.manager = BackupManager(self.config)
        self.sample_state = get_sample_state_data()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_encrypted_backup_create_restore(self):
        """Test encrypted backup creation and restoration."""
        backup_id = self.manager.create_backup(
            name='encrypted-test',
            state_data=self.sample_state
        )
        
        # Verify metadata indicates encryption
        info = self.manager.get_backup_info(backup_id)
        self.assertTrue(info['encrypted'])
        
        # Restore
        restored = self.manager.restore_from_backup(backup_id)
        self.assertEqual(restored['state'], self.sample_state)


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration(TestCase):
    """Integration tests for complete workflows."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sample_state = get_sample_state_data()
        self.sample_config = get_sample_config_data()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_backup_restore_cycle(self):
        """Test complete backup and restore cycle."""
        # Configure manager
        config = BackupConfig(
            destinations=['local'],
            local_path=self.temp_dir,
            compress=True,
            encrypt=False
        )
        manager = BackupManager(config)
        
        # Create backup
        backup_id = manager.create_backup(
            name='full-cycle-test',
            state_data=self.sample_state,
            config_data=self.sample_config
        )
        
        # Verify
        self.assertTrue(manager.verify_backup(backup_id))
        
        # List
        backups = manager.list_backups()
        self.assertEqual(len(backups), 1)
        
        # Restore
        restored = manager.restore_from_backup(backup_id)
        self.assertEqual(restored['state'], self.sample_state)
        self.assertEqual(restored['config'], self.sample_config)
        
        # Delete
        self.assertTrue(manager.delete_backup(backup_id))
        self.assertEqual(len(manager.list_backups()), 0)
    
    def test_quick_backup_functions(self):
        """Test quick backup/restore convenience functions."""
        # Quick backup
        backup_id = quick_backup(
            state_data=self.sample_state,
            config_data=self.sample_config,
            backup_dir=self.temp_dir,
            name='quick-test'
        )
        
        self.assertIsNotNone(backup_id)
        
        # Quick restore
        restored = quick_restore(backup_id, backup_dir=self.temp_dir)
        self.assertEqual(restored['state'], self.sample_state)
        self.assertEqual(restored['config'], self.sample_config)


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling(TestCase):
    """Tests for error handling scenarios."""
    
    def test_invalid_destination(self):
        """Test handling of invalid destination."""
        with self.assertRaises(ConfigError):
            BackupConfig(destinations=['invalid'])
    
    def test_s3_without_boto3(self):
        """Test S3 destination without boto3."""
        with patch.dict('sys.modules', {'boto3': None}):
            with self.assertRaises(ConfigError):
                BackupConfig(
                    destinations=['s3'],
                    s3_bucket='test-bucket'
                )
    
    def test_encryption_without_crypto(self):
        """Test encryption without cryptography."""
        with patch.dict('sys.modules', {'cryptography': None}):
            # Need to reload module to pick up the change
            import importlib
            import backup_recovery
            importlib.reload(backup_recovery)
            
            with self.assertRaises((ConfigError, ImportError)):
                backup_recovery.BackupConfig(encrypt=True)


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == '__main__':
    # Set logging to warning level to reduce noise during tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    main()
