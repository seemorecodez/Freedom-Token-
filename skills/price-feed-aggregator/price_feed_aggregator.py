"""
Price Feed Aggregator - Multi-source cryptocurrency price aggregation with outlier detection.

This module provides robust price aggregation across multiple exchanges with
statistical outlier detection and confidence scoring.
"""

import asyncio
import time
import statistics
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum
from collections import defaultdict
import hashlib
import json

import aiohttp


logger = logging.getLogger(__name__)


class AggregationMethod(Enum):
    """Supported price aggregation methods."""
    WEIGHTED_AVERAGE = "weighted_average"
    MEDIAN = "median"
    TRIMMED_MEAN = "trimmed_mean"


class PriceFeedException(Exception):
    """Base exception for price feed errors."""
    pass


class PriceFeedSourceError(PriceFeedException):
    """Raised when a price source fails."""
    pass


class AllSourcesFailedError(PriceFeedException):
    """Raised when all price sources fail."""
    pass


@dataclass
class PriceFeedConfig:
    """Configuration for price feed aggregator.
    
    Attributes:
        sources: List of source names to use (e.g., ["kraken", "coinbase"])
        weights: Optional weights for weighted average (sums to 1.0)
        refresh_interval: Minimum seconds between fresh fetches
        outlier_threshold: Modified z-score threshold for outlier detection
        aggregation_method: How to combine prices
        cache_ttl: Cache time-to-live in seconds
        max_retries: Number of retries per source
        timeout: HTTP timeout in seconds per source
        trim_percent: Percentage to trim from each end for trimmed mean (0.0-0.5)
    """
    sources: List[str] = field(default_factory=lambda: ["kraken", "coinbase", "binance", "chainlink"])
    weights: Optional[Dict[str, float]] = None
    refresh_interval: int = 30
    outlier_threshold: float = 3.5
    aggregation_method: str = "weighted_average"
    cache_ttl: int = 60
    max_retries: int = 3
    timeout: int = 5
    trim_percent: float = 0.1
    
    def __post_init__(self):
        """Validate configuration."""
        valid_sources = {"kraken", "coinbase", "binance", "chainlink"}
        invalid = set(self.sources) - valid_sources
        if invalid:
            raise ValueError(f"Invalid sources: {invalid}. Valid: {valid_sources}")
        
        if self.weights:
            total = sum(self.weights.values())
            if not 0.99 <= total <= 1.01:  # Allow small floating point error
                raise ValueError(f"Weights must sum to 1.0, got {total}")
            missing = set(self.sources) - set(self.weights.keys())
            if missing:
                raise ValueError(f"Missing weights for sources: {missing}")
        
        if not 0.0 <= self.trim_percent <= 0.5:
            raise ValueError(f"trim_percent must be between 0.0 and 0.5")
        
        valid_methods = {m.value for m in AggregationMethod}
        if self.aggregation_method not in valid_methods:
            raise ValueError(f"Invalid aggregation_method: {self.aggregation_method}")


@dataclass
class PriceResult:
    """Result of a price aggregation.
    
    Attributes:
        price: The aggregated price
        confidence: Score from 0.0 to 1.0 indicating reliability
        sources_used: List of sources that contributed
        sources_failed: List of sources that failed
        outliers: Dict of source -> price for detected outliers
        timestamp: Unix timestamp of the aggregation
        method: Aggregation method used
        raw_prices: All prices fetched (including outliers)
    """
    price: float
    confidence: float
    sources_used: List[str]
    sources_failed: List[str]
    outliers: Dict[str, float]
    timestamp: float
    method: str
    raw_prices: Dict[str, float]
    
    def __str__(self) -> str:
        return (f"PriceResult(price={self.price:.2f}, confidence={self.confidence:.2%}, "
                f"sources={len(self.sources_used)}/{len(self.sources_used) + len(self.sources_failed)})")


