"""
Price History Tracker
Tracks hourly price data for markets to enable swing trading strategies.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class PricePoint:
    """A single price observation."""
    timestamp: str  # ISO format
    price: float
    volume_24h: float
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PricePoint':
        return cls(
            timestamp=data['timestamp'],
            price=data['price'],
            volume_24h=data.get('volume_24h', 0)
        )


@dataclass
class PriceAnalysis:
    """Analysis of price history for a market."""
    market_id: str
    current_price: float
    price_1h_ago: Optional[float]
    price_6h_ago: Optional[float]
    price_24h_ago: Optional[float]
    
    # Changes
    change_1h: Optional[float]  # Percentage change
    change_6h: Optional[float]
    change_24h: Optional[float]
    
    # Technical indicators
    high_24h: float
    low_24h: float
    volatility_24h: float  # Standard deviation of hourly changes
    
    # Signals
    is_dip: bool  # Price significantly below recent high
    is_pump: bool  # Price significantly above recent low
    momentum: str  # 'up', 'down', 'neutral'
    
    @property
    def dip_size(self) -> float:
        """How much the price has dropped from 24h high."""
        if self.high_24h > 0:
            return (self.high_24h - self.current_price) / self.high_24h
        return 0


class PriceTracker:
    """
    Tracks price history for markets and provides analysis.
    
    Stores hourly price snapshots and calculates:
    - Price changes over 1h, 6h, 24h
    - Volatility
    - Dip/pump detection
    - Momentum signals
    """
    
    def __init__(self, data_dir: str = "./data"):
        """
        Initialize the price tracker.
        
        Args:
            data_dir: Directory to store price history data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "price_history.json"
        
        # In-memory cache: market_id -> list of PricePoints
        self.history: Dict[str, List[PricePoint]] = {}
        
        # Load existing history
        self._load_history()
        
        # Configuration
        self.max_history_hours = 168  # Keep 7 days of hourly data
        self.dip_threshold = 0.10  # 10% drop from high = dip
        self.pump_threshold = 0.10  # 10% rise from low = pump
    
    def _load_history(self):
        """Load price history from disk."""
        if not self.history_file.exists():
            return
        
        try:
            with open(self.history_file, 'r') as f:
                data = json.load(f)
            
            for market_id, points in data.items():
                self.history[market_id] = [
                    PricePoint.from_dict(p) for p in points
                ]
            
            logger.info(f"Loaded price history for {len(self.history)} markets")
            
        except Exception as e:
            logger.error(f"Failed to load price history: {e}")
    
    def _save_history(self):
        """Save price history to disk."""
        try:
            data = {
                market_id: [p.to_dict() for p in points]
                for market_id, points in self.history.items()
            }
            
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save price history: {e}")
    
    def update_price(self, market_id: str, price: float, volume_24h: float = 0):
        """
        Record a new price observation.
        
        Args:
            market_id: Market identifier
            price: Current price (0-1)
            volume_24h: 24h trading volume
        """
        now = datetime.now()
        
        # Check if we should add a new point (hourly updates)
        if market_id in self.history and self.history[market_id]:
            last_point = self.history[market_id][-1]
            last_time = datetime.fromisoformat(last_point.timestamp)
            
            # Only add if at least 55 minutes have passed
            if (now - last_time).total_seconds() < 55 * 60:
                # Update the last point instead
                self.history[market_id][-1] = PricePoint(
                    timestamp=now.isoformat(),
                    price=price,
                    volume_24h=volume_24h
                )
                return
        
        # Add new point
        if market_id not in self.history:
            self.history[market_id] = []
        
        self.history[market_id].append(PricePoint(
            timestamp=now.isoformat(),
            price=price,
            volume_24h=volume_24h
        ))
        
        # Trim old data
        self._trim_history(market_id)
        
        # Periodically save
        if len(self.history[market_id]) % 5 == 0:
            self._save_history()
    
    def _trim_history(self, market_id: str):
        """Remove data older than max_history_hours."""
        if market_id not in self.history:
            return
        
        cutoff = datetime.now() - timedelta(hours=self.max_history_hours)
        
        self.history[market_id] = [
            p for p in self.history[market_id]
            if datetime.fromisoformat(p.timestamp) >= cutoff
        ]
    
    def update_batch(self, markets: List[Dict]):
        """
        Update prices for multiple markets.
        
        Args:
            markets: List of dicts with 'id', 'price', 'volume_24h'
        """
        for market in markets:
            self.update_price(
                market_id=market.get('id', ''),
                price=market.get('price', 0),
                volume_24h=market.get('volume_24h', 0)
            )
        
        self._save_history()
    
    def get_analysis(self, market_id: str) -> Optional[PriceAnalysis]:
        """
        Get price analysis for a market.
        
        Args:
            market_id: Market identifier
            
        Returns:
            PriceAnalysis with price changes, volatility, and signals
        """
        if market_id not in self.history or not self.history[market_id]:
            return None
        
        points = self.history[market_id]
        current = points[-1]
        current_price = current.price
        now = datetime.fromisoformat(current.timestamp)
        
        # Get prices at different time horizons
        price_1h = self._get_price_at_offset(points, now, hours=1)
        price_6h = self._get_price_at_offset(points, now, hours=6)
        price_24h = self._get_price_at_offset(points, now, hours=24)
        
        # Calculate changes
        change_1h = self._calc_change(current_price, price_1h)
        change_6h = self._calc_change(current_price, price_6h)
        change_24h = self._calc_change(current_price, price_24h)
        
        # Get 24h high/low
        prices_24h = self._get_prices_in_window(points, now, hours=24)
        if prices_24h:
            high_24h = max(prices_24h)
            low_24h = min(prices_24h)
        else:
            high_24h = current_price
            low_24h = current_price
        
        # Calculate volatility (std dev of hourly returns)
        volatility = self._calc_volatility(points, hours=24)
        
        # Determine if this is a dip or pump
        dip_from_high = (high_24h - current_price) / high_24h if high_24h > 0 else 0
        pump_from_low = (current_price - low_24h) / low_24h if low_24h > 0 else 0
        
        is_dip = dip_from_high >= self.dip_threshold
        is_pump = pump_from_low >= self.pump_threshold
        
        # Determine momentum
        if change_1h is not None and change_6h is not None:
            if change_1h > 0.02 and change_6h > 0.03:
                momentum = 'up'
            elif change_1h < -0.02 and change_6h < -0.03:
                momentum = 'down'
            else:
                momentum = 'neutral'
        else:
            momentum = 'neutral'
        
        return PriceAnalysis(
            market_id=market_id,
            current_price=current_price,
            price_1h_ago=price_1h,
            price_6h_ago=price_6h,
            price_24h_ago=price_24h,
            change_1h=change_1h,
            change_6h=change_6h,
            change_24h=change_24h,
            high_24h=high_24h,
            low_24h=low_24h,
            volatility_24h=volatility,
            is_dip=is_dip,
            is_pump=is_pump,
            momentum=momentum
        )
    
    def _get_price_at_offset(self, points: List[PricePoint], 
                             now: datetime, hours: int) -> Optional[float]:
        """Get the price closest to X hours ago."""
        target = now - timedelta(hours=hours)
        
        closest = None
        min_diff = float('inf')
        
        for point in points:
            t = datetime.fromisoformat(point.timestamp)
            diff = abs((t - target).total_seconds())
            
            if diff < min_diff:
                min_diff = diff
                closest = point.price
        
        # Only return if within 2 hours of target
        if min_diff <= 2 * 3600:
            return closest
        return None
    
    def _get_prices_in_window(self, points: List[PricePoint],
                              now: datetime, hours: int) -> List[float]:
        """Get all prices within the last X hours."""
        cutoff = now - timedelta(hours=hours)
        
        return [
            p.price for p in points
            if datetime.fromisoformat(p.timestamp) >= cutoff
        ]
    
    def _calc_change(self, current: float, previous: Optional[float]) -> Optional[float]:
        """Calculate percentage change."""
        if previous is None or previous == 0:
            return None
        return (current - previous) / previous
    
    def _calc_volatility(self, points: List[PricePoint], hours: int) -> float:
        """Calculate volatility (std dev of hourly returns)."""
        now = datetime.fromisoformat(points[-1].timestamp) if points else datetime.now()
        cutoff = now - timedelta(hours=hours)
        
        recent_points = [
            p for p in points
            if datetime.fromisoformat(p.timestamp) >= cutoff
        ]
        
        if len(recent_points) < 2:
            return 0
        
        # Calculate hourly returns
        returns = []
        for i in range(1, len(recent_points)):
            prev_price = recent_points[i-1].price
            curr_price = recent_points[i].price
            if prev_price > 0:
                returns.append((curr_price - prev_price) / prev_price)
        
        if not returns:
            return 0
        
        # Standard deviation
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return variance ** 0.5
    
    def get_dip_opportunities(self, min_dip_size: float = 0.10) -> List[PriceAnalysis]:
        """
        Find markets that have dipped significantly.
        
        Args:
            min_dip_size: Minimum drop from 24h high (as fraction)
            
        Returns:
            List of PriceAnalysis for markets that have dipped
        """
        opportunities = []
        
        for market_id in self.history:
            analysis = self.get_analysis(market_id)
            if analysis and analysis.is_dip and analysis.dip_size >= min_dip_size:
                opportunities.append(analysis)
        
        # Sort by dip size (biggest dips first)
        opportunities.sort(key=lambda a: a.dip_size, reverse=True)
        
        return opportunities
    
    def get_momentum_markets(self, direction: str = 'up') -> List[PriceAnalysis]:
        """
        Find markets with strong momentum.
        
        Args:
            direction: 'up' or 'down'
            
        Returns:
            List of PriceAnalysis for markets with matching momentum
        """
        results = []
        
        for market_id in self.history:
            analysis = self.get_analysis(market_id)
            if analysis and analysis.momentum == direction:
                results.append(analysis)
        
        return results
    
    def save(self):
        """Manually trigger a save."""
        self._save_history()
    
    def get_tracked_markets(self) -> List[str]:
        """Get list of all tracked market IDs."""
        return list(self.history.keys())
    
    def get_history(self, market_id: str, hours: int = 24) -> List[PricePoint]:
        """Get raw price history for a market."""
        if market_id not in self.history:
            return []
        
        now = datetime.now()
        cutoff = now - timedelta(hours=hours)
        
        return [
            p for p in self.history[market_id]
            if datetime.fromisoformat(p.timestamp) >= cutoff
        ]


def create_price_tracker(data_dir: str = "./data") -> PriceTracker:
    """Create a price tracker instance."""
    return PriceTracker(data_dir)
