"""
Unit tests for the Price Feed Aggregator.

Run with: python -m pytest test_price_feed_aggregator.py -v
"""

import pytest
import asyncio
import time
import statistics
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict

from price_feed_aggregator import (
    PriceFeedConfig,
    PriceFeedAggregator,
    PriceResult,
    PriceCache,
    PriceFeedSource,
    PriceFeedException,
    PriceFeedSourceError,
    AllSourcesFailedError,
    KrakenSource,
    CoinbaseSource,
    BinanceSource,
    ChainlinkSource,
    detect_outliers,
    detect_outliers_iqr,
    aggregate_price,
    calculate_confidence,
    fetch_prices,
    AggregationMethod,
    SOURCE_CLASSES,
)


class TestPriceFeedConfig:
    """Tests for PriceFeedConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = PriceFeedConfig()
        assert config.sources == ["kraken", "coinbase", "binance", "chainlink"]
        assert config.weights is None
        assert config.refresh_interval == 30
        assert config.outlier_threshold == 3.5
        assert config.aggregation_method == "weighted_average"
        assert config.cache_ttl == 60
        assert config.max_retries == 3
        assert config.timeout == 5
        assert config.trim_percent == 0.1
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = PriceFeedConfig(
            sources=["kraken", "coinbase"],
            weights={"kraken": 0.6, "coinbase": 0.4},
            refresh_interval=15,
            aggregation_method="median"
        )
        assert config.sources == ["kraken", "coinbase"]
        assert config.weights == {"kraken": 0.6, "coinbase": 0.4}
        assert config.refresh_interval == 15
        assert config.aggregation_method == "median"
    
    def test_invalid_source(self):
        """Test validation of invalid source."""
        with pytest.raises(ValueError, match="Invalid sources"):
            PriceFeedConfig(sources=["kraken", "invalid_exchange"])
    
    def test_weights_dont_sum_to_one(self):
        """Test validation of weights not summing to 1.0."""
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            PriceFeedConfig(
                sources=["kraken", "coinbase"],
                weights={"kraken": 0.5, "coinbase": 0.3}
            )
    
    def test_missing_weights(self):
        """Test validation of missing weights for sources."""
        with pytest.raises(ValueError, match="Missing weights"):
            PriceFeedConfig(
                sources=["kraken", "coinbase", "binance"],
                weights={"kraken": 0.5, "coinbase": 0.5}
            )
    
    def test_invalid_trim_percent(self):
        """Test validation of trim_percent bounds."""
        with pytest.raises(ValueError, match="trim_percent"):
            PriceFeedConfig(trim_percent=0.6)
        
        with pytest.raises(ValueError, match="trim_percent"):
            PriceFeedConfig(trim_percent=-0.1)
    
    def test_invalid_aggregation_method(self):
        """Test validation of aggregation method."""
        with pytest.raises(ValueError, match="Invalid aggregation_method"):
            PriceFeedConfig(aggregation_method="invalid_method")


class TestOutlierDetection:
    """Tests for outlier detection functions."""
    
    def test_detect_outliers_no_outliers(self):
        """Test outlier detection with clean data."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 50100.0,
            "binance": 50050.0,
            "chainlink": 50025.0
        }
        outliers = detect_outliers(prices, threshold=3.5)
        assert outliers == {}
    
    def test_detect_outliers_with_outlier(self):
        """Test outlier detection with one obvious outlier."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 50100.0,
            "binance": 50050.0,
            "chainlink": 60000.0  # Clear outlier
        }
        outliers = detect_outliers(prices, threshold=3.5)
        assert "chainlink" in outliers
        assert len(outliers) == 1
    
    def test_detect_outliers_insufficient_data(self):
        """Test outlier detection with less than 3 data points."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 50100.0
        }
        outliers = detect_outliers(prices)
        assert outliers == {}
    
    def test_detect_outliers_identical_values(self):
        """Test outlier detection with all identical values."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 50000.0,
            "binance": 50000.0,
            "chainlink": 50000.0
        }
        outliers = detect_outliers(prices)
        assert outliers == {}
    
    def test_detect_outliers_iqr_no_outliers(self):
        """Test IQR outlier detection with clean data."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 50100.0,
            "binance": 50050.0,
            "chainlink": 50025.0
        }
        outliers = detect_outliers_iqr(prices)
        assert outliers == {}
    
    def test_detect_outliers_iqr_with_outlier(self):
        """Test IQR outlier detection with an outlier."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 50100.0,
            "binance": 50050.0,
            "chainlink": 60000.0  # Outlier
        }
        outliers = detect_outliers_iqr(prices)
        assert "chainlink" in outliers
    
    def test_detect_outliers_iqr_insufficient_data(self):
        """Test IQR with insufficient data."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 50100.0,
            "binance": 50200.0
        }
        outliers = detect_outliers_iqr(prices)
        assert outliers == {}


