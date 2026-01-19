"""
AGGRESSIVE GROWTH STRATEGY - Target 10%+ Weekly Returns
========================================================
Optimized parameters for Polymarket prediction market trading

WARNING: This is an aggressive strategy with higher risk.
Paper trade extensively before deploying real capital.

Expected Weekly Return: 8-15% (target 10%+)
Maximum Expected Drawdown: 25-35%
Capital Requirement: $50-$200 (optimized for small bankrolls)
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class StrategyMode(Enum):
    """Strategy intensity levels."""
    CONSERVATIVE = "conservative"  # 3-5% weekly target
    MODERATE = "moderate"          # 5-8% weekly target
    AGGRESSIVE = "aggressive"      # 10-15% weekly target
    ULTRA_AGGRESSIVE = "ultra"     # 15-25% weekly target (very high risk)


@dataclass
class EntryParameters:
    """
    ENTRY CRITERIA - Optimized for High-Probability Setups
    ======================================================
    """
    # === EDGE THRESHOLDS (Critical for 10%+ returns) ===
    min_edge_threshold: float = 0.12          # Minimum 12% edge to enter (was 5%)
    optimal_edge_threshold: float = 0.18      # Sweet spot: 18% edge
    max_edge_threshold: float = 0.40          # Cap at 40% (likely mispriced data)
    
    # === CONFIDENCE LEVELS ===
    min_confidence: float = 0.65              # Minimum 65% confidence (was 60%)
    optimal_confidence: float = 0.75          # Target 75%+ confidence
    required_confidence_for_max_size: float = 0.80  # Need 80% for full Kelly
    
    # === SIGNAL REQUIREMENTS ===
    min_signals_required: int = 2             # Require 2+ confirming signals
    signal_agreement_threshold: float = 0.70  # 70%+ signals must agree on direction
    
    # === PRICE ZONE FILTERS ===
    min_price: float = 0.15                   # Avoid < 15 cents (too volatile)
    max_price: float = 0.85                   # Avoid > 85 cents (limited upside)
    optimal_price_range: tuple = (0.25, 0.65) # Best risk/reward zone
    
    # === MARKET QUALITY FILTERS ===
    min_volume_24h: float = 1000.0           # Minimum $1K 24h volume
    optimal_volume_24h: float = 5000.0       # Prefer $5K+ volume
    min_liquidity: float = 500.0             # Minimum $500 liquidity
    max_spread: float = 0.08                 # Maximum 8% bid-ask spread
    
    # === TIMING FILTERS ===
    min_hours_to_expiry: int = 48            # At least 48 hours to resolution
    optimal_hours_to_expiry: int = 168       # 1 week ideal (time for edge to realize)
    max_hours_to_expiry: int = 720           # Cap at 30 days (opportunity cost)
    
    # === NEWS CATALYST REQUIREMENTS ===
    max_news_age_hours: float = 4.0          # News must be < 4 hours old (was 6)
    require_high_priority_news: bool = True  # Require "breaking/confirmed" keywords
    min_news_relevance_score: float = 0.60   # 60%+ keyword match to market
    
    def validate_entry(self, opportunity: Dict) -> tuple[bool, str, float]:
        """
        Validate if opportunity meets entry criteria.
        
        Returns:
            (is_valid, reason, quality_score)
        """
        edge = opportunity.get('edge', 0)
        confidence = opportunity.get('confidence', 0)
        price = opportunity.get('current_price', 0.5)
        volume = opportunity.get('volume_24h', 0)
        liquidity = opportunity.get('liquidity', 0)
        signals = opportunity.get('signal_count', 0)
        
        # Check edge
        if edge < self.min_edge_threshold:
            return False, f"Edge {edge:.1%} below minimum {self.min_edge_threshold:.1%}", 0
        if edge > self.max_edge_threshold:
            return False, f"Edge {edge:.1%} suspiciously high", 0
        
        # Check confidence
        if confidence < self.min_confidence:
            return False, f"Confidence {confidence:.1%} below minimum {self.min_confidence:.1%}", 0
        
        # Check price zone
        if price < self.min_price or price > self.max_price:
            return False, f"Price {price:.2f} outside valid range", 0
        
        # Check liquidity
        if liquidity < self.min_liquidity:
            return False, f"Liquidity ${liquidity:.0f} below minimum ${self.min_liquidity:.0f}", 0
        
        # Check signals
        if signals < self.min_signals_required:
            return False, f"Only {signals} signals, need {self.min_signals_required}+", 0
        
        # Calculate quality score (0-100)
        quality = 0
        
        # Edge contribution (max 35 points)
        edge_score = min(35, (edge - self.min_edge_threshold) / 0.20 * 35)
        quality += edge_score
        
        # Confidence contribution (max 25 points)
        conf_score = min(25, (confidence - self.min_confidence) / 0.25 * 25)
        quality += conf_score
        
        # Price zone (max 15 points)
        if self.optimal_price_range[0] <= price <= self.optimal_price_range[1]:
            quality += 15
        else:
            quality += 8
        
        # Volume/liquidity (max 15 points)
        if volume >= self.optimal_volume_24h:
            quality += 15
        elif volume >= self.min_volume_24h:
            quality += 10
        
        # Signals (max 10 points)
        quality += min(10, signals * 3)
        
        return True, "Valid entry", quality


@dataclass  
class PositionSizingParameters:
    """
    POSITION SIZING - Kelly-Optimized for Aggressive Growth
    ========================================================
    """
    # === KELLY CRITERION SETTINGS ===
    kelly_fraction: float = 0.35              # 35% Kelly (was 25% - more aggressive)
    min_kelly_for_trade: float = 0.05         # Minimum 5% Kelly to take trade
    max_kelly_cap: float = 0.50               # Never exceed 50% Kelly
    
    # === POSITION LIMITS ===
    max_position_pct: float = 0.20            # Max 20% of capital per position (was 15%)
    min_position_dollars: float = 2.0         # Minimum $2 per trade
    max_position_dollars: float = 50.0        # Cap at $50 per trade (for small bankroll)
    
    # === SCALING BY CONFIDENCE ===
    # Scale position by confidence level
    confidence_scaling: Dict = field(default_factory=lambda: {
        0.65: 0.60,   # 65% confidence = 60% of calculated size
        0.70: 0.75,   # 70% confidence = 75% of calculated size
        0.75: 0.85,   # 75% confidence = 85% of calculated size
        0.80: 1.00,   # 80%+ confidence = full calculated size
        0.85: 1.10,   # 85%+ confidence = 110% (slight boost)
        0.90: 1.20,   # 90%+ confidence = 120% (rare but aggressive)
    })
    
    # === SCALING BY EDGE ===
    edge_scaling: Dict = field(default_factory=lambda: {
        0.12: 0.70,   # 12% edge = 70% of calculated size
        0.15: 0.85,   # 15% edge = 85% of calculated size
        0.18: 1.00,   # 18%+ edge = full size
        0.22: 1.15,   # 22%+ edge = 115%
        0.28: 1.25,   # 28%+ edge = 125%
    })
    
    def calculate_aggressive_position(self, 
                                      capital: float,
                                      price: float,
                                      edge: float,
                                      confidence: float) -> Dict:
        """
        Calculate optimal position size for aggressive growth.
        
        Args:
            capital: Available capital
            price: Current market price (0-1)
            edge: Estimated edge (0-1)
            confidence: Confidence level (0-1)
        
        Returns:
            Dict with position sizing details
        """
        # Calculate raw Kelly
        fair_value = price + edge
        fair_value = max(0.05, min(0.95, fair_value))
        
        # Blend probability with confidence
        win_prob = fair_value * confidence + 0.5 * (1 - confidence)
        
        # Kelly formula for binary outcomes
        b = (1 - price) / price  # Payout ratio
        raw_kelly = (b * win_prob - (1 - win_prob)) / b
        raw_kelly = max(0, min(1, raw_kelly))
        
        if raw_kelly < self.min_kelly_for_trade:
            return {
                'amount': 0,
                'shares': 0,
                'kelly': raw_kelly,
                'reason': f"Kelly {raw_kelly:.1%} below threshold"
            }
        
        # Apply fractional Kelly
        adjusted_kelly = raw_kelly * self.kelly_fraction
        adjusted_kelly = min(adjusted_kelly, self.max_kelly_cap)
        
        # Apply confidence scaling
        conf_scale = 1.0
        for threshold, scale in sorted(self.confidence_scaling.items(), reverse=True):
            if confidence >= threshold:
                conf_scale = scale
                break
        
        # Apply edge scaling
        edge_scale = 1.0
        for threshold, scale in sorted(self.edge_scaling.items(), reverse=True):
            if edge >= threshold:
                edge_scale = scale
                break
        
        # Calculate final position
        position_pct = adjusted_kelly * conf_scale * edge_scale
        position_pct = min(position_pct, self.max_position_pct)
        
        amount = capital * position_pct
        amount = max(self.min_position_dollars, amount)
        amount = min(self.max_position_dollars, amount)
        amount = min(amount, capital * 0.95)  # Never bet more than 95% of capital
        
        shares = amount / price
        
        return {
            'amount': round(amount, 2),
            'shares': round(shares, 2),
            'kelly': raw_kelly,
            'adjusted_kelly': adjusted_kelly,
            'position_pct': position_pct,
            'confidence_scale': conf_scale,
            'edge_scale': edge_scale,
            'expected_value': round(amount * edge * confidence, 2),
            'max_loss': round(amount, 2),
            'max_profit': round(amount * (1/price - 1), 2),
        }


@dataclass
class ExitParameters:
    """
    EXIT STRATEGY - Optimized for Profit Capture
    =============================================
    """
    # === TAKE PROFIT RULES ===
    take_profit_pct: float = 0.40             # Exit at 40% profit (was 50%)
    trailing_stop_activation: float = 0.25    # Activate trailing stop at 25% profit
    trailing_stop_distance: float = 0.15      # Trail by 15% from peak
    
    # === PARTIAL EXIT RULES ===
    partial_exit_1_pct: float = 0.30          # Take 30% off at first target
    partial_exit_1_target: float = 0.25       # First target: 25% profit
    partial_exit_2_pct: float = 0.30          # Take another 30% at second target
    partial_exit_2_target: float = 0.45       # Second target: 45% profit
    # Remaining 40% rides with trailing stop
    
    # === STOP LOSS RULES ===
    hard_stop_loss_pct: float = 0.35          # Hard stop at 35% loss (was 50%)
    time_stop_hours: int = 120                # Exit if no movement in 5 days
    
    # === EDGE DECAY EXIT ===
    exit_if_edge_below: float = 0.03          # Exit if edge drops below 3%
    exit_if_confidence_below: float = 0.45    # Exit if confidence drops below 45%
    
    # === MARKET CONDITION EXITS ===
    exit_on_resolution_approach: int = 12     # Exit 12 hours before resolution
    exit_on_volume_collapse: float = 0.20     # Exit if volume drops to 20% of entry
    
    def get_exit_action(self, position: Dict, current_market: Dict) -> Dict:
        """
        Determine exit action for a position.
        
        Returns:
            Dict with exit action and details
        """
        entry_price = position.get('entry_price', 0.5)
        current_price = current_market.get('price', entry_price)
        amount = position.get('amount', 0)
        peak_price = position.get('peak_price', current_price)
        hours_held = position.get('hours_held', 0)
        
        # Calculate P&L
        if position.get('direction') == 'YES':
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        action = {'action': 'hold', 'reason': 'No exit trigger', 'size': 0}
        
        # Check hard stop loss
        if pnl_pct <= -self.hard_stop_loss_pct:
            return {
                'action': 'exit_all',
                'reason': f'Hard stop loss triggered at {pnl_pct:.1%}',
                'size': 1.0,
                'urgency': 'high'
            }
        
        # Check time stop
        if hours_held >= self.time_stop_hours and abs(pnl_pct) < 0.10:
            return {
                'action': 'exit_all',
                'reason': f'Time stop: {hours_held}h with minimal movement',
                'size': 1.0,
                'urgency': 'medium'
            }
        
        # Check trailing stop (if activated)
        if pnl_pct >= self.trailing_stop_activation:
            peak_pnl = (peak_price - entry_price) / entry_price
            drawdown_from_peak = peak_pnl - pnl_pct
            
            if drawdown_from_peak >= self.trailing_stop_distance:
                return {
                    'action': 'exit_all',
                    'reason': f'Trailing stop: {self.trailing_stop_distance:.0%} pullback from peak',
                    'size': 1.0,
                    'urgency': 'high'
                }
        
        # Check take profit
        if pnl_pct >= self.take_profit_pct:
            return {
                'action': 'exit_all',
                'reason': f'Take profit at {pnl_pct:.1%}',
                'size': 1.0,
                'urgency': 'medium'
            }
        
        # Check partial exits
        if pnl_pct >= self.partial_exit_2_target and position.get('partial_exits', 0) < 2:
            return {
                'action': 'partial_exit',
                'reason': f'Partial exit 2 at {pnl_pct:.1%}',
                'size': self.partial_exit_2_pct,
                'urgency': 'low'
            }
        
        if pnl_pct >= self.partial_exit_1_target and position.get('partial_exits', 0) < 1:
            return {
                'action': 'partial_exit',
                'reason': f'Partial exit 1 at {pnl_pct:.1%}',
                'size': self.partial_exit_1_pct,
                'urgency': 'low'
            }
        
        return action


@dataclass
class PortfolioParameters:
    """
    PORTFOLIO CONSTRUCTION - Diversified Aggressive Growth
    ======================================================
    """
    # === POSITION LIMITS ===
    max_open_positions: int = 6               # Max 6 concurrent positions (was 5)
    min_open_positions: int = 3               # Maintain at least 3 positions when possible
    
    # === CAPITAL ALLOCATION ===
    max_total_exposure_pct: float = 0.85      # Max 85% of capital deployed
    reserve_capital_pct: float = 0.15         # Keep 15% as reserve
    
    # === CORRELATION MANAGEMENT ===
    max_same_category: int = 2                # Max 2 positions in same category (crypto, politics, etc.)
    max_same_direction: int = 4               # Max 4 positions all YES or all NO
    
    # === REBALANCING RULES ===
    rebalance_if_position_exceeds: float = 0.35  # Trim if position grows to 35%+ of portfolio
    rebalance_target_pct: float = 0.20           # Trim back to 20%
    
    # === OPPORTUNITY COST MANAGEMENT ===
    min_score_for_new_position: float = 65.0  # Minimum quality score for new positions
    replace_position_if_score_delta: float = 20.0  # Replace if new opp scores 20+ higher
    
    def get_portfolio_action(self, 
                            current_positions: List[Dict],
                            new_opportunity: Optional[Dict] = None,
                            capital: float = 0) -> Dict:
        """
        Determine portfolio action.
        
        Returns:
            Dict with recommended action
        """
        num_positions = len(current_positions)
        total_invested = sum(p.get('amount', 0) for p in current_positions)
        exposure_pct = total_invested / capital if capital > 0 else 0
        
        action = {
            'can_add_position': False,
            'should_reduce': False,
            'positions_to_trim': [],
            'reason': ''
        }
        
        # Check if we can add new position
        if num_positions < self.max_open_positions and exposure_pct < self.max_total_exposure_pct:
            action['can_add_position'] = True
        
        # Check for positions to trim
        for pos in current_positions:
            pos_value = pos.get('current_value', pos.get('amount', 0))
            pos_pct = pos_value / capital if capital > 0 else 0
            
            if pos_pct > self.rebalance_if_position_exceeds:
                action['positions_to_trim'].append({
                    'market_id': pos.get('market_id'),
                    'current_pct': pos_pct,
                    'target_pct': self.rebalance_target_pct,
                    'trim_pct': pos_pct - self.rebalance_target_pct
                })
                action['should_reduce'] = True
        
        return action


@dataclass
class PerformanceTargets:
    """
    PERFORMANCE TARGETS & METRICS
    =============================
    """
    # === WEEKLY TARGETS ===
    target_weekly_return: float = 0.10        # 10%+ weekly return target
    min_weekly_return: float = 0.05           # Minimum 5% to consider week successful
    
    # === TRADE-LEVEL TARGETS ===
    target_win_rate: float = 0.58             # Target 58% win rate
    min_win_rate: float = 0.52                # Minimum 52% (must be profitable long-term)
    target_avg_win_pct: float = 0.45          # Average winning trade: +45%
    target_avg_loss_pct: float = 0.28         # Average losing trade: -28%
    target_profit_factor: float = 1.75        # Gross profits / Gross losses
    
    # === ACTIVITY TARGETS ===
    target_trades_per_week: int = 12          # Target 12 trades per week
    min_trades_per_week: int = 6              # Minimum 6 trades per week
    max_trades_per_week: int = 20             # Maximum 20 trades per week (avoid overtrading)
    
    # === RISK TARGETS ===
    max_drawdown_pct: float = 0.30            # Maximum 30% drawdown before pause
    max_daily_loss_pct: float = 0.12          # Maximum 12% loss in single day
    max_consecutive_losses: int = 5           # Pause after 5 consecutive losses
    
    # === R-MULTIPLE TARGETS ===
    # R = risk per trade (amount risked)
    target_r_multiple: float = 1.5            # Average trade should make 1.5R
    min_risk_reward: float = 1.2              # Minimum 1.2:1 risk/reward to enter
    
    # === EXPECTED STATISTICS (Based on targets) ===
    @property
    def expected_edge_per_trade(self) -> float:
        """Expected edge per trade based on win rate and outcomes."""
        # E = (Win% * AvgWin) - (Loss% * AvgLoss)
        return (self.target_win_rate * self.target_avg_win_pct) - \
               ((1 - self.target_win_rate) * self.target_avg_loss_pct)
    
    @property 
    def expected_weekly_return(self) -> float:
        """Expected weekly return based on trade targets."""
        edge_per_trade = self.expected_edge_per_trade
        avg_position_size = 0.12  # 12% of capital per trade
        return edge_per_trade * self.target_trades_per_week * avg_position_size
    
    def is_on_track(self, actual_metrics: Dict) -> Dict:
        """
        Check if actual performance is on track.
        
        Returns:
            Dict with status and recommendations
        """
        status = {
            'on_track': True,
            'warnings': [],
            'recommendations': []
        }
        
        # Check win rate
        actual_wr = actual_metrics.get('win_rate', 0)
        if actual_wr < self.min_win_rate:
            status['on_track'] = False
            status['warnings'].append(f'Win rate {actual_wr:.1%} below minimum {self.min_win_rate:.1%}')
            status['recommendations'].append('Increase edge threshold or improve signal quality')
        
        # Check drawdown
        actual_dd = actual_metrics.get('drawdown', 0)
        if actual_dd > self.max_drawdown_pct * 0.8:  # Warning at 80% of max
            status['warnings'].append(f'Drawdown {actual_dd:.1%} approaching maximum')
            status['recommendations'].append('Reduce position sizes or pause trading')
        
        # Check trade frequency
        trades_this_week = actual_metrics.get('trades_this_week', 0)
        if trades_this_week < self.min_trades_per_week:
            status['warnings'].append(f'Only {trades_this_week} trades this week')
            status['recommendations'].append('Consider lowering edge threshold slightly')
        elif trades_this_week > self.max_trades_per_week:
            status['warnings'].append(f'{trades_this_week} trades may indicate overtrading')
            status['recommendations'].append('Increase quality filters')
        
        return status


@dataclass
class TradingRules:
    """
    TRADING RULES - Complete Ruleset
    ================================
    """
    # === RULE CATEGORIES ===
    
    # Pre-Trade Rules
    pre_trade_rules: List[str] = field(default_factory=lambda: [
        "Verify edge >= 12% before ANY trade",
        "Confirm minimum 2 agreeing signals",
        "Check portfolio has room for new position",
        "Ensure liquidity >= $500",
        "Verify bid-ask spread <= 8%",
        "Confirm time to expiry >= 48 hours",
        "News catalyst must be < 4 hours old",
        "Never chase - wait for next opportunity if missed",
    ])
    
    # Position Management Rules
    position_rules: List[str] = field(default_factory=lambda: [
        "Use fractional Kelly (35%) for position sizing",
        "Never risk more than 20% on single position",
        "Scale in: 70% initial, 30% on confirmation",
        "Set stop loss at entry: 35% max loss",
        "Update trailing stop when profit > 25%",
        "Take 30% profit at 25% gain",
        "Take another 30% at 45% gain",
        "Let final 40% ride with trailing stop",
    ])
    
    # Portfolio Rules
    portfolio_rules: List[str] = field(default_factory=lambda: [
        "Maximum 6 concurrent positions",
        "Keep 15% capital in reserve always",
        "Max 2 positions in same category",
        "Rebalance if any position exceeds 35%",
        "Replace weakest position if better opportunity (20+ quality delta)",
        "Review portfolio daily for edge decay",
    ])
    
    # Risk Management Rules
    risk_rules: List[str] = field(default_factory=lambda: [
        "STOP trading if drawdown exceeds 30%",
        "STOP trading if 5 consecutive losses",
        "Reduce position size by 50% after 3 consecutive losses",
        "Maximum 12% loss in single day",
        "Never average down on losing positions",
        "If uncertain, DO NOT trade",
    ])
    
    # Exit Rules
    exit_rules: List[str] = field(default_factory=lambda: [
        "Exit ALL positions if edge drops below 3%",
        "Exit if confidence drops below 45%",
        "Exit 12 hours before market resolution",
        "Exit if volume collapses to 20% of entry level",
        "Exit on hard stop: 35% loss",
        "Exit on time stop: 120 hours with <10% movement",
        "Take profits - don't be greedy",
    ])


# === COMPLETE STRATEGY CONFIGURATION ===

@dataclass
class AggressiveGrowthStrategy:
    """
    Complete optimized strategy configuration for 10%+ weekly returns.
    """
    name: str = "Aggressive Growth Strategy v1.0"
    target_return: str = "10%+ weekly"
    risk_level: str = "HIGH"
    
    entry: EntryParameters = field(default_factory=EntryParameters)
    position_sizing: PositionSizingParameters = field(default_factory=PositionSizingParameters)
    exit: ExitParameters = field(default_factory=ExitParameters)
    portfolio: PortfolioParameters = field(default_factory=PortfolioParameters)
    targets: PerformanceTargets = field(default_factory=PerformanceTargets)
    rules: TradingRules = field(default_factory=TradingRules)
    
    def get_summary(self) -> Dict:
        """Get strategy summary."""
        return {
            'name': self.name,
            'target_return': self.target_return,
            'risk_level': self.risk_level,
            
            # Entry Summary
            'entry': {
                'min_edge': f"{self.entry.min_edge_threshold:.0%}",
                'min_confidence': f"{self.entry.min_confidence:.0%}",
                'min_signals': self.entry.min_signals_required,
                'price_range': f"{self.entry.min_price:.0%}-{self.entry.max_price:.0%}",
            },
            
            # Position Sizing Summary
            'position_sizing': {
                'kelly_fraction': f"{self.position_sizing.kelly_fraction:.0%}",
                'max_position': f"{self.position_sizing.max_position_pct:.0%}",
                'min_position': f"${self.position_sizing.min_position_dollars}",
            },
            
            # Exit Summary
            'exit': {
                'take_profit': f"{self.exit.take_profit_pct:.0%}",
                'stop_loss': f"{self.exit.hard_stop_loss_pct:.0%}",
                'trailing_stop': f"{self.exit.trailing_stop_distance:.0%}",
            },
            
            # Portfolio Summary
            'portfolio': {
                'max_positions': self.portfolio.max_open_positions,
                'max_exposure': f"{self.portfolio.max_total_exposure_pct:.0%}",
            },
            
            # Targets Summary
            'targets': {
                'win_rate': f"{self.targets.target_win_rate:.0%}",
                'trades_per_week': self.targets.target_trades_per_week,
                'profit_factor': self.targets.target_profit_factor,
                'max_drawdown': f"{self.targets.max_drawdown_pct:.0%}",
            }
        }
    
    def print_rules(self):
        """Print all trading rules."""
        print("\n" + "=" * 60)
        print("AGGRESSIVE GROWTH STRATEGY - TRADING RULES")
        print("=" * 60)
        
        print("\n[PRE-TRADE CHECKLIST]")
        for i, rule in enumerate(self.rules.pre_trade_rules, 1):
            print(f"  {i}. {rule}")
        
        print("\n[POSITION MANAGEMENT]")
        for i, rule in enumerate(self.rules.position_rules, 1):
            print(f"  {i}. {rule}")
        
        print("\n[PORTFOLIO RULES]")
        for i, rule in enumerate(self.rules.portfolio_rules, 1):
            print(f"  {i}. {rule}")
        
        print("\n[RISK MANAGEMENT - CRITICAL]")
        for i, rule in enumerate(self.rules.risk_rules, 1):
            print(f"  {i}. {rule}")
        
        print("\n[EXIT RULES]")
        for i, rule in enumerate(self.rules.exit_rules, 1):
            print(f"  {i}. {rule}")
        
        print("\n" + "=" * 60)


# === EXPECTED PERFORMANCE METRICS ===

EXPECTED_METRICS = {
    'weekly_return': {
        'target': '10%+',
        'range': '8-15%',
        'pessimistic': '5%',
        'optimistic': '20%',
    },
    'monthly_return': {
        'target': '40-60%',
        'range': '30-80%',
        'note': 'Compounding effect of weekly returns',
    },
    'win_rate': {
        'target': '58%',
        'min_viable': '52%',
        'with_edge_threshold_12%': '55-62%',
    },
    'trades_per_week': {
        'target': 12,
        'min': 6,
        'max': 20,
    },
    'avg_win': {
        'target': '+45%',
        'range': '+30% to +100%',
        'note': 'Binary markets can pay 100%+',
    },
    'avg_loss': {
        'target': '-28%',
        'with_stop_loss': '-35% max',
    },
    'profit_factor': {
        'target': 1.75,
        'min_viable': 1.3,
        'formula': '(WinRate * AvgWin) / (LossRate * AvgLoss)',
    },
    'sharpe_ratio': {
        'target': 2.5,
        'range': '1.5-4.0',
        'note': 'High due to edge-based trading',
    },
    'max_drawdown': {
        'target': '<20%',
        'stop_trading_at': '30%',
        'recovery_expectation': '2-4 weeks',
    },
    'r_multiple': {
        'target': 1.5,
        'range': '1.2-2.5',
        'definition': 'Profit / Initial Risk',
    },
}


# === QUICK REFERENCE ===

QUICK_REFERENCE = """
================================================================================
                    AGGRESSIVE GROWTH STRATEGY - QUICK REFERENCE
