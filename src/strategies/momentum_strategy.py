"""
Momentum Trading Strategy for Polymarket
=========================================
A simpler, more aggressive strategy that focuses on:
1. Sentiment-price divergence
2. Extreme price levels
3. Clear directional momentum

Designed for 10%+ weekly returns through higher trade frequency
and better signal-to-outcome correlation.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class MomentumConfig:
    """Configuration for momentum strategy."""
    # Edge thresholds (aggressive)
    min_edge: float = 0.08           # 8% minimum edge
    optimal_edge: float = 0.15       # 15% optimal
    
    # Confidence thresholds
    min_confidence: float = 0.55     # 55% minimum
    
    # Market filters
    max_spread: float = 0.08         # 8% max spread
    min_volume: float = 500          # $500 min volume
    min_hours_to_resolution: int = 48
    max_hours_to_resolution: int = 336
    
    # Position sizing
    base_position_pct: float = 0.10  # 10% base
    max_position_pct: float = 0.15   # 15% max
    min_position: float = 3.0        # $3 min
    max_position: float = 15.0       # $15 max
    
    # Portfolio
    max_positions: int = 5
    
    # Trading costs estimate
    round_trip_cost: float = 0.025   # 2.5% total costs


class MomentumStrategy:
    """
    Simple momentum-based trading strategy.
    """
    
    def __init__(self, config: Optional[MomentumConfig] = None):
        self.config = config if config is not None else MomentumConfig()
        self.positions: Dict[str, Dict] = {}
    
    def get_signal(self, market_state: Dict, capital: float) -> Optional[Dict]:
        """
        Generate trading signal.
        
        Core logic:
        - Positive sentiment + low price = BUY YES
        - Negative sentiment + high price = BUY NO
        """
        price = market_state.get("price", 0.5)
        sentiment = market_state.get("sentiment", 0)
        spread = market_state.get("spread", 0.05)
        volume = market_state.get("volume_24h", 1000)
        hours_left = market_state.get("hours_to_resolution", 168)
        
        # Market quality filters
        if spread > self.config.max_spread:
            return None
        if volume < self.config.min_volume:
            return None
        if hours_left < self.config.min_hours_to_resolution:
            return None
        if hours_left > self.config.max_hours_to_resolution:
            return None
        
        # Portfolio check
        if len(self.positions) >= self.config.max_positions:
            return None
        
        # Calculate signal direction and strength
        signal = self._calculate_signal(price, sentiment, hours_left)
        
        if signal is None:
            return None
        
        direction, edge, confidence = signal
        
        # Check minimum thresholds
        if edge < self.config.min_edge:
            return None
        if confidence < self.config.min_confidence:
            return None
        
        # Adjust edge for costs
        net_edge = edge - self.config.round_trip_cost
        if net_edge <= 0:
            return None
        
        # Calculate position size
        amount = self._calculate_position(capital, net_edge, confidence)
        
        if amount < self.config.min_position:
            return None
        
        return {
            "action": "buy",
            "direction": direction,
            "amount": round(amount, 2),
            "price": price if direction == "YES" else (1 - price),
            "edge": net_edge,
            "raw_edge": edge,
            "confidence": confidence,
        }
    
    def _calculate_signal(self, price: float, sentiment: float, 
                         hours_left: float) -> Optional[Tuple[str, float, float]]:
        """
        Calculate signal direction, edge, and confidence.
        
        Returns: (direction, edge, confidence) or None
        """
        # Sentiment implies a fair value
        # Strong positive sentiment = higher YES probability
        # Strong negative sentiment = higher NO probability
        
        # Map sentiment to implied probability
        # sentiment ranges from -1 to 1
        # Map to probability range 0.25 to 0.75 (conservative)
        implied_prob = 0.5 + sentiment * 0.30
        implied_prob = max(0.20, min(0.80, implied_prob))
        
        # Calculate divergence
        divergence = implied_prob - price
        
        # Confidence based on sentiment strength and time to resolution
        base_confidence = 0.50 + abs(sentiment) * 0.30
        
        # Higher confidence closer to resolution (market discovers truth)
        time_factor = min(1.0, (336 - hours_left) / 336)
        time_bonus = time_factor * 0.10
        
        confidence = min(0.85, base_confidence + time_bonus)
        
        # Determine direction and edge
        if divergence > 0.05:
            # Underpriced - buy YES
            edge = divergence
            direction = "YES"
        elif divergence < -0.05:
            # Overpriced - buy NO
            edge = abs(divergence)
            direction = "NO"
        else:
            # No clear signal
            return None
        
        # Boost edge for extreme prices (higher upside)
        if direction == "YES" and price < 0.30:
            edge *= 1.2  # 20% bonus for low prices
            confidence *= 1.05
        elif direction == "NO" and price > 0.70:
            edge *= 1.2
            confidence *= 1.05
        
        return (direction, edge, confidence)
    
    def _calculate_position(self, capital: float, edge: float, 
                           confidence: float) -> float:
        """Calculate position size using simplified Kelly."""
        # Simplified Kelly: f = edge / odds
        # For binary markets at price p: odds = (1-p)/p
        # Approximate with edge-based sizing
        
        kelly_fraction = edge * confidence * 2  # Aggressive multiplier
        kelly_fraction = min(kelly_fraction, self.config.max_position_pct)
        kelly_fraction = max(kelly_fraction, 0)
        
        # Scale by edge quality
        if edge > self.config.optimal_edge:
            kelly_fraction *= 1.2
        
        amount = capital * kelly_fraction
        amount = max(self.config.min_position, amount)
        amount = min(self.config.max_position, amount)
        amount = min(capital * 0.90, amount)
        
        return amount


def create_momentum_strategy(
    capital: float = 75.0,
    aggressiveness: str = "high"
) -> MomentumStrategy:
    """
    Create momentum strategy with specified aggressiveness.
    """
    if aggressiveness == "low":
        config = MomentumConfig(
            min_edge=0.12,
            min_confidence=0.60,
            max_position_pct=0.10,
        )
    elif aggressiveness == "high":
        config = MomentumConfig(
            min_edge=0.06,
            min_confidence=0.52,
            max_position_pct=0.18,
            max_position=20.0,
        )
    else:  # medium
        config = MomentumConfig()
    
    return MomentumStrategy(config)


def get_momentum_signal_fn(strategy: MomentumStrategy) -> Callable:
    """Get signal function for backtesting."""
    def signal_fn(market_state: Dict, capital: float) -> Optional[Dict]:
        return strategy.get_signal(market_state, capital)
    return signal_fn


if __name__ == "__main__":
    # Test
    strategy = create_momentum_strategy(aggressiveness="high")
    
    test_cases = [
        {"price": 0.30, "sentiment": 0.25, "spread": 0.03, "volume_24h": 2000, "hours_to_resolution": 120},
        {"price": 0.70, "sentiment": -0.30, "spread": 0.04, "volume_24h": 3000, "hours_to_resolution": 96},
        {"price": 0.50, "sentiment": 0.10, "spread": 0.02, "volume_24h": 5000, "hours_to_resolution": 168},
        {"price": 0.25, "sentiment": 0.35, "spread": 0.05, "volume_24h": 1000, "hours_to_resolution": 200},
    ]
    
    print("Testing Momentum Strategy (High Aggressiveness)")
    print("=" * 60)
    
    for i, market in enumerate(test_cases, 1):
        signal = strategy.get_signal(market, 75.0)
        print(f"\nCase {i}: Price={market['price']:.0%}, Sentiment={market['sentiment']:.2f}")
        if signal:
            print(f"  SIGNAL: {signal['direction']} ${signal['amount']:.2f}")
            print(f"  Edge: {signal['edge']:.1%}, Confidence: {signal['confidence']:.1%}")
        else:
            print("  NO SIGNAL")