class TestAggregatePrice:
    """Tests for price aggregation functions."""
    
    def test_aggregate_weighted_average_default(self):
        """Test weighted average without explicit weights."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 51000.0
        }
        result = aggregate_price(prices, method="weighted_average")
        assert result == 50500.0  # Simple mean
    
    def test_aggregate_weighted_average_with_weights(self):
        """Test weighted average with explicit weights."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 51000.0
        }
        weights = {"kraken": 0.7, "coinbase": 0.3}
        result = aggregate_price(prices, method="weighted_average", weights=weights)
        expected = 50000.0 * 0.7 + 51000.0 * 0.3
        assert result == expected
    
    def test_aggregate_median_odd_count(self):
        """Test median with odd number of prices."""
        prices = {
            "kraken": 49000.0,
            "coinbase": 51000.0,
            "binance": 50000.0
        }
        result = aggregate_price(prices, method="median")
        assert result == 50000.0
    
    def test_aggregate_median_even_count(self):
        """Test median with even number of prices."""
        prices = {
            "kraken": 49000.0,
            "coinbase": 51000.0
        }
        result = aggregate_price(prices, method="median")
        assert result == 50000.0  # Average of two middle values
    
    def test_aggregate_trimmed_mean(self):
        """Test trimmed mean aggregation."""
        prices = {
            "a": 100.0,
            "b": 101.0,
            "c": 102.0,
            "d": 103.0,
            "e": 200.0  # Outlier to be trimmed
        }
        result = aggregate_price(prices, method="trimmed_mean", trim_percent=0.2)
        # Removes one from each end (20% of 5 = 1)
        # Remaining: 101, 102, 103
        expected = (101.0 + 102.0 + 103.0) / 3
        assert result == pytest.approx(expected)
    
    def test_aggregate_trimmed_mean_small_sample(self):
        """Test trimmed mean with small sample."""
        prices = {
            "a": 100.0,
            "b": 101.0
        }
        result = aggregate_price(prices, method="trimmed_mean", trim_percent=0.1)
        # Not enough data, falls back to mean
        assert result == 100.5
    
    def test_aggregate_empty_prices(self):
        """Test aggregation with empty prices."""
        with pytest.raises(ValueError, match="No prices to aggregate"):
            aggregate_price({})
    
    def test_aggregate_invalid_method(self):
        """Test aggregation with invalid method."""
        prices = {"kraken": 50000.0}
        with pytest.raises(ValueError, match="Unknown aggregation method"):
            aggregate_price(prices, method="invalid")


