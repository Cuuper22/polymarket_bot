"""
Position Sizing & Risk Management - Critical for small bankroll
Implements Kelly Criterion with safety adjustments
"""
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import math

logger = logging.getLogger(__name__)


@dataclass
class PositionSize:
    """Recommended position size with details."""
    amount: float  # Dollar amount to bet
    shares: float  # Number of shares at current price
    kelly_fraction: float  # Raw Kelly fraction
    adjusted_fraction: float  # Safety-adjusted fraction
    max_loss: float  # Maximum loss if wrong
    expected_profit: float  # Expected profit if right
    expected_value: float  # Overall expected value
    risk_reward_ratio: float
    reason: str


@dataclass
class PortfolioRisk:
    """Current portfolio risk metrics."""
    total_capital: float
    available_capital: float
    invested_capital: float
    num_positions: int
    max_position_size: float
    current_drawdown: float
    max_drawdown_allowed: float
    is_trading_allowed: bool
    reason: str


class KellyPositionSizer:
    """
    Implements Kelly Criterion for optimal position sizing.
    
    Kelly formula: f* = (bp - q) / b
    Where:
        f* = fraction of bankroll to bet
        b = odds received (payout ratio)
        p = probability of winning
        q = probability of losing (1 - p)
    
    For binary markets where you buy at price P:
        - If you win, you get $1 per share (profit = 1 - P)
        - If you lose, you lose P per share
        - b = (1 - P) / P
    """
    
    def __init__(self,
                 kelly_fraction: float = 0.25,  # Quarter Kelly
                 max_position_pct: float = 0.15,  # Max 15% per trade
                 min_position: float = 1.0,  # Minimum $1
                 max_positions: int = 5):  # Max concurrent positions
        """
        Args:
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
            max_position_pct: Maximum position as % of capital
            min_position: Minimum position size in dollars
            max_positions: Maximum number of concurrent positions
        """
        self.kelly_fraction = kelly_fraction
        self.max_position_pct = max_position_pct
        self.min_position = min_position
        self.max_positions = max_positions
    
    def calculate_kelly(self, win_probability: float, 
                       current_price: float) -> float:
        """
        Calculate raw Kelly fraction.
        
        Args:
            win_probability: Estimated probability of winning (0 to 1)
            current_price: Price to buy at (0 to 1)
        
        Returns:
            Optimal fraction of bankroll to bet
        """
        if current_price <= 0 or current_price >= 1:
            return 0
        
        # Binary market odds
        # If win: profit = 1 - price
        # If lose: loss = price
        b = (1 - current_price) / current_price  # Payout ratio
        if b < 0.01:
            return 0
        
        p = win_probability
        q = 1 - p
        
        # Kelly formula
        kelly = (b * p - q) / b
        
        # Kelly can be negative (don't bet) or > 1 (bet more than 100%)
        # Clamp to reasonable range
        kelly = max(0, min(1, kelly))
        
        return kelly
    
    def calculate_position(self, 
                          capital: float,
                          current_price: float,
                          edge: float,
                          confidence: float,
                          existing_positions: int = 0,
                          existing_exposure: float = 0) -> PositionSize:
        """
        Calculate recommended position size.
        
        Args:
            capital: Total capital available
            current_price: Price to buy at
            edge: Estimated edge (expected return)
            confidence: Confidence in the edge estimate
            existing_positions: Number of existing positions
            existing_exposure: Total $ in existing positions
        
        Returns:
            PositionSize with recommendation
        """
        # Estimate win probability from edge
        # If edge is 10%, and price is 50%, fair value is 60%
        fair_value = current_price + edge
        fair_value = max(0.05, min(0.95, fair_value))
        
        # Use confidence-weighted probability
        # Blend between fair value and 50% based on confidence
        win_probability = fair_value * confidence + 0.5 * (1 - confidence)
        
        # Calculate raw Kelly
        raw_kelly = self.calculate_kelly(win_probability, current_price)
        
        if raw_kelly <= 0:
            return PositionSize(
                amount=0,
                shares=0,
                kelly_fraction=raw_kelly,
                adjusted_fraction=0,
                max_loss=0,
                expected_profit=0,
                expected_value=0,
                risk_reward_ratio=0,
                reason="No positive edge (Kelly <= 0)"
            )
        
        # Apply fractional Kelly
        adjusted_kelly = raw_kelly * self.kelly_fraction
        
        # Apply maximum position constraint
        max_by_capital = self.max_position_pct
        adjusted_kelly = min(adjusted_kelly, max_by_capital)
        
        # Check position limits
        if existing_positions >= self.max_positions:
            return PositionSize(
                amount=0,
                shares=0,
                kelly_fraction=raw_kelly,
                adjusted_fraction=0,
                max_loss=0,
                expected_profit=0,
                expected_value=0,
                risk_reward_ratio=0,
                reason=f"Max positions ({self.max_positions}) reached"
            )
        
        # Calculate available capital
        available = capital - existing_exposure
        
        # Calculate position size
        position_amount = available * adjusted_kelly
        
        # Apply minimum
        if position_amount < self.min_position:
            if available >= self.min_position and raw_kelly > 0.02:
                # Use minimum if we have edge but Kelly is small
                position_amount = self.min_position
            else:
                return PositionSize(
                    amount=0,
                    shares=0,
                    kelly_fraction=raw_kelly,
                    adjusted_fraction=adjusted_kelly,
                    max_loss=0,
                    expected_profit=0,
                    expected_value=0,
                    risk_reward_ratio=0,
                    reason=f"Position too small (< ${self.min_position})"
                )
        
        # Cap at available capital
        position_amount = min(position_amount, available)
        
        # Calculate shares
        shares = position_amount / current_price
        
        # Calculate risk/reward
        max_loss = position_amount  # Lose entire bet
        expected_profit = position_amount * (1 / current_price - 1)  # If win
        expected_value = expected_profit * win_probability - max_loss * (1 - win_probability)
        risk_reward = expected_profit / max_loss if max_loss > 0 else 0
        
        return PositionSize(
            amount=round(position_amount, 2),
            shares=round(shares, 2),
            kelly_fraction=raw_kelly,
            adjusted_fraction=adjusted_kelly,
            max_loss=round(max_loss, 2),
            expected_profit=round(expected_profit, 2),
            expected_value=round(expected_value, 2),
            risk_reward_ratio=round(risk_reward, 2),
            reason=f"Kelly: {raw_kelly:.1%} -> {adjusted_kelly:.1%} after {self.kelly_fraction:.0%} reduction"
        )


