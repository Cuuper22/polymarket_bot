@echo off
title Polymarket Paper Trader - Live Trading
cd /d "%~dp0"

echo ============================================================
echo   POLYMARKET PAPER TRADER
echo   Edge-Aware Strategy - Live Market Data
echo ============================================================
echo.
echo Starting at: %date% %time%
echo Capital: $75
echo Interval: 15 minutes
echo.
echo This window will stay open. Close it to stop trading.
echo ============================================================
echo.

python paper_trade_runner.py --capital 75 --interval 15

echo.
echo Trading stopped at: %date% %time%
pause