class TestCalculateConfidence:
    """Tests for confidence scoring."""
    
    def test_confidence_perfect(self):
        """Test confidence with perfect conditions."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 50001.0,
            "binance": 50000.5,
            "chainlink": 50000.25
        }
        confidence = calculate_confidence(prices, {}, [], 4)
        assert confidence > 0.9  # High confidence
    
    def test_confidence_with_outliers(self):
        """Test confidence with outliers."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 50001.0,
            "binance": 60000.0  # Outlier
        }
        outliers = {"binance": 60000.0}
        confidence = calculate_confidence(prices, outliers, [], 4)
        assert 0.5 < confidence < 0.9  # Reduced confidence
    
    def test_confidence_with_failures(self):
        """Test confidence with failed sources."""
        prices = {
            "kraken": 50000.0,
            "coinbase": 50001.0
        }
        failed = ["binance", "chainlink"]
        confidence = calculate_confidence(prices, {}, failed, 4)
        assert 0.5 < confidence < 0.9  # Reduced due to failures
    
    def test_confidence_high_spread(self):
        """Test confidence with high price spread."""
        prices = {
            "kraken": 40000.0,
            "coinbase": 60000.0  # Large spread
        }
        confidence = calculate_confidence(prices, {}, [], 4)
        assert confidence < 0.7  # Lower confidence due to spread
    
    def test_confidence_empty_prices(self):
        """Test confidence with no prices."""
        confidence = calculate_confidence({}, [], [], 4)
        assert confidence == 0.0
    
    def test_confidence_single_source(self):
        """Test confidence with single source."""
        prices = {"kraken": 50000.0}
        confidence = calculate_confidence(prices, {}, ["coinbase", "binance", "chainlink"], 4)
        # Single source = lower diversity score
        assert confidence < 0.8


class TestPriceCache:
    """Tests for PriceCache class."""
    
    def test_cache_set_and_get(self):
        """Test basic cache operations."""
        cache = PriceCache(ttl_seconds=60)
        cache.set("BTC", "USD", "median", 50000.0)
        
        result = cache.get("BTC", "USD", "median")
        assert result == 50000.0
    
    def test_cache_miss(self):
        """Test cache miss."""
        cache = PriceCache(ttl_seconds=60)
        result = cache.get("BTC", "USD", "median")
        assert result is None
    
    def test_cache_expiration(self):
        """Test cache TTL expiration."""
        cache = PriceCache(ttl_seconds=0.1)
        cache.set("BTC", "USD", "median", 50000.0)
        
        # Immediately should hit
        assert cache.get("BTC", "USD", "median") == 50000.0
        
        # Wait for expiration
        time.sleep(0.15)
        assert cache.get("BTC", "USD", "median") is None
    
    def test_cache_different_keys(self):
        """Test cache with different keys."""
        cache = PriceCache(ttl_seconds=60)
        cache.set("BTC", "USD", "median", 50000.0)
        cache.set("ETH", "USD", "median", 3000.0)
        cache.set("BTC", "EUR", "median", 46000.0)
        
        assert cache.get("BTC", "USD", "median") == 50000.0
        assert cache.get("ETH", "USD", "median") == 3000.0
        assert cache.get("BTC", "EUR", "median") == 46000.0
    
    def test_cache_clear(self):
        """Test cache clear."""
        cache = PriceCache(ttl_seconds=60)
        cache.set("BTC", "USD", "median", 50000.0)
        cache.clear()
        
        assert cache.get("BTC", "USD", "median") is None
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = PriceCache(ttl_seconds=0.1)
        
        # Miss
        cache.get("BTC", "USD", "median")
        
        # Hit
        cache.set("BTC", "USD", "median", 50000.0)
        cache.get("BTC", "USD", "median")
        
        # Expire
        time.sleep(0.15)
        cache.get("BTC", "USD", "median")
        
        stats = cache.get_stats()
        assert stats["misses"] == 2
        assert stats["hits"] == 1
        assert stats["evictions"] == 1


