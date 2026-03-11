"""
Unit tests for the liquidity_analyzer module.

Tests cover:
- LiquidityConfig validation
- Pool depth analysis
- Slippage calculation
- Best venue routing
- Real-time monitoring
- Error handling
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from liquidity_analyzer import (
    LiquidityAnalyzer,
    LiquidityConfig,
    PoolDepth,
    SlippageEstimate,
    VenueRecommendation,
    LiquidityError,
    VenueNotSupportedError,
    InsufficientLiquidityError,
    create_analyzer,
    UniswapV3Adapter,
    CurveAdapter,
    SushiSwapAdapter,
)


class TestLiquidityConfig:
    """Test LiquidityConfig initialization and validation."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = LiquidityConfig()
        assert config.venues == ["uniswap_v3", "curve", "sushiswap"]
        assert config.min_depth_eth == 50.0
        assert config.max_slippage == 0.02
        assert config.update_interval == 30
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = LiquidityConfig(
            venues=["uniswap_v3", "curve"],
            min_depth_eth=100.0,
            max_slippage=0.01,
            update_interval=60
        )
        assert config.venues == ["uniswap_v3", "curve"]
        assert config.min_depth_eth == 100.0
        assert config.max_slippage == 0.01
        assert config.update_interval == 60
    
    def test_invalid_venue_raises_error(self):
        """Test that invalid venues raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            LiquidityConfig(venues=["invalid_venue", "uniswap_v3"])
        assert "invalid_venue" in str(exc_info.value)
    
    def test_valid_venues_accepted(self):
        """Test that all valid venues are accepted."""
        valid_venues = ["uniswap_v2", "uniswap_v3", "curve", "sushiswap"]
        config = LiquidityConfig(venues=valid_venues)
        assert set(config.venues) == set(valid_venues)


class TestLiquidityAnalyzerInit:
    """Test LiquidityAnalyzer initialization."""
    
    def test_init_with_default_config(self):
        """Test analyzer initialization with default config."""
        config = LiquidityConfig()
        analyzer = LiquidityAnalyzer(config)
        assert len(analyzer._adapters) == 3
        assert "uniswap_v3" in analyzer._adapters
        assert "curve" in analyzer._adapters
        assert "sushiswap" in analyzer._adapters
    
    def test_init_with_subset_of_venues(self):
        """Test analyzer with subset of venues."""
        config = LiquidityConfig(venues=["uniswap_v3", "curve"])
        analyzer = LiquidityAnalyzer(config)
        assert len(analyzer._adapters) == 2
        assert "sushiswap" not in analyzer._adapters
    
    def test_create_analyzer_helper(self):
        """Test the create_analyzer convenience function."""
        analyzer = create_analyzer(venues=["curve"], min_depth_eth=200.0)
        assert len(analyzer._adapters) == 1
        assert analyzer.config.min_depth_eth == 200.0


@pytest.mark.asyncio
class TestPoolDepthAnalysis:
    """Test pool depth analysis functionality."""
    
    async def test_analyze_pool_depth_specific_venue(self):
        """Test analyzing pool depth for a specific venue."""
        config = LiquidityConfig(venues=["uniswap_v3"])
        analyzer = LiquidityAnalyzer(config)
        
        depth = await analyzer.analyze_pool_depth("WETH", "USDC", venue="uniswap_v3")
        
        assert isinstance(depth, PoolDepth)
        assert depth.venue == "uniswap_v3"
        assert depth.token_in == "WETH"
        assert depth.token_out == "USDC"
        assert depth.total_liquidity_usd > 0
        assert depth.spot_price > 0
        assert depth.depth_at_1pct > 0
        assert depth.depth_at_5pct > 0
    
    async def test_analyze_pool_depth_best_venue(self):
        """Test analyzing pool depth without specifying venue."""
        config = LiquidityConfig(venues=["uniswap_v3", "curve", "sushiswap"])
        analyzer = LiquidityAnalyzer(config)
        
        depth = await analyzer.analyze_pool_depth("WETH", "USDC")
        
        assert isinstance(depth, PoolDepth)
        assert depth.venue in ["uniswap_v3", "curve", "sushiswap"]
        assert depth.total_liquidity_usd > 0
    
    async def test_analyze_unsupported_venue_raises_error(self):
        """Test that unsupported venue raises VenueNotSupportedError."""
        config = LiquidityConfig(venues=["uniswap_v3"])
        analyzer = LiquidityAnalyzer(config)
        
        with pytest.raises(VenueNotSupportedError):
            await analyzer.analyze_pool_depth("WETH", "USDC", venue="curve")
    
    async def test_insufficient_liquidity_raises_error(self):
        """Test that insufficient liquidity raises InsufficientLiquidityError."""
        config = LiquidityConfig(venues=["sushiswap"], min_depth_eth=10000)
        analyzer = LiquidityAnalyzer(config)
        
        with pytest.raises(InsufficientLiquidityError):
            await analyzer.analyze_pool_depth("WETH", "USDC")
    
    async def test_analyze_stable_pair_curve_best(self):
        """Test that Curve is best for stable pairs."""
        config = LiquidityConfig(venues=["uniswap_v3", "curve"])
        analyzer = LiquidityAnalyzer(config)
        
        depth = await analyzer.analyze_pool_depth("USDC", "USDT")
        
        # Curve typically has higher liquidity for stable pairs
        assert depth.total_liquidity_usd > 1000000


@pytest.mark.asyncio
class TestSlippageCalculation:
    """Test slippage calculation functionality."""
    
    async def test_calculate_slippage_specific_venue(self):
        """Test slippage calculation for specific venue."""
        config = LiquidityConfig(venues=["uniswap_v3"])
        analyzer = LiquidityAnalyzer(config)
        
        estimate = await analyzer.calculate_slippage("WETH", "USDC", 10.0, venue="uniswap_v3")
        
        assert isinstance(estimate, SlippageEstimate)
        assert estimate.venue == "uniswap_v3"
        assert estimate.token_in == "WETH"
        assert estimate.token_out == "USDC"
        assert estimate.amount_in == 10.0
        assert estimate.price_impact >= 0
        assert estimate.expected_out > 0
        assert estimate.minimum_out < estimate.expected_out
    
    async def test_calculate_slippage_finds_best(self):
        """Test that slippage calculation finds best venue."""
        config = LiquidityConfig(venues=["uniswap_v3", "curve", "sushiswap"])
        analyzer = LiquidityAnalyzer(config)
        
        estimate = await analyzer.calculate_slippage("WETH", "USDC", 50.0)
        
        assert isinstance(estimate, SlippageEstimate)
        assert estimate.price_impact >= 0
        assert estimate.price_impact <= 0.5  # Reasonable bounds
    
    async def test_slippage_increases_with_amount(self):
        """Test that slippage increases with trade size."""
        config = LiquidityConfig(venues=["uniswap_v3"])
        analyzer = LiquidityAnalyzer(config)
        
        small = await analyzer.calculate_slippage("WETH", "USDC", 1.0, venue="uniswap_v3")
        large = await analyzer.calculate_slippage("WETH", "USDC", 100.0, venue="uniswap_v3")
        
        assert large.price_impact > small.price_impact
    
    async def test_excessive_slippage_raises_error(self):
        """Test that excessive slippage raises InsufficientLiquidityError."""
        config = LiquidityConfig(venues=["sushiswap"], max_slippage=0.001)
        analyzer = LiquidityAnalyzer(config)
        
        with pytest.raises(InsufficientLiquidityError):
            await analyzer.calculate_slippage("WETH", "USDC", 1000.0)


@pytest.mark.asyncio
class TestBestVenueRouting:
    """Test best venue routing functionality."""
    
    async def test_find_best_venue_returns_recommendation(self):
        """Test that find_best_venue returns a valid recommendation."""
        config = LiquidityConfig(venues=["uniswap_v3", "curve", "sushiswap"])
        analyzer = LiquidityAnalyzer(config)
        
        recommendation = await analyzer.find_best_venue("WETH", "USDC", 50.0)
        
        assert isinstance(recommendation, VenueRecommendation)
        assert recommendation.venue in ["uniswap_v3", "curve", "sushiswap"]
        assert recommendation.liquidity_score >= 0
        assert recommendation.liquidity_score <= 100
        assert recommendation.reason in ["lowest_slippage", "highest_liquidity", "best_composite_score"]
        assert isinstance(recommendation.alternatives, list)
    
    async def test_stable_pair_prefers_curve(self):
        """Test that stable pairs prefer Curve."""
        config = LiquidityConfig(venues=["uniswap_v3", "curve"])
        analyzer = LiquidityAnalyzer(config)
        
        recommendation = await analyzer.find_best_venue("USDC", "USDT", 100000.0)
        
        # Curve should be preferred for stable pairs due to lower slippage
        assert recommendation.venue == "curve"
        assert recommendation.estimated_slippage < 0.01
    
    async def test_best_venue_includes_alternatives(self):
        """Test that recommendation includes alternative venues."""
        config = LiquidityConfig(venues=["uniswap_v3", "curve", "sushiswap"])
        analyzer = LiquidityAnalyzer(config)
        
        recommendation = await analyzer.find_best_venue("WETH", "USDC", 10.0)
        
        assert len(recommendation.alternatives) == 2
        assert recommendation.venue not in recommendation.alternatives


@pytest.mark.asyncio
class TestRealTimeMonitoring:
    """Test real-time liquidity monitoring."""
    
    async def test_start_monitoring_creates_task(self):
        """Test that start_monitoring creates a monitoring task."""
        config = LiquidityConfig(update_interval=1)
        analyzer = LiquidityAnalyzer(config)
        
        updates = []
        def callback(depth):
            updates.append(depth)
        
        analyzer.start_monitoring([("WETH", "USDC")], callback)
        
        # Wait for at least one update
        await asyncio.sleep(1.5)
        
        analyzer.stop_monitoring()
        
        assert len(updates) >= 1
        assert all(isinstance(u, PoolDepth) for u in updates)
    
    async def test_stop_monitoring_cancels_task(self):
        """Test that stop_monitoring cancels the monitoring task."""
        config = LiquidityConfig(update_interval=1)
        analyzer = LiquidityAnalyzer(config)
        
        analyzer.start_monitoring([("WETH", "USDC")])
        assert analyzer._monitoring_task is not None
        
        analyzer.stop_monitoring()
        assert analyzer._monitoring_task is None
    
    async def test_multiple_callbacks(self):
        """Test that multiple callbacks are all called."""
        config = LiquidityConfig(update_interval=1)
        analyzer = LiquidityAnalyzer(config)
        
        updates1 = []
        updates2 = []
        
        analyzer._monitoring_callbacks.append(lambda d: updates1.append(d))
        analyzer._monitoring_callbacks.append(lambda d: updates2.append(d))
        
        analyzer.start_monitoring([("WETH", "USDC")])
        await asyncio.sleep(1.5)
        analyzer.stop_monitoring()
        
        assert len(updates1) >= 1
        assert len(updates2) >= 1
    
    async def test_get_last_update(self):
        """Test retrieving last cached update."""
        config = LiquidityConfig()
        analyzer = LiquidityAnalyzer(config)
        
        # Initially no update
        assert analyzer.get_last_update("WETH", "USDC") is None
        
        # After analysis, should have update
        await analyzer.analyze_pool_depth("WETH", "USDC")
        last = analyzer.get_last_update("WETH", "USDC")
        
        assert last is not None
        assert isinstance(last, PoolDepth)


@pytest.mark.asyncio
class TestVenueAdapters:
    """Test individual venue adapters."""
    
    async def test_uniswap_v3_adapter(self):
        """Test Uniswap V3 adapter."""
        adapter = UniswapV3Adapter()
        assert adapter.name == "uniswap_v3"
        
        depth = await adapter.get_pool_depth("WETH", "USDC")
        assert depth.venue == "uniswap_v3"
        
        slippage = await adapter.estimate_slippage("WETH", "USDC", 10.0)
        assert slippage.venue == "uniswap_v3"
        
        score = await adapter.get_liquidity_score("WETH", "USDC")
        assert 0 <= score <= 100
    
    async def test_curve_adapter(self):
        """Test Curve adapter."""
        adapter = CurveAdapter()
        assert adapter.name == "curve"
        
        depth = await adapter.get_pool_depth("USDC", "USDT")
        assert depth.venue == "curve"
        
        # Curve has very low slippage for stable pairs
        slippage = await adapter.estimate_slippage("USDC", "USDT", 100000.0)
        assert slippage.price_impact < 0.005
    
    async def test_sushiswap_adapter(self):
        """Test SushiSwap adapter."""
        adapter = SushiSwapAdapter()
        assert adapter.name == "sushiswap"
        
        depth = await adapter.get_pool_depth("WETH", "USDC")
        assert depth.venue == "sushiswap"
    
    async def test_all_depths(self):
        """Test getting depths from all venues."""
        config = LiquidityConfig(venues=["uniswap_v3", "curve"])
        analyzer = LiquidityAnalyzer(config)
        
        depths = await analyzer.get_all_depths("WETH", "USDC")
        
        assert len(depths) == 2
        venues = [d.venue for d in depths]
        assert "uniswap_v3" in venues
        assert "curve" in venues


class TestPoolDepthDataClass:
    """Test PoolDepth dataclass functionality."""
    
    def test_to_dict(self):
        """Test PoolDepth serialization."""
        depth = PoolDepth(
            venue="uniswap_v3",
            token_in="WETH",
            token_out="USDC",
            total_liquidity_usd=10000000,
            depth_at_1pct=100000,
            depth_at_5pct=500000,
            spot_price=1850.0,
            timestamp=1234567890
        )
        
        d = depth.to_dict()
        assert d["venue"] == "uniswap_v3"
        assert d["token_in"] == "WETH"
        assert d["total_liquidity_usd"] == 10000000


class TestSlippageEstimateDataClass:
    """Test SlippageEstimate dataclass functionality."""
    
    def test_to_dict(self):
        """Test SlippageEstimate serialization."""
        estimate = SlippageEstimate(
            token_in="WETH",
            token_out="USDC",
            amount_in=10.0,
            expected_out=18500.0,
            price_impact=0.01,
            minimum_out=18307.5,
            venue="uniswap_v3",
            route=["WETH", "USDC"]
        )
        
        d = estimate.to_dict()
        assert d["venue"] == "uniswap_v3"
        assert d["price_impact"] == 0.01
        assert d["route"] == ["WETH", "USDC"]


class TestVenueRecommendationDataClass:
    """Test VenueRecommendation dataclass functionality."""
    
    def test_to_dict(self):
        """Test VenueRecommendation serialization."""
        rec = VenueRecommendation(
            venue="curve",
            reason="lowest_slippage",
            liquidity_score=95,
            estimated_slippage=0.001,
            alternatives=["uniswap_v3", "sushiswap"]
        )
        
        d = rec.to_dict()
        assert d["venue"] == "curve"
        assert d["liquidity_score"] == 95
        assert len(d["alternatives"]) == 2


class TestErrorHierarchy:
    """Test error class hierarchy."""
    
    def test_liquidity_error_base(self):
        """Test LiquidityError is base exception."""
        assert issubclass(VenueNotSupportedError, LiquidityError)
        assert issubclass(InsufficientLiquidityError, LiquidityError)
    
    def test_error_messages(self):
        """Test error messages are preserved."""
        err = VenueNotSupportedError("Test message")
        assert str(err) == "Test message"
        
        err2 = InsufficientLiquidityError("Not enough liquidity")
        assert str(err2) == "Not enough liquidity"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])