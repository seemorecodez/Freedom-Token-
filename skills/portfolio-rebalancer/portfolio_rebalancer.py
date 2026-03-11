#!/usr/bin/env python3
"""
Portfolio Rebalancer - Automatically rebalance portfolios based on target allocations.

This module provides intelligent portfolio rebalancing with:
- Drift detection and threshold monitoring
- Tax-aware rebalancing strategies
- Multiple rebalancing approaches (threshold, periodic, cash-flow)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Literal
from datetime import datetime, timedelta
from enum import Enum
import json
import argparse


class RebalanceStrategy(Enum):
    """Rebalancing strategy types."""
    THRESHOLD = "threshold"
    PERIODIC = "periodic"
    CASH_FLOW = "cash_flow"


@dataclass
class RebalanceConfig:
    """Configuration for portfolio rebalancing.
    
    Attributes:
        targets: Asset symbol -> target allocation (0.0-1.0, should sum to 1.0)
        drift_threshold: Maximum allowed drift before triggering rebalance (default 5%)
        strategy: Rebalancing strategy to use
        period_days: Days between periodic rebalances (for PERIODIC strategy)
        tax_sensitive: Whether to consider tax implications
        min_trade_value: Minimum dollar value for a trade to execute
        max_turnover: Maximum annual turnover allowed (0.0-1.0)
        cash_buffer: Minimum cash to maintain (as fraction of portfolio)
    """
    targets: Dict[str, float]
    drift_threshold: float = 0.05
    strategy: RebalanceStrategy = RebalanceStrategy.THRESHOLD
    period_days: int = 90
    tax_sensitive: bool = True
    min_trade_value: float = 100.0
    max_turnover: float = 0.50
    cash_buffer: float = 0.0
    
    def __post_init__(self):
        """Validate configuration."""
        total = sum(self.targets.values())
        if not 0.99 <= total <= 1.01:
            raise ValueError(f"Target allocations must sum to 1.0, got {total}")
        if any(t < 0 for t in self.targets.values()):
            raise ValueError("Target allocations must be non-negative")


@dataclass
class TaxLot:
    """Represents a single tax lot of an asset.
    
    Attributes:
        shares: Number of shares
        cost_basis: Cost per share
        date_acquired: Date shares were purchased
        account: Account identifier
    """
    shares: float
    cost_basis: float
    date_acquired: datetime
    account: str
    
    @property
    def value(self) -> float:
        """Calculate current value at given price."""
        return self.shares * self.cost_basis
    
    def unrealized_gain(self, current_price: float) -> float:
        """Calculate unrealized gain/loss."""
        return self.shares * (current_price - self.cost_basis)
    
    def is_long_term(self, as_of: Optional[datetime] = None) -> bool:
        """Check if holding qualifies for long-term capital gains."""
        if as_of is None:
            as_of = datetime.now()
        return (as_of - self.date_acquired).days >= 365


def calculate_current_allocations(
    portfolio: Dict[str, Dict],
    include_cash: bool = False,
    cash_value: float = 0.0
) -> Dict[str, float]:
    """Calculate current allocation percentages from portfolio holdings.
    
    Args:
        portfolio: Dict mapping asset symbol to holding info with 'shares' and 'price'
        include_cash: Whether to include cash in allocation calculation
        cash_value: Current cash value if included
        
    Returns:
        Dict mapping asset symbol to allocation percentage (0.0-1.0)
        
    Example:
        >>> portfolio = {
        ...     "VTI": {"shares": 100, "price": 220.50},
        ...     "BND": {"shares": 50, "price": 85.00}
        ... }
        >>> calculate_current_allocations(portfolio)
        {'VTI': 0.838, 'BND': 0.162}
    """
    values = {}
    total_value = cash_value if include_cash else 0.0
    
    for symbol, holding in portfolio.items():
        value = holding.get("shares", 0) * holding.get("price", 0)
        values[symbol] = value
        total_value += value
    
    if include_cash and cash_value > 0:
        values["CASH"] = cash_value
    
    if total_value == 0:
        return {symbol: 0.0 for symbol in portfolio}
    
    return {symbol: value / total_value for symbol, value in values.items()}


def calculate_rebalance_trades(
    portfolio: Dict[str, Dict],
    config: RebalanceConfig,
    cash_available: float = 0.0
) -> List[Dict]:
    """Calculate trades needed to rebalance portfolio to target allocations.
    
    Args:
        portfolio: Current portfolio holdings
        config: Rebalancing configuration with targets
        cash_available: Additional cash available for investment
        
    Returns:
        List of trade dictionaries with keys:
        - asset: Symbol to trade
        - action: "buy" or "sell"
        - shares: Number of shares to trade
        - value: Dollar value of trade
        - current_price: Price per share
    """
    # Calculate total portfolio value
    total_value = cash_available
    for holding in portfolio.values():
        total_value += holding.get("shares", 0) * holding.get("price", 0)
    
    if total_value == 0:
        return []
    
    # Calculate target values and required trades
    trades = []
    
    for symbol, target_alloc in config.targets.items():
        target_value = total_value * target_alloc
        
        if symbol in portfolio:
            current_shares = portfolio[symbol].get("shares", 0)
            current_price = portfolio[symbol].get("price", 0)
            current_value = current_shares * current_price
        else:
            current_shares = 0
            current_price = 0
            current_value = 0
        
        value_diff = target_value - current_value
        
        # Skip trades below minimum
        if abs(value_diff) < config.min_trade_value:
            continue
        
        if current_price > 0:
            shares_diff = value_diff / current_price
            
            if abs(shares_diff) >= 0.001:  # Minimum 0.001 shares
                action = "buy" if shares_diff > 0 else "sell"
                trades.append({
                    "asset": symbol,
                    "action": action,
                    "shares": abs(shares_diff),
                    "value": abs(value_diff),
                    "current_price": current_price
                })
    
    return trades


def drift_threshold_check(
    portfolio: Dict[str, Dict],
    config: RebalanceConfig,
    include_cash: bool = False,
    cash_value: float = 0.0
) -> Tuple[bool, Dict[str, float]]:
    """Check if portfolio drift exceeds threshold, triggering rebalance need.
    
    Args:
        portfolio: Current portfolio holdings
        config: Rebalancing configuration
        include_cash: Whether cash is included in drift calculation
        cash_value: Current cash value
        
    Returns:
        Tuple of (needs_rebalance: bool, drifts: Dict[symbol, drift_amount])
        
    Example:
        >>> config = RebalanceConfig(targets={"VTI": 0.60, "BND": 0.40}, drift_threshold=0.05)
        >>> portfolio = {"VTI": {"shares": 100, "price": 200}, "BND": {"shares": 50, "price": 100}}
        >>> needs_rebal, drifts = drift_threshold_check(portfolio, config)
        >>> print(f"Needs rebalance: {needs_rebal}, Drifts: {drifts}")
    """
    current_allocations = calculate_current_allocations(portfolio, include_cash, cash_value)
    drifts = {}
    max_drift = 0.0
    
    # Check drift for all target assets
    for symbol, target_alloc in config.targets.items():
        current_alloc = current_allocations.get(symbol, 0.0)
        drift = abs(current_alloc - target_alloc)
        drifts[symbol] = drift
        max_drift = max(max_drift, drift)
    
    # Also check for assets not in targets (drifted to 0)
    for symbol, current_alloc in current_allocations.items():
        if symbol not in config.targets and symbol != "CASH":
            drifts[symbol] = current_alloc  # Full allocation is drift from 0
            max_drift = max(max_drift, current_alloc)
    
    needs_rebalance = max_drift > config.drift_threshold
    return needs_rebalance, drifts


def tax_aware_rebalancing(
    portfolio: Dict[str, Dict],
    config: RebalanceConfig,
    tax_lots: Dict[str, List[TaxLot]],
    account_types: Dict[str, Literal["taxable", "tax_deferred", "tax_free"]],
    current_prices: Optional[Dict[str, float]] = None
) -> Dict:
    """Generate tax-optimized rebalancing plan.
    
    Prioritizes:
    1. Selling losses first (tax loss harvesting)
    2. Long-term gains over short-term
    3. Tax-advantaged accounts before taxable
    4. Using new contributions for underweight assets
    
    Args:
        portfolio: Current portfolio holdings
        config: Rebalancing configuration
        tax_lots: Asset symbol -> list of tax lots
        account_types: Account name -> account type classification
        current_prices: Optional current prices (uses portfolio prices if not provided)
        
    Returns:
        Dict with:
        - trades: List of recommended trades
        - tax_impact: Estimated tax impact
        - priority: Tax priority ranking for each trade
        - harvest_opportunities: List of tax loss harvesting opportunities
    """
    if current_prices is None:
        current_prices = {s: h.get("price", 0) for s, h in portfolio.items()}
    
    trades = []
    harvest_opportunities = []
    total_tax_impact = 0.0
    
    # First pass: identify tax loss harvesting opportunities
    for symbol, lots in tax_lots.items():
        if symbol not in current_prices:
            continue
        price = current_prices[symbol]
        
        for lot in lots:
            unrealized = lot.unrealized_gain(price)
            account_type = account_types.get(lot.account, "taxable")
            
            if account_type == "taxable" and unrealized < 0:
                harvest_opportunities.append({
                    "symbol": symbol,
                    "shares": lot.shares,
                    "loss": abs(unrealized),
                    "lot": lot
                })
    
    # Sort harvest opportunities by loss amount (largest first)
    harvest_opportunities.sort(key=lambda x: x["loss"], reverse=True)
    
    # Calculate needed trades
    needed_trades = calculate_rebalance_trades(portfolio, config)
    
    # Prioritize trades by tax efficiency
    for trade in needed_trades:
        symbol = trade["asset"]
        action = trade["action"]
        
        if action == "sell" and symbol in tax_lots:
            # Sort lots for optimal tax efficiency
            lots = tax_lots[symbol]
            price = current_prices.get(symbol, 0)
            
            # Prioritize: losses > long-term gains > short-term gains
            # Within each category, prioritize tax-advantaged accounts
            def lot_priority(lot: TaxLot) -> tuple:
                unrealized = lot.unrealized_gain(price)
                account_type = account_types.get(lot.account, "taxable")
                is_tax_adv = account_type in ("tax_deferred", "tax_free")
                is_long_term = lot.is_long_term()
                
                if unrealized < 0:
                    return (0, not is_tax_adv, 0)  # Losses first
                elif is_long_term:
                    return (1, not is_tax_adv, 0)  # Then long-term gains
                else:
                    return (2, not is_tax_adv, 0)  # Short-term gains last
            
            sorted_lots = sorted(lots, key=lot_priority)
            
            # Build trade with lot selection
            remaining_shares = trade["shares"]
            lot_selections = []
            
            for lot in sorted_lots:
                if remaining_shares <= 0:
                    break
                
                shares_to_sell = min(remaining_shares, lot.shares)
                unrealized = lot.unrealized_gain(price) * (shares_to_sell / lot.shares)
                
                lot_selections.append({
                    "shares": shares_to_sell,
                    "account": lot.account,
                    "cost_basis": lot.cost_basis,
                    "unrealized_gain": unrealized,
                    "is_long_term": lot.is_long_term()
                })
                
                total_tax_impact += max(0, unrealized)  # Only count gains as tax liability
                remaining_shares -= shares_to_sell
            
            trade["lot_selections"] = lot_selections
            trade["tax_priority"] = "high" if lot_selections and lot_selections[0].get("unrealized_gain", 0) < 0 else "medium"
        else:
            trade["tax_priority"] = "neutral"  # Buys don't have immediate tax impact
        
        trades.append(trade)
    
    return {
        "trades": trades,
        "tax_impact": total_tax_impact,
        "harvest_opportunities": harvest_opportunities,
        "strategy": "tax_optimized"
    }


def check_periodic_rebalance(
    last_rebalance_date: Optional[datetime],
    config: RebalanceConfig,
    current_date: Optional[datetime] = None
) -> bool:
    """Check if periodic rebalancing is due.
    
    Args:
        last_rebalance_date: Date of last rebalance (None if never)
        config: Rebalancing configuration
        current_date: Date to check (defaults to now)
        
    Returns:
        True if rebalancing is due based on schedule
    """
    if config.strategy != RebalanceStrategy.PERIODIC:
        return False
    
    if current_date is None:
        current_date = datetime.now()
    
    if last_rebalance_date is None:
        return True
    
    days_since = (current_date - last_rebalance_date).days
    return days_since >= config.period_days


def cash_flow_rebalancing(
    portfolio: Dict[str, Dict],
    config: RebalanceConfig,
    cash_flow: float,  # Positive for contribution, negative for withdrawal
    current_prices: Optional[Dict[str, float]] = None
) -> List[Dict]:
    """Rebalance using only cash flows without selling existing positions.
    
    This strategy is ideal for:
    - Tax-sensitive taxable accounts
    - Accumulation phase with regular contributions
    - Avoiding capital gains taxes
    
    Args:
        portfolio: Current portfolio holdings
        config: Rebalancing configuration
        cash_flow: New cash to invest (positive) or withdraw (negative)
        current_prices: Current asset prices
        
    Returns:
        List of trades using cash flow only
    """
    if cash_flow == 0:
        return []
    
    if current_prices is None:
        current_prices = {s: h.get("price", 0) for s, h in portfolio.items()}
    
    # Calculate current allocations
    current_allocations = calculate_current_allocations(portfolio)
    total_value = sum(h.get("shares", 0) * h.get("price", 0) for h in portfolio.values())
    new_total = total_value + cash_flow
    
    trades = []
    
    if cash_flow > 0:
        # Contribution: buy underweight assets
        for symbol, target_alloc in config.targets.items():
            current_alloc = current_allocations.get(symbol, 0.0)
            target_value = new_total * target_alloc
            
            if symbol in portfolio:
                current_value = portfolio[symbol].get("shares", 0) * portfolio[symbol].get("price", 0)
            else:
                current_value = 0
            
            value_to_add = target_value - current_value
            
            if value_to_add > 0 and symbol in current_prices and current_prices[symbol] > 0:
                shares_to_buy = value_to_add / current_prices[symbol]
                if shares_to_buy >= 0.001:
                    trades.append({
                        "asset": symbol,
                        "action": "buy",
                        "shares": shares_to_buy,
                        "value": value_to_add,
                        "current_price": current_prices[symbol],
                        "method": "cash_flow"
                    })
    else:
        # Withdrawal: sell overweight assets first
        withdrawal_needed = abs(cash_flow)
        
        # Sort by most overweight
        overweights = []
        for symbol, target_alloc in config.targets.items():
            current_alloc = current_allocations.get(symbol, 0.0)
            overweight = current_alloc - target_alloc
            if overweight > 0:
                overweights.append((symbol, overweight))
        
        overweights.sort(key=lambda x: x[1], reverse=True)
        
        for symbol, _ in overweights:
            if withdrawal_needed <= 0:
                break
            
            if symbol not in portfolio or symbol not in current_prices:
                continue
            
            price = current_prices[symbol]
            available_shares = portfolio[symbol].get("shares", 0)
            available_value = available_shares * price
            
            sell_value = min(available_value, withdrawal_needed)
            sell_shares = sell_value / price
            
            if sell_shares >= 0.001:
                trades.append({
                    "asset": symbol,
                    "action": "sell",
                    "shares": sell_shares,
                    "value": sell_value,
                    "current_price": price,
                    "method": "cash_flow"
                })
                withdrawal_needed -= sell_value
    
    return trades


def generate_rebalance_report(
    portfolio: Dict[str, Dict],
    config: RebalanceConfig,
    trades: List[Dict],
    drifts: Dict[str, float],
    tax_info: Optional[Dict] = None
) -> str:
    """Generate a human-readable rebalancing report.
    
    Args:
        portfolio: Current portfolio
        config: Rebalancing configuration
        trades: Recommended trades
        drifts: Current drift amounts
        tax_info: Optional tax impact information
        
    Returns:
        Formatted report string
    """
    lines = []
    lines.append("=" * 60)
    lines.append("PORTFOLIO REBALANCING REPORT")
    lines.append("=" * 60)
    
    # Current allocations
    current_allocs = calculate_current_allocations(portfolio)
    lines.append("\n📊 CURRENT ALLOCATIONS:")
    lines.append(f"{'Asset':<10} {'Current':>10} {'Target':>10} {'Drift':>10}")
    lines.append("-" * 42)
    
    all_symbols = set(current_allocs.keys()) | set(config.targets.keys())
    for symbol in sorted(all_symbols):
        current = current_allocs.get(symbol, 0.0)
        target = config.targets.get(symbol, 0.0)
        drift = drifts.get(symbol, current)
        lines.append(f"{symbol:<10} {current:>9.2%} {target:>9.2%} {drift:>+9.2%}")
    
    # Trades
    lines.append("\n🔄 RECOMMENDED TRADES:")
    if trades:
        lines.append(f"{'Action':<8} {'Asset':<10} {'Shares':>12} {'Value':>15}")
        lines.append("-" * 47)
        total_value = 0.0
        for trade in trades:
            lines.append(f"{trade['action'].upper():<8} {trade['asset']:<10} {trade['shares']:>12.2f} ${trade['value']:>14,.2f}")
            total_value += trade['value']
        lines.append("-" * 47)
        lines.append(f"{'TOTAL':<20} {len(trades):>12} ${total_value:>14,.2f}")
    else:
        lines.append("No trades needed - portfolio is within target allocations.")
    
    # Tax info
    if tax_info:
        lines.append("\n💰 TAX IMPACT:")
        lines.append(f"Estimated tax liability: ${tax_info.get('tax_impact', 0):,.2f}")
        harvest = tax_info.get('harvest_opportunities', [])
        if harvest:
            lines.append(f"\nTax loss harvesting opportunities: {len(harvest)}")
            total_harvest = sum(h['loss'] for h in harvest)
            lines.append(f"Total harvestable losses: ${total_harvest:,.2f}")
    
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def main():
    """CLI entry point for portfolio rebalancer."""
    parser = argparse.ArgumentParser(description="Portfolio Rebalancer")
    parser.add_argument("--portfolio", "-p", help="Portfolio JSON file path")
    parser.add_argument("--config", "-c", help="Config JSON file path")
    parser.add_argument("--check", action="store_true", help="Check if rebalancing needed")
    parser.add_argument("--plan", action="store_true", help="Generate rebalancing plan")
    parser.add_argument("--tax-aware", action="store_true", help="Enable tax-aware rebalancing")
    parser.add_argument("--output", "-o", help="Output file for report")
    
    args = parser.parse_args()
    
    # Example/demo if no files provided
    if not args.portfolio:
        print("Demo mode - using example portfolio\n")
        portfolio = {
            "VTI": {"shares": 100, "price": 250.00, "cost_basis": 200.00},
            "VTIAX": {"shares": 200, "price": 35.00, "cost_basis": 30.00},
            "BND": {"shares": 30, "price": 80.00, "cost_basis": 82.00}
        }
        config = RebalanceConfig(
            targets={"VTI": 0.60, "VTIAX": 0.30, "BND": 0.10},
            drift_threshold=0.05
        )
    else:
        with open(args.portfolio) as f:
            portfolio = json.load(f)
        with open(args.config) as f:
            config_data = json.load(f)
            config = RebalanceConfig(**config_data)
    
    # Run rebalancing logic
    needs_rebal, drifts = drift_threshold_check(portfolio, config)
    
    if args.check:
        print(f"Rebalancing needed: {needs_rebal}")
        print(f"Max drift: {max(drifts.values()):.2%}")
        return
    
    trades = calculate_rebalance_trades(portfolio, config)
    
    tax_info = None
    if args.tax_aware:
        # Demo tax lots
        tax_lots = {
            "VTI": [TaxLot(100, 200.00, datetime(2023, 1, 15), "taxable")],
            "VTIAX": [TaxLot(200, 30.00, datetime(2023, 6, 20), "taxable")],
            "BND": [TaxLot(30, 82.00, datetime(2024, 1, 10), "taxable")]
        }
        account_types = {"taxable": "taxable"}
        tax_info = tax_aware_rebalancing(portfolio, config, tax_lots, account_types)
        trades = tax_info["trades"]
    
    report = generate_rebalance_report(portfolio, config, trades, drifts, tax_info)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report saved to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
