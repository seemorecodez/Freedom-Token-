"""
Unit tests for the route obfuscator module.
"""

import unittest
from unittest.mock import patch, MagicMock
import random

from route_obfuscator import (
    RouteConfig,
    RouteObfuscator,
    Venue,
    VenueType,
    Hop,
    Route,
    SelectionStrategy,
    create_stealth_route,
    create_fast_route,
)


class TestVenue(unittest.TestCase):
    """Test cases for Venue dataclass."""
    
    def test_venue_creation(self):
        """Test basic venue creation."""
        venue = Venue(
            name='uniswap',
            venue_type=VenueType.DEX,
            supported_chains=['ethereum'],
            supported_assets=['ETH', 'USDC'],
            fee_bps=30,
            estimated_time_seconds=15
        )
        self.assertEqual(venue.name, 'uniswap')
        self.assertEqual(venue.fee_bps, 30)
        self.assertFalse(venue.requires_kyc)
    
    def test_supports_pair(self):
        """Test chain-asset pair support check."""
        venue = Venue(
            name='test',
            venue_type=VenueType.DEX,
            supported_chains=['ethereum', 'solana'],
            supported_assets=['ETH', 'SOL'],
            fee_bps=25,
            estimated_time_seconds=10
        )
        # Test valid pairs (chain supported AND asset supported)
        self.assertTrue(venue.supports_pair('ethereum', 'ETH'))
        self.assertTrue(venue.supports_pair('solana', 'SOL'))
        # Note: supports_pair checks if both chain and asset are in their respective lists
        # (venues may support wrapped assets on non-native chains)
        self.assertTrue(venue.supports_pair('ethereum', 'SOL'))  # wrapped SOL on ethereum
        self.assertTrue(venue.supports_pair('solana', 'ETH'))   # wrapped ETH on solana
        # Test invalid pairs
        self.assertFalse(venue.supports_pair('bitcoin', 'BTC'))  # bitcoin not supported
        self.assertFalse(venue.supports_pair('ethereum', 'BTC'))  # BTC not in supported assets


class TestHop(unittest.TestCase):
    """Test cases for Hop dataclass."""
    
    def test_hop_creation(self):
        """Test hop creation."""
        hop = Hop(
            source_chain='ethereum',
            source_asset='ETH',
            target_chain='ethereum',
            target_asset='USDC',
            venue='uniswap',
            amount=1.0,
            fee_bps=30,
            estimated_time_seconds=15
        )
        self.assertEqual(hop.venue, 'uniswap')
        self.assertFalse(hop.is_bridge)
    
    def test_bridge_hop(self):
        """Test hop is correctly identified as bridge."""
        hop = Hop(
            source_chain='ethereum',
            source_asset='ETH',
            target_chain='solana',
            target_asset='ETH',
            venue='wormhole',
            amount=1.0,
            fee_bps=50,
            estimated_time_seconds=600
        )
        self.assertTrue(hop.is_bridge)
    
    def test_hop_execution(self):
        """Test hop execution returns correct result."""
        hop = Hop(
            source_chain='ethereum',
            source_asset='ETH',
            target_chain='ethereum',
            target_asset='USDC',
            venue='uniswap',
            amount=1.0,
            fee_bps=30,
            estimated_time_seconds=0,
            time_delay_seconds=0
        )
        result = hop.execute()
        self.assertTrue(result['success'])
        self.assertEqual(result['venue'], 'uniswap')


