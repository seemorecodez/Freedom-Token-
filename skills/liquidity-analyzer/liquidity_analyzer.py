"""
Liquidity Analyzer - Pool depth and slippage analysis for DeFi trading.

Supports Uniswap V2/V3, Curve, and SushiSwap for optimal trade routing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("liquidity_analyzer")


class LiquidityError(Exception):
    """Raised when liquidity analysis fails."""
    pass


class VenueNotSupportedError(LiquidityError):
    """Raised when an unsupported venue is requested."""
    pass


class InsufficientLiquidityError(LiquidityError):
    """Raised when liquidity is below threshold."""
    pass


@dataclass
class LiquidityConfig:
    """Configuration for liquidity analysis.
    
    Args:
        venues: List of DEX venues to analyze (uniswap_v2, uniswap_v3, curve, sushiswap)
        min_depth_eth: Minimum liquidity threshold in ETH equivalent
        max_slippage: Maximum acceptable slippage as decimal (0.02 = 2%)
        update_interval: Seconds between liquidity updates when monitoring
    """
    venues: List[str] = field(default_factory=lambda: ["uniswap_v3", "curve", "sushiswap"])
    min_depth_eth: float = 50.0
    max_slippage: float = 0.02
    update_interval: int = 30

    def __post_init__(self):
        valid_venues = {"uniswap_v2", "uniswap_v3", "curve", "sushiswap"}
        invalid = set(self.venues) - valid_venues
        if invalid:
            raise ValueError(f"Unsupported venues: {invalid}. Valid: {valid_venues}")


@dataclass
class PoolDepth:
    """Pool depth analysis result."""
    venue: str
    token_in: str
    token_out: str
    total_liquidity_usd: float
    depth_at_1pct: float  # Liquidity within 1% of spot price
    depth_at_5pct: float  # Liquidity within 5% of spot price
    spot_price: float
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "venue": self.venue,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "total_liquidity_usd": self.total_liquidity_usd,
            "depth_at_1pct": self.depth_at_1pct,
            "depth_at_5pct": self.depth_at_5pct,
            "spot_price": self.spot_price,
            "timestamp": self.timestamp
        }


@dataclass  
class SlippageEstimate:
    """Slippage estimation result."""
    token_in: str
    token_out: str
    amount_in: float
    expected_out: float
    price_impact: float
    minimum_out: float
    venue: str
    route: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_in": self.token_in,
            "token_out": self.token_out,
            "amount_in": self.amount_in,
            "expected_out": self.expected_out,
            "price_impact": self.price_impact,
            "minimum_out": self.minimum_out,
            "venue": self.venue,
            "route": self.route
        }


@dataclass
class VenueRecommendation:
    """Best venue recommendation result."""
    venue: str
    reason: str
    liquidity_score: int  # 0-100
    estimated_slippage: float
    alternatives: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "venue": self.venue,
            "reason": self.reason,
            "liquidity_score": self.liquidity_score,
            "estimated_slippage": self.estimated_slippage,
            "alternatives": self.alternatives
        }


class DEXAdapter(ABC):
    """Abstract base class for DEX adapters."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    async def get_pool_depth(
        self, 
        token_in: str, 
        token_out: str
    ) -> PoolDepth:
        """Get pool depth for token pair."""
        pass
    
    @abstractmethod
    async def estimate_slippage(
        self,
        token_in: str,
        token_out: str,
        amount_in: float
    ) -> SlippageEstimate:
        """Estimate slippage for a trade."""
        pass
    
    @abstractmethod
    async def get_liquidity_score(
        self,
        token_in: str,
        token_out: str
    ) -> int:
        """Get liquidity score 0-100."""
        pass


