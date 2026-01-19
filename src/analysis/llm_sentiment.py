"""
LLM-Enhanced Sentiment Analysis using Claude
=============================================
Uses Claude 4.5 Haiku for fast, accurate sentiment analysis
of news and market-related text data.

SETUP:
1. Set environment variable: ANTHROPIC_API_KEY=your_key_here
2. Or add to .env file (never commit this file!)
"""
import os
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Check for API key
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Try to import anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not installed. Run: pip install anthropic")


@dataclass
class SentimentResult:
    """Result from LLM sentiment analysis."""
    sentiment_score: float      # -1 to 1
    confidence: float           # 0 to 1
    direction: str              # "bullish", "bearish", "neutral"
    key_factors: List[str]      # Key factors identified
    reasoning: str              # Brief explanation
    model_used: str
    latency_ms: float


class ClaudeSentimentAnalyzer:
    """
    Uses Claude Haiku for fast sentiment analysis of market-related text.
    
    Haiku is ideal for:
    - Low latency (fast responses)
    - Cost efficiency (cheapest Claude model)
    - Good accuracy for classification tasks
    """
    
    MODEL = "claude-sonnet-4-20250514"  # Fast and cost-effective
    
    SYSTEM_PROMPT = """You are a financial sentiment analyst specializing in prediction markets. 
Your task is to analyze text and determine the sentiment regarding a specific market outcome.

For each analysis, you must return a JSON object with:
- sentiment_score: float from -1 (very bearish/unlikely) to 1 (very bullish/likely)
- confidence: float from 0 to 1 indicating your confidence in the assessment
- direction: "bullish", "bearish", or "neutral"
- key_factors: list of 2-4 key factors influencing your assessment
- reasoning: one sentence explaining your assessment

Be objective and focus on factual indicators. Consider:
- Source credibility
- Recency of information
- Strength of evidence
- Market implications

Return ONLY valid JSON, no other text."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize with API key from parameter or environment.
        
        Args:
            api_key: Optional API key. If not provided, uses ANTHROPIC_API_KEY env var.
        """
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.client = None
        
        if not ANTHROPIC_AVAILABLE:
            logger.error("anthropic package not available")
            return
        
        if not self.api_key:
            logger.warning("No API key provided. Set ANTHROPIC_API_KEY environment variable.")
            return
        
        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            logger.info("Claude sentiment analyzer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")
    
    @property
    def is_available(self) -> bool:
        """Check if the analyzer is ready to use."""
        return self.client is not None
    
    def analyze_text(self, 
                    text: str, 
                    market_question: str,
                    max_tokens: int = 300) -> Optional[SentimentResult]:
        """
        Analyze text sentiment relative to a market question.
        
        Args:
            text: News article, social media post, or other text
            market_question: The prediction market question
            max_tokens: Maximum response tokens
        
        Returns:
            SentimentResult or None if analysis fails
        """
        if not self.is_available:
            logger.warning("Claude analyzer not available, using fallback")
            return self._fallback_analysis(text, market_question)
        
        prompt = f"""Analyze the following text for sentiment regarding this prediction market:

MARKET QUESTION: {market_question}

TEXT TO ANALYZE:
{text[:2000]}  # Limit text length

Provide your analysis as JSON."""

        start_time = datetime.now()
        
        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=max_tokens,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            # Parse response
            content = response.content[0].text
            
            # Extract JSON
            try:
                # Handle potential markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                data = json.loads(content.strip())
                
                return SentimentResult(
                    sentiment_score=float(data.get("sentiment_score", 0)),
                    confidence=float(data.get("confidence", 0.5)),
                    direction=data.get("direction", "neutral"),
                    key_factors=data.get("key_factors", []),
                    reasoning=data.get("reasoning", ""),
                    model_used=self.MODEL,
                    latency_ms=latency
                )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Claude response: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return None
    
    def analyze_multiple(self,
                        texts: List[Dict],
                        market_question: str) -> List[SentimentResult]:
        """
        Analyze multiple texts and aggregate sentiment.
        
        Args:
            texts: List of dicts with 'text' and optional 'source', 'timestamp'
            market_question: The prediction market question
        
        Returns:
            List of SentimentResults
        """
        results = []
        
        for item in texts[:10]:  # Limit to 10 items
            text = item.get("text", "")
            if not text:
                continue
            
            result = self.analyze_text(text, market_question)
            if result:
                results.append(result)
        
        return results
    
    def get_aggregated_sentiment(self,
                                texts: List[Dict],
                                market_question: str) -> Tuple[float, float]:
        """
        Get aggregated sentiment score and confidence.
        
        Returns: (sentiment_score, confidence)
        """
        results = self.analyze_multiple(texts, market_question)
        
        if not results:
            return 0.0, 0.0
        
        # Weighted average by confidence
        total_weight = sum(r.confidence for r in results)
        if total_weight == 0:
            return 0.0, 0.0
        
        weighted_sentiment = sum(r.sentiment_score * r.confidence for r in results) / total_weight
        avg_confidence = sum(r.confidence for r in results) / len(results)
        
        return weighted_sentiment, avg_confidence
    
    def _fallback_analysis(self, text: str, market_question: str) -> SentimentResult:
        """
        Fallback analysis when Claude is not available.
        Uses simple keyword-based sentiment.
        """
        text_lower = text.lower()
        
        bullish_words = ["confirmed", "approved", "success", "win", "positive", "likely", 
                        "increase", "growth", "bullish", "yes", "will"]
        bearish_words = ["denied", "rejected", "failure", "loss", "negative", "unlikely",
                        "decrease", "decline", "bearish", "no", "won't"]
        
        bullish_count = sum(1 for w in bullish_words if w in text_lower)
        bearish_count = sum(1 for w in bearish_words if w in text_lower)
        
        total = bullish_count + bearish_count
        if total == 0:
            sentiment = 0.0
        else:
            sentiment = (bullish_count - bearish_count) / total
        
        return SentimentResult(
            sentiment_score=sentiment,
            confidence=0.3,  # Low confidence for fallback
            direction="bullish" if sentiment > 0.1 else "bearish" if sentiment < -0.1 else "neutral",
            key_factors=["keyword_analysis"],
            reasoning="Fallback keyword-based analysis (Claude unavailable)",
            model_used="fallback",
            latency_ms=0
        )