================================================================================

ENTRY CRITERIA:
  Edge:       >= 12% (optimal 18%+)
  Confidence: >= 65% (optimal 75%+)  
  Signals:    >= 2 confirming
  Price Zone: 15-85 cents (optimal 25-65 cents)
  Liquidity:  >= $500
  Volume:     >= $1,000 24h
  Spread:     <= 8%
  Time:       >= 48 hours to expiry

POSITION SIZING:
  Kelly:      35% fractional Kelly
  Max Size:   20% of capital
  Min Size:   $2
  Scaling:    Increase size with higher edge/confidence

EXIT STRATEGY:
  Stop Loss:     35% loss (HARD STOP)
  Take Profit:   40% gain (or trailing stop)
  Partial Exit:  30% at +25%, 30% at +45%
  Trailing Stop: 15% from peak (activates at +25%)
  Time Stop:     120 hours if <10% movement

PORTFOLIO:
  Max Positions: 6
  Max Exposure:  85% of capital
  Reserve:       15% always
  Category Limit: 2 per category

RISK LIMITS:
  Max Drawdown:       30% (STOP TRADING)
  Max Daily Loss:     12%
  Consecutive Losses: 5 (PAUSE AND REVIEW)

PERFORMANCE TARGETS:
  Weekly Return:    10%+
  Win Rate:         58%
  Profit Factor:    1.75
  Trades/Week:      12

================================================================================
"""


# Create default strategy instance
strategy = AggressiveGrowthStrategy()


if __name__ == "__main__":
    print(QUICK_REFERENCE)
    strategy.print_rules()
    
    print("\n[STRATEGY SUMMARY]")
    import json
    print(json.dumps(strategy.get_summary(), indent=2))
    
    print("\n[EXPECTED METRICS]")
    print(json.dumps(EXPECTED_METRICS, indent=2))
