"""
Edge Detection Engine - Identifies trading opportunities
Combines multiple signals to find mispriced markets
"""
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of trading signals."""
    SENTIMENT_DIVERGENCE = "sentiment_divergence"
    VOLUME_SPIKE = "volume_spike"
    NEWS_CATALYST = "news_catalyst"
    TREND_MOMENTUM = "trend_momentum"
    MARKET_INEFFICIENCY = "market_inefficiency"


@dataclass
class Signal:
    """Represents a trading signal."""
    type: SignalType
    direction: str  # "YES" or "NO"
    strength: float  # 0 to 1
    confidence: float  # 0 to 1
    edge: float  # Estimated edge (expected return)
    reason: str
    data: Dict = field(default_factory=dict)
    
    @property
    def score(self) -> float:
        """Combined score for ranking."""
        return self.strength * self.confidence * (1 + self.edge)


@dataclass
class TradingOpportunity:
    """Represents a potential trade."""
    market_id: str
    market_question: str
    market_slug: str
    token_id: str
    direction: str  # "YES" or "NO"
    current_price: float
    estimated_fair_value: float
    edge: float  # expected edge
    confidence: float
    signals: List[Signal]
    recommended_size: float  # In dollars
    expected_return: float
    risk_score: float  # 0 to 1 (higher = riskier)
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def score(self) -> float:
        """Overall opportunity score for ranking."""
        # Combine edge, confidence, and inverse risk
        return self.edge * self.confidence * (1 - self.risk_score * 0.5)
    
    def to_dict(self) -> Dict:
        return {
            "market_id": self.market_id,
            "market_question": self.market_question,
            "direction": self.direction,
            "current_price": self.current_price,
            "estimated_fair_value": self.estimated_fair_value,
            "edge": self.edge,
            "confidence": self.confidence,
            "recommended_size": self.recommended_size,
            "expected_return": self.expected_return,
            "risk_score": self.risk_score,
            "signal_count": len(self.signals),
        }


class SentimentDivergenceDetector:
    """
    Detects when market price diverges from news sentiment.
    This is a key edge: markets can be slow to react to news.
    """
    
    def __init__(self, min_divergence: float = 0.10):
        """
        Args:
            min_divergence: Minimum divergence to generate signal (10% default)
        """
        self.min_divergence = min_divergence
    
    def detect(self, market_price: float, 
               sentiment_score: float,
               sentiment_confidence: float) -> Optional[Signal]:
        """
        Detect sentiment divergence.
        
        Args:
            market_price: Current YES price (0 to 1)
            sentiment_score: News sentiment (-1 to 1)
            sentiment_confidence: Confidence in sentiment
        
        Returns:
            Signal if divergence detected, None otherwise
        """
        # Convert sentiment to implied probability
        # Sentiment -1 to 1 maps to probability 0.2 to 0.8
        # (We don't go to extremes to be conservative)
        implied_prob = 0.5 + (sentiment_score * 0.3)
        implied_prob = max(0.2, min(0.8, implied_prob))
        
        divergence = implied_prob - market_price
        
        if abs(divergence) < self.min_divergence:
            return None
        
        direction = "YES" if divergence > 0 else "NO"
        strength = min(1.0, abs(divergence) / 0.3)
        edge = abs(divergence) * sentiment_confidence
        
        return Signal(
            type=SignalType.SENTIMENT_DIVERGENCE,
            direction=direction,
            strength=strength,
            confidence=sentiment_confidence,
            edge=edge,
            reason=f"Sentiment implies {implied_prob:.0%} but market at {market_price:.0%}",
            data={
                "implied_probability": implied_prob,
                "market_price": market_price,
                "divergence": divergence,
            }
        )


class VolumeSpikeDetector:
    """
    Detects unusual trading volume that may indicate informed trading.
    """
    
    def __init__(self, spike_threshold: float = 2.0):
        """
        Args:
            spike_threshold: Multiplier for volume spike (2x = 100% increase)
        """
        self.spike_threshold = spike_threshold
    
    def detect(self, current_volume_24h: float,
               avg_volume_24h: float,
               price_direction: Optional[str] = None) -> Optional[Signal]:
        """
        Detect volume spike.
        
        Args:
            current_volume_24h: Current 24h volume
            avg_volume_24h: Average 24h volume
            price_direction: "up" or "down" for recent price movement
        
        Returns:
            Signal if spike detected
        """
        if avg_volume_24h == 0:
            return None
        
        volume_ratio = current_volume_24h / avg_volume_24h
        
        if volume_ratio < self.spike_threshold:
            return None
        
        # Direction based on price movement or default to YES (more common)
        direction = "YES" if price_direction != "down" else "NO"
        
        strength = min(1.0, (volume_ratio - 1) / 3)  # Normalize
        confidence = min(0.6, 0.3 + strength * 0.3)  # Lower base confidence
        edge = 0.05 * strength  # Conservative edge estimate
        
        return Signal(
            type=SignalType.VOLUME_SPIKE,
            direction=direction,
            strength=strength,
            confidence=confidence,
            edge=edge,
            reason=f"Volume spike {volume_ratio:.1f}x normal",
            data={
                "volume_ratio": volume_ratio,
                "current_volume": current_volume_24h,
            }
        )


class NewsCatalystDetector:
    """
    Detects breaking news that could move markets.
    """
    
    CATALYST_KEYWORDS = {
        'high': [
            'breaking', 'just in', 'confirmed', 'official', 'announced',
            'signed', 'passed', 'approved', 'rejected', 'cancelled',
            'dies', 'dead', 'resigns', 'fired', 'arrested',
        ],
        'medium': [
            'sources say', 'reportedly', 'expected', 'likely', 'planning',
            'considering', 'discussing', 'meeting', 'talks',
        ],
    }
    
    def detect(self, news_items: List[Dict],
               market_keywords: List[str]) -> Optional[Signal]:
        """
        Detect news catalyst.
        
        Args:
            news_items: List of news items with title, content, published_at
            market_keywords: Keywords related to the market
        
        Returns:
            Signal if catalyst detected
        """
        if not news_items or not market_keywords:
            return None
        
        recent_news = []
        now = datetime.now()
        
        for item in news_items:
            # Check recency
            pub_date = item.get('published_at', now)
            if isinstance(pub_date, str):
                try:
                    pub_date = datetime.fromisoformat(pub_date)
                except ValueError:
                    pub_date = now
            
            age_hours = (now - pub_date).total_seconds() / 3600
            if age_hours > 6:  # Only last 6 hours
                continue
            
            text = f"{item.get('title', '')} {item.get('content', '')}".lower()
            
            # Check for market keywords
            keyword_matches = sum(1 for kw in market_keywords if kw.lower() in text)
            if keyword_matches == 0:
                continue
            
            # Check for catalyst keywords
            high_priority = any(kw in text for kw in self.CATALYST_KEYWORDS['high'])
            medium_priority = any(kw in text for kw in self.CATALYST_KEYWORDS['medium'])
            
            if high_priority or medium_priority:
                recent_news.append({
                    'item': item,
                    'priority': 'high' if high_priority else 'medium',
                    'keyword_matches': keyword_matches,
                    'age_hours': age_hours,
                })
        
        if not recent_news:
            return None
        
        # Get highest priority news
        recent_news.sort(key=lambda x: (
            0 if x['priority'] == 'high' else 1,
            x['age_hours'],
            -x['keyword_matches']
        ))
        
        top_news = recent_news[0]
        
        strength = 0.8 if top_news['priority'] == 'high' else 0.5
        recency_factor = max(0.5, 1 - top_news['age_hours'] / 6)
        
        return Signal(
            type=SignalType.NEWS_CATALYST,
            direction="YES",  # Will be refined by sentiment
            strength=strength * recency_factor,
            confidence=0.5,  # Medium confidence until analyzed
            edge=0.10 * strength,
            reason=f"Breaking news: {top_news['item'].get('title', '')[:50]}...",
            data={
                'news_title': top_news['item'].get('title', ''),
                'priority': top_news['priority'],
                'age_hours': top_news['age_hours'],
            }
        )


class TrendMomentumDetector:
    """
    Detects price momentum and trends.
    """
    
    def detect(self, price_history: List[Tuple[datetime, float]],
               lookback_hours: int = 24) -> Optional[Signal]:
        """
        Detect price momentum.
        
        Args:
            price_history: List of (timestamp, price) tuples
            lookback_hours: Hours to look back
        
        Returns:
            Signal if momentum detected
        """
        if len(price_history) < 3:
            return None
        
        now = datetime.now()
        cutoff = now - timedelta(hours=lookback_hours)
        
        # Filter to lookback period
        recent = [(t, p) for t, p in price_history if t >= cutoff]
        if len(recent) < 2:
            return None
        
        prices = [p for _, p in recent]
        
        # Calculate momentum
        start_price = prices[0]
        end_price = prices[-1]
        change = end_price - start_price
        
        if abs(change) < 0.05:  # Less than 5% move
            return None
        
        direction = "YES" if change > 0 else "NO"
        
        # Calculate strength based on consistency
        if len(prices) >= 3:
            # Check if trend is consistent
            mid_price = prices[len(prices) // 2]
            if change > 0:
                consistent = mid_price > start_price and end_price > mid_price
            else:
                consistent = mid_price < start_price and end_price < mid_price
        else:
            consistent = True
        
        strength = min(1.0, abs(change) / 0.20)  # Normalize to 20% max
        confidence = 0.6 if consistent else 0.3
        
        # Momentum following has modest edge
        edge = 0.03 * strength
        
        return Signal(
            type=SignalType.TREND_MOMENTUM,
            direction=direction,
            strength=strength,
            confidence=confidence,
            edge=edge,
            reason=f"Price moved {change:+.0%} in {lookback_hours}h",
            data={
                'start_price': start_price,
                'end_price': end_price,
                'change': change,
                'consistent': consistent,
            }
        )


class MarketInefficiencyDetector:
    """
    Detects market inefficiencies like wide spreads or stale prices.
    """
    
    def __init__(self, max_spread: float = 0.10):
        self.max_spread = max_spread
    
    def detect(self, bid: float, ask: float,
               last_trade_time: Optional[datetime] = None,
               volume: float = 0) -> Optional[Signal]:
        """
        Detect market inefficiency.
        
        Args:
            bid: Best bid price
            ask: Best ask price
            last_trade_time: Time of last trade
            volume: Trading volume
        
        Returns:
            Signal if inefficiency detected
        """
        spread = ask - bid
        
        signals = []
        
        # Wide spread opportunity
        if spread > self.max_spread:
            mid = (bid + ask) / 2
            # Can potentially capture spread
            edge = spread * 0.3  # Assume capture 30% of spread
            
            signals.append(Signal(
                type=SignalType.MARKET_INEFFICIENCY,
                direction="YES" if mid < 0.5 else "NO",
                strength=min(1.0, spread / 0.20),
                confidence=0.4,  # Lower confidence
                edge=edge,
                reason=f"Wide spread: {spread:.0%}",
                data={'spread': spread, 'mid': mid}
            ))
        
        # Stale market (no recent trades)
        if last_trade_time:
            hours_since_trade = (datetime.now() - last_trade_time).total_seconds() / 3600
            if hours_since_trade > 12 and volume < 1000:
                signals.append(Signal(
                    type=SignalType.MARKET_INEFFICIENCY,
                    direction="YES",  # Default
                    strength=0.3,
                    confidence=0.3,
                    edge=0.02,
                    reason=f"Stale market: {hours_since_trade:.0f}h since last trade",
                    data={'hours_since_trade': hours_since_trade}
                ))
        
        # Return strongest signal
        if signals:
            return max(signals, key=lambda s: s.score)
        return None


class EdgeDetector:
    """
    Main edge detection engine that combines all detectors.
    """
    
    def __init__(self, min_edge: float = 0.05, min_confidence: float = 0.4):
        """
        Args:
            min_edge: Minimum edge to consider (5% default)
            min_confidence: Minimum confidence threshold
        """
        self.min_edge = min_edge
        self.min_confidence = min_confidence
        
        # Initialize detectors
        self.sentiment_detector = SentimentDivergenceDetector()
        self.volume_detector = VolumeSpikeDetector()
        self.news_detector = NewsCatalystDetector()
        self.trend_detector = TrendMomentumDetector()
        self.inefficiency_detector = MarketInefficiencyDetector()
    
    def detect_opportunities(self, market_data: Dict,
                            news_data: Optional[List[Dict]] = None,
                            sentiment_score: Optional[float] = None,
                            sentiment_confidence: float = 0.5) -> Optional[TradingOpportunity]:
        """
        Detect trading opportunities for a market.
        
        Args:
            market_data: Market information
            news_data: Related news items
            sentiment_score: Overall sentiment (-1 to 1)
            sentiment_confidence: Confidence in sentiment
        
        Returns:
            TradingOpportunity if found, None otherwise
        """
        signals = []
        
        current_price = market_data.get('yes_price', 0.5)
        
        # 1. Sentiment divergence
        if sentiment_score is not None:
            signal = self.sentiment_detector.detect(
                current_price, sentiment_score, sentiment_confidence
            )
            if signal:
                signals.append(signal)
        
        # 2. Volume spike
        volume_24h = market_data.get('volume_24h', 0)
        avg_volume = market_data.get('avg_volume_24h', volume_24h)
        if volume_24h and avg_volume:
            signal = self.volume_detector.detect(volume_24h, avg_volume)
            if signal:
                signals.append(signal)
        
        # 3. News catalyst
        if news_data:
            keywords = market_data.get('keywords', [])
            question = market_data.get('question', '')
            if not keywords:
                keywords = question.split()[:5]
            
            signal = self.news_detector.detect(
                [{'title': n.get('title', ''), 
                  'content': n.get('content', ''),
                  'published_at': n.get('published_at')} for n in news_data[:10]],
                keywords
            )
            if signal:
                signals.append(signal)
        
        # 4. Market inefficiency
        bid = market_data.get('best_bid')
        ask = market_data.get('best_ask')
        if bid is not None and ask is not None:
            signal = self.inefficiency_detector.detect(
                bid, ask, volume=volume_24h
            )
            if signal:
                signals.append(signal)
        
        if not signals:
            return None
        
        # Combine signals
        opportunity = self._combine_signals(market_data, signals)
        
        # Filter by minimum thresholds
        if opportunity.edge < self.min_edge:
            return None
        if opportunity.confidence < self.min_confidence:
            return None
        
        return opportunity
    
    def _combine_signals(self, market_data: Dict, 
                        signals: List[Signal]) -> TradingOpportunity:
        """Combine multiple signals into a trading opportunity."""
        
        # Determine direction by majority vote weighted by strength
        yes_weight = sum(s.strength for s in signals if s.direction == "YES")
        no_weight = sum(s.strength for s in signals if s.direction == "NO")
        direction = "YES" if yes_weight >= no_weight else "NO"
        
        # Filter signals to matching direction
        matching_signals = [s for s in signals if s.direction == direction]
        
        if not matching_signals:
            matching_signals = signals
        
        # Calculate combined metrics
        avg_edge = statistics.mean(s.edge for s in matching_signals)
        avg_confidence = statistics.mean(s.confidence for s in matching_signals)
        max_strength = max(s.strength for s in matching_signals)
        
        # Boost confidence if multiple signals agree
        if len(matching_signals) >= 2:
            avg_confidence = min(0.9, avg_confidence * 1.2)
        
        current_price = market_data.get('yes_price', 0.5)
        if direction == "NO":
            current_price = 1 - current_price
        
        # Estimate fair value
        fair_value = current_price + (avg_edge if direction == "YES" else -avg_edge)
        fair_value = max(0.05, min(0.95, fair_value))
        
        # Calculate risk score
        time_to_expiry = market_data.get('hours_to_expiry', 168)  # Default 1 week
        liquidity = market_data.get('liquidity', 1000)
        
        risk_score = 0.3  # Base risk
        if time_to_expiry < 24:
            risk_score += 0.2  # Short expiry risk
        if liquidity < 1000:
            risk_score += 0.2  # Low liquidity risk
        if current_price < 0.10 or current_price > 0.90:
            risk_score += 0.1  # Extreme price risk
        
        risk_score = min(1.0, risk_score)
        
        # Determine token ID
        if direction == "YES":
            token_id = market_data.get('yes_token_id', '')
        else:
            token_id = market_data.get('no_token_id', '')
        
        return TradingOpportunity(
            market_id=market_data.get('id', ''),
            market_question=market_data.get('question', ''),
            market_slug=market_data.get('slug', ''),
            token_id=token_id,
            direction=direction,
            current_price=current_price,
            estimated_fair_value=fair_value,
            edge=avg_edge,
            confidence=avg_confidence,
            signals=matching_signals,
            recommended_size=0,  # Will be calculated by position sizer
            expected_return=avg_edge * avg_confidence,
            risk_score=risk_score,
        )
    
    def rank_opportunities(self, opportunities: List[TradingOpportunity]) -> List[TradingOpportunity]:
        """Rank opportunities by score."""
        return sorted(opportunities, key=lambda x: x.score, reverse=True)
