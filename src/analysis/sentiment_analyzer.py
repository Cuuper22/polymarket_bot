"""
Sentiment Analysis Engine - Analyzes text sentiment using free tools
Uses VADER for quick sentiment, TextBlob as backup
"""
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)


@dataclass 
class SentimentResult:
    """Result of sentiment analysis."""
    text: str
    compound_score: float  # -1 to 1
    positive: float  # 0 to 1
    negative: float  # 0 to 1
    neutral: float  # 0 to 1
    confidence: float  # 0 to 1
    
    @property
    def label(self) -> str:
        """Get sentiment label."""
        if self.compound_score >= 0.05:
            return "positive"
        elif self.compound_score <= -0.05:
            return "negative"
        return "neutral"
    
    @property
    def is_strong(self) -> bool:
        """Check if sentiment is strong."""
        return abs(self.compound_score) >= 0.5


class VaderSentimentAnalyzer:
    """VADER sentiment analyzer - optimized for social media."""
    
    def __init__(self):
        self._analyzer = None
    
    def _get_analyzer(self):
        """Lazy initialization of VADER."""
        if self._analyzer is None:
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore[import-not-found]
                self._analyzer = SentimentIntensityAnalyzer()
            except ImportError:
                logger.warning("vaderSentiment not installed")
                return None
        return self._analyzer
    
    def analyze(self, text: str) -> Optional[SentimentResult]:
        """
        Analyze sentiment of text.
        
        Args:
            text: Text to analyze
        
        Returns:
            SentimentResult or None if failed
        """
        analyzer = self._get_analyzer()
        if not analyzer or not text:
            return None
        
        assert analyzer is not None
        
        try:
            scores = analyzer.polarity_scores(text)
            
            # Calculate confidence based on text length and score strength
            word_count = len(text.split())
            score_strength = abs(scores['compound'])
            confidence = min(1.0, (word_count / 50) * (0.5 + score_strength / 2))
            
            return SentimentResult(
                text=text[:200],
                compound_score=scores['compound'],
                positive=scores['pos'],
                negative=scores['neg'],
                neutral=scores['neu'],
                confidence=confidence,
            )
        except Exception as e:
            logger.error(f"VADER analysis failed: {e}")
            return None


class TextBlobSentimentAnalyzer:
    """TextBlob sentiment analyzer - backup option."""
    
    def analyze(self, text: str) -> Optional[SentimentResult]:
        """Analyze sentiment using TextBlob."""
        try:
            from textblob import TextBlob  # type: ignore[import-not-found]
        except ImportError:
            logger.warning("textblob not installed")
            return None
        
        if not text:
            return None
        
        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity  # -1 to 1
            subjectivity = blob.sentiment.subjectivity  # 0 to 1
            
            # Map to VADER-like scores
            if polarity > 0:
                pos = polarity
                neg = 0
            else:
                pos = 0
                neg = abs(polarity)
            neutral = 1 - abs(polarity)
            
            # Confidence based on subjectivity
            confidence = subjectivity
            
            return SentimentResult(
                text=text[:200],
                compound_score=polarity,
                positive=pos,
                negative=neg,
                neutral=neutral,
                confidence=confidence,
            )
        except Exception as e:
            logger.error(f"TextBlob analysis failed: {e}")
            return None