class RiskManager:
    """
    Manages overall portfolio risk.
    """
    
    def __init__(self,
                 starting_capital: float,
                 max_drawdown: float = 0.30,  # 30% max drawdown
                 max_daily_loss: float = 0.10,  # 10% max daily loss
                 max_position_pct: float = 0.15,
                 max_positions: int = 5):
        """
        Args:
            starting_capital: Initial capital
            max_drawdown: Maximum allowed drawdown before stopping
            max_daily_loss: Maximum daily loss allowed
            max_position_pct: Maximum single position size
            max_positions: Maximum concurrent positions
        """
        self.starting_capital = starting_capital
        self.max_drawdown = max_drawdown
        self.max_daily_loss = max_daily_loss
        self.max_position_pct = max_position_pct
        self.max_positions = max_positions
        
        # Track state
        self.current_capital = starting_capital
        self.high_water_mark = starting_capital
        self.positions: Dict[str, Dict] = {}  # market_id -> position info
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
    
    def update_capital(self, new_capital: float):
        """Update current capital level."""
        self.current_capital = new_capital
        if new_capital > self.high_water_mark:
            self.high_water_mark = new_capital
    
    def record_trade_result(self, pnl: float):
        """Record a trade result."""
        # Reset daily PnL if new day
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_pnl = 0
            self.last_reset_date = today
        
        self.daily_pnl += pnl
        self.current_capital += pnl
        
        if self.current_capital > self.high_water_mark:
            self.high_water_mark = self.current_capital
    
    def add_position(self, market_id: str, amount: float, 
                    price: float, direction: str):
        """Add a position to tracking."""
        self.positions[market_id] = {
            'amount': amount,
            'entry_price': price,
            'direction': direction,
            'entry_time': datetime.now(),
        }
    
    def remove_position(self, market_id: str):
        """Remove a position from tracking."""
        if market_id in self.positions:
            del self.positions[market_id]
    
    def get_portfolio_risk(self) -> PortfolioRisk:
        """Get current portfolio risk status."""
        # Calculate invested capital
        invested = sum(p['amount'] for p in self.positions.values())
        available = self.current_capital - invested
        
        # Calculate drawdown
        if self.high_water_mark > 0:
            drawdown = (self.high_water_mark - self.current_capital) / self.high_water_mark
        else:
            drawdown = 0
        
        # Check if trading is allowed
        is_allowed = True
        reason = "Trading allowed"
        
        if drawdown >= self.max_drawdown:
            is_allowed = False
            reason = f"Max drawdown ({self.max_drawdown:.0%}) exceeded"
        elif self.daily_pnl / self.starting_capital <= -self.max_daily_loss:
            is_allowed = False
            reason = f"Max daily loss ({self.max_daily_loss:.0%}) exceeded"
        elif len(self.positions) >= self.max_positions:
            is_allowed = False
            reason = f"Max positions ({self.max_positions}) reached"
        elif available < 1.0:
            is_allowed = False
            reason = "Insufficient available capital"
        
        return PortfolioRisk(
            total_capital=self.current_capital,
            available_capital=max(0, available),
            invested_capital=invested,
            num_positions=len(self.positions),
            max_position_size=self.current_capital * self.max_position_pct,
            current_drawdown=drawdown,
            max_drawdown_allowed=self.max_drawdown,
            is_trading_allowed=is_allowed,
            reason=reason,
        )
    
    def can_open_position(self, amount: float) -> Tuple[bool, str]:
        """Check if a new position can be opened."""
        risk = self.get_portfolio_risk()
        
        if not risk.is_trading_allowed:
            return False, risk.reason
        
        if amount > risk.available_capital:
            return False, f"Insufficient capital (need ${amount:.2f}, have ${risk.available_capital:.2f})"
        
        if amount > risk.max_position_size:
            return False, f"Position too large (max ${risk.max_position_size:.2f})"
        
        return True, "OK"
    
    def get_position_summary(self) -> Dict:
        """Get summary of current positions."""
        return {
            'positions': list(self.positions.keys()),
            'count': len(self.positions),
            'total_invested': sum(p['amount'] for p in self.positions.values()),
            'details': self.positions.copy(),
        }


