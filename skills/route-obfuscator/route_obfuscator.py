"""
Route Obfuscator - Multi-hop routing through liquidity pools for privacy.

This module provides privacy-preserving transaction routing by creating
multi-hop paths through various venues (DEXs, CEXs, bridges) to obscure
the origin and destination of cryptocurrency transactions.
"""

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict, Callable, Any
from abc import ABC, abstractmethod


class VenueType(Enum):
    """Types of venues for routing."""
    DEX = "dex"
    CEX = "cex"
    BRIDGE = "bridge"


class SelectionStrategy(Enum):
    """Strategies for selecting hops in a route."""
    RANDOM = "random"
    COST_OPTIMIZED = "cost_optimized"
    PRIVACY_MAXIMIZED = "privacy_maximized"


@dataclass
class Venue:
    """Represents a venue for executing swaps or transfers."""
    name: str
    venue_type: VenueType
    supported_chains: List[str]
    supported_assets: List[str]
    fee_bps: int  # Basis points (1/100 of 1%)
    estimated_time_seconds: int
    requires_kyc: bool = False
    
    def supports_pair(self, chain: str, asset: str) -> bool:
        """Check if venue supports a chain-asset pair."""
        return chain in self.supported_chains and asset in self.supported_assets


@dataclass
class Hop:
    """Represents a single hop in a route."""
    source_chain: str
    source_asset: str
    target_chain: str
    target_asset: str
    venue: str
    amount: float
    fee_bps: int
    estimated_time_seconds: int
    time_delay_seconds: int = 0
    
    @property
    def is_bridge(self) -> bool:
        """Check if this hop is a cross-chain bridge."""
        return self.source_chain != self.target_chain
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute this hop.
        
        Returns:
            Dict containing execution result and metadata.
        """
        # Simulate time delay
        if self.time_delay_seconds > 0:
            time.sleep(self.time_delay_seconds)
        
        return {
            'success': True,
            'source_chain': self.source_chain,
            'source_asset': self.source_asset,
            'target_chain': self.target_chain,
            'target_asset': self.target_asset,
            'venue': self.venue,
            'amount': self.amount,
            'fee_bps': self.fee_bps,
            'time_delay': self.time_delay_seconds
        }


@dataclass
class Route:
    """Represents a complete obfuscated route."""
    hops: List[Hop]
    source_chain: str
    source_asset: str
    target_chain: str
    target_asset: str
    original_amount: float
    
    @property
    def total_cost_bps(self) -> int:
        """Calculate total cost in basis points."""
        return sum(hop.fee_bps for hop in self.hops)
    
    @property
    def estimated_time_seconds(self) -> int:
        """Calculate total estimated time."""
        return sum(hop.estimated_time_seconds + hop.time_delay_seconds for hop in self.hops)
    
    @property
    def privacy_score(self) -> float:
        """
        Calculate privacy score (0-1, higher is better).
        
        Factors:
        - Number of hops
        - Venue diversity
        - Cross-chain bridges
        - Time delays
        """
        if not self.hops:
            return 0.0
        
        # Base score from hop count (diminishing returns after 5 hops)
        hop_score = min(len(self.hops) / 5.0, 1.0) * 0.3
        
        # Venue diversity score
        unique_venues = len(set(hop.venue for hop in self.hops))
        venue_score = min(unique_venues / 3.0, 1.0) * 0.25
        
        # Bridge usage score
        bridge_hops = sum(1 for hop in self.hops if hop.is_bridge)
        bridge_score = min(bridge_hops / 2.0, 1.0) * 0.25
        
        # Time delay score
        delay_hops = sum(1 for hop in self.hops if hop.time_delay_seconds > 0)
        delay_score = (delay_hops / len(self.hops)) * 0.2
        
        return min(hop_score + venue_score + bridge_score + delay_score, 1.0)
    
    @property
    def hop_count(self) -> int:
        """Return number of hops in route."""
        return len(self.hops)


@dataclass
class RouteConfig:
    """
    Configuration for route obfuscation.
    
    Attributes:
        min_hops: Minimum number of intermediate hops
        max_hops: Maximum number of intermediate hops
        venues: List of allowed venue names
        chains: List of supported blockchain networks
        selection_strategy: How to select hops ('random', 'cost_optimized', 'privacy_maximized')
        allow_bridges: Whether to allow cross-chain bridges
        time_delay_range: Tuple of (min, max) seconds between hops
        asset_pool: Assets available for intermediate swaps
        max_slippage_bps: Maximum acceptable slippage in basis points
    """
    min_hops: int = 2
    max_hops: int = 5
    venues: Optional[List[str]] = None
    chains: Optional[List[str]] = None
    selection_strategy: str = 'random'
    allow_bridges: bool = True
    time_delay_range: Tuple[int, int] = (0, 0)
    asset_pool: Optional[List[str]] = None
    max_slippage_bps: int = 100
    
    def __post_init__(self):
        """Set default values for optional fields."""
        if self.venues is None:
            self.venues = ['uniswap', 'curve', 'jupiter', 'binance', 'wormhole']
        if self.chains is None:
            self.chains = ['ethereum', 'solana', 'arbitrum', 'base']
        if self.asset_pool is None:
            self.asset_pool = ['ETH', 'USDC', 'USDT', 'WBTC', 'SOL', 'MATIC']
        
        # Validate configuration
        if self.min_hops < 0:
            raise ValueError("min_hops must be non-negative")
        if self.max_hops < self.min_hops:
            raise ValueError("max_hops must be >= min_hops")
        if self.selection_strategy not in ['random', 'cost_optimized', 'privacy_maximized']:
            raise ValueError(f"Invalid selection_strategy: {self.selection_strategy}")


class RouteObfuscator:
    """
    Main class for finding and executing obfuscated routes.
    
    Provides multi-hop routing through various venues to obscure
