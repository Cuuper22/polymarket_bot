"""
Swing Trading Strategy
Buy low, sell high based on price movements - not waiting for resolution.
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class SwingConfig:
    """Configuration for swing trading strategy."""
    # Entry criteria
    min_dip_pct: float = 0.08  # 8% drop from 24h high to consider buying
    min_volume: float = 500  # Minimum 24h volume
    min_price: float = 0.10  # Don't trade below 10%
    max_price: float = 0.90  # Don't trade above 90%
    
    # Exit criteria (conservative, accounting for 2% Polymarket fee)
    take_profit_pct: float = 0.08  # 8% gain (nets ~6% after fees)
    stop_loss_pct: float = 0.15  # 15% loss
    max_hold_hours: int = 24  # Exit after 24h if no movement
    
    # Trailing stop (optional)
    use_trailing_stop: bool = True
    trailing_stop_pct: float = 0.05  # 5% from highest price
    
    # Position sizing
    base_position_pct: float = 0.10  # 10% of capital per trade
    max_position_pct: float = 0.15  # 15% max per trade
    min_position: float = 3.0  # $3 minimum
    max_position: float = 15.0  # $15 maximum
    max_concurrent: int = 6  # Max open positions
    max_exposure_pct: float = 0.70  # 70% max invested
    
    # Signal requirements (HYBRID STRATEGY - require positive sentiment!)
    require_positive_sentiment: bool = True
    min_sentiment_score: float = 0.1  # Require positive sentiment (benchmark showed this filters traps)
    require_grok_bullish: bool = False  # If True, needs Grok to say "up"


@dataclass
class SwingSignal:
    """A trading signal from the swing strategy."""
    market_id: str
    market_question: str
    action: str  # 'buy', 'sell', 'hold'
    direction: str  # 'YES' or 'NO'
    price: float
    reason: str
    
    # For buys
    dip_size: Optional[float] = None  # How much it dipped
    sentiment_score: Optional[float] = None
    grok_direction: Optional[str] = None
    
    # For sells
    return_pct: Optional[float] = None
    hold_hours: Optional[float] = None


class SwingStrategy:
    """
    Swing trading strategy for prediction markets.
    
    Entry Logic (BUY):
    1. Price dipped X% from 24h high (oversold)
    2. Sentiment is neutral or positive (not a fundamental collapse)
    3. Volume is sufficient for liquidity
    4. Price in tradeable range (10-90%)
    
    Exit Logic (SELL):
    1. Take profit: Price up X% from entry
    2. Stop loss: Price down Y% from entry  
    3. Trailing stop: Price down Z% from highest since entry
    4. Time exit: Held for 24h with no significant movement
    """
    
    def __init__(self, config: Optional[SwingConfig] = None):
        """
        Initialize the swing strategy.
        
        Args:
            config: Strategy configuration
        """
        self.config = config or SwingConfig()
        
        # Track highest price since entry for trailing stops
        self.position_highs: Dict[str, float] = {}
    
    def evaluate_entry(self, market_data: Dict, price_analysis: Optional[Dict] = None,
                       sentiment: Optional[Dict] = None, 
                       grok_analysis: Optional[Dict] = None) -> Optional[SwingSignal]:
        """
        Evaluate whether to enter a position.
        
        Args:
            market_data: Current market data (id, question, price, volume_24h, etc.)
            price_analysis: From PriceTracker (change_24h, is_dip, dip_size, etc.)
            sentiment: Sentiment analysis results
            grok_analysis: Grok AI analysis results
            
        Returns:
            SwingSignal if we should buy, None otherwise
        """
        market_id = market_data.get('id', '')
        question = market_data.get('question', '')
        price = market_data.get('price', 0.5)
        volume = market_data.get('volume_24h', 0)
        
        # Basic filters
        if price < self.config.min_price or price > self.config.max_price:
            return None
        
        if volume < self.config.min_volume:
            return None
        
        # Check for dip
        dip_size = 0
        if price_analysis:
            if not price_analysis.get('is_dip', False):
                return None
            dip_size = price_analysis.get('dip_size', 0)
            if dip_size < self.config.min_dip_pct:
                return None
        
        # Check sentiment
        sentiment_score = 0
        if sentiment:
            sentiment_score = sentiment.get('score', 0)
            if self.config.require_positive_sentiment:
                if sentiment_score < self.config.min_sentiment_score:
                    return None
        
        # Check Grok analysis
        grok_direction = None
        if grok_analysis:
            grok_direction = grok_analysis.get('price_direction', 'neutral')
            if self.config.require_grok_bullish:
                if grok_direction != 'up':
                    return None
        
        # We have a buy signal - buying YES when price dipped
        reason_parts = [f"Price dipped {dip_size:.1%} from 24h high"]
        if sentiment_score > 0:
            reason_parts.append(f"positive sentiment ({sentiment_score:.2f})")
        if grok_direction == 'up':
            reason_parts.append("Grok expects price to rise")
        
        return SwingSignal(
            market_id=market_id,
            market_question=question,
            action='buy',
            direction='YES',  # Always buy YES on dips
            price=price,
            reason=", ".join(reason_parts),
            dip_size=dip_size,
            sentiment_score=sentiment_score,
            grok_direction=grok_direction
        )
    
    def evaluate_exit(self, position: Dict, current_price: float) -> Optional[SwingSignal]:
        """
        Evaluate whether to exit a position.
        
        Args:
            position: Current position data (market_id, entry_price, entry_time, amount, etc.)
            current_price: Current market price
            
        Returns:
            SwingSignal if we should sell, None otherwise
        """
        market_id = position.get('market_id', '')
        entry_price = position.get('entry_price', 0)
        entry_time = position.get('entry_time', '')
        question = position.get('market_question', '')
        
        if entry_price == 0:
            return None
        
        # Calculate return
        return_pct = (current_price - entry_price) / entry_price
        
        # Calculate hold time
        if isinstance(entry_time, str):
            entry_dt = datetime.fromisoformat(entry_time)
        else:
            entry_dt = entry_time
        hold_hours = (datetime.now() - entry_dt).total_seconds() / 3600
        
        # Update position high for trailing stop
        if market_id not in self.position_highs:
            self.position_highs[market_id] = entry_price
        if current_price > self.position_highs[market_id]:
            self.position_highs[market_id] = current_price
        
        # Check exit conditions
        
        # 1. Take profit
        if return_pct >= self.config.take_profit_pct:
            return SwingSignal(
                market_id=market_id,
                market_question=question,
                action='sell',
                direction=position.get('direction', 'YES'),
                price=current_price,
                reason=f"Take profit: {return_pct:.1%} gain",
                return_pct=return_pct,
                hold_hours=hold_hours
            )
        
        # 2. Stop loss
        if return_pct <= -self.config.stop_loss_pct:
            return SwingSignal(
                market_id=market_id,
                market_question=question,
                action='sell',
                direction=position.get('direction', 'YES'),
                price=current_price,
                reason=f"Stop loss: {return_pct:.1%} loss",
                return_pct=return_pct,
                hold_hours=hold_hours
            )
        
        # 3. Trailing stop
        if self.config.use_trailing_stop and entry_price > 0:
            high = self.position_highs.get(market_id, entry_price)
            if high and high > entry_price:  # Only if we've been in profit
                drop_from_high = (high - current_price) / high
                if drop_from_high >= self.config.trailing_stop_pct:
                    return SwingSignal(
                        market_id=market_id,
                        market_question=question,
                        action='sell',
                        direction=position.get('direction', 'YES'),
                        price=current_price,
                        reason=f"Trailing stop: dropped {drop_from_high:.1%} from high",
                        return_pct=return_pct,
                        hold_hours=hold_hours
                    )
        
        # 4. Time exit
        if hold_hours >= self.config.max_hold_hours:
            return SwingSignal(
                market_id=market_id,
                market_question=question,
                action='sell',
                direction=position.get('direction', 'YES'),
                price=current_price,
                reason=f"Time exit: held {hold_hours:.1f}h with {return_pct:.1%} return",
                return_pct=return_pct,
                hold_hours=hold_hours
            )
        
        return None  # Hold
    
    def calculate_position_size(self, capital: float, signal: SwingSignal,
                               current_positions: int) -> float:
        """
        Calculate position size for a trade.
        
        Args:
            capital: Available capital
            signal: The buy signal
            current_positions: Number of open positions
            
        Returns:
            Position size in dollars
        """
        if current_positions >= self.config.max_concurrent:
            return 0
        
        # Base position size
        base_size = capital * self.config.base_position_pct
        
        # Increase size for larger dips (more confident entry)
        dip_size = signal.dip_size or 0
        if dip_size >= 0.15:  # 15%+ dip
            size = capital * self.config.max_position_pct
        elif dip_size >= 0.10:  # 10%+ dip
            size = capital * (self.config.base_position_pct + 0.03)
        else:
            size = base_size
        
        # Boost for positive Grok signal
        if signal.grok_direction == 'up':
            size *= 1.1
        
        # Apply min/max constraints
        size = max(self.config.min_position, min(self.config.max_position, size))
        
        # Don't exceed available capital
        size = min(size, capital * 0.95)
        
        return round(size, 2)
    
    def clear_position_high(self, market_id: str):
        """Clear the tracked high for a position (after closing)."""
        if market_id in self.position_highs:
            del self.position_highs[market_id]


def create_swing_strategy(config: Optional[SwingConfig] = None) -> SwingStrategy:
    """Create a swing strategy instance with default or custom config."""
    return SwingStrategy(config)


# Default conservative config (HYBRID: requires positive sentiment)
CONSERVATIVE_CONFIG = SwingConfig(
    min_dip_pct=0.08,
    take_profit_pct=0.08,  # 8% gross, ~6% net after fees
    stop_loss_pct=0.15,
    max_hold_hours=24,
    use_trailing_stop=True,
    trailing_stop_pct=0.05,
    min_sentiment_score=0.1,  # KEY: Filter out dead cat bounces
)

# More aggressive config
AGGRESSIVE_CONFIG = SwingConfig(
    min_dip_pct=0.05,
    take_profit_pct=0.12,
    stop_loss_pct=0.20,
    max_hold_hours=48,
    use_trailing_stop=True,
    trailing_stop_pct=0.08,
    max_position_pct=0.20,
)