class TestFetchPrices:
    """Tests for fetch_prices function."""
    
    @pytest.mark.asyncio
    async def test_fetch_prices_success(self):
        """Test successful price fetching from multiple sources."""
        with patch("price_feed_aggregator.KrakenSource") as mock_kraken, \
             patch("price_feed_aggregator.CoinbaseSource") as mock_coinbase:
            
            # Setup mocks
            kraken_instance = AsyncMock()
            kraken_instance.fetch_price = AsyncMock(return_value=50000.0)
            kraken_instance.close = AsyncMock()
            mock_kraken.return_value = kraken_instance
            
            coinbase_instance = AsyncMock()
            coinbase_instance.fetch_price = AsyncMock(return_value=50100.0)
            coinbase_instance.close = AsyncMock()
            mock_coinbase.return_value = coinbase_instance
            
            prices, errors = await fetch_prices(
                ["kraken", "coinbase"],
                "BTC",
                "USD",
                timeout=5,
                max_retries=1
            )
            
            assert "kraken" in prices
            assert "coinbase" in prices
            assert prices["kraken"] == 50000.0
            assert prices["coinbase"] == 50100.0
            assert errors == {}
    
    @pytest.mark.asyncio
    async def test_fetch_prices_partial_failure(self):
        """Test fetching when some sources fail."""
        with patch("price_feed_aggregator.KrakenSource") as mock_kraken, \
             patch("price_feed_aggregator.CoinbaseSource") as mock_coinbase:
            
            # Kraken succeeds, Coinbase fails
            kraken_instance = AsyncMock()
            kraken_instance.fetch_price = AsyncMock(return_value=50000.0)
            kraken_instance.close = AsyncMock()
            mock_kraken.return_value = kraken_instance
            
            coinbase_instance = AsyncMock()
            coinbase_instance.fetch_price = AsyncMock(
                side_effect=PriceFeedSourceError("API error")
            )
            coinbase_instance.close = AsyncMock()
            mock_coinbase.return_value = coinbase_instance
            
            prices, errors = await fetch_prices(
                ["kraken", "coinbase"],
                "BTC",
                "USD",
                timeout=5,
                max_retries=1
            )
            
            assert "kraken" in prices
            assert "kraken" not in errors
            assert "coinbase" in errors
            assert isinstance(errors["coinbase"], PriceFeedSourceError)
    
    @pytest.mark.asyncio
    async def test_fetch_prices_all_fail(self):
        """Test fetching when all sources fail."""
        with patch("price_feed_aggregator.KrakenSource") as mock_kraken:
            kraken_instance = AsyncMock()
            kraken_instance.fetch_price = AsyncMock(
                side_effect=PriceFeedSourceError("API error")
            )
            kraken_instance.close = AsyncMock()
            mock_kraken.return_value = kraken_instance
            
            prices, errors = await fetch_prices(
                ["kraken"],
                "BTC",
                "USD",
                timeout=5,
                max_retries=1
            )
            
            assert prices == {}
            assert "kraken" in errors