class UniswapV3Adapter(DEXAdapter):
    """Uniswap V3 adapter using concentrated liquidity model."""
    
    @property
    def name(self) -> str:
        return "uniswap_v3"
    
    async def get_pool_depth(
        self, 
        token_in: str, 
        token_out: str
    ) -> PoolDepth:
        """Simulate fetching Uniswap V3 pool depth with tick-based liquidity."""
        # Simulated data - in production, would fetch from subgraph/RPC
        import time
        
        # Mock liquidity distribution for concentrated positions
        base_liquidity = self._get_mock_liquidity(token_in, token_out)
        
        return PoolDepth(
            venue=self.name,
            token_in=token_in,
            token_out=token_out,
            total_liquidity_usd=base_liquidity["total"],
            depth_at_1pct=base_liquidity["depth_1pct"],
            depth_at_5pct=base_liquidity["depth_5pct"],
            spot_price=base_liquidity["price"],
            timestamp=time.time()
        )
    
    async def estimate_slippage(
        self,
        token_in: str,
        token_out: str,
        amount_in: float
    ) -> SlippageEstimate:
        """Estimate slippage using concentrated liquidity math."""
        depth = await self.get_pool_depth(token_in, token_out)
        
        # Calculate price impact based on liquidity depth
        # Using simplified formula: impact = amount / depth
        price_impact = min(amount_in * depth.spot_price / depth.depth_at_1pct * 0.01, 0.5)
        
        expected_out = amount_in * depth.spot_price * (1 - price_impact)
        minimum_out = expected_out * (1 - 0.005)  # 0.5% buffer
        
        return SlippageEstimate(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            expected_out=expected_out,
            price_impact=price_impact,
            minimum_out=minimum_out,
            venue=self.name
        )
    
    async def get_liquidity_score(
        self,
        token_in: str,
        token_out: str
    ) -> int:
        """Calculate liquidity score 0-100."""
        depth = await self.get_pool_depth(token_in, token_out)
        # Score based on total liquidity depth
        score = min(int(depth.total_liquidity_usd / 100000), 100)
        return max(score, 10)  # Minimum 10 for any existing pool
    
    def _get_mock_liquidity(self, token_in: str, token_out: str) -> Dict[str, float]:
        """Generate mock liquidity data based on token pair."""
        # Simulate different liquidity for different pairs
        pair_key = tuple(sorted([token_in, token_out]))
        
        # High liquidity pairs
        if pair_key in [("USDC", "WETH"), ("USDT", "WETH"), ("USDC", "USDT")]:
            return {
                "total": 25000000,
                "depth_1pct": 500000,
                "depth_5pct": 2500000,
                "price": 1850.0 if "WETH" in pair_key else 1.0
            }
        # Medium liquidity
        elif pair_key in [("WBTC", "WETH"), ("DAI", "WETH")]:
            return {
                "total": 12000000,
                "depth_1pct": 200000,
                "depth_5pct": 1000000,
                "price": 18.5 if "WBTC" in pair_key else 1850.0
            }
        # Lower liquidity (altcoins)
        else:
            return {
                "total": 2000000,
                "depth_1pct": 30000,
                "depth_5pct": 150000,
                "price": 100.0
            }