class BatchAnalyzer:
    """
    Batch analyzer for processing multiple news items efficiently.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.analyzer = ClaudeSentimentAnalyzer(api_key)
    
    def analyze_news_batch(self,
                          news_items: List[Dict],
                          market_question: str) -> Dict:
        """
        Analyze a batch of news items for a market.
        
        Returns dict with:
        - overall_sentiment: float
        - overall_confidence: float
        - item_count: int
        - bullish_count: int
        - bearish_count: int
        - individual_results: list
        """
        if not news_items:
            return {
                "overall_sentiment": 0.0,
                "overall_confidence": 0.0,
                "item_count": 0,
                "bullish_count": 0,
                "bearish_count": 0,
                "individual_results": []
            }
        
        results = []
        
        for item in news_items[:10]:
            text = item.get("title", "") + " " + item.get("content", "")
            if len(text.strip()) < 20:
                continue
            
            result = self.analyzer.analyze_text(text, market_question)
            if result:
                results.append({
                    "source": item.get("source", "unknown"),
                    "sentiment": result.sentiment_score,
                    "confidence": result.confidence,
                    "direction": result.direction,
                    "reasoning": result.reasoning
                })
        
        if not results:
            return {
                "overall_sentiment": 0.0,
                "overall_confidence": 0.0,
                "item_count": 0,
                "bullish_count": 0,
                "bearish_count": 0,
                "individual_results": []
            }
        
        # Aggregate
        total_conf = sum(r["confidence"] for r in results)
        if total_conf > 0:
            overall_sentiment = sum(r["sentiment"] * r["confidence"] for r in results) / total_conf
        else:
            overall_sentiment = 0.0
        
        overall_confidence = sum(r["confidence"] for r in results) / len(results)
        bullish = sum(1 for r in results if r["direction"] == "bullish")
        bearish = sum(1 for r in results if r["direction"] == "bearish")
        
        return {
            "overall_sentiment": overall_sentiment,
            "overall_confidence": overall_confidence,
            "item_count": len(results),
            "bullish_count": bullish,
            "bearish_count": bearish,
            "individual_results": results
        }


# Convenience function
def analyze_sentiment(text: str, market_question: str, api_key: Optional[str] = None) -> Tuple[float, float]:
    """
    Quick sentiment analysis.
    
    Returns: (sentiment_score, confidence)
    """
    analyzer = ClaudeSentimentAnalyzer(api_key)
    result = analyzer.analyze_text(text, market_question)
    
    if result:
        return result.sentiment_score, result.confidence
    return 0.0, 0.0


if __name__ == "__main__":
    # Test the analyzer
    print("LLM Sentiment Analyzer Test")
    print("=" * 50)
    
    analyzer = ClaudeSentimentAnalyzer()
    
    if not analyzer.is_available:
        print("\nClaude not available. To enable:")
        print("1. pip install anthropic")
        print("2. Set ANTHROPIC_API_KEY environment variable")
        print("\nUsing fallback analysis...")
    
    # Test text
    test_text = """
    Breaking: Federal Reserve announces unexpected rate cut of 0.5%.
    Markets rally on the news with major indices up over 2%.
    Analysts say this signals confidence in economic recovery.
    """
    
    test_question = "Will the S&P 500 close above 5000 by end of month?"
    
    result = analyzer.analyze_text(test_text, test_question)
    
    if result:
        print(f"\nSentiment Score: {result.sentiment_score:.2f}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Direction: {result.direction}")
        print(f"Key Factors: {result.key_factors}")
        print(f"Reasoning: {result.reasoning}")
        print(f"Model: {result.model_used}")
        print(f"Latency: {result.latency_ms:.0f}ms")
