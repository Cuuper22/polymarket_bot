# Polymarket Bot - Windows Automation & Packaging Design

## Executive Summary

This document provides a comprehensive design for packaging the Polymarket trading bot as a standalone Windows executable with auto-start capabilities, web dashboard, and enterprise-grade logging and state management.

---

## 1. Technology Stack

### Core Runtime
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Runtime | Python | 3.11+ | Core application runtime |
| Packaging | PyInstaller | 6.x | Windows executable creation |
| Installer | Inno Setup | 6.x | MSI/Setup installer creation |
| Process Manager | Windows Services | Native | Background service support |

### Web Dashboard
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Backend | FastAPI | 0.100+ | REST API & WebSocket server |
| Frontend | React/Vite | 18.x/5.x | Modern SPA dashboard |
| Real-time | WebSocket | Native | Live data streaming |
| Charts | Plotly.js | 2.x | Trading charts & analytics |
| UI Framework | Tailwind CSS | 3.x | Responsive styling |

### Data & Storage
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Database | SQLite | 3.x | Local persistent storage |
| Cache | LRU Cache | Built-in | In-memory caching |
| State | JSON/SQLite | - | Application state persistence |
| Config | TOML/ENV | - | Configuration management |

### Logging & Monitoring
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Logging | loguru | 0.7+ | Structured logging (planned) |
| Metrics | Prometheus Client | 0.17+ | Metrics collection (planned) |
| Alerts | Windows Toast | pywin32 | Desktop notifications (planned) |

---

## 2. Application Architecture

### 2.1 High-Level Architecture

```
+------------------------------------------------------------------+
|                    POLYMARKET BOT WINDOWS APP                      |
+------------------------------------------------------------------+
|                                                                    |
|  +-------------------+     +-------------------+                   |
|  |   System Tray     |<--->|   Main Process    |                   |
|  |   Controller      |     |   (Orchestrator)  |                   |
|  +-------------------+     +-------------------+                   |
|           |                        |                               |
|           v                        v                               |
|  +-------------------+     +-------------------+                   |
|  |   Web Dashboard   |<--->|   Trading Engine  |                   |
|  |   (FastAPI+React) |     |   (Core Logic)    |                   |
|  +-------------------+     +-------------------+                   |
|           |                        |                               |
|           v                        v                               |
|  +-------------------+     +-------------------+                   |
|  |   WebSocket Hub   |<--->|   Data Services   |                   |
|  |   (Real-time)     |     |   (API Clients)   |                   |
|  +-------------------+     +-------------------+                   |
|           |                        |                               |
|           v                        v                               |
|  +-------------------+     +-------------------+                   |
|  |   SQLite DB       |     |   State Manager   |                   |
|  |   (Persistence)   |<--->|   (JSON/Cache)    |                   |
|  +-------------------+     +-------------------+                   |
|                                                                    |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                     EXTERNAL SERVICES                              |
+------------------------------------------------------------------+
|  Polymarket API  |  News RSS  |  Reddit API  |  Google Trends     |
+------------------------------------------------------------------+
```

### 2.2 Component Breakdown

#### Core Process Manager (`src/core/process_manager.py`)
```python
# Planned component (not implemented yet)
- ApplicationManager: Main orchestrator
- ProcessPool: Manages trading engine threads
- SignalHandler: Handles SIGTERM, SIGINT for clean shutdown
- HealthChecker: Monitors component health
```

#### Trading Engine (`src/core/trading_engine.py`)
```python
# Planned component (not implemented yet)
- TradingEngine: Main trading loop
- OpportunityScanner: Market scanning
- PositionManager: Position lifecycle
- RiskController: Risk management
```

#### Web Server (`src/dashboard/server.py`)
```python
# Planned component (not implemented yet)
- DashboardServer: HTTP/WS server
- APIRouter: REST endpoints
- WebSocketManager: Real-time updates
- StaticFileServer: Serves React build
```

#### System Tray (`src/gui/tray_app.py`)
```python
# Planned component (not implemented yet)
- TrayApplication: System tray icon
- MenuController: Context menu actions
- NotificationManager: Toast notifications
- SettingsDialog: Quick settings access
```

---

## 3. Directory Structure (Planned vs Current)

This tree represents a planned packaging layout; only a subset exists today.

```
polymarket_bot/
├── build/                          # Build artifacts (planned)
│   ├── pyinstaller/
│   ├── installer/
│   └── release/
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── aggressive_strategy.py
│
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── polymarket_client.py
│   │   └── news_aggregator.py
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── sentiment_analyzer.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── edge_detector.py
│   │   └── position_sizer.py
│   ├── trading/
│   │   ├── __init__.py
│   │   └── paper_trader.py
│   └── backtesting/
│       ├── __init__.py
│       └── backtest_engine.py
│
├── main.py
├── app.py
├── polymarket_bot.spec
└── requirements-build.txt
```

