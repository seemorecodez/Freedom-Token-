"""
Unit tests for Wallet Rotator

Tests all core functionality including wallet generation, rotation,
lifecycle tracking, and multi-chain support.
"""

import unittest
import time
from wallet_rotator import (
    WalletRotator, WalletRotatorConfig, Wallet, WalletMetadata,
    WalletStatus, Chain, quick_wallet, rotate_for_privacy
)


class TestWalletRotator(unittest.TestCase):
    """Test cases for WalletRotator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = WalletRotatorConfig(
            default_chain=Chain.ETHEREUM,
            max_usage_per_wallet=1,
            auto_rotate=False,
            generate_backup=False
        )
        self.rotator = WalletRotator(self.config)
    
    def test_initialization(self):
        """Test rotator initialization"""
        self.assertEqual(self.rotator.config.default_chain, Chain.ETHEREUM)
        self.assertEqual(len(self.rotator._wallets), 0)
        self.assertIsNone(self.rotator._active_wallet)
    
    def test_generate_temp_wallet_ethereum(self):
        """Test Ethereum wallet generation"""
        wallet = self.rotator.generate_temp_wallet(Chain.ETHEREUM)
        
        self.assertIsInstance(wallet, Wallet)
        self.assertEqual(wallet.chain, Chain.ETHEREUM)
        self.assertTrue(wallet.address.startswith("0x"))
        self.assertEqual(len(wallet.address), 42)  # 0x + 40 hex chars
        self.assertEqual(wallet.metadata.status, WalletStatus.ACTIVE)
    
    def test_generate_temp_wallet_bitcoin(self):
        """Test Bitcoin wallet generation"""
        wallet = self.rotator.generate_temp_wallet(Chain.BITCOIN)
        
        self.assertIsInstance(wallet, Wallet)
        self.assertEqual(wallet.chain, Chain.BITCOIN)
        self.assertTrue(wallet.address.startswith("bc1"))
        self.assertEqual(wallet.metadata.status, WalletStatus.ACTIVE)
    
    def test_generate_temp_wallet_solana(self):
        """Test Solana wallet generation"""
        wallet = self.rotator.generate_temp_wallet(Chain.SOLANA)
        
        self.assertIsInstance(wallet, Wallet)
        self.assertEqual(wallet.chain, Chain.SOLANA)
        # Solana addresses are base58, typically 32-44 chars
        self.assertGreater(len(wallet.address), 30)
        self.assertEqual(wallet.metadata.status, WalletStatus.ACTIVE)
    
    def test_wallet_uniqueness(self):
        """Test that generated wallets are unique"""
        addresses = set()
        for _ in range(10):
            wallet = self.rotator.generate_temp_wallet(Chain.ETHEREUM)
            addresses.add(wallet.address)
        
        self.assertEqual(len(addresses), 10)
    
    def test_get_active_wallet_creates_new(self):
        """Test that get_active_wallet creates wallet if none exists"""
        self.assertIsNone(self.rotator._active_wallet)
        
        wallet = self.rotator.get_active_wallet()
        
        self.assertIsNotNone(wallet)
        self.assertIsNotNone(self.rotator._active_wallet)
    
    def test_get_active_wallet_returns_existing(self):
        """Test that get_active_wallet returns existing active wallet"""
        wallet1 = self.rotator.get_active_wallet()
        wallet2 = self.rotator.get_active_wallet()
        
        self.assertEqual(wallet1.address, wallet2.address)
    
    def test_rotate_wallet(self):
        """Test wallet rotation"""
        wallet1 = self.rotator.get_active_wallet()
        wallet2 = self.rotator.rotate_wallet()
        
        self.assertNotEqual(wallet1.address, wallet2.address)
        self.assertEqual(self.rotator._active_wallet.address, wallet2.address)
    
    def test_rotate_wallet_retires_previous(self):
        """Test that rotation retires the previous wallet"""
        config = WalletRotatorConfig(auto_rotate=True, track_lifecycle=True)
        rotator = WalletRotator(config)
        
        wallet1 = rotator.get_active_wallet()
        wallet2 = rotator.rotate_wallet()
        
        self.assertEqual(wallet1.metadata.status, WalletStatus.RETIRED)
        self.assertEqual(wallet2.metadata.status, WalletStatus.ACTIVE)
    
    def test_mark_used(self):
        """Test marking wallet as used"""
        wallet = self.rotator.generate_temp_wallet()
        
        self.assertEqual(wallet.metadata.usage_count, 0)
        
        self.rotator.mark_used(wallet.address)
        
        self.assertEqual(wallet.metadata.usage_count, 1)
        self.assertEqual(wallet.metadata.status, WalletStatus.USED)
        self.assertIsNotNone(wallet.metadata.last_used_at)
    
    def test_mark_used_unknown_address(self):
        """Test marking unknown address as used"""
        # Should not raise exception
        self.rotator.mark_used("0xUnknownAddress")
    
    def test_auto_rotation(self):
        """Test automatic wallet rotation"""
        config = WalletRotatorConfig(
            max_usage_per_wallet=1,
            auto_rotate=True,
            generate_backup=False
        )
        rotator = WalletRotator(config)
        
        wallet1 = rotator.get_active_wallet()
        rotator.mark_used(wallet1.address)
        
        # Auto-rotation should have created a new active wallet
        self.assertIsNotNone(rotator._active_wallet)
        self.assertNotEqual(rotator._active_wallet.address, wallet1.address)
    
    def test_track_wallet_lifecycle(self):
        """Test lifecycle tracking"""
        wallet = self.rotator.generate_temp_wallet()
        
        lifecycle = self.rotator.track_wallet_lifecycle(wallet.address)
        
        self.assertIsNotNone(lifecycle)
        self.assertEqual(lifecycle['address'], wallet.address)
        self.assertEqual(lifecycle['chain'], Chain.ETHEREUM.value)
        self.assertEqual(lifecycle['status'], 'ACTIVE')
        self.assertIn('age_seconds', lifecycle)
    
    def test_track_wallet_lifecycle_unknown(self):
        """Test tracking unknown wallet"""
        lifecycle = self.rotator.track_wallet_lifecycle("0xUnknown")
        self.assertIsNone(lifecycle)
    
    def test_get_all_wallets(self):
        """Test getting all wallets"""
        self.rotator.generate_temp_wallet(Chain.ETHEREUM)
        self.rotator.generate_temp_wallet(Chain.BITCOIN)
        self.rotator.generate_temp_wallet(Chain.SOLANA)
        
        all_wallets = self.rotator.get_all_wallets()
        self.assertEqual(len(all_wallets), 3)
    
    def test_get_all_wallets_filtered_by_chain(self):
        """Test filtering wallets by chain"""
        self.rotator.generate_temp_wallet(Chain.ETHEREUM)
        self.rotator.generate_temp_wallet(Chain.ETHEREUM)
        self.rotator.generate_temp_wallet(Chain.BITCOIN)
        
        eth_wallets = self.rotator.get_all_wallets(chain=Chain.ETHEREUM)
        btc_wallets = self.rotator.get_all_wallets(chain=Chain.BITCOIN)
        
        self.assertEqual(len(eth_wallets), 2)
        self.assertEqual(len(btc_wallets), 1)
    
    def test_get_all_wallets_filtered_by_status(self):
        """Test filtering wallets by status"""
        wallet = self.rotator.generate_temp_wallet()
        self.rotator.mark_used(wallet.address)
        
        active_wallets = self.rotator.get_all_wallets(status=WalletStatus.ACTIVE)
        used_wallets = self.rotator.get_all_wallets(status=WalletStatus.USED)
        
        self.assertEqual(len(used_wallets), 1)
        self.assertEqual(used_wallets[0].address, wallet.address)
    
    def test_get_stats(self):
        """Test statistics retrieval"""
        self.rotator.generate_temp_wallet(Chain.ETHEREUM)
        self.rotator.generate_temp_wallet(Chain.BITCOIN)
        
        stats = self.rotator.get_stats()
        
        self.assertEqual(stats['total_wallets'], 2)
        self.assertEqual(stats['by_chain']['eth'], 1)
        self.assertEqual(stats['by_chain']['btc'], 1)
        self.assertIn('by_status', stats)
    
    def test_retire_all(self):
        """Test retiring all wallets"""
        self.rotator.generate_temp_wallet()
        self.rotator.generate_temp_wallet()
        
        count = self.rotator.retire_all()
        
        self.assertEqual(count, 2)
        retired = self.rotator.get_all_wallets(status=WalletStatus.RETIRED)
        self.assertEqual(len(retired), 2)
    
    def test_cleanup_retired(self):
        """Test cleanup of retired wallets"""
        wallet = self.rotator.generate_temp_wallet()
        self.rotator.mark_used(wallet.address)
        self.rotator._retire_wallet(wallet.address)
        
        count = self.rotator.cleanup_retired()
        
        self.assertEqual(count, 1)
        self.assertEqual(len(self.rotator._wallets), 0)
    
    def test_cleanup_retired_with_age(self):
        """Test cleanup with age threshold"""
        wallet = self.rotator.generate_temp_wallet()
        self.rotator._retire_wallet(wallet.address)
        
        # Should not clean up (just retired)
        count = self.rotator.cleanup_retired(max_age_seconds=3600)
        self.assertEqual(count, 0)
    
    def test_backup_pool_initialization(self):
        """Test backup pool initialization"""
        config = WalletRotatorConfig(generate_backup=True, backup_pool_size=3)
        rotator = WalletRotator(config)
        
        self.assertEqual(len(rotator._backup_pool), 3)
    
    def test_backup_pool_usage(self):
        """Test using wallets from backup pool"""
        config = WalletRotatorConfig(
            generate_backup=True,
            backup_pool_size=2,
            default_chain=Chain.ETHEREUM
        )
        rotator = WalletRotator(config)
        
        initial_pool_size = len(rotator._backup_pool)
        rotator.rotate_wallet()
        
        # Pool should be replenished
        self.assertEqual(len(rotator._backup_pool), initial_pool_size)


class TestWalletMetadata(unittest.TestCase):
    """Test cases for WalletMetadata"""
    
    def test_to_dict(self):
        """Test metadata serialization"""
        metadata = WalletMetadata(
            address="0x123",
            chain=Chain.ETHEREUM,
            created_at=1234567890.0,
            status=WalletStatus.ACTIVE,
            usage_count=5,
            tags=["test", "demo"]
        )
        
        data = metadata.to_dict()
        
        self.assertEqual(data['address'], "0x123")
        self.assertEqual(data['chain'], "eth")
        self.assertEqual(data['status'], "ACTIVE")
        self.assertEqual(data['usage_count'], 5)
        self.assertEqual(data['tags'], ["test", "demo"])


class TestWallet(unittest.TestCase):
    """Test cases for Wallet class"""
    
    def test_wallet_properties(self):
        """Test wallet properties"""
        metadata = WalletMetadata(
            address="0x123",
            chain=Chain.ETHEREUM,
            created_at=time.time(),
            status=WalletStatus.ACTIVE
        )
        wallet = Wallet(address="0x123", chain=Chain.ETHEREUM, metadata=metadata)
        
        self.assertTrue(wallet.is_active)
        self.assertFalse(wallet.is_retired)
    
    def test_wallet_retired_property(self):
        """Test retired property"""
        metadata = WalletMetadata(
            address="0x123",
            chain=Chain.ETHEREUM,
            created_at=time.time(),
            status=WalletStatus.RETIRED
        )
        wallet = Wallet(address="0x123", chain=Chain.ETHEREUM, metadata=metadata)
        
        self.assertFalse(wallet.is_active)
        self.assertTrue(wallet.is_retired)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions"""
    
    def test_quick_wallet(self):
        """Test quick_wallet function"""
        address = quick_wallet(Chain.ETHEREUM)
        
        self.assertIsInstance(address, str)
        self.assertTrue(address.startswith("0x"))
    
    def test_rotate_for_privacy(self):
        """Test rotate_for_privacy function"""
        old_addresses = ["0x111", "0x222"]
        new_address = rotate_for_privacy(old_addresses, Chain.ETHEREUM)
        
        self.assertIsInstance(new_address, str)
        self.assertTrue(new_address.startswith("0x"))
        self.assertNotIn(new_address, old_addresses)


