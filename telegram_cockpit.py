#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cockpit Telegram Universel (100% Automatique & Multimodal)
Auteur: Wilfried Manfouo Fomekong
Description:
1. Reçoit et traite TOUS les types d'entrées depuis Telegram :
   - Un LIEN (URL) direct vers une offre (Greenhouse, Lever, LinkedIn, Indeed, etc.)
   - Une PHOTO / CAPTURE D'ÉCRAN d'une offre d'emploi (Cerveau IA Multimodal)
   - Un TEXTE COMPLET copié-collé d'une offre
2. Rédige un Anschreiben allemand d'excellence DIN 5008 sur-mesure et le compile en PDF.
3. Envoie le PDF de la lettre sur Telegram pour validation visuelle.
4. Lance Chromium Playwright en plein écran sur le PC pour pré-remplir la candidature,
   téléverser cv.pdf et anschreiben.pdf, et inspecter visuellement le résultat avec l'IA.
"""

import os
import sys
import json
import time
import re
import threading
import urllib.request
import urllib.parse
import socket
from pathlib import Path

_LOCK_SOCKET = None
def acquire_single_instance_lock():
    global _LOCK_SOCKET
    _LOCK_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _LOCK_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _LOCK_SOCKET.bind(("127.0.0.1", 58941))
    except OSError:
        print("⚠️ [AVERTISSEMENT] Une instance du Cockpit Telegram est déjà active sur cette machine.", flush=True)
        print("💡 Pour éviter les conflits (erreur 409 Conflict), cette nouvelle tentative s'arrête proprement.", flush=True)
        sys.exit(0)


# Importer le moteur Playwright, le générateur de PDF DIN 5008, le Superviseur Visuel IA et la clé Gemini
from copilot_apply import (
    load_profile,
    smart_fill,
    handle_cloudflare_challenge,
    generate_anschreiben_pdf,
    visual_qa_critique,
    get_gemini_api_key,
    query_gemini,
    DOCS_DIR
)
from playwright.sync_api import sync_playwright

# Forcer l'encodage UTF-8 et le flush en temps réel des logs en console Windows
if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
if sys.stderr:
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
PROFIL_PATH = BASE_DIR / "profil.json"
SCREENSHOTS_DIR = DOCS_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Caches d'état en mémoire
URL_CACHE = {}
LAST_PENDING_JOB = {}

# Clavier tactile persistant Telegram (toujours affiché sur le smartphone)
TACTILE_KEYBOARD = {
    "keyboard": [
        [{"text": "📋 Formats acceptés"}, {"text": "👤 Mon Profil & CV"}],
        [{"text": "🟢 Statut du Cockpit"}, {"text": "ℹ️ Aide"}]
    ],
    "resize_keyboard": True,
    "persistent": True
}

def get_telegram_token():
    # 1. Vérifier dans profil.json (priorité absolue)
    if PROFIL_PATH.exists():
        try:
            with open(PROFIL_PATH, "r", encoding="utf-8") as f:
                p = json.load(f)
                token = p.get("telegram", {}).get("bot_token", "").strip()
                if token:
                    return token
        except Exception:
            pass

    # 2. Vérifier le fichier .env
    if ENV_PATH.exists():
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass

    # 3. Variable d'environnement système
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token.strip()

    print("[ERREUR CRITIQUE] Aucun token Telegram trouvé dans profil.json ou .env.", flush=True)
    sys.exit(1)

def telegram_api(token, method, data=None):
    """Appel direct à l'API Telegram en HTTPS sortant."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        if data:
            json_data = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=json_data, headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=35) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"[TELEGRAM API INFO] {method}: {e}", flush=True)
        return None

def answer_callback(token, callback_id, text):
    telegram_api(token, "answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": False
    })

def send_telegram_message(token, chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return telegram_api(token, "sendMessage", payload)

def send_telegram_photo(token, chat_id, photo_path, caption):
    """Envoie une capture d'écran de preuve vers Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        with open(photo_path, "rb") as f:
            file_data = f.read()

        body = bytearray()
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode("utf-8"))
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode("utf-8"))
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{Path(photo_path).name}\"\r\nContent-Type: image/png\r\n\r\n".encode("utf-8"))
        body.extend(file_data)
        body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        urllib.request.urlopen(req, timeout=35)
        print("  ✓ Capture envoyée sur ton Telegram avec succès !", flush=True)
    except Exception as e:
        print(f"[ERREUR ENVOI PHOTO] {e}", flush=True)

def download_telegram_file(token, file_id, dest_path):
    """Télécharge un fichier (photo ou document) envoyé sur Telegram."""
    res = telegram_api(token, "getFile", {"file_id": file_id})
    if res and res.get("ok"):
        file_path = res["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        req = urllib.request.Request(download_url)
        with urllib.request.urlopen(req, timeout=40) as r, open(dest_path, "wb") as f:
            f.write(r.read())
        return dest_path
    return None

def send_telegram_document(token, chat_id, doc_path, caption):
    """Envoie un document (ex: PDF Anschreiben) vers Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        with open(doc_path, "rb") as f:
            file_data = f.read()

        body = bytearray()
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode("utf-8"))
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode("utf-8"))
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{Path(doc_path).name}\"\r\nContent-Type: application/pdf\r\n\r\n".encode("utf-8"))
        body.extend(file_data)
        body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        urllib.request.urlopen(req, timeout=35)
        print("  ✓ Document PDF envoyé sur ton Telegram avec succès !", flush=True)
    except Exception as e:
        print(f"[ERREUR ENVOI DOCUMENT] {e}", flush=True)