polymarket_bot/
├── build/                          # Build artifacts
│   ├── pyinstaller/               # PyInstaller output
│   ├── installer/                 # Inno Setup output
│   └── release/                   # Final release packages
│
├── config/                         # Configuration
│   ├── __init__.py
│   ├── settings.py                # Pydantic settings
│   ├── defaults.toml              # Default configuration
│   └── logging_config.py          # Logging configuration
│
├── src/                            # Source code
│   ├── __init__.py
│   │
│   ├── core/                      # Core application
│   │   ├── __init__.py
│   │   ├── app.py                 # Main application entry
│   │   ├── process_manager.py     # Process lifecycle
│   │   ├── trading_engine.py      # Trading logic
│   │   ├── scheduler.py           # Task scheduling
│   │   └── service.py             # Windows service wrapper
│   │
│   ├── data/                      # Data layer
│   │   ├── __init__.py
│   │   ├── polymarket_client.py   # Polymarket API
│   │   ├── news_aggregator.py     # News collection
│   │   └── cache_manager.py       # Caching layer
│   │
│   ├── analysis/                  # Analysis modules
│   │   ├── __init__.py
│   │   └── sentiment_analyzer.py  # Sentiment analysis
│   │
│   ├── strategies/                # Trading strategies
│   │   ├── __init__.py
│   │   ├── edge_detector.py       # Signal detection
│   │   └── position_sizer.py      # Position sizing
│   │
│   ├── trading/                   # Trading execution
│   │   ├── __init__.py
│   │   ├── paper_trader.py        # Paper trading
│   │   └── live_trader.py         # Live trading
│   │
│   ├── backtesting/               # Backtesting
│   │   ├── __init__.py
│   │   └── backtest_engine.py     # Backtest engine
│   │
│   ├── dashboard/                 # Web dashboard
│   │   ├── __init__.py
│   │   ├── server.py              # FastAPI server
│   │   ├── api/                   # API routes
│   │   │   ├── __init__.py
│   │   │   ├── markets.py         # Market endpoints
│   │   │   ├── trading.py         # Trading endpoints
│   │   │   ├── analytics.py       # Analytics endpoints
│   │   │   └── websocket.py       # WebSocket handlers
│   │   └── static/                # React build output
│   │       └── (bundled frontend)
│   │
│   ├── gui/                       # Windows GUI components
│   │   ├── __init__.py
│   │   ├── tray_app.py            # System tray application
│   │   ├── notifications.py       # Windows notifications
│   │   └── settings_dialog.py     # Settings UI
│   │
│   ├── storage/                   # Data storage
│   │   ├── __init__.py
│   │   ├── database.py            # SQLite wrapper
│   │   ├── state_manager.py       # State persistence
│   │   └── migrations/            # DB migrations
│   │
│   └── utils/                     # Utilities
│       ├── __init__.py
│       ├── logging.py             # Logging setup
│       ├── crypto.py              # Encryption utilities
│       └── windows.py             # Windows-specific utils
│
├── dashboard-ui/                   # React dashboard source
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── services/
│   ├── package.json
│   └── vite.config.js
│
├── scripts/                        # Build scripts
│   ├── build_exe.py               # PyInstaller build script
│   ├── build_installer.py         # Inno Setup build
│   ├── build_dashboard.py         # React build
│   └── release.py                 # Full release pipeline
│
├── installer/                      # Installer resources
│   ├── setup.iss                  # Inno Setup script
│   ├── license.txt                # License file
│   └── assets/                    # Icons, images
│       ├── icon.ico
│       ├── banner.bmp
│       └── wizard.bmp
│
├── data/                           # Runtime data (user)
│   ├── polymarket_bot.db          # SQLite database
│   ├── state/                     # State files
│   └── cache/                     # Cache files
│
├── logs/                           # Log files (user)
│   ├── app.log                    # Main application log
│   ├── trading.log                # Trading activity log
│   └── error.log                  # Error log
│
├── tests/                          # Test suite
│   └── ...
│
├── main.py                         # CLI entry point
├── app.py                          # GUI/Service entry point
├── polymarket_bot.spec             # PyInstaller spec file
├── requirements.txt                # Dependencies
├── requirements-build.txt          # Build dependencies
└── README.md
```

---

## 4. Windows Auto-Start Mechanisms

### 4.1 Option A: Startup Folder (User-Level)

**Implementation:**
```python
# src/utils/windows.py

import os
import sys
import winreg
from pathlib import Path

def get_startup_folder() -> Path:
    """Get Windows startup folder path."""
    return Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Startup'

def create_startup_shortcut(target_exe: str, name: str = "PolymarketBot"):
    """Create startup shortcut using Windows Shell."""
    try:
        import win32com.client
        
        startup_folder = get_startup_folder()
        shortcut_path = startup_folder / f"{name}.lnk"
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = target_exe
        shortcut.WorkingDirectory = str(Path(target_exe).parent)
        shortcut.IconLocation = target_exe
        shortcut.Description = "Polymarket Trading Bot"
        shortcut.Arguments = "--minimized"
        shortcut.save()
        
        return True
    except Exception as e:
        logging.error(f"Failed to create startup shortcut: {e}")
        return False

