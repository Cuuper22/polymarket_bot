#!/usr/bin/env python3
"""
Polymarket Trading Bot - Main Entry Point
Automated prediction market trading with news sentiment analysis
"""
import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('polymarket_bot.log'),
    ]
)
logger = logging.getLogger(__name__)


def setup_environment():
    """Setup the environment and check dependencies."""
    try:
        import requests
        logger.info("Core dependencies OK")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Run: pip install -r requirements.txt")
        sys.exit(1)


def cmd_scan(args):
    """Scan for trading opportunities."""
    from src.data.polymarket_client import PolymarketClient
    from src.data.news_aggregator import NewsAggregator
    from src.analysis.sentiment_analyzer import SentimentAnalyzer
    from src.strategies.edge_detector import EdgeDetector
    
    print("\n" + "=" * 60)
    print("POLYMARKET OPPORTUNITY SCANNER")
    print("=" * 60 + "\n")
    
    client = PolymarketClient()
    news_agg = NewsAggregator()
    sentiment = SentimentAnalyzer()
    edge_detector = EdgeDetector(min_edge=args.min_edge)
    
    print("Fetching active markets...")
    markets = client.get_active_markets(limit=args.limit, min_volume=args.min_volume)
    print(f"Found {len(markets)} markets\n")
    
    print("Fetching news...")
    news = news_agg.fetch_all_news(max_age_hours=24)
    print(f"Found {len(news)} news items\n")
    
    opportunities = []
    
    print("Analyzing markets for opportunities...")
    for i, market in enumerate(markets[:args.analyze]):
        print(f"  [{i+1}/{min(len(markets), args.analyze)}] {market.question[:50]}...")
        
        try:
            # Get relevant news
            market_news = news_agg.search_news(
                market.question.split()[:5], 
                news
            )
            
            # Analyze sentiment
            if market_news:
                texts = [f"{n.title} {n.content}" for n in market_news[:5]]
                sent_result = sentiment.analyze(" ".join(texts))
            else:
                from src.analysis.sentiment_analyzer import SentimentResult
                sent_result = SentimentResult(
                    text="",
                    compound_score=0,
                    positive=0,
                    negative=0,
                    neutral=1,
                    confidence=0.3,
                )
            
            # Detect edge
            market_data = {
                'id': market.id,
                'question': market.question,
                'slug': market.slug,
                'yes_price': market.yes_price,
                'no_price': market.no_price,
                'yes_token_id': market.yes_token_id,
                'no_token_id': market.no_token_id,
                'volume_24h': market.volume_24h,
                'liquidity': market.liquidity,
            }
            
            opp = edge_detector.detect_opportunities(
                market_data,
                sentiment_score=sent_result.compound_score,
                sentiment_confidence=sent_result.confidence
            )
            
            if opp:
                opportunities.append(opp)
                
        except Exception as e:
            logger.warning(f"Error: {e}")
            continue
    
    # Sort by score
    opportunities = edge_detector.rank_opportunities(opportunities)
    
    print("\n" + "=" * 60)
    print(f"TOP OPPORTUNITIES (min edge: {args.min_edge:.0%})")
    print("=" * 60)
    
    if not opportunities:
        print("\nNo opportunities found meeting criteria.")
    else:
        for i, opp in enumerate(opportunities[:10]):
            print(f"\n{i+1}. {opp.market_question[:60]}")
            print(f"   Direction: {opp.direction} | Price: {opp.current_price:.2f}")
            print(f"   Edge: {opp.edge:.1%} | Confidence: {opp.confidence:.1%}")
            print(f"   Signals: {', '.join(s.type.value for s in opp.signals)}")
    
    print("\n" + "=" * 60 + "\n")


