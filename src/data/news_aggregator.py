"""
Free News Aggregator - Collects news from free sources
Sources: RSS feeds, Reddit, Google Trends
"""
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import re
import json
import threading

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """Represents a news item from any source."""
    title: str
    content: str
    source: str
    url: str
    published_at: datetime
    relevance_score: float = 0.0
    sentiment_score: float = 0.0  # -1 to 1
    keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "url": self.url,
            "published_at": self.published_at.isoformat(),
            "relevance_score": self.relevance_score,
            "sentiment_score": self.sentiment_score,
            "keywords": self.keywords,
        }


class RSSFetcher:
    """Fetches news from RSS feeds."""
    
    DEFAULT_FEEDS = [
        # General News
        ("Google News", "https://news.google.com/rss"),
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Reuters", "https://www.reutersagency.com/feed/"),
        
        # Crypto/Finance
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("CoinTelegraph", "https://cointelegraph.com/rss"),
        ("Decrypt", "https://decrypt.co/feed"),
        
        # Politics/World
        ("AP News", "https://rsshub.app/apnews/topics/apf-topnews"),
        ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    ]
    
    def __init__(self, feeds: Optional[List[tuple]] = None):
        self.feeds = feeds or self.DEFAULT_FEEDS
        
    def fetch_all(self, max_age_hours: int = 24) -> List[NewsItem]:
        """Fetch news from all RSS feeds."""
        try:
            import feedparser  # type: ignore[import-not-found]
        except ImportError:
            logger.warning("feedparser not installed")
            return []
        
        all_news = []
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        for name, url in self.feeds:
            try:
                feed = feedparser.parse(url)
                
                for entry in feed.entries[:20]:  # Limit per feed
                    try:
                        # Parse publication date
                        pub_date = datetime.now()
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            pub_date = datetime(*entry.published_parsed[:6])
                        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                            pub_date = datetime(*entry.updated_parsed[:6])
                        
                        # Skip old news
                        if pub_date < cutoff:
                            continue
                        
                        # Get content
                        content = ""
                        if hasattr(entry, 'summary'):
                            content = entry.summary
                        elif hasattr(entry, 'description'):
                            content = entry.description
                        
                        # Clean HTML
                        content = self._clean_html(content)
                        title = self._clean_html(entry.get('title', ''))
                        
                        news_item = NewsItem(
                            title=title,
                            content=content[:1000],  # Limit content
                            source=name,
                            url=entry.get('link', ''),
                            published_at=pub_date,
                        )
                        all_news.append(news_item)
                        
                    except Exception as e:
                        logger.debug(f"Failed to parse entry: {e}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Failed to fetch {name}: {e}")
                continue
        
        logger.info(f"Fetched {len(all_news)} news items from RSS feeds")
        return all_news
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        clean = re.sub(r'<[^>]+>', '', text)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean


