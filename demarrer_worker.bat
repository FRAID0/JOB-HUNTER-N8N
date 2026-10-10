@echo off
chcp 65001 > nul
echo =========================================================
echo    WORKER PLAYWRIGHT (FASTAPI) - ECOUTE DES CANDIDATURES
echo =========================================================
echo.
echo Le Worker tourne sur http://127.0.0.1:8000
echo Il attend les ordres de candidature depuis n8n...
echo.
.\venv\Scripts\python.exe worker_api.py
pause
