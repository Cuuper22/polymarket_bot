"""
Grok 4.1 Fast Integration via OpenRouter API
For sentiment analysis and market intelligence on prediction markets.
"""
import os
import json
import logging
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class GrokAnalysis:
    """Result from Grok analysis."""
    market_question: str
    sentiment_score: float  # -1 to 1
    confidence: float  # 0 to 1
    price_direction: str  # 'up', 'down', 'neutral'
    key_factors: List[str]
    summary: str
    timestamp: datetime


class GrokAnalyzer:
    """
    Uses Grok 4.1 Fast via OpenRouter for market sentiment analysis.
    Particularly strong at analyzing Twitter/X sentiment and breaking news.
    """
    
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODEL = "x-ai/grok-4.1-fast"  # Grok 4.1 fast model
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Grok analyzer.
        
        Args:
            api_key: OpenRouter API key. Falls back to OPENROUTER_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.warning("No OpenRouter API key provided. Grok analysis disabled.")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://polymarket-bot.local",
            "X-Title": "Polymarket Trading Bot"
        }
    
    def analyze_market(self, market_question: str, current_price: float,
                       recent_news: Optional[List[str]] = None) -> Optional[GrokAnalysis]:
        """
        Analyze a prediction market using Grok.
        
        Args:
            market_question: The market question (e.g., "Will Bitcoin reach $100k?")
            current_price: Current YES price (0-1)
            recent_news: List of recent news headlines related to the market
            
        Returns:
            GrokAnalysis with sentiment, direction prediction, and reasoning
        """
        if not self.api_key:
            return None
        
        news_context = ""
        if recent_news:
            news_context = "\n\nRecent news:\n" + "\n".join(f"- {n}" for n in recent_news[:10])
        
        prompt = f"""Analyze this prediction market for trading opportunities:

Market: {market_question}
Current YES price: {current_price:.1%} (meaning the market thinks there's a {current_price:.1%} chance of YES)
{news_context}

Provide a trading analysis in JSON format:
{{
    "sentiment_score": <float from -1 (very bearish) to 1 (very bullish)>,
    "confidence": <float from 0 to 1, how confident in this analysis>,
    "price_direction": <"up", "down", or "neutral" - expected short-term price movement>,
    "key_factors": [<list of 2-4 key factors driving this assessment>],
    "summary": <one sentence summary of the trading opportunity>
}}

Focus on:
1. Is the current price too low or too high based on recent developments?
2. What is the likely short-term (24-48h) price direction?
3. Are there any catalysts that could move the price soon?

Return ONLY the JSON, no other text."""

        try:
            response = requests.post(
                self.OPENROUTER_URL,
                headers=self.headers,
                json={
                    "model": self.MODEL,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                return None
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Parse JSON from response
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content.strip())
            
            return GrokAnalysis(
                market_question=market_question,
                sentiment_score=float(data.get("sentiment_score", 0)),
                confidence=float(data.get("confidence", 0.5)),
                price_direction=data.get("price_direction", "neutral"),
                key_factors=data.get("key_factors", []),
                summary=data.get("summary", ""),
                timestamp=datetime.now()
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Grok response: {e}")
            return None
        except Exception as e:
            logger.error(f"Grok analysis failed: {e}")
            return None
    
    def analyze_batch(self, markets: List[Dict]) -> Dict[str, GrokAnalysis]:
        """
        Analyze multiple markets efficiently.
        
        Args:
            markets: List of dicts with 'question', 'price', and optional 'news'
            
        Returns:
            Dict mapping market question to GrokAnalysis
        """
        if not self.api_key:
            return {}
        
        results = {}
        
        # Batch into groups of 5 for efficiency
        for market in markets[:10]:  # Limit to 10 to control API costs
            analysis = self.analyze_market(
                market_question=market.get("question", ""),
                current_price=market.get("price", 0.5),
                recent_news=market.get("news", [])
            )
            if analysis:
                results[market["question"]] = analysis
        
        return results
    
    def get_twitter_sentiment(self, topic: str) -> Optional[Dict]:
        """
        Get Twitter/X sentiment analysis for a topic using Grok.
        Grok has native access to Twitter data.
        
        Args:
            topic: Topic to analyze (e.g., "Bitcoin", "Fed interest rates")
            
        Returns:
            Dict with sentiment analysis
        """
        if not self.api_key:
            return None
        
        prompt = f"""Analyze current Twitter/X sentiment about: {topic}

Based on recent Twitter discussions and posts, provide:
{{
    "overall_sentiment": <float from -1 to 1>,
    "trending_direction": <"bullish", "bearish", "neutral">,
    "volume": <"high", "medium", "low" - how much discussion>,
    "key_narratives": [<list of 2-3 main talking points>],
    "notable_events": [<any breaking news or significant events>]
}}

Return ONLY the JSON."""

        try:
            response = requests.post(
                self.OPENROUTER_URL,
                headers=self.headers,
                json={
                    "model": self.MODEL,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 400
                },
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Grok API error: {response.status_code}")
                return None
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
            
        except Exception as e:
            logger.error(f"Twitter sentiment analysis failed: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if Grok API is available."""
        return self.api_key is not None


# Convenience function
def create_grok_analyzer(api_key: Optional[str] = None) -> GrokAnalyzer:
    """Create a Grok analyzer instance."""
    return GrokAnalyzer(api_key)