def extract_text_from_url(url):
    """
    Extrait le contenu textuel d'une offre d'emploi depuis son URL.
    1. Tente un HTTP GET rapide avec parsing regex.
    2. Si le contenu est insuffisant (site dynamique React/Vue/SPA), utilise Playwright headless.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as res:
            html = res.read().decode("utf-8", errors="ignore")
            clean = re.sub(r'<script.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
            clean = re.sub(r'<style.*?</style>', ' ', clean, flags=re.DOTALL | re.IGNORECASE)
            clean = re.sub(r'<nav.*?</nav>', ' ', clean, flags=re.DOTALL | re.IGNORECASE)
            clean = re.sub(r'<footer.*?</footer>', ' ', clean, flags=re.DOTALL | re.IGNORECASE)
            clean = re.sub(r'<[^>]+>', ' ', clean)
            clean = ' '.join(clean.split())
            bot_markers = ["bot-schutz", "cloudflare", "verify you are human", "attention required", "just a moment", "turnstile"]
            if any(b in clean.lower() for b in bot_markers):
                print("⚠️ [EXTRACTION HTTP] Contenu bloqué par anti-bot Cloudflare/Jobvector. Ignoré.", flush=True)
            elif len(clean) > 250:
                return clean[:7000]
    except Exception as e:
        print(f"ℹ️ [EXTRACTION HTTP INFO] {e}", flush=True)

    # Secours Playwright headless pour sites rendus en JavaScript
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=25000, wait_until="domcontentloaded")
            time.sleep(2)
            body_text = page.inner_text("body")
            browser.close()
            if body_text and len(body_text.strip()) > 250:
                clean_text = ' '.join(body_text.split())
                bot_markers = ["bot-schutz", "cloudflare", "verify you are human", "attention required", "just a moment", "turnstile"]
                if any(b in clean_text.lower() for b in bot_markers):
                    print("⚠️ [EXTRACTION PLAYWRIGHT] Page de captcha / bot-schutz détectée. Ignoré.", flush=True)
                    return None
                return clean_text[:7000]
    except Exception as e:
        print(f"ℹ️ [EXTRACTION PLAYWRIGHT INFO] {e}", flush=True)

    return None

def analyze_job_with_gemini(text_content=None, image_path=None, profile=None):
    """
    Analyse universelle d'une offre d'emploi (texte ou photo) avec Gemini 3 Flash.
    Extrait l'entreprise, le poste, l'URL de candidature, et rédige un Anschreiben allemand DIN 5008.
    """
    import base64

    key = get_gemini_api_key()
    if not key:
        return {}

    prof = load_profile()
    p_info = prof.get("personal_info", prof)
    c_name = p_info.get("full_name", "Wilfried Manfouo Fomekong")
    c_phone = p_info.get("phone", "+49 170 0000000")
    c_email = p_info.get("email", "wfomekong0@gmail.com")
    addr = p_info.get("address", {})
    c_addr_str = f"{addr.get('street', '')}, {addr.get('postal_code', '')} {addr.get('city', '')}".strip(", ")

    prompt = f"""Du bist ein erstklassiger deutscher Karriereberater und Senior IT-Headhunter.
Analysiere folgende Stellenausschreibung für {c_name} und erstelle ein überzeugendes deutsches Anschreiben (DIN 5008 Standard):

MASTER-PROFIL DES BEWERBERS (REALE PROJEKTE & KOMPETENZEN):
- Name: {c_name}
- Kontakt: {c_phone} | {c_email} | {c_addr_str}
- Online-Portfolio: https://portfolio-pro-fraid.vercel.app/de | GitHub: https://github.com/FRAID0
- Studium: B.Sc. Angewandte Informatik an der Hochschule Worms (abschlussnah).
- Sprachen: Deutsch (verhandlungssicher / C1, TestDaF 4), Französisch (Muttersprache), Englisch (fließend im technischen Umfeld).

TECH-STACK & PROJEKT-NACHWEISE:
1. Backend & Web-APIs:
   - TypeScript / JavaScript: Modulare APIs und Web-Plattformen mit NestJS, Node.js, Express und PostgreSQL.
   - Python: RESTful APIs mit FastAPI, Flask, Daten-Pipelines.
2. Frontend: React, Angular, Tailwind CSS, reaktive Benutzeroberflächen.
3. Data & Streaming: Apache Kafka, QuestDB, PostgreSQL, SQLite, MQTT (Industrieprojekt in Kooperation mit Bosch für Telemetrie-Echtzeitdaten).
4. DevOps & Cloud:
   - CI/CD & Automatisierung bei der PWO AG: Azure DevOps, Python, SCADA, relationale SQL-Datenstrukturen.
   - Containerisierung mit Docker & Docker Compose: In universitären IIoT-Projekten (z. B. TOP-Projekt, Telemetrie-Architektur) sowie Web-Plattform-Deployments.
5. Arbeitsweise: Agile Methoden, Clean Code, Type Safety, moderne KI-gestützte Entwicklungs-Workflows als Produktivitäts- und Qualitätshebel.

STRIKTE REGELN FÜR DAS ANSCHREIBEN:
1. KEINE DEFENSIVE SPRACHE ODER ENTSCHULDIGUNGEN:
   - Verwende NIEMALS Phrasen wie "Obwohl mein bisheriger Schwerpunkt...", "Auch wenn ich noch lernen muss...", "Trotz fehlender Erfahrung...".
   - Präsentiere TypeScript/NestJS, Python, Fullstack-Architekturen und DevOps als bereits erprobte, fundierte Kernkompetenzen! Der Ton muss selbstbewusst, lösungsorientiert und professionell sein.
2. ECHTE FULLSTACK-EXPERTISE VERKNÜPFEN (Match & Anchor):
   - Verbinde Backend- und Datenkompetenzen (FastAPI/Python, Kafka, PostgreSQL) logisch mit modernen TypeScript/NestJS-Architekturen und Frontend (React/Tailwind).
   - Verankere jede Kernanforderung der Stellenanzeige in einem realen Projekt (PWO AG, Bosch-Projekt, Portfolio-Webplattformen).