class KeywordSentimentAnalyzer:
    """Simple keyword-based sentiment analyzer - no dependencies."""
    
    POSITIVE_WORDS = {
        'bullish', 'surge', 'soar', 'rally', 'gain', 'rise', 'climb',
        'success', 'win', 'victory', 'breakthrough', 'approve', 'pass',
        'increase', 'growth', 'boost', 'jump', 'spike', 'boom',
        'confident', 'optimistic', 'positive', 'strong', 'solid',
        'confirmed', 'agreed', 'yes', 'likely', 'probable', 'certain',
        'launch', 'release', 'announce', 'reveal', 'unveil',
    }
    
    NEGATIVE_WORDS = {
        'bearish', 'crash', 'plunge', 'drop', 'fall', 'decline', 'sink',
        'fail', 'loss', 'defeat', 'reject', 'deny', 'block', 'ban',
        'decrease', 'shrink', 'cut', 'slump', 'dump', 'bust',
        'worried', 'pessimistic', 'negative', 'weak', 'unstable',
        'cancelled', 'disputed', 'no', 'unlikely', 'improbable', 'doubt',
        'delay', 'postpone', 'suspend', 'halt', 'stop',
        'investigation', 'scandal', 'crisis', 'problem', 'issue',
    }
    
    INTENSIFIERS = {
        'very', 'extremely', 'highly', 'significantly', 'massively',
        'strongly', 'definitely', 'absolutely', 'completely', 'totally',
    }
    
    NEGATORS = {
        'not', 'no', 'never', 'neither', 'nobody', 'nothing',
        "n't", 'cannot', "won't", "wouldn't", "shouldn't", "couldn't",
    }
    
    def analyze(self, text: str) -> SentimentResult:
        """
        Analyze sentiment using keyword matching.
        Simple but dependency-free.
        """
        if not text:
            return SentimentResult(
                text="",
                compound_score=0,
                positive=0,
                negative=0,
                neutral=1,
                confidence=0,
            )
        
        words = text.lower().split()
        word_set = set(words)
        
        pos_count = sum(1 for w in words if w in self.POSITIVE_WORDS)
        neg_count = sum(1 for w in words if w in self.NEGATIVE_WORDS)
        
        # Check for negation
        has_negation = bool(word_set & self.NEGATORS)
        if has_negation:
            pos_count, neg_count = neg_count, pos_count
        
        # Check for intensifiers
        intensifier_count = sum(1 for w in words if w in self.INTENSIFIERS)
        intensity = 1 + (intensifier_count * 0.2)
        
        total = pos_count + neg_count
        if total == 0:
            return SentimentResult(
                text=text[:200],
                compound_score=0,
                positive=0,
                negative=0,
                neutral=1,
                confidence=0.1,
            )
        
        pos_ratio = pos_count / total
        neg_ratio = neg_count / total
        
        compound = (pos_ratio - neg_ratio) * intensity
        compound = max(-1, min(1, compound))  # Clamp to [-1, 1]
        
        confidence = min(1.0, total / 10)  # More keywords = more confidence
        
        return SentimentResult(
            text=text[:200],
            compound_score=compound,
            positive=pos_ratio,
            negative=neg_ratio,
            neutral=max(0, 1 - total / len(words)),
            confidence=confidence,
        )