class SmallBankrollOptimizer:
    """
    Special optimizations for small bankrolls ($50-$100).
    """
    
    def __init__(self, capital: float):
        self.capital = capital
        
        # Adjusted parameters for small bankroll
        if capital < 50:
            self.kelly_fraction = 0.15  # Very conservative
            self.max_position_pct = 0.10
            self.min_position = 0.50
            self.max_positions = 3
            self.min_edge = 0.10
        elif capital < 100:
            self.kelly_fraction = 0.20
            self.max_position_pct = 0.12
            self.min_position = 1.0
            self.max_positions = 4
            self.min_edge = 0.08
        else:
            self.kelly_fraction = 0.25
            self.max_position_pct = 0.15
            self.min_position = 1.0
            self.max_positions = 5
            self.min_edge = 0.06
    
    def get_position_sizer(self) -> KellyPositionSizer:
        """Get optimized position sizer for this bankroll."""
        return KellyPositionSizer(
            kelly_fraction=self.kelly_fraction,
            max_position_pct=self.max_position_pct,
            min_position=self.min_position,
            max_positions=self.max_positions,
        )
    
    def get_risk_manager(self) -> RiskManager:
        """Get optimized risk manager for this bankroll."""
        return RiskManager(
            starting_capital=self.capital,
            max_drawdown=0.25,  # Tighter for small bankroll
            max_daily_loss=0.08,
            max_position_pct=self.max_position_pct,
            max_positions=self.max_positions,
        )
    
    def optimize_for_growth(self) -> Dict:
        """Get recommended settings for growth focus."""
        return {
            'strategy': 'growth',
            'kelly_fraction': self.kelly_fraction,
            'max_position_pct': self.max_position_pct,
            'min_edge': self.min_edge,
            'min_confidence': 0.60,
            'focus': [
                'high_volume_markets',
                'strong_sentiment_divergence',
                'breaking_news_catalyst',
            ],
            'avoid': [
                'low_liquidity',
                'long_expiry',
                'extreme_prices',
            ],
        }
    
    def optimize_for_preservation(self) -> Dict:
        """Get recommended settings for capital preservation."""
        return {
            'strategy': 'preservation',
            'kelly_fraction': self.kelly_fraction * 0.6,
            'max_position_pct': self.max_position_pct * 0.7,
            'min_edge': 0.12,  # Require even higher edge
            'min_confidence': 0.70,
            'focus': [
                'very_high_confidence',
                'confirmed_news',
                'high_liquidity',
            ],
            'avoid': [
                'any_uncertainty',
                'volatile_markets',
                'near_expiry',
            ],
        }


# Convenience functions
def calculate_optimal_bet(capital: float, price: float, 
                         edge: float, confidence: float) -> PositionSize:
    """Quick function to calculate optimal bet size."""
    sizer = SmallBankrollOptimizer(capital).get_position_sizer()
    return sizer.calculate_position(capital, price, edge, confidence)


def is_bet_worthwhile(edge: float, price: float, min_edge: float = 0.05) -> bool:
    """Check if a bet is worthwhile based on edge."""
    # Edge should be higher for extreme prices (more risk)
    if price < 0.15 or price > 0.85:
        required_edge = min_edge * 1.5
    else:
        required_edge = min_edge
    
    return edge >= required_edge