3. PFLICHT-REFERENZ AUF DAS PORTFOLIO:
   - Binde den Link zum Online-Portfolio (https://portfolio-pro-fraid.vercel.app/de) zwingend und natürlich im 2. Absatz ein (z. B.: "Einen detaillierten Einblick in meine bisherigen Architekturen und Projekte finden Sie auf meiner Portfolio-Website unter https://portfolio-pro-fraid.vercel.app/de").
4. AUFBAU & FORM:
   - 3 bis 4 prägnante Absätze, Anrede "Sehr geehrte Damen und Herren" (oder Name falls bekannt), klare Betreffzeile ("Bewerbung als [job_title]"), Abschluss mit "Mit freundlichen Grüßen".
5. STRIKTE TRENNUNG DER PROJEKTE (KEINE FALSCHEN ZUORDNUNGEN):
   - Bosch-Kooperation: Praxisnahes Hochschulprojekt der Hochschule Worms in Kooperation mit der Bosch-Gruppe (Echtzeit-Telemetriedaten mit FastAPI, Apache Kafka und QuestDB). Betone: Es war ein praxisnahes Studienprojekt in Kooperation mit Bosch, keine direkte Festanstellung!
   - PWO AG: Praktikum & Bachelorarbeit (Prozessautomatisierung, relationale SQL-Datenstrukturen, SCADA-Systeme und CI/CD-Pipelines mit Azure DevOps, YAML und Python). Erwähne NIEMALS Kafka und NIEMALS Docker bei der PWO AG!
   - TOP-Projekt (Hochschule Worms): Cloud-Webanwendung zur Workshop-Verwaltung mit Node.js, Express, PostgreSQL, Sequelize und Deployment auf AWS EC2.
   - Containerisierung mit Docker & Docker Compose: In universitären IIoT-Projekten (z. B. TOP-Projekt), Microservices und Web-Plattform-Deployments.
   - TypeScript / NestJS / React: Web-Plattformen und modulare APIs im Portfolio (https://portfolio-pro-fraid.vercel.app/de).

AUFGABEN:
1. Extrahiere den Unternehmensnamen (company_name), die genaue Stellenbezeichnung (job_title) und die Bewerbungs-URL (apply_url) falls sichtbar.
2. Ermittle einen strategischen Match-Score (score: 1-100) und eine prägnante Begründung (begruendung).
3. Verfasse das Anschreiben gemäß den oben genannten strikten Regeln.

Antworte STRENG als valides JSON-Objekt in diesem Format:
{{
  "company_name": "...",
  "job_title": "...",
  "apply_url": "...",
  "score": 85,
  "begruendung": "...",
  "anschreiben": "Sehr geehrte Damen und Herren,\\n\\n..."
}}
"""

    parts = [{"text": prompt}]
    if text_content:
        parts.append({"text": f"Stellenanzeigen-Inhalt:\n{text_content}"})

    if image_path and Path(image_path).exists():
        with open(image_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")
        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": b64_img
            }
        })

    payload = {"contents": [{"parts": parts}]}
    try:
        raw = query_gemini(payload, key, timeout=35)
        if raw:
            try:
                return json.loads(raw, strict=False)
            except Exception:
                data = {}
                co_m = re.search(r'"company_name"\s*:\s*"([^"]+)"', raw)
                if co_m: data["company_name"] = co_m.group(1)
                jt_m = re.search(r'"job_title"\s*:\s*"([^"]+)"', raw)
                if jt_m: data["job_title"] = jt_m.group(1)
                sc_m = re.search(r'"score"\s*:\s*(\d+)', raw)
                if sc_m: data["score"] = int(sc_m.group(1))
                bg_m = re.search(r'"begruendung"\s*:\s*"([^"]+)"', raw)
                if bg_m: data["begruendung"] = bg_m.group(1)
                ans_m = re.search(r'"anschreiben"\s*:\s*"(.*?)"\s*(?:}|\n})', raw, flags=re.DOTALL)
                if ans_m:
                    data["anschreiben"] = ans_m.group(1).replace("\\n", "\n")
                return data
        return {}
    except Exception as e:
        print(f"⚠️ [ERREUR ANALYSE GEMINI] {e}", flush=True)
        return {}

def execute_playwright_application(url, token, chat_id, job_title="Offre d'emploi", company_name="Unternehmen", cover_letter_text=None):
    profile = load_profile()
    print("\n" + "=" * 60, flush=True)
    print(f"🚀 [PLAYWRIGHT] Démarrage automatique pour : {job_title}", flush=True)
    print(f"🏢 Entreprise : {company_name}", flush=True)
    print(f"🔗 URL : {url}", flush=True)
    print("=" * 60, flush=True)

    # 1. Générer ou compiler l'Anschreiben DIN 5008 et l'envoyer sur Telegram
    if not cover_letter_text and url:
        try:
            print("📝 Génération automatique de l'Anschreiben DIN 5008...", flush=True)
            res_analysis = analyze_job_with_gemini(
                text_content=f"Stelle: {job_title} bei {company_name}. URL: {url}",
                profile=profile
            )
            cover_letter_text = res_analysis.get("anschreiben")
        except Exception as err:
            print(f"⚠️ [AVERTISSEMENT] Erreur analyse lettre : {err}", flush=True)

    if cover_letter_text:
        try:
            generate_anschreiben_pdf(cover_letter_text, job_title, company_name)
            anschreiben_pdf = DOCS_DIR / "anschreiben.pdf"
            if anschreiben_pdf.exists():
                send_telegram_document(
                    token, chat_id, anschreiben_pdf,
                    caption=f"📄 Ton Anschreiben DIN 5008 pour {job_title} chez {company_name}"
                )
        except Exception as err:
            print(f"⚠️ [AVERTISSEMENT] Erreur lors de la génération / envoi du PDF Anschreiben : {err}", flush=True)

    browser_profile_dir = BASE_DIR / "browser_profile"
    browser_profile_dir.mkdir(parents=True, exist_ok=True)

    # 2. Nettoyer les fichiers de verrouillage résiduels Chrome
    for lock_name in ["lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"]:
        for p_target in [browser_profile_dir / lock_name, browser_profile_dir / "Default" / lock_name]:
            if p_target.exists():
                try:
                    p_target.unlink()
                except Exception:
                    pass

    with sync_playwright() as p:
        context = None
        browser_fallback = None

        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(browser_profile_dir.resolve()),
                headless=False,
                slow_mo=50,
                no_viewport=True,
                locale="de-DE",
                args=[
                    "--start-maximized",
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
        except Exception as ctx_err:
            print(f"⚠️ [PLAYWRIGHT] Profil Chrome verrouillé ({ctx_err}). Bascule automatique en session isolée...", flush=True)
            browser_fallback = p.chromium.launch(
                headless=False,
                slow_mo=50,
                args=[
                    "--start-maximized",
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            context = browser_fallback.new_context(
                viewport={"width": 1366, "height": 850},
                locale="de-DE"
            )

        try:
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        except Exception:
            pass

        page = context.pages[0] if context.pages else context.new_page()

        try:
            print("🌐 Chargement de la page dans Chromium...", flush=True)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.bring_to_front()
            time.sleep(2)

            # Résolution automatique du défi Cloudflare Turnstile si présent
            handle_cloudflare_challenge(page)

            # ─────────────────────────────────────────────────────────────────
            # 🤖 MOTEUR AGENTIQUE : navigation agrégateur + remplissage formulaire
            # smart_fill gère : résolution agrégateur (Arbeitnow→Personio),
            # clic sur 'Auf diese Stelle bewerben', indexation DOM, FastPath,
            # LLM Gemini, upload CV, et s'arrête avant le bouton 'Envoyer'.
            # ─────────────────────────────────────────────────────────────────
            print("🤖 [AGENT] Lancement du moteur de remplissage automatique...", flush=True)
            active_page = page  # sera mis à jour si l'agent navigue vers un autre onglet

            def on_human_gate(screenshot_p, reason):
                """Callback appelé quand l'agent atteint le Human Gate (avant soumission)."""
                print(f"🛑 [HUMAN GATE] {reason}", flush=True)

            try:
                agent_result = smart_fill(
                    page=page,
                    profile=profile,
                    cover_letter_text=cover_letter_text,
                    job_title=job_title,
                    on_human_gate_callback=on_human_gate,
                )
                # Récupérer la page active après navigation éventuelle de l'agent
                if agent_result and hasattr(agent_result, 'active_page') and agent_result.active_page:
                    active_page = agent_result.active_page
                else:
                    # Prendre le dernier onglet actif
                    if context and context.pages:
                        active_page = context.pages[-1]
                print(f"✅ [AGENT] Moteur terminé. Pages actives : {len(context.pages) if context else 1}", flush=True)
            except Exception as agent_err:
                print(f"⚠️ [AGENT] Erreur moteur (page reste ouverte) : {agent_err}", flush=True)
                active_page = context.pages[-1] if (context and context.pages) else page

            # ─────────────────────────────────────────────────────────────────
            # 📸 Capture de preuve APRÈS remplissage (pas avant)
            # ─────────────────────────────────────────────────────────────────
            # Scroller sur le formulaire pour que la capture montre les champs remplis
            try:
                active_page.evaluate(
                    """() => {
                        const form = document.querySelector(
                            'form, #apply, .application-form, [data-qa="application-form"]'
                        );
                        if (form) form.scrollIntoView({behavior: 'instant'});
                    }"""
                )
                time.sleep(0.5)
            except Exception:
                pass

            screenshot_path = SCREENSHOTS_DIR / f"candidature_{int(time.time())}.png"
            try:
                active_page.screenshot(path=str(screenshot_path))
            except Exception:
                try:
                    page.screenshot(path=str(screenshot_path))
                except Exception:
                    pass
            print(f"📸 Capture d'écran enregistrée : {screenshot_path.name}", flush=True)

            # Comptage objectif des champs réellement remplis
            try:
                filled_count = active_page.evaluate("""
                    () => {
                        const inputs = Array.from(
                            document.querySelectorAll('input:not([type="hidden"]), textarea')
                        );
                        return inputs.filter(
                            i => (i.value && i.value.trim().length > 0) || (i.files && i.files.length > 0)
                        ).length;
                    }
                """)
            except Exception:
                filled_count = 0

            # 👁️ Superviseur Qualité Multimodal
            qa = visual_qa_critique(screenshot_path, profile, job_title)
            verdict = qa.get("verdict", "Vérification effectuée.")

            # Envoi du statut honnête et vérifié sur Telegram
            if filled_count >= 3:
                caption = (
                    f"✅ **Formulaire pré-rempli avec succès** ({filled_count} champs complétés) !\n"
                    f"🏢 **{job_title}** chez **{company_name}**\n"
                    f"📄 CV & coordonnées attachés au formulaire.\n"
                    f"👀 Regarde ton écran : tout est prêt, tu n'as plus qu'à cliquer sur 'Envoyer' !"
                )
            else:
                caption = (
                    f"⚠️ **Formulaire non encore rempli** ({filled_count} champ détecté)\n"
                    f"🏢 **{job_title}** ({company_name})\n"
                    f"👁️ Diagnostic IA : {verdict}\n"
                    f"👀 La page reste ouverte sur ton écran — clique toi-même sur le bouton 'Bewerben'."
                )

            send_telegram_photo(token, chat_id, screenshot_path, caption)

            print("\n" + "*" * 60, flush=True)
            print("🛡️ [CONTRÔLE HUMAIN ACTIF] La fenêtre Chromium est ouverte devant vous !", flush=True)
            print("👉 Vérifiez les champs et cliquez sur 'Postuler / Envoyer' !", flush=True)
            print("💡 La fenêtre reste ouverte. Vous pouvez la fermer dès que vous avez terminé.", flush=True)
            print("*" * 60 + "\n", flush=True)

            # Reste ouvert tant que l'utilisateur n'a pas fermé la fenêtre (max 10 minutes)
            start_time = time.time()
            while time.time() - start_time < 600:
                try:
                    pages_list = context.pages if context else []
                    all_closed = all(p.is_closed() for p in pages_list) if pages_list else active_page.is_closed()
                    if all_closed:
                        print("Fermeture de la fenêtre détectée par l'utilisateur.", flush=True)
                        break
                    time.sleep(1)
                except Exception:
                    break

        except Exception as e:
            print(f"[ERREUR PLAYWRIGHT] {e}", flush=True)
            send_telegram_message(token, chat_id, f"⚠️ Note : {e}\n👀 La fenêtre Chromium reste ouverte sur votre écran pour finaliser la candidature.")
            # Laisser la fenêtre ouverte pour Wilfried même après une exception
            start_time = time.time()
            while time.time() - start_time < 600:
                try:
                    all_closed = all(p.is_closed() for p in context.pages) if (context and context.pages) else (page.is_closed())
                    if all_closed:
                        print("Fermeture de la fenêtre détectée par l'utilisateur.", flush=True)
                        break
                    time.sleep(1)
                except Exception:
                    break
        finally:
            try:
                if context:
                    context.close()
                if browser_fallback:
                    browser_fallback.close()
            except Exception:
                pass
            print("🔒 Session Playwright terminée. En attente du prochain ordre...", flush=True)

def start_cockpit():
    acquire_single_instance_lock()
    global LAST_PENDING_JOB
    token = get_telegram_token()
    profile = load_profile()
    candidate_name = profile["personal_info"]["full_name"]

    # Nettoyer d'éventuels webhooks résiduels
    telegram_api(token, "deleteWebhook", {"drop_pending_updates": False})

    # Configurer le menu officiel Telegram
    telegram_api(token, "setMyCommands", {
        "commands": [
            {"command": "start", "description": "Afficher l'accueil et les boutons"},
            {"command": "status", "description": "État du Cockpit et connexion PC"},
            {"command": "profil", "description": "Profil candidat et documents"},
            {"command": "help", "description": "Guide d'utilisation"}
        ]
    })

    # Test de connexion Telegram
    bot_info = telegram_api(token, "getMe")
    if not bot_info or not bot_info.get("ok"):
        print("[ERREUR CRITIQUE] Impossible de se connecter avec ce token Telegram.", flush=True)
        sys.exit(1)

    bot_name = bot_info["result"]["first_name"]

    print("=" * 65, flush=True)
    print("🤖 COCKPIT TELEGRAM UNIVERSEL (100% ACTIF)", flush=True)
    print(f"👤 Candidat    : {candidate_name}", flush=True)
    print(f"🤖 Bot connecte: @{bot_info['result'].get('username')} ({bot_name})", flush=True)
    print("🎯 Formats acceptés en direct :", flush=True)
    print("   1. 🔗 Liens / URLs d'offres", flush=True)
    print("   2. 📸 Photos & Captures d'écran d'offres", flush=True)
    print("   3. 📝 Textes complets d'offres copiés-collés", flush=True)
    print("   4. 🚀 Clics sur les boutons [POSTULER]", flush=True)
    print("=" * 65, flush=True)

    offset = 0
    processed_clicks = {}

    while True:
        try:
            # Demander explicitement messages ET callback_query pour ne rien manquer
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=25&allowed_updates=%5B%22message%22%2C%22callback_query%22%5D"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=35) as res:
                data = json.loads(res.read().decode("utf-8"))

            if not data.get("ok"):
                time.sleep(2)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                # ==========================================================
                # A. CLIC SUR UN BOUTON TELEGRAM (CALLBACK QUERY)
                # ==========================================================
                if "callback_query" in update:
                    cq = update["callback_query"]
                    cq_id = cq["id"]
                    cq_data = cq.get("data", "")
                    from_user = cq["from"]
                    chat_id = cq["message"]["chat"]["id"]
                    msg = cq["message"]

                    now = time.time()
                    if cq_data in processed_clicks and (now - processed_clicks[cq_data]) < 45:
                        answer_callback(token, cq_id, "⏳ Traitement déjà en cours sur ton PC !")
                        continue
                    processed_clicks[cq_data] = now

                    print(f"\n📩 [TELEGRAM] Bouton cliqué par {from_user.get('first_name')} : {cq_data}", flush=True)

                    is_apply = cq_data.startswith("apply:") or cq_data.startswith("apply_")
                    is_ignore = cq_data.startswith("ignore:") or cq_data.startswith("ignore_")

                    if is_apply:
                        answer_callback(token, cq_id, "🚀 Ordre reçu ! Playwright démarre...")

                        # 1. Extraire titre et entreprise
                        job_title = "Offre d'emploi"
                        company_name = "Unternehmen"
                        msg_text = msg.get("text", "")
                        for line in msg_text.splitlines():
                            clean = line.replace("*", "").strip()
                            if "Poste" in clean or "poste" in clean:
                                job_title = clean.replace("📌", "").replace("Poste :", "").replace("Poste:", "").strip()
                            elif "Entreprise" in clean or "entreprise" in clean:
                                company_name = clean.replace("🏢", "").replace("Entreprise :", "").replace("Entreprise:", "").strip()

                        # 2. Extraire la lettre de motivation si présente
                        cover_letter_text = None
                        if "--- ANSCHREIBEN ---" in msg_text:
                            cover_letter_text = msg_text.split("--- ANSCHREIBEN ---", 1)[1].strip()
                        elif "Lettre de motivation :" in msg_text:
                            cover_letter_text = msg_text.split("Lettre de motivation :", 1)[1].strip()
                        elif "Anschreiben :" in msg_text:
                            cover_letter_text = msg_text.split("Anschreiben :", 1)[1].strip()
                        elif "Sehr geehrte" in msg_text:
                            cover_letter_text = "Sehr geehrte" + msg_text.split("Sehr geehrte", 1)[1]

                        # Utiliser le cache si disponible
                        if not cover_letter_text and LAST_PENDING_JOB.get("anschreiben"):
                            cover_letter_text = LAST_PENDING_JOB["anschreiben"]
                            if LAST_PENDING_JOB.get("job_title"):
                                job_title = LAST_PENDING_JOB["job_title"]
                            if LAST_PENDING_JOB.get("company_name"):
                                company_name = LAST_PENDING_JOB["company_name"]

                        # 3. Résoudre l'URL cible
                        target_url = None
                        try:
                            # Décodage du slug dans callback_data
                            slug = cq_data
                            for prefix in ["apply:", "apply_"]:
                                if slug.startswith(prefix):
                                    slug = slug[len(prefix):]
                            slug = slug.strip()

                            if slug in URL_CACHE:
                                target_url = URL_CACHE[slug]
                            elif slug.startswith("http"):
                                target_url = slug
                            elif slug and "arbeitnow" not in slug and "/" not in slug:
                                target_url = f"https://www.arbeitnow.com/view/{slug}"

                            # Boutons de message
                            if not target_url:
                                rows = msg.get("reply_markup", {}).get("inline_keyboard", [])
                                for row in rows:
                                    for btn in row:
                                        btn_text = btn.get("text", "").upper()
                                        btn_url = btn.get("url")
                                        if btn_url and btn_url.startswith("http") and "PORTFOLIO" not in btn_text:
                                            target_url = btn_url
                                            break
                                    if target_url:
                                        break

                            # Entités du message
                            if not target_url:
                                for entity in msg.get("entities", []):
                                    if entity.get("type") == "text_link":
                                        target_url = entity.get("url")
                                        break
                                    elif entity.get("type") == "url":
                                        o = entity.get("offset", 0)
                                        l = entity.get("length", 0)
                                        target_url = msg_text[o:o+l].strip()
                                        break
                        except Exception as err:
                            print(f"[EXTRACTION ERROR] {err}", flush=True)

                        if target_url:
                            print(f"🎯 URL identifiée : {target_url}", flush=True)
                            threading.Thread(
                                target=execute_playwright_application,
                                args=(target_url, token, chat_id, job_title, company_name, cover_letter_text),
                                daemon=True
                            ).start()
                        else:
                            print("⚠️ Impossible d'extraire l'URL cible.", flush=True)
                            send_telegram_message(token, chat_id, "⚠️ Impossible de trouver l'URL de candidature dans ce message.")

                    elif is_ignore:
                        answer_callback(token, cq_id, "❌ Offre ignorée.")
                        send_telegram_message(token, chat_id, "🗑️ Cette offre a été marquée comme ignorée.")

                # ==========================================================
                # B. RÉCEPTION D'UN MESSAGE (PHOTO, TEXTE, OU LIEN)
                # ==========================================================
                elif "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    caption = msg.get("caption", "").strip()

                    # ------------------------------------------------------
                    # 1. ENTRÉE PAR PHOTO / CAPTURE D'ÉCRAN
                    # ------------------------------------------------------
                    is_image_doc = False
                    if "document" in msg:
                        doc = msg["document"]
                        mime = doc.get("mime_type", "").lower()
                        fname = doc.get("file_name", "").lower()
                        if mime.startswith("image/") or any(fname.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                            is_image_doc = True

                    if "photo" in msg or is_image_doc:
                        file_id = msg["photo"][-1]["file_id"] if "photo" in msg else msg["document"]["file_id"]
                        temp_img = DOCS_DIR / f"temp_job_{int(time.time())}.png"

                        print(f"\n📸 [TELEGRAM] Image d'offre reçue de {chat_id}. Téléchargement...", flush=True)
                        send_telegram_message(token, chat_id, "📸 Photo de l'offre reçue ! Mon Cerveau IA Multimodal analyse le visuel et rédige ton Anschreiben DIN 5008...")

                        download_telegram_file(token, file_id, temp_img)

                        # Analyse Multimodale avec Gemini
                        res = analyze_job_with_gemini(
                            text_content=caption if caption else None,
                            image_path=temp_img,
                            profile=profile
                        )

                        job_title = res.get("job_title", "Offre d'emploi")
                        company_name = res.get("company_name", "Unternehmen")
                        score = res.get("score", "N/A")
                        begruendung = res.get("begruendung", "")
                        anschreiben = res.get("anschreiben", "")
                        apply_url = res.get("apply_url")

                        # Vérifier si l'URL est aussi dans la légende (caption)
                        if caption and not apply_url:
                            cap_url = re.search(r'(https?://[^\s<>"]+)', caption)
                            if cap_url:
                                apply_url = cap_url.group(1)

                        # Compiler le PDF DIN 5008
                        if anschreiben:
                            generate_anschreiben_pdf(anschreiben, job_title, company_name)
                            anschreiben_pdf = DOCS_DIR / "anschreiben.pdf"
                            send_telegram_document(
                                token, chat_id, anschreiben_pdf,
                                caption=f"📄 Anschreiben DIN 5008 personnalisé pour {job_title} chez {company_name}"
                            )

                        # Enregistrer le contexte
                        LAST_PENDING_JOB = {
                            "job_title": job_title,
                            "company_name": company_name,
                            "anschreiben": anschreiben,
                            "apply_url": apply_url,
                            "timestamp": time.time()
                        }

                        if apply_url and apply_url.startswith("http"):
                            cache_id = f"job_{int(time.time())}"
                            URL_CACHE[cache_id] = apply_url
                            reply_markup = {
                                "inline_keyboard": [
                                    [{"text": "🚀 POSTULER SUR MON ÉCRAN", "callback_data": f"apply:{cache_id}"}],
                                    [{"text": "❌ IGNORER", "callback_data": f"ignore:{cache_id}"}]
                                ]
                            }
                            send_telegram_message(
                                token, chat_id,
                                f"🎯 Poste : {job_title}\n🏢 Entreprise : {company_name}\n📊 Score IA : {score}/100\n💡 {begruendung}\n\n👉 Clique ci-dessous pour que j'ouvre Chromium et remplisse le formulaire !",
                                reply_markup=reply_markup
                            )
                        else:
                            send_telegram_message(
                                token, chat_id,
                                f"🎯 Poste : {job_title}\n🏢 Entreprise : {company_name}\n📊 Score IA : {score}/100\n💡 {begruendung}\n\n✅ Ton Anschreiben est prêt et envoyé ci-dessus !\n👉 Envoie-moi simplement le lien direct (URL) pour que j'ouvre Chromium et remplisse la candidature sur ton PC !"
                            )

                    # ------------------------------------------------------
                    # 2. ENTRÉE PAR TEXTE OU LIEN (URL)
                    # ------------------------------------------------------
                    elif "text" in msg:
                        text = msg["text"].strip()
                        print(f"\n📩 [TELEGRAM] Message texte de {chat_id} : {text[:80]}", flush=True)

                        # a) Boutons de navigation et commandes rapides
                        if text.startswith("/start") or text.startswith("/help") or text in ["ℹ️ Aide", "📋 Formats acceptés"]:
                            send_telegram_message(
                                token, chat_id,
                                f"👋 Bonjour {candidate_name} !\n\n"
                                "🤖 **Cockpit de Candidature IA (100% Connecté)**\n\n"
                                "Tu peux m'envoyer à tout moment :\n"
                                "1️⃣ 🔗 **Un lien (URL)** vers une offre (LinkedIn, Indeed, StepStone, Greenhouse...)\n"
                                "2️⃣ 📸 **Une photo ou capture d'écran** de l'annonce\n"
                                "3️⃣ 📝 **Le texte complet** copié-collé d'une offre\n\n"
                                "⚡ Dès réception :\n"
                                "• Je rédige un **Anschreiben allemand DIN 5008** et t'envoie le PDF\n"
                                "• J'ouvre **Chromium en plein écran** sur ton PC et pré-remplis tout !",
                                reply_markup=TACTILE_KEYBOARD
                            )
                            continue

                        elif text.startswith("/profil") or text == "👤 Mon Profil & CV":
                            send_telegram_message(
                                token, chat_id,
                                f"👤 **PROFIL CANDIDAT ACTIF**\n\n"
                                f"• **Nom** : {candidate_name}\n"
                                f"• **Formation** : B.Sc. Angewandte Informatik (Hochschule Worms)\n"
                                f"• **Expériences** : PWO AG (DevOps & Automatisation) | Projet Bosch (FastAPI & Kafka)\n"
                                f"• **Langues** : Allemand (Fließend TestDaF 4), Français (Natif), Anglais (B1)\n"
                                f"• **CV configuré** : `d:/N8N/documents/cv.pdf` ✅\n"
                                f"• **Portfolio** : https://portfolio-pro-fraid.vercel.app/de\n\n"
                                "👉 Tu peux m'envoyer n'importe quelle offre pour postuler !",
                                reply_markup=TACTILE_KEYBOARD
                            )
                            continue

                        elif text.startswith("/status") or text == "🟢 Statut du Cockpit":
                            send_telegram_message(
                                token, chat_id,
                                "🟢 **STATUT DU COCKPIT : 100% OPÉRATIONNEL**\n\n"
                                "• **PC Local** : Connecté & en écoute 🎧\n"
                                "• **Cerveau IA** : Gemini 3 Flash actif 🧠\n"
                                "• **Navigateur** : Chromium Playwright prêt 🚀\n"
                                "• **Générateur PDF** : DIN 5008 prêt 📄\n"
                                "• **Dossier documents** : `d:/N8N/documents/` accessible 📁",
                                reply_markup=TACTILE_KEYBOARD
                            )
                            continue

                        # b) Détecter la présence d'une URL dans le message
                        url_match = re.search(r'(https?://[^\s<>"]+)', text)
                        detected_url = url_match.group(1) if url_match else None

                        # CAS 1 : C'est un LIEN direct (court ou commande /apply)
                        if detected_url and (len(text) < 220 or text.startswith("/apply")):
                            print(f"\n🔗 [TELEGRAM] Lien reçu : {detected_url}", flush=True)

                            # Vérifier si on a un Anschreiben récent en attente pour CETTE MÊME offre (ex: photo envoyée juste avant)
                            cached_url = LAST_PENDING_JOB.get("apply_url")
                            has_cached_letter = bool(
                                LAST_PENDING_JOB.get("anschreiben") and 
                                (time.time() - LAST_PENDING_JOB.get("timestamp", 0) < 300) and
                                (cached_url == detected_url or not cached_url)
                            )

                            if has_cached_letter:
                                job_title = LAST_PENDING_JOB.get("job_title", "Offre d'emploi")
                                company_name = LAST_PENDING_JOB.get("company_name", "Unternehmen")
                                anschreiben = LAST_PENDING_JOB.get("anschreiben")
                                print(f"  ✓ Utilisation de la lettre en mémoire pour {job_title} ({company_name})", flush=True)
                                send_telegram_message(token, chat_id, f"🔗 Lien reçu ! Utilisation de l'Anschreiben déjà prêt pour {job_title} ({company_name}).\n🚀 Lancement de Chromium sur ton écran...")
                            else:
                                send_telegram_message(token, chat_id, f"🔎 Lien reçu ! Extraction de l'offre et analyse stratégique par l'IA...")
                                page_text = extract_text_from_url(detected_url)
                                res = analyze_job_with_gemini(
                                    text_content=page_text if page_text else f"Offre d'emploi à l'URL : {detected_url}",
                                    profile=profile
                                )
                                job_title = res.get("job_title", "Offre d'emploi")
                                company_name = res.get("company_name", "Unternehmen")

                                # Sécurisation contre faux titre de bot-schutz / Cloudflare
                                if any(b in (job_title or "").lower() for b in ["bot-schutz", "nicht identifizierbar", "cloudflare"]):
                                    url_kw = re.search(r'/jobs/([^/?]+)', detected_url)
                                    if url_kw:
                                        job_title = url_kw.group(1).replace('+', ' ').replace('-', ' ').title()
                                    else:
                                        job_title = "Junior Software Developer"
                                if any(b in (company_name or "").lower() for b in ["bot-schutz", "nicht identifizierbar", "cloudflare"]):
                                    company_name = "Unternehmen"

                                score = res.get("score", "N/A")
                                begruendung = res.get("begruendung", "")
                                anschreiben = res.get("anschreiben", "")

                                if anschreiben:
                                    generate_anschreiben_pdf(anschreiben, job_title, company_name)
                                    anschreiben_pdf = DOCS_DIR / "anschreiben.pdf"
                                    send_telegram_document(
                                        token, chat_id, anschreiben_pdf,
                                        caption=f"📄 Anschreiben DIN 5008 pour {job_title} chez {company_name}\n📊 Score IA : {score}/100"
                                    )

                                send_telegram_message(token, chat_id, f"🚀 Ouverture de Chromium en plein écran sur ton PC pour pré-remplir la candidature...")

                            threading.Thread(
                                target=execute_playwright_application,
                                args=(detected_url, token, chat_id, job_title, company_name, anschreiben),
                                daemon=True
                            ).start()

                        # CAS 2 : C'est un TEXTE COMPLET de description d'offre (> 120 caractères)
                        elif len(text) >= 120:
                            print(f"\n📝 [TELEGRAM] Descriptif complet d'offre reçu ({len(text)} caractères)", flush=True)
                            send_telegram_message(token, chat_id, "📝 Descriptif complet reçu ! Mon Cerveau IA analyse les exigences et rédige ton Anschreiben DIN 5008...")

                            res = analyze_job_with_gemini(text_content=text, profile=profile)
                            job_title = res.get("job_title", "Offre d'emploi")
                            company_name = res.get("company_name", "Unternehmen")
                            score = res.get("score", "N/A")
                            begruendung = res.get("begruendung", "")
                            anschreiben = res.get("anschreiben", "")
                            apply_url = detected_url or res.get("apply_url")

                            if anschreiben:
                                generate_anschreiben_pdf(anschreiben, job_title, company_name)
                                anschreiben_pdf = DOCS_DIR / "anschreiben.pdf"
                                send_telegram_document(
                                    token, chat_id, anschreiben_pdf,
                                    caption=f"📄 Anschreiben DIN 5008 personnalisé pour {job_title} chez {company_name}"
                                )

                            LAST_PENDING_JOB = {
                                "job_title": job_title,
                                "company_name": company_name,
                                "anschreiben": anschreiben,
                                "apply_url": apply_url,
                                "timestamp": time.time()
                            }

                            if apply_url and apply_url.startswith("http"):
                                cache_id = f"job_{int(time.time())}"
                                URL_CACHE[cache_id] = apply_url
                                reply_markup = {
                                    "inline_keyboard": [
                                        [{"text": "🚀 POSTULER SUR MON ÉCRAN", "callback_data": f"apply:{cache_id}"}],
                                        [{"text": "❌ IGNORER", "callback_data": f"ignore:{cache_id}"}]
                                    ]
                                }
                                send_telegram_message(
                                    token, chat_id,
                                    f"🎯 Poste : {job_title}\n🏢 Entreprise : {company_name}\n📊 Score IA : {score}/100\n💡 {begruendung}\n\n👉 Clique ci-dessous pour que j'ouvre Chromium et remplisse le formulaire !",
                                    reply_markup=reply_markup
                                )
                            else:
                                send_telegram_message(
                                    token, chat_id,
                                    f"🎯 Poste : {job_title}\n🏢 Entreprise : {company_name}\n📊 Score IA : {score}/100\n💡 {begruendung}\n\n✅ Ton Anschreiben est prêt et envoyé ci-dessus !\n👉 Envoie-moi maintenant le lien de l'offre (URL) pour que j'ouvre Chromium et remplisse tout pour toi !"
                                )

                        # CAS 3 : Message court / conversationnel
                        else:
                            send_telegram_message(
                                token, chat_id,
                                "💡 Pour lancer une candidature automatique, tu peux simplement m'envoyer :\n"
                                "• Le lien (URL) de l'offre\n"
                                "• Une capture d'écran / photo de l'offre\n"
                                "• Le texte complet du descriptif de poste",
                                reply_markup=TACTILE_KEYBOARD
                            )

        except KeyboardInterrupt:
            print("\nArrêt du Cockpit Telegram. À bientôt !", flush=True)
            break
        except Exception as e:
            err_str = str(e)
            if "409" in err_str:
                print("⚠️ [CONFLIT TELEGRAM] Une autre session interroge le bot (409 Conflict). Attente 5s...", flush=True)
                time.sleep(5)
            else:
                print(f"⚠️ [BOUCLE TELEGRAM] {e}", flush=True)
                time.sleep(2)

if __name__ == "__main__":
    start_cockpit()
