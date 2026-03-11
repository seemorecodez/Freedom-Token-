"""
Arbitrage Detector - Cryptocurrency price arbitrage detection across exchanges.

This module provides tools to detect simple and triangular arbitrage opportunities
by comparing prices across multiple cryptocurrency exchanges.
"""

import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP


@dataclass
class ArbitrageConfig:
    """Configuration for the arbitrage detector.
    
    Attributes:
        pairs: List of trading pairs to monitor (e.g., "BTC/USDT")
        min_spread_percent: Minimum spread percentage to consider (default: 0.5)
        exchanges: List of exchange IDs to monitor
        trading_fees: Trading fee percentage per exchange
        withdrawal_fees: Withdrawal fees per asset per exchange
        slippage_percent: Expected slippage percentage (default: 0.1)
        min_profit_usd: Minimum profit in USD to report (default: 10.0)
        simulate: Use simulated data instead of real APIs (default: True)
        simulate_volatility: Price variance between exchanges in sim mode (default: 0.02)
        api_keys: API credentials for real exchange access
    """
    pairs: List[str] = field(default_factory=list)
    min_spread_percent: float = 0.5
    exchanges: List[str] = field(default_factory=lambda: ["binance", "coinbase", "kraken"])
    trading_fees: Dict[str, float] = field(default_factory=lambda: {
        "binance": 0.001,
        "coinbase": 0.005,
        "kraken": 0.0026,
        "bitstamp": 0.005,
        "gemini": 0.0025
    })
    withdrawal_fees: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "binance": {"BTC": 0.0005, "ETH": 0.005, "USDT": 1.0},
        "coinbase": {"BTC": 0.0001, "ETH": 0.001, "USDT": 0.0},
        "kraken": {"BTC": 0.0002, "ETH": 0.002, "USDT": 2.5}
    })
    slippage_percent: float = 0.1
    min_profit_usd: float = 10.0
    simulate: bool = True
    simulate_volatility: float = 0.02
    api_keys: Dict[str, Dict[str, str]] = field(default_factory=dict)


