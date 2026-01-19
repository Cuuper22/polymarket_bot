# Polymarket Bot: 24/7 Trading Workflow Architecture (Full)

## Executive Summary

This document outlines a comprehensive 24/7 automated trading workflow architecture for the Polymarket trading bot. The system is designed for resilience, self-healing, and continuous operation with minimal human intervention.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Main Trading Loop Architecture](#2-main-trading-loop-architecture)
3. [Error Recovery Framework](#3-error-recovery-framework)
4. [Risk Management Workflow](#4-risk-management-workflow)
5. [Monitoring & Alerting System](#5-monitoring--alerting-system)
6. [Self-Healing Mechanisms](#6-self-healing-mechanisms)
7. [State Machine Specifications](#7-state-machine-specifications)
8. [Decision Trees](#8-decision-trees)
9. [Implementation Roadmap](#9-implementation-roadmap)

## Status

This is a full reference architecture document. Some subsystems are planned but not implemented in the current codebase.

---

## 1. System Overview

### High-Level Architecture Diagram

```mermaid
flowchart TB
    subgraph External["External Systems"]
        PM[("Polymarket API")]
        NEWS[("News Sources")]
        ALERTS[("Alert Channels")]
    end
    
    subgraph Core["Core Trading Engine"]
        ORCH["Orchestrator<br/>24/7 Scheduler"]
        
        subgraph DataLayer["Data Layer"]
            DC["Data Collector"]
            NC["News Aggregator"]
            SA["Sentiment Analyzer"]
        end
        
        subgraph TradingLayer["Trading Layer"]
            ED["Edge Detector"]
            PS["Position Sizer"]
            EX["Trade Executor"]
        end
        
        subgraph RiskLayer["Risk Layer"]
            RM["Risk Manager"]
            PC["Position Controller"]
            DD["Drawdown Monitor"]
        end
    end
    
    subgraph Resilience["Resilience Layer"]
        HB["Heartbeat Monitor"]
        ER["Error Recovery"]
        SH["Self-Healer"]
        CB["Circuit Breaker"]
    end
    
    subgraph Monitoring["Monitoring Layer"]
        MM["Metrics Manager"]
        AM["Alert Manager"]
        LOG["Log Aggregator"]
        DASH["Dashboard"]
    end
    
    subgraph State["State Management"]
        DB[("SQLite DB")]
        CACHE[("Redis Cache")]
        CKPT[("Checkpoints")]
    end
    
    PM <--> DC
    NEWS --> NC
    ORCH --> DataLayer
    ORCH --> TradingLayer
    ORCH --> RiskLayer
    
    DataLayer --> TradingLayer
    TradingLayer <--> RiskLayer
    EX <--> PM
    
    Resilience --> Core
    Core --> Monitoring
    Monitoring --> ALERTS
    
    Core <--> State
    Resilience --> State
```

### Component Responsibilities

| Component | Responsibility | Criticality |
|-----------|---------------|-------------|
| Orchestrator | Main loop timing, task scheduling | Critical |
| Data Collector | Market data fetching, caching | High |
| Edge Detector | Opportunity identification | High |
| Risk Manager | Portfolio protection | Critical |
| Self-Healer | Automatic recovery | Critical |
| Circuit Breaker | Failure isolation | Critical |

---

## 2. Main Trading Loop Architecture

### 2.1 Primary Trading Cycle

```mermaid
flowchart TD
    START((Start Cycle)) --> CHECK_HEALTH{System<br/>Healthy?}
    
    CHECK_HEALTH -->|No| RECOVERY[Enter Recovery Mode]
    RECOVERY --> WAIT_RECOVERY[Wait for Recovery]
    WAIT_RECOVERY --> CHECK_HEALTH
    
    CHECK_HEALTH -->|Yes| CHECK_RISK{Risk<br/>Limits OK?}
    
    CHECK_RISK -->|No| RISK_PAUSE[Risk Pause Mode]
    RISK_PAUSE --> LOG_RISK[Log Risk Event]
    LOG_RISK --> WAIT_COOLDOWN[Cooldown: 5min]
    WAIT_COOLDOWN --> CHECK_HEALTH
    
    CHECK_RISK -->|Yes| FETCH_DATA[Fetch Market Data]
    
    FETCH_DATA --> VALIDATE_DATA{Data<br/>Valid?}
    VALIDATE_DATA -->|No| RETRY_DATA[Retry with Backoff]
    RETRY_DATA --> FETCH_DATA
    
    VALIDATE_DATA -->|Yes| UPDATE_POSITIONS[Update Position Prices]
    
    UPDATE_POSITIONS --> CHECK_EXITS{Exit<br/>Conditions?}
    CHECK_EXITS -->|Yes| EXECUTE_EXITS[Execute Exits]
    CHECK_EXITS -->|No| SCAN_OPPS[Scan Opportunities]
    EXECUTE_EXITS --> SCAN_OPPS
    
    SCAN_OPPS --> FILTER_OPPS{Quality<br/>Opportunities?}
    FILTER_OPPS -->|No| SAVE_STATE[Save State]
    
    FILTER_OPPS -->|Yes| RANK_OPPS[Rank by Score]
    RANK_OPPS --> SIZE_POSITIONS[Calculate Sizes]
    SIZE_POSITIONS --> RISK_CHECK{Passes<br/>Risk Check?}
    
    RISK_CHECK -->|No| SAVE_STATE
    RISK_CHECK -->|Yes| EXECUTE_TRADES[Execute Trades]
    
    EXECUTE_TRADES --> CONFIRM{Trades<br/>Confirmed?}
    CONFIRM -->|No| HANDLE_FAILURE[Handle Failure]
    HANDLE_FAILURE --> SAVE_STATE
    
    CONFIRM -->|Yes| UPDATE_STATE[Update Portfolio State]
    UPDATE_STATE --> SAVE_STATE
    
    SAVE_STATE --> EMIT_METRICS[Emit Metrics]
    EMIT_METRICS --> CALC_SLEEP[Calculate Sleep Time]
    CALC_SLEEP --> SLEEP[Adaptive Sleep]
    SLEEP --> START
```

### 2.2 Timing Configuration

```mermaid
gantt
    title Trading Cycle Timing (15-minute base interval)
    dateFormat X
    axisFormat %S
    
    section Data Collection
    Fetch Markets       :0, 10
    Fetch News          :10, 20
    Analyze Sentiment   :20, 40
    
    section Analysis
    Update Positions    :40, 50
    Check Exits         :50, 60
    Scan Opportunities  :60, 90
    
    section Execution
    Risk Validation     :90, 100
    Execute Trades      :100, 120
    Confirm Orders      :120, 140
    
    section State
    Save Checkpoint     :140, 150
    Emit Metrics        :150, 160
    
    section Sleep
    Adaptive Sleep      :160, 900
```

### 2.3 Adaptive Timing Logic

```python
# Timing Configuration
TIMING_CONFIG = {
    "base_interval_seconds": 900,        # 15 minutes normal
    "fast_interval_seconds": 300,        # 5 minutes when active
    "urgent_interval_seconds": 60,       # 1 minute on breaking news
    "slow_interval_seconds": 1800,       # 30 minutes low activity
    
    "max_execution_time_seconds": 120,   # Max time for cycle
    "health_check_interval": 60,         # Health check every minute
    "heartbeat_interval": 30,            # Heartbeat every 30s
    
    "market_hours": {
        "active": {"start": 8, "end": 22},    # UTC
        "reduced": {"start": 22, "end": 8},
    },
    
    "volatility_multipliers": {
        "low": 2.0,      # Double interval
        "normal": 1.0,   # Standard
        "high": 0.5,     # Half interval
        "extreme": 0.25, # Quarter interval
    }
}
```

---

## 3. Error Recovery Framework

### 3.1 Error Classification Hierarchy

```mermaid
flowchart TB
    ERROR[Error Detected] --> CLASSIFY{Classify Error}
    
    CLASSIFY -->|Transient| TRANS[Transient Error]
    CLASSIFY -->|Recoverable| RECOV[Recoverable Error]
    CLASSIFY -->|Critical| CRIT[Critical Error]
    CLASSIFY -->|Fatal| FATAL[Fatal Error]
    
    subgraph Transient["Transient (Auto-Retry)"]
        TRANS --> T1[Network Timeout]
        TRANS --> T2[Rate Limit Hit]
        TRANS --> T3[Temporary API Error]
        T1 & T2 & T3 --> RETRY[Exponential Backoff<br/>Max 3 retries]
    end
    
    subgraph Recoverable["Recoverable (Circuit Break)"]
        RECOV --> R1[API Endpoint Down]
        RECOV --> R2[Data Source Failure]
        RECOV --> R3[Execution Failure]
        R1 & R2 & R3 --> CIRCUIT[Open Circuit<br/>Fallback Mode]
    end
    
    subgraph Critical["Critical (Alert + Pause)"]
        CRIT --> C1[Risk Limit Breach]
        CRIT --> C2[Position Sync Failure]
        CRIT --> C3[Database Corruption]
        C1 & C2 & C3 --> PAUSE[Pause Trading<br/>Alert Human]
    end
    
    subgraph Fatal["Fatal (Shutdown)"]
        FATAL --> F1[Authentication Failure]
        FATAL --> F2[Wallet Compromise]
        FATAL --> F3[Unrecoverable State]
        F1 & F2 & F3 --> SHUTDOWN[Safe Shutdown<br/>Emergency Alert]
    end
```

### 3.2 Circuit Breaker State Machine

```mermaid
stateDiagram-v2
    [*] --> Closed
    
    Closed --> Open : Failure threshold exceeded
    Closed --> Closed : Success / Failure below threshold
    
    Open --> HalfOpen : Timeout expires
    Open --> Open : Requests blocked
    
    HalfOpen --> Closed : Probe succeeds
    HalfOpen --> Open : Probe fails
    
    state Closed {
        [*] --> Monitoring
        Monitoring --> CountingFailures : Failure
        CountingFailures --> Monitoring : Success resets count
        CountingFailures --> [*] : Threshold reached
    }
    
    state Open {
        [*] --> Blocking
        Blocking --> Timing : Block requests
        Timing --> [*] : Timeout (30-300s)
    }
    
    state HalfOpen {
        [*] --> Probing
        Probing --> SingleRequest : Allow 1 request
        SingleRequest --> [*] : Result determines next state
    }
```

### 3.3 Recovery Workflow

```mermaid
flowchart TD
    subgraph Detection["Error Detection"]
        ERR[Error Occurs] --> LOG[Log Error Details]
        LOG --> INC[Increment Error Counter]
        INC --> CHECK_THRESH{Threshold<br/>Exceeded?}
    end
    
    subgraph Classification["Error Classification"]
        CHECK_THRESH -->|No| RETRY_SIMPLE[Simple Retry]
        CHECK_THRESH -->|Yes| ANALYZE[Analyze Pattern]
        
        ANALYZE --> IS_TRANS{Transient<br/>Pattern?}
        IS_TRANS -->|Yes| BACKOFF[Exponential Backoff]
        IS_TRANS -->|No| IS_RECOV{Recoverable?}
        
        IS_RECOV -->|Yes| CIRCUIT_BREAK[Open Circuit]
        IS_RECOV -->|No| IS_CRIT{Critical?}
        
        IS_CRIT -->|Yes| PAUSE_TRADE[Pause Trading]
        IS_CRIT -->|No| FATAL_ERR[Fatal - Shutdown]
    end
    
    subgraph Recovery["Recovery Actions"]
        BACKOFF --> WAIT1[Wait: 2^n seconds]
        WAIT1 --> RETRY1[Retry Operation]
        RETRY1 --> SUCCESS1{Success?}
        SUCCESS1 -->|Yes| RESET[Reset Counters]
        SUCCESS1 -->|No| CHECK_MAX{Max<br/>Retries?}
        CHECK_MAX -->|No| WAIT1
        CHECK_MAX -->|Yes| CIRCUIT_BREAK
        
        CIRCUIT_BREAK --> FALLBACK[Use Fallback]
        FALLBACK --> WAIT_CIRCUIT[Wait Circuit Timeout]
        WAIT_CIRCUIT --> HALF_OPEN[Half-Open State]
        HALF_OPEN --> PROBE[Probe Request]
        PROBE --> SUCCESS2{Success?}
        SUCCESS2 -->|Yes| CLOSE_CIRCUIT[Close Circuit]
        SUCCESS2 -->|No| CIRCUIT_BREAK
        
        PAUSE_TRADE --> ALERT[Alert Operator]
        ALERT --> SAFE_STATE[Enter Safe State]
        SAFE_STATE --> WAIT_HUMAN[Wait for Human]
        
        FATAL_ERR --> EMERGENCY[Emergency Protocol]
        EMERGENCY --> CLOSE_POS[Close All Positions]
        CLOSE_POS --> SAVE_ALL[Save All State]
        SAVE_ALL --> SHUTDOWN[Controlled Shutdown]
    end
    
    RESET --> NORMAL[Resume Normal]
    CLOSE_CIRCUIT --> NORMAL
```

### 3.4 Error Recovery Configuration

```python
ERROR_RECOVERY_CONFIG = {
    "transient_errors": {
        "max_retries": 3,
        "base_delay_seconds": 1,
        "max_delay_seconds": 60,
        "backoff_multiplier": 2,
        "jitter_range": 0.1,
    },
    
    "circuit_breaker": {
        "failure_threshold": 5,
        "success_threshold": 3,
        "timeout_seconds": 60,
        "max_timeout_seconds": 300,
        "half_open_max_requests": 1,
    },
    
    "critical_errors": {
        "pause_duration_seconds": 300,
        "alert_channels": ["telegram", "email", "sms"],
        "max_auto_recovery_attempts": 3,
        "require_human_ack": True,
    },
    
    "fatal_errors": {
        "emergency_close_positions": True,
        "save_full_state": True,
        "alert_priority": "critical",
        "restart_policy": "manual_only",
    }
}
```

---

## 4. Risk Management Workflow

### 4.1 Multi-Layer Risk Architecture

```mermaid
flowchart TB
    subgraph PreTrade["Pre-Trade Risk (Layer 1)"]
        direction LR
        PT1[Position Size Check]
        PT2[Capital Availability]
        PT3[Max Positions Check]
        PT4[Correlation Check]
        PT1 --> PT2 --> PT3 --> PT4
    end
    
    subgraph LiveRisk["Live Risk Monitoring (Layer 2)"]
        direction LR
        LR1[Price Monitoring]
        LR2[P&L Tracking]
        LR3[Drawdown Calc]
        LR4[Volatility Watch]
        LR1 --> LR2 --> LR3 --> LR4
    end
    
    subgraph Limits["Risk Limits (Layer 3)"]
        direction LR
        L1[Daily Loss Limit]
        L2[Max Drawdown]
        L3[Position Concentration]
        L4[Volatility Limits]
        L1 --> L2 --> L3 --> L4
    end
    
    subgraph Actions["Risk Actions (Layer 4)"]
        direction LR
        A1[Reduce Position]
        A2[Hedge]
        A3[Pause Trading]
        A4[Emergency Exit]
        A1 --> A2 --> A3 --> A4
    end
    
    TRADE[Trade Request] --> PreTrade
    PreTrade -->|Pass| LiveRisk
    PreTrade -->|Fail| REJECT[Reject Trade]
    
    LiveRisk --> Limits
    Limits -->|Breach| Actions
    Limits -->|OK| CONTINUE[Continue Trading]
    
    Actions --> NOTIFY[Notify & Log]
```

### 4.2 Risk Decision Tree

```mermaid
flowchart TD
    START[Risk Check Request] --> PHASE1{Pre-Trade<br/>Checks}
    
    %% Pre-Trade Phase
    PHASE1 --> CAP{Capital<br/>Available?}
    CAP -->|No| REJECT1[REJECT: Insufficient Capital]
    CAP -->|Yes| SIZE{Position<br/>Size OK?}
    
    SIZE -->|Over Max| ADJUST1[Adjust to Max Size]
    SIZE -->|OK| POS_COUNT{Position<br/>Limit?}
    
    POS_COUNT -->|Exceeded| REJECT2[REJECT: Max Positions]
    POS_COUNT -->|OK| CORR{Correlation<br/>Check?}
    
    CORR -->|High Correlation| REJECT3[REJECT: Correlation Risk]
    CORR -->|OK| EDGE{Edge<br/>Sufficient?}
    
    EDGE -->|Below Threshold| REJECT4[REJECT: Low Edge]
    EDGE -->|OK| PHASE2{Live Risk<br/>Checks}
    
    %% Live Risk Phase
    PHASE2 --> DD{Current<br/>Drawdown?}
    DD -->|Over 20%| REDUCE[Reduce Position 50%]
    DD -->|Over 25%| PAUSE[Pause New Trades]
    DD -->|Over 30%| EXIT[Emergency Exit All]
    DD -->|OK| DAILY{Daily<br/>Loss?}
    
    DAILY -->|Over 8%| STOP[Stop Trading Today]
    DAILY -->|Over 5%| CAUTIOUS[Cautious Mode]
    DAILY -->|OK| VOL{Volatility<br/>Level?}
    
    VOL -->|Extreme| REDUCE_SIZE[Reduce All Sizes 50%]
    VOL -->|High| TIGHTER[Tighter Stops]
    VOL -->|Normal| APPROVE[APPROVE Trade]
    
    %% Results
    ADJUST1 --> POS_COUNT
    REDUCE --> APPROVE
    REDUCE_SIZE --> APPROVE
    TIGHTER --> APPROVE
    CAUTIOUS --> APPROVE
```

### 4.3 Portfolio Risk State Machine

```mermaid
stateDiagram-v2
    [*] --> Normal
    
    Normal --> Cautious : Daily PnL < -5%
    Normal --> ReducedRisk : Drawdown > 15%
    Normal --> Normal : All metrics OK
    
    Cautious --> Normal : Daily PnL recovers
    Cautious --> ReducedRisk : Drawdown > 15%
    Cautious --> TradingPaused : Daily PnL < -8%
    
    ReducedRisk --> Normal : Drawdown < 10%
    ReducedRisk --> TradingPaused : Drawdown > 25%
    ReducedRisk --> Cautious : Drawdown < 15%
    
    TradingPaused --> Cautious : After cooldown + manual review
    TradingPaused --> EmergencyExit : Drawdown > 30%
    
    EmergencyExit --> SystemHalt : All positions closed
    SystemHalt --> [*] : Requires manual restart
    
    state Normal {
        [*] --> FullTrading
        FullTrading : Max position size: 15%
        FullTrading : Max positions: 5
        FullTrading : All strategies active
    }
    
    state Cautious {
        [*] --> LimitedTrading
        LimitedTrading : Max position size: 10%
        LimitedTrading : Max positions: 3
        LimitedTrading : High-confidence only
    }
    
    state ReducedRisk {
        [*] --> MinimalTrading
        MinimalTrading : Max position size: 5%
        MinimalTrading : Max positions: 2
        MinimalTrading : Exit signals prioritized
    }
    
    state TradingPaused {
        [*] --> NoNewTrades
        NoNewTrades : Only manage exits
        NoNewTrades : Monitor existing positions
        NoNewTrades : Cooldown: 4 hours minimum
    }
    
    state EmergencyExit {
        [*] --> ClosingAll
        ClosingAll : Close all positions
        ClosingAll : Market orders if needed
        ClosingAll : Alert all channels
    }
```

### 4.4 Risk Parameters

```python
RISK_MANAGEMENT_CONFIG = {
    "position_limits": {
        "max_position_pct": 0.15,          # 15% max single position
        "max_positions": 5,                 # Maximum concurrent
        "min_position_size": 1.0,           # Minimum $1
        "max_correlated_exposure": 0.30,    # 30% in correlated markets
    },
    
    "loss_limits": {
        "max_daily_loss_pct": 0.08,         # 8% daily loss
        "max_weekly_loss_pct": 0.15,        # 15% weekly loss
        "max_drawdown_pct": 0.30,           # 30% max drawdown
        "drawdown_reduce_threshold": 0.15,  # Start reducing at 15%
        "drawdown_pause_threshold": 0.25,   # Pause at 25%
    },
    
    "edge_requirements": {
        "min_edge_normal": 0.05,            # 5% minimum edge
        "min_edge_cautious": 0.08,          # 8% in cautious mode
        "min_edge_reduced": 0.12,           # 12% in reduced mode
        "min_confidence": 0.60,             # 60% minimum confidence
    },
    
    "volatility_adjustments": {
        "low_vol_multiplier": 1.2,          # Increase sizes
        "high_vol_multiplier": 0.7,         # Reduce sizes
        "extreme_vol_multiplier": 0.4,      # Significantly reduce
        "extreme_vol_threshold": 3.0,       # 3x normal volatility
    },
    
    "kelly_parameters": {
        "kelly_fraction": 0.25,             # Quarter Kelly
        "max_kelly_fraction": 0.50,         # Never exceed half Kelly
        "confidence_weighting": True,       # Weight by confidence
    }
}
```

---

## 5. Monitoring & Alerting System

### 5.1 Monitoring Architecture

```mermaid
flowchart TB
    subgraph Collectors["Metric Collectors"]
        direction LR
        C1[Trading Metrics]
        C2[System Metrics]
        C3[Risk Metrics]
        C4[API Metrics]
    end
    
    subgraph Processing["Processing Layer"]
        AGG[Aggregator]
        CALC[Calculator]
        TREND[Trend Analyzer]
        ANOM[Anomaly Detector]
    end
    
    subgraph Storage["Storage Layer"]
        TSDB[Time Series DB]
        EVENTS[Event Log]
        ALERTS_DB[Alert History]
    end
    
    subgraph Alerting["Alert System"]
        RULES[Alert Rules Engine]
        THRESH[Threshold Monitor]
        ESCALATE[Escalation Manager]
    end
    
    subgraph Channels["Alert Channels"]
        TG[Telegram Bot]
        EMAIL[Email]
        SMS[SMS Critical]
        WEBHOOK[Webhooks]
    end
    
    subgraph Display["Dashboards"]
        LIVE[Live Dashboard]
        HIST[Historical Analysis]
        PERF[Performance Reports]
    end
    
    Collectors --> AGG
    AGG --> CALC & TREND & ANOM
    CALC & TREND & ANOM --> TSDB
    CALC & TREND & ANOM --> EVENTS
    
    TSDB --> RULES
    EVENTS --> RULES
    ANOM --> RULES
    
    RULES --> THRESH
    THRESH --> ESCALATE
    ESCALATE --> Channels
    
    TSDB --> Display
    EVENTS --> Display
    ALERTS_DB --> Display
```

### 5.2 Alert Severity Levels

```mermaid
flowchart LR
    subgraph Severity["Alert Severity Classification"]
        direction TB
        
        INFO[INFO<br/>Informational] --> |Examples| INFO_EX[Trade executed<br/>Position opened<br/>Cycle completed]
        
        WARNING[WARNING<br/>Attention Needed] --> |Examples| WARN_EX[Retry occurred<br/>Slow response<br/>Unusual pattern]
        
        ERROR[ERROR<br/>Action Required] --> |Examples| ERR_EX[Trade failed<br/>API error<br/>Risk limit near]
        
        CRITICAL[CRITICAL<br/>Immediate Action] --> |Examples| CRIT_EX[Drawdown breach<br/>System failure<br/>Data corruption]
        
        EMERGENCY[EMERGENCY<br/>All Hands] --> |Examples| EMRG_EX[Security breach<br/>Wallet issue<br/>Complete failure]
    end
    
    subgraph Routing["Channel Routing"]
        direction TB
        INFO --> LOG_ONLY[Log Only]
        WARNING --> LOG_TG[Log + Telegram]
        ERROR --> LOG_TG_EMAIL[Log + Telegram + Email]
        CRITICAL --> ALL_MINUS_SMS[All Channels]
        EMERGENCY --> ALL_PLUS_SMS[All + SMS + Phone Call]
    end
```

### 5.3 Key Metrics Dashboard

```mermaid
flowchart TB
    subgraph Trading["Trading Metrics"]
        T1[Total PnL: $X.XX]
        T2[Win Rate: XX%]
        T3[Open Positions: X]
        T4[Avg Trade: $X.XX]
        T5[Sharpe Ratio: X.XX]
    end
    
    subgraph Risk["Risk Metrics"]
        R1[Current Drawdown: XX%]
        R2[Daily PnL: $X.XX]
        R3[Capital Utilization: XX%]
        R4[Max Drawdown: XX%]
        R5[Risk Score: X/10]
    end
    
    subgraph System["System Health"]
        S1[Uptime: XX.X%]
        S2[API Latency: XXXms]
        S3[Error Rate: X.XX%]
        S4[Last Cycle: Xs ago]
        S5[Memory Usage: XX%]
    end
    
    subgraph Market["Market Data"]
        M1[Markets Tracked: XXX]
        M2[Opportunities/hr: XX]
        M3[Avg Edge: X.X%]
        M4[News Items: XXX]
        M5[Data Freshness: Xs]
    end
```

### 5.4 Alert Rules Configuration

```python
ALERT_RULES = {
    "trading_alerts": {
        "trade_executed": {
            "severity": "INFO",
            "channels": ["log", "telegram"],
            "template": "Trade: {direction} ${amount} @ {price} on {market}",
        },
        "trade_failed": {
            "severity": "ERROR",
            "channels": ["log", "telegram", "email"],
            "template": "TRADE FAILED: {error} for {market}",
            "throttle_minutes": 5,
        },
        "position_closed": {
            "severity": "INFO",
            "channels": ["log", "telegram"],
            "template": "Closed: {direction} PnL ${pnl} ({pnl_pct}%)",
        },
    },
    
    "risk_alerts": {
        "drawdown_warning": {
            "condition": "drawdown > 15%",
            "severity": "WARNING",
            "channels": ["log", "telegram", "email"],
            "template": "Drawdown at {drawdown}% - monitoring",
        },
        "drawdown_critical": {
            "condition": "drawdown > 25%",
            "severity": "CRITICAL",
            "channels": ["all"],
            "template": "CRITICAL: Drawdown {drawdown}% - trading paused",
        },
        "daily_loss_limit": {
            "condition": "daily_loss > 8%",
            "severity": "CRITICAL",
            "channels": ["all"],
            "template": "Daily loss limit hit: {loss}%",
        },
    },
    
    "system_alerts": {
        "heartbeat_missed": {
            "condition": "no_heartbeat > 60s",
            "severity": "ERROR",
            "channels": ["log", "telegram", "email"],
            "template": "Heartbeat missed for {duration}s",
        },
        "api_failure": {
            "condition": "api_errors > 5 in 5min",
            "severity": "ERROR",
            "channels": ["log", "telegram", "email"],
            "template": "API failures: {count} in last 5 minutes",
        },
        "system_down": {
            "condition": "no_response > 300s",
            "severity": "EMERGENCY",
            "channels": ["all", "sms"],
            "template": "EMERGENCY: System unresponsive for {duration}s",
        },
    },
    
    "performance_alerts": {
        "exceptional_win": {
            "condition": "trade_pnl > 30%",
            "severity": "INFO",
            "channels": ["log", "telegram"],
            "template": "Big win! +{pnl}% on {market}",
        },
        "losing_streak": {
            "condition": "consecutive_losses > 5",
            "severity": "WARNING",
            "channels": ["log", "telegram"],
            "template": "Losing streak: {count} consecutive losses",
        },
    }
}
```

---

## 6. Self-Healing Mechanisms

### 6.1 Self-Healing Architecture

```mermaid
flowchart TB
    subgraph Detection["Anomaly Detection"]
        D1[Health Checks]
        D2[Performance Monitors]
        D3[State Validators]
        D4[Consistency Checks]
    end
    
    subgraph Analysis["Root Cause Analysis"]
        A1[Pattern Matcher]
        A2[Historical Comparator]
        A3[Dependency Analyzer]
        A4[Impact Assessor]
    end
    
    subgraph Healing["Healing Actions"]
        H1[Auto-Restart Services]
        H2[Clear Caches]
        H3[Reconnect APIs]
        H4[Rollback State]
        H5[Rebalance Load]
    end
    
    subgraph Verification["Verification"]
        V1[Health Recheck]
        V2[State Validation]
        V3[Performance Test]
        V4[Integration Test]
    end
    
    Detection --> Analysis
    Analysis --> DECIDE{Healing<br/>Possible?}
    
    DECIDE -->|Yes| Healing
    DECIDE -->|No| ESCALATE[Escalate to Human]
    
    Healing --> Verification
    Verification --> SUCCESS{Healed?}
    
    SUCCESS -->|Yes| RESUME[Resume Operations]
    SUCCESS -->|No| RETRY{Retry<br/>Count OK?}
    
    RETRY -->|Yes| Analysis
    RETRY -->|No| ESCALATE
```

### 6.2 Healing Procedures State Machine

```mermaid
stateDiagram-v2
    [*] --> Healthy
    
    Healthy --> Detecting : Anomaly signal
    Healthy --> Healthy : Regular checks pass
    
    Detecting --> Analyzing : Anomaly confirmed
    Detecting --> Healthy : False positive
    
    Analyzing --> Healing : Cause identified
    Analyzing --> Escalating : Unknown cause
    
    Healing --> Verifying : Action completed
    Healing --> Escalating : Action failed
    
    Verifying --> Healthy : Verification passed
    Verifying --> Healing : Verification failed, retry
    Verifying --> Escalating : Max retries exceeded
    
    Escalating --> ManualIntervention : Alert sent
    ManualIntervention --> Healthy : Human resolves
    
    state Healthy {
        [*] --> Monitoring
        Monitoring --> HealthCheck : Every 30s
        HealthCheck --> Monitoring : Pass
    }
    
    state Detecting {
        [*] --> CollectingEvidence
        CollectingEvidence --> ConfirmingAnomaly
        ConfirmingAnomaly --> [*]
    }
    
    state Healing {
        [*] --> SelectingAction
        SelectingAction --> ExecutingAction
        ExecutingAction --> [*]
    }
    
    state Verifying {
        [*] --> RunningChecks
        RunningChecks --> ValidatingState
        ValidatingState --> [*]
    }
```

### 6.3 Healing Actions Matrix

```mermaid
flowchart LR
    subgraph Issues["Detected Issues"]
        I1[API Connection Lost]
        I2[Stale Data]
        I3[Memory Leak]
        I4[State Inconsistency]
        I5[Rate Limit Hit]
        I6[Position Sync Error]
    end
    
    subgraph Actions["Healing Actions"]
        A1[Reconnect with Backoff]
        A2[Force Refresh + Cache Clear]
        A3[Restart Worker Process]
        A4[Reload from Checkpoint]
        A5[Pause + Gradual Resume]
        A6[Sync from Exchange]
    end
    
    subgraph Verify["Verification Steps"]
        V1[Test API Call]
        V2[Compare Timestamps]
        V3[Monitor Memory]
        V4[Validate Checksums]
        V5[Check Rate Headers]
        V6[Reconcile Positions]
    end
    
    I1 --> A1 --> V1
    I2 --> A2 --> V2
    I3 --> A3 --> V3
    I4 --> A4 --> V4
    I5 --> A5 --> V5
    I6 --> A6 --> V6
```

### 6.4 Self-Healing Configuration

```python
SELF_HEALING_CONFIG = {
    "health_checks": {
        "interval_seconds": 30,
        "timeout_seconds": 10,
        "consecutive_failures_threshold": 3,
        
        "checks": [
            {
                "name": "api_connectivity",
                "endpoint": "polymarket_client.get_active_markets",
                "expected": "non_empty_list",
                "healing_action": "reconnect_api",
            },
            {
                "name": "data_freshness",
                "check": "last_data_update < 5_minutes",
                "healing_action": "force_refresh",
            },
            {
                "name": "position_sync",
                "check": "local_positions == remote_positions",
                "healing_action": "sync_positions",
            },
            {
                "name": "memory_usage",
                "threshold": "memory_pct < 80",
                "healing_action": "restart_worker",
            },
            {
                "name": "state_consistency",
                "check": "validate_state_checksums",
                "healing_action": "rollback_checkpoint",
            },
        ],
    },
    
    "healing_actions": {
        "reconnect_api": {
            "max_attempts": 5,
            "backoff_base": 2,
            "max_backoff": 300,
            "cooldown_after_success": 60,
        },
        "force_refresh": {
            "clear_cache": True,
            "reset_rate_limits": True,
            "max_attempts": 3,
        },
        "sync_positions": {
            "source_of_truth": "exchange",
            "reconcile_discrepancies": True,
            "alert_on_mismatch": True,
        },
        "restart_worker": {
            "graceful_shutdown": True,
            "save_state_first": True,
            "restart_delay": 5,
        },
        "rollback_checkpoint": {
            "max_rollback_age_hours": 24,
            "verify_after_rollback": True,
            "alert_on_rollback": True,
        },
    },
    
    "escalation": {
        "max_healing_attempts": 3,
        "escalation_channels": ["telegram", "email"],
        "require_human_ack": True,
        "auto_resume_after_hours": 4,
    }
}
```

---

## 7. State Machine Specifications

### 7.1 Main Bot State Machine

```mermaid
stateDiagram-v2
    [*] --> Initializing
    
    Initializing --> Running : Init complete
    Initializing --> Failed : Init error
    
    Running --> Paused : Pause command / Risk trigger
    Running --> Recovering : Error detected
    Running --> Stopping : Stop command
    Running --> Running : Normal cycle
    
    Paused --> Running : Resume command
    Paused --> Stopping : Stop command
    Paused --> Recovering : Error detected
    
    Recovering --> Running : Recovery success
    Recovering --> Paused : Recovery partial
    Recovering --> Failed : Recovery failed
    
    Stopping --> Stopped : Graceful stop
    Stopping --> Failed : Stop error
    
    Stopped --> Initializing : Restart command
    Stopped --> [*] : Shutdown
    
    Failed --> Initializing : Manual restart
    Failed --> [*] : Shutdown
    
    state Running {
        [*] --> Idle
        Idle --> Scanning : Cycle start
        Scanning --> Analyzing : Data collected
        Analyzing --> Trading : Opportunities found
        Analyzing --> Idle : No opportunities
        Trading --> Executing : Trade approved
        Trading --> Idle : Trade rejected
        Executing --> Confirming : Order placed
        Confirming --> Idle : Order confirmed
        Confirming --> Retrying : Order failed
        Retrying --> Executing : Retry
        Retrying --> Idle : Max retries
    }
    
    state Recovering {
        [*] --> Diagnosing
        Diagnosing --> Healing : Issue identified
        Diagnosing --> Escalating : Unknown issue
        Healing --> Verifying : Action taken
        Verifying --> [*] : Success
        Verifying --> Healing : Retry needed
        Escalating --> [*] : Human notified
    }
```

### 7.2 Trading Cycle State Machine

```mermaid
stateDiagram-v2
    [*] --> CycleStart
    
    CycleStart --> HealthCheck
    
    HealthCheck --> DataCollection : Health OK
    HealthCheck --> WaitAndRetry : Health Issue
    
    WaitAndRetry --> HealthCheck : After delay
    WaitAndRetry --> Abort : Max retries
    
    DataCollection --> DataValidation : Data fetched
    DataCollection --> RetryDataFetch : Fetch failed
    
    RetryDataFetch --> DataCollection : Retry
    RetryDataFetch --> SkipCycle : Max retries
    
    DataValidation --> PositionUpdate : Data valid
    DataValidation --> SkipCycle : Invalid data
    
    PositionUpdate --> ExitCheck
    
    ExitCheck --> ExecuteExits : Exit needed
    ExitCheck --> OpportunityScanning : No exits
    
    ExecuteExits --> OpportunityScanning : Exits done
    
    OpportunityScanning --> OpportunityRanking : Found opportunities
    OpportunityScanning --> SaveState : No opportunities
    
    OpportunityRanking --> RiskValidation : Ranked
    
    RiskValidation --> PositionSizing : Risk OK
    RiskValidation --> SaveState : Risk blocked
    
    PositionSizing --> TradeExecution : Sized
    PositionSizing --> SaveState : Size too small
    
    TradeExecution --> TradeConfirmation : Executed
    TradeExecution --> TradeRetry : Execution failed
    
    TradeRetry --> TradeExecution : Retry
    TradeRetry --> LogFailure : Max retries
    
    TradeConfirmation --> UpdatePortfolio : Confirmed
    TradeConfirmation --> ReconcileState : Confirmation failed
    
    UpdatePortfolio --> SaveState
    ReconcileState --> SaveState
    LogFailure --> SaveState
    
    SaveState --> EmitMetrics
    
    EmitMetrics --> CalculateSleep
    
    CalculateSleep --> Sleep
    
    Sleep --> CycleStart : Wake up
    
    SkipCycle --> SaveState
    Abort --> [*]
```

### 7.3 Position Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Identified
    
    Identified --> Evaluating : Opportunity found
    
    Evaluating --> Approved : Passes all checks
    Evaluating --> Rejected : Fails checks
    
    Rejected --> [*] : Logged
    
    Approved --> Sizing : Risk approved
    
    Sizing --> Executing : Size calculated
    Sizing --> Rejected : Size too small
    
    Executing --> Pending : Order submitted
    
    Pending --> Open : Order filled
    Pending --> PartialFill : Partial fill
    Pending --> Cancelled : Order cancelled
    Pending --> Failed : Order failed
    
    PartialFill --> Open : Complete fill
    PartialFill --> AdjustSize : Timeout
    
    AdjustSize --> Open : Accept partial
    
    Cancelled --> [*] : Logged
    Failed --> [*] : Logged
    
    Open --> Monitoring : Position active
    
    Monitoring --> Monitoring : Price update
    Monitoring --> ExitTriggered : Exit condition
    
    ExitTriggered --> Closing : Initiate close
    
    Closing --> Closed : Close confirmed
    Closing --> ForceClose : Close failed
    
    ForceClose --> Closed : Market order
    
    Closed --> Reconciled : PnL calculated
    
    Reconciled --> [*] : Position archived
    
    state Monitoring {
        [*] --> Healthy
        Healthy --> StopLoss : Price < stop
        Healthy --> TakeProfit : Price > target
        Healthy --> TimeExit : Expiry near
        Healthy --> SignalExit : Exit signal
        Healthy --> Healthy : Normal
    }
```

---

## 8. Decision Trees

### 8.1 Trade Entry Decision Tree

```
TRADE ENTRY DECISION TREE
=========================

1. OPPORTUNITY DETECTED
   |
   +--[NO]--> END (No Trade)
   |
   +--[YES]
        |
        2. EDGE >= MIN_EDGE?
           |
           +--[NO]--> END (Insufficient Edge)
           |
           +--[YES]
                |
                3. CONFIDENCE >= MIN_CONFIDENCE?
                   |
                   +--[NO]--> END (Low Confidence)
                   |
                   +--[YES]
                        |
                        4. CAPITAL AVAILABLE?
                           |
                           +--[NO]--> END (No Capital)
                           |
                           +--[YES]
                                |
                                5. POSITION COUNT < MAX?
                                   |
                                   +--[NO]--> END (Position Limit)
                                   |
                                   +--[YES]
                                        |
                                        6. DRAWDOWN < THRESHOLD?
                                           |
                                           +--[NO]
                                           |    |
                                           |    +--[DD < 25%]--> REDUCED_SIZE
                                           |    |
                                           |    +--[DD >= 25%]--> END (Risk Pause)
                                           |
                                           +--[YES]
                                                |
                                                7. CORRELATION CHECK PASS?
                                                   |
                                                   +--[NO]--> END (Correlation Risk)
                                                   |
                                                   +--[YES]
                                                        |
                                                        8. CALCULATE KELLY SIZE
                                                           |
                                                           +--[SIZE < MIN]--> END (Too Small)
                                                           |
                                                           +--[SIZE >= MIN]
                                                                |
                                                                9. VOLATILITY ADJUSTMENT
                                                                   |
                                                                   +--[EXTREME]--> SIZE *= 0.4
                                                                   +--[HIGH]----> SIZE *= 0.7
                                                                   +--[NORMAL]--> SIZE *= 1.0
                                                                   +--[LOW]-----> SIZE *= 1.2
                                                                        |
                                                                        10. EXECUTE TRADE
                                                                            |
                                                                            --> SUCCESS / RETRY / FAIL
```

### 8.2 Trade Exit Decision Tree

```
TRADE EXIT DECISION TREE
========================

1. POSITION ACTIVE
   |
   +-- CHECK EVERY CYCLE
        |
        2. MARKET RESOLVED?
           |
           +--[YES]--> CLOSE (Resolution)
           |
           +--[NO]
                |
                3. STOP LOSS HIT? (Current PnL <= -50%)
                   |
                   +--[YES]--> CLOSE (Stop Loss)
                   |
                   +--[NO]
                        |
                        4. TAKE PROFIT HIT? (Current PnL >= +50%)
                           |
                           +--[YES]--> CLOSE (Take Profit)
                           |
                           +--[NO]
                                |
                                5. TRAILING STOP TRIGGERED?
                                   |
                                   +--[YES]--> CLOSE (Trailing Stop)
                                   |
                                   +--[NO]
                                        |
                                        6. TIME-BASED EXIT? (Age > Max Hold)
                                           |
                                           +--[YES]--> CLOSE (Time Exit)
                                           |
                                           +--[NO]
                                                |
                                                7. SIGNAL REVERSED? (New signal opposite)
                                                   |
                                                   +--[YES]
                                                   |    |
                                                   |    +--[STRONG REVERSAL]--> CLOSE
                                                   |    |
                                                   |    +--[WEAK REVERSAL]--> REDUCE 50%
                                                   |
                                                   +--[NO]
                                                        |
                                                        8. EDGE DETERIORATED? (Edge < 2%)
                                                           |
                                                           +--[YES]--> CLOSE (Edge Gone)
                                                           |
                                                           +--[NO]
                                                                |
                                                                9. EMERGENCY EXIT? (System/Risk)
                                                                   |
                                                                   +--[YES]--> CLOSE (Emergency)
                                                                   |
                                                                   +--[NO]
                                                                        |
                                                                        --> HOLD POSITION
```

### 8.3 Error Response Decision Tree

```
ERROR RESPONSE DECISION TREE
============================

1. ERROR DETECTED
   |
   +-- CLASSIFY ERROR TYPE
        |
        2. NETWORK/TRANSIENT ERROR?
           |
           +--[YES]
           |    |
           |    3. RETRY COUNT < MAX?
           |       |
           |       +--[YES]--> WAIT (2^n seconds) --> RETRY
           |       |
           |       +--[NO]--> CIRCUIT_BREAK
           |
           +--[NO]
                |
                4. API/SERVICE ERROR?
                   |
                   +--[YES]
                   |    |
                   |    5. CIRCUIT ALREADY OPEN?
                   |       |
                   |       +--[YES]--> USE_FALLBACK
                   |       |
                   |       +--[NO]--> OPEN_CIRCUIT --> USE_FALLBACK
                   |
                   +--[NO]
                        |
                        6. DATA VALIDATION ERROR?
                           |
                           +--[YES]
                           |    |
                           |    7. CRITICAL DATA?
                           |       |
                           |       +--[YES]--> SKIP_CYCLE + ALERT
                           |       |
                           |       +--[NO]--> USE_CACHED + LOG
                           |
                           +--[NO]
                                |
                                8. EXECUTION ERROR?
                                   |
                                   +--[YES]
                                   |    |
                                   |    9. ORDER SUBMITTED?
                                   |       |
                                   |       +--[YES]--> VERIFY_STATE + RECONCILE
                                   |       |
                                   |       +--[NO]--> LOG + CONTINUE
                                   |
                                   +--[NO]
                                        |
                                        10. RISK/LIMIT BREACH?
                                            |
                                            +--[YES]
                                            |    |
                                            |    11. CRITICAL BREACH?
                                            |        |
                                            |        +--[YES]--> EMERGENCY_EXIT + HALT
                                            |        |
                                            |        +--[NO]--> PAUSE_TRADING + ALERT
                                            |
                                            +--[NO]
                                                 |
                                                 12. UNKNOWN ERROR
                                                     |
                                                     --> LOG_FULL_CONTEXT
                                                     --> ALERT_OPERATOR
                                                     --> SAFE_STATE
```

### 8.4 Self-Healing Decision Tree

```
SELF-HEALING DECISION TREE
==========================

1. HEALTH CHECK TRIGGERED
   |
   +-- RUN ALL HEALTH CHECKS
        |
        2. ALL CHECKS PASS?
           |
           +--[YES]--> CONTINUE (Healthy)
           |
           +--[NO]
                |
                3. IDENTIFY FAILING CHECK
                   |
                   +--[API_CONNECTIVITY]
                   |    |
                   |    --> ACTION: Reconnect with backoff
                   |    --> VERIFY: Test API call
                   |
                   +--[DATA_FRESHNESS]
                   |    |
                   |    --> ACTION: Force refresh + clear cache
                   |    --> VERIFY: Check data timestamps
                   |
                   +--[POSITION_SYNC]
                   |    |
                   |    --> ACTION: Sync from exchange
                   |    --> VERIFY: Reconcile positions
                   |
                   +--[MEMORY_USAGE]
                   |    |
                   |    --> ACTION: Restart worker process
                   |    --> VERIFY: Monitor memory after restart
                   |
                   +--[STATE_CONSISTENCY]
                        |
                        --> ACTION: Rollback to checkpoint
                        --> VERIFY: Validate checksums
                        |
                        4. HEALING ACTION TAKEN
                           |
                           5. VERIFICATION PASS?
                              |
                              +--[YES]--> RESUME_NORMAL
                              |
                              +--[NO]
                                   |
                                   6. RETRY COUNT < MAX?
                                      |
                                      +--[YES]--> RETRY_HEALING
                                      |
                                      +--[NO]
                                           |
                                           7. ESCALATE TO HUMAN
                                              |
                                              --> SEND_ALERTS
                                              --> ENTER_SAFE_MODE
                                              --> WAIT_INTERVENTION
```

---

## 9. Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1-2)

```mermaid
gantt
    title Phase 1: Core Infrastructure
    dateFormat YYYY-MM-DD
    
    section State Management
    SQLite Schema Design       :a1, 2026-01-20, 2d
    Checkpoint System          :a2, after a1, 2d
    State Recovery Logic       :a3, after a2, 2d
    
    section Main Loop
    Orchestrator Framework     :b1, 2026-01-20, 3d
    Timing Configuration       :b2, after b1, 2d
    Cycle Management          :b3, after b2, 2d
    
    section Basic Monitoring
    Logging Enhancement        :c1, 2026-01-27, 2d
    Basic Metrics Collection   :c2, after c1, 2d
    Health Check Framework     :c3, after c2, 2d
```

### Phase 2: Resilience Layer (Week 3-4)

```mermaid
gantt
    title Phase 2: Resilience Layer
    dateFormat YYYY-MM-DD
    
    section Error Handling
    Error Classification       :a1, 2026-02-03, 2d
    Retry Logic               :a2, after a1, 2d
    Circuit Breaker           :a3, after a2, 3d
    
    section Recovery
    Recovery Procedures        :b1, 2026-02-03, 3d
    Fallback Mechanisms       :b2, after b1, 2d
    State Reconciliation      :b3, after b2, 2d
    
    section Testing
    Error Injection Tests      :c1, 2026-02-10, 3d
    Recovery Tests            :c2, after c1, 2d
    Integration Tests         :c3, after c2, 2d
```

### Phase 3: Risk Management (Week 5-6)

```mermaid
gantt
    title Phase 3: Risk Management
    dateFormat YYYY-MM-DD
    
    section Risk Engine
    Risk State Machine         :a1, 2026-02-17, 3d
    Multi-Layer Checks        :a2, after a1, 3d
    Dynamic Adjustments       :a3, after a2, 2d
    
    section Position Control
    Position Limits           :b1, 2026-02-17, 2d
    Correlation Tracking      :b2, after b1, 3d
    Exit Automation           :b3, after b2, 2d
    
    section Emergency Protocols
    Emergency Exit Logic       :c1, 2026-02-24, 2d
    Safe State Entry          :c2, after c1, 2d
    Recovery Procedures       :c3, after c2, 2d
```

### Phase 4: Monitoring & Alerting (Week 7-8)

```mermaid
gantt
    title Phase 4: Monitoring & Alerting
    dateFormat YYYY-MM-DD
    
    section Metrics
    Metrics Framework          :a1, 2026-03-02, 3d
    Custom Metrics            :a2, after a1, 2d
    Aggregation Logic         :a3, after a2, 2d
    
    section Alerting
    Alert Rules Engine         :b1, 2026-03-02, 3d
    Telegram Integration      :b2, after b1, 2d
    Email Alerts              :b3, after b2, 2d
    
    section Dashboard
    Real-time Dashboard        :c1, 2026-03-09, 3d
    Historical Views          :c2, after c1, 2d
    Mobile Notifications      :c3, after c2, 2d
```

### Phase 5: Self-Healing (Week 9-10)

```mermaid
gantt
    title Phase 5: Self-Healing
    dateFormat YYYY-MM-DD
    
    section Detection
    Anomaly Detection          :a1, 2026-03-16, 3d
    Pattern Recognition       :a2, after a1, 2d
    Root Cause Analysis       :a3, after a2, 2d
    
    section Healing
    Healing Actions           :b1, 2026-03-16, 3d
    Verification Logic        :b2, after b1, 3d
    Escalation Paths          :b3, after b2, 2d
    
    section Integration
    Full System Integration    :c1, 2026-03-23, 3d
    Load Testing              :c2, after c1, 2d
    Production Deployment     :c3, after c2, 2d
```

---

## Appendix A: Configuration Templates

### Complete Bot Configuration

```python
BOT_CONFIG = {
    # Core Settings
    "bot_name": "PolymarketBot",
    "version": "2.0.0",
    "environment": "production",
    
    # Timing
    "timing": TIMING_CONFIG,
    
    # Risk Management
    "risk": RISK_MANAGEMENT_CONFIG,
    
    # Error Recovery
    "error_recovery": ERROR_RECOVERY_CONFIG,
    
    # Alerting
    "alerts": ALERT_RULES,
    
    # Self-Healing
    "self_healing": SELF_HEALING_CONFIG,
    
    # State Management
    "state": {
        "database_path": "./data/polymarket_bot.db",
        "checkpoint_interval_seconds": 300,
        "max_checkpoints": 24,
        "state_encryption": True,
    },
    
    # API Configuration
    "apis": {
        "polymarket": {
            "gamma_host": "https://gamma-api.polymarket.com",
            "clob_host": "https://clob.polymarket.com",
            "rate_limit_per_minute": 60,
            "timeout_seconds": 30,
        },
        "news_sources": [
            "https://news.google.com/rss",
            "https://feeds.bbci.co.uk/news/rss.xml",
        ],
    },
}
```

---

## Appendix B: Mermaid Diagram Index

| Diagram | Section | Purpose |
|---------|---------|---------|
| System Overview | 1 | High-level architecture |
| Primary Trading Cycle | 2.1 | Main loop flow |
| Timing Gantt | 2.2 | Cycle timing breakdown |
| Error Classification | 3.1 | Error type hierarchy |
| Circuit Breaker States | 3.2 | Circuit breaker FSM |
| Recovery Workflow | 3.3 | Error recovery flow |
| Risk Architecture | 4.1 | Multi-layer risk system |
| Risk Decision Tree | 4.2 | Risk check flow |
| Portfolio Risk States | 4.3 | Risk state machine |
| Monitoring Architecture | 5.1 | Monitoring system |
| Alert Severity | 5.2 | Alert classification |
| Dashboard Metrics | 5.3 | Key metrics layout |
| Self-Healing Architecture | 6.1 | Healing system |
| Healing States | 6.2 | Healing FSM |
| Healing Matrix | 6.3 | Issue-action mapping |
| Main Bot States | 7.1 | Bot state machine |
| Trading Cycle States | 7.2 | Cycle FSM |
| Position Lifecycle | 7.3 | Position FSM |

---

*Document Version: 1.0*
*Last Updated: January 17, 2026*
*Author: AI Workflow Designer*
