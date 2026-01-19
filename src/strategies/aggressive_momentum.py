"""
Aggressive Momentum Strategy - Target 10%+ Weekly Returns
=========================================================
Enhanced version with:
- Higher position sizing on strong signals
- Multiple entry opportunities
- Dynamic sizing based on edge quality
"""
from dataclasses import dataclass
from typing import Dict, Optional, Callable
import math


@dataclass
class AggressiveMomentumConfig:
    """Configuration for aggressive momentum strategy."""
    # Lower thresholds for more trades
    min_edge: float = 0.05           # 5% minimum edge
    min_confidence: float = 0.50     # 50% minimum
    
    # Aggressive position sizing
    base_position_pct: float = 0.12  # 12% base
    max_position_pct: float = 0.25   # 25% max for strong signals
    min_position: float = 3.0        # $3 min
    max_position: float = 25.0       # $25 max
    
    # Edge scaling - bigger positions on better edges
    edge_scale_factor: float = 2.0   # Position scales with edge
    
    # Portfolio
    max_positions: int = 6
    max_exposure: float = 0.85       # 85% max deployed
    
    # Costs
    round_trip_cost: float = 0.02    # 2% costs


class AggressiveMomentumStrategy:
    """
    Aggressive momentum strategy targeting 10%+ weekly returns.
    """
    
    def __init__(self, config: Optional[AggressiveMomentumConfig] = None):
        self.config = config if config is not None else AggressiveMomentumConfig()
        self.positions: Dict[str, Dict] = {}
        self.total_invested = 0.0
    
    def get_signal(self, market_state: Dict, capital: float) -> Optional[Dict]:
        """Generate trading signal."""
        price = market_state.get("price", 0.5)
        sentiment = market_state.get("sentiment", 0)
        spread = market_state.get("spread", 0.05)
        volume = market_state.get("volume_24h", 1000)
        hours_left = market_state.get("hours_to_resolution", 168)
        
        # Relaxed filters for more opportunities
        if spread > 0.10:  # Only skip very wide spreads
            return None
        if hours_left < 24:  # Only skip very close to resolution
            return None
        if hours_left > 500:  # Skip very long dated
            return None
        
        # Check exposure limits
        if self.total_invested >= capital * self.config.max_exposure:
            return None
        if len(self.positions) >= self.config.max_positions:
            return None
        
        # Calculate signal
        signal_data = self._calculate_signal(price, sentiment, hours_left, volume)
        
        if signal_data is None:
            return None
        
        direction, raw_edge, confidence = signal_data
        
        # Adjust for costs
        net_edge = raw_edge - self.config.round_trip_cost
        if net_edge < self.config.min_edge:
            return None
        if confidence < self.config.min_confidence:
            return None
        
        # Calculate aggressive position size
        amount = self._calculate_position(capital, net_edge, confidence, price)
        
        if amount < self.config.min_position:
            return None
        
        # Check available capital
        available = capital - self.total_invested
        amount = min(amount, available * 0.9)
        
        if amount < self.config.min_position:
            return None
        
        return {
            "action": "buy",
            "direction": direction,
            "amount": round(amount, 2),
            "price": price if direction == "YES" else (1 - price),
            "edge": net_edge,
            "raw_edge": raw_edge,
            "confidence": confidence,
        }
    
    def _calculate_signal(self, price: float, sentiment: float, 
                         hours_left: float, volume: float) -> Optional[tuple]:
        """Calculate signal with multiple entry criteria."""
        
        # Method 1: Sentiment divergence (strongest signal)
        implied_prob = 0.5 + sentiment * 0.35
        divergence = implied_prob - price
        
        # Method 2: Extreme price levels
        extreme_signal = 0
        if price < 0.25:
            extreme_signal = 0.15  # Underpriced
        elif price > 0.75:
            extreme_signal = -0.15  # Overpriced
        
        # Method 3: Strong sentiment with volume
        volume_signal = 0
        if volume > 2000 and abs(sentiment) > 0.20:
            volume_signal = sentiment * 0.10
        
        # Combine signals
        combined_signal = divergence * 0.6 + extreme_signal * 0.25 + volume_signal * 0.15
        
        if abs(combined_signal) < 0.05:
            return None
        
        direction = "YES" if combined_signal > 0 else "NO"
        raw_edge = abs(combined_signal)
        
        # Confidence based on signal strength and agreement
        base_confidence = 0.50 + abs(sentiment) * 0.25
        
        # Boost confidence for aligned signals
        signals_aligned = (divergence * extreme_signal >= 0) if extreme_signal != 0 else True
        if signals_aligned and abs(sentiment) > 0.25:
            base_confidence += 0.10
        
        # Time decay - higher confidence closer to resolution
        time_factor = max(0, min(1, (336 - hours_left) / 336))
        base_confidence += time_factor * 0.08
        
        confidence = min(0.88, base_confidence)
        
        # Edge boost for extreme prices (higher potential return)
        if (direction == "YES" and price < 0.30) or (direction == "NO" and price > 0.70):
            raw_edge *= 1.3
        
        return (direction, raw_edge, confidence)
    
    def _calculate_position(self, capital: float, edge: float, 
                           confidence: float, price: float) -> float:
        """Calculate position size with edge-based scaling."""
        
        # Base position
        base = capital * self.config.base_position_pct
        
        # Scale by edge quality (more edge = bigger position)
        edge_mult = 1.0 + (edge - self.config.min_edge) * self.config.edge_scale_factor
        edge_mult = min(2.0, max(1.0, edge_mult))
        
        # Scale by confidence
        conf_mult = 1.0 + (confidence - 0.5) * 1.5
        conf_mult = min(1.5, max(0.8, conf_mult))
        
        # Calculate
        amount = base * edge_mult * conf_mult
        
        # Apply limits
        max_by_pct = capital * self.config.max_position_pct
        amount = min(amount, max_by_pct)
        amount = min(amount, self.config.max_position)
        amount = max(amount, self.config.min_position)
        
        return amount
    
    def record_position(self, market_id: str, amount: float):
        """Record a position for exposure tracking."""
        self.positions[market_id] = {"amount": amount}
        self.total_invested += amount
    
    def close_position(self, market_id: str):
        """Close a position."""
        if market_id in self.positions:
            self.total_invested -= self.positions[market_id]["amount"]
            del self.positions[market_id]
    
    def reset(self):
        """Reset for new backtest."""
        self.positions = {}
        self.total_invested = 0.0


