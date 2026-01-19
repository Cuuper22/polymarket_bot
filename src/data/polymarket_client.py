"""
Polymarket Data Client - Fetches market data from Polymarket APIs
"""
import requests
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import time
import json

logger = logging.getLogger(__name__)


@dataclass
class Market:
    """Represents a Polymarket market."""
    id: str
    question: str
    slug: str
    condition_id: str
    clob_token_ids: List[str]
    outcomes: List[str]
    outcome_prices: List[float]
    volume: float
    volume_24h: float
    liquidity: float
    end_date: Optional[datetime]
    category: str
    active: bool
    closed: bool
    
    @property
    def yes_price(self) -> float:
        """Get YES outcome price (probability)."""
        if len(self.outcome_prices) > 0:
            return self.outcome_prices[0]
        return 0.5
    
    @property
    def no_price(self) -> float:
        """Get NO outcome price (probability)."""
        if len(self.outcome_prices) > 1:
            return self.outcome_prices[1]
        return 1 - self.yes_price
    
    @property
    def yes_token_id(self) -> Optional[str]:
        """Get YES token ID for trading."""
        if len(self.clob_token_ids) > 0:
            return self.clob_token_ids[0]
        return None
    
    @property
    def no_token_id(self) -> Optional[str]:
        """Get NO token ID for trading."""
        if len(self.clob_token_ids) > 1:
            return self.clob_token_ids[1]
        return None


@dataclass
class OrderBook:
    """Represents an order book for a market."""
    token_id: str
    bids: List[Dict[str, float]]  # [{"price": 0.5, "size": 100}, ...]
    asks: List[Dict[str, float]]
    
    @property
    def best_bid(self) -> float:
        """Get best bid price."""
        if self.bids:
            return max(b["price"] for b in self.bids)
        return 0.0
    
    @property
    def best_ask(self) -> float:
        """Get best ask price."""
        if self.asks:
            return min(a["price"] for a in self.asks)
        return 1.0
    
    @property
    def spread(self) -> float:
        """Get bid-ask spread."""
        return self.best_ask - self.best_bid
    
    @property
    def mid_price(self) -> float:
        """Get mid price."""
        return (self.best_bid + self.best_ask) / 2


