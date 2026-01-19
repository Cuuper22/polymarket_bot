#!/usr/bin/env python3
"""
Polymarket Trading Bot - Windows Application Entry Point

This is the main entry point for the packaged Windows executable.
Supports multiple run modes:
- GUI mode with system tray (default)
- Console mode for debugging
- Windows service mode
- Headless daemon mode
"""

import argparse
import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

# Setup frozen app support
def get_app_paths():
    """Get application paths for both frozen and development modes."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_path = Path(sys._MEIPASS)
        app_path = Path(sys.executable).parent
    else:
        # Running as script
        base_path = Path(__file__).parent
        app_path = base_path
    
    return {
        'base': base_path,
        'app': app_path,
        'data': app_path / 'data',
        'logs': app_path / 'logs',
        'config': app_path / 'config',
    }

PATHS = get_app_paths()

# Ensure data directories exist
for key in ['data', 'logs']:
    PATHS[key].mkdir(parents=True, exist_ok=True)

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PATHS['logs'] / 'app.log'),
    ]
)
logger = logging.getLogger(__name__)


class PolymarketBotApp:
    """
    Main application class for Polymarket Trading Bot.
    Coordinates all components: trading engine, dashboard, and system tray.
    """
    
    def __init__(self, headless: bool = False, debug: bool = False):
        """
        Initialize the application.
        
        Args:
            headless: Run without GUI (daemon mode)
            debug: Enable debug logging
        """
        self.headless = headless
        self.debug = debug
        self.running = False
        self.dashboard_thread: Optional[threading.Thread] = None
        self.trading_thread: Optional[threading.Thread] = None
        
        # Components (lazy loaded)
        self._trading_engine = None
        self._dashboard_server = None
        self._tray_app = None
        self._state_manager = None
        
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
        
        logger.info(f"Initializing Polymarket Bot (headless={headless})")
        logger.info(f"App path: {PATHS['app']}")
        logger.info(f"Data path: {PATHS['data']}")
    
    @property
    def state_manager(self):
        """Get or create state manager."""
        if self._state_manager is None:
            from src.storage.state_manager import StateManager
            self._state_manager = StateManager(
                db_path=PATHS['data'] / 'state.db',
                state_dir=PATHS['data'] / 'state'
            )
        return self._state_manager
    
    @property
    def trading_engine(self):
        """Get or create trading engine."""
        if self._trading_engine is None:
            from src.trading.paper_trader import PaperTradingBot
            self._trading_engine = PaperTradingBot()
        return self._trading_engine
    
    @property
    def dashboard_server(self):
        """Get or create dashboard server."""
        if self._dashboard_server is None:
            from src.dashboard.server import DashboardServer
            self._dashboard_server = DashboardServer(
                trading_engine=self.trading_engine,
                host="127.0.0.1",
                port=8765
            )
        return self._dashboard_server
    
    def start_dashboard(self):
        """Start the web dashboard in background thread."""
        logger.info("Starting dashboard server...")
        self.dashboard_thread = self.dashboard_server.run(blocking=False)
        logger.info("Dashboard available at http://127.0.0.1:8765")
    
    def start_trading(self, interval_minutes: int = 15):
        """Start the trading engine in background thread."""
        logger.info(f"Starting trading engine (interval: {interval_minutes}m)...")
        
        def trading_loop():
            import time
            while self.running:
                try:
                    result = self.trading_engine.run_cycle()
                    logger.info(
                        f"Cycle complete: {result['opportunities_found']} opportunities, "
                        f"{result['positions_opened']} opened, "
                        f"{result['positions_closed']} closed"
                    )
                    
                    # Record metrics
                    summary = result['account_summary']
                    # self.state_manager.record_metrics(...)
                    
                except Exception as e:
                    logger.error(f"Trading cycle error: {e}", exc_info=True)
                
                # Sleep in small increments for faster shutdown
                for _ in range(interval_minutes * 60):
                    if not self.running:
                        break
                    time.sleep(1)
        
        self.trading_thread = threading.Thread(target=trading_loop, daemon=True)
        self.trading_thread.start()
    
    def start_tray(self):
        """Start system tray application (Windows only)."""
        if self.headless:
            return
        
        try:
            from src.gui.tray_app import TrayApplication
            self._tray_app = TrayApplication(
                on_start=self._on_tray_start,
                on_stop=self._on_tray_stop,
                on_dashboard=self._on_tray_dashboard,
                on_exit=self.shutdown,
            )
            self._tray_app.run()
        except ImportError as e:
            logger.warning(f"System tray not available: {e}")
            # Fall back to console mode
            self._run_console()
    
    def _on_tray_start(self):
        """Handle start trading from tray."""
        if not self.running:
            self.running = True
            self.start_trading()
    
    def _on_tray_stop(self):
        """Handle stop trading from tray."""
        self.running = False
    
    def _on_tray_dashboard(self):
        """Open dashboard in browser."""
        webbrowser.open("http://127.0.0.1:8765")
    
    def _run_console(self):
        """Run in console mode (for debugging or when tray unavailable)."""
        logger.info("Running in console mode. Press Ctrl+C to stop.")
        try:
            while self.running:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
    
    def run(self, start_trading: bool = True, start_dashboard: bool = True,
            minimized: bool = False):
        """
        Run the application.
        
        Args:
            start_trading: Automatically start trading engine
            start_dashboard: Start web dashboard
            minimized: Start minimized to tray
        """
        self.running = True
        
        try:
            # Start dashboard first
            if start_dashboard:
                self.start_dashboard()
            
            # Start trading if requested
            if start_trading:
                self.start_trading()
            
            # Start GUI or console
            if not self.headless:
                if not minimized:
                    # Open dashboard in browser on first run
                    import time
                    time.sleep(1)  # Wait for server to start
                    webbrowser.open("http://127.0.0.1:8765")
                
                self.start_tray()
            else:
                self._run_console()
                
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            self.shutdown()
            raise
    
    def shutdown(self):
        """Gracefully shutdown the application."""
        logger.info("Shutting down...")
        self.running = False
        
        # Wait for threads to finish
        if self.trading_thread and self.trading_thread.is_alive():
            self.trading_thread.join(timeout=5)
        
        # Save final state
        try:
            # self.state_manager.export_state_json()
            pass
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
        
        logger.info("Shutdown complete")
        sys.exit(0)


def run_as_service():
    """Run as Windows service."""
    try:
        from src.core.service import install_service
        install_service()
    except ImportError:
        logger.error("Windows service support not available")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Polymarket Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                     # Run with GUI (default)
  %(prog)s --minimized         # Start minimized to tray
  %(prog)s --headless          # Run without GUI (daemon mode)
  %(prog)s --no-trading        # Start dashboard only
  %(prog)s --debug             # Enable debug logging
  %(prog)s --service install   # Install as Windows service
        """
    )
    
    parser.add_argument('--minimized', action='store_true',
                        help='Start minimized to system tray')
    parser.add_argument('--headless', action='store_true',
                        help='Run without GUI (daemon mode)')
    parser.add_argument('--no-trading', action='store_true',
                        help='Do not start trading engine automatically')
    parser.add_argument('--no-dashboard', action='store_true',
                        help='Do not start web dashboard')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--service', choices=['install', 'remove', 'start', 'stop'],
                        help='Windows service management')
    parser.add_argument('--port', type=int, default=8765,
                        help='Dashboard port (default: 8765)')
    
    args = parser.parse_args()
    
    # Handle service commands
    if args.service:
        run_as_service()
        return
    
    # Multiprocessing freeze support for Windows
    if sys.platform == 'win32':
        import multiprocessing
        multiprocessing.freeze_support()
    
    # Create and run application
    app = PolymarketBotApp(
        headless=args.headless,
        debug=args.debug
    )
    
    try:
        app.run(
            start_trading=not args.no_trading,
            start_dashboard=not args.no_dashboard,
            minimized=args.minimized
        )
    except KeyboardInterrupt:
        app.shutdown()


if __name__ == '__main__':
    main()
