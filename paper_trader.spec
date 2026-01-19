# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Polymarket Paper Trader
Build with: pyinstaller paper_trader.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Get the project root
project_root = Path(SPECPATH)

# Analysis
a = Analysis(
    ['paper_trade_runner.py'],
    pathex=[str(project_root), str(project_root / 'src')],
    binaries=[],
    datas=[
        # Include source modules
        ('src', 'src'),
        ('config', 'config'),
        # Include .env.example as template
        ('.env.example', '.'),
    ],
    hiddenimports=[
        # Core Python
        'json',
        'logging',
        'pathlib',
        'datetime',
        'dataclasses',
        'typing',
        'random',
        'time',
        'argparse',
        
        # HTTP & Async
        'requests',
        'aiohttp',
        'httpx',
        
        # Data processing
        'pandas',
        'numpy',
        
        # Sentiment analysis
        'textblob',
        'vaderSentiment',
        'vaderSentiment.vaderSentiment',
        
        # Web scraping
        'feedparser',
        'bs4',
        'lxml',
        
        # Environment
        'dotenv',
        'python_dotenv',
        
        # Our modules
        'src',
        'src.data',
        'src.data.polymarket_client',
        'src.data.news_aggregator',
        'src.analysis',
        'src.analysis.sentiment_analyzer',
        'src.analysis.llm_sentiment',
        'src.strategies',
        'src.strategies.edge_aware_strategy',
        'src.strategies.momentum_strategy',
        'src.trading',
        'src.trading.paper_trader',
        'src.backtesting',
        'config',
        'config.settings',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy/unnecessary packages
        'transformers',
        'torch',
        'tensorflow',
        'matplotlib',
        'plotly',
        'dash',
        'pytest',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PolymarketPaperTrader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path if you have one
)
