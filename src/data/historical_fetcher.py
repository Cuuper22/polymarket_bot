"""
Historical Data Fetcher for Polymarket
Fetches real historical price data from Polymarket CLOB API for backtesting.
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import requests

logger = logging.getLogger(__name__)


@dataclass
class PricePoint:
    """A single price point in history."""
    timestamp: int  # Unix timestamp
    price: float
    datetime_str: str = ""
    
    def __post_init__(self):
        if not self.datetime_str:
            self.datetime_str = datetime.fromtimestamp(self.timestamp).isoformat()


@dataclass
class MarketHistory:
    """Historical data for a single market."""
    market_id: str
    token_id: str
    question: str
    category: str
    start_time: int
    end_time: int
    prices: List[PricePoint]
    volume_24h: float = 0
    resolution_price: Optional[float] = None  # Final price if resolved
    
    @property
    def duration_hours(self) -> float:
        return (self.end_time - self.start_time) / 3600
    
    @property
    def price_values(self) -> List[float]:
        return [p.price for p in self.prices]
    
    @property
    def timestamps(self) -> List[int]:
        return [p.timestamp for p in self.prices]
    
    def get_price_at(self, timestamp: int) -> Optional[float]:
        """Get price at or before a specific timestamp."""
        for p in reversed(self.prices):
            if p.timestamp <= timestamp:
                return p.price
        return self.prices[0].price if self.prices else None
    
    def resample_hourly(self) -> List[Tuple[int, float]]:
        """Resample to hourly data (last price per hour)."""
        if not self.prices:
            return []
        
        hourly = {}
        for p in self.prices:
            hour_ts = (p.timestamp // 3600) * 3600
            hourly[hour_ts] = p.price
        
        return sorted(hourly.items())


class HistoricalFetcher:
    """
    Fetches historical price data from Polymarket CLOB API.
    
    API Endpoint: https://clob.polymarket.com/prices-history
    Parameters:
        - market: Token ID (required)
        - startTs: Start timestamp (optional)
        - endTs: End timestamp (optional)  
        - interval: '1h', '1d', 'max' (alternative to timestamps)
    
    Returns ~1 minute resolution data.
    """
    
    CLOB_HOST = "https://clob.polymarket.com"
    GAMMA_HOST = "https://gamma-api.polymarket.com"
    
    def __init__(self, data_dir: str = "./data/historical"):
        """
        Initialize the fetcher.
        
        Args:
            data_dir: Directory to cache historical data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "PolymarketBacktester/1.0"
        })
        
        self._last_request = 0
        self._min_delay = 0.2  # 200ms between requests
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request
        if elapsed < self._min_delay:
            time.sleep(self._min_delay - elapsed)
        self._last_request = time.time()
    
    def get_active_markets(self, limit: int = 100, min_volume: float = 10000) -> List[Dict]:
        """
        Get list of active markets for data collection.
        
        Args:
            limit: Max markets to fetch
            min_volume: Minimum 24h volume
            
        Returns:
            List of market info dicts
        """
        self._rate_limit()
        
        try:
            resp = self.session.get(
                f"{self.GAMMA_HOST}/markets",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": limit,
                    "order": "volume24hr",
                    "ascending": "false",
                    "volume_num_min": min_volume,
                },
                timeout=30
            )
            resp.raise_for_status()
            
            markets = []
            for m in resp.json():
                clob_ids = json.loads(m.get("clobTokenIds", "[]"))
                if clob_ids:
                    markets.append({
                        "market_id": str(m.get("id", "")),
                        "token_id": clob_ids[0],
                        "question": m.get("question", ""),
                        "category": m.get("category", ""),
                        "volume_24h": float(m.get("volume24hr", 0) or 0),
                        "liquidity": float(m.get("liquidityNum", 0) or 0),
                        "current_price": float(json.loads(m.get("outcomePrices", "[0.5]"))[0]),
                    })
            
            return markets
            
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []
    
    def get_resolved_markets(self, limit: int = 100, min_volume: float = 5000) -> List[Dict]:
        """
        Get resolved markets (for backtesting with known outcomes).
        
        Args:
            limit: Max markets
            min_volume: Minimum volume
            
        Returns:
            List of resolved market info
        """
        self._rate_limit()
        
        try:
            resp = self.session.get(
                f"{self.GAMMA_HOST}/markets",
                params={
                    "closed": "true",
                    "limit": limit,
                    "order": "volume",
                    "ascending": "false",
                    "volume_num_min": min_volume,
                },
                timeout=30
            )
            resp.raise_for_status()
            
            markets = []
            for m in resp.json():
                clob_ids = json.loads(m.get("clobTokenIds", "[]"))
                if clob_ids:
                    # Get final resolution price
                    prices = json.loads(m.get("outcomePrices", "[0.5]"))
                    resolution_price = float(prices[0]) if prices else None
                    
                    markets.append({
                        "market_id": str(m.get("id", "")),
                        "token_id": clob_ids[0],
                        "question": m.get("question", ""),
                        "category": m.get("category", ""),
                        "volume": float(m.get("volumeNum", 0) or 0),
                        "resolution_price": resolution_price,
                        "end_date": m.get("endDate"),
                    })
            
            return markets
            
        except Exception as e:
            logger.error(f"Failed to fetch resolved markets: {e}")
            return []
    
    def fetch_price_history(self, token_id: str, 
                           start_ts: Optional[int] = None,
                           end_ts: Optional[int] = None,
                           interval: Optional[str] = None) -> List[PricePoint]:
        """
        Fetch historical prices for a token.
        
        Args:
            token_id: The CLOB token ID
            start_ts: Start timestamp (optional)
            end_ts: End timestamp (optional)
            interval: '1h', '1d', 'max' (alternative to timestamps)
            
        Returns:
            List of PricePoint objects
        """
        self._rate_limit()
        
        params = {"market": token_id}
        
        if start_ts and end_ts:
            params["startTs"] = start_ts
            params["endTs"] = end_ts
        elif interval:
            params["interval"] = interval
        else:
            # Default to max available history
            params["interval"] = "max"
        
        try:
            resp = self.session.get(
                f"{self.CLOB_HOST}/prices-history",
                params=params,
                timeout=60
            )
            resp.raise_for_status()
            
            data = resp.json()
            history = data.get("history", [])
            
            prices = []
            for h in history:
                prices.append(PricePoint(
                    timestamp=h.get("t", 0),
                    price=h.get("p", 0.5)
                ))
            
            logger.info(f"Fetched {len(prices)} price points for token {token_id[:20]}...")
            return prices
            
        except Exception as e:
            logger.error(f"Failed to fetch price history: {e}")
            return []
    
    def fetch_market_history(self, market_info: Dict,
                            days_back: int = 30) -> Optional[MarketHistory]:
        """
        Fetch complete history for a market.
        
        Args:
            market_info: Market info dict from get_active_markets()
            days_back: How many days of history to fetch
            
        Returns:
            MarketHistory object
        """
        end_ts = int(time.time())
        start_ts = end_ts - (days_back * 24 * 60 * 60)
        
        prices = self.fetch_price_history(
            token_id=market_info["token_id"],
            start_ts=start_ts,
            end_ts=end_ts
        )
        
        if not prices:
            return None
        
        return MarketHistory(
            market_id=market_info["market_id"],
            token_id=market_info["token_id"],
            question=market_info["question"],
            category=market_info.get("category", ""),
            start_time=prices[0].timestamp if prices else start_ts,
            end_time=prices[-1].timestamp if prices else end_ts,
            prices=prices,
            volume_24h=market_info.get("volume_24h", 0),
            resolution_price=market_info.get("resolution_price"),
        )
    
    def fetch_multiple_markets(self, num_markets: int = 20,
                               days_back: int = 14,
                               min_volume: float = 50000) -> List[MarketHistory]:
        """
        Fetch historical data for multiple markets.
        
        Args:
            num_markets: Number of markets to fetch
            days_back: Days of history per market
            min_volume: Minimum 24h volume
            
        Returns:
            List of MarketHistory objects
        """
        markets = self.get_active_markets(limit=num_markets * 2, min_volume=min_volume)
        logger.info(f"Found {len(markets)} markets matching criteria")
        
        histories = []
        for i, market in enumerate(markets[:num_markets]):
            logger.info(f"Fetching {i+1}/{num_markets}: {market['question'][:50]}...")
            
            history = self.fetch_market_history(market, days_back=days_back)
            if history and len(history.prices) > 100:  # At least 100 data points
                histories.append(history)
            
            time.sleep(0.3)  # Rate limiting
        
        logger.info(f"Successfully fetched {len(histories)} market histories")
        return histories
    
    def save_histories(self, histories: List[MarketHistory], filename: str = "market_histories.json"):
        """Save histories to disk."""
        filepath = self.data_dir / filename
        
        data = []
        for h in histories:
            data.append({
                "market_id": h.market_id,
                "token_id": h.token_id,
                "question": h.question,
                "category": h.category,
                "start_time": h.start_time,
                "end_time": h.end_time,
                "volume_24h": h.volume_24h,
                "resolution_price": h.resolution_price,
                "prices": [{"t": p.timestamp, "p": p.price} for p in h.prices],
            })
        
        with open(filepath, 'w') as f:
            json.dump(data, f)
        
        logger.info(f"Saved {len(histories)} histories to {filepath}")
    
    def load_histories(self, filename: str = "market_histories.json") -> List[MarketHistory]:
        """Load histories from disk."""
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            return []
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        histories = []
        for d in data:
            prices = [PricePoint(timestamp=p["t"], price=p["p"]) for p in d["prices"]]
            histories.append(MarketHistory(
                market_id=d["market_id"],
                token_id=d["token_id"],
                question=d["question"],
                category=d.get("category", ""),
                start_time=d["start_time"],
                end_time=d["end_time"],
                prices=prices,
                volume_24h=d.get("volume_24h", 0),
                resolution_price=d.get("resolution_price"),
            ))
        
        logger.info(f"Loaded {len(histories)} histories from {filepath}")
        return histories


def download_backtest_data(num_markets: int = 30, days_back: int = 14):
    """
    Convenience function to download data for backtesting.
    
    Args:
        num_markets: Number of markets to download
        days_back: Days of history
    """
    fetcher = HistoricalFetcher()
    
    print(f"Downloading {days_back} days of history for {num_markets} markets...")
    print()
    
    histories = fetcher.fetch_multiple_markets(
        num_markets=num_markets,
        days_back=days_back,
        min_volume=20000
    )
    
    fetcher.save_histories(histories)
    
    print()
    print(f"Downloaded {len(histories)} market histories")
    print(f"Total price points: {sum(len(h.prices) for h in histories):,}")
    
    # Summary
    print()
    print("Markets downloaded:")
    for h in histories[:10]:
        print(f"  - {h.question[:50]}... ({len(h.prices):,} points)")
    if len(histories) > 10:
        print(f"  ... and {len(histories) - 10} more")
    
    return histories


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    download_backtest_data(num_markets=20, days_back=7)