def create_aggressive_momentum(capital: float = 75.0) -> AggressiveMomentumStrategy:
    """Create aggressive momentum strategy."""
    config = AggressiveMomentumConfig()
    
    # Adjust for capital size
    if capital < 50:
        config.max_position = 15.0
        config.max_position_pct = 0.20
    elif capital > 100:
        config.max_position = 35.0
    
    return AggressiveMomentumStrategy(config)


def get_aggressive_signal_fn(strategy: AggressiveMomentumStrategy) -> Callable:
    """Get signal function for backtesting."""
    def signal_fn(market_state: Dict, capital: float) -> Optional[Dict]:
        return strategy.get_signal(market_state, capital)
    return signal_fn


if __name__ == "__main__":
    strategy = create_aggressive_momentum()
    
    tests = [
        {"price": 0.25, "sentiment": 0.30, "spread": 0.03, "volume_24h": 3000, "hours_to_resolution": 120},
        {"price": 0.70, "sentiment": -0.35, "spread": 0.04, "volume_24h": 5000, "hours_to_resolution": 96},
        {"price": 0.45, "sentiment": 0.25, "spread": 0.02, "volume_24h": 2000, "hours_to_resolution": 168},
    ]
    
    print("Aggressive Momentum Strategy Test")
    print("=" * 50)
    
    for i, m in enumerate(tests, 1):
        signal = strategy.get_signal(m, 75.0)
        print(f"\nTest {i}: Price={m['price']:.0%}, Sentiment={m['sentiment']:.2f}")
        if signal:
            print(f"  -> {signal['direction']} ${signal['amount']:.2f}, Edge={signal['edge']:.1%}")
        else:
            print("  -> No signal")
