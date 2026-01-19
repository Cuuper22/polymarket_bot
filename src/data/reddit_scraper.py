"""
Reddit Scraper - No API Key Required
Uses Reddit's public JSON endpoints to fetch posts and comments.
"""
import logging
import time
import random
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)

@dataclass
class RedditPost:
    """A Reddit post."""
    title: str
    selftext: str
    subreddit: str
    score: int
    num_comments: int
    created_utc: datetime
    url: str
    permalink: str
    
    @property
    def age_hours(self) -> float:
        """Hours since post was created."""
        return (datetime.now() - self.created_utc).total_seconds() / 3600


class RedditScraper:
    """
    Scrape Reddit without API keys using public JSON endpoints.
    
    Reddit exposes .json endpoints for all pages:
    - https://www.reddit.com/r/subreddit/hot.json
    - https://www.reddit.com/r/subreddit/new.json
    - https://www.reddit.com/r/subreddit/top.json?t=day
    """
    
    BASE_URL = "https://www.reddit.com"  # Use www.reddit.com with proper headers
    
    # Subreddits relevant to prediction markets
    DEFAULT_SUBREDDITS = [
        "polymarket",
        "Polymarket", 
        "predictit",
        "wallstreetbets",
        "stocks",
        "investing",
        "cryptocurrency",
        "bitcoin",
        "ethereum",
        "politics",
        "news",
        "worldnews",
        "technology",
        "economics",
    ]
    
    def __init__(self, subreddits: Optional[List[str]] = None):
        """
        Initialize the scraper.
        
        Args:
            subreddits: List of subreddits to scrape. Defaults to prediction-relevant ones.
        """
        self.subreddits = subreddits or self.DEFAULT_SUBREDDITS
        self.session = requests.Session()
        
        # Reddit requires a descriptive User-Agent for public access
        # Use a browser-like User-Agent to avoid 403 blocks
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
        import random
        self.session.headers.update({
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        })
        
        self._last_request = 0
        self._min_delay = 2.0  # Minimum seconds between requests (respect rate limits)
    
    def _rate_limit(self):
        """Enforce rate limiting to avoid getting blocked."""
        elapsed = time.time() - self._last_request
        if elapsed < self._min_delay:
            sleep_time = self._min_delay - elapsed + random.uniform(0.5, 1.5)
            time.sleep(sleep_time)
        self._last_request = time.time()
    
    def _fetch_json(self, url: str) -> Optional[Dict]:
        """Fetch JSON from a URL with error handling."""
        self._rate_limit()
        
        try:
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 429:
                logger.warning("Reddit rate limit hit, waiting...")
                time.sleep(60)
                return None
            
            if response.status_code != 200:
                logger.debug(f"Reddit returned {response.status_code} for {url}")
                return None
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Reddit request failed: {e}")
            return None
        except Exception as e:
            logger.debug(f"Reddit parse failed: {e}")
            return None
    
    def get_subreddit_posts(self, subreddit: str, sort: str = "hot", 
                           limit: int = 25, time_filter: str = "day") -> List[RedditPost]:
        """
        Get posts from a subreddit.
        
        Args:
            subreddit: Subreddit name (without r/)
            sort: "hot", "new", "top", "rising"
            limit: Max posts to fetch (max 100)
            time_filter: For "top" sort: "hour", "day", "week", "month", "year", "all"
            
        Returns:
            List of RedditPost objects
        """
        url = f"{self.BASE_URL}/r/{subreddit}/{sort}.json?limit={limit}"
        if sort == "top":
            url += f"&t={time_filter}"
        
        data = self._fetch_json(url)
        if not data:
            return []
        
        posts = []
        try:
            children = data.get("data", {}).get("children", [])
            for child in children:
                post_data = child.get("data", {})
                
                # Skip stickied posts
                if post_data.get("stickied"):
                    continue
                
                posts.append(RedditPost(
                    title=post_data.get("title", ""),
                    selftext=post_data.get("selftext", "")[:500],  # Limit text length
                    subreddit=post_data.get("subreddit", subreddit),
                    score=post_data.get("score", 0),
                    num_comments=post_data.get("num_comments", 0),
                    created_utc=datetime.fromtimestamp(post_data.get("created_utc", 0)),
                    url=post_data.get("url", ""),
                    permalink=f"https://reddit.com{post_data.get('permalink', '')}",
                ))
        except Exception as e:
            logger.error(f"Error parsing Reddit posts: {e}")
        
        return posts
    
    def get_all_posts(self, max_age_hours: int = 24, 
                      min_score: int = 10) -> List[RedditPost]:
        """
        Get posts from all configured subreddits.
        
        Args:
            max_age_hours: Maximum age of posts to include
            min_score: Minimum score (upvotes) to include
            
        Returns:
            List of RedditPost objects, sorted by score
        """
        all_posts = []
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        for subreddit in self.subreddits:
            try:
                # Get hot posts
                posts = self.get_subreddit_posts(subreddit, sort="hot", limit=25)
                
                for post in posts:
                    if post.created_utc >= cutoff and post.score >= min_score:
                        all_posts.append(post)
                        
            except Exception as e:
                logger.debug(f"Failed to fetch r/{subreddit}: {e}")
                continue
        
        # Sort by score
        all_posts.sort(key=lambda p: p.score, reverse=True)
        
        logger.info(f"Scraped {len(all_posts)} Reddit posts from {len(self.subreddits)} subreddits")
        return all_posts
    
    def search_posts(self, query: str, subreddit: Optional[str] = None,
                    limit: int = 25) -> List[RedditPost]:
        """
        Search Reddit for posts matching a query.
        
        Args:
            query: Search query
            subreddit: Optional subreddit to limit search
            limit: Max results
            
        Returns:
            List of matching posts
        """
        if subreddit:
            url = f"{self.BASE_URL}/r/{subreddit}/search.json?q={query}&restrict_sr=on&limit={limit}&sort=relevance&t=week"
        else:
            url = f"{self.BASE_URL}/search.json?q={query}&limit={limit}&sort=relevance&t=week"
        
        data = self._fetch_json(url)
        if not data:
            return []
        
        posts = []
        try:
            children = data.get("data", {}).get("children", [])
            for child in children:
                post_data = child.get("data", {})
                posts.append(RedditPost(
                    title=post_data.get("title", ""),
                    selftext=post_data.get("selftext", "")[:500],
                    subreddit=post_data.get("subreddit", ""),
                    score=post_data.get("score", 0),
                    num_comments=post_data.get("num_comments", 0),
                    created_utc=datetime.fromtimestamp(post_data.get("created_utc", 0)),
                    url=post_data.get("url", ""),
                    permalink=f"https://reddit.com{post_data.get('permalink', '')}",
                ))
        except Exception as e:
            logger.error(f"Error parsing Reddit search: {e}")
        
        return posts
    
    def get_market_related_posts(self, market_question: str, 
                                 max_posts: int = 20) -> List[RedditPost]:
        """
        Get posts related to a specific prediction market.
        
        Args:
            market_question: The market question
            max_posts: Maximum posts to return
            
        Returns:
            List of relevant posts
        """
        # Extract key terms from market question
        keywords = self._extract_keywords(market_question)
        
        all_posts = []
        seen_urls = set()
        
        for keyword in keywords[:3]:  # Search top 3 keywords
            posts = self.search_posts(keyword, limit=10)
            for post in posts:
                if post.url not in seen_urls:
                    seen_urls.add(post.url)
                    all_posts.append(post)
        
        # Sort by relevance (score * recency)
        now = datetime.now()
        all_posts.sort(
            key=lambda p: p.score * (1 / (1 + (now - p.created_utc).total_seconds() / 3600)),
            reverse=True
        )
        
        return all_posts[:max_posts]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract searchable keywords from text."""
        # Remove common words
        stop_words = {
            "will", "the", "a", "an", "in", "on", "at", "to", "for", "of",
            "by", "be", "is", "are", "was", "were", "been", "being",
            "have", "has", "had", "do", "does", "did", "can", "could",
            "would", "should", "may", "might", "must", "shall",
            "this", "that", "these", "those", "it", "its",
            "before", "after", "during", "between", "under", "over",
            "and", "or", "but", "if", "then", "else", "when", "where",
            "what", "which", "who", "whom", "whose", "why", "how",
        }
        
        words = text.lower().replace("?", "").replace("!", "").split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Return unique keywords, preserving order
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        
        return unique


def create_reddit_scraper(subreddits: Optional[List[str]] = None) -> RedditScraper:
    """Create a Reddit scraper instance."""
    return RedditScraper(subreddits)
