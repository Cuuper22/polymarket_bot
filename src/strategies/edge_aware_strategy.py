"""
Edge-Aware Momentum Strategy
============================
Improved strategy that handles edge cases better by:
1. Detecting and avoiding volatile/trap conditions
2. Requiring stronger confirmation for risky setups
3. Being aggressive on high-quality setups (news-driven, trending)

Target: 15%+ weekly with edge cases handled
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable
import math


@dataclass
class EdgeAwareConfig:
    """Configuration with edge case awareness."""
    
    # Base thresholds
    min_edge: float = 0.06
    min_confidence: float = 0.50
    
    # HIGHER thresholds for risky conditions
    volatile_min_edge: float = 0.12        # Double for volatile
    volatile_min_confidence: float = 0.65
    
    # Position sizing
    base_position_pct: float = 0.45
    max_position_pct: float = 0.60         # Higher max for quality
    volatile_position_pct: float = 0.20    # Much lower for volatile
    min_position: float = 5.0
    max_position: float = 55.0
    
    # Market quality
    max_spread: float = 0.08
    min_volume: float = 500
    min_hours_to_resolution: int = 48
    max_hours_to_resolution: int = 336
    
    # Volatility detection
    sentiment_consistency_threshold: float = 0.15  # Max sentiment swing to be "consistent"
    
    # Portfolio
    max_positions: int = 5
    
    # Costs
    round_trip_cost: float = 0.012


class EdgeAwareStrategy:
    """
    Strategy with edge case awareness.
    
    Key improvements:
    1. Detect volatile conditions -> reduce size or skip
    2. Detect sentiment traps -> require strong confirmation
    3. Detect trending/news -> be aggressive
    """
    
    def __init__(self, config: Optional[EdgeAwareConfig] = None):
        self.config = config if config is not None else EdgeAwareConfig()
        self.positions: Dict[str, Dict] = {}
    
    def detect_market_regime(self, market_state: Dict) -> Tuple[str, float]:
        """
        Detect market regime and confidence.
        
        Returns: (regime, confidence)
        Regimes: "trending", "news_driven", "volatile", "ranging", "trap"
        """
        price = market_state.get("price", 0.5)
        sentiment = market_state.get("sentiment", 0)
        volume = market_state.get("volume_24h", 1000)
        spread = market_state.get("spread", 0.03)
        hours_left = market_state.get("hours_to_resolution", 168)
        
        # Indicators
        sentiment_strength = abs(sentiment)
        high_volume = volume > 3000
        wide_spread = spread > 0.06  # More lenient
        
        # TRAP DETECTION: Only flag CLEAR traps
        # Strong contradictory signal: negative sentiment + very low price (or vice versa)
        clear_trap = (sentiment < -0.30 and price < 0.25) or (sentiment > 0.30 and price > 0.75)
        
        if clear_trap:
            return "trap", 0.8
        
        # VOLATILE: very wide spread near resolution
        if wide_spread and hours_left < 48:
            return "volatile", 0.6
        
        # NEWS-DRIVEN: high volume + strong sentiment (best setups)
        if high_volume and sentiment_strength > 0.25:
            return "news_driven", 0.85
        
        # TRENDING: any meaningful directional sentiment
        if sentiment_strength > 0.15:
            return "trending", 0.7
        
        # MILD TREND: weak but present sentiment
        if sentiment_strength > 0.08:
            return "mild_trend", 0.55
        
        # RANGING: very weak sentiment only
        if sentiment_strength < 0.08:
            return "ranging", 0.4
        
        # DEFAULT - treat as mild trend
        return "mild_trend", 0.5
    
    def get_signal(self, market_state: Dict, capital: float) -> Optional[Dict]:
        """
        Generate signal with edge case awareness.
        """
        price = market_state.get("price", 0.5)
        sentiment = market_state.get("sentiment", 0)
        spread = market_state.get("spread", 0.05)
        volume = market_state.get("volume_24h", 1000)
        hours_left = market_state.get("hours_to_resolution", 168)
        
        # Basic filters
        if spread > self.config.max_spread:
            return None
        if volume < self.config.min_volume:
            return None
        if hours_left < self.config.min_hours_to_resolution:
            return None
        if hours_left > self.config.max_hours_to_resolution:
            return None
        
        # Detect regime
        regime, regime_confidence = self.detect_market_regime(market_state)
        
        # SKIP traps entirely
        if regime == "trap":
            return None
        
        # SKIP ranging markets (no edge)
        if regime == "ranging":
            return None
        
        # Calculate base signal
        implied_prob = 0.5 + sentiment * 0.35
        divergence = implied_prob - price
        
        direction = "YES" if divergence > 0 else "NO"
        raw_edge = abs(divergence)
        
        # Determine thresholds based on regime
        if regime == "volatile":
            min_edge = self.config.volatile_min_edge
            min_conf = self.config.volatile_min_confidence
            max_position = self.config.volatile_position_pct
        else:
            min_edge = self.config.min_edge
            min_conf = self.config.min_confidence
            max_position = self.config.max_position_pct
        
        # Calculate confidence
        base_confidence = 0.50 + abs(sentiment) * 0.30
        
        # Regime bonus/penalty
        if regime == "news_driven":
            base_confidence += 0.12
            raw_edge *= 1.15  # Edge boost for news
        elif regime == "trending":
            base_confidence += 0.08
            raw_edge *= 1.10
        elif regime == "mild_trend":
            base_confidence += 0.03  # Small bonus
            raw_edge *= 1.0  # No edge boost
        
        confidence = min(0.90, base_confidence * regime_confidence)
        
        # Apply thresholds
        net_edge = raw_edge - self.config.round_trip_cost
        
        if net_edge < min_edge:
            return None
        if confidence < min_conf:
            return None
        
        # Calculate position size
        amount = self._calculate_position(capital, net_edge, confidence, max_position, regime)
        
        if amount < self.config.min_position:
            return None
        
        return {
            "action": "buy",
            "direction": direction,
            "amount": round(amount, 2),
            "price": price if direction == "YES" else (1 - price),
            "edge": net_edge,
            "confidence": confidence,
            "regime": regime,
        }
    
    def _calculate_position(self, capital: float, edge: float, confidence: float,
                           max_pct: float, regime: str) -> float:
        """Calculate position with regime awareness."""
        
        # Base position
        base = self.config.base_position_pct
        
        # Scale by edge
        edge_mult = 1.0 + (edge - self.config.min_edge) * 4
        edge_mult = min(1.8, max(0.7, edge_mult))
        
        # Scale by confidence
        conf_mult = confidence / self.config.min_confidence
        conf_mult = min(1.5, max(0.7, conf_mult))
        
        # Regime multiplier
        regime_mult = {
            "news_driven": 1.3,    # Aggressive on news
            "trending": 1.2,       # Good on trends
            "mild_trend": 1.0,     # Normal sizing
            "volatile": 0.5,       # Very conservative
            "unknown": 0.8,
        }.get(regime, 1.0)
        
        # Calculate
        position_pct = base * edge_mult * conf_mult * regime_mult
        position_pct = min(position_pct, max_pct)
        
        amount = capital * position_pct
        amount = max(self.config.min_position, amount)
        amount = min(self.config.max_position, amount)
        
        return amount


def create_edge_aware_strategy() -> EdgeAwareStrategy:
    """Create edge-aware strategy."""
    return EdgeAwareStrategy()


def get_edge_aware_signal_fn(strategy: EdgeAwareStrategy) -> Callable:
    """Get signal function for backtesting."""
    def signal_fn(market_state: Dict, capital: float) -> Optional[Dict]:
        return strategy.get_signal(market_state, capital)
    return signal_fn


if __name__ == "__main__":
    strategy = create_edge_aware_strategy()
    
    # Test cases
    tests = [
        # News-driven (should trade aggressively)
        {"name": "News-driven", "price": 0.40, "sentiment": 0.35, "spread": 0.03, 
         "volume_24h": 5000, "hours_to_resolution": 120},
        
        # Trending (should trade)
        {"name": "Trending", "price": 0.35, "sentiment": 0.28, "spread": 0.03,
         "volume_24h": 2000, "hours_to_resolution": 150},
        
        # Trap (should skip - negative sentiment but low price)
        {"name": "Trap", "price": 0.30, "sentiment": -0.30, "spread": 0.04,
         "volume_24h": 2000, "hours_to_resolution": 100},
        
        # Volatile (should be conservative)
        {"name": "Volatile", "price": 0.50, "sentiment": 0.20, "spread": 0.06,
         "volume_24h": 1500, "hours_to_resolution": 60},
        
        # Ranging (should skip)
        {"name": "Ranging", "price": 0.48, "sentiment": 0.05, "spread": 0.03,
         "volume_24h": 1000, "hours_to_resolution": 168},
    ]
    
    print("Edge-Aware Strategy Tests")
    print("=" * 60)
    
    for test in tests:
        name = test.pop("name")
        regime, conf = strategy.detect_market_regime(test)
        signal = strategy.get_signal(test, 75.0)
        
        print(f"\n{name}:")
        print(f"  Regime: {regime} ({conf:.0%} confidence)")
        if signal:
            print(f"  Signal: {signal['direction']} ${signal['amount']:.2f}")
            print(f"  Edge: {signal['edge']:.1%}, Confidence: {signal['confidence']:.1%}")
        else:
            print(f"  Signal: SKIP")
