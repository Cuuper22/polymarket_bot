@echo off
title Polymarket Swing Trader Launcher
cd /d "%~dp0"
color 0B

echo.
echo  ============================================================
echo   POLYMARKET SWING TRADER V2 - LAUNCHER
echo  ============================================================
echo.
echo   Starting Paper Trader and Live Dashboard...
echo.

REM Start Paper Trader in a new window
start "Swing Trader V2" cmd /k "cd /d %~dp0 && color 0A && python paper_trader_v2.py --interval 5"

REM Wait for trader to initialize
echo   Waiting for trader to initialize...
timeout /t 5 /nobreak >nul

REM Start Dashboard in a new window
start "Live Dashboard" cmd /k "cd /d %~dp0 && color 0E && python dashboard.py --refresh 5"

echo.
echo  ============================================================
echo   Two windows are now running:
echo.
echo   1. Swing Trader V2 (Green) - Running the trading bot
echo   2. Live Dashboard (Yellow) - Showing real-time stats
echo.
echo   You can close this launcher window.
echo   Keep the other two windows open for trading to continue!
echo  ============================================================
echo.
pause
