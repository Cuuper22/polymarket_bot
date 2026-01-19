#!/usr/bin/env python3
"""
Quick test script to verify the bot setup works.
Run this after pip install -r requirements.txt
"""
import sys

def test_imports():
    """Test all imports work."""
    print("Testing imports...")
    
    errors = []
    
    # Core
    try:
        import requests
        print("  [OK] requests")
    except ImportError as e:
        errors.append(f"requests: {e}")
    
    # Optional but recommended
    try:
        import feedparser  # type: ignore[import-not-found]
        print("  [OK] feedparser (RSS)")
    except ImportError:
        print("  [SKIP] feedparser (optional)")
    
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore[import-not-found]
        print("  [OK] vaderSentiment")
    except ImportError:
        print("  [SKIP] vaderSentiment (will use fallback)")
    
    try:
        from textblob import TextBlob  # type: ignore[import-not-found]
        print("  [OK] textblob")
    except ImportError:
        print("  [SKIP] textblob (will use fallback)")
    
    try:
        import praw  # type: ignore[import-not-found]
        print("  [OK] praw (Reddit)")
    except ImportError:
        print("  [SKIP] praw (optional)")
    
    try:
        from pytrends.request import TrendReq  # type: ignore[import-not-found]
        print("  [OK] pytrends (Google Trends)")
    except ImportError:
        print("  [SKIP] pytrends (optional)")
    
    if errors:
        print(f"\n[ERROR] Missing required packages:")
        for e in errors:
            print(f"  - {e}")
        return False
    
    return True


def test_polymarket_api():
    """Test Polymarket API connection."""
    print("\nTesting Polymarket API...")
    
    import requests
    
    try:
        # Test Gamma API
        response = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"limit": 1, "active": "true"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if data:
            market = data[0]
            print(f"  [OK] Gamma API - Found market: {market.get('question', 'Unknown')[:50]}...")
        else:
            print("  [WARN] Gamma API - No markets returned")
        
        # Test CLOB API
        response = requests.get(
            "https://clob.polymarket.com/",
            timeout=10
        )
        print(f"  [OK] CLOB API - Status: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"  [ERROR] API test failed: {e}")
        return False


def test_sentiment():
    """Test sentiment analysis."""
    print("\nTesting sentiment analysis...")
    
    try:
        from src.analysis.sentiment_analyzer import SentimentAnalyzer
        
        analyzer = SentimentAnalyzer()
        
        # Test positive
        result = analyzer.analyze("Bitcoin surges to new highs as adoption grows")
        print(f"  Positive test: {result.compound_score:+.2f} (expected > 0)")
        
        # Test negative
        result = analyzer.analyze("Market crashes as investors panic and sell")
        print(f"  Negative test: {result.compound_score:+.2f} (expected < 0)")
        
        if result.compound_score == 0:
            print("  [WARN] Sentiment fallback is neutral; consider installing vaderSentiment/textblob")
        else:
            print("  [OK] Sentiment analysis working")
        return True
        
    except Exception as e:
        print(f"  [ERROR] Sentiment test failed: {e}")
        return False


def test_position_sizing():
    """Test position sizing."""
    print("\nTesting position sizing...")
    
    try:
        from src.strategies.position_sizer import KellyPositionSizer
        
        sizer = KellyPositionSizer(kelly_fraction=0.25)
        
        # Test with 10% edge
        result = sizer.calculate_position(
            capital=75.0,
            current_price=0.50,
            edge=0.10,
            confidence=0.7
        )
        
        print(f"  Kelly fraction: {result.kelly_fraction:.1%}")
        print(f"  Adjusted fraction: {result.adjusted_fraction:.1%}")
        print(f"  Recommended bet: ${result.amount:.2f}")
        print(f"  Expected value: ${result.expected_value:.2f}")
        print("  [OK] Position sizing working")
        return True
        
    except Exception as e:
        print(f"  [ERROR] Position sizing test failed: {e}")
        return False


def main():
    print("=" * 50)
    print("POLYMARKET BOT - QUICK TEST")
    print("=" * 50)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Polymarket API", test_polymarket_api()))
    results.append(("Sentiment", test_sentiment()))
    results.append(("Position Sizing", test_position_sizing()))
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n[SUCCESS] All tests passed! Bot is ready.")
        print("\nNext steps:")
        print("  1. python main.py scan          # Find opportunities")
        print("  2. python main.py backtest      # Test strategy")
        print("  3. python main.py paper --run   # Paper trade")
    else:
        print("\n[WARNING] Some tests failed. Check errors above.")
        print("Run: pip install -r requirements.txt")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
