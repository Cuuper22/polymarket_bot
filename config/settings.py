"""
Configuration settings for Polymarket Trading Bot
Supports CONSERVATIVE, MODERATE, and AGGRESSIVE strategy modes
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, Literal
from pathlib import Path
from enum import Enum


class StrategyMode(str, Enum):
    """Trading strategy intensity levels."""
    CONSERVATIVE = "conservative"  # 3-5% weekly target, lower risk
    MODERATE = "moderate"          # 5-8% weekly target, balanced
    AGGRESSIVE = "aggressive"      # 10-15% weekly target, higher risk


class Settings(BaseSettings):
    """Main configuration settings."""
    
    # === Polymarket API ===
    POLYMARKET_HOST: str = "https://clob.polymarket.com"
    GAMMA_API_HOST: str = "https://gamma-api.polymarket.com"
    CHAIN_ID: int = 137  # Polygon
    
    # Wallet (NEVER commit real keys!)
    PRIVATE_KEY: Optional[str] = Field(default=None, description="Your wallet private key")
    FUNDER_ADDRESS: Optional[str] = Field(default=None, description="Funder address if using proxy wallet")
    SIGNATURE_TYPE: int = 0  # 0=EOA, 1=Magic/Email, 2=Browser proxy
    
    # === STRATEGY MODE ===
    # Set to "aggressive" for 10%+ weekly returns target
    STRATEGY_MODE: StrategyMode = StrategyMode.AGGRESSIVE
    
    # === Trading Parameters (Default: AGGRESSIVE MODE) ===
    STARTING_CAPITAL: float = 75.0  # Starting with $75 (middle of 50-100 range)
    MAX_POSITION_SIZE_PCT: float = 0.20  # Max 20% of capital per position (was 15%)
    MIN_POSITION_SIZE: float = 2.0  # Minimum $2 per trade (was $1)
    MAX_OPEN_POSITIONS: int = 6  # Allow 6 positions (was 5)
    
    # === Risk Management (AGGRESSIVE MODE) ===
    KELLY_FRACTION: float = 0.35  # 35% Kelly for aggressive growth (was 25%)
    MAX_DRAWDOWN_PCT: float = 0.30  # Stop trading if 30% drawdown
    MIN_EDGE_THRESHOLD: float = 0.12  # Minimum 12% edge to trade (was 5%)
    MIN_CONFIDENCE: float = 0.65  # Minimum 65% confidence (was 60%)
    
    # === AGGRESSIVE MODE: Additional Parameters ===
    # Entry criteria
    MIN_SIGNALS_REQUIRED: int = 2  # Require 2+ confirming signals
    MIN_PRICE: float = 0.15  # Avoid prices < 15 cents
    MAX_PRICE: float = 0.85  # Avoid prices > 85 cents
    MIN_VOLUME_24H: float = 1000.0  # Minimum $1K 24h volume
    MIN_LIQUIDITY: float = 500.0  # Minimum $500 liquidity
    MAX_SPREAD: float = 0.08  # Maximum 8% bid-ask spread
    
    # Exit parameters
    TAKE_PROFIT_PCT: float = 0.40  # Exit at 40% profit
    STOP_LOSS_PCT: float = 0.35  # Hard stop at 35% loss
    TRAILING_STOP_ACTIVATION: float = 0.25  # Activate trailing at 25% profit
    TRAILING_STOP_DISTANCE: float = 0.15  # Trail by 15% from peak
    TIME_STOP_HOURS: int = 120  # Exit if no movement in 5 days
    
    # Performance targets
    TARGET_WIN_RATE: float = 0.58  # Target 58% win rate
    TARGET_WEEKLY_RETURN: float = 0.10  # Target 10%+ weekly
    TARGET_TRADES_PER_WEEK: int = 12  # Target 12 trades per week
    MAX_CONSECUTIVE_LOSSES: int = 5  # Pause after 5 consecutive losses
    MAX_DAILY_LOSS_PCT: float = 0.12  # Maximum 12% daily loss
    
    # === Data Sources (Free) ===
    # Reddit
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None
    REDDIT_USER_AGENT: str = "PolymarketBot/1.0"
    
    # Google Trends (no API key needed)
    GOOGLE_TRENDS_ENABLED: bool = True
    
    # RSS Feeds (free, no API key)
    RSS_FEEDS: list = [
        "https://news.google.com/rss",
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.reuters.com/reuters/topNews",
    ]
    
    # === Timing (AGGRESSIVE: More frequent scans) ===
    SCAN_INTERVAL_MINUTES: int = 10  # Scan every 10 minutes (was 15)
    NEWS_REFRESH_MINUTES: int = 3  # Refresh news every 3 minutes (was 5)
    
    # === Paths ===
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOGS_DIR: Path = BASE_DIR / "logs"
    DB_PATH: Path = BASE_DIR / "data" / "polymarket_bot.db"
    
    # === Paper Trading ===
    PAPER_TRADING: bool = True  # Start with paper trading!
    
    # === Logging ===
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


# === STRATEGY PRESETS ===
# Quick reference for different strategy modes

STRATEGY_PRESETS = {
    StrategyMode.CONSERVATIVE: {
        'name': 'Conservative',
        'weekly_target': '3-5%',
        'kelly_fraction': 0.20,
        'max_position_pct': 0.12,
        'min_edge': 0.08,
        'min_confidence': 0.70,
        'max_positions': 4,
        'stop_loss_pct': 0.25,
        'take_profit_pct': 0.30,
    },
    StrategyMode.MODERATE: {
        'name': 'Moderate',
        'weekly_target': '5-8%',
        'kelly_fraction': 0.25,
        'max_position_pct': 0.15,
        'min_edge': 0.08,
        'min_confidence': 0.65,
        'max_positions': 5,
        'stop_loss_pct': 0.30,
        'take_profit_pct': 0.35,
    },
    StrategyMode.AGGRESSIVE: {
        'name': 'Aggressive Growth',
        'weekly_target': '10-15%',
        'kelly_fraction': 0.35,
        'max_position_pct': 0.20,
        'min_edge': 0.12,
        'min_confidence': 0.65,
        'max_positions': 6,
        'stop_loss_pct': 0.35,
        'take_profit_pct': 0.40,
    },
}


def get_strategy_settings(mode: Optional[StrategyMode] = None) -> dict:
    """Get settings for a specific strategy mode."""
    mode = mode or settings.STRATEGY_MODE
    preset = STRATEGY_PRESETS.get(mode, STRATEGY_PRESETS[StrategyMode.AGGRESSIVE])
    return {
        **preset,
        'starting_capital': settings.STARTING_CAPITAL,
        'paper_trading': settings.PAPER_TRADING,
    }


def print_current_strategy():
    """Print current strategy configuration."""
    mode = settings.STRATEGY_MODE
    preset = STRATEGY_PRESETS.get(mode, {})
    
    print(f"\n{'='*60}")
    print(f"CURRENT STRATEGY: {preset.get('name', 'Unknown').upper()}")
    print(f"{'='*60}")
    print(f"Weekly Target: {preset.get('weekly_target', 'N/A')}")
    print(f"Kelly Fraction: {settings.KELLY_FRACTION:.0%}")
    print(f"Max Position: {settings.MAX_POSITION_SIZE_PCT:.0%}")
    print(f"Min Edge: {settings.MIN_EDGE_THRESHOLD:.0%}")
    print(f"Min Confidence: {settings.MIN_CONFIDENCE:.0%}")
    print(f"Max Positions: {settings.MAX_OPEN_POSITIONS}")
    print(f"Stop Loss: {settings.STOP_LOSS_PCT:.0%}")
    print(f"Take Profit: {settings.TAKE_PROFIT_PCT:.0%}")
    print(f"Paper Trading: {settings.PAPER_TRADING}")
    print(f"Starting Capital: ${settings.STARTING_CAPITAL:.2f}")
    print(f"{'='*60}\n")
