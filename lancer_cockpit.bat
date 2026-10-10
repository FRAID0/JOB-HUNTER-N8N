@echo off
chcp 65001 > nul
title Cockpit Telegram Playwright - Wilfried Manfouo Fomekong
echo =================================================================
echo    COCKPIT TELEGRAM PLAYWRIGHT (100% AUTOMATIQUE)
echo =================================================================
echo.
echo Ce programme tourne en arriere-plan et ecoute votre Telegram.
echo Demarrage du bot...
echo.
.\venv\Scripts\python.exe -u telegram_cockpit.py
pause