class ArbitrageDetector:
    """Main arbitrage detection engine.
    
    Detects simple arbitrage (buy low on one exchange, sell high on another)
    and triangular arbitrage (exploiting price discrepancies between three pairs).
    """
    
    # Base prices for simulation mode
    SIMULATION_BASE_PRICES = {
        "BTC/USDT": 50000.0,
        "ETH/USDT": 3000.0,
        "ETH/BTC": 0.06,
        "SOL/USDT": 100.0,
        "SOL/BTC": 0.002,
        "SOL/ETH": 0.033,
        "ADA/USDT": 0.5,
        "ADA/BTC": 0.00001,
        "XRP/USDT": 0.6,
        "XRP/BTC": 0.000012,
        "DOT/USDT": 7.0,
        "LINK/USDT": 15.0,
        "MATIC/USDT": 0.8,
        "AVAX/USDT": 35.0
    }
    
    def __init__(self, config: ArbitrageConfig):
        """Initialize the arbitrage detector.
        
        Args:
            config: ArbitrageConfig instance with detection parameters
        """
        self.config = config
        self.price_cache: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.last_update: Optional[datetime] = None
        
    def fetch_prices_multi_exchange(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Fetch current prices from all configured exchanges.
        
        In simulation mode, generates realistic synthetic price data.
        In real mode, would connect to exchange APIs.
        
        Returns:
            Nested dictionary: {pair: {exchange: {bid, ask, last}}}
        """
        if self.config.simulate:
            return self._generate_simulated_prices()
        else:
            return self._fetch_real_prices()
    
    def _generate_simulated_prices(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Generate simulated price data with realistic variance.
        
        Returns:
            Simulated price data for all configured pairs and exchanges
        """
        prices = {}
        volatility = self.config.simulate_volatility
        
        for pair in self.config.pairs:
            base_price = self.SIMULATION_BASE_PRICES.get(pair, 100.0)
            prices[pair] = {}
            
            for exchange in self.config.exchanges:
                # Add random variance to create arbitrage opportunities
                variance = random.uniform(-volatility, volatility)
                
                # Some exchanges tend to have higher/lower prices
                exchange_bias = {
                    "binance": 0.0,
                    "coinbase": 0.0005,
                    "kraken": -0.0003,
                    "bitstamp": 0.0002,
                    "gemini": 0.0004
                }.get(exchange, 0.0)
                
                adjusted_price = base_price * (1 + variance + exchange_bias)
                
                # Create bid-ask spread (typically 0.01% to 0.1%)
                spread = base_price * random.uniform(0.0001, 0.001)
                
                prices[pair][exchange] = {
                    "bid": round(adjusted_price - spread / 2, 8),
                    "ask": round(adjusted_price + spread / 2, 8),
                    "last": round(adjusted_price, 8)
                }
        
        self.price_cache = prices
        self.last_update = datetime.now(timezone.utc)
        return prices
    
    def _fetch_real_prices(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Fetch real prices from exchange APIs.
        
        Note: This is a placeholder. Real implementation would use
        exchange-specific APIs like ccxt or direct REST calls.
        
        Returns:
            Real price data from exchanges
        """
        # Placeholder for real API integration
        # In production, use libraries like ccxt:
        # import ccxt
        # exchange = ccxt.binance({'apiKey': '...', 'secret': '...'})
        # ticker = exchange.fetch_ticker('BTC/USDT')
        
        raise NotImplementedError(
            "Real price fetching not implemented. Use simulate=True for testing."
        )
    
    def find_opportunities(self) -> List[Dict[str, Any]]:
        """Find all arbitrage opportunities across exchanges.
        
        Scans all configured pairs and exchanges for simple arbitrage
        opportunities where buy price < sell price with sufficient spread.
        
        Returns:
            List of opportunity dictionaries with profit calculations
        """
        prices = self.fetch_prices_multi_exchange()
        opportunities = []
        
        for pair in self.config.pairs:
            if pair not in prices:
                continue
                
            pair_prices = prices[pair]
            
            # Compare all exchange combinations
            for buy_exchange in self.config.exchanges:
                for sell_exchange in self.config.exchanges:
                    if buy_exchange == sell_exchange:
                        continue
                    
                    if buy_exchange not in pair_prices or sell_exchange not in pair_prices:
                        continue
                    
                    buy_price = pair_prices[buy_exchange]["ask"]  # Buy at ask
                    sell_price = pair_prices[sell_exchange]["bid"]  # Sell at bid
                    
                    # Calculate raw spread
                    if buy_price <= 0:
                        continue
                        
                    spread_percent = ((sell_price - buy_price) / buy_price) * 100
                    
                    # Check minimum spread threshold
                    if spread_percent < self.config.min_spread_percent:
                        continue
                    
                    # Calculate profit with fees
                    profit_calc = self.calculate_profit(
                        buy_price=buy_price,
                        sell_price=sell_price,
                        volume=1.0,  # Normalized to 1 unit for comparison
                        buy_exchange=buy_exchange,
                        sell_exchange=sell_exchange
                    )
                    
                    if profit_calc["is_profitable"] and profit_calc["net_profit_usd"] >= self.config.min_profit_usd:
                        opportunity = {
                            "type": "simple",
                            "pair": pair,
                            "buy_exchange": buy_exchange,
                            "sell_exchange": sell_exchange,
                            "buy_price": buy_price,
                            "sell_price": sell_price,
                            "spread_percent": round(spread_percent, 4),
                            "profit_percent": round(profit_calc["net_profit_percent"], 4),
                            "profit_usd": round(profit_calc["net_profit_usd"], 2),
                            "volume": 1.0,
                            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                            "details": profit_calc
                        }
                        opportunities.append(opportunity)
        
        # Sort by profit potential
        opportunities.sort(key=lambda x: x["profit_usd"], reverse=True)
        return opportunities
    
    def calculate_profit(
        self,
        buy_price: float,
        sell_price: float,
        volume: float,
        buy_exchange: str,
        sell_exchange: str,
        include_withdrawal: bool = True
    ) -> Dict[str, Any]:
        """Calculate net profit after all fees and slippage.
        
        Args:
            buy_price: Price to buy at
            sell_price: Price to sell at
            volume: Trading volume in base asset units
            buy_exchange: Exchange to buy on
            sell_exchange: Exchange to sell on
            include_withdrawal: Include withdrawal fees in calculation
            
        Returns:
            Dictionary with detailed profit breakdown
        """
        # Gross profit calculation
        buy_cost = buy_price * volume
        sell_revenue = sell_price * volume
        gross_profit = sell_revenue - buy_cost
        gross_profit_percent = (gross_profit / buy_cost) * 100 if buy_cost > 0 else 0
        
        # Trading fees
        buy_fee_rate = self.config.trading_fees.get(buy_exchange, 0.001)
        sell_fee_rate = self.config.trading_fees.get(sell_exchange, 0.001)
        
        buy_fee = buy_cost * buy_fee_rate
        sell_fee = sell_revenue * sell_fee_rate
        total_trading_fees = buy_fee + sell_fee
        
        # Slippage estimation
        slippage_cost = buy_cost * (self.config.slippage_percent / 100)
        
        # Withdrawal fees (if different exchanges)
        withdrawal_fees = 0.0
        if include_withdrawal and buy_exchange != sell_exchange:
            # Estimate withdrawal fee in USD (simplified)
            withdrawal_fees = buy_cost * 0.0001  # 0.01% estimated
        
        # Net profit
        total_costs = total_trading_fees + slippage_cost + withdrawal_fees
        net_profit = gross_profit - total_costs
        net_profit_percent = (net_profit / buy_cost) * 100 if buy_cost > 0 else 0
        
        return {
            "buy_cost": round(buy_cost, 2),
            "sell_revenue": round(sell_revenue, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_profit_percent": round(gross_profit_percent, 4),
            "buy_fee": round(buy_fee, 2),
            "sell_fee": round(sell_fee, 2),
            "total_trading_fees": round(total_trading_fees, 2),
            "slippage_cost": round(slippage_cost, 2),
            "withdrawal_fees": round(withdrawal_fees, 2),
            "total_costs": round(total_costs, 2),
            "net_profit": round(net_profit, 2),
            "net_profit_usd": round(net_profit, 2),
            "net_profit_percent": round(net_profit_percent, 4),
            "is_profitable": net_profit > 0
        }
    
    def find_triangular_opportunities(self, base_asset: str = "USDT") -> List[Dict[str, Any]]:
        """Find triangular arbitrage opportunities.
        
        Triangular arbitrage involves three trades:
        Base → Asset A → Asset B → Base
        
        Example: USDT → BTC → ETH → USDT
        
        Args:
            base_asset: The base currency to start and end with
            
        Returns:
            List of triangular arbitrage opportunities
        """
        prices = self.fetch_prices_multi_exchange()
        opportunities = []
        
        # Find pairs involving base asset
        base_pairs = [p for p in self.config.pairs if p.endswith(f"/{base_asset}")]
        
        for pair_a in base_pairs:
            asset_a = pair_a.split("/")[0]  # e.g., BTC from BTC/USDT
            
            # Find pairs connecting asset_a to other assets
            for pair_b in self.config.pairs:
                if pair_b == pair_a:
                    continue
                    
                parts_b = pair_b.split("/")
                
                # Check if pair_b involves asset_a
                if asset_a not in parts_b:
                    continue
                
                # Determine asset_b
                if parts_b[0] == asset_a:
                    asset_b = parts_b[1]
                    pair_b_direction = "forward"  # asset_a/asset_b
                else:
                    asset_b = parts_b[0]
                    pair_b_direction = "reverse"  # asset_b/asset_a
                
                # Find pair_c connecting asset_b back to base
                pair_c_forward = f"{asset_b}/{base_asset}"
                pair_c_reverse = f"{base_asset}/{asset_b}"
                
                pair_c = None
                pair_c_direction = None
                if pair_c_forward in self.config.pairs:
                    pair_c = pair_c_forward
                    pair_c_direction = "forward"
                elif pair_c_reverse in self.config.pairs:
                    pair_c = pair_c_reverse
                    pair_c_direction = "reverse"
                
                if not pair_c:
                    continue
                
                # Calculate triangular arbitrage on each exchange
                for exchange in self.config.exchanges:
                    if exchange not in prices.get(pair_a, {}):
                        continue
                    if exchange not in prices.get(pair_b, {}):
                        continue
                    if exchange not in prices.get(pair_c, {}):
                        continue
                    
                    opportunity = self._calculate_triangular_profit(
                        exchange=exchange,
                        pair_a=pair_a,
                        pair_b=pair_b,
                        pair_c=pair_c,
                        pair_b_direction=pair_b_direction,
                        pair_c_direction=pair_c_direction,
                        base_asset=base_asset,
                        asset_a=asset_a,
                        asset_b=asset_b,
                        prices=prices
                    )
                    
                    if opportunity and opportunity["net_profit_percent"] > self.config.min_spread_percent:
                        opportunities.append(opportunity)
        
        # Sort by profit
        opportunities.sort(key=lambda x: x["net_profit_percent"], reverse=True)
        return opportunities
    
    def _calculate_triangular_profit(
        self,
        exchange: str,
        pair_a: str,
        pair_b: str,
        pair_c: str,
        pair_b_direction: str,
        pair_c_direction: str,
        base_asset: str,
        asset_a: str,
        asset_b: str,
        prices: Dict
    ) -> Optional[Dict[str, Any]]:
        """Calculate profit for a specific triangular arbitrage path.
        
        Args:
            exchange: Exchange to execute on
            pair_a, pair_b, pair_c: The three trading pairs
            pair_b_direction, pair_c_direction: Direction of trades
            base_asset, asset_a, asset_b: Assets involved
            prices: Current price data
            
        Returns:
            Opportunity dictionary or None if not profitable
        """
        start_amount = 1000.0  # Start with 1000 units of base asset
        
        # Step 1: Base → Asset A
        price_a = prices[pair_a][exchange]["ask"]  # Buy asset_a
        amount_a = start_amount / price_a
        fee_a = start_amount * self.config.trading_fees.get(exchange, 0.001)
        amount_a_after_fee = (start_amount - fee_a) / price_a
        
        # Step 2: Asset A → Asset B
        if pair_b_direction == "forward":
            # Selling asset_a for asset_b
            price_b = prices[pair_b][exchange]["bid"]
            amount_b = amount_a_after_fee * price_b
        else:
            # Buying asset_a with asset_b (selling asset_b)
            price_b = prices[pair_b][exchange]["ask"]
            amount_b = amount_a_after_fee / price_b
        
        fee_b = amount_a_after_fee * self.config.trading_fees.get(exchange, 0.001) * price_a
        amount_b_after_fee = amount_b - (fee_b / price_a if price_a > 0 else 0)
        
        # Step 3: Asset B → Base
        if pair_c_direction == "forward":
            # Selling asset_b for base
            price_c = prices[pair_c][exchange]["bid"]
            final_amount = amount_b_after_fee * price_c
        else:
            # Buying asset_b with base (selling base)
            price_c = prices[pair_c][exchange]["ask"]
            final_amount = amount_b_after_fee / price_c
        
        fee_c = amount_b_after_fee * self.config.trading_fees.get(exchange, 0.001) * (
            price_b if pair_b_direction == "forward" else 1/price_b
        )
        final_amount_after_fee = final_amount - fee_c
        
        # Calculate profit
        net_profit = final_amount_after_fee - start_amount
        net_profit_percent = (net_profit / start_amount) * 100
        
        if net_profit_percent < self.config.min_spread_percent:
            return None
        
        return {
            "type": "triangular",
            "exchange": exchange,
            "path": f"{base_asset} → {asset_a} → {asset_b} → {base_asset}",
            "pairs": [pair_a, pair_b, pair_c],
            "start_amount": start_amount,
            "final_amount": round(final_amount_after_fee, 2),
            "net_profit": round(net_profit, 2),
            "net_profit_usd": round(net_profit, 2),
            "net_profit_percent": round(net_profit_percent, 4),
            "is_profitable": net_profit > 0,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "steps": [
                {"step": 1, "pair": pair_a, "action": "buy", "amount": round(amount_a_after_fee, 8)},
                {"step": 2, "pair": pair_b, "action": "sell" if pair_b_direction == "forward" else "buy", "amount": round(amount_b_after_fee, 8)},
                {"step": 3, "pair": pair_c, "action": "sell" if pair_c_direction == "forward" else "buy", "amount": round(final_amount_after_fee, 2)}
            ]
        }
    
    def print_price_table(self, prices: Optional[Dict] = None) -> None:
        """Print a formatted price table for all exchanges.
        
        Args:
            prices: Price data (fetches new data if None)
        """
        if prices is None:
            prices = self.fetch_prices_multi_exchange()
        
        print("\n" + "=" * 80)
        print(f"{'PAIR':<15} {'EXCHANGE':<12} {'BID':>15} {'ASK':>15} {'SPREAD %':>12}")
        print("=" * 80)
        
        for pair in sorted(prices.keys()):
            for exchange in sorted(prices[pair].keys()):
                data = prices[pair][exchange]
                bid = data["bid"]
                ask = data["ask"]
                spread_pct = ((ask - bid) / bid) * 100 if bid > 0 else 0
                print(f"{pair:<15} {exchange:<12} {bid:>15.8f} {ask:>15.8f} {spread_pct:>11.4f}%")
        
        print("=" * 80)
    
    def get_best_prices(self, pair: str) -> Dict[str, Any]:
        """Get the best bid and ask prices across all exchanges for a pair.
        
        Args:
            pair: Trading pair (e.g., "BTC/USDT")
            
        Returns:
            Dictionary with best bid and ask information
        """
        prices = self.fetch_prices_multi_exchange()
        
        if pair not in prices:
            return {"error": f"Pair {pair} not found"}
        
        best_bid = 0.0
        best_bid_exchange = ""
        best_ask = float("inf")
        best_ask_exchange = ""
        
        for exchange, data in prices[pair].items():
            if data["bid"] > best_bid:
                best_bid = data["bid"]
                best_bid_exchange = exchange
            if data["ask"] < best_ask:
                best_ask = data["ask"]
                best_ask_exchange = exchange
        
        spread = best_bid - best_ask
        spread_percent = (spread / best_ask) * 100 if best_ask > 0 else 0
        
        return {
            "pair": pair,
            "best_bid": best_bid,
            "best_bid_exchange": best_bid_exchange,
            "best_ask": best_ask,
            "best_ask_exchange": best_ask_exchange,
            "spread": spread,
            "spread_percent": round(spread_percent, 4)
        }


def main():
    """Example usage of the arbitrage detector."""
    # Configure detector
    config = ArbitrageConfig(
        pairs=["BTC/USDT", "ETH/USDT", "ETH/BTC"],
        min_spread_percent=0.1,
        exchanges=["binance", "coinbase", "kraken"],
        simulate=True,
        simulate_volatility=0.015
    )
    
    # Initialize
    detector = ArbitrageDetector(config)
    
    # Print price table
    detector.print_price_table()
    
    # Find simple arbitrage opportunities
    print("\n--- Simple Arbitrage Opportunities ---")
    opportunities = detector.find_opportunities()
    
    if opportunities:
        for opp in opportunities:
            print(f"\n{opp['pair']}: {opp['buy_exchange']} → {opp['sell_exchange']}")
            print(f"  Spread: {opp['spread_percent']:.4f}%")
            print(f"  Net Profit: ${opp['profit_usd']:.2f} ({opp['profit_percent']:.4f}%)")
    else:
        print("No profitable opportunities found.")
    
    # Find triangular arbitrage
    print("\n--- Triangular Arbitrage Opportunities ---")
    tri_opps = detector.find_triangular_opportunities(base_asset="USDT")
    
    if tri_opps:
        for opp in tri_opps[:5]:  # Show top 5
            print(f"\n{opp['exchange']}: {opp['path']}")
            print(f"  Profit: ${opp['net_profit']:.2f} ({opp['net_profit_percent']:.4f}%)")
    else:
        print("No triangular opportunities found.")
    
    # Get best prices for BTC
    print("\n--- Best BTC/USDT Prices ---")
    best = detector.get_best_prices("BTC/USDT")
    print(f"Best Bid:  ${best['best_bid']:.2f} on {best['best_bid_exchange']}")
    print(f"Best Ask:  ${best['best_ask']:.2f} on {best['best_ask_exchange']}")
    print(f"Spread:    {best['spread_percent']:.4f}%")


if __name__ == "__main__":
    main()