class PriceCache:
    """Simple TTL cache for price data."""
    
    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Tuple[float, float]] = {}  # key -> (price, timestamp)
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def _make_key(self, base: str, quote: str, method: str) -> str:
        """Create cache key."""
        return hashlib.md5(f"{base}_{quote}_{method}".encode()).hexdigest()
    
    def get(self, base: str, quote: str, method: str) -> Optional[float]:
        """Get cached price if not expired."""
        key = self._make_key(base, quote, method)
        if key in self._cache:
            price, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                self._stats["hits"] += 1
                return price
            else:
                del self._cache[key]
                self._stats["evictions"] += 1
        self._stats["misses"] += 1
        return None
    
    def set(self, base: str, quote: str, method: str, price: float) -> None:
        """Cache a price."""
        key = self._make_key(base, quote, method)
        self._cache[key] = (price, time.time())
    
    def clear(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return dict(self._stats)


class PriceSource:
    """Base class for price sources."""
    
    BASE_URLS = {
        "kraken": "https://api.kraken.com/0/public/Ticker",
        "coinbase": "https://api.coinbase.com/v2/exchange-rates",
        "binance": "https://api.binance.com/api/v3/ticker/price",
        "chainlink": "https://rpc.ankr.com/eth",  # Uses ETH RPC for Chainlink feeds
    }
    
    def __init__(self, name: str, timeout: int = 5):
        self.name = name
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"User-Agent": "PriceFeedAggregator/1.0"}
            )
        return self._session
    
    async def fetch_price(self, base: str, quote: str) -> float:
        """Fetch price from this source. Override in subclasses."""
        raise NotImplementedError
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


class KrakenSource(PriceSource):
    """Kraken exchange price source."""
    
    def __init__(self, timeout: int = 5):
        super().__init__("kraken", timeout)
    
    async def fetch_price(self, base: str, quote: str) -> float:
        """Fetch price from Kraken."""
        session = await self._get_session()
        
        # Kraken uses XBT for BTC
        kraken_base = "XBT" if base.upper() == "BTC" else base.upper()
        kraken_quote = "USD" if quote.upper() == "USD" else quote.upper()
        pair = f"{kraken_base}{kraken_quote}"
        
        url = f"{self.BASE_URLS['kraken']}?pair={pair}"
        
        async with session.get(url) as response:
            if response.status != 200:
                raise PriceFeedSourceError(f"Kraken API error: {response.status}")
            
            data = await response.json()
            
            if data.get("error"):
                raise PriceFeedSourceError(f"Kraken error: {data['error']}")
            
            result = data.get("result", {})
            if not result:
                raise PriceFeedSourceError(f"No data for pair {pair}")
            
            # Get the first (and usually only) pair data
            pair_data = list(result.values())[0]
            # c[0] is the last trade closed price
            price = float(pair_data["c"][0])
            return price


class CoinbaseSource(PriceSource):
    """Coinbase exchange price source."""
    
    def __init__(self, timeout: int = 5):
        super().__init__("coinbase", timeout)
    
    async def fetch_price(self, base: str, quote: str) -> float:
        """Fetch price from Coinbase."""
        session = await self._get_session()
        
        url = f"{self.BASE_URLS['coinbase']}?currency={base.upper()}"
        
        async with session.get(url) as response:
            if response.status != 200:
                raise PriceFeedSourceError(f"Coinbase API error: {response.status}")
            
            data = await response.json()
            rates = data.get("data", {}).get("rates", {})
            
            quote_upper = quote.upper()
            if quote_upper not in rates:
                raise PriceFeedSourceError(f"No rate for {quote_upper}")
            
            # Rate is how much 1 base = quote
            rate = float(rates[quote_upper])
            
            # If we're asking for BTC/USD, rate is directly the price
            # For inverse pairs, we may need to invert
            return rate


class BinanceSource(PriceSource):
    """Binance exchange price source."""
    
    def __init__(self, timeout: int = 5):
        super().__init__("binance", timeout)
    
    async def fetch_price(self, base: str, quote: str) -> float:
        """Fetch price from Binance."""
        session = await self._get_session()
        
        symbol = f"{base.upper()}{quote.upper()}"
        url = f"{self.BASE_URLS['binance']}?symbol={symbol}"
        
        async with session.get(url) as response:
            if response.status != 200:
                # Try reverse pair for some cases
                raise PriceFeedSourceError(f"Binance API error: {response.status}")
            
            data = await response.json()
            price = float(data.get("price", 0))
            
            if price <= 0:
                raise PriceFeedSourceError("Invalid price from Binance")
            
            return price