class CurveAdapter(DEXAdapter):
    """Curve adapter optimized for stable pairs."""
    
    @property
    def name(self) -> str:
        return "curve"
    
    async def get_pool_depth(
        self, 
        token_in: str, 
        token_out: str
    ) -> PoolDepth:
        """Simulate fetching Curve pool depth."""
        import time
        
        liquidity = self._get_mock_liquidity(token_in, token_out)
        
        return PoolDepth(
            venue=self.name,
            token_in=token_in,
            token_out=token_out,
            total_liquidity_usd=liquidity["total"],
            depth_at_1pct=liquidity["depth_1pct"],
            depth_at_5pct=liquidity["depth_5pct"],
            spot_price=liquidity["price"],
            timestamp=time.time()
        )
    
    async def estimate_slippage(
        self,
        token_in: str,
        token_out: str,
        amount_in: float
    ) -> SlippageEstimate:
        """Estimate slippage using Curve's stableswap math."""
        depth = await self.get_pool_depth(token_in, token_out)
        
        # Curve has lower slippage for stable pairs
        is_stable = abs(depth.spot_price - 1.0) < 0.01
        slippage_factor = 0.0005 if is_stable else 0.002
        
        price_impact = min(amount_in * depth.spot_price / depth.depth_at_1pct * slippage_factor, 0.3)
        expected_out = amount_in * depth.spot_price * (1 - price_impact)
        minimum_out = expected_out * (1 - 0.003)
        
        return SlippageEstimate(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            expected_out=expected_out,
            price_impact=price_impact,
            minimum_out=minimum_out,
            venue=self.name
        )
    
    async def get_liquidity_score(
        self,
        token_in: str,
        token_out: str
    ) -> int:
        """Calculate liquidity score 0-100."""
        depth = await self.get_pool_depth(token_in, token_out)
        score = min(int(depth.total_liquidity_usd / 80000), 100)
        return max(score, 5)
    
    def _get_mock_liquidity(self, token_in: str, token_out: str) -> Dict[str, float]:
        """Generate mock Curve liquidity data."""
        pair_key = tuple(sorted([token_in, token_out]))
        
        # Curve excels at stable pairs
        if pair_key in [("USDC", "USDT"), ("DAI", "USDC"), ("DAI", "USDT")]:
            return {
                "total": 45000000,
                "depth_1pct": 2000000,
                "depth_5pct": 10000000,
                "price": 1.0
            }
        elif pair_key in [("USDC", "WETH"), ("USDT", "WETH")]:
            return {
                "total": 15000000,
                "depth_1pct": 400000,
                "depth_5pct": 2000000,
                "price": 1850.0
            }
        else:
            return {
                "total": 5000000,
                "depth_1pct": 80000,
                "depth_5pct": 400000,
                "price": 1.0 if "USD" in token_in or "USD" in token_out else 100.0
            }


class SushiSwapAdapter(DEXAdapter):
    """SushiSwap adapter using standard AMM model."""
    
    @property
    def name(self) -> str:
        return "sushiswap"
    
    async def get_pool_depth(
        self, 
        token_in: str, 
        token_out: str
    ) -> PoolDepth:
        """Simulate fetching SushiSwap pool depth."""
        import time
        
        liquidity = self._get_mock_liquidity(token_in, token_out)
        
        return PoolDepth(
            venue=self.name,
            token_in=token_in,
            token_out=token_out,
            total_liquidity_usd=liquidity["total"],
            depth_at_1pct=liquidity["depth_1pct"],
            depth_at_5pct=liquidity["depth_5pct"],
            spot_price=liquidity["price"],
            timestamp=time.time()
        )
    
    async def estimate_slippage(
        self,
        token_in: str,
        token_out: str,
        amount_in: float
    ) -> SlippageEstimate:
        """Estimate slippage using constant product formula."""
        depth = await self.get_pool_depth(token_in, token_out)
        
        # Standard AMM slippage calculation
        # x * y = k model
        price_impact = min(amount_in * depth.spot_price / depth.depth_at_1pct * 0.015, 0.4)
        expected_out = amount_in * depth.spot_price * (1 - price_impact)
        minimum_out = expected_out * (1 - 0.005)
        
        return SlippageEstimate(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            expected_out=expected_out,
            price_impact=price_impact,
            minimum_out=minimum_out,
            venue=self.name
        )
    
    async def get_liquidity_score(
        self,
        token_in: str,
        token_out: str
    ) -> int:
        """Calculate liquidity score 0-100."""
        depth = await self.get_pool_depth(token_in, token_out)
        score = min(int(depth.total_liquidity_usd / 120000), 100)
        return max(score, 5)
    
    def _get_mock_liquidity(self, token_in: str, token_out: str) -> Dict[str, float]:
        """Generate mock SushiSwap liquidity data."""
        pair_key = tuple(sorted([token_in, token_out]))
        
        if pair_key in [("USDC", "WETH"), ("USDT", "WETH")]:
            return {
                "total": 8000000,
                "depth_1pct": 120000,
                "depth_5pct": 600000,
                "price": 1850.0
            }
        elif pair_key in [("WBTC", "WETH")]:
            return {
                "total": 5000000,
                "depth_1pct": 80000,
                "depth_5pct": 400000,
                "price": 18.5
            }
        else:
            return {
                "total": 1500000,
                "depth_1pct": 20000,
                "depth_5pct": 100000,
                "price": 50.0
            }