the link between source and destination of cryptocurrency transactions.
    """
    
    # Built-in venue registry
    VENUES = {
        # DEXs
        'uniswap': Venue('uniswap', VenueType.DEX, 
                        ['ethereum', 'arbitrum', 'base', 'polygon'],
                        ['ETH', 'USDC', 'USDT', 'WBTC', 'DAI'], 30, 15),
        'curve': Venue('curve', VenueType.DEX,
                      ['ethereum', 'arbitrum', 'polygon'],
                      ['USDC', 'USDT', 'DAI', 'ETH'], 15, 20),
        'jupiter': Venue('jupiter', VenueType.DEX,
                        ['solana'],
                        ['SOL', 'USDC', 'USDT', 'WBTC', 'ETH'], 25, 10),
        'raydium': Venue('raydium', VenueType.DEX,
                        ['solana'],
                        ['SOL', 'USDC', 'USDT'], 30, 12),
        'pancakeswap': Venue('pancakeswap', VenueType.DEX,
                            ['bsc', 'ethereum'],
                            ['BNB', 'ETH', 'USDC', 'USDT'], 25, 15),
        
        # CEXs
        'binance': Venue('binance', VenueType.CEX,
                        ['ethereum', 'solana', 'bitcoin', 'arbitrum', 'base'],
                        ['ETH', 'SOL', 'BTC', 'USDC', 'USDT', 'BNB'], 100, 300, True),
        'coinbase': Venue('coinbase', VenueType.CEX,
                         ['ethereum', 'solana', 'bitcoin', 'base'],
                         ['ETH', 'SOL', 'BTC', 'USDC'], 150, 600, True),
        'kraken': Venue('kraken', VenueType.CEX,
                       ['ethereum', 'solana', 'bitcoin'],
                       ['ETH', 'SOL', 'BTC', 'USDC', 'USDT'], 120, 400, True),
        
        # Bridges
        'wormhole': Venue('wormhole', VenueType.BRIDGE,
                         ['ethereum', 'solana', 'arbitrum', 'base', 'polygon'],
                         ['ETH', 'SOL', 'USDC', 'USDT', 'WBTC'], 50, 600),
        'layerzero': Venue('layerzero', VenueType.BRIDGE,
                          ['ethereum', 'arbitrum', 'base', 'polygon', 'bsc'],
                          ['ETH', 'USDC', 'USDT'], 40, 300),
        'stargate': Venue('stargate', VenueType.BRIDGE,
                         ['ethereum', 'arbitrum', 'base', 'polygon'],
                         ['USDC', 'USDT', 'ETH'], 35, 180),
        'thorchain': Venue('thorchain', VenueType.BRIDGE,
                          ['ethereum', 'bitcoin', 'bsc'],
                          ['ETH', 'BTC', 'BNB'], 75, 600),
        'across': Venue('across', VenueType.BRIDGE,
                       ['ethereum', 'arbitrum', 'base', 'polygon'],
                       ['ETH', 'USDC', 'USDT'], 25, 60),
    }
    
    # Cross-chain bridge pairs
    BRIDGE_PAIRS = {
        ('ethereum', 'solana'): ['wormhole'],
        ('solana', 'ethereum'): ['wormhole'],
        ('ethereum', 'arbitrum'): ['wormhole', 'layerzero', 'stargate', 'across'],
        ('arbitrum', 'ethereum'): ['wormhole', 'layerzero', 'stargate', 'across'],
        ('ethereum', 'base'): ['wormhole', 'layerzero', 'stargate', 'across'],
        ('base', 'ethereum'): ['wormhole', 'layerzero', 'stargate', 'across'],
        ('ethereum', 'bitcoin'): ['thorchain'],
        ('bitcoin', 'ethereum'): ['thorchain'],
    }
    
    def __init__(self, config: Optional[RouteConfig] = None):
        """
        Initialize the route obfuscator.
        
        Args:
            config: RouteConfig instance, uses defaults if not provided
        """
        self.config = config or RouteConfig()
        self._venue_cache: Dict[str, Venue] = {}
    
    def _get_venue(self, name: str) -> Optional[Venue]:
        """Get venue by name with caching."""
        if name not in self._venue_cache:
            self._venue_cache[name] = self.VENUES.get(name)
        return self._venue_cache[name]
    
    def _get_eligible_venues(self, chain: str, asset: str, venue_type: Optional[VenueType] = None) -> List[Venue]:
        """Get venues that support a given chain-asset pair."""
        venues = []
        for name in self.config.venues:
            venue = self._get_venue(name)
            if venue and venue.supports_pair(chain, asset):
                if venue_type is None or venue.venue_type == venue_type:
                    venues.append(venue)
        return venues
    
    def _get_bridge_venues(self, source_chain: str, target_chain: str) -> List[Venue]:
        """Get bridge venues for a cross-chain transfer."""
        if not self.config.allow_bridges:
            return []
        
        bridge_names = self.BRIDGE_PAIRS.get((source_chain, target_chain), [])
        venues = []
        for name in bridge_names:
            if name in self.config.venues:
                venue = self._get_venue(name)
                if venue:
                    venues.append(venue)
        return venues
    
    def _select_intermediate_asset(self, current_asset: str, available_assets: List[str]) -> str:
        """Select an intermediate asset for swapping."""
        # Prefer stablecoins and major assets for liquidity
        preferred = ['USDC', 'USDT', 'ETH', 'WBTC']
        
        if self.config.selection_strategy == 'random':
            candidates = [a for a in available_assets if a != current_asset]
            return random.choice(candidates) if candidates else current_asset
        
        elif self.config.selection_strategy == 'cost_optimized':
            # Prefer assets with deep liquidity (stablecoins)
            for asset in preferred:
                if asset in available_assets and asset != current_asset:
                    return asset
            return random.choice([a for a in available_assets if a != current_asset])
        
        else:  # privacy_maximized
            # Select less common assets for better obfuscation
            common = set(preferred)
            uncommon = [a for a in available_assets if a not in common and a != current_asset]
            if uncommon:
                return random.choice(uncommon)
            return random.choice([a for a in available_assets if a != current_asset])
    
    def _generate_hop(
        self,
        source_chain: str,
        source_asset: str,
        target_chain: Optional[str] = None,
        target_asset: Optional[str] = None,
        amount: float = 0.0,
        allow_bridge: bool = True
    ) -> Optional[Hop]:
        """Generate a single hop."""
        # Determine if this should be a bridge hop
        if allow_bridge and target_chain and target_chain != source_chain:
            # Cross-chain hop
            bridges = self._get_bridge_venues(source_chain, target_chain)
            if not bridges:
                return None
            
            venue = random.choice(bridges)
            return Hop(
                source_chain=source_chain,
                source_asset=source_asset,
                target_chain=target_chain,
                target_asset=source_asset,  # Bridges typically keep same asset
                venue=venue.name,
                amount=amount,
                fee_bps=venue.fee_bps,
                estimated_time_seconds=venue.estimated_time_seconds,
                time_delay_seconds=random.randint(*self.config.time_delay_range) if self.config.time_delay_range[1] > 0 else 0
            )
        
        # Same-chain swap
        venues = self._get_eligible_venues(source_chain, source_asset, VenueType.DEX)
        if not venues:
            return None
        
        # Select target asset
        if target_asset:
            intermediate_asset = target_asset
        else:
            all_assets = set()
            for v in venues:
                all_assets.update(v.supported_assets)
            intermediate_asset = self._select_intermediate_asset(source_asset, list(all_assets))
        
        # Select venue
        if self.config.selection_strategy == 'cost_optimized':
            venue = min(venues, key=lambda v: v.fee_bps)
        elif self.config.selection_strategy == 'privacy_maximized':
            # Prefer venues with more supported assets (more obfuscation options)
            venue = max(venues, key=lambda v: len(v.supported_assets))
        else:
            venue = random.choice(venues)
        
        return Hop(
            source_chain=source_chain,
            source_asset=source_asset,
            target_chain=source_chain,
            target_asset=intermediate_asset,
            venue=venue.name,
            amount=amount,
            fee_bps=venue.fee_bps,
            estimated_time_seconds=venue.estimated_time_seconds,
            time_delay_seconds=random.randint(*self.config.time_delay_range) if self.config.time_delay_range[1] > 0 else 0
        )
    
    def find_route(
        self,
        source_chain: str,
        source_asset: str,
        target_chain: str,
        target_asset: str,
        amount: float,
        num_hops: Optional[int] = None
    ) -> Optional[Route]:
        """
        Discover a multi-hop route from source to target.
        
        Args:
            source_chain: Source blockchain network
            source_asset: Asset at source
            target_chain: Target blockchain network
            target_asset: Asset at destination
            amount: Amount to transfer
            num_hops: Specific number of hops, or None to randomize within config range
        
        Returns:
            Route object or None if no valid route found
        """
        # Validate chains are supported
        if source_chain not in self.config.chains or target_chain not in self.config.chains:
            return None
        
        # Determine number of hops
        if num_hops is None:
            num_hops = random.randint(self.config.min_hops, self.config.max_hops)
        
        hops = []
        current_chain = source_chain
        current_asset = source_asset
        
        for i in range(num_hops):
            is_last_hop = (i == num_hops - 1)
            
            if is_last_hop:
                # Final hop must reach target
                hop = self._generate_hop(
                    current_chain, current_asset,
                    target_chain, target_asset,
                    amount,
                    allow_bridge=True
                )
            else:
                # Intermediate hop - introduce randomness
                # Occasionally add a cross-chain hop for extra obfuscation
                should_bridge = (
                    self.config.allow_bridges and 
                    random.random() < 0.3 and  # 30% chance of bridge
                    len(self.config.chains) > 1
                )
                
                if should_bridge:
                    # Bridge to a random different chain
                    other_chains = [c for c in self.config.chains if c != current_chain]
                    if other_chains:
                        bridge_target = random.choice(other_chains)
                        hop = self._generate_hop(
                            current_chain, current_asset,
                            bridge_target, None,
                            amount,
                            allow_bridge=True
                        )
                        if hop:
                            hops.append(hop)
                            current_chain = bridge_target
                            current_asset = hop.target_asset
                            continue
                
                # Regular same-chain swap
                hop = self._generate_hop(
                    current_chain, current_asset,
                    None, None,
                    amount,
                    allow_bridge=False
                )
            
            if hop is None:
                return None
            
            hops.append(hop)
            current_chain = hop.target_chain
            current_asset = hop.target_asset
        
        # Verify final state matches target
        if current_chain != target_chain or current_asset != target_asset:
            return None
        
        return Route(
            hops=hops,
            source_chain=source_chain,
            source_asset=source_asset,
            target_chain=target_chain,
            target_asset=target_asset,
            original_amount=amount
        )
    
    def obfuscate_route(
        self,
        source_chain: str,
        source_asset: str,
        target_chain: str,
        target_asset: str,
        amount: float
    ) -> Optional[Route]:
        """
        Create an obfuscated route with intermediate hops.
        
        This is the main entry point for route obfuscation. It generates
        a multi-hop route through various venues to obscure the transaction path.
        
        Args:
            source_chain: Source blockchain network
            source_asset: Asset at source
            target_chain: Target blockchain network  
            target_asset: Asset at destination
            amount: Amount to transfer
        
        Returns:
            Route object or None if obfuscation not possible
        """
        # Try multiple times to find a valid route
        max_attempts = 10
        for _ in range(max_attempts):
            route = self.find_route(
                source_chain, source_asset,
                target_chain, target_asset,
                amount
            )
            if route:
                return route
        
        return None
    
    def estimate_cost(self, route: Route) -> Dict[str, Any]:
        """
        Estimate the total cost of a route.
        
        Args:
            route: Route to estimate
        
        Returns:
            Dict with cost breakdown
        """
        total_fee_bps = route.total_cost_bps
        total_fee_pct = total_fee_bps / 100  # Convert bps to percentage
        
        hop_costs = []
        for i, hop in enumerate(route.hops):
            hop_costs.append({
                'hop_number': i + 1,
                'venue': hop.venue,
                'fee_bps': hop.fee_bps,
                'is_bridge': hop.is_bridge
            })
        
        return {
            'total_fee_bps': total_fee_bps,
            'total_fee_percentage': total_fee_pct,
            'hop_costs': hop_costs,
            'estimated_slippage_bps': min(total_fee_bps // 2, self.config.max_slippage_bps)
        }
    
    def estimate_time(self, route: Route) -> Dict[str, Any]:
        """
        Estimate the total time for route execution.
        
        Args:
            route: Route to estimate
        
        Returns:
            Dict with time breakdown
        """
        hop_times = []
        for i, hop in enumerate(route.hops):
            hop_times.append({
                'hop_number': i + 1,
                'venue': hop.venue,
                'execution_time': hop.estimated_time_seconds,
                'time_delay': hop.time_delay_seconds,
                'total': hop.estimated_time_seconds + hop.time_delay_seconds
            })
        
        return {
            'total_time_seconds': route.estimated_time_seconds,
            'total_time_minutes': route.estimated_time_seconds / 60,
            'hop_times': hop_times
        }
    
    def validate_route(self, route: Route) -> Dict[str, Any]:
        """
        Validate a route for correctness and safety.
        
        Args:
            route: Route to validate
        
        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []
        
        # Check hop count
        if route.hop_count < self.config.min_hops:
            issues.append(f"Route has fewer hops ({route.hop_count}) than minimum ({self.config.min_hops})")
        if route.hop_count > self.config.max_hops:
            issues.append(f"Route has more hops ({route.hop_count}) than maximum ({self.config.max_hops})")
        
        # Check chain continuity
        for i, hop in enumerate(route.hops):
            if i > 0:
                prev_hop = route.hops[i - 1]
                if hop.source_chain != prev_hop.target_chain:
                    issues.append(f"Chain discontinuity at hop {i}")
                if hop.source_asset != prev_hop.target_asset:
                    issues.append(f"Asset discontinuity at hop {i}")
        
        # Check source/target match
        if route.hops and route.hops[0].source_chain != route.source_chain:
            issues.append("First hop source chain doesn't match route source")
        if route.hops and route.hops[-1].target_chain != route.target_chain:
            issues.append("Last hop target chain doesn't match route target")
        
        # Cost warnings
        cost = self.estimate_cost(route)
        if cost['total_fee_bps'] > 500:  # > 5%
            warnings.append("High fee route (>5% total fees)")
        
        # Privacy warnings
        if route.privacy_score < 0.3:
            warnings.append("Low privacy score - consider more hops or bridges")
        
        # CEX warnings
        cex_hops = [h for h in route.hops if self._get_venue(h.venue) and self._get_venue(h.venue).requires_kyc]
        if cex_hops:
            warnings.append(f"Route includes {len(cex_hops)} CEX hops requiring KYC")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'privacy_score': route.privacy_score,
            'recommended': len(issues) == 0 and len(warnings) <= 1
        }
    
    def get_supported_chains(self) -> List[str]:
        """Get list of supported chains."""
        return self.config.chains.copy()
    
    def get_supported_venues(self) -> List[str]:
        """Get list of configured venues."""
        return self.config.venues.copy()
    
    def get_venue_info(self, venue_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific venue."""
        venue = self._get_venue(venue_name)
        if venue:
            return {
                'name': venue.name,
                'type': venue.venue_type.value,
                'supported_chains': venue.supported_chains,
                'supported_assets': venue.supported_assets,
                'fee_bps': venue.fee_bps,
                'estimated_time_seconds': venue.estimated_time_seconds,
                'requires_kyc': venue.requires_kyc
            }
        return None


# Convenience functions for common use cases

def create_stealth_route(
    source_chain: str,
    source_asset: str,
    target_chain: str,
    target_asset: str,
    amount: float,
    min_hops: int = 4,
    max_hops: int = 7
) -> Optional[Route]:
    """
    Create a high-privacy stealth route with maximum obfuscation.
    
    Args:
        source_chain: Source blockchain
        source_asset: Source asset
        target_chain: Target blockchain
        target_asset: Target asset
        amount: Amount to transfer
        min_hops: Minimum hops (default 4)
        max_hops: Maximum hops (default 7)
    
    Returns:
        Obfuscated Route or None
    """
    config = RouteConfig(
        min_hops=min_hops,
        max_hops=max_hops,
        selection_strategy='privacy_maximized',
        allow_bridges=True,
        time_delay_range=(30, 300)  # 30s to 5min delays
    )
    
    obfuscator = RouteObfuscator(config)
    return obfuscator.obfuscate_route(
        source_chain, source_asset,
        target_chain, target_asset,
        amount
    )


def create_fast_route(
    source_chain: str,
    source_asset: str,
    target_chain: str,
    target_asset: str,
    amount: float
) -> Optional[Route]:
    """
    Create a fast route with minimal hops for speed over privacy.
    
    Args:
        source_chain: Source blockchain
        source_asset: Source asset
        target_chain: Target blockchain
        target_asset: Target asset
        amount: Amount to transfer
    
    Returns:
        Fast Route or None
    """
    config = RouteConfig(
        min_hops=1,
        max_hops=2,
        selection_strategy='cost_optimized',
        allow_bridges=True,
        time_delay_range=(0, 0)
    )
    
    obfuscator = RouteObfuscator(config)
    return obfuscator.obfuscate_route(
        source_chain, source_asset,
        target_chain, target_asset,
        amount
    )