class RedditFetcher:
    """Fetches posts from relevant Reddit communities."""
    
    RELEVANT_SUBREDDITS = [
        "polymarket",  # Direct Polymarket discussion
        "prediction_markets",
        "wallstreetbets",  # Market sentiment
        "cryptocurrency",
        "bitcoin",
        "ethereum",
        "politics",  # For political markets
        "worldnews",
        "news",
        "technology",
    ]
    
    def __init__(self, client_id: Optional[str] = None, 
                 client_secret: Optional[str] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self._reddit = None
    
    def _get_reddit(self):
        """Get Reddit API client (lazy init)."""
        if self._reddit is None:
            try:
                import praw  # type: ignore[import-not-found]
                
                if self.client_id and self.client_secret:
                    self._reddit = praw.Reddit(
                        client_id=self.client_id,
                        client_secret=self.client_secret,
                        user_agent="PolymarketBot/1.0"
                    )
                else:
                    # Read-only mode without credentials
                    self._reddit = praw.Reddit(
                        client_id="placeholder",
                        client_secret="placeholder", 
                        user_agent="PolymarketBot/1.0"
                    )
                    self._reddit.read_only = True
            except ImportError:
                logger.warning("praw not installed")
                return None
            except Exception as e:
                logger.warning(f"Failed to initialize Reddit: {e}")
                return None
        return self._reddit
    
    def fetch_subreddit(self, subreddit: str, limit: int = 25,
                       time_filter: str = "day") -> List[NewsItem]:
        """Fetch posts from a subreddit."""
        reddit = self._get_reddit()
        if not reddit:
            return []
        
        news_items = []
        
        try:
            sub = reddit.subreddit(subreddit)
            
            for post in sub.hot(limit=limit):
                try:
                    # Convert timestamp
                    pub_date = datetime.fromtimestamp(post.created_utc)
                    
                    # Skip very old posts
                    if datetime.now() - pub_date > timedelta(days=2):
                        continue
                    
                    content = post.selftext[:1000] if post.selftext else ""
                    
                    news_item = NewsItem(
                        title=post.title,
                        content=content,
                        source=f"r/{subreddit}",
                        url=f"https://reddit.com{post.permalink}",
                        published_at=pub_date,
                        relevance_score=self._calc_relevance(post),
                    )
                    news_items.append(news_item)
                    
                except Exception as e:
                    logger.debug(f"Failed to parse post: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to fetch r/{subreddit}: {e}")
        
        return news_items
    
    def fetch_all(self, subreddits: Optional[List[str]] = None) -> List[NewsItem]:
        """Fetch from all relevant subreddits."""
        subs = subreddits or self.RELEVANT_SUBREDDITS
        all_news = []
        
        for sub in subs:
            news = self.fetch_subreddit(sub, limit=15)
            all_news.extend(news)
            time.sleep(0.5)  # Rate limiting
        
        logger.info(f"Fetched {len(all_news)} posts from Reddit")
        return all_news
    
    def _calc_relevance(self, post) -> float:
        """Calculate relevance score based on engagement."""
        # Score based on upvotes and comments
        score = min(1.0, (post.score + post.num_comments * 2) / 1000)
        
        # Boost for high upvote ratio
        if hasattr(post, 'upvote_ratio'):
            score *= post.upvote_ratio
        
        return score


class GoogleTrendsFetcher:
    """Fetches trending topics from Google Trends."""
    
    def __init__(self):
        self._pytrends = None
    
    def _get_pytrends(self):
        """Get pytrends client (lazy init)."""
        if self._pytrends is None:
            try:
                from pytrends.request import TrendReq  # type: ignore[import-not-found]
                self._pytrends = TrendReq(hl='en-US', tz=360)
            except ImportError:
                logger.warning("pytrends not installed")
                return None
        return self._pytrends
    
    def get_trending_searches(self, geo: str = 'US') -> List[str]:
        """Get today's trending searches."""
        pytrends = self._get_pytrends()
        if not pytrends:
            return []
        
        try:
            df = pytrends.trending_searches(pn=geo.lower())
            return df[0].tolist()[:20]
        except Exception as e:
            logger.warning(f"Failed to get trending searches: {e}")
            return []
    
    def get_interest_over_time(self, keywords: List[str], 
                                timeframe: str = 'now 7-d') -> Dict[str, float]:
        """
        Get search interest for keywords.
        
        Returns dict mapping keyword to relative interest (0-100).
        """
        pytrends = self._get_pytrends()
        if not pytrends or not keywords:
            return {}
        
        try:
            # Build payload (max 5 keywords at a time)
            kw_list = keywords[:5]
            pytrends.build_payload(kw_list, timeframe=timeframe)
            
            df = pytrends.interest_over_time()
            if df.empty:
                return {}
            
            # Get latest values
            latest = df.iloc[-1]
            return {kw: float(latest.get(kw, 0)) for kw in kw_list}
            
        except Exception as e:
            logger.warning(f"Failed to get interest: {e}")
            return {}
    
    def detect_interest_spike(self, keyword: str, 
                              threshold: float = 1.5) -> bool:
        """
        Detect if a keyword has spiking interest.
        
        Args:
            keyword: Search term to check
            threshold: Spike multiplier (e.g., 1.5 = 50% above average)
        
        Returns:
            True if interest is spiking
        """
        pytrends = self._get_pytrends()
        if not pytrends:
            return False
        
        try:
            pytrends.build_payload([keyword], timeframe='now 7-d')
            df = pytrends.interest_over_time()
            
            if df.empty or len(df) < 2:
                return False
            
            values = df[keyword].values
            avg = values[:-1].mean()  # Average excluding latest
            latest = values[-1]
            
            if avg > 0:
                return latest / avg >= threshold
            return False
            
        except Exception as e:
            logger.debug(f"Failed to detect spike: {e}")
            return False


class NewsAggregator:
    """
    Main aggregator that combines all news sources.
    """
    
    def __init__(self, reddit_id: Optional[str] = None,
                 reddit_secret: Optional[str] = None):
        self.rss_fetcher = RSSFetcher()
        self.reddit_fetcher = RedditFetcher(reddit_id, reddit_secret)
        self.trends_fetcher = GoogleTrendsFetcher()
        
        self._cache: Dict[str, List[NewsItem]] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_lock = threading.Lock()
        self._cache_duration = timedelta(minutes=10)
    
    def fetch_all_news(self, max_age_hours: int = 24,
                       use_cache: bool = True) -> List[NewsItem]:
        """
        Fetch news from all sources.
        
        Args:
            max_age_hours: Maximum age of news items
            use_cache: Use cached results if available
        
        Returns:
            List of NewsItem objects, deduplicated
        """
        cache_key = f"all_news_{max_age_hours}"
        
        # Check cache
        if use_cache:
            with self._cache_lock:
                if cache_key in self._cache:
                    if datetime.now() - self._cache_time[cache_key] < self._cache_duration:
                        return self._cache[cache_key]
        
        all_news = []

        # Fetch from all sources in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.rss_fetcher.fetch_all, max_age_hours): "rss",
                executor.submit(self.reddit_fetcher.fetch_all): "reddit",
            }
            
            for future in as_completed(futures):
                source = futures[future]
                try:
                    news = future.result()
                    all_news.extend(news)
                except Exception as e:
                    logger.warning(f"Failed to fetch {source}: {e}")
        
        # Deduplicate by title similarity
        all_news = self._deduplicate(all_news)
        
        # Sort by recency
        all_news.sort(key=lambda x: x.published_at, reverse=True)
        
        # Cache
        with self._cache_lock:
            self._cache[cache_key] = all_news
            self._cache_time[cache_key] = datetime.now()
        
        logger.info(f"Aggregated {len(all_news)} unique news items")
        return all_news
    
    def search_news(self, keywords: List[str], 
                    news: Optional[List[NewsItem]] = None) -> List[NewsItem]:
        """
        Search news items for keywords.
        
        Args:
            keywords: List of keywords to search for
            news: Optional list of news to search (fetches if None)
        
        Returns:
            Filtered and scored news items
        """
        if news is None:
            news = self.fetch_all_news()
        
        matching = []
        
        for item in news:
            text = f"{item.title} {item.content}".lower()
            
            # Count keyword matches
            matches = sum(1 for kw in keywords if kw.lower() in text)
            
            if matches > 0:
                item.relevance_score = matches / len(keywords)
                item.keywords = [kw for kw in keywords if kw.lower() in text]
                matching.append(item)
        
        # Sort by relevance
        matching.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return matching
    
    def get_market_news(self, market_question: str,
                        market_keywords: Optional[List[str]] = None) -> List[NewsItem]:
        """
        Get news relevant to a specific market.
        
        Args:
            market_question: The market question text
            market_keywords: Optional additional keywords
        
        Returns:
            Relevant news items
        """
        # Extract keywords from question
        keywords = self._extract_keywords(market_question)
        
        if market_keywords:
            keywords.extend(market_keywords)
        
        # Remove duplicates
        keywords = list(set(keywords))
        
        return self.search_news(keywords)
    
    def get_trending_topics(self) -> List[str]:
        """Get currently trending topics."""
        return self.trends_fetcher.get_trending_searches()
    
    def check_topic_interest(self, topics: List[str]) -> Dict[str, float]:
        """Check Google search interest for topics."""
        return self.trends_fetcher.get_interest_over_time(topics)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        # Remove common words
        stop_words = {
            'will', 'the', 'be', 'in', 'by', 'to', 'a', 'an', 'is', 'are',
            'on', 'for', 'of', 'and', 'or', 'that', 'this', 'with', 'as',
            'at', 'from', 'it', 'have', 'has', 'do', 'does', 'did', 'was',
            'were', 'been', 'being', 'which', 'who', 'whom', 'whose',
            'before', 'after', 'during', 'while', 'until', 'unless',
        }
        
        # Tokenize and clean
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = [w for w in words if w not in stop_words]
        
        # Get unique, prioritize longer words
        keywords = list(set(keywords))
        keywords.sort(key=len, reverse=True)
        
        return keywords[:10]  # Return top 10
    
    def _deduplicate(self, news: List[NewsItem]) -> List[NewsItem]:
        """Remove duplicate news items by title similarity."""
        seen_titles = set()
        unique = []
        
        for item in news:
            # Normalize title
            normalized = re.sub(r'[^\w\s]', '', item.title.lower())
            normalized = ' '.join(normalized.split()[:5])  # First 5 words
            
            if normalized not in seen_titles:
                seen_titles.add(normalized)
                unique.append(item)
        
        return unique