class TestPriceFeedAggregator:
    """Tests for PriceFeedAggregator class."""
    
    @pytest.fixture
    def config(self):
        return PriceFeedConfig(
            sources=["kraken", "coinbase"],
            aggregation_method="median",
            cache_ttl=60
        )
    
    @pytest.fixture
    def aggregator(self, config):
        return PriceFeedAggregator(config)
    
    @pytest.mark.asyncio
    async def test_get_price_success(self, aggregator):
        """Test successful price retrieval."""
        with patch("price_feed_aggregator.fetch_prices") as mock_fetch:
            mock_fetch.return_value = (
                {"kraken": 50000.0, "coinbase": 50100.0},
                {}
            )
            
            result = await aggregator.get_price("BTC", "USD")
            
            assert isinstance(result, PriceResult)
            assert result.price == 50050.0  # Median of 50000, 50100
            assert result.confidence > 0.5
            assert "kraken" in result.sources_used
            assert "coinbase" in result.sources_used
            assert result.method == "median"
    
    @pytest.mark.asyncio
    async def test_get_price_with_outliers(self, aggregator):
        """Test price retrieval with outlier detection."""
        with patch("price_feed_aggregator.fetch_prices") as mock_fetch:
            mock_fetch.return_value = (
                {
                    "kraken": 50000.0,
                    "coinbase": 50100.0,
                },
                {}
            )
            
            result = await aggregator.get_price("BTC", "USD")
            
            # With only 2 sources, outlier detection is skipped
            assert len(result.outliers) == 0
    
    @pytest.mark.asyncio
    async def test_get_price_all_sources_fail(self, aggregator):
        """Test error when all sources fail."""
        with patch("price_feed_aggregator.fetch_prices") as mock_fetch:
            mock_fetch.return_value = (
                {},
                {
                    "kraken": PriceFeedSourceError("Timeout"),
                    "coinbase": PriceFeedSourceError("API error")
                }
            )
            
            with pytest.raises(AllSourcesFailedError):
                await aggregator.get_price("BTC", "USD")
    
    @pytest.mark.asyncio
    async def test_get_price_uses_cache(self, aggregator):
        """Test that caching works correctly."""
        with patch("price_feed_aggregator.fetch_prices") as mock_fetch:
            mock_fetch.return_value = (
                {"kraken": 50000.0, "coinbase": 50100.0},
                {}
            )
            
            # First call - should fetch
            result1 = await aggregator.get_price("BTC", "USD")
            assert mock_fetch.call_count == 1
            
            # Second call - should use cache
            result2 = await aggregator.get_price("BTC", "USD", use_cache=True)
            assert mock_fetch.call_count == 1  # No additional fetch
    
    @pytest.mark.asyncio
    async def test_get_price_bypass_cache(self, aggregator):
        """Test bypassing cache."""
        with patch("price_feed_aggregator.fetch_prices") as mock_fetch:
            mock_fetch.return_value = (
                {"kraken": 50000.0, "coinbase": 50100.0},
                {}
            )
            
            # First call
            await aggregator.get_price("BTC", "USD")
            
            # Second call bypassing cache
            await aggregator.get_price("BTC", "USD", use_cache=False)
            
            assert mock_fetch.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_prices_multiple_pairs(self, aggregator):
        """Test fetching multiple pairs."""
        with patch("price_feed_aggregator.fetch_prices") as mock_fetch:
            mock_fetch.return_value = (
                {"kraken": 50000.0, "coinbase": 50100.0},
                {}
            )
            
            results = await aggregator.get_prices([
                ("BTC", "USD"),
                ("ETH", "USD")
            ])
            
            assert "BTC_USD" in results
            assert "ETH_USD" in results
            assert results["BTC_USD"] is not None
            assert results["ETH_USD"] is not None
    
    def test_get_cache_stats(self, aggregator):
        """Test cache statistics retrieval."""
        stats = aggregator.get_cache_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "evictions" in stats
    
    def test_clear_cache(self, aggregator):
        """Test cache clearing."""
        # Add something to cache
        aggregator.cache.set("BTC", "USD", "median", 50000.0)
        
        # Clear
        aggregator.clear_cache()
        
        # Verify cleared
        assert aggregator.cache.get("BTC", "USD", "median") is None


class TestPriceSources:
    """Tests for individual price source implementations."""
    
    @pytest.mark.asyncio
    async def test_kraken_fetch_success(self):
        """Test Kraken API parsing."""
        source = KrakenSource(timeout=5)
        
        mock_response = {
            "error": [],
            "result": {
                "XBTUSD": {
                    "c": ["50000.0", "1.5"]  # last trade closed
                }
            }
        }
        
        mock_session = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.status = 200
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_session.get = AsyncMock(return_value=mock_response_obj)
        
        source._session = mock_session
        
        price = await source.fetch_price("BTC", "USD")
        assert price == 50000.0
        await source.close()
    
    @pytest.mark.asyncio
    async def test_kraken_fetch_error(self):
        """Test Kraken API error handling."""
        source = KrakenSource(timeout=5)
        
        mock_response = {"error": ["EGeneral:Invalid arguments"]}
        
        mock_session = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.status = 200
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_session.get = AsyncMock(return_value=mock_response_obj)
        
        source._session = mock_session
        
        with pytest.raises(PriceFeedSourceError):
            await source.fetch_price("INVALID", "PAIR")
        
        await source.close()
    
    @pytest.mark.asyncio
    async def test_coinbase_fetch_success(self):
        """Test Coinbase API parsing."""
        source = CoinbaseSource(timeout=5)
        
        mock_response = {
            "data": {
                "currency": "BTC",
                "rates": {
                    "USD": "50000.00",
                    "EUR": "46000.00"
                }
            }
        }
        
        mock_session = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.status = 200
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_session.get = AsyncMock(return_value=mock_response_obj)
        
        source._session = mock_session
        
        price = await source.fetch_price("BTC", "USD")
        assert price == 50000.0
        await source.close()
    
    @pytest.mark.asyncio
    async def test_binance_fetch_success(self):
        """Test Binance API parsing."""
        source = BinanceSource(timeout=5)
        
        mock_response = {
            "symbol": "BTCUSD",
            "price": "50000.00"
        }
        
        mock_session = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.status = 200
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_session.get = AsyncMock(return_value=mock_response_obj)
        
        source._session = mock_session
        
        price = await source.fetch_price("BTC", "USD")
        assert price == 50000.0
        await source.close()
    
    @pytest.mark.asyncio
    async def test_chainlink_fetch_success(self):
        """Test Chainlink oracle parsing."""
        source = ChainlinkSource(timeout=5)
        
        # Mock RPC response - latestRoundData returns (uint80,int256,uint256,uint256,uint80)
        # Answer is at slot 1 (32 bytes offset, 32 bytes data)
        # 50000 * 10^8 = 5000000000000 = 0x48C27395000
        answer = 50000 * 10**8
        answer_hex = f"{answer:064x}"
        result = "0x" + "0" * 64 + answer_hex + "0" * 128
        
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": result
        }
        
        mock_session = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.status = 200
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_session.post = AsyncMock(return_value=mock_response_obj)
        
        source._session = mock_session
        
        price = await source.fetch_price("BTC", "USD")
        assert price == 50000.0
        await source.close()
    
    @pytest.mark.asyncio
    async def test_chainlink_unsupported_pair(self):
        """Test Chainlink with unsupported pair."""
        source = ChainlinkSource(timeout=5)
        
        with pytest.raises(PriceFeedSourceError, match="No Chainlink feed"):
            await source.fetch_price("XYZ", "ABC")