class ChainlinkSource(PriceSource):
    """Chainlink oracle price source (simplified implementation)."""
    
    # Chainlink price feed addresses on Ethereum mainnet
    FEEDS = {
        ("BTC", "USD"): "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",
        ("ETH", "USD"): "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
        ("LINK", "USD"): "0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c",
        ("DAI", "USD"): "0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9",
        ("USDC", "USD"): "0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6",
        ("USDT", "USD"): "0x3E7d1eAB13ad0104d2750B8863b489D65364e32D",
    }
    
    def __init__(self, timeout: int = 5):
        super().__init__("chainlink", timeout)
    
    async def fetch_price(self, base: str, quote: str) -> float:
        """Fetch price from Chainlink oracle via RPC."""
        key = (base.upper(), quote.upper())
        
        if key not in self.FEEDS:
            raise PriceFeedSourceError(f"No Chainlink feed for {base}/{quote}")
        
        feed_address = self.FEEDS[key]
        session = await self._get_session()
        
        # Chainlink latestRoundData() selector: 0xfeaf968c
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{
                "to": feed_address,
                "data": "0xfeaf968c"  # latestRoundData()
            }, "latest"],
            "id": 1
        }
        
        async with session.post(self.BASE_URLS["chainlink"], json=payload) as response:
            if response.status != 200:
                raise PriceFeedSourceError(f"Chainlink RPC error: {response.status}")
            
            data = await response.json()
            
            if "error" in data:
                raise PriceFeedSourceError(f"Chainlink error: {data['error']}")
            
            result = data.get("result", "0x")
            if len(result) < 66:
                raise PriceFeedSourceError("Invalid Chainlink response")
            
            # Parse the answer from the return data (uint80 roundId, int256 answer, ...)
            # Answer is at position 64 bytes (second slot)
            answer_hex = result[66:130]  # 64 hex chars
            answer = int(answer_hex, 16)
            
            # Chainlink prices have 8 decimals
            price = answer / 10**8
            
            if price <= 0:
                raise PriceFeedSourceError("Invalid Chainlink price")
            
            return price


# Source factory
SOURCE_CLASSES: Dict[str, type] = {
    "kraken": KrakenSource,
    "coinbase": CoinbaseSource,
    "binance": BinanceSource,
    "chainlink": ChainlinkSource,
}


def detect_outliers(prices: Dict[str, float], threshold: float = 3.5) -> Dict[str, float]:
    """Detect outliers using Modified Z-Score based on MAD.
    
    The modified z-score is more robust than standard z-score for small samples
    and non-normal distributions common in crypto markets.
    
    Args:
        prices: Dict of source name -> price
        threshold: Modified z-score threshold (default 3.5)
    
    Returns:
        Dict of outlier source names and their prices
    """
    if len(prices) < 3:
        # Not enough data for meaningful outlier detection
        return {}
    
    values = list(prices.values())
    median = statistics.median(values)
    
    # Calculate MAD (Median Absolute Deviation)
    abs_deviations = [abs(v - median) for v in values]
    mad = statistics.median(abs_deviations)
    
    if mad == 0:
        # All values are identical or nearly so
        return {}
    
    outliers = {}
    for source, price in prices.items():
        # Modified z-score: 0.6745 * (x - median) / MAD
        modified_z_score = 0.6745 * (price - median) / mad
        
        if abs(modified_z_score) > threshold:
            outliers[source] = price
            logger.debug(f"Outlier detected: {source}={price} (z={modified_z_score:.2f})")
    
    return outliers


def detect_outliers_iqr(prices: Dict[str, float], k: float = 1.5) -> Dict[str, float]:
    """Detect outliers using the IQR method.
    
    Args:
        prices: Dict of source name -> price
        k: IQR multiplier (default 1.5 for standard outliers)
    
    Returns:
        Dict of outlier source names and their prices
    """
    if len(prices) < 4:
        return {}
    
    values = sorted(prices.values())
    n = len(values)
    
    # Calculate Q1 and Q3
    q1_idx = (n - 1) * 0.25
    q3_idx = (n - 1) * 0.75
    
    # Linear interpolation for quartiles
    q1_lower = int(q1_idx)
    q1_upper = min(q1_lower + 1, n - 1)
    q1_frac = q1_idx - q1_lower
    q1 = values[q1_lower] * (1 - q1_frac) + values[q1_upper] * q1_frac
    
    q3_lower = int(q3_idx)
    q3_upper = min(q3_lower + 1, n - 1)
    q3_frac = q3_idx - q3_lower
    q3 = values[q3_lower] * (1 - q3_frac) + values[q3_upper] * q3_frac
    
    iqr = q3 - q1
    lower_bound = q1 - k * iqr
    upper_bound = q3 + k * iqr
    
    outliers = {}
    for source, price in prices.items():
        if price < lower_bound or price > upper_bound:
            outliers[source] = price
            logger.debug(f"IQR outlier: {source}={price} (bounds: {lower_bound:.2f}-{upper_bound:.2f})")
    
    return outliers