class UniswapV2Adapter(DEXAdapter):
    """Uniswap V2 adapter using constant product AMM."""
    
    @property
    def name(self) -> str:
        return "uniswap_v2"
    
    async def get_pool_depth(
        self, 
        token_in: str, 
        token_out: str
    ) -> PoolDepth:
        """Simulate fetching Uniswap V2 pool depth."""
        import time
        
        liquidity = self._get_mock_liquidity(token_in, token_out)
        
        return PoolDepth(
            venue=self.name,
            token_in=token_in,
            token_out=token_out,
            total_liquidity_usd=liquidity["total"],
            depth_at_1pct=liquidity["depth_1pct"],
            depth_at_5pct=liquidity["depth_5pct"],
            spot_price=liquidity["price"],
            timestamp=time.time()
        )
    
    async def estimate_slippage(
        self,
        token_in: str,
        token_out: str,
        amount_in: float
    ) -> SlippageEstimate:
        """Estimate slippage using x*y=k formula."""
        depth = await self.get_pool_depth(token_in, token_out)
        
        price_impact = min(amount_in * depth.spot_price / depth.depth_at_1pct * 0.012, 0.35)
        expected_out = amount_in * depth.spot_price * (1 - price_impact)
        minimum_out = expected_out * (1 - 0.005)
        
        return SlippageEstimate(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            expected_out=expected_out,
            price_impact=price_impact,
            minimum_out=minimum_out,
            venue=self.name
        )
    
    async def get_liquidity_score(
        self,
        token_in: str,
        token_out: str
    ) -> int:
        """Calculate liquidity score 0-100."""
        depth = await self.get_pool_depth(token_in, token_out)
        score = min(int(depth.total_liquidity_usd / 150000), 100)
        return max(score, 5)
    
    def _get_mock_liquidity(self, token_in: str, token_out: str) -> Dict[str, float]:
        """Generate mock Uniswap V2 liquidity data."""
        pair_key = tuple(sorted([token_in, token_out]))
        
        if pair_key in [("USDC", "WETH"), ("USDT", "WETH")]:
            return {
                "total": 10000000,
                "depth_1pct": 150000,
                "depth_5pct": 750000,
                "price": 1850.0
            }
        else:
            return {
                "total": 3000000,
                "depth_1pct": 45000,
                "depth_5pct": 225000,
                "price": 100.0
            }


