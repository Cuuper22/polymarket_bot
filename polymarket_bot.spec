# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Polymarket Trading Bot
================================================

Build Commands:
  pyinstaller polymarket_bot.spec              # Standard build
  pyinstaller polymarket_bot.spec --clean      # Clean build
  
Output: dist/PolymarketBot/PolymarketBot.exe
"""

import sys
import os
from pathlib import Path

# ==============================================================================
# PROJECT CONFIGURATION
# ==============================================================================

PROJECT_ROOT = Path(SPECPATH)
SRC_PATH = PROJECT_ROOT / 'src'
CONFIG_PATH = PROJECT_ROOT / 'config'
ASSETS_PATH = PROJECT_ROOT / 'installer' / 'assets'

# Application metadata
APP_NAME = 'PolymarketBot'
APP_VERSION = '1.0.0'
APP_DESCRIPTION = 'Polymarket Trading Bot'

# ==============================================================================
# HIDDEN IMPORTS
# ==============================================================================
# Modules that PyInstaller cannot detect automatically

hidden_imports = [
    # === Core Python ===
    'asyncio',
    'concurrent.futures',
    'multiprocessing',
    'threading',
    'queue',
    'json',
    'sqlite3',
    'decimal',
    'fractions',
    'statistics',
    
    # === Pydantic & Settings ===
    'pydantic',
    'pydantic.fields',
    'pydantic_settings',
    'pydantic_core',
    
    # === Web Framework (Optional Dashboard) ===
    # Uncomment if using FastAPI dashboard
    # 'fastapi',
    # 'fastapi.middleware',
    # 'fastapi.middleware.cors',
    # 'uvicorn',
    # 'uvicorn.config',
    # 'uvicorn.main',
    # 'uvicorn.protocols',
    # 'uvicorn.protocols.http',
    # 'uvicorn.protocols.http.auto',
    # 'uvicorn.lifespan',
    # 'uvicorn.lifespan.on',
    # 'starlette',
    # 'starlette.routing',
    # 'starlette.middleware',
    # 'websockets',
    
    # === HTTP Clients ===
    'requests',
    'requests.adapters',
    'urllib3',
    'urllib3.util',
    'urllib3.util.retry',
    'certifi',
    'charset_normalizer',
    'idna',
    
    # === Async HTTP (Optional) ===
    'aiohttp',
    'httpx',
    
    # === Data Processing ===
    'pandas',
    'pandas.core',
    'pandas.core.arrays',
    'numpy',
    'numpy.core',
    'numpy.core._methods',
    'numpy.lib.format',
    
    # === Scientific (Optional) ===
    # 'scipy',
    # 'scipy.stats',
    # 'sklearn',
    # 'sklearn.utils',
    
    # === NLP & Sentiment ===
    'textblob',
    'textblob.blob',
    'textblob.en',
    'textblob.en.sentiments',
    'vaderSentiment',
    'vaderSentiment.vaderSentiment',
    
    # === News Sources ===
    'feedparser',
    'praw',
    'praw.models',
    'beautifulsoup4',
    'bs4',
    'lxml',
    'lxml.etree',
    
    # === Database ===
    'sqlalchemy',
    'sqlalchemy.sql',
    'sqlalchemy.engine',
    'sqlalchemy.pool',
    'sqlalchemy.dialects.sqlite',
    
    # === Logging ===
    'loguru',
    'loguru._logger',
    
    # === Windows GUI ===
    'win32api',
    'win32con',
    'win32gui',
    'win32event',
    'win32service',
    'win32serviceutil',
    'servicemanager',
    'pystray',
    'pystray._win32',
    'PIL',
    'PIL.Image',
    
    # === Visualization (Optional) ===
    # 'plotly',
    # 'plotly.graph_objects',
    
    # === Polymarket ===
    'py_clob_client',
    'web3',
    'web3.auto',
    'eth_account',
    'eth_utils',
    
    # === Encryption ===
    'cryptography',
    'cryptography.fernet',
    'cryptography.hazmat',
    'cryptography.hazmat.primitives',
]

# ==============================================================================
# DATA FILES
# ==============================================================================
# Non-Python files to include in the bundle

datas = [
    # Configuration
    (str(CONFIG_PATH / 'settings.py'), 'config'),
    (str(PROJECT_ROOT / '.env.example'), '.'),
    
    # Dashboard static files (if exists)
    # (str(SRC_PATH / 'dashboard' / 'static'), 'dashboard/static'),
]

# Add VADER lexicon data
try:
    import vaderSentiment
    vader_path = Path(vaderSentiment.__file__).parent
    if (vader_path / 'vader_lexicon.txt').exists():
        datas.append((str(vader_path / 'vader_lexicon.txt'), 'vaderSentiment'))
except ImportError:
    pass

# ==============================================================================
# BINARY FILES
# ==============================================================================
# DLLs and compiled extensions

binaries = []

# ==============================================================================
# EXCLUDES
# ==============================================================================
# Modules to exclude from the bundle (reduces size)

excludes = [
    # Development tools
    'pytest',
    'pytest_asyncio',
    'sphinx',
    'IPython',
    'jupyter',
    'notebook',
    
    # GUI frameworks not used
    'tkinter',
    '_tkinter',
    'tk',
    'tcl',
    
    # Heavy ML packages (exclude if not using)
    'transformers',
    'torch',
    'tensorflow',
    'keras',
    
    # Plotting (exclude if not using)
    'matplotlib',
    'matplotlib.pyplot',
    
    # Testing
    'test',
    'tests',
    'unittest',
]

# ==============================================================================
# ANALYSIS
# ==============================================================================

a = Analysis(
    ['app.py'],
    pathex=[str(PROJECT_ROOT), str(SRC_PATH)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# ==============================================================================
# CLEANUP (Optional)
# ==============================================================================
# Remove duplicate entries

def remove_duplicates(items):
    seen = set()
    result = []
    for item in items:
        key = item[0] if isinstance(item, tuple) else item
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

a.binaries = remove_duplicates(a.binaries)
a.datas = remove_duplicates(a.datas)

# ==============================================================================
# PYZ ARCHIVE
# ==============================================================================

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)

# ==============================================================================
# EXECUTABLE - DIRECTORY MODE (Recommended for Development)
# ==============================================================================

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS_PATH / 'icon.ico') if (ASSETS_PATH / 'icon.ico').exists() else None,
    uac_admin=False,
    uac_uiaccess=False,
)

# Collect all files into directory
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        # Don't compress these (may cause issues)
        'vcruntime140.dll',
        'vcruntime140_1.dll',
        'python3.dll',
        'python311.dll',
        'python312.dll',
        'msvcp140.dll',
        'api-ms-*.dll',
        'ucrtbase.dll',
    ],
    name=APP_NAME,
)

# ==============================================================================
# ONE-FILE BUILD (Alternative - Uncomment to use)
# ==============================================================================
# Creates single EXE file, slower to start but easier to distribute

"""
exe_onefile = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        'vcruntime140.dll',
        'python3.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS_PATH / 'icon.ico') if (ASSETS_PATH / 'icon.ico').exists() else None,
)
"""

# ==============================================================================
# BUILD INFO
# ==============================================================================

print(f"""
================================================================================
PyInstaller Build Configuration
================================================================================
Application:     {APP_NAME} v{APP_VERSION}
Entry Point:     app.py
Output:          dist/{APP_NAME}/{APP_NAME}.exe
Mode:            Directory (folder)
Console:         No (GUI mode)
UPX Compression: Enabled
================================================================================
""")
