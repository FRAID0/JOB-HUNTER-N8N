@echo off
chcp 65001 > nul
echo ======================================================
echo    COPILOTE PLAYWRIGHT - CANDIDATURES AUTOMATISEES
echo ======================================================
echo.
set /p JOB_URL="Entrez l'URL de l'offre d'emploi : "
if "%JOB_URL%"=="" (
    echo [ERREUR] Aucune URL saisie.
    pause
    exit /b
)

.\venv\Scripts\python.exe copilot_apply.py "%JOB_URL%"
pause
