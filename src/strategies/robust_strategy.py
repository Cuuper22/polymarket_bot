"""
Robust Cost-Aware Trading Strategy
==================================
Strategy designed to:
1. Account for all trading costs when calculating edge
2. Avoid overfitting through conservative parameters
3. Adapt to market microstructure conditions
4. Maintain consistent positive expectancy

Target: 10%+ weekly returns with realistic cost modeling
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from enum import Enum
import statistics
import math

logger = logging.getLogger(__name__)


class MarketQuality(Enum):
    """Market quality classification."""
    EXCELLENT = "excellent"  # Trade with full size
    GOOD = "good"           # Trade with reduced size
    MARGINAL = "marginal"   # Trade only with very high edge
    POOR = "poor"           # Do not trade


class SignalStrength(Enum):
    """Signal strength levels."""
    STRONG = "strong"       # Multiple confirming signals
    MODERATE = "moderate"   # Single strong signal
    WEAK = "weak"           # Marginal signal
    NONE = "none"           # No signal


@dataclass
class CostModel:
    """
    Model of all trading costs for edge calculation.
    """
    # Polymarket fees
    profit_fee: float = 0.02  # 2% on profits
    
    # Spread costs (as fraction of position)
    avg_spread_cost: float = 0.01  # 1% average spread
    wide_spread_threshold: float = 0.05  # Spreads above this are "wide"
    
    # Slippage (for $10 average trade in $1000 depth market)
    base_slippage: float = 0.005  # 0.5% base
    
    # Total expected cost per round trip
    @property
    def expected_round_trip_cost(self) -> float:
        """Expected cost for entry + exit."""
        return self.avg_spread_cost + self.base_slippage * 2
    
    @property
    def minimum_edge_for_profit(self) -> float:
        """Minimum edge needed to break even after costs."""
        # Need edge > costs + expected profit fee
        # If we win 55% at 10% edge: 0.55 * 0.10 - 0.45 * 0.10 = 1% raw
        # After 2% fee on profit: 0.55 * 0.10 * 0.98 - 0.45 * 0.10 = 0.89%
        # Plus trading costs ~2-3%
        return self.expected_round_trip_cost + self.profit_fee * 0.5 + 0.02
    
    def adjust_edge_for_costs(self, 
                             raw_edge: float, 
                             spread: float,
                             position_size: float,
                             book_depth: float) -> float:
        """
        Adjust raw edge for expected trading costs.
        
        Returns: net expected edge after costs
        """
        # Spread cost
        spread_cost = spread / 2  # Half spread to cross
        
        # Slippage based on size
        if book_depth > 0:
            slippage = self.base_slippage + (position_size / book_depth) * 0.01
        else:
            slippage = self.base_slippage * 3
        
        # Profit fee (expected)
        expected_win_rate = 0.5 + raw_edge / 2  # Approximate
        expected_fee = self.profit_fee * expected_win_rate * raw_edge
        
        # Net edge
        net_edge = raw_edge - spread_cost - slippage * 2 - expected_fee
        
        return max(0, net_edge)


@dataclass
class RobustStrategyConfig:
    """
    Configuration for robust strategy.
    Designed to be conservative and avoid overfitting.
    """
    # Edge thresholds (HIGHER than naive to account for costs)
    min_raw_edge: float = 0.15           # 15% minimum raw edge
    min_net_edge: float = 0.08           # 8% minimum after costs
    optimal_edge: float = 0.20           # 20% edge for full position
    
    # Confidence thresholds
    min_confidence: float = 0.60         # 60% minimum
    optimal_confidence: float = 0.75     # 75% for full position
    
    # Market quality filters
    max_spread: float = 0.06             # 6% max spread (lower than before)
    min_volume_24h: float = 2000         # $2000 minimum volume
    min_book_depth: float = 500          # $500 minimum depth
    
    # Timing filters
    min_hours_to_resolution: int = 72    # 3+ days to resolution (more conservative)
    max_hours_to_resolution: int = 336   # 2 weeks max (avoid long-dated)
    
    # Position sizing (conservative)
    max_position_pct: float = 0.12       # 12% max (down from 20%)
    base_position_pct: float = 0.08      # 8% base position
    min_position_dollars: float = 3.0    # $3 minimum
    max_position_dollars: float = 20.0   # $20 max per trade
    
    # Portfolio limits
    max_open_positions: int = 4          # Max 4 positions
    max_portfolio_exposure: float = 0.50 # Max 50% deployed
    
    # Signal requirements
    min_signals_for_trade: int = 1       # At least 1 signal
    signals_for_full_size: int = 2       # 2+ signals for full size
    
    # Exit rules
    stop_loss_pct: float = 0.30          # 30% stop loss
    take_profit_pct: float = 0.50        # 50% take profit
    
    # Cost model
    costs: CostModel = field(default_factory=CostModel)


class RobustStrategy:
    """
    Robust cost-aware trading strategy.
    """
    
    def __init__(self, config: Optional[RobustStrategyConfig] = None):
        self.config = config if config is not None else RobustStrategyConfig()
        self.open_positions: Dict[str, Dict] = {}
        self.trade_history: List[Dict] = []
    
    def assess_market_quality(self, market_state: Dict) -> Tuple[MarketQuality, str]:
        """
        Assess market quality for trading.
        
        Returns: (quality, reason)
        """
        spread = market_state.get("spread", 0.05)
        volume = market_state.get("volume_24h", 0)
        depth = market_state.get("bid_depth", 0) + market_state.get("ask_depth", 0)
        hours_left = market_state.get("hours_to_resolution", 168)
        
        issues = []
        
        # Check spread
        if spread > self.config.max_spread:
            issues.append(f"spread {spread:.1%} > {self.config.max_spread:.1%}")
        
        # Check volume
        if volume < self.config.min_volume_24h:
            issues.append(f"volume ${volume:.0f} < ${self.config.min_volume_24h:.0f}")
        
        # Check depth
        if depth < self.config.min_book_depth:
            issues.append(f"depth ${depth:.0f} < ${self.config.min_book_depth:.0f}")
        
        # Check timing
        if hours_left < self.config.min_hours_to_resolution:
            issues.append(f"only {hours_left:.0f}h left")
        elif hours_left > self.config.max_hours_to_resolution:
            issues.append(f"{hours_left:.0f}h too long")
        
        # Classify
        if len(issues) == 0:
            if spread < 0.03 and volume > 5000 and depth > 1000:
                return MarketQuality.EXCELLENT, "All conditions excellent"
            return MarketQuality.GOOD, "Meets all requirements"
        elif len(issues) == 1:
            if "spread" in issues[0] and spread < 0.08:
                return MarketQuality.MARGINAL, issues[0]
            return MarketQuality.POOR, issues[0]
        else:
            return MarketQuality.POOR, "; ".join(issues)
    
    def calculate_signals(self, market_state: Dict) -> Tuple[SignalStrength, List[str], float, float]:
        """
        Calculate trading signals from market state.
        
        Returns: (strength, signal_names, direction_score, confidence)
        """
        signals = []
        direction_scores = []  # Positive = YES, Negative = NO
        signal_weights = []    # Weight for each signal
        
        price = market_state.get("price", 0.5)
        sentiment = market_state.get("sentiment", 0)
        volume = market_state.get("volume_24h", 1000)
        spread = market_state.get("spread", 0.02)
        hours_left = market_state.get("hours_to_resolution", 168)
        
        # Signal 1: Strong sentiment divergence (only very strong signals)
        # Only trust sentiment when it's very strong AND price is extreme
        implied_fv = 0.5 + sentiment * 0.35
        sentiment_edge = implied_fv - price
        
        # Strong bullish case: positive sentiment + low price
        if sentiment > 0.25 and price < 0.40:
            signals.append("bullish_divergence")
            direction_scores.append(0.20)
            signal_weights.append(1.5)
        # Strong bearish case: negative sentiment + high price
        elif sentiment < -0.25 and price > 0.60:
            signals.append("bearish_divergence")
            direction_scores.append(-0.20)
            signal_weights.append(1.5)
        # Moderate divergence only with very strong sentiment
        elif abs(sentiment_edge) > 0.15 and abs(sentiment) > 0.30:
            signals.append("sentiment_divergence")
            direction_scores.append(sentiment_edge * 0.8)
            signal_weights.append(1.0)
        
        # Signal 2: Extreme price levels (contrarian)
        # Very low prices often have upward pressure
        if price < 0.25:
            # Underpriced - buy YES
            signals.append("extreme_low_price")
            direction_scores.append(0.15)
            signal_weights.append(1.2)
        elif price > 0.75:
            # Overpriced - buy NO
            signals.append("extreme_high_price")
            direction_scores.append(-0.15)
            signal_weights.append(1.2)
        
        # Signal 3: Volume + sentiment alignment
        if volume > 5000 and abs(sentiment) > 0.25:
            signals.append("volume_sentiment_aligned")
            direction_scores.append(sentiment * 0.15)
            signal_weights.append(1.3)
        
        # Signal 4: Time value (closer to resolution with clear signals)
        if hours_left < 120 and abs(sentiment) > 0.20:
            # Sentiment more reliable closer to resolution
            signals.append("late_stage_sentiment")
            direction_scores.append(sentiment * 0.12)
            signal_weights.append(1.1)
        
        # Signal 5: Price zone + sentiment confirmation
        # Mid-range prices with strong sentiment
        if 0.35 <= price <= 0.65 and abs(sentiment) > 0.35:
            signals.append("mid_range_momentum")
            direction_scores.append(sentiment * 0.10)
            signal_weights.append(1.0)
        
        # Aggregate with weights
        if not signals:
            return SignalStrength.NONE, [], 0, 0
        
        # Weighted average direction
        total_weight = sum(signal_weights)
        weighted_direction = sum(d * w for d, w in zip(direction_scores, signal_weights)) / total_weight
        
        # Confidence based on signal count and agreement
        same_direction = all(s * weighted_direction > 0 for s in direction_scores if s != 0)
        
        # Base confidence
        confidence = 0.45 + len(signals) * 0.10
        
        # Bonus for agreement
        if same_direction and len(signals) >= 2:
            confidence += 0.12
        
        # Bonus for extreme positions
        if abs(weighted_direction) > 0.15:
            confidence += 0.05
        
        confidence = min(0.88, confidence)
        
        # Strength
        if len(signals) >= 3 and same_direction:
            strength = SignalStrength.STRONG
        elif len(signals) >= 2:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK
        
        return strength, signals, weighted_direction, confidence
    
    def calculate_edge(self, 
                      market_state: Dict,
                      direction_score: float,
                      confidence: float) -> Tuple[float, float]:
        """
        Calculate raw and net edge.
        
        Returns: (raw_edge, net_edge)
        """
        price = market_state.get("price", 0.5)
        spread = market_state.get("spread", 0.02)
        depth = market_state.get("bid_depth", 500) + market_state.get("ask_depth", 500)
        
        # Raw edge from signals
        raw_edge = abs(direction_score) * confidence
        
        # Adjust for costs
        est_position = 10.0  # Estimate average position
        net_edge = self.config.costs.adjust_edge_for_costs(
            raw_edge, spread, est_position, depth
        )
        
        return raw_edge, net_edge
    
    def calculate_position_size(self,
                               capital: float,
                               net_edge: float,
                               confidence: float,
                               quality: MarketQuality) -> float:
        """
        Calculate position size based on edge, confidence, and quality.
        """
        # Base size
        base_pct = self.config.base_position_pct
        
        # Adjust by edge
        edge_mult = min(1.5, net_edge / self.config.min_net_edge)
        
        # Adjust by confidence
        conf_mult = min(1.3, confidence / self.config.min_confidence)
        
        # Adjust by quality
        quality_mult = {
            MarketQuality.EXCELLENT: 1.0,
            MarketQuality.GOOD: 0.8,
            MarketQuality.MARGINAL: 0.5,
            MarketQuality.POOR: 0,
        }[quality]
        
        # Calculate
        position_pct = base_pct * edge_mult * conf_mult * quality_mult
        position_pct = min(position_pct, self.config.max_position_pct)
        
        # Dollar amount
        amount = capital * position_pct
        amount = max(self.config.min_position_dollars, amount)
        amount = min(self.config.max_position_dollars, amount)
        
        # Don't exceed available capital
        amount = min(amount, capital * 0.90)
        
        return amount
    
    def check_portfolio_constraints(self, capital: float, amount: float) -> Tuple[bool, str]:
        """
        Check if trade fits portfolio constraints.
        """
        # Check position count
        if len(self.open_positions) >= self.config.max_open_positions:
            return False, f"Max positions ({self.config.max_open_positions}) reached"
        
        # Check exposure
        current_exposure = sum(p.get("amount", 0) for p in self.open_positions.values())
        new_exposure = current_exposure + amount
        
        if new_exposure > capital * self.config.max_portfolio_exposure:
            return False, f"Would exceed max exposure ({self.config.max_portfolio_exposure:.0%})"
        
        return True, "OK"
    
    def get_signal(self, market_state: Dict, capital: float) -> Optional[Dict]:
        """
        Main strategy entry point.
        
        Args:
            market_state: Current market conditions
            capital: Available capital
        
        Returns:
            Trade signal dict or None
        """
        # Check market quality
        quality, quality_reason = self.assess_market_quality(market_state)
        
        if quality == MarketQuality.POOR:
            logger.debug(f"Skip: Poor market quality - {quality_reason}")
            return None
        
        # Calculate signals
        strength, signal_names, direction_score, confidence = self.calculate_signals(market_state)
        
        if strength == SignalStrength.NONE:
            return None
        
        if strength == SignalStrength.WEAK and quality != MarketQuality.EXCELLENT:
            logger.debug("Skip: Weak signal in non-excellent market")
            return None
        
        # Check minimum signals
        if len(signal_names) < self.config.min_signals_for_trade:
            return None
        
        # Check confidence
        if confidence < self.config.min_confidence:
            return None
        
        # Calculate edge
        raw_edge, net_edge = self.calculate_edge(market_state, direction_score, confidence)
        
        # Check edge thresholds
        if raw_edge < self.config.min_raw_edge:
            logger.debug(f"Skip: Raw edge {raw_edge:.1%} below minimum")
            return None
        
        if net_edge < self.config.min_net_edge:
            logger.debug(f"Skip: Net edge {net_edge:.1%} below minimum after costs")
            return None
        
        # Calculate position size
        amount = self.calculate_position_size(capital, net_edge, confidence, quality)
        
        if amount < self.config.min_position_dollars:
            return None
        
        # Check portfolio constraints
        can_trade, constraint_reason = self.check_portfolio_constraints(capital, amount)
        if not can_trade:
            logger.debug(f"Skip: {constraint_reason}")
            return None
        
        # Determine direction
        direction = "YES" if direction_score > 0 else "NO"
        price = market_state.get("price", 0.5)
        if direction == "NO":
            price = 1 - price
        
        # Build signal
        return {
            "action": "buy",
            "direction": direction,
            "amount": round(amount, 2),
            "price": price,
            "edge": net_edge,
            "raw_edge": raw_edge,
            "confidence": confidence,
            "signals": signal_names,
            "signal_strength": strength.value,
            "market_quality": quality.value,
            "quality_reason": quality_reason,
        }
    
    def should_exit(self, 
                   position: Dict, 
                   current_price: float,
                   hours_held: float) -> Tuple[bool, str]:
        """
        Check if position should be exited.
        """
        entry_price = position.get("entry_price", 0.5)
        direction = position.get("direction", "YES")
        
        # Calculate P&L
        if direction == "YES":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = ((1 - current_price) - (1 - entry_price)) / (1 - entry_price)
        
        # Stop loss
        if pnl_pct < -self.config.stop_loss_pct:
            return True, f"Stop loss triggered at {pnl_pct:.1%}"
        
        # Take profit
        if pnl_pct > self.config.take_profit_pct:
            return True, f"Take profit at {pnl_pct:.1%}"
        
        # Time-based exit (if too long without significant move)
        if hours_held > 120 and abs(pnl_pct) < 0.10:
            return True, f"Time stop after {hours_held:.0f}h"
        
        return False, "Hold"


# =============================================================================
# STRATEGY FACTORY
# =============================================================================

def create_robust_strategy(
    capital: float = 75.0,
    risk_level: str = "moderate"
) -> RobustStrategy:
    """
    Create robust strategy with appropriate risk level.
    
    Args:
        capital: Starting capital
        risk_level: "conservative", "moderate", or "aggressive"
    
    Returns:
        Configured RobustStrategy
    """
    if risk_level == "conservative":
        config = RobustStrategyConfig(
            min_raw_edge=0.18,
            min_net_edge=0.10,
            max_position_pct=0.08,
            max_open_positions=3,
            max_spread=0.04,
        )
    elif risk_level == "aggressive":
        config = RobustStrategyConfig(
            min_raw_edge=0.12,
            min_net_edge=0.06,
            max_position_pct=0.15,
            max_open_positions=5,
            max_spread=0.07,
        )
    else:  # moderate (default)
        config = RobustStrategyConfig()
    
    # Adjust position sizes for capital
    if capital < 50:
        config.max_position_dollars = 10
        config.base_position_pct = 0.06
    elif capital < 100:
        config.max_position_dollars = 15
    
    return RobustStrategy(config)


def get_strategy_signal_fn(strategy: RobustStrategy) -> Callable:
    """
    Get a simple signal function for backtesting.
    """
    def signal_fn(market_state: Dict, capital: float) -> Optional[Dict]:
        return strategy.get_signal(market_state, capital)
    
    return signal_fn


# =============================================================================
# PARAMETER GRID FOR OPTIMIZATION
# =============================================================================

PARAMETER_GRID = {
    "min_raw_edge": [0.12, 0.15, 0.18, 0.20],
    "min_net_edge": [0.06, 0.08, 0.10],
    "min_confidence": [0.55, 0.60, 0.65],
    "max_spread": [0.04, 0.06, 0.08],
    "max_position_pct": [0.08, 0.12, 0.15],
    "min_signals_for_trade": [1, 2],
}


def generate_parameter_combinations() -> List[Dict]:
    """Generate all parameter combinations for grid search."""
    import itertools
    
    keys = list(PARAMETER_GRID.keys())
    values = list(PARAMETER_GRID.values())
    
    combinations = []
    for combo in itertools.product(*values):
        combinations.append(dict(zip(keys, combo)))
    
    return combinations


if __name__ == "__main__":
    # Test strategy
    strategy = create_robust_strategy(capital=75.0, risk_level="moderate")
    
    # Sample market states
    test_markets = [
        {
            "price": 0.40,
            "sentiment": 0.35,
            "spread": 0.02,
            "volume_24h": 5000,
            "bid_depth": 1000,
            "ask_depth": 1000,
            "hours_to_resolution": 120,
        },
        {
            "price": 0.60,
            "sentiment": -0.30,
            "spread": 0.03,
            "volume_24h": 3000,
            "bid_depth": 800,
            "ask_depth": 800,
            "hours_to_resolution": 96,
        },
        {
            "price": 0.50,
            "sentiment": 0.05,  # Weak sentiment
            "spread": 0.08,    # Wide spread
            "volume_24h": 500, # Low volume
            "bid_depth": 200,
            "ask_depth": 200,
            "hours_to_resolution": 48,
        },
    ]
    
    print("Testing Robust Strategy")
    print("=" * 50)
    
    for i, market in enumerate(test_markets, 1):
        print(f"\nMarket {i}:")
        print(f"  Price: {market['price']:.0%}, Sentiment: {market['sentiment']:.2f}")
        print(f"  Spread: {market['spread']:.1%}, Volume: ${market['volume_24h']}")
        
        signal = strategy.get_signal(market, 75.0)
        
        if signal:
            print(f"  SIGNAL: {signal['direction']} ${signal['amount']:.2f}")
            print(f"    Edge: {signal['edge']:.1%} (raw: {signal['raw_edge']:.1%})")
            print(f"    Confidence: {signal['confidence']:.1%}")
            print(f"    Signals: {signal['signals']}")
        else:
            print("  NO SIGNAL")
    
    print("\n" + "=" * 50)
    print(f"Strategy config:")
    print(f"  Min raw edge: {strategy.config.min_raw_edge:.0%}")
    print(f"  Min net edge: {strategy.config.min_net_edge:.0%}")
    print(f"  Min confidence: {strategy.config.min_confidence:.0%}")
    print(f"  Max spread: {strategy.config.max_spread:.0%}")
    print(f"  Max position: {strategy.config.max_position_pct:.0%}")