def aggregate_price(
    prices: Dict[str, float],
    method: str = "weighted_average",
    weights: Optional[Dict[str, float]] = None,
    trim_percent: float = 0.1
) -> float:
    """Aggregate prices using the specified method.
    
    Args:
        prices: Dict of source name -> price
        method: Aggregation method (weighted_average, median, trimmed_mean)
        weights: Optional weights for weighted average
        trim_percent: Percentage to trim from each end for trimmed mean
    
    Returns:
        Aggregated price
    
    Raises:
        ValueError: If no prices provided or invalid method
    """
    if not prices:
        raise ValueError("No prices to aggregate")
    
    values = list(prices.values())
    
    if method == AggregationMethod.WEIGHTED_AVERAGE.value:
        if weights:
            # Use provided weights
            total_weight = 0.0
            weighted_sum = 0.0
            for source, price in prices.items():
                weight = weights.get(source, 1.0 / len(prices))
                weighted_sum += price * weight
                total_weight += weight
            return weighted_sum / total_weight if total_weight > 0 else statistics.mean(values)
        else:
            # Equal weights
            return statistics.mean(values)
    
    elif method == AggregationMethod.MEDIAN.value:
        return statistics.median(values)
    
    elif method == AggregationMethod.TRIMMED_MEAN.value:
        if len(values) < 4:
            # Not enough data for meaningful trim
            return statistics.mean(values)
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        trim_count = int(n * trim_percent)
        
        if trim_count == 0:
            return statistics.mean(sorted_values)
        
        trimmed = sorted_values[trim_count:-trim_count]
        if not trimmed:
            trimmed = sorted_values  # Fallback if trim was too aggressive
        
        return statistics.mean(trimmed)
    
    else:
        raise ValueError(f"Unknown aggregation method: {method}")


def calculate_confidence(
    prices: Dict[str, float],
    outliers: Dict[str, float],
    failed_sources: List[str],
    total_sources: int
) -> float:
    """Calculate confidence score for the aggregated price.
    
    Factors (equal weight):
    - Response rate: % of sources that responded
    - Outlier ratio: % of prices that are NOT outliers
    - Price spread: inverse of coefficient of variation
    - Source diversity: normalized count of sources used
    
    Args:
        prices: All prices that responded
        outliers: Detected outliers
        failed_sources: List of sources that failed
        total_sources: Total number of sources attempted
    
    Returns:
        Confidence score between 0.0 and 1.0
    """
    if not prices:
        return 0.0
    
    # Response rate (25% weight)
    successful = len(prices)
    response_rate = successful / total_sources if total_sources > 0 else 0
    
    # Outlier ratio (25% weight)
    clean_prices = {k: v for k, v in prices.items() if k not in outliers}
    outlier_ratio = len(outliers) / successful if successful > 0 else 1
    
    # Price spread (25% weight) - using coefficient of variation
    clean_values = list(clean_prices.values())
    if len(clean_values) >= 2:
        mean_price = statistics.mean(clean_values)
        stdev = statistics.stdev(clean_values) if len(clean_values) > 1 else 0
        cv = stdev / mean_price if mean_price > 0 else 1
        # Convert CV to spread score (lower CV = higher score)
        spread_score = max(0, 1 - cv * 10)  # Scale factor of 10
    else:
        spread_score = 0.5  # Neutral for single source
    
    # Source diversity (25% weight)
    diversity_score = min(1.0, successful / 4)  # Cap at 4 sources = full score
    
    # Weighted average
    confidence = (
        0.25 * response_rate +
        0.25 * (1 - outlier_ratio) +
        0.25 * spread_score +
        0.25 * diversity_score
    )
    
    return round(max(0.0, min(1.0, confidence)), 4)