class TestChainSupport(unittest.TestCase):
    """Test multi-chain support"""
    
    def test_all_chains_supported(self):
        """Test that all chains can generate wallets"""
        rotator = WalletRotator()
        
        for chain in Chain:
            wallet = rotator.generate_temp_wallet(chain)
            self.assertIsNotNone(wallet)
            self.assertEqual(wallet.chain, chain)
    
    def test_chain_counters(self):
        """Test chain-specific counters"""
        config = WalletRotatorConfig(generate_backup=False)
        rotator = WalletRotator(config)
        
        rotator.generate_temp_wallet(Chain.ETHEREUM)
        rotator.generate_temp_wallet(Chain.ETHEREUM)
        rotator.generate_temp_wallet(Chain.BITCOIN)
        
        self.assertEqual(rotator._chain_counters[Chain.ETHEREUM], 2)
        self.assertEqual(rotator._chain_counters[Chain.BITCOIN], 1)
        self.assertEqual(rotator._chain_counters[Chain.SOLANA], 0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""
    
    def test_invalid_chain(self):
        """Test handling of invalid chain"""
        # This should be caught by type hints, but test anyway
        rotator = WalletRotator()
        
        with self.assertRaises((ValueError, AttributeError)):
            # Attempt to generate with invalid chain
            rotator._generate_address("invalid_chain")  # type: ignore
    
    def test_multiple_rotations(self):
        """Test multiple consecutive rotations"""
        rotator = WalletRotator()
        addresses = []
        
        for _ in range(10):
            wallet = rotator.rotate_wallet()
            addresses.append(wallet.address)
        
        # All addresses should be unique
        self.assertEqual(len(set(addresses)), 10)
    
    def test_concurrent_chain_usage(self):
        """Test using multiple chains simultaneously"""
        rotator = WalletRotator()
        
        eth_wallet = rotator.generate_temp_wallet(Chain.ETHEREUM)
        btc_wallet = rotator.generate_temp_wallet(Chain.BITCOIN)
        sol_wallet = rotator.generate_temp_wallet(Chain.SOLANA)
        
        # All should exist and be active
        self.assertEqual(eth_wallet.metadata.status, WalletStatus.ACTIVE)
        self.assertEqual(btc_wallet.metadata.status, WalletStatus.ACTIVE)
        self.assertEqual(sol_wallet.metadata.status, WalletStatus.ACTIVE)


if __name__ == "__main__":
    unittest.main()