def remove_startup_shortcut(name: str = "PolymarketBot"):
    """Remove startup shortcut."""
    shortcut_path = get_startup_folder() / f"{name}.lnk"
    if shortcut_path.exists():
        shortcut_path.unlink()
        return True
    return False
```

### 4.2 Option B: Registry Run Key (User-Level)

**Implementation:**
```python
# src/utils/windows.py

def add_to_registry_startup(exe_path: str, name: str = "PolymarketBot"):
    """Add application to Windows Registry startup."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, f'"{exe_path}" --minimized')
        winreg.CloseKey(key)
        return True
    except WindowsError as e:
        logging.error(f"Failed to add registry startup: {e}")
        return False

def remove_from_registry_startup(name: str = "PolymarketBot"):
    """Remove application from Windows Registry startup."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, name)
        winreg.CloseKey(key)
        return True
    except WindowsError:
        return False
```

### 4.3 Option C: Windows Service (System-Level)

**Implementation:**
```python
# src/core/service.py

import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import logging

class PolymarketBotService(win32serviceutil.ServiceFramework):
    """Windows Service wrapper for Polymarket Bot."""
    
    _svc_name_ = "PolymarketBot"
    _svc_display_name_ = "Polymarket Trading Bot"
    _svc_description_ = "Automated prediction market trading bot"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        socket.setdefaulttimeout(60)
        
    def SvcStop(self):
        """Handle service stop."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.running = False
        
    def SvcDoRun(self):
        """Main service entry point."""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()
        
    def main(self):
        """Main service loop."""
        from src.core.app import PolymarketBotApp
        
        app = PolymarketBotApp(headless=True)
        
        while self.running:
            # Check for stop signal
            rc = win32event.WaitForSingleObject(self.stop_event, 1000)
            if rc == win32event.WAIT_OBJECT_0:
                break
            
            # Run trading cycle
            app.run_cycle()
        
        app.shutdown()


def install_service():
    """Install Windows service."""
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PolymarketBotService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(PolymarketBotService)


# CLI commands for service management
# python service.py install
# python service.py start
# python service.py stop
# python service.py remove
```

### 4.4 Task Scheduler (Recommended for Reliability)

**Implementation:**
```python
# src/utils/windows.py

import subprocess

def create_scheduled_task(exe_path: str, name: str = "PolymarketBot"):
    """Create Windows Task Scheduler task for auto-start."""
    task_xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Polymarket Trading Bot Auto-Start</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT5M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions>
    <Exec>
      <Command>{exe_path}</Command>
      <Arguments>--minimized</Arguments>
    </Exec>
  </Actions>
</Task>'''
    
    # Write XML to temp file and import
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(task_xml)
        temp_path = f.name
    
    try:
        result = subprocess.run([
            'schtasks', '/Create', '/TN', name, '/XML', temp_path, '/F'
        ], capture_output=True, text=True)
        
        return result.returncode == 0
    finally:
        Path(temp_path).unlink(missing_ok=True)


def remove_scheduled_task(name: str = "PolymarketBot"):
    """Remove scheduled task."""
    result = subprocess.run([
        'schtasks', '/Delete', '/TN', name, '/F'
    ], capture_output=True)
    return result.returncode == 0
```

---

## 5. PyInstaller Specification

### 5.1 Main Spec File (`polymarket_bot.spec`)

```python
# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Polymarket Trading Bot
Build command: pyinstaller polymarket_bot.spec
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Project paths
PROJECT_ROOT = Path(SPECPATH)
SRC_PATH = PROJECT_ROOT / 'src'
CONFIG_PATH = PROJECT_ROOT / 'config'
ASSETS_PATH = PROJECT_ROOT / 'installer' / 'assets'

# Collect hidden imports for complex packages
hidden_imports = [
    # Core dependencies
    'asyncio',
    'concurrent.futures',
    'multiprocessing',
    'threading',
    
    # Web framework
    'fastapi',
    'uvicorn',
    'starlette',
    'pydantic',
    'pydantic_settings',
    'websockets',
    
    # Data processing
    'pandas',
    'numpy',
    'scipy',
    'sklearn',
    
    # HTTP clients
    'requests',
    'aiohttp',
    'httpx',
    
    # NLP/Sentiment
    'textblob',
    'vaderSentiment',
    'nltk',
    
    # News sources
    'feedparser',
    'praw',
    'beautifulsoup4',
    'lxml',
    
    # Database
    'sqlalchemy',
    'sqlite3',
    
    # Windows-specific
    'win32api',
    'win32con',
    'win32gui',
    'win32service',
    'win32serviceutil',
    'pystray',
    'PIL',
    
    # Logging
    'loguru',
    
    # Visualization (for dashboard)
    'plotly',
    
    # Polymarket
    'py_clob_client',
    'web3',
    'eth_account',
]

# Collect all submodules for complex packages
hidden_imports += collect_submodules('sklearn')
hidden_imports += collect_submodules('scipy')
hidden_imports += collect_submodules('pydantic')
hidden_imports += collect_submodules('starlette')

# Data files to include
datas = [
    # Configuration files
    (str(CONFIG_PATH / 'defaults.toml'), 'config'),
    (str(PROJECT_ROOT / '.env.example'), '.'),
    
    # Dashboard static files (React build)
    (str(SRC_PATH / 'dashboard' / 'static'), 'dashboard/static'),
    
    # NLTK data (if used)
    # (str(Path(sys.prefix) / 'nltk_data'), 'nltk_data'),
    
    # TextBlob corpora
    # Collected via hooks
]

# Collect data files from packages
datas += collect_data_files('vaderSentiment')
datas += collect_data_files('textblob')

# Binary files (DLLs, etc.)
binaries = []

# Analysis configuration
a = Analysis(
    ['app.py'],  # Main entry point
    pathex=[str(PROJECT_ROOT), str(SRC_PATH)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[str(PROJECT_ROOT / 'hooks')],  # Custom hooks directory
    hooksconfig={},
    runtime_hooks=[str(PROJECT_ROOT / 'hooks' / 'runtime_hook.py')],
    excludes=[
        # Exclude unnecessary packages
        'tkinter',
        'matplotlib',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'sphinx',
        # Exclude transformers (too heavy, optional)
        'transformers',
        'torch',
        'tensorflow',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate binaries/data
# (helps reduce size)
a.binaries = list(set(a.binaries))
a.datas = list(set(a.datas))

# Create PYZ archive
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None
)

# Create EXE
exe = EXE(
    pyz,
    a.scripts,
    [],  # Not one-file mode
    exclude_binaries=True,
    name='PolymarketBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Enable UPX compression
    console=False,  # GUI mode (no console window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS_PATH / 'icon.ico'),
    version=str(PROJECT_ROOT / 'version_info.txt'),
    uac_admin=False,  # Don't require admin
    uac_uiaccess=False,
)

# Create COLLECT (directory mode)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        'vcruntime140.dll',
        'python3.dll',
        'python311.dll',
    ],
    name='PolymarketBot',
)

# ============================================================
# ONE-FILE BUILD (Alternative - larger but single executable)
# ============================================================
# Uncomment below for single-file build:

# exe_onefile = EXE(
#     pyz,
#     a.scripts,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     [],
#     name='PolymarketBot',
#     debug=False,
#     bootloader_ignore_signals=False,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     runtime_tmpdir=None,
#     console=False,
#     disable_windowed_traceback=False,
#     argv_emulation=False,
#     target_arch=None,
#     codesign_identity=None,
#     entitlements_file=None,
#     icon=str(ASSETS_PATH / 'icon.ico'),
# )
```

### 5.2 Runtime Hook (`hooks/runtime_hook.py`)

```python
# hooks/runtime_hook.py
"""
Runtime hook for PyInstaller - executed before main script
"""

import os
import sys

def setup_environment():
    """Configure environment for bundled application."""
    
    # Set base path for bundled resources
    if getattr(sys, 'frozen', False):
        # Running as compiled
        BASE_PATH = sys._MEIPASS
        APP_PATH = os.path.dirname(sys.executable)
    else:
        # Running as script
        BASE_PATH = os.path.dirname(os.path.abspath(__file__))
        APP_PATH = BASE_PATH
    
    # Set environment variables
    os.environ['POLYMARKET_BOT_BASE'] = BASE_PATH
    os.environ['POLYMARKET_BOT_APP'] = APP_PATH
    os.environ['POLYMARKET_BOT_DATA'] = os.path.join(APP_PATH, 'data')
    os.environ['POLYMARKET_BOT_LOGS'] = os.path.join(APP_PATH, 'logs')
    
    # Create data directories if they don't exist
    for dir_path in [
        os.environ['POLYMARKET_BOT_DATA'],
        os.environ['POLYMARKET_BOT_LOGS'],
    ]:
        os.makedirs(dir_path, exist_ok=True)
    
    # Fix multiprocessing for frozen app
    if sys.platform == 'win32':
        import multiprocessing
        multiprocessing.freeze_support()

setup_environment()
```

### 5.3 Version Info File (`version_info.txt`)

```python
# version_info.txt - Windows version resource

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [
            StringStruct(u'CompanyName', u'Your Company'),
            StringStruct(u'FileDescription', u'Polymarket Trading Bot'),
            StringStruct(u'FileVersion', u'1.0.0.0'),
            StringStruct(u'InternalName', u'PolymarketBot'),
            StringStruct(u'LegalCopyright', u'Copyright (c) 2024'),
            StringStruct(u'OriginalFilename', u'PolymarketBot.exe'),
            StringStruct(u'ProductName', u'Polymarket Trading Bot'),
            StringStruct(u'ProductVersion', u'1.0.0.0'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
```

---

## 6. Web Dashboard Architecture

### 6.1 Backend API Structure

```python
# src/dashboard/server.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from pathlib import Path

class DashboardServer:
    """FastAPI-based dashboard server."""
    
    def __init__(self, trading_engine, host: str = "127.0.0.1", port: int = 8765):
        self.app = FastAPI(
            title="Polymarket Bot Dashboard",
            version="1.0.0"
        )
        self.trading_engine = trading_engine
        self.host = host
        self.port = port
        self.websocket_clients: set = set()
        
        self._setup_middleware()
        self._setup_routes()
        self._setup_websocket()
        self._setup_static_files()
    
    def _setup_middleware(self):
        """Configure CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://127.0.0.1:8765"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self):
        """Setup API routes."""
        from .api import markets, trading, analytics
        
        self.app.include_router(markets.router, prefix="/api/markets", tags=["markets"])
        self.app.include_router(trading.router, prefix="/api/trading", tags=["trading"])
        self.app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
        
        @self.app.get("/api/health")
        async def health_check():
            return {"status": "healthy", "version": "1.0.0"}
        
        @self.app.get("/api/status")
        async def get_status():
            return {
                "running": self.trading_engine.is_running,
                "account": self.trading_engine.get_account_summary(),
                "last_cycle": self.trading_engine.last_cycle_time,
            }
    
    def _setup_websocket(self):
        """Setup WebSocket endpoint for real-time updates."""
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.websocket_clients.add(websocket)
            
            try:
                while True:
                    # Keep connection alive, receive commands
                    data = await websocket.receive_text()
                    await self._handle_ws_message(websocket, data)
            except WebSocketDisconnect:
                self.websocket_clients.discard(websocket)
    
    async def _handle_ws_message(self, websocket: WebSocket, message: str):
        """Handle incoming WebSocket messages."""
        import json
        try:
            data = json.loads(message)
            action = data.get("action")
            
            if action == "subscribe":
                channel = data.get("channel")
                # Handle subscription
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
        except Exception as e:
            await websocket.send_json({"type": "error", "message": str(e)})
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        import json
        for client in self.websocket_clients.copy():
            try:
                await client.send_text(json.dumps(message))
            except:
                self.websocket_clients.discard(client)
    
    def _setup_static_files(self):
        """Serve React dashboard static files."""
        static_path = Path(__file__).parent / "static"
        if static_path.exists():
            self.app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")
    
    def run(self, blocking: bool = True):
        """Start the dashboard server."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False
        )
        server = uvicorn.Server(config)
        
        if blocking:
            server.run()
        else:
            # Run in background thread
            import threading
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            return thread
```

### 6.2 API Endpoints Structure

```
GET  /api/health                    - Health check
GET  /api/status                    - Bot status

GET  /api/markets                   - List active markets
GET  /api/markets/{id}              - Get market details
GET  /api/markets/{id}/orderbook    - Get order book
GET  /api/markets/opportunities     - Get current opportunities

GET  /api/trading/account           - Account summary
GET  /api/trading/positions         - Open positions
GET  /api/trading/history           - Trade history
POST /api/trading/start             - Start trading
POST /api/trading/stop              - Stop trading
POST /api/trading/execute           - Execute trade (paper)

GET  /api/analytics/performance     - Performance metrics
GET  /api/analytics/pnl             - P&L chart data
GET  /api/analytics/signals         - Signal history

WS   /ws                            - Real-time updates
```

### 6.3 Frontend Structure (React)

```
dashboard-ui/
├── src/
│   ├── components/
│   │   ├── common/
│   │   │   ├── Card.tsx
│   │   │   ├── Button.tsx
│   │   │   ├── Badge.tsx
│   │   │   └── Loading.tsx
│   │   ├── charts/
│   │   │   ├── PnLChart.tsx
│   │   │   ├── EquityCurve.tsx
│   │   │   └── MarketHeatmap.tsx
│   │   ├── trading/
│   │   │   ├── PositionCard.tsx
│   │   │   ├── OpportunityList.tsx
│   │   │   └── TradeHistory.tsx
│   │   └── layout/
│   │       ├── Sidebar.tsx
│   │       ├── Header.tsx
│   │       └── StatusBar.tsx
│   │
│   ├── pages/
│   │   ├── Dashboard.tsx          # Main dashboard
│   │   ├── Markets.tsx            # Market explorer
│   │   ├── Trading.tsx            # Trading view
│   │   ├── Analytics.tsx          # Performance analytics
│   │   ├── Backtest.tsx           # Backtesting
│   │   └── Settings.tsx           # Configuration
│   │
│   ├── hooks/
│   │   ├── useWebSocket.ts        # WebSocket connection
│   │   ├── useApi.ts              # API calls
│   │   └── useAccount.ts          # Account state
│   │
│   ├── services/
│   │   ├── api.ts                 # API client
│   │   └── websocket.ts           # WebSocket manager
│   │
│   ├── store/
│   │   ├── index.ts               # Zustand store
│   │   └── slices/
│   │
│   ├── App.tsx
│   └── main.tsx
│
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

---

## 7. Logging and State Management

### 7.1 Logging Configuration

```python
# config/logging_config.py

import sys
from pathlib import Path
from loguru import logger
from datetime import datetime

def setup_logging(log_dir: Path = None, debug: bool = False):
    """Configure application logging with Loguru."""
    
    if log_dir is None:
        log_dir = Path.home() / '.polymarket_bot' / 'logs'
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Remove default handler
    logger.remove()
    
    # Console handler (colored output)
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if debug else "INFO",
        colorize=True,
    )
    
    # Main application log (rotating)
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="00:00",      # Rotate at midnight
        retention="30 days",   # Keep 30 days
        compression="zip",     # Compress old logs
        enqueue=True,          # Thread-safe
    )
    
    # Trading-specific log
    logger.add(
        log_dir / "trading_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
        level="INFO",
        filter=lambda record: "trading" in record["extra"].get("module", ""),
        rotation="00:00",
        retention="90 days",   # Keep trading logs longer
        compression="zip",
    )
    
    # Error log (separate for easy monitoring)
    logger.add(
        log_dir / "error.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}\n{exception}",
        level="ERROR",
        rotation="10 MB",
        retention="60 days",
        backtrace=True,
        diagnose=True,
    )
    
    # JSON log for structured logging / external tools
    logger.add(
        log_dir / "structured_{time:YYYY-MM-DD}.json",
        format="{message}",
        level="INFO",
        rotation="00:00",
        retention="14 days",
        serialize=True,  # JSON format
    )
    
    return logger


# Usage example:
# from config.logging_config import setup_logging
# logger = setup_logging()
# logger.bind(module="trading").info("Position opened")
```

### 7.2 State Management

```python
# src/storage/state_manager.py

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
from contextlib import contextmanager
import threading
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class AppState:
    """Application state structure."""
    is_running: bool = False
    last_scan_time: Optional[str] = None
    last_cycle_result: Optional[dict] = None
    total_cycles: int = 0
    settings_hash: Optional[str] = None


class StateManager:
    """
    Manages application state persistence with SQLite backend
    and JSON export for dashboard consumption.
    """
    
    def __init__(self, db_path: Path = None, state_dir: Path = None):
        self.db_path = db_path or Path.home() / '.polymarket_bot' / 'data' / 'state.db'
        self.state_dir = state_dir or Path.home() / '.polymarket_bot' / 'state'
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database."""
        with self._get_connection() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS positions (
                    id TEXT PRIMARY KEY,
                    market_id TEXT,
                    data TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    position_id TEXT,
                    data TEXT,
                    created_at TEXT
                );
                
                CREATE TABLE IF NOT EXISTS metrics (
                    timestamp TEXT PRIMARY KEY,
                    equity REAL,
                    capital REAL,
                    pnl REAL,
                    open_positions INTEGER
                );
                
                CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at);
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
            ''')
    
    @contextmanager
    def _get_connection(self):
        """Get thread-safe database connection."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def set(self, key: str, value: Any):
        """Set a state value."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO state (key, value, updated_at)
                       VALUES (?, ?, ?)''',
                    (key, json.dumps(value), datetime.now().isoformat())
                )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        with self._get_connection() as conn:
            row = conn.execute(
                'SELECT value FROM state WHERE key = ?', (key,)
            ).fetchone()
            
            if row:
                return json.loads(row['value'])
            return default
    
    def save_position(self, position_id: str, position_data: dict):
        """Save position to database."""
        with self._lock:
            with self._get_connection() as conn:
                now = datetime.now().isoformat()
                conn.execute(
                    '''INSERT OR REPLACE INTO positions (id, market_id, data, created_at, updated_at)
                       VALUES (?, ?, ?, COALESCE((SELECT created_at FROM positions WHERE id = ?), ?), ?)''',
                    (position_id, position_data.get('market_id'), json.dumps(position_data),
                     position_id, now, now)
                )
    
    def save_trade(self, trade_data: dict):
        """Save completed trade to database."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    '''INSERT INTO trades (id, position_id, data, created_at)
                       VALUES (?, ?, ?, ?)''',
                    (trade_data['trade_id'], trade_data.get('position_id'),
                     json.dumps(trade_data), datetime.now().isoformat())
                )
    
    def record_metrics(self, equity: float, capital: float, pnl: float, open_positions: int):
        """Record periodic metrics for charting."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    '''INSERT INTO metrics (timestamp, equity, capital, pnl, open_positions)
                       VALUES (?, ?, ?, ?, ?)''',
                    (datetime.now().isoformat(), equity, capital, pnl, open_positions)
                )
    
    def get_metrics_history(self, days: int = 30) -> list:
        """Get metrics history for charts."""
        with self._get_connection() as conn:
            rows = conn.execute(
                '''SELECT * FROM metrics 
                   WHERE timestamp > datetime('now', ?)
                   ORDER BY timestamp''',
                (f'-{days} days',)
            ).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_trade_history(self, limit: int = 100) -> list:
        """Get trade history."""
        with self._get_connection() as conn:
            rows = conn.execute(
                '''SELECT data FROM trades ORDER BY created_at DESC LIMIT ?''',
                (limit,)
            ).fetchall()
            
            return [json.loads(row['data']) for row in rows]
    
    def export_state_json(self):
        """Export current state to JSON file for dashboard."""
        state = {
            'app_state': self.get('app_state', {}),
            'account': self.get('account', {}),
            'positions': self.get('positions', []),
            'last_updated': datetime.now().isoformat(),
        }
        
        state_file = self.state_dir / 'current_state.json'
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
        
        return state_file
```

### 7.3 Configuration Encryption

```python
# src/utils/crypto.py

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pathlib import Path


class ConfigEncryption:
    """Encrypt sensitive configuration data."""
    
    def __init__(self, key_file: Path = None):
        self.key_file = key_file or Path.home() / '.polymarket_bot' / '.key'
        self._fernet = None
    
    def _get_or_create_key(self) -> bytes:
        """Get existing key or create new one."""
        if self.key_file.exists():
            return self.key_file.read_bytes()
        
        # Generate new key
        key = Fernet.generate_key()
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        self.key_file.write_bytes(key)
        
        # Set restrictive permissions (Windows)
        import stat
        os.chmod(self.key_file, stat.S_IRUSR | stat.S_IWUSR)
        
        return key
    
    @property
    def fernet(self) -> Fernet:
        """Get Fernet instance."""
        if self._fernet is None:
            key = self._get_or_create_key()
            self._fernet = Fernet(key)
        return self._fernet
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        encrypted = self.fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data."""
        decoded = base64.urlsafe_b64decode(encrypted_data.encode())
        return self.fernet.decrypt(decoded).decode()
    
    def encrypt_file(self, source: Path, dest: Path = None):
        """Encrypt a file."""
        dest = dest or source.with_suffix(source.suffix + '.enc')
        encrypted = self.fernet.encrypt(source.read_bytes())
        dest.write_bytes(encrypted)
        return dest
    
    def decrypt_file(self, source: Path, dest: Path = None):
        """Decrypt a file."""
        dest = dest or source.with_suffix('')
        decrypted = self.fernet.decrypt(source.read_bytes())
        dest.write_bytes(decrypted)
        return dest
```

---

## 8. Resource Estimates

### 8.1 Memory Usage

| Component | Idle | Active | Peak |
|-----------|------|--------|------|
| Core Application | 50 MB | 80 MB | 150 MB |
| Trading Engine | 30 MB | 60 MB | 100 MB |
| Web Dashboard (Backend) | 40 MB | 70 MB | 120 MB |
| Dashboard (Frontend) | Browser | Browser | Browser |
| SQLite Database | 5 MB | 10 MB | 50 MB |
| Sentiment Analysis | 20 MB | 100 MB | 200 MB |
| **Total (No NLP)** | **~125 MB** | **~220 MB** | **~420 MB** |
| **Total (With VADER)** | **~145 MB** | **~320 MB** | **~620 MB** |

### 8.2 CPU Usage

| Component | Idle | Scanning | Analysis |
|-----------|------|----------|----------|
| Core Application | <1% | 5-10% | 10-15% |
| Web Server | <1% | 2-3% | 2-3% |
| Database Operations | <1% | 1-2% | 1-2% |
| Sentiment Analysis | 0% | 5-15% | 20-30% |
| **Total** | **~2%** | **~15%** | **~30-50%** |

### 8.3 Disk Usage

| Component | Size |
|-----------|------|
| Executable (Directory Mode) | 150-250 MB |
| Executable (One-File Mode) | 100-180 MB |
| Database (Empty) | <1 MB |
| Database (After 1 Month) | 5-20 MB |
| Logs (Per Day) | 1-5 MB |
| Logs (30 Days, Compressed) | 20-50 MB |
| **Total Installation** | **~200-300 MB** |
| **Total After 1 Month** | **~250-400 MB** |

### 8.4 Network Usage

| Activity | Bandwidth |
|----------|-----------|
| Market Data Fetch (per cycle) | 50-200 KB |
| News RSS Fetch (per cycle) | 100-500 KB |
| Order Book Updates | 10-50 KB |
| Dashboard WebSocket | 1-5 KB/s |
| **Total Per Hour (Active)** | **~5-20 MB** |
| **Total Per Day (15 min cycles)** | **~100-500 MB** |

### 8.5 Build Time Estimates

| Step | Time |
|------|------|
| PyInstaller Analysis | 30-60 sec |
| PyInstaller Build | 2-5 min |
| React Dashboard Build | 30-60 sec |
| UPX Compression | 1-2 min |
| Installer Creation | 30-60 sec |
| **Total Build Time** | **~5-10 min** |

---

## 9. Build Scripts

### 9.1 Main Build Script (`scripts/build_exe.py`)

```python
#!/usr/bin/env python3
"""
Build script for Polymarket Bot Windows executable.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BUILD_DIR = PROJECT_ROOT / 'build'
DIST_DIR = PROJECT_ROOT / 'dist'

def clean_build():
    """Clean previous build artifacts."""
    print("Cleaning previous builds...")
    for path in [BUILD_DIR / 'pyinstaller', DIST_DIR]:
        if path.exists():
            shutil.rmtree(path)
    print("Clean complete.")

def build_dashboard():
    """Build React dashboard."""
    print("Building dashboard...")
    dashboard_dir = PROJECT_ROOT / 'dashboard-ui'
    
    if not dashboard_dir.exists():
        print("Dashboard not found, skipping...")
        return
    
    subprocess.run(['npm', 'install'], cwd=dashboard_dir, check=True)
    subprocess.run(['npm', 'run', 'build'], cwd=dashboard_dir, check=True)
    
    # Copy build to src/dashboard/static
    static_dir = PROJECT_ROOT / 'src' / 'dashboard' / 'static'
    if static_dir.exists():
        shutil.rmtree(static_dir)
    shutil.copytree(dashboard_dir / 'dist', static_dir)
    
    print("Dashboard built successfully.")

def build_executable():
    """Build Windows executable with PyInstaller."""
    print("Building executable...")
    
    spec_file = PROJECT_ROOT / 'polymarket_bot.spec'
    
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        str(spec_file)
    ]
    
    subprocess.run(cmd, check=True)
    print("Executable built successfully.")

def compress_with_upx():
    """Compress binaries with UPX."""
    print("Compressing with UPX...")
    
    upx_path = shutil.which('upx')
    if not upx_path:
        print("UPX not found, skipping compression...")
        return
    
    exe_dir = DIST_DIR / 'PolymarketBot'
    for dll in exe_dir.glob('*.dll'):
        # Skip certain DLLs that don't compress well
        if any(skip in dll.name.lower() for skip in ['vcruntime', 'python3', 'msvcp']):
            continue
        subprocess.run([upx_path, '--best', str(dll)], capture_output=True)
    
    print("Compression complete.")

def create_installer():
    """Create installer with Inno Setup."""
    print("Creating installer...")
    
    iscc_path = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if not Path(iscc_path).exists():
        print("Inno Setup not found, skipping installer creation...")
        return
    
    iss_file = PROJECT_ROOT / 'installer' / 'setup.iss'
    subprocess.run([iscc_path, str(iss_file)], check=True)
    
    print("Installer created successfully.")

def main():
    """Main build process."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Build Polymarket Bot')
    parser.add_argument('--clean', action='store_true', help='Clean build first')
    parser.add_argument('--skip-dashboard', action='store_true', help='Skip dashboard build')
    parser.add_argument('--skip-installer', action='store_true', help='Skip installer creation')
    args = parser.parse_args()
    
    print("=" * 60)
    print("POLYMARKET BOT BUILD")
    print("=" * 60)
    
    if args.clean:
        clean_build()
    
    if not args.skip_dashboard:
        build_dashboard()
    
    build_executable()
    compress_with_upx()
    
    if not args.skip_installer:
        create_installer()
    
    print("=" * 60)
    print("BUILD COMPLETE!")
    print(f"Executable: {DIST_DIR / 'PolymarketBot' / 'PolymarketBot.exe'}")
    print("=" * 60)

if __name__ == '__main__':
    main()
```

### 9.2 Inno Setup Script (`installer/setup.iss`)

```iss
; Inno Setup Script for Polymarket Bot

#define MyAppName "Polymarket Bot"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Your Company"
#define MyAppURL "https://github.com/yourusername/polymarket_bot"
#define MyAppExeName "PolymarketBot.exe"

[Setup]
AppId={{UNIQUE-GUID-HERE}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=..\build\installer
OutputBaseFilename=PolymarketBot_Setup_{#MyAppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start automatically with Windows"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\PolymarketBot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"" --minimized"; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Check for .NET or other prerequisites here
end;
```

---

## 10. Build Dependencies (`requirements-build.txt`)

```txt
# PyInstaller and dependencies
pyinstaller>=6.0.0
pyinstaller-hooks-contrib>=2024.0

# Windows-specific
pywin32>=306
pystray>=0.19.0

# UPX compression (optional, download separately)
# https://github.com/upx/upx/releases

# Dashboard build (Node.js required)
# npm install in dashboard-ui/

# Installer (download Inno Setup separately)
# https://jrsoftware.org/isinfo.php
```

---

## 11. Summary & Recommendations

### Recommended Auto-Start Method
**Task Scheduler** is recommended for the best balance of:
- Reliability (auto-restart on failure)
- No admin privileges required
- Network dependency awareness
- Clean integration with Windows

### Build Configuration
- Use **directory mode** for easier debugging and updates
- Enable **UPX compression** to reduce size by 40-50%
- Create **Inno Setup installer** for professional distribution

### Resource Optimization
- Exclude `transformers` and `torch` for lighter builds (~100MB saved)
- Use VADER sentiment only (no heavy ML models)
- Enable database compression after 7 days of logs

### Security Considerations
- Encrypt private keys with `ConfigEncryption`
- Store sensitive data in `%APPDATA%`, not install directory
- Use Windows Credential Manager for API keys (future enhancement)

---

*Document Version: 1.0.0*
*Last Updated: January 2026*