class TestPriceResult:
    """Tests for PriceResult dataclass."""
    
    def test_price_result_str(self):
        """Test string representation."""
        result = PriceResult(
            price=50000.0,
            confidence=0.95,
            sources_used=["kraken", "coinbase"],
            sources_failed=[],
            outliers={},
            timestamp=time.time(),
            method="median",
            raw_prices={"kraken": 50000.0, "coinbase": 50100.0}
        )
        
        str_repr = str(result)
        assert "50000.00" in str_repr
        assert "95.00%" in str_repr or "95%" in str_repr


class TestIntegration:
    """Integration tests with mocked external APIs."""
    
    @pytest.mark.asyncio
    async def test_full_flow_median(self):
        """Test complete flow with median aggregation."""
        config = PriceFeedConfig(
            sources=["kraken", "coinbase", "binance"],
            aggregation_method="median"
        )
        aggregator = PriceFeedAggregator(config)
        
        with patch("price_feed_aggregator.fetch_prices") as mock_fetch:
            mock_fetch.return_value = (
                {
                    "kraken": 50000.0,
                    "coinbase": 50100.0,
                    "binance": 50200.0
                },
                {}
            )
            
            result = await aggregator.get_price("BTC", "USD")
            
            assert result.price == 50100.0  # Median
            assert result.confidence > 0.8
            assert len(result.sources_used) == 3
            assert result.method == "median"
    
    @pytest.mark.asyncio
    async def test_full_flow_with_outlier_removal(self):
        """Test complete flow with outlier detection and removal."""
        config = PriceFeedConfig(
            sources=["kraken", "coinbase", "binance", "chainlink"],
            aggregation_method="trimmed_mean",
            outlier_threshold=2.0,  # Lower threshold for testing
            trim_percent=0.1
        )
        aggregator = PriceFeedAggregator(config)
        
        with patch("price_feed_aggregator.fetch_prices") as mock_fetch:
            mock_fetch.return_value = (
                {
                    "kraken": 50000.0,
                    "coinbase": 50050.0,
                    "binance": 50100.0,
                    "chainlink": 65000.0  # Clear outlier
                },
                {}
            )
            
            result = await aggregator.get_price("BTC", "USD")
            
            # Should exclude the outlier
            assert "chainlink" in result.outliers
            assert 50000.0 < result.price < 50150.0
            # Confidence should be reduced due to outlier
            assert result.confidence < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