class LiquidityAnalyzer:
    """Main liquidity analyzer for pool depth and slippage analysis.
    
    Supports real-time monitoring and multi-venue analysis.
    
    Example:
        >>> config = LiquidityConfig(venues=["uniswap_v3", "curve"])
        >>> analyzer = LiquidityAnalyzer(config)
        >>> depth = await analyzer.analyze_pool_depth("WETH", "USDC")
        >>> slippage = await analyzer.calculate_slippage("WETH", "USDC", 50)
    """
    
    def __init__(self, config: LiquidityConfig):
        self.config = config
        self._adapters: Dict[str, DEXAdapter] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_callbacks: List[Callable[[PoolDepth], None]] = []
        self._last_updates: Dict[str, PoolDepth] = {}
        
        # Initialize adapters based on config
        self._init_adapters()
    
    def _init_adapters(self):
        """Initialize DEX adapters."""
        adapter_map = {
            "uniswap_v2": UniswapV2Adapter,
            "uniswap_v3": UniswapV3Adapter,
            "curve": CurveAdapter,
            "sushiswap": SushiSwapAdapter
        }
        
        for venue in self.config.venues:
            if venue in adapter_map:
                self._adapters[venue] = adapter_map[venue]()
                logger.info(f"Initialized {venue} adapter")
    
    async def analyze_pool_depth(
        self, 
        token_in: str, 
        token_out: str,
        venue: Optional[str] = None
    ) -> PoolDepth:
        """Analyze pool depth for a token pair.
        
        Args:
            token_in: Input token symbol
            token_out: Output token symbol
            venue: Specific venue to analyze (None for best venue)
            
        Returns:
            PoolDepth object with liquidity analysis
            
        Raises:
            LiquidityError: If liquidity analysis fails
            InsufficientLiquidityError: If liquidity below threshold
        """
        if venue:
            if venue not in self._adapters:
                raise VenueNotSupportedError(f"Venue '{venue}' not configured")
            adapter = self._adapters[venue]
            depth = await adapter.get_pool_depth(token_in, token_out)
        else:
            # Get depth from all venues and return best
            depths = await asyncio.gather(*[
                adapter.get_pool_depth(token_in, token_out)
                for adapter in self._adapters.values()
            ])
            depth = max(depths, key=lambda d: d.total_liquidity_usd)
        
        # Check minimum depth requirement
        min_depth_usd = self.config.min_depth_eth * 1850  # Approx ETH price
        if depth.total_liquidity_usd < min_depth_usd:
            raise InsufficientLiquidityError(
                f"Liquidity {depth.total_liquidity_usd:.0f} USD below threshold {min_depth_usd:.0f} USD"
            )
        
        self._last_updates[f"{token_in}/{token_out}"] = depth
        return depth
    
    async def calculate_slippage(
        self,
        token_in: str,
        token_out: str,
        amount_in: float,
        venue: Optional[str] = None
    ) -> SlippageEstimate:
        """Calculate slippage for a trade.
        
        Args:
            token_in: Input token symbol
            token_out: Output token symbol  
            amount_in: Amount to trade
            venue: Specific venue (None for best)
            
        Returns:
            SlippageEstimate with price impact details
            
        Raises:
            LiquidityError: If slippage calculation fails
        """
        if venue:
            if venue not in self._adapters:
                raise VenueNotSupportedError(f"Venue '{venue}' not configured")
            return await self._adapters[venue].estimate_slippage(
                token_in, token_out, amount_in
            )
        
        # Get estimates from all venues and return best
        estimates = await asyncio.gather(*[
            adapter.estimate_slippage(token_in, token_out, amount_in)
            for adapter in self._adapters.values()
        ])
        
        # Find venue with lowest slippage
        best = min(estimates, key=lambda e: e.price_impact)
        
        if best.price_impact > self.config.max_slippage:
            raise InsufficientLiquidityError(
                f"Slippage {best.price_impact:.2%} exceeds max {self.config.max_slippage:.2%}"
            )
        
        return best
    
    async def find_best_venue(
        self,
        token_in: str,
        token_out: str,
        amount_in: float
    ) -> VenueRecommendation:
        """Find the best venue for a trade based on liquidity and slippage.
        
        Args:
            token_in: Input token symbol
            token_out: Output token symbol
            amount_in: Amount to trade
            
        Returns:
            VenueRecommendation with best venue and alternatives
        """
        # Gather data from all venues
        results = []
        for name, adapter in self._adapters.items():
            try:
                depth = await adapter.get_pool_depth(token_in, token_out)
                slippage = await adapter.estimate_slippage(token_in, token_out, amount_in)
                score = await adapter.get_liquidity_score(token_in, token_out)
                results.append({
                    "venue": name,
                    "depth": depth,
                    "slippage": slippage,
                    "score": score
                })
            except Exception as e:
                logger.warning(f"Failed to analyze {name}: {e}")
        
        if not results:
            raise LiquidityError("No venues available for this pair")
        
        # Sort by composite score (liquidity score - slippage penalty)
        for r in results:
            slippage_penalty = int(r["slippage"].price_impact * 1000)
            r["composite"] = r["score"] - slippage_penalty
        
        results.sort(key=lambda x: x["composite"], reverse=True)
        
        best = results[0]
        alternatives = [r["venue"] for r in results[1:]]
        
        # Determine reason
        if best["slippage"].price_impact < 0.005:
            reason = "lowest_slippage"
        elif best["score"] > 80:
            reason = "highest_liquidity"
        else:
            reason = "best_composite_score"
        
        return VenueRecommendation(
            venue=best["venue"],
            reason=reason,
            liquidity_score=best["score"],
            estimated_slippage=best["slippage"].price_impact,
            alternatives=alternatives
        )
    
    def start_monitoring(
        self,
        token_pairs: List[Tuple[str, str]],
        callback: Optional[Callable[[PoolDepth], None]] = None
    ):
        """Start real-time liquidity monitoring.
        
        Args:
            token_pairs: List of (token_in, token_out) tuples to monitor
            callback: Optional callback function for updates
        """
        if self._monitoring_task:
            logger.warning("Monitoring already active")
            return
        
        if callback:
            self._monitoring_callbacks.append(callback)
        
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(token_pairs)
        )
        logger.info(f"Started monitoring {len(token_pairs)} pairs")
    
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            self._monitoring_task = None
            self._monitoring_callbacks.clear()
            logger.info("Stopped monitoring")
    
    async def _monitoring_loop(self, token_pairs: List[Tuple[str, str]]):
        """Internal monitoring loop."""
        while True:
            try:
                for token_in, token_out in token_pairs:
                    try:
                        depth = await self.analyze_pool_depth(token_in, token_out)
                        for callback in self._monitoring_callbacks:
                            callback(depth)
                    except Exception as e:
                        logger.error(f"Error monitoring {token_in}/{token_out}: {e}")
                
                await asyncio.sleep(self.config.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(self.config.update_interval)
    
    def get_last_update(self, token_in: str, token_out: str) -> Optional[PoolDepth]:
        """Get last cached pool depth for a pair."""
        return self._last_updates.get(f"{token_in}/{token_out}")
    
    async def get_all_depths(
        self,
        token_in: str,
        token_out: str
    ) -> List[PoolDepth]:
        """Get pool depth from all configured venues.
        
        Args:
            token_in: Input token symbol
            token_out: Output token symbol
            
        Returns:
            List of PoolDepth from all venues
        """
        return await asyncio.gather(*[
            adapter.get_pool_depth(token_in, token_out)
            for adapter in self._adapters.values()
        ])


# Convenience functions for non-async usage
def create_analyzer(
    venues: List[str] = None,
    min_depth_eth: float = 50.0,
    max_slippage: float = 0.02
) -> LiquidityAnalyzer:
    """Create a LiquidityAnalyzer with simplified config.
    
    Args:
        venues: List of venue names (default: all)
        min_depth_eth: Minimum depth in ETH
        max_slippage: Maximum slippage tolerance
        
    Returns:
        Configured LiquidityAnalyzer
    """
    if venues is None:
        venues = ["uniswap_v3", "curve", "sushiswap"]
    
    config = LiquidityConfig(
        venues=venues,
        min_depth_eth=min_depth_eth,
        max_slippage=max_slippage
    )
    return LiquidityAnalyzer(config)


# Export main classes
__all__ = [
    "LiquidityAnalyzer",
    "LiquidityConfig",
    "PoolDepth",
    "SlippageEstimate",
    "VenueRecommendation",
    "LiquidityError",
    "VenueNotSupportedError",
    "InsufficientLiquidityError",
    "create_analyzer"
]