def cmd_paper_trade(args):
    """Run paper trading."""
    from src.trading.paper_trader import PaperTradingAccount, PaperTradingBot
    from config.settings import settings, StrategyMode
    
    if args.strategy:
        settings.STRATEGY_MODE = StrategyMode(args.strategy)
    
    print("\n" + "=" * 60)
    print("PAPER TRADING MODE")
    print("=" * 60 + "\n")
    
    if args.reset:
        account = PaperTradingAccount(args.capital)
        account.reset(confirm=True)
        print("Account reset!\n")
    
    if args.status:
        account = PaperTradingAccount(args.capital)
        summary = account.get_account_summary()
        
        print("ACCOUNT STATUS:")
        print("-" * 40)
        for key, value in summary.items():
            print(f"  {key}: {value}")
        
        positions = account.get_open_positions()
        if positions:
            print("\nOPEN POSITIONS:")
            print("-" * 40)
            for p in positions:
                print(f"  {p['direction']} ${p['amount']:.2f} @ {p['entry_price']:.2f}")
                print(f"    {p['market_question']}")
                print(f"    Unrealized: ${p['unrealized_pnl']:.2f}")
        
        return
    
    if args.run:
        bot = PaperTradingBot(args.capital)
        
        print(f"Starting paper trading bot with ${args.capital} capital")
        print(f"Scan interval: {args.interval} minutes")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Running cycle...")
                result = bot.run_cycle()
                
                print(f"  Opportunities: {result['opportunities_found']}")
                print(f"  Positions opened: {result['positions_opened']}")
                print(f"  Positions closed: {result['positions_closed']}")
                
                summary = result['account_summary']
                print(f"  Capital: ${summary['current_capital']} | Return: {summary['total_return']}")
                
                print(f"\nSleeping {args.interval} minutes...")
                time.sleep(args.interval * 60)
                
        except KeyboardInterrupt:
            print("\n\nStopping bot...")
            summary = bot.account.get_account_summary()
            print("\nFINAL STATUS:")
            for key, value in summary.items():
                print(f"  {key}: {value}")


def cmd_backtest(args):
    """Run backtest."""
    from src.backtesting.backtest_engine import (
        BacktestEngine, generate_simulated_markets
    )
    from datetime import timedelta
    
    print("\n" + "=" * 60)
    print("BACKTESTING")
    print("=" * 60 + "\n")
    
    # Generate simulated markets
    start_date = datetime.now() - timedelta(days=args.days)
    end_date = datetime.now()
    
    print(f"Generating {args.markets} simulated markets...")
    markets = generate_simulated_markets(
        num_markets=args.markets,
        start_date=start_date,
        duration_days=args.days
    )
    
    # Define strategy
    def simple_sentiment_strategy(market_data, capital):
        """Simple strategy based on sentiment divergence."""
        sentiment = market_data.get('sentiment', 0)
        price = market_data.get('price', 0.5)
        
        # Calculate implied probability from sentiment
        implied = 0.5 + sentiment * 0.3
        implied = max(0.2, min(0.8, implied))
        
        # Look for divergence
        divergence = implied - price
        
        if abs(divergence) >= args.min_edge:
            if capital <= args.capital * 0.25:
                return None
            direction = "YES" if divergence > 0 else "NO"
            trade_price = price if direction == "YES" else (1 - price)
            
            # Kelly-like sizing
            edge = abs(divergence)
            bet_fraction = min(0.15, edge * 0.5)
            amount = capital * bet_fraction
            
            if amount >= 3.0:
                return {
                    'action': 'buy',
                    'direction': direction,
                    'price': trade_price,
                    'amount': amount,
                    'edge': edge,
                    'confidence': 0.6,
                }
        
        return None
    
    # Run backtest
    print(f"Running backtest from {start_date.date()} to {end_date.date()}...")
    engine = BacktestEngine(initial_capital=args.capital)
    result = engine.run_backtest(
        markets=markets,
        strategy_fn=simple_sentiment_strategy,
        start_date=start_date,
        end_date=end_date
    )
    
    result.print_summary()
    
    # Show individual trades
    if args.show_trades and result.trades:
        print("\nTRADE HISTORY:")
        print("-" * 40)
        for t in result.trades[:20]:
            outcome = "WIN" if t.outcome.value == "win" else "LOSS"
            print(f"  {outcome}: ${t.pnl:+.2f} ({t.return_pct:+.1%}) - {t.direction}")