class SentimentAnalyzer:
    """
    Main sentiment analyzer that combines multiple methods.
    Uses ensemble approach for more robust results.
    """
    
    def __init__(self, use_vader: bool = True, use_textblob: bool = True):
        self.analyzers = []
        
        # Add analyzers in order of preference
        if use_vader:
            self.analyzers.append(("vader", VaderSentimentAnalyzer()))
        if use_textblob:
            self.analyzers.append(("textblob", TextBlobSentimentAnalyzer()))
        
        # Always have keyword analyzer as fallback
        self.analyzers.append(("keyword", KeywordSentimentAnalyzer()))
    
    def analyze(self, text: str) -> SentimentResult:
        """
        Analyze sentiment using ensemble of methods.
        
        Args:
            text: Text to analyze
        
        Returns:
            Combined SentimentResult
        """
        if not text:
            return SentimentResult(
                text="",
                compound_score=0,
                positive=0,
                negative=0,
                neutral=1,
                confidence=0,
            )
        
        # Clean text
        text = self._clean_text(text)
        
        results = []
        weights = []
        
        for name, analyzer in self.analyzers:
            result = analyzer.analyze(text)
            if result:
                results.append(result)
                # VADER gets higher weight
                weight = 2.0 if name == "vader" else 1.0
                weights.append(weight)
        
        if not results:
            # Fallback
            return KeywordSentimentAnalyzer().analyze(text)
        
        # Weighted average of scores
        total_weight = sum(weights)
        
        compound = sum(r.compound_score * w for r, w in zip(results, weights)) / total_weight
        positive = sum(r.positive * w for r, w in zip(results, weights)) / total_weight
        negative = sum(r.negative * w for r, w in zip(results, weights)) / total_weight
        neutral = sum(r.neutral * w for r, w in zip(results, weights)) / total_weight
        confidence = sum(r.confidence * w for r, w in zip(results, weights)) / total_weight
        
        return SentimentResult(
            text=text[:200],
            compound_score=compound,
            positive=positive,
            negative=negative,
            neutral=neutral,
            confidence=confidence,
        )
    
    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze multiple texts."""
        return [self.analyze(text) for text in texts]
    
    def analyze_for_market(self, texts: List[str], 
                           yes_keywords: Optional[List[str]] = None,
                           no_keywords: Optional[List[str]] = None) -> Tuple[float, float]:
        """
        Analyze texts for a binary market outcome.
        
        Args:
            texts: List of texts to analyze
            yes_keywords: Keywords indicating YES outcome
            no_keywords: Keywords indicating NO outcome
        
        Returns:
            (yes_sentiment, no_sentiment) scores from -1 to 1
        """
        if not texts:
            return 0.0, 0.0
        
        yes_scores = []
        no_scores = []
        
        for text in texts:
            result = self.analyze(text)
            text_lower = text.lower()
            
            # Check for outcome-specific keywords
            has_yes_keywords = any(kw.lower() in text_lower for kw in (yes_keywords or []))
            has_no_keywords = any(kw.lower() in text_lower for kw in (no_keywords or []))
            
            weighted_score = result.compound_score * result.confidence
            
            if has_yes_keywords and not has_no_keywords:
                yes_scores.append(weighted_score)
            elif has_no_keywords and not has_yes_keywords:
                no_scores.append(-weighted_score)  # Flip for NO
            else:
                # Neutral text - affects both
                yes_scores.append(weighted_score * 0.5)
                no_scores.append(weighted_score * 0.5)
        
        yes_sentiment = sum(yes_scores) / len(yes_scores) if yes_scores else 0
        no_sentiment = sum(no_scores) / len(no_scores) if no_scores else 0
        
        return yes_sentiment, no_sentiment
    
    def _clean_text(self, text: str) -> str:
        """Clean text for analysis."""
        # Remove URLs
        text = re.sub(r'http\S+|www.\S+', '', text)
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        return text


def analyze_market_sentiment(market_question: str, 
                             news_texts: List[str]) -> Dict:
    """
    Convenience function to analyze sentiment for a market.
    
    Args:
        market_question: The market question
        news_texts: Related news texts
    
    Returns:
        Dictionary with sentiment analysis results
    """
    analyzer = SentimentAnalyzer()
    
    # Analyze individual texts
    results = analyzer.analyze_batch(news_texts)
    
    if not results:
        return {
            "overall_sentiment": 0,
            "confidence": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "strong_signals": [],
        }
    
    # Aggregate
    overall = sum(r.compound_score * r.confidence for r in results) / len(results)
    avg_confidence = sum(r.confidence for r in results) / len(results)
    
    positive_count = sum(1 for r in results if r.label == "positive")
    negative_count = sum(1 for r in results if r.label == "negative")
    neutral_count = sum(1 for r in results if r.label == "neutral")
    
    # Find strong signals
    strong_signals = [
        {"text": r.text, "score": r.compound_score}
        for r in results if r.is_strong
    ]
    
    return {
        "overall_sentiment": overall,
        "confidence": avg_confidence,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "strong_signals": strong_signals[:5],  # Top 5
    }
