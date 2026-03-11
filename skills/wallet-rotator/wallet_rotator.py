"""
Wallet Rotator - Privacy-focused temporary wallet generation

Implements wallet rotation for enhanced privacy in cryptocurrency transactions.
Uses single-use addresses to prevent blockchain surveillance and tracking.
"""

import hashlib
import secrets
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WalletRotator")


class Chain(Enum):
    """Supported blockchain networks"""
    ETHEREUM = "eth"
    BITCOIN = "btc"
    SOLANA = "sol"


class WalletStatus(Enum):
    """Lifecycle status of a wallet"""
    CREATED = auto()    # Generated, not yet used
    ACTIVE = auto()     # Currently the active receiving address
    USED = auto()       # Has received funds
    RETIRED = auto()    # Funds moved, no longer in use


@dataclass
class WalletMetadata:
    """Metadata tracking for a wallet"""
    address: str
    chain: Chain
    created_at: float
    status: WalletStatus = WalletStatus.CREATED
    usage_count: int = 0
    last_used_at: Optional[float] = None
    retired_at: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert metadata to dictionary"""
        return {
            "address": self.address,
            "chain": self.chain.value,
            "created_at": self.created_at,
            "status": self.status.name,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at,
            "retired_at": self.retired_at,
            "tags": self.tags
        }


@dataclass
class Wallet:
    """Represents a temporary wallet"""
    address: str
    chain: Chain
    metadata: WalletMetadata
    private_key: Optional[str] = None  # In real impl, use secure storage
    
    @property
    def is_active(self) -> bool:
        """Check if wallet is active"""
        return self.metadata.status == WalletStatus.ACTIVE
    
    @property
    def is_retired(self) -> bool:
        """Check if wallet is retired"""
        return self.metadata.status == WalletStatus.RETIRED


@dataclass
class WalletRotatorConfig:
    """Configuration for wallet rotation"""
    default_chain: Chain = Chain.ETHEREUM
    max_usage_per_wallet: int = 1  # Single-use by default
    auto_rotate: bool = True       # Auto-switch on usage
    retirement_threshold: int = 10  # Retire after N uses
    track_lifecycle: bool = True
    generate_backup: bool = True   # Pre-generate backup wallets
    backup_pool_size: int = 3


class WalletRotator:
    """
    Core class for wallet rotation management.
    
    Generates temporary addresses for transactions to enhance privacy
    by preventing address reuse and tracking.
    """
    
    # Address prefixes for different chains
    ADDRESS_PREFIXES = {
        Chain.ETHEREUM: "0x",
        Chain.BITCOIN: "bc1",
        Chain.SOLANA: ""  # Solana uses base58, no prefix
    }
    
    # Address lengths (in characters, excluding prefix)
    ADDRESS_LENGTHS = {
        Chain.ETHEREUM: 40,   # 20 bytes in hex
        Chain.BITCOIN: 39,    # bech32 address
        Chain.SOLANA: 44      # 32 bytes in base58
    }
    
    def __init__(self, config: Optional[WalletRotatorConfig] = None):
        """
        Initialize the wallet rotator
        
        Args:
            config: Configuration options
        """
        self.config = config or WalletRotatorConfig()
        
        # Wallet storage
        self._wallets: Dict[str, Wallet] = {}
        self._active_wallet: Optional[Wallet] = None
        self._backup_pool: List[Wallet] = []
        self._used_addresses: Set[str] = set()
        
        # Chain-specific counters
        self._chain_counters: Dict[Chain, int] = {
            Chain.ETHEREUM: 0,
            Chain.BITCOIN: 0,
            Chain.SOLANA: 0
        }
        
        # Initialize backup pool if configured
        if self.config.generate_backup:
            self._initialize_backup_pool()
        
        logger.info(f"WalletRotator initialized (chain: {self.config.default_chain.value})")
    
    def _initialize_backup_pool(self) -> None:
        """Pre-generate backup wallets for faster rotation"""
        for _ in range(self.config.backup_pool_size):
            wallet = self._create_wallet(self.config.default_chain)
            self._backup_pool.append(wallet)
        logger.debug(f"Initialized backup pool with {len(self._backup_pool)} wallets")
    
    def _create_wallet(self, chain: Chain) -> Wallet:
        """
        Internal method to create a new wallet
        
        Args:
            chain: Blockchain network
            
        Returns:
            New Wallet instance
        """
        address = self._generate_address(chain)
        
        metadata = WalletMetadata(
            address=address,
            chain=chain,
            created_at=time.time()
        )
        
        wallet = Wallet(
            address=address,
            chain=chain,
            metadata=metadata
        )
        
        self._wallets[address] = wallet
        self._chain_counters[chain] += 1
        
        return wallet
    
    def _generate_address(self, chain: Chain) -> str:
        """
        Generate a wallet address for the specified chain
        
        Args:
            chain: Blockchain network
            
        Returns:
            Generated address string
        """
        # Generate random bytes based on chain requirements
        if chain == Chain.ETHEREUM:
            # Ethereum: 0x + 40 hex chars (20 bytes)
            prefix = self.ADDRESS_PREFIXES[chain]
            random_bytes = secrets.token_hex(20)
            address = prefix + random_bytes
            
        elif chain == Chain.BITCOIN:
            # Bitcoin: bech32 format (bc1...)
            prefix = self.ADDRESS_PREFIXES[chain]
            # Simplified - real bech32 requires proper encoding
            random_bytes = secrets.token_hex(20)
            address = prefix + self._to_bech32_chars(random_bytes[:20])
            
        elif chain == Chain.SOLANA:
            # Solana: base58 encoded 32 bytes
            random_bytes = secrets.token_bytes(32)
            address = self._to_base58(random_bytes)
            
        else:
            raise ValueError(f"Unsupported chain: {chain}")
        
        # Ensure uniqueness
        if address in self._wallets:
            return self._generate_address(chain)
        
        return address
    
    def _to_bech32_chars(self, hex_str: str) -> str:
        """Convert hex to bech32-compatible characters"""
        bech32_charset = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
        result = ""
        for char in hex_str:
            idx = int(char, 16) % len(bech32_charset)
            result += bech32_charset[idx]
        return result
    
    def _to_base58(self, data: bytes) -> str:
        """Convert bytes to base58 string"""
        base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        
        # Convert bytes to integer
        num = int.from_bytes(data, 'big')
        
        # Encode to base58
        result = ""
        while num > 0:
            num, remainder = divmod(num, 58)
            result = base58_chars[remainder] + result
        
        # Add leading '1's for leading zero bytes
        leading_zeros = len(data) - len(data.lstrip(b'\x00'))
        return '1' * leading_zeros + result
    
    def generate_temp_wallet(self, chain: Optional[Chain] = None) -> Wallet:
        """
        Generate a new temporary wallet for single use
        
        Args:
            chain: Blockchain network (defaults to config.default_chain)
            
        Returns:
            New Wallet instance
            
        Example:
            >>> rotator = WalletRotator()
            >>> wallet = rotator.generate_temp_wallet(chain=Chain.ETHEREUM)
            >>> print(wallet.address)
            0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
        """
        target_chain = chain or self.config.default_chain
        
        wallet = self._create_wallet(target_chain)
        wallet.metadata.status = WalletStatus.ACTIVE
        
        logger.info(f"Generated {target_chain.value} wallet: {wallet.address[:16]}...")
        return wallet
    
    def rotate_wallet(self, chain: Optional[Chain] = None) -> Wallet:
        """
        Switch to a new active wallet
        
        Retires the current active wallet (if any) and activates a new one.
        Uses backup pool if available for faster rotation.
        
        Args:
            chain: Blockchain network (defaults to config.default_chain)
            
        Returns:
            New active Wallet instance
            
        Example:
            >>> rotator = WalletRotator()
            >>> wallet1 = rotator.get_active_wallet()
            >>> wallet2 = rotator.rotate_wallet()
            >>> assert wallet1.address != wallet2.address
        """
        target_chain = chain or self.config.default_chain
        
        # Retire current active wallet
        if self._active_wallet and self.config.track_lifecycle:
            self._retire_wallet(self._active_wallet.address)
        
        # Get new wallet from backup pool or generate fresh
        if self._backup_pool:
            new_wallet = self._backup_pool.pop(0)
            # Replenish backup pool
            if self.config.generate_backup:
                backup = self._create_wallet(self.config.default_chain)
                self._backup_pool.append(backup)
        else:
            new_wallet = self._create_wallet(target_chain)
        
        # Activate the new wallet
        new_wallet.metadata.status = WalletStatus.ACTIVE
        self._active_wallet = new_wallet
        
        logger.info(f"Rotated to new wallet: {new_wallet.address[:16]}...")
        return new_wallet
    
    def get_active_wallet(self, chain: Optional[Chain] = None) -> Wallet:
        """
        Get the currently active wallet
        
        If no active wallet exists, generates a new one.
        
        Args:
            chain: Blockchain network filter
            
        Returns:
            Active Wallet instance
        """
        if self._active_wallet is None:
            self._active_wallet = self.generate_temp_wallet(chain)
        
        # Filter by chain if specified
        if chain and self._active_wallet.chain != chain:
            return self.rotate_wallet(chain)
        
        return self._active_wallet
    
    def mark_used(self, address: str) -> None:
        """
        Mark a wallet address as used
        
        Updates metadata and triggers auto-rotation if configured.
        
        Args:
            address: The wallet address to mark
            
        Example:
            >>> rotator = WalletRotator()
            >>> wallet = rotator.get_active_wallet()
            >>> rotator.mark_used(wallet.address)
        """
        if address not in self._wallets:
            logger.warning(f"Unknown wallet address: {address}")
            return
        
        wallet = self._wallets[address]
        wallet.metadata.usage_count += 1
        wallet.metadata.last_used_at = time.time()
        wallet.metadata.status = WalletStatus.USED
        self._used_addresses.add(address)
        
        logger.info(f"Marked wallet as used: {address[:16]}... (count: {wallet.metadata.usage_count})")
        
        # Auto-rotate if configured and threshold reached
        if (self.config.auto_rotate and 
            wallet.metadata.usage_count >= self.config.max_usage_per_wallet):
            logger.info("Auto-rotating wallet due to usage threshold")
            self.rotate_wallet(wallet.chain)
    
    def _retire_wallet(self, address: str) -> None:
        """
        Internal: Retire a wallet from active use
        
        Args:
            address: The wallet address to retire
        """
        if address not in self._wallets:
            return
        
        wallet = self._wallets[address]
        wallet.metadata.status = WalletStatus.RETIRED
        wallet.metadata.retired_at = time.time()
        
        logger.debug(f"Retired wallet: {address[:16]}...")
    
    def track_wallet_lifecycle(self, address: str) -> Optional[Dict]:
        """
        Get lifecycle metadata for a wallet
        
        Args:
            address: The wallet address to query
            
        Returns:
            Wallet metadata dictionary or None if not found
            
        Example:
            >>> rotator = WalletRotator()
            >>> wallet = rotator.generate_temp_wallet()
            >>> lifecycle = rotator.track_wallet_lifecycle(wallet.address)
            >>> print(lifecycle['status'])
            'CREATED'
        """
        if address not in self._wallets:
            return None
        
        wallet = self._wallets[address]
        metadata = wallet.metadata.to_dict()
        
        # Add derived fields
        metadata['age_seconds'] = time.time() - wallet.metadata.created_at
        metadata['is_retired'] = wallet.is_retired
        metadata['is_active'] = wallet.is_active
        
        return metadata
    
    def get_all_wallets(self, chain: Optional[Chain] = None, 
                       status: Optional[WalletStatus] = None) -> List[Wallet]:
        """
        Get all wallets, optionally filtered
        
        Args:
            chain: Filter by blockchain
            status: Filter by lifecycle status
            
        Returns:
            List of Wallet instances
        """
        wallets = list(self._wallets.values())
        
        if chain:
            wallets = [w for w in wallets if w.chain == chain]
        
        if status:
            wallets = [w for w in wallets if w.metadata.status == status]
        
        return wallets
    
    def get_stats(self) -> Dict:
        """
        Get usage statistics
        
        Returns:
            Dictionary with wallet statistics
        """
        stats = {
            "total_wallets": len(self._wallets),
            "by_chain": {
                chain.value: self._chain_counters[chain]
                for chain in Chain
            },
            "by_status": {
                status.name: len(self.get_all_wallets(status=status))
                for status in WalletStatus
            },
            "used_addresses": len(self._used_addresses),
            "backup_pool_size": len(self._backup_pool),
            "active_wallet": self._active_wallet.address[:16] + "..." if self._active_wallet else None
        }
        
        return stats
    
    def retire_all(self) -> int:
        """
        Retire all active and used wallets
        
        Returns:
            Number of wallets retired
        """
        count = 0
        for wallet in self._wallets.values():
            if wallet.metadata.status in [WalletStatus.ACTIVE, WalletStatus.USED]:
                self._retire_wallet(wallet.address)
                count += 1
        
        self._active_wallet = None
        logger.info(f"Retired {count} wallets")
        return count
    
    def cleanup_retired(self, max_age_seconds: Optional[float] = None) -> int:
        """
        Remove retired wallets from memory
        
        Args:
            max_age_seconds: Only remove if retired longer than this
            
        Returns:
            Number of wallets removed
        """
        to_remove = []
        current_time = time.time()
        
        for address, wallet in self._wallets.items():
            if wallet.metadata.status == WalletStatus.RETIRED:
                if max_age_seconds is None:
                    to_remove.append(address)
                elif wallet.metadata.retired_at:
                    age = current_time - wallet.metadata.retired_at
                    if age > max_age_seconds:
                        to_remove.append(address)
        
        for address in to_remove:
            del self._wallets[address]
        
        logger.info(f"Cleaned up {len(to_remove)} retired wallets")
        return len(to_remove)


# Convenience functions for quick usage
def quick_wallet(chain: Chain = Chain.ETHEREUM) -> str:
    """Generate a single temporary wallet address"""
    rotator = WalletRotator()
    wallet = rotator.generate_temp_wallet(chain)
    return wallet.address


def rotate_for_privacy(addresses_used: List[str], chain: Chain = Chain.ETHEREUM) -> str:
    """
    Get a fresh wallet after using previous addresses
    
    Args:
        addresses_used: List of addresses that have been used
        chain: Blockchain network
        
    Returns:
        New wallet address
    """
    rotator = WalletRotator()
    
    for addr in addresses_used:
        rotator.mark_used(addr)
    
    return rotator.rotate_wallet(chain).address


# Example usage
if __name__ == "__main__":
    # Demo the wallet rotator
    print("=== Wallet Rotator Demo ===\n")
    
    # Initialize
    config = WalletRotatorConfig(
        default_chain=Chain.ETHEREUM,
        max_usage_per_wallet=1,
        auto_rotate=True
    )
    rotator = WalletRotator(config)
    
    # Generate wallets for different chains
    print("1. Generating wallets for different chains:")
    for chain in Chain:
        wallet = rotator.generate_temp_wallet(chain)
        print(f"   {chain.value.upper()}: {wallet.address}")
    
    # Rotate wallets
    print("\n2. Wallet rotation:")
    wallet1 = rotator.get_active_wallet()
    print(f"   Active: {wallet1.address[:30]}...")
    
    rotator.mark_used(wallet1.address)
    wallet2 = rotator.rotate_wallet()
    print(f"   Rotated: {wallet2.address[:30]}...")
    
    # Lifecycle tracking
    print("\n3. Lifecycle tracking:")
    lifecycle = rotator.track_wallet_lifecycle(wallet1.address)
    print(f"   Wallet 1 status: {lifecycle['status']}")
    print(f"   Usage count: {lifecycle['usage_count']}")
    
    # Statistics
    print("\n4. Statistics:")
    stats = rotator.get_stats()
    print(f"   Total wallets: {stats['total_wallets']}")
    print(f"   By chain: {stats['by_chain']}")
    print(f"   By status: {stats['by_status']}")