def cmd_analyze(args):
    """Analyze a specific market."""
    from src.data.polymarket_client import PolymarketClient
    from src.data.news_aggregator import NewsAggregator
    from src.analysis.sentiment_analyzer import SentimentAnalyzer, analyze_market_sentiment
    
    print("\n" + "=" * 60)
    print("MARKET ANALYSIS")
    print("=" * 60 + "\n")
    
    client = PolymarketClient()
    news_agg = NewsAggregator()
    
    # Fetch market
    print(f"Fetching market: {args.market}...")
    market = client.get_market_by_slug(args.market)
    
    if not market:
        print(f"Market not found: {args.market}")
        return
    
    print(f"\nQuestion: {market.question}")
    print(f"YES Price: {market.yes_price:.2%}")
    print(f"NO Price: {market.no_price:.2%}")
    print(f"Volume (24h): ${market.volume_24h:,.0f}")
    print(f"Liquidity: ${market.liquidity:,.0f}")
    
    # Get order book
    if market.yes_token_id:
        order_book = client.get_order_book(market.yes_token_id)
        if order_book:
            print(f"\nOrder Book:")
            print(f"  Best Bid: {order_book.best_bid:.2f}")
            print(f"  Best Ask: {order_book.best_ask:.2f}")
            print(f"  Spread: {order_book.spread:.2%}")
    
    # Get news
    print("\nSearching for related news...")
    market_news = news_agg.get_market_news(market.question)
    
    if market_news:
        print(f"\nFound {len(market_news)} related news items:")
        for news in market_news[:5]:
            print(f"  - {news.title[:60]}...")
            print(f"    Source: {news.source} | {news.published_at.strftime('%Y-%m-%d %H:%M')}")
        
        # Analyze sentiment
        news_texts = [f"{n.title} {n.content}" for n in market_news[:10]]
        sentiment = analyze_market_sentiment(market.question, news_texts)
        
        print(f"\nSentiment Analysis:")
        print(f"  Overall: {sentiment['overall_sentiment']:+.2f}")
        print(f"  Confidence: {sentiment['confidence']:.2f}")
        print(f"  Positive: {sentiment['positive_count']} | Negative: {sentiment['negative_count']} | Neutral: {sentiment['neutral_count']}")
    else:
        print("\nNo recent news found.")
    
    print("\n" + "=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Polymarket Trading Bot - Automated prediction market trading"
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Scan for opportunities')
    scan_parser.add_argument('--limit', type=int, default=50, help='Max markets to fetch')
    scan_parser.add_argument('--analyze', type=int, default=30, help='Max markets to analyze')
    scan_parser.add_argument('--min-volume', type=float, default=500, help='Minimum volume')
    scan_parser.add_argument('--min-edge', type=float, default=0.05, help='Minimum edge (0.05 = 5%)')
    
    # Paper trade command
    paper_parser = subparsers.add_parser('paper', help='Paper trading')
    paper_parser.add_argument('--capital', type=float, default=75.0, help='Starting capital')
    paper_parser.add_argument('--run', action='store_true', help='Run trading loop')
    paper_parser.add_argument('--status', action='store_true', help='Show account status')
    paper_parser.add_argument('--reset', action='store_true', help='Reset account')
    paper_parser.add_argument('--interval', type=int, default=15, help='Scan interval (minutes)')
    paper_parser.add_argument('--strategy', choices=['conservative', 'moderate', 'aggressive'], default=None,
                              help='Override strategy mode for this run')
    
    # Backtest command
    backtest_parser = subparsers.add_parser('backtest', help='Run backtest')
    backtest_parser.add_argument('--capital', type=float, default=75.0, help='Starting capital')
    backtest_parser.add_argument('--days', type=int, default=30, help='Days to backtest')
    backtest_parser.add_argument('--markets', type=int, default=20, help='Number of markets')
    backtest_parser.add_argument('--min-edge', type=float, default=0.08, help='Minimum edge')
    backtest_parser.add_argument('--show-trades', action='store_true', help='Show trade history')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze a market')
    analyze_parser.add_argument('market', help='Market slug')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    setup_environment()
    
    if args.command == 'scan':
        cmd_scan(args)
    elif args.command == 'paper':
        cmd_paper_trade(args)
    elif args.command == 'backtest':
        cmd_backtest(args)
    elif args.command == 'analyze':
        cmd_analyze(args)


if __name__ == '__main__':
    main()
