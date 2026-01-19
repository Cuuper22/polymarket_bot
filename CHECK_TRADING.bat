@echo off
cd /d "%~dp0"
echo.
echo Checking paper trading status...
echo.
python paper_trade_runner.py --status
echo.
pause
