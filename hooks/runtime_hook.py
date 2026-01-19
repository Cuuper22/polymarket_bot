"""
Runtime Hook for PyInstaller - Polymarket Bot
=============================================

This hook is executed BEFORE the main script when running as a frozen executable.
It sets up the environment for bundled applications.
"""

import os
import sys


def setup_frozen_environment():
    """Configure environment for PyInstaller bundle."""
    
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        # _MEIPASS contains extracted bundle contents
        base_path = sys._MEIPASS
        app_path = os.path.dirname(sys.executable)
    else:
        # Running as script (development mode)
        base_path = os.path.dirname(os.path.abspath(__file__))
        app_path = base_path
    
    # Set environment variables for app to discover paths
    os.environ['POLYMARKET_BOT_FROZEN'] = '1' if getattr(sys, 'frozen', False) else '0'
    os.environ['POLYMARKET_BOT_BASE'] = base_path
    os.environ['POLYMARKET_BOT_APP'] = app_path
    os.environ['POLYMARKET_BOT_DATA'] = os.path.join(app_path, 'data')
    os.environ['POLYMARKET_BOT_LOGS'] = os.path.join(app_path, 'logs')
    os.environ['POLYMARKET_BOT_CONFIG'] = os.path.join(app_path, 'config')
    
    # Create required directories
    for dir_env in ['POLYMARKET_BOT_DATA', 'POLYMARKET_BOT_LOGS']:
        dir_path = os.environ.get(dir_env)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
    
    # Windows-specific setup
    if sys.platform == 'win32':
        # Multiprocessing freeze support
        import multiprocessing
        multiprocessing.freeze_support()
        
        # Set process DPI awareness for high-DPI displays
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    
    # Suppress asyncio Windows event loop warnings
    if sys.platform == 'win32':
        import asyncio
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except AttributeError:
            pass


# Execute setup on import
setup_frozen_environment()
