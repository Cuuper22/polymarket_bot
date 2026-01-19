@echo off
title Polymarket Paper Trader - LIVE
cd /d "%~dp0"
color 0A

echo.
echo  ============================================================
echo   POLYMARKET PAPER TRADER - LIVE TRADING
echo  ============================================================
echo.
echo   Capital: $75     Strategy: Edge-Aware
echo   Interval: 15 minutes
echo.
echo   KEEP THIS WINDOW OPEN for trading to continue!
echo   Press Ctrl+C to stop.
echo.
echo  ============================================================
echo.
echo  Starting at %date% %time%
echo.

python paper_trade_runner.py --capital 75 --interval 15

echo.
echo  ============================================================
echo  Trading stopped at %date% %time%
echo  ============================================================
pause
