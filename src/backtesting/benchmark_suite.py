"""
HFT Benchmark Suite - 50 Scenarios for Robust Strategy Testing
==============================================================
25 Normal market scenarios + 25 Edge cases/stress tests

This suite tests strategy robustness across diverse market conditions
to prevent overfitting and ensure real-world performance.
"""
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from enum import Enum
import math


class ScenarioType(Enum):
    """Categories of benchmark scenarios."""
    NORMAL = "normal"
    EDGE_CASE = "edge_case"
    STRESS_TEST = "stress_test"


class MarketCondition(Enum):
    """Market condition types."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    MEAN_REVERTING = "mean_reverting"
    NEWS_DRIVEN = "news_driven"
    LOW_LIQUIDITY = "low_liquidity"
    HIGH_LIQUIDITY = "high_liquidity"


@dataclass
class OrderBookSnapshot:
    """Realistic order book state."""
    bids: List[Tuple[float, float]]  # [(price, size), ...]
    asks: List[Tuple[float, float]]
    timestamp: datetime
    
    @property
    def best_bid(self) -> float:
        return self.bids[0][0] if self.bids else 0
    
    @property
    def best_ask(self) -> float:
        return self.asks[0][0] if self.asks else 1
    
    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid
    
    @property
    def mid_price(self) -> float:
        return (self.best_bid + self.best_ask) / 2
    
    @property
    def bid_depth(self) -> float:
        return sum(size for _, size in self.bids[:5])
    
    @property
    def ask_depth(self) -> float:
        return sum(size for _, size in self.asks[:5])
    
    def get_fill_price(self, side: str, size: float) -> Tuple[float, float, float]:
        """
        Calculate execution price with slippage.
        
        Returns: (avg_fill_price, filled_size, unfilled_size)
        """
        if side == "buy":
            levels = self.asks
        else:
            levels = self.bids
        
        if not levels:
            return (0, 0, size)
        
        remaining = size
        total_cost = 0
        filled = 0
        
        for price, available in levels:
            if remaining <= 0:
                break
            
            fill_at_level = min(remaining, available)
            total_cost += fill_at_level * price
            filled += fill_at_level
            remaining -= fill_at_level
        
        if filled == 0:
            return (levels[0][0], 0, size)
        
        avg_price = total_cost / filled
        return (avg_price, filled, remaining)


@dataclass
class BenchmarkScenario:
    """A single benchmark scenario for backtesting."""
    scenario_id: str
    name: str
    description: str
    scenario_type: ScenarioType
    market_condition: MarketCondition
    
    # Market parameters
    start_price: float
    end_price: float
    resolution: bool  # True = YES wins
    resolution_date: datetime
    
    # Price path
    price_history: List[Tuple[datetime, float]] = field(default_factory=list)
    
    # Order book history (for microstructure modeling)
    orderbook_history: List[OrderBookSnapshot] = field(default_factory=list)
    
    # Sentiment history
    sentiment_history: List[Tuple[datetime, float]] = field(default_factory=list)
    
    # Volume history
    volume_history: List[Tuple[datetime, float]] = field(default_factory=list)
    
    # News events
    news_events: List[Dict] = field(default_factory=list)
    
    # Expected strategy behavior
    expected_trades: int = 0  # Expected number of trades
    expected_win_rate: float = 0.5  # Expected win rate in this scenario
    expected_edge: float = 0.0  # Expected edge available
    difficulty: str = "medium"  # easy/medium/hard
    
    def to_dict(self) -> Dict:
        return {
            "id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "type": self.scenario_type.value,
            "condition": self.market_condition.value,
            "start_price": self.start_price,
            "end_price": self.end_price,
            "resolution": self.resolution,
            "price_points": len(self.price_history),
            "difficulty": self.difficulty,
        }


def generate_price_path(
    start_price: float,
    end_price: float,
    duration_hours: int,
    condition: MarketCondition,
    volatility: float = 0.02,
    start_time: Optional[datetime] = None
) -> List[Tuple[datetime, float]]:
    """Generate realistic price path based on market condition."""
    
    if start_time is None:
        start_time = datetime.now() - timedelta(hours=duration_hours)
    
    path = []
    current_price = start_price
    drift = (end_price - start_price) / duration_hours
    
    # Interval between price updates (1-4 hours depending on condition)
    if condition in [MarketCondition.VOLATILE, MarketCondition.NEWS_DRIVEN]:
        interval_hours = 1
    elif condition == MarketCondition.LOW_LIQUIDITY:
        interval_hours = 4
    else:
        interval_hours = 2
    
    for hour in range(0, duration_hours, interval_hours):
        timestamp = start_time + timedelta(hours=hour)
        
        if condition == MarketCondition.TRENDING_UP:
            noise = random.gauss(0, volatility * 0.5)
            current_price = min(0.98, current_price + abs(drift) + noise)
            
        elif condition == MarketCondition.TRENDING_DOWN:
            noise = random.gauss(0, volatility * 0.5)
            current_price = max(0.02, current_price - abs(drift) + noise)
            
        elif condition == MarketCondition.RANGING:
            # Oscillate around mid-point
            mid = (start_price + end_price) / 2
            cycle = math.sin(hour / duration_hours * math.pi * 4)
            noise = random.gauss(0, volatility * 0.3)
            current_price = mid + cycle * 0.1 + noise
            
        elif condition == MarketCondition.VOLATILE:
            # Large random moves
            noise = random.gauss(0, volatility * 2)
            current_price += noise
            
        elif condition == MarketCondition.MEAN_REVERTING:
            # Mean revert to fair value
            mean = (start_price + end_price) / 2
            reversion = (mean - current_price) * 0.1
            noise = random.gauss(0, volatility)
            current_price += reversion + noise
            
        elif condition == MarketCondition.NEWS_DRIVEN:
            # Jump on news, then drift
            if random.random() < 0.1:  # 10% chance of news
                jump = random.choice([-1, 1]) * random.uniform(0.05, 0.15)
                current_price += jump
            noise = random.gauss(0, volatility * 0.3)
            current_price += drift * 0.3 + noise
        
        else:
            noise = random.gauss(0, volatility)
            current_price += drift + noise
        
        current_price = max(0.02, min(0.98, current_price))
        path.append((timestamp, current_price))
    
    # Ensure we end at target price
    path.append((start_time + timedelta(hours=duration_hours), end_price))
    
    return path


def generate_orderbook(
    mid_price: float,
    spread_bps: int,
    depth_dollars: float,
    timestamp: datetime,
    imbalance: float = 0  # -1 to 1, negative = more bids
) -> OrderBookSnapshot:
    """Generate realistic order book snapshot."""
    
    spread = spread_bps / 10000
    half_spread = spread / 2
    
    bid_start = mid_price - half_spread
    ask_start = mid_price + half_spread
    
    # Adjust depth by imbalance
    bid_depth = depth_dollars * (1 - imbalance * 0.5)
    ask_depth = depth_dollars * (1 + imbalance * 0.5)
    
    # Generate 10 levels
    bids = []
    asks = []
    
    for i in range(10):
        # Price decreases for bids, increases for asks
        bid_price = bid_start - i * 0.005
        ask_price = ask_start + i * 0.005
        
        # Size decreases at deeper levels
        bid_size = (bid_depth / 10) * (1 - i * 0.08) * random.uniform(0.8, 1.2)
        ask_size = (ask_depth / 10) * (1 - i * 0.08) * random.uniform(0.8, 1.2)
        
        if bid_price > 0.01:
            bids.append((round(bid_price, 4), round(bid_size, 2)))
        if ask_price < 0.99:
            asks.append((round(ask_price, 4), round(ask_size, 2)))
    
    return OrderBookSnapshot(
        bids=bids,
        asks=asks,
        timestamp=timestamp
    )


def generate_sentiment_path(
    resolution: bool,
    duration_hours: int,
    accuracy: float = 0.6,  # How accurately sentiment predicts outcome
    start_time: Optional[datetime] = None
) -> List[Tuple[datetime, float]]:
    """Generate sentiment history that partially predicts outcome."""
    
    if start_time is None:
        start_time = datetime.now() - timedelta(hours=duration_hours)
    
    path = []
    
    # True sentiment based on outcome - stronger correlation for high accuracy
    true_sentiment = 0.50 if resolution else -0.50
    
    for hour in range(0, duration_hours, 6):
        timestamp = start_time + timedelta(hours=hour)
        
        # Sentiment trends towards truth as resolution approaches
        time_factor = hour / duration_hours
        
        # Accuracy increases over time (markets discover truth)
        current_accuracy = accuracy * (0.6 + 0.4 * time_factor)
        
        # Base sentiment with accuracy weighting
        base = true_sentiment * current_accuracy
        
        # Less noise for high accuracy scenarios
        noise_scale = 0.20 * (1 - accuracy * 0.5)
        noise = random.gauss(0, noise_scale)
        
        sentiment = max(-1, min(1, base + noise))
        path.append((timestamp, sentiment))
    
    return path


def generate_volume_path(
    duration_hours: int,
    base_volume: float,
    condition: MarketCondition,
    start_time: Optional[datetime] = None
) -> List[Tuple[datetime, float]]:
    """Generate volume history."""
    
    if start_time is None:
        start_time = datetime.now() - timedelta(hours=duration_hours)
    
    path = []
    
    for hour in range(0, duration_hours, 4):
        timestamp = start_time + timedelta(hours=hour)
        
        # Volume multiplier based on condition
        if condition == MarketCondition.VOLATILE:
            mult = random.uniform(1.5, 4.0)
        elif condition == MarketCondition.NEWS_DRIVEN:
            mult = random.uniform(1.0, 5.0) if random.random() < 0.2 else random.uniform(0.5, 1.5)
        elif condition == MarketCondition.LOW_LIQUIDITY:
            mult = random.uniform(0.1, 0.5)
        elif condition == MarketCondition.HIGH_LIQUIDITY:
            mult = random.uniform(1.5, 3.0)
        else:
            mult = random.uniform(0.5, 2.0)
        
        volume = base_volume * mult
        path.append((timestamp, volume))
    
    return path


# =============================================================================
# NORMAL SCENARIOS (25)
# =============================================================================

def create_normal_scenarios(base_time: datetime) -> List[BenchmarkScenario]:
    """Create 25 normal market scenarios."""
    scenarios = []
    
    # Duration is typically 7 days (168 hours)
    duration = 168
    
    # --- Scenario 1-5: Different price levels with trending up ---
    for i, start_p in enumerate([0.20, 0.35, 0.50, 0.65, 0.80]):
        end_p = min(0.95, start_p + 0.20)
        resolution = True
        
        scenario = BenchmarkScenario(
            scenario_id=f"NORM-{i+1:02d}",
            name=f"Trending Up from {start_p:.0%}",
            description=f"Steady uptrend from {start_p:.0%} to {end_p:.0%}, resolves YES",
            scenario_type=ScenarioType.NORMAL,
            market_condition=MarketCondition.TRENDING_UP,
            start_price=start_p,
            end_price=end_p,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=2,
            expected_win_rate=0.65,
            expected_edge=0.15,
            difficulty="easy"
        )
        
        scenario.price_history = generate_price_path(
            start_p, end_p, duration, MarketCondition.TRENDING_UP, 0.015, base_time
        )
        scenario.sentiment_history = generate_sentiment_path(resolution, duration, 0.65, base_time)
        scenario.volume_history = generate_volume_path(duration, 5000, MarketCondition.TRENDING_UP, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario 6-10: Different price levels with trending down ---
    for i, start_p in enumerate([0.80, 0.65, 0.50, 0.35, 0.20]):
        end_p = max(0.05, start_p - 0.20)
        resolution = False
        
        scenario = BenchmarkScenario(
            scenario_id=f"NORM-{i+6:02d}",
            name=f"Trending Down from {start_p:.0%}",
            description=f"Steady downtrend from {start_p:.0%} to {end_p:.0%}, resolves NO",
            scenario_type=ScenarioType.NORMAL,
            market_condition=MarketCondition.TRENDING_DOWN,
            start_price=start_p,
            end_price=end_p,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=2,
            expected_win_rate=0.65,
            expected_edge=0.15,
            difficulty="easy"
        )
        
        scenario.price_history = generate_price_path(
            start_p, end_p, duration, MarketCondition.TRENDING_DOWN, 0.015, base_time
        )
        scenario.sentiment_history = generate_sentiment_path(resolution, duration, 0.65, base_time)
        scenario.volume_history = generate_volume_path(duration, 5000, MarketCondition.TRENDING_DOWN, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario 11-15: Ranging markets (choppy) ---
    for i, (start_p, resolution) in enumerate([
        (0.45, True), (0.55, False), (0.50, True), (0.40, False), (0.60, True)
    ]):
        end_p = 0.85 if resolution else 0.15
        
        scenario = BenchmarkScenario(
            scenario_id=f"NORM-{i+11:02d}",
            name=f"Ranging Market at {start_p:.0%}",
            description=f"Sideways chop around {start_p:.0%}, eventually resolves {'YES' if resolution else 'NO'}",
            scenario_type=ScenarioType.NORMAL,
            market_condition=MarketCondition.RANGING,
            start_price=start_p,
            end_price=end_p,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=3,
            expected_win_rate=0.50,
            expected_edge=0.08,
            difficulty="medium"
        )
        
        scenario.price_history = generate_price_path(
            start_p, end_p, duration, MarketCondition.RANGING, 0.02, base_time
        )
        scenario.sentiment_history = generate_sentiment_path(resolution, duration, 0.50, base_time)
        scenario.volume_history = generate_volume_path(duration, 3000, MarketCondition.RANGING, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario 16-20: Mean reverting markets ---
    for i, (start_p, resolution) in enumerate([
        (0.30, True),   # Starts underpriced, reverts up
        (0.70, False),  # Starts overpriced, reverts down  
        (0.25, True),   # Extreme underpricing
        (0.75, False),  # Extreme overpricing
        (0.50, True),   # Fair value, drifts up
    ]):
        end_p = 0.90 if resolution else 0.10
        
        scenario = BenchmarkScenario(
            scenario_id=f"NORM-{i+16:02d}",
            name=f"Mean Reversion from {start_p:.0%}",
            description=f"Market reverts from {start_p:.0%} towards fair value",
            scenario_type=ScenarioType.NORMAL,
            market_condition=MarketCondition.MEAN_REVERTING,
            start_price=start_p,
            end_price=end_p,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=2,
            expected_win_rate=0.60,
            expected_edge=0.12,
            difficulty="medium"
        )
        
        scenario.price_history = generate_price_path(
            start_p, end_p, duration, MarketCondition.MEAN_REVERTING, 0.02, base_time
        )
        scenario.sentiment_history = generate_sentiment_path(resolution, duration, 0.60, base_time)
        scenario.volume_history = generate_volume_path(duration, 4000, MarketCondition.MEAN_REVERTING, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario 21-25: High liquidity, clear signals ---
    for i, (start_p, resolution) in enumerate([
        (0.40, True),
        (0.60, False),
        (0.35, True),
        (0.55, False),
        (0.45, True),
    ]):
        end_p = 0.92 if resolution else 0.08
        
        scenario = BenchmarkScenario(
            scenario_id=f"NORM-{i+21:02d}",
            name=f"High Liquidity Clear Signal {i+1}",
            description=f"High volume market with clear directional signal",
            scenario_type=ScenarioType.NORMAL,
            market_condition=MarketCondition.HIGH_LIQUIDITY,
            start_price=start_p,
            end_price=end_p,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=3,
            expected_win_rate=0.70,
            expected_edge=0.18,
            difficulty="easy"
        )
        
        condition = MarketCondition.TRENDING_UP if resolution else MarketCondition.TRENDING_DOWN
        scenario.price_history = generate_price_path(
            start_p, end_p, duration, condition, 0.01, base_time
        )
        scenario.sentiment_history = generate_sentiment_path(resolution, duration, 0.75, base_time)
        scenario.volume_history = generate_volume_path(duration, 10000, MarketCondition.HIGH_LIQUIDITY, base_time)
        
        scenarios.append(scenario)
    
    return scenarios


# =============================================================================
# EDGE CASE SCENARIOS (25)
# =============================================================================

def create_edge_case_scenarios(base_time: datetime) -> List[BenchmarkScenario]:
    """Create 25 edge case/stress test scenarios."""
    scenarios = []
    duration = 168
    
    # --- Scenario E1-E3: Flash crashes ---
    for i, (start_p, crash_to, recovery) in enumerate([
        (0.60, 0.25, True),   # Flash crash, recovers, wins
        (0.40, 0.70, False),  # Flash spike, crashes, loses
        (0.50, 0.15, True),   # Deep crash, full recovery
    ]):
        scenario = BenchmarkScenario(
            scenario_id=f"EDGE-{i+1:02d}",
            name=f"Flash {'Crash' if crash_to < start_p else 'Spike'} {i+1}",
            description=f"Sudden move from {start_p:.0%} to {crash_to:.0%}, then {'recovery' if recovery else 'continuation'}",
            scenario_type=ScenarioType.EDGE_CASE,
            market_condition=MarketCondition.VOLATILE,
            start_price=start_p,
            end_price=0.90 if recovery else 0.10,
            resolution=recovery,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=1,
            expected_win_rate=0.40,
            expected_edge=0.05,
            difficulty="hard"
        )
        
        # Custom price path with crash
        path = []
        crash_hour = random.randint(24, 72)
        for hour in range(0, duration, 2):
            timestamp = base_time + timedelta(hours=hour)
            
            if hour < crash_hour:
                price = start_p + random.gauss(0, 0.02)
            elif hour < crash_hour + 4:
                # Crash happens
                progress = (hour - crash_hour) / 4
                price = start_p + (crash_to - start_p) * progress
            elif hour < crash_hour + 24:
                # Consolidation
                price = crash_to + random.gauss(0, 0.03)
            else:
                # Drift to resolution
                end_p = 0.90 if recovery else 0.10
                progress = (hour - crash_hour - 24) / (duration - crash_hour - 24)
                price = crash_to + (end_p - crash_to) * progress + random.gauss(0, 0.02)
            
            path.append((timestamp, max(0.02, min(0.98, price))))
        
        scenario.price_history = path
        scenario.sentiment_history = generate_sentiment_path(recovery, duration, 0.40, base_time)
        scenario.volume_history = generate_volume_path(duration, 8000, MarketCondition.VOLATILE, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario E4-E6: Extreme spreads (low liquidity traps) ---
    for i, (start_p, spread_pct) in enumerate([
        (0.50, 0.15),  # 15% spread
        (0.30, 0.20),  # 20% spread on cheap contract
        (0.70, 0.12),  # 12% spread on expensive
    ]):
        resolution = random.choice([True, False])
        
        scenario = BenchmarkScenario(
            scenario_id=f"EDGE-{i+4:02d}",
            name=f"Wide Spread Trap {i+1} ({spread_pct:.0%})",
            description=f"Market with {spread_pct:.0%} bid-ask spread, low liquidity",
            scenario_type=ScenarioType.EDGE_CASE,
            market_condition=MarketCondition.LOW_LIQUIDITY,
            start_price=start_p,
            end_price=0.85 if resolution else 0.15,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=0,  # Should NOT trade due to spread
            expected_win_rate=0.50,
            expected_edge=-0.05,  # Negative edge after spread
            difficulty="hard"
        )
        
        scenario.price_history = generate_price_path(
            start_p, scenario.end_price, duration, MarketCondition.LOW_LIQUIDITY, 0.01, base_time
        )
        
        # Generate wide-spread order books
        for ts, price in scenario.price_history[::4]:
            ob = generate_orderbook(price, int(spread_pct * 10000), 200, ts, 0)
            scenario.orderbook_history.append(ob)
        
        scenario.sentiment_history = generate_sentiment_path(resolution, duration, 0.50, base_time)
        scenario.volume_history = generate_volume_path(duration, 500, MarketCondition.LOW_LIQUIDITY, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario E7-E9: News-driven volatility spikes ---
    for i, resolution in enumerate([True, False, True]):
        start_p = 0.50 + random.uniform(-0.1, 0.1)
        
        scenario = BenchmarkScenario(
            scenario_id=f"EDGE-{i+7:02d}",
            name=f"News Volatility Spike {i+1}",
            description="Multiple news events causing price swings",
            scenario_type=ScenarioType.EDGE_CASE,
            market_condition=MarketCondition.NEWS_DRIVEN,
            start_price=start_p,
            end_price=0.88 if resolution else 0.12,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=2,
            expected_win_rate=0.55,
            expected_edge=0.10,
            difficulty="medium"
        )
        
        scenario.price_history = generate_price_path(
            start_p, scenario.end_price, duration, MarketCondition.NEWS_DRIVEN, 0.03, base_time
        )
        
        # Add news events
        for _ in range(5):
            news_hour = random.randint(0, duration - 6)
            scenario.news_events.append({
                "timestamp": base_time + timedelta(hours=news_hour),
                "title": f"Breaking: Major development in market",
                "sentiment": random.uniform(-0.5, 0.5),
                "priority": random.choice(["high", "medium"]),
            })
        
        scenario.sentiment_history = generate_sentiment_path(resolution, duration, 0.55, base_time)
        scenario.volume_history = generate_volume_path(duration, 6000, MarketCondition.NEWS_DRIVEN, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario E10-E12: Whipsaw markets (false signals) ---
    for i, resolution in enumerate([True, False, True]):
        start_p = 0.50
        
        scenario = BenchmarkScenario(
            scenario_id=f"EDGE-{i+10:02d}",
            name=f"Whipsaw Market {i+1}",
            description="Multiple direction changes, false breakouts",
            scenario_type=ScenarioType.EDGE_CASE,
            market_condition=MarketCondition.VOLATILE,
            start_price=start_p,
            end_price=0.80 if resolution else 0.20,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=4,
            expected_win_rate=0.35,
            expected_edge=0.02,
            difficulty="hard"
        )
        
        # Custom whipsaw path
        path = []
        current = start_p
        for hour in range(0, duration, 2):
            timestamp = base_time + timedelta(hours=hour)
            
            # Reverse direction every 24-48 hours
            if hour % 36 == 0 and hour > 0:
                # Fake breakout
                direction = 1 if random.random() < 0.5 else -1
                current += direction * random.uniform(0.08, 0.15)
            elif hour % 36 == 12:
                # Reversal
                mean = 0.50
                current += (mean - current) * 0.3
            
            noise = random.gauss(0, 0.025)
            current = max(0.15, min(0.85, current + noise))
            
            # Drift towards end near resolution
            if hour > duration * 0.8:
                drift = (scenario.end_price - current) / ((duration - hour) / 2 + 1)
                current += drift
            
            path.append((timestamp, current))
        
        path.append((base_time + timedelta(hours=duration), scenario.end_price))
        scenario.price_history = path
        
        # Whipsaw sentiment (contradictory)
        sentiment_path = []
        for hour in range(0, duration, 6):
            timestamp = base_time + timedelta(hours=hour)
            # Oscillating sentiment
            sentiment = 0.3 * math.sin(hour / 24 * math.pi) + random.gauss(0, 0.2)
            sentiment_path.append((timestamp, max(-1, min(1, sentiment))))
        scenario.sentiment_history = sentiment_path
        
        scenario.volume_history = generate_volume_path(duration, 4000, MarketCondition.VOLATILE, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario E13-E15: Resolution day volatility ---
    for i, resolution in enumerate([True, False, True]):
        start_p = 0.55 if resolution else 0.45
        
        scenario = BenchmarkScenario(
            scenario_id=f"EDGE-{i+13:02d}",
            name=f"Resolution Day Chaos {i+1}",
            description="Extreme volatility in final 24 hours before resolution",
            scenario_type=ScenarioType.EDGE_CASE,
            market_condition=MarketCondition.VOLATILE,
            start_price=start_p,
            end_price=0.95 if resolution else 0.05,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=1,
            expected_win_rate=0.50,
            expected_edge=0.0,  # No edge in resolution chaos
            difficulty="hard"
        )
        
        # Normal path then crazy ending
        path = []
        for hour in range(0, duration, 2):
            timestamp = base_time + timedelta(hours=hour)
            
            if hour < duration - 24:
                # Normal drift
                progress = hour / (duration - 24)
                target = start_p + (0.60 if resolution else 0.40 - start_p) * progress
                price = target + random.gauss(0, 0.02)
            else:
                # Resolution chaos
                hours_left = duration - hour
                if hours_left > 12:
                    # Wild swings
                    swing = random.uniform(-0.15, 0.15)
                    price = path[-1][1] + swing
                else:
                    # Convergence to resolution
                    target = 0.95 if resolution else 0.05
                    price = path[-1][1] + (target - path[-1][1]) * (12 - hours_left) / 12
            
            path.append((timestamp, max(0.02, min(0.98, price))))
        
        scenario.price_history = path
        scenario.sentiment_history = generate_sentiment_path(resolution, duration, 0.70, base_time)
        scenario.volume_history = generate_volume_path(duration, 15000, MarketCondition.VOLATILE, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario E16-E18: Sentiment divergence traps ---
    for i, (sentiment_dir, resolution) in enumerate([
        (1, False),   # Positive sentiment but resolves NO
        (-1, True),   # Negative sentiment but resolves YES
        (1, False),   # Another false positive
    ]):
        start_p = 0.50
        
        scenario = BenchmarkScenario(
            scenario_id=f"EDGE-{i+16:02d}",
            name=f"Sentiment Trap {i+1}",
            description=f"{'Positive' if sentiment_dir > 0 else 'Negative'} sentiment, resolves {'YES' if resolution else 'NO'}",
            scenario_type=ScenarioType.EDGE_CASE,
            market_condition=MarketCondition.MEAN_REVERTING,
            start_price=start_p,
            end_price=0.85 if resolution else 0.15,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=1,
            expected_win_rate=0.30,
            expected_edge=-0.05,
            difficulty="hard"
        )
        
        scenario.price_history = generate_price_path(
            start_p, scenario.end_price, duration, MarketCondition.MEAN_REVERTING, 0.02, base_time
        )
        
        # Misleading sentiment
        sentiment_path = []
        base_sentiment = 0.4 * sentiment_dir
        for hour in range(0, duration, 6):
            timestamp = base_time + timedelta(hours=hour)
            sentiment = base_sentiment + random.gauss(0, 0.15)
            sentiment_path.append((timestamp, max(-1, min(1, sentiment))))
        scenario.sentiment_history = sentiment_path
        
        scenario.volume_history = generate_volume_path(duration, 3000, MarketCondition.MEAN_REVERTING, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario E19-E21: Stop hunting patterns ---
    for i, resolution in enumerate([True, False, True]):
        start_p = 0.50
        
        scenario = BenchmarkScenario(
            scenario_id=f"EDGE-{i+19:02d}",
            name=f"Stop Hunt Pattern {i+1}",
            description="Price spikes to trigger stops then reverses",
            scenario_type=ScenarioType.STRESS_TEST,
            market_condition=MarketCondition.VOLATILE,
            start_price=start_p,
            end_price=0.82 if resolution else 0.18,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=2,
            expected_win_rate=0.40,
            expected_edge=0.05,
            difficulty="hard"
        )
        
        # Path with stop hunts
        path = []
        current = start_p
        stop_hunt_hours = [48, 96]
        
        for hour in range(0, duration, 2):
            timestamp = base_time + timedelta(hours=hour)
            
            is_stop_hunt = any(abs(hour - sh) < 4 for sh in stop_hunt_hours)
            
            if is_stop_hunt:
                # Sharp move against trend
                spike = -0.12 if resolution else 0.12
                if any(hour == sh for sh in stop_hunt_hours):
                    current += spike
                elif any(hour == sh + 2 for sh in stop_hunt_hours):
                    current -= spike * 1.2  # Reversal overshoots
            else:
                # Normal drift
                drift = 0.001 if resolution else -0.001
                current += drift + random.gauss(0, 0.015)
            
            path.append((timestamp, max(0.10, min(0.90, current))))
        
        scenario.price_history = path
        scenario.sentiment_history = generate_sentiment_path(resolution, duration, 0.55, base_time)
        scenario.volume_history = generate_volume_path(duration, 5000, MarketCondition.VOLATILE, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario E22-E23: Correlated market movements ---
    for i, resolution in enumerate([True, False]):
        scenario = BenchmarkScenario(
            scenario_id=f"EDGE-{i+22:02d}",
            name=f"Correlated Move {i+1}",
            description="Market moves with broader crypto/market sentiment",
            scenario_type=ScenarioType.EDGE_CASE,
            market_condition=MarketCondition.TRENDING_UP if resolution else MarketCondition.TRENDING_DOWN,
            start_price=0.45,
            end_price=0.78 if resolution else 0.22,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=2,
            expected_win_rate=0.55,
            expected_edge=0.10,
            difficulty="medium"
        )
        
        condition = MarketCondition.TRENDING_UP if resolution else MarketCondition.TRENDING_DOWN
        scenario.price_history = generate_price_path(
            0.45, scenario.end_price, duration, condition, 0.02, base_time
        )
        scenario.sentiment_history = generate_sentiment_path(resolution, duration, 0.60, base_time)
        scenario.volume_history = generate_volume_path(duration, 7000, condition, base_time)
        
        scenarios.append(scenario)
    
    # --- Scenario E24-E25: Partial fill scenarios (large orders) ---
    for i, resolution in enumerate([True, False]):
        scenario = BenchmarkScenario(
            scenario_id=f"EDGE-{i+24:02d}",
            name=f"Thin Book Large Order {i+1}",
            description="Attempt large order in thin order book",
            scenario_type=ScenarioType.STRESS_TEST,
            market_condition=MarketCondition.LOW_LIQUIDITY,
            start_price=0.50,
            end_price=0.80 if resolution else 0.20,
            resolution=resolution,
            resolution_date=base_time + timedelta(hours=duration),
            expected_trades=1,
            expected_win_rate=0.45,
            expected_edge=0.03,
            difficulty="hard"
        )
        
        scenario.price_history = generate_price_path(
            0.50, scenario.end_price, duration, MarketCondition.LOW_LIQUIDITY, 0.015, base_time
        )
        
        # Thin order books
        for ts, price in scenario.price_history[::4]:
            ob = generate_orderbook(price, 400, 100, ts, random.uniform(-0.3, 0.3))  # Only $100 per level
            scenario.orderbook_history.append(ob)
        
        scenario.sentiment_history = generate_sentiment_path(resolution, duration, 0.50, base_time)
        scenario.volume_history = generate_volume_path(duration, 300, MarketCondition.LOW_LIQUIDITY, base_time)
        
        scenarios.append(scenario)
    
    return scenarios


# =============================================================================
# BENCHMARK SUITE
# =============================================================================

class BenchmarkSuite:
    """Complete benchmark suite with 50 scenarios."""
    
    def __init__(self, base_time: Optional[datetime] = None):
        if base_time is None:
            base_time = datetime.now() - timedelta(days=7)
        
        self.base_time = base_time
        self.normal_scenarios = create_normal_scenarios(base_time)
        self.edge_case_scenarios = create_edge_case_scenarios(base_time)
        self.all_scenarios = self.normal_scenarios + self.edge_case_scenarios
    
    @property
    def scenario_count(self) -> int:
        return len(self.all_scenarios)
    
    def get_scenario(self, scenario_id: str) -> Optional[BenchmarkScenario]:
        for s in self.all_scenarios:
            if s.scenario_id == scenario_id:
                return s
        return None
    
    def get_scenarios_by_type(self, scenario_type: ScenarioType) -> List[BenchmarkScenario]:
        return [s for s in self.all_scenarios if s.scenario_type == scenario_type]
    
    def get_scenarios_by_difficulty(self, difficulty: str) -> List[BenchmarkScenario]:
        return [s for s in self.all_scenarios if s.difficulty == difficulty]
    
    def get_scenarios_by_condition(self, condition: MarketCondition) -> List[BenchmarkScenario]:
        return [s for s in self.all_scenarios if s.market_condition == condition]
    
    def get_summary(self) -> Dict:
        """Get suite summary statistics."""
        return {
            "total_scenarios": self.scenario_count,
            "normal_scenarios": len(self.normal_scenarios),
            "edge_case_scenarios": len(self.edge_case_scenarios),
            "by_difficulty": {
                "easy": len(self.get_scenarios_by_difficulty("easy")),
                "medium": len(self.get_scenarios_by_difficulty("medium")),
                "hard": len(self.get_scenarios_by_difficulty("hard")),
            },
            "by_resolution": {
                "yes_wins": len([s for s in self.all_scenarios if s.resolution]),
                "no_wins": len([s for s in self.all_scenarios if not s.resolution]),
            },
            "by_condition": {
                c.value: len(self.get_scenarios_by_condition(c))
                for c in MarketCondition
            }
        }
    
    def print_summary(self):
        """Print suite summary."""
        summary = self.get_summary()
        
        print("\n" + "=" * 60)
        print("HFT BENCHMARK SUITE - 50 SCENARIOS")
        print("=" * 60)
        print(f"Total Scenarios: {summary['total_scenarios']}")
        print(f"  Normal: {summary['normal_scenarios']}")
        print(f"  Edge Cases: {summary['edge_case_scenarios']}")
        print("-" * 60)
        print("By Difficulty:")
        for diff, count in summary["by_difficulty"].items():
            print(f"  {diff.capitalize()}: {count}")
        print("-" * 60)
        print("By Resolution:")
        print(f"  YES wins: {summary['by_resolution']['yes_wins']}")
        print(f"  NO wins: {summary['by_resolution']['no_wins']}")
        print("-" * 60)
        print("By Market Condition:")
        for cond, count in summary["by_condition"].items():
            if count > 0:
                print(f"  {cond}: {count}")
        print("=" * 60)


def create_benchmark_suite(seed: Optional[int] = None) -> BenchmarkSuite:
    """Create benchmark suite with optional seed for reproducibility."""
    if seed is not None:
        random.seed(seed)
    return BenchmarkSuite()


if __name__ == "__main__":
    # Create and display benchmark suite
    suite = create_benchmark_suite(seed=42)
    suite.print_summary()
    
    print("\n[SAMPLE SCENARIOS]")
    for s in suite.all_scenarios[:5]:
        print(f"\n{s.scenario_id}: {s.name}")
        print(f"  Type: {s.scenario_type.value}, Condition: {s.market_condition.value}")
        print(f"  Price: {s.start_price:.0%} -> {s.end_price:.0%}")
        print(f"  Resolution: {'YES' if s.resolution else 'NO'}")
        print(f"  Difficulty: {s.difficulty}")
        print(f"  Expected: {s.expected_trades} trades, {s.expected_win_rate:.0%} WR, {s.expected_edge:.0%} edge")