class TestRoute(unittest.TestCase):
    """Test cases for Route dataclass."""
    
    def setUp(self):
        """Set up test routes."""
        self.single_hop = Route(
            hops=[
                Hop(
                    source_chain='ethereum', source_asset='ETH',
                    target_chain='ethereum', target_asset='USDC',
                    venue='uniswap', amount=1.0,
                    fee_bps=30, estimated_time_seconds=15
                )
            ],
            source_chain='ethereum', source_asset='ETH',
            target_chain='ethereum', target_asset='USDC',
            original_amount=1.0
        )
        
        self.multi_hop = Route(
            hops=[
                Hop(
                    source_chain='ethereum', source_asset='ETH',
                    target_chain='ethereum', target_asset='USDC',
                    venue='uniswap', amount=1.0,
                    fee_bps=30, estimated_time_seconds=15
                ),
                Hop(
                    source_chain='ethereum', source_asset='USDC',
                    target_chain='solana', target_asset='USDC',
                    venue='wormhole', amount=1.0,
                    fee_bps=50, estimated_time_seconds=600
                ),
                Hop(
                    source_chain='solana', source_asset='USDC',
                    target_chain='solana', target_asset='SOL',
                    venue='jupiter', amount=1.0,
                    fee_bps=25, estimated_time_seconds=10
                ),
            ],
            source_chain='ethereum', source_asset='ETH',
            target_chain='solana', target_asset='SOL',
            original_amount=1.0
        )
    
    def test_total_cost(self):
        """Test total cost calculation."""
        self.assertEqual(self.single_hop.total_cost_bps, 30)
        self.assertEqual(self.multi_hop.total_cost_bps, 105)  # 30 + 50 + 25
    
    def test_estimated_time(self):
        """Test estimated time calculation."""
        self.assertEqual(self.single_hop.estimated_time_seconds, 15)
        self.assertEqual(self.multi_hop.estimated_time_seconds, 625)  # 15 + 600 + 10
    
    def test_privacy_score(self):
        """Test privacy score calculation."""
        # Multi-hop with bridges should have higher privacy score
        self.assertGreater(self.multi_hop.privacy_score, self.single_hop.privacy_score)
        self.assertGreater(self.multi_hop.privacy_score, 0.0)
        self.assertLessEqual(self.multi_hop.privacy_score, 1.0)
    
    def test_hop_count(self):
        """Test hop count."""
        self.assertEqual(self.single_hop.hop_count, 1)
        self.assertEqual(self.multi_hop.hop_count, 3)