class PolymarketClient:
    """Client for fetching Polymarket data."""
    
    def __init__(self, gamma_host: str = "https://gamma-api.polymarket.com",
                 clob_host: str = "https://clob.polymarket.com"):
        self.gamma_host = gamma_host
        self.clob_host = clob_host
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "PolymarketBot/1.0"
        })
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 0.1  # 100ms between requests
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def _get(self, url: str, params: Optional[Dict] = None) -> Any:
        """Make a GET request with rate limiting."""
        self._rate_limit()
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def get_active_markets(self, limit: int = 100, 
                           min_volume: float = 1000,
                           min_liquidity: float = 500) -> List[Market]:
        """
        Fetch active markets suitable for trading.
        
        Args:
            limit: Maximum number of markets to fetch
            min_volume: Minimum total volume
            min_liquidity: Minimum liquidity
        
        Returns:
            List of Market objects
        """
        url = f"{self.gamma_host}/markets"
        params = {
            "active": "true",
            "closed": "false",
            "limit": limit,
            "order": "volume24hr",
            "ascending": "false",
            "volume_num_min": min_volume,
            "liquidity_num_min": min_liquidity,
        }
        
        try:
            data = self._get(url, params)
            if not data:
                return []
            markets = []
            
            for item in data:
                try:
                    # Parse outcomes and prices
                    outcomes = self._parse_json_string(item.get("outcomes", "[]"))
                    prices = self._parse_json_string(item.get("outcomePrices", "[]"))
                    clob_ids = self._parse_json_string(item.get("clobTokenIds", "[]"))
                    
                    # Parse end date
                    end_date = None
                    if item.get("endDate"):
                        try:
                            end_date = datetime.fromisoformat(
                                item["endDate"].replace("Z", "+00:00")
                            )
                        except:
                            pass
                    
                    market = Market(
                        id=str(item.get("id", "")),
                        question=item.get("question", ""),
                        slug=item.get("slug", ""),
                        condition_id=item.get("conditionId", ""),
                        clob_token_ids=clob_ids if clob_ids else [],
                        outcomes=outcomes if outcomes else ["Yes", "No"],
                        outcome_prices=[float(p) for p in prices] if prices else [0.5, 0.5],
                        volume=float(item.get("volumeNum", 0) or 0),
                        volume_24h=float(item.get("volume24hr", 0) or 0),
                        liquidity=float(item.get("liquidityNum", 0) or 0),
                        end_date=end_date,
                        category=item.get("category", ""),
                        active=item.get("active", True),
                        closed=item.get("closed", False),
                    )
                    
                    # Only include markets with valid token IDs for trading
                    if market.yes_token_id:
                        markets.append(market)
                        
                except Exception as e:
                    logger.warning(f"Failed to parse market: {e}")
                    continue
            
            logger.info(f"Fetched {len(markets)} active markets")
            return markets
            
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []
    
    def get_events(self, active: bool = True, limit: int = 50,
                   tag_id: Optional[int] = None) -> List[Dict]:
        """
        Fetch events from Gamma API.
        
        Args:
            active: Only active events
            limit: Maximum events
            tag_id: Filter by tag (e.g., crypto, politics)
        
        Returns:
            List of event dictionaries
        """
        url = f"{self.gamma_host}/events"
        params = {
            "active": str(active).lower(),
            "closed": "false",
            "limit": limit,
        }
        if tag_id:
            params["tag_id"] = tag_id
        
        return self._get(url, params)
    
    def get_market_by_slug(self, slug: str) -> Optional[Market]:
        """Fetch a specific market by slug."""
        url = f"{self.gamma_host}/markets"
        params = {"slug": slug}
        
        data = self._get(url, params)
        if data and len(data) > 0:
            return self._parse_market(data[0])
        return None
    
    def get_order_book(self, token_id: str) -> Optional[OrderBook]:
        """
        Fetch order book for a token.
        
        Args:
            token_id: The CLOB token ID
        
        Returns:
            OrderBook object
        """
        url = f"{self.clob_host}/book"
        params = {"token_id": token_id}
        
        try:
            data = self._get(url, params)
            if not data:
                return None
            
            bids = [
                {"price": float(b["price"]), "size": float(b["size"])}
                for b in data.get("bids", [])
            ]
            asks = [
                {"price": float(a["price"]), "size": float(a["size"])}
                for a in data.get("asks", [])
            ]
            
            return OrderBook(token_id=token_id, bids=bids, asks=asks)
            
        except Exception as e:
            logger.error(f"Failed to fetch order book: {e}")
            return None
    
    def get_price(self, token_id: str, side: str = "buy") -> Optional[float]:
        """
        Get current price for a token.
        
        Args:
            token_id: The CLOB token ID
            side: "buy" or "sell"
        
        Returns:
            Price as float
        """
        url = f"{self.clob_host}/price"
        params = {"token_id": token_id, "side": side}
        
        try:
            data = self._get(url, params)
            if not data:
                return None
            return float(data.get("price", 0))
        except Exception as e:
            logger.error(f"Failed to fetch price: {e}")
            return None
    
    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get midpoint price for a token."""
        url = f"{self.clob_host}/midpoint"
        params = {"token_id": token_id}
        
        try:
            data = self._get(url, params)
            if not data:
                return None
            return float(data.get("mid", 0))
        except Exception as e:
            logger.error(f"Failed to fetch midpoint: {e}")
            return None
    
    def get_market_trades(self, token_id: str, limit: int = 100) -> List[Dict]:
        """Fetch recent trades for a market."""
        url = f"{self.clob_host}/trades"
        params = {"asset_id": token_id, "limit": limit}
        
        try:
            data = self._get(url, params)
            return data or []
        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}")
            return []
    
    def _parse_json_string(self, s: str) -> List:
        """Parse JSON string to list."""
        if not s:
            return []
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return []
    
    def _parse_market(self, item: Dict) -> Market:
        """Parse market dictionary to Market object."""
        outcomes = self._parse_json_string(item.get("outcomes", "[]"))
        prices = self._parse_json_string(item.get("outcomePrices", "[]"))
        clob_ids = self._parse_json_string(item.get("clobTokenIds", "[]"))
        
        end_date = None
        if item.get("endDate"):
            try:
                end_date = datetime.fromisoformat(
                    item["endDate"].replace("Z", "+00:00")
                )
            except:
                pass
        
        return Market(
            id=str(item.get("id", "")),
            question=item.get("question", ""),
            slug=item.get("slug", ""),
            condition_id=item.get("conditionId", ""),
            clob_token_ids=clob_ids if clob_ids else [],
            outcomes=outcomes if outcomes else ["Yes", "No"],
            outcome_prices=[float(p) for p in prices] if prices else [0.5, 0.5],
            volume=float(item.get("volumeNum", 0) or 0),
            volume_24h=float(item.get("volume24hr", 0) or 0),
            liquidity=float(item.get("liquidityNum", 0) or 0),
            end_date=end_date,
            category=item.get("category", ""),
            active=item.get("active", True),
            closed=item.get("closed", False),
        )


# Convenience function for quick access
def get_client() -> PolymarketClient:
    """Get a configured Polymarket client."""
    return PolymarketClient()