async def fetch_prices(
    sources: List[str],
    base: str,
    quote: str,
    timeout: int = 5,
    max_retries: int = 3
) -> Tuple[Dict[str, float], Dict[str, Exception]]:
    """Fetch prices from multiple sources concurrently.
    
    Args:
        sources: List of source names
        base: Base currency (e.g., "BTC")
        quote: Quote currency (e.g., "USD")
        timeout: Timeout per request
        max_retries: Max retries per source
    
    Returns:
        Tuple of (successful prices dict, failed sources with exceptions)
    """
    prices: Dict[str, float] = {}
    errors: Dict[str, Exception] = {}
    
    async def fetch_with_retry(source_name: str) -> Optional[float]:
        """Fetch with retry logic."""
        source_class = SOURCE_CLASSES.get(source_name)
        if not source_class:
            errors[source_name] = PriceFeedSourceError(f"Unknown source: {source_name}")
            return None
        
        source = source_class(timeout=timeout)
        
        for attempt in range(max_retries):
            try:
                price = await source.fetch_price(base, quote)
                await source.close()
                return price
            except Exception as e:
                logger.warning(f"{source_name} attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    errors[source_name] = e
                    await source.close()
                    return None
                # Exponential backoff with jitter
                await asyncio.sleep(0.1 * (2 ** attempt) + (hash(source_name) % 100) / 1000)
        
        return None
    
    # Fetch all sources concurrently
    tasks = [fetch_with_retry(source) for source in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for source, result in zip(sources, results):
        if isinstance(result, Exception) and source not in errors:
            errors[source] = result
        elif result is not None:
            prices[source] = result
    
    return prices, errors


class PriceFeedAggregator:
    """Main price feed aggregator class.
    
    Provides multi-source price aggregation with outlier detection,
    configurable aggregation methods, and confidence scoring.
    
    Example:
        aggregator = PriceFeedAggregator()
        result = await aggregator.get_price("BTC", "USD")
        print(f"Price: ${result.price:,.2f} (confidence: {result.confidence:.1%})")
    """
    
    def __init__(self, config: Optional[PriceFeedConfig] = None):
        """Initialize the aggregator.
        
        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or PriceFeedConfig()
        self.cache = PriceCache(self.config.cache_ttl)
        self._last_fetch: Dict[str, float] = {}  # Track last fetch time per pair
    
    async def get_price(
        self,
        base: str,
        quote: str,
        use_cache: bool = True
    ) -> PriceResult:
        """Get aggregated price for a trading pair.
        
        Args:
            base: Base currency (e.g., "BTC", "ETH")
            quote: Quote currency (e.g., "USD", "EUR")
            use_cache: Whether to use cached data if available
        
        Returns:
            PriceResult with aggregated price and metadata
        
        Raises:
            AllSourcesFailedError: If all sources fail to respond
        """
        base_upper = base.upper()
        quote_upper = quote.upper()
        method = self.config.aggregation_method
        
        # Check cache
        if use_cache:
            cached = self.cache.get(base_upper, quote_upper, method)
            if cached is not None:
                # Return cached result structure (without raw data)
                return PriceResult(
                    price=cached,
                    confidence=0.0,  # Can't determine from cache alone
                    sources_used=[],
                    sources_failed=[],
                    outliers={},
                    timestamp=time.time(),
                    method=f"{method}_cached",
                    raw_prices={}
                )
        
        # Check refresh interval
        pair_key = f"{base_upper}_{quote_upper}"
        last_fetch = self._last_fetch.get(pair_key, 0)
        if time.time() - last_fetch < self.config.refresh_interval:
            # Too soon, use cache or wait
            if not use_cache:
                await asyncio.sleep(self.config.refresh_interval - (time.time() - last_fetch))
        
        # Fetch from all sources
        prices, errors = await fetch_prices(
            self.config.sources,
            base_upper,
            quote_upper,
            self.config.timeout,
            self.config.max_retries
        )
        
        if not prices:
            raise AllSourcesFailedError(
                f"All sources failed for {base_upper}/{quote_upper}: {errors}"
            )
        
        # Detect outliers
        outliers = detect_outliers(prices, self.config.outlier_threshold)
        
        # Filter outliers for aggregation
        clean_prices = {k: v for k, v in prices.items() if k not in outliers}
        
        if not clean_prices:
            # All prices are outliers - use median of all as fallback
            logger.warning(f"All prices flagged as outliers for {base_upper}/{quote_upper}")
            clean_prices = prices
        
        # Aggregate
        aggregated = aggregate_price(
            clean_prices,
            self.config.aggregation_method,
            self.config.weights,
            self.config.trim_percent
        )
        
        # Calculate confidence
        confidence = calculate_confidence(
            prices,
            outliers,
            list(errors.keys()),
            len(self.config.sources)
        )
        
        # Update cache and timestamp
        self.cache.set(base_upper, quote_upper, method, aggregated)
        self._last_fetch[pair_key] = time.time()
        
        return PriceResult(
            price=aggregated,
            confidence=confidence,
            sources_used=list(clean_prices.keys()),
            sources_failed=list(errors.keys()),
            outliers=outliers,
            timestamp=time.time(),
            method=self.config.aggregation_method,
            raw_prices=prices
        )
    
    async def get_prices(
        self,
        pairs: List[Tuple[str, str]]
    ) -> Dict[str, PriceResult]:
        """Get prices for multiple pairs concurrently.
        
        Args:
            pairs: List of (base, quote) tuples
        
        Returns:
            Dict mapping "BASE_QUOTE" to PriceResult
        """
        tasks = [self.get_price(base, quote) for base, quote in pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        output = {}
        for (base, quote), result in zip(pairs, results):
            key = f"{base.upper()}_{quote.upper()}"
            output[key] = result if not isinstance(result, Exception) else None
        
        return output
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return self.cache.get_stats()
    
    def clear_cache(self) -> None:
        """Clear the price cache."""
        self.cache.clear()