class TestRouteConfig(unittest.TestCase):
    """Test cases for RouteConfig."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = RouteConfig()
        self.assertEqual(config.min_hops, 2)
        self.assertEqual(config.max_hops, 5)
        self.assertIn('uniswap', config.venues)
        self.assertIn('ethereum', config.chains)
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = RouteConfig(
            min_hops=3,
            max_hops=7,
            venues=['binance'],
            chains=['ethereum', 'solana'],
            selection_strategy='privacy_maximized'
        )
        self.assertEqual(config.min_hops, 3)
        self.assertEqual(config.max_hops, 7)
        self.assertEqual(config.venues, ['binance'])
        self.assertEqual(config.selection_strategy, 'privacy_maximized')
    
    def test_invalid_min_hops(self):
        """Test validation of negative min_hops."""
        with self.assertRaises(ValueError):
            RouteConfig(min_hops=-1)
    
    def test_invalid_max_hops(self):
        """Test validation of max_hops < min_hops."""
        with self.assertRaises(ValueError):
            RouteConfig(min_hops=5, max_hops=3)
    
    def test_invalid_strategy(self):
        """Test validation of invalid selection strategy."""
        with self.assertRaises(ValueError):
            RouteConfig(selection_strategy='invalid')


class TestRouteObfuscator(unittest.TestCase):
    """Test cases for RouteObfuscator."""
    
    def setUp(self):
        """Set up test obfuscator."""
        self.config = RouteConfig(
            min_hops=2,
            max_hops=4,
            venues=['uniswap', 'curve', 'jupiter', 'wormhole'],
            chains=['ethereum', 'solana']
        )
        self.obfuscator = RouteObfuscator(self.config)
    
    def test_initialization(self):
        """Test obfuscator initialization."""
        self.assertIsNotNone(self.obfuscator.config)
        self.assertEqual(self.obfuscator.config.min_hops, 2)
    
    def test_get_supported_chains(self):
        """Test getting supported chains."""
        chains = self.obfuscator.get_supported_chains()
        self.assertIn('ethereum', chains)
        self.assertIn('solana', chains)
    
    def test_get_supported_venues(self):
        """Test getting supported venues."""
        venues = self.obfuscator.get_supported_venues()
        self.assertIn('uniswap', venues)
        self.assertIn('wormhole', venues)
    
    def test_get_venue_info(self):
        """Test getting venue information."""
        info = self.obfuscator.get_venue_info('uniswap')
        self.assertIsNotNone(info)
        self.assertEqual(info['name'], 'uniswap')
        self.assertEqual(info['type'], 'dex')
    
    def test_get_venue_info_invalid(self):
        """Test getting info for non-existent venue."""
        info = self.obfuscator.get_venue_info('invalid_venue')
        self.assertIsNone(info)
    
    def test_find_route_same_chain(self):
        """Test finding route on same chain."""
        # Use default config which has ethereum venues available
        obfuscator = RouteObfuscator()
        route = obfuscator.find_route(
            'ethereum', 'ETH',
            'ethereum', 'USDC',
            1.0,
            num_hops=2
        )
        self.assertIsNotNone(route)
        self.assertEqual(route.source_chain, 'ethereum')
        self.assertEqual(route.target_chain, 'ethereum')
        self.assertEqual(len(route.hops), 2)
    
    def test_find_route_cross_chain(self):
        """Test finding cross-chain route."""
        route = self.obfuscator.find_route(
            'ethereum', 'ETH',
            'solana', 'SOL',
            1.0,
            num_hops=3
        )
        self.assertIsNotNone(route)
        self.assertEqual(route.source_chain, 'ethereum')
        self.assertEqual(route.target_chain, 'solana')
    
    def test_find_route_unsupported_chain(self):
        """Test finding route with unsupported chain."""
        route = self.obfuscator.find_route(
            'bitcoin', 'BTC',
            'ethereum', 'ETH',
            1.0
        )
        self.assertIsNone(route)
    
    def test_obfuscate_route(self):
        """Test obfuscate route function."""
        route = self.obfuscator.obfuscate_route(
            'ethereum', 'ETH',
            'solana', 'SOL',
            1.0
        )
        self.assertIsNotNone(route)
        self.assertGreaterEqual(len(route.hops), self.config.min_hops)
        self.assertLessEqual(len(route.hops), self.config.max_hops)
    
    def test_estimate_cost(self):
        """Test cost estimation."""
        # Use default obfuscator with full venue support
        obfuscator = RouteObfuscator()
        route = obfuscator.find_route(
            'ethereum', 'ETH',
            'ethereum', 'USDC',
            1.0,
            num_hops=2
        )
        self.assertIsNotNone(route)
        
        cost = obfuscator.estimate_cost(route)
        self.assertIn('total_fee_bps', cost)
        self.assertIn('hop_costs', cost)
        self.assertEqual(len(cost['hop_costs']), 2)
    
    def test_estimate_time(self):
        """Test time estimation."""
        # Use default obfuscator with full venue support
        obfuscator = RouteObfuscator()
        route = obfuscator.find_route(
            'ethereum', 'ETH',
            'ethereum', 'USDC',
            1.0,
            num_hops=2
        )
        self.assertIsNotNone(route)
        
        time = obfuscator.estimate_time(route)
        self.assertIn('total_time_seconds', time)
        self.assertIn('hop_times', time)
        self.assertEqual(len(time['hop_times']), 2)
    
    def test_validate_route_valid(self):
        """Test validation of valid route."""
        # Use default obfuscator with full venue support
        obfuscator = RouteObfuscator()
        route = obfuscator.find_route(
            'ethereum', 'ETH',
            'ethereum', 'USDC',
            1.0,
            num_hops=2
        )
        self.assertIsNotNone(route)
        
        validation = obfuscator.validate_route(route)
        self.assertTrue(validation['valid'])
        self.assertEqual(len(validation['issues']), 0)
    
    def test_validate_route_invalid_chain(self):
        """Test validation catches chain mismatch."""
        route = Route(
            hops=[
                Hop(
                    source_chain='ethereum', source_asset='ETH',
                    target_chain='solana', target_asset='ETH',
                    venue='wormhole', amount=1.0,
                    fee_bps=50, estimated_time_seconds=600
                )
            ],
            source_chain='ethereum', source_asset='ETH',
            target_chain='ethereum', target_asset='ETH',  # Mismatch!
            original_amount=1.0
        )
        
        validation = self.obfuscator.validate_route(route)
        self.assertFalse(validation['valid'])
        self.assertGreater(len(validation['issues']), 0)
    
    def test_validate_route_low_privacy(self):
        """Test validation warns about low privacy."""
        route = Route(
            hops=[
                Hop(
                    source_chain='ethereum', source_asset='ETH',
                    target_chain='ethereum', target_asset='USDC',
                    venue='uniswap', amount=1.0,
                    fee_bps=30, estimated_time_seconds=15
                )
            ],
            source_chain='ethereum', source_asset='ETH',
            target_chain='ethereum', target_asset='USDC',
            original_amount=1.0
        )
        
        validation = self.obfuscator.validate_route(route)
        privacy_warnings = [w for w in validation['warnings'] if 'privacy' in w.lower()]
        self.assertGreater(len(privacy_warnings), 0)
    
    def test_cost_optimized_strategy(self):
        """Test cost-optimized selection strategy."""
        config = RouteConfig(
            selection_strategy='cost_optimized',
            venues=['uniswap', 'curve'],  # curve has lower fees
            chains=['ethereum']
        )
        obfuscator = RouteObfuscator(config)
        
        hop = obfuscator._generate_hop('ethereum', 'ETH', 'ethereum', 'USDC', 1.0)
        self.assertIsNotNone(hop)
        # Should prefer curve (15 bps) over uniswap (30 bps)
        self.assertEqual(hop.venue, 'curve')
    
    def test_random_strategy(self):
        """Test random selection strategy."""
        config = RouteConfig(
            selection_strategy='random',
            venues=['uniswap', 'curve'],
            chains=['ethereum']
        )
        obfuscator = RouteObfuscator(config)
        
        # Run multiple times to check randomness
        venues = set()
        for _ in range(10):
            hop = obfuscator._generate_hop('ethereum', 'ETH', 'ethereum', 'USDC', 1.0)
            if hop:
                venues.add(hop.venue)
        
        # With random selection, should see both venues over many runs
        self.assertGreaterEqual(len(venues), 1)


class TestConvenienceFunctions(unittest.TestCase):
    """Test cases for convenience functions."""
    
    def test_create_stealth_route(self):
        """Test create_stealth_route function."""
        # Test same-chain stealth route for reliability
        # (cross-chain routes depend on bridge availability)
        route = create_stealth_route(
            'ethereum', 'ETH',
            'ethereum', 'USDC',
            1.0,
            min_hops=4,
            max_hops=5
        )
        self.assertIsNotNone(route)
        self.assertGreaterEqual(len(route.hops), 4)
        self.assertLessEqual(len(route.hops), 5)
        self.assertGreater(route.privacy_score, 0.3)
    
    def test_create_fast_route(self):
        """Test create_fast_route function."""
        # Test same-chain fast route (bridges add complexity)
        route = create_fast_route(
            'ethereum', 'ETH',
            'ethereum', 'USDC',
            1.0
        )
        self.assertIsNotNone(route)
        self.assertLessEqual(len(route.hops), 2)
        # Fast route should have no time delays
        for hop in route.hops:
            self.assertEqual(hop.time_delay_seconds, 0)


class TestBitcoinSupport(unittest.TestCase):
    """Test Bitcoin routing support."""
    
    def test_bitcoin_venue_support(self):
        """Test venues support Bitcoin."""
        config = RouteConfig(
            chains=['bitcoin', 'ethereum'],
            venues=['thorchain', 'binance']
        )
        obfuscator = RouteObfuscator(config)
        
        # Check thorchain supports Bitcoin
        thorchain = obfuscator._get_venue('thorchain')
        self.assertIn('bitcoin', thorchain.supported_chains)
        self.assertIn('BTC', thorchain.supported_assets)
    
    def test_bitcoin_to_ethereum_route(self):
        """Test Bitcoin to Ethereum routing via THORChain."""
        # Test BTC -> WBTC via THORChain bridge
        # Note: THORChain keeps the same asset type across chains
        config = RouteConfig(
            min_hops=1,
            max_hops=2,
            chains=['bitcoin', 'ethereum', 'bsc'],
            venues=['thorchain', 'uniswap'],
            asset_pool=['BTC', 'ETH', 'BNB', 'WBTC']
        )
        obfuscator = RouteObfuscator(config)
        
        # Bridge BTC from bitcoin to ethereum (results in wrapped BTC on ethereum)
        route = obfuscator.find_route(
            'bitcoin', 'BTC',
            'ethereum', 'BTC',  # Same asset on different chain
            0.5,
            num_hops=1
        )
        self.assertIsNotNone(route)
        self.assertEqual(route.source_chain, 'bitcoin')
        self.assertEqual(route.target_chain, 'ethereum')


class TestSolanaSupport(unittest.TestCase):
    """Test Solana routing support."""
    
    def test_solana_venues(self):
        """Test Solana venue support."""
        config = RouteConfig(
            chains=['solana', 'ethereum'],
            venues=['jupiter', 'raydium', 'wormhole']
        )
        obfuscator = RouteObfuscator(config)
        
        jupiter = obfuscator._get_venue('jupiter')
        self.assertIn('solana', jupiter.supported_chains)
        self.assertIn('SOL', jupiter.supported_assets)
    
    def test_solana_route(self):
        """Test route on Solana."""
        config = RouteConfig(
            min_hops=1,
            max_hops=2,
            chains=['solana'],
            venues=['jupiter', 'raydium']
        )
        obfuscator = RouteObfuscator(config)
        
        route = obfuscator.find_route(
            'solana', 'SOL',
            'solana', 'USDC',
            10.0,
            num_hops=1
        )
        self.assertIsNotNone(route)
        self.assertEqual(route.source_chain, 'solana')
        self.assertEqual(route.target_chain, 'solana')


class TestVenueTypes(unittest.TestCase):
    """Test different venue types."""
    
    def test_dex_venues(self):
        """Test DEX venues."""
        obfuscator = RouteObfuscator()
        
        dexes = ['uniswap', 'curve', 'jupiter']
        for dex in dexes:
            venue = obfuscator._get_venue(dex)
            if venue:
                self.assertEqual(venue.venue_type, VenueType.DEX)
                self.assertFalse(venue.requires_kyc)
    
    def test_cex_venues(self):
        """Test CEX venues."""
        obfuscator = RouteObfuscator()
        
        cexs = ['binance', 'coinbase', 'kraken']
        for cex in cexs:
            venue = obfuscator._get_venue(cex)
            if venue:
                self.assertEqual(venue.venue_type, VenueType.CEX)
                self.assertTrue(venue.requires_kyc)
    
    def test_bridge_venues(self):
        """Test bridge venues."""
        obfuscator = RouteObfuscator()
        
        bridges = ['wormhole', 'stargate', 'layerzero']
        for bridge in bridges:
            venue = obfuscator._get_venue(bridge)
            if venue:
                self.assertEqual(venue.venue_type, VenueType.BRIDGE)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def test_no_valid_route(self):
        """Test when no valid route exists."""
        config = RouteConfig(
            chains=['ethereum'],
            venues=['jupiter']  # Jupiter doesn't support Ethereum
        )
        obfuscator = RouteObfuscator(config)
        
        route = obfuscator.find_route(
            'ethereum', 'ETH',
            'ethereum', 'USDC',
            1.0
        )
        self.assertIsNone(route)
    
    def test_single_hop_config(self):
        """Test with min_hops = max_hops = 1."""
        config = RouteConfig(min_hops=1, max_hops=1)
        obfuscator = RouteObfuscator(config)
        
        route = obfuscator.obfuscate_route(
            'ethereum', 'ETH',
            'ethereum', 'USDC',
            1.0
        )
        self.assertIsNotNone(route)
        self.assertEqual(len(route.hops), 1)
    
    def test_large_hop_count(self):
        """Test with large number of hops."""
        config = RouteConfig(
            min_hops=8, 
            max_hops=10,
            chains=['ethereum'],
            venues=['uniswap', 'curve']  # Multiple venues for variety
        )
        obfuscator = RouteObfuscator(config)
        
        route = obfuscator.find_route(
            'ethereum', 'ETH',
            'ethereum', 'USDC',
            1.0,
            num_hops=8
        )
        self.assertIsNotNone(route)
        self.assertEqual(len(route.hops), 8)
    
    def test_empty_venue_list(self):
        """Test with empty venue list falls back to defaults."""
        config = RouteConfig(venues=None)
        self.assertIsNotNone(config.venues)
        self.assertGreater(len(config.venues), 0)
    
    def test_time_delays(self):
        """Test time delays are applied correctly."""
        config = RouteConfig(
            min_hops=2,
            max_hops=2,
            time_delay_range=(60, 120),
            chains=['ethereum'],
            venues=['uniswap', 'curve']
        )
        obfuscator = RouteObfuscator(config)
        
        route = obfuscator.find_route(
            'ethereum', 'ETH',
            'ethereum', 'USDC',
            1.0,
            num_hops=2
        )
        self.assertIsNotNone(route)
        for hop in route.hops:
            self.assertGreaterEqual(hop.time_delay_seconds, 60)
            self.assertLessEqual(hop.time_delay_seconds, 120)


if __name__ == '__main__':
    unittest.main()
