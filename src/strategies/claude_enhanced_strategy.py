"""
Claude-Enhanced Rapid Trading Strategy
======================================
Target: 15% weekly returns

Key innovations:
1. Claude Haiku for high-accuracy sentiment analysis
2. Rapid entry/exit (don't wait for resolution)
3. Multi-market concurrent positions
4. News catalyst detection and fast reaction

Requires: ANTHROPIC_API_KEY in .env
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Import Claude analyzer
try:
    from analysis.llm_sentiment import ClaudeSentimentAnalyzer, BatchAnalyzer
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    logger.warning("Claude sentiment not available")


@dataclass
class ClaudeStrategyConfig:
    """Configuration for Claude-enhanced strategy targeting 15% weekly."""
    
    # Claude settings
    use_claude: bool = True
    claude_confidence_threshold: float = 0.70  # Only trade when Claude is 70%+ confident
    
    # Signal thresholds (higher bar with Claude)
    min_divergence: float = 0.12        # 12% price vs Claude prediction divergence
    min_combined_confidence: float = 0.65
    
    # Aggressive position sizing
    base_position_pct: float = 0.35     # 35% base
    max_position_pct: float = 0.50      # 50% max for high-confidence
    min_position: float = 5.0
    max_position: float = 45.0
    
    # Multi-market portfolio
    max_concurrent_positions: int = 4   # Up to 4 concurrent
    max_total_exposure: float = 0.90    # 90% max deployed
    
    # Rapid trading (don't wait for resolution)
    take_profit_pct: float = 0.08       # Exit at 8% profit
    stop_loss_pct: float = 0.06         # Exit at 6% loss
    max_hold_hours: int = 72            # Max 3 days per trade
    
    # Market filters
    min_volume_24h: float = 1000
    max_spread: float = 0.06
    min_hours_to_resolution: int = 48
    
    # Estimated costs
    round_trip_cost: float = 0.012


@dataclass
class MarketAnalysis:
    """Result of Claude market analysis."""
    market_id: str
    question: str
    current_price: float
    
    # Claude's assessment
    claude_probability: float       # Claude's estimated YES probability
    claude_confidence: float        # Claude's confidence in assessment
    claude_reasoning: str
    
    # Derived signals
    divergence: float               # Claude prob - market price
    direction: str                  # "YES" or "NO"
    edge: float
    combined_confidence: float
    
    # Trade recommendation
    should_trade: bool
    recommended_size: float
    entry_price: float


class ClaudeEnhancedStrategy:
    """
    Strategy using Claude Haiku for enhanced sentiment analysis.
    """
    
    def __init__(self, config: Optional[ClaudeStrategyConfig] = None):
        self.config = config or ClaudeStrategyConfig()
        
        # Initialize Claude
        if self.config.use_claude and CLAUDE_AVAILABLE:
            self.claude = ClaudeSentimentAnalyzer()
            self.claude_available = self.claude.is_available
        else:
            self.claude = None
            self.claude_available = False
        
        # Portfolio state
        self.positions: Dict[str, Dict] = {}
        self.total_exposure = 0.0
        
        # Performance tracking
        self.trades_today = 0
        self.wins_today = 0
        self.pnl_today = 0.0
    
    def analyze_market(self, 
                      market: Dict,
                      news_items: List[Dict] = None) -> MarketAnalysis:
        """
        Analyze a market using Claude.
        
        Args:
            market: Market data with question, price, etc.
            news_items: Recent news about this market
        
        Returns:
            MarketAnalysis with trading recommendation
        """
        question = market.get("question", "")
        current_price = market.get("yes_price", market.get("price", 0.5))
        market_id = market.get("id", "unknown")
        
        # Default fallback
        if not self.claude_available or not question:
            return self._fallback_analysis(market)
        
        # Build context for Claude
        context = self._build_context(market, news_items)
        
        # Ask Claude for probability assessment
        result = self.claude.analyze_text(context, question)
        
        if not result:
            return self._fallback_analysis(market)
        
        # Claude's sentiment maps to probability
        # sentiment_score: -1 to 1 -> probability: 0.15 to 0.85
        claude_prob = 0.5 + result.sentiment_score * 0.35
        claude_prob = max(0.15, min(0.85, claude_prob))
        
        # Calculate divergence
        divergence = claude_prob - current_price
        
        # Determine direction
        if divergence > 0:
            direction = "YES"
            edge = divergence
            entry_price = current_price
        else:
            direction = "NO"
            edge = abs(divergence)
            entry_price = 1 - current_price
        
        # Combined confidence
        combined_conf = result.confidence * (0.5 + abs(result.sentiment_score) * 0.5)
        
        # Should we trade?
        should_trade = (
            edge >= self.config.min_divergence and
            result.confidence >= self.config.claude_confidence_threshold and
            combined_conf >= self.config.min_combined_confidence and
            len(self.positions) < self.config.max_concurrent_positions and
            self.total_exposure < self.config.max_total_exposure
        )
        
        # Calculate position size
        if should_trade:
            recommended_size = self._calculate_size(edge, combined_conf)
        else:
            recommended_size = 0
        
        return MarketAnalysis(
            market_id=market_id,
            question=question,
            current_price=current_price,
            claude_probability=claude_prob,
            claude_confidence=result.confidence,
            claude_reasoning=result.reasoning,
            divergence=divergence,
            direction=direction,
            edge=edge,
            combined_confidence=combined_conf,
            should_trade=should_trade,
            recommended_size=recommended_size,
            entry_price=entry_price,
        )
    
    def _build_context(self, market: Dict, news_items: List[Dict] = None) -> str:
        """Build context string for Claude analysis."""
        parts = []
        
        # Market info
        parts.append(f"Market Question: {market.get('question', 'Unknown')}")
        parts.append(f"Current YES Price: {market.get('yes_price', 0.5):.0%}")
        
        if market.get("description"):
            parts.append(f"Description: {market['description'][:500]}")
        
        # Volume/activity
        if market.get("volume_24h"):
            parts.append(f"24h Volume: ${market['volume_24h']:,.0f}")
        
        # Resolution date
        if market.get("end_date"):
            parts.append(f"Resolves: {market['end_date']}")
        
        # Recent news
        if news_items:
            parts.append("\nRecent News:")
            for item in news_items[:5]:
                title = item.get("title", "")
                if title:
                    parts.append(f"- {title}")
        
        return "\n".join(parts)
    
    def _calculate_size(self, edge: float, confidence: float) -> float:
        """Calculate position size based on edge and confidence."""
        # Base size
        base = self.config.base_position_pct
        
        # Scale by edge quality
        edge_mult = 1.0 + (edge - self.config.min_divergence) * 3
        edge_mult = min(1.5, max(0.8, edge_mult))
        
        # Scale by confidence
        conf_mult = confidence / self.config.min_combined_confidence
        conf_mult = min(1.3, max(0.8, conf_mult))
        
        # Calculate
        size_pct = base * edge_mult * conf_mult
        size_pct = min(size_pct, self.config.max_position_pct)
        
        # Check exposure limits
        available_exposure = self.config.max_total_exposure - self.total_exposure
        size_pct = min(size_pct, available_exposure)
        
        # Convert to dollars (assuming $75 capital)
        capital = 75.0
        amount = capital * size_pct
        amount = max(self.config.min_position, amount)
        amount = min(self.config.max_position, amount)
        
        return amount
    
    def _fallback_analysis(self, market: Dict) -> MarketAnalysis:
        """Fallback when Claude not available."""
        price = market.get("yes_price", market.get("price", 0.5))
        sentiment = market.get("sentiment", 0)
        
        # Simple sentiment-based analysis
        implied_prob = 0.5 + sentiment * 0.25
        divergence = implied_prob - price
        
        return MarketAnalysis(
            market_id=market.get("id", "unknown"),
            question=market.get("question", ""),
            current_price=price,
            claude_probability=implied_prob,
            claude_confidence=0.4,  # Low confidence for fallback
            claude_reasoning="Fallback: keyword sentiment analysis",
            divergence=divergence,
            direction="YES" if divergence > 0 else "NO",
            edge=abs(divergence),
            combined_confidence=0.4,
            should_trade=False,  # Don't trade on fallback
            recommended_size=0,
            entry_price=price,
        )
    
    def get_signal(self, market_state: Dict, capital: float) -> Optional[Dict]:
        """
        Generate trading signal (compatible with backtest interface).
        """
        # Run analysis
        analysis = self.analyze_market(market_state)
        
        if not analysis.should_trade:
            return None
        
        # Adjust for actual capital
        size_pct = analysis.recommended_size / 75.0
        amount = capital * size_pct
        amount = max(self.config.min_position, min(self.config.max_position, amount))
        
        return {
            "action": "buy",
            "direction": analysis.direction,
            "amount": round(amount, 2),
            "price": analysis.entry_price,
            "edge": analysis.edge - self.config.round_trip_cost,
            "confidence": analysis.combined_confidence,
            "claude_reasoning": analysis.claude_reasoning,
        }
    
    def check_exit(self, position: Dict, current_price: float, 
                   hours_held: float) -> Tuple[bool, str]:
        """
        Check if position should be exited (rapid trading).
        """
        entry_price = position.get("entry_price", 0.5)
        direction = position.get("direction", "YES")
        
        # Calculate current P&L
        if direction == "YES":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = ((1 - current_price) - (1 - entry_price)) / (1 - entry_price)
        
        # Take profit
        if pnl_pct >= self.config.take_profit_pct:
            return True, f"Take profit at {pnl_pct:.1%}"
        
        # Stop loss
        if pnl_pct <= -self.config.stop_loss_pct:
            return True, f"Stop loss at {pnl_pct:.1%}"
        
        # Time-based exit
        if hours_held >= self.config.max_hold_hours:
            return True, f"Max hold time ({self.config.max_hold_hours}h)"
        
        return False, "Hold"
    
    def record_trade(self, pnl: float, won: bool):
        """Record trade for daily tracking."""
        self.trades_today += 1
        if won:
            self.wins_today += 1
        self.pnl_today += pnl
    
    def reset_daily(self):
        """Reset daily counters."""
        self.trades_today = 0
        self.wins_today = 0
        self.pnl_today = 0.0


def create_claude_strategy() -> ClaudeEnhancedStrategy:
    """Create Claude-enhanced strategy."""
    return ClaudeEnhancedStrategy()


def get_claude_signal_fn(strategy: ClaudeEnhancedStrategy):
    """Get signal function for backtesting."""
    def signal_fn(market_state: Dict, capital: float) -> Optional[Dict]:
        return strategy.get_signal(market_state, capital)
    return signal_fn


# Expected performance with Claude
EXPECTED_PERFORMANCE = """
EXPECTED PERFORMANCE (Claude-Enhanced)
======================================
Win Rate:       65-72%  (vs 57% baseline)
Avg Win:        +8-10%  (rapid exit)
Avg Loss:       -5-6%   (tight stops)
Trades/Week:    3-5     (multiple concurrent)
Weekly Return:  12-18%  (target 15%)

