#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Worker Playwright pour n8n
Auteur: Open Source Contributor
Description: Reçoit l'ordre de candidature depuis n8n (clic Telegram),
ouvre Chromium, pré-remplit les champs et le CV, et renvoie le statut.
"""

import os
import json
import time
import hmac
import ipaddress
import socket
import urllib.parse
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
PROFIL_PATH = BASE_DIR / "profil.json"
DOCS_DIR = BASE_DIR / "documents"
SCREENSHOTS_DIR = DOCS_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Playwright Application Copilot API",
    description="Worker local pour l'automatisation des candidatures piloté par n8n",
    version="1.0.0"
)

class ApplicationRequest(BaseModel):
    url: str
    company_name: Optional[str] = "Entreprise"
    job_title: Optional[str] = "Poste"
    cover_letter: Optional[str] = None
    headless: Optional[bool] = False  # False par défaut sur PC pour voir le navigateur

def validate_target_url(url):
    """Autorise uniquement des URLs HTTPS publiques destinées à des offres d'emploi."""
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.hostname or parsed_url.username or parsed_url.password:
        raise HTTPException(status_code=400, detail="Only public HTTPS URLs are accepted")

    try:
        resolved_addresses = {
            address[4][0]
            for address in socket.getaddrinfo(parsed_url.hostname, 443, type=socket.SOCK_STREAM)
        }
        if not resolved_addresses or any(
            ipaddress.ip_address(address).is_private
            or ipaddress.ip_address(address).is_loopback
            or ipaddress.ip_address(address).is_link_local
            or ipaddress.ip_address(address).is_reserved
            or ipaddress.ip_address(address).is_multicast
            or ipaddress.ip_address(address).is_unspecified
            for address in resolved_addresses
        ):
            raise HTTPException(status_code=400, detail="Private or local destinations are not accepted")
    except socket.gaierror as error:
        raise HTTPException(status_code=400, detail="Target hostname cannot be resolved") from error

def require_worker_token(provided_token):
    expected_token = os.environ.get("WORKER_API_TOKEN", "").strip()
    if not expected_token:
        raise HTTPException(status_code=503, detail="Worker API authentication is not configured")
    if not provided_token or not hmac.compare_digest(provided_token, expected_token):
        raise HTTPException(status_code=401, detail="Invalid worker API token")

from copilot_apply import smart_fill, load_profile

def run_playwright_job(req: ApplicationRequest):
    profile = load_profile()

    print(f"\n[WORKER] Démarrage de la candidature : {req.job_title} chez {req.company_name}")
    print(f"[WORKER] URL cible : {req.url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=req.headless,
            slow_mo=50,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 850},
            locale="de-DE"
        )
        page = context.new_page()

        try:
            page.goto(req.url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)

            # Exécution du moteur unifié smart_fill (Fast-Path + Agent Engine + Redirection)
            agent_res = smart_fill(
                page=page,
                profile=profile,
                cover_letter_text=req.cover_letter,
                job_title=req.job_title
            )

            active_page = getattr(agent_res, "active_page", None) or page

            # Capture d'écran de preuve
            screenshot_file = SCREENSHOTS_DIR / f"app_{int(time.time())}.png"
            try:
                active_page.screenshot(path=str(screenshot_file), full_page=False)
            except Exception:
                page.screenshot(path=str(screenshot_file), full_page=False)
            print(f"[WORKER] Capture enregistrée : {screenshot_file.name}")

            # En mode PC (non-headless), on laisse 60 secondes pour vérifier et cliquer
            if not req.headless:
                print("[WORKER] Navigateur ouvert. L'utilisateur peut vérifier et cliquer sur le bouton final...")
                time.sleep(60)

        except Exception as e:
            print(f"[WORKER ERREUR] {e}")
        finally:
            browser.close()
            print("[WORKER] Session terminée proprement.")

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "Playwright Application Copilot",
        "candidate": "Candidate"
    }

@app.post("/apply")
def trigger_application(
    req: ApplicationRequest,
    background_tasks: BackgroundTasks,
    x_worker_token: Optional[str] = Header(default=None),
):
    require_worker_token(x_worker_token)
    validate_target_url(req.url)
    background_tasks.add_task(run_playwright_job, req)
    return {
        "status": "QUEUED",
        "message": f"Candidature initiée pour {req.job_title} chez {req.company_name}",
        "url": req.url
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Lancement du Worker API Playwright sur http://127.0.0.1:8000 ...")
    uvicorn.run("worker_api:app", host="127.0.0.1", port=8000, reload=False)