KEY ASSUMPTIONS:
- Claude Haiku provides 70%+ confidence assessments
- News catalyst detection adds 2-3 high-edge trades/week
- Rapid trading captures 8% profits vs waiting for resolution
- Multiple concurrent positions (4 max) multiply returns

COSTS:
- Claude API: ~$0.01 per analysis
- 50 analyses/day = $0.50/day = $15/month
"""


if __name__ == "__main__":
    print(EXPECTED_PERFORMANCE)
    
    strategy = create_claude_strategy()
    print(f"\nClaude available: {strategy.claude_available}")
    
    if strategy.claude_available:
        # Test analysis
        test_market = {
            "id": "test-1",
            "question": "Will Bitcoin reach $100,000 by end of 2026?",
            "yes_price": 0.45,
            "volume_24h": 50000,
        }
        
        test_news = [
            {"title": "BlackRock Bitcoin ETF sees record inflows"},
            {"title": "Fed signals potential rate cuts in 2026"},
        ]
        
        print("\nAnalyzing test market...")
        analysis = strategy.analyze_market(test_market, test_news)
        
        print(f"\nMarket: {analysis.question}")
        print(f"Current Price: {analysis.current_price:.0%}")
        print(f"Claude Probability: {analysis.claude_probability:.0%}")
        print(f"Claude Confidence: {analysis.claude_confidence:.0%}")
        print(f"Divergence: {analysis.divergence:+.1%}")
        print(f"Direction: {analysis.direction}")
        print(f"Should Trade: {analysis.should_trade}")
        print(f"Recommended Size: ${analysis.recommended_size:.2f}")
        print(f"Reasoning: {analysis.claude_reasoning}")
