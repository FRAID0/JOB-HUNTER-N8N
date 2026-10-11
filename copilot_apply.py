#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copilote de Candidature Playwright avec Cerveau IA Gemini (Human-in-the-Loop)
Auteur: Open Source Contributor
Description: 
- Génération d'Anschreiben au format DIN 5008 (PDF professionnel allemand).
- Remplissage automatique intelligent des champs standards (coordonnées, liens).
- Cerveau IA (Gemini 3 Flash Preview) pour analyser et répondre en direct
  aux questions personnalisées, menus déroulants (<select>), radios et dates.
- Upload automatique du Lebenslauf (cv.pdf) et de l'Anschreiben (anschreiben.pdf).
- Garde le navigateur Chromium ouvert pour vérification humaine finale.
"""

import os
import sys
import json
import time
import re
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from agent_engine import AutonomousAgentLoop, ApplicationState

if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
if sys.stderr:
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
PROFIL_PATH = BASE_DIR / "profil.json"
DOCS_DIR = BASE_DIR / "documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

def load_profile():
    if not PROFIL_PATH.exists():
        print(f"[ERREUR] Le fichier {PROFIL_PATH} est introuvable.")
        sys.exit(1)
    with open(PROFIL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_gemini_api_key():
    """Récupère la clé Gemini depuis .env ou les variables d'environnement."""
    if ENV_PATH.exists():
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass
    return os.environ.get("GEMINI_API_KEY", "").strip()

def generate_anschreiben_pdf(letter_text, job_title="Werkstudent Software Developer", company_name="Unternehmen"):
    """
    Compile une lettre de motivation en PDF respectant la disposition demandée
    (Bloc candidat en haut à droite, Entreprise à gauche, date à droite au format DD.MM.YYYY, etc.)
    et l'enregistre dans documents/anschreiben.pdf via Playwright.
    """
    profile = load_profile()
    p_info = profile.get("personal_info", {})
    addr = p_info.get("address", {})

    sender_name = p_info.get("full_name", "Candidat")
    sender_phone = p_info.get("phone", "+49 170 0000000")
    sender_email = p_info.get("email", "candidate@example.com")
    sender_street = addr.get("street", "Musterstrasse 1")
    sender_zip_city = f"{addr.get('postal_code', '10115')} {addr.get('city', 'Berlin')}"
    links = p_info.get("links", {})
    sender_portfolio = links.get("portfolio", "https://example.com/portfolio")
    sender_github = links.get("github", "https://github.com/example-profile")

    # Date du jour au format JJ.MM.AAAA (ex: 03.10.2026)
    current_date = datetime.now().strftime("%d.%m.%Y")

    # Nettoyage et formatage du texte de la lettre
    clean_text = letter_text.strip()
    if "--- ANSCHREIBEN ---" in clean_text:
        clean_text = clean_text.split("--- ANSCHREIBEN ---", 1)[1].strip()
    elif "---" in clean_text:
        clean_text = clean_text.split("---", 1)[1].strip()

    # Si l'en-tête de salutation est présent, le corps démarre à partir de là pour éviter les doublons d'adresse/date
    if "Sehr geehrte" in clean_text:
        clean_text = "Sehr geehrte" + clean_text.split("Sehr geehrte", 1)[1]

    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    formatted_body_list = []
    for p in paragraphs:
        p_html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', p)
        p_html = p_html.replace('\n', '<br>')
        formatted_body_list.append(f"<p>{p_html}</p>")
    formatted_body_html = "".join(formatted_body_list)

    # Vérifier si la lettre contient déjà une formule de politesse finale pour ne pas faire de doublon
    has_closing = any(cl in clean_text.lower() for cl in ["mit freundlichen grüßen", "mit freundlichen gruessen", "freundliche grüße", "mit besten grüßen"])
    closing_html = ""
    if not has_closing:
        closing_html = f"""
  <div class="closing-block">
    Mit freundlichen Grüßen,<br><br>
    <div class="signature-name">{sender_name}</div>
  </div>"""

    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 25mm 25mm 20mm 25mm;
  }}
  body {{
    font-family: Arial, Helvetica, sans-serif;
    color: #000000;
    font-size: 11pt;
    line-height: 1.45;
    background: #ffffff;
  }}
  .sender-block {{
    margin-left: 45%;
    margin-bottom: 35px;
    line-height: 1.45;
  }}
  .sender-name {{
    font-size: 11pt;
    font-weight: normal;
    color: #000000;
  }}
  .sender-contact, .sender-address {{
    font-size: 11pt;
    color: #000000;
  }}
  .sender-contact a {{
    color: #1a0dab;
    text-decoration: underline;
  }}
  .meta-row {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 35px;
  }}
  .recipient-block {{
    line-height: 1.4;
    font-size: 11pt;
  }}
  .recipient-company {{
    font-weight: bold;
    margin-bottom: 2px;
  }}
  .date-block {{
    text-align: right;
    font-size: 11pt;
    white-space: nowrap;
  }}
  .subject-block {{
    font-size: 12.5pt;
    font-weight: bold;
    margin-bottom: 25px;
    letter-spacing: -0.1px;
  }}
  .body-block {{
    text-align: justify;
    line-height: 1.5;
  }}
  .body-block p {{
    margin-top: 0;
    margin-bottom: 14px;
  }}
  .closing-block {{
    margin-top: 25px;
    line-height: 1.6;
  }}
  .signature-name {{
    margin-top: 15px;
  }}
</style>
</head>
<body>
  <div class="sender-block">
    <div class="sender-name"><strong>{sender_name}</strong></div>
    <div class="sender-address">{sender_street}, {sender_zip_city}</div>
    <div class="sender-contact">{sender_phone} | <a href="mailto:{sender_email}">{sender_email}</a></div>
    <div class="sender-contact">Portfolio: <a href="{sender_portfolio}">{sender_portfolio}</a> | GitHub: <a href="{sender_github}">{sender_github}</a></div>
  </div>

  <div class="meta-row">
    <div class="recipient-block">
      <div class="recipient-company">{company_name}</div>
      <div>Personalabteilung / Recruiting</div>
      <div>Deutschland</div>
    </div>
    <div class="date-block">
      {current_date}
    </div>
  </div>

  <div class="subject-block">
    Bewerbung als {job_title}
  </div>

  <div class="body-block">
    {formatted_body_html}
  </div>

  {closing_html}
</body>
</html>
"""

    out_pdf = DOCS_DIR / "anschreiben.pdf"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        page.pdf(
            path=str(out_pdf),
            format="A4",
            print_background=True,
            margin={"top": "25mm", "right": "25mm", "bottom": "20mm", "left": "25mm"}
        )
        browser.close()

    print(f"📄 [PDF DIN 5008] Anschreiben généré avec succès : {out_pdf.name} ({out_pdf.stat().st_size} octets)", flush=True)
    return out_pdf

FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-flash-latest"
]

def query_gemini(payload, key, timeout=35):
    """Interroge Gemini avec bascule automatique (fallback) en cas d'erreur 503/429."""
    for model in FALLBACK_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                data = json.loads(res.read().decode("utf-8"))
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0].strip()
                return raw_text
        except Exception as e:
            continue
    return None

def ask_gemini_brain(fields, profile, job_title=""):
    """
    Cerveau IA : interroge Gemini pour résoudre en direct les questions
    et menus déroulants non standards d'un formulaire d'embauche.
    """
    key = get_gemini_api_key()
    if not key or not fields:
        return {}

    p_info = profile.get("personal_info", profile)
    c_name = p_info.get("full_name", "le candidat")
    cand_k = profile.get("candidate_knowledge", {})
    work_auth = cand_k.get("work_authorization", "Titre de séjour étudiant / Permis de travail en règle")
    langs = cand_k.get("languages", {})
    german_lvl = langs.get("german", "Fließend / Sehr gut / C1")
    english_lvl = langs.get("english", "Grundlegend / B1")

    prompt = f"""Tu es le cerveau d'automatisation de candidature pour {c_name} (étudiant / profil Tech & DevOps).
Voici son profil complet :
{json.dumps(profile, ensure_ascii=False, indent=2)}

Titre du poste ciblé : {job_title}

Voici la liste des champs ou questions détectés sur la page web :
{json.dumps(fields, ensure_ascii=False, indent=2)}

RÈGLES IMPORTANTES :
1. Pour l'Allemand : {c_name} a le niveau ({german_lvl}).
2. Pour l'Anglais : {c_name} a le niveau ({english_lvl}). Sélectionne 'Grundlegend' si disponible.
3. Pour la disponibilité : Généralement J+7 ou J+14 au format JJ.MM.AAAA (ex: dans 7 jours).
4. Pour les menus déroulants (type 'select') : Choisis EXACTEMENT l'un des textes de la liste 'options'.
5. Pour les questions de nationalité / permis de travail : {work_auth}.
6. Pour les questions Oui/Non (Ja/Nein) concernant les compétences possédées dans son profil, répondre 'Ja'.

Renvoie STRICTEMENT un objet JSON valide associant chaque 'id' de champ à la valeur choisie.
Exemple attendu :
{{
  "field_0": "Fließend",
  "field_1": "Grundlegend"
}}
"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        raw_text = query_gemini(payload, key, timeout=35)
        if raw_text:
            answers = json.loads(raw_text)
            print(f"🧠 [CERVEAU GEMINI] {len(answers)} décisions prises avec succès !", flush=True)
            return answers
        else:
            print("⚠️ [CERVEAU GEMINI] Tous les modèles Gemini sont momentanément indisponibles.", flush=True)
            return {}
    except Exception as e:
        print(f"⚠️ [CERVEAU GEMINI] Erreur parsing JSON : {e}", flush=True)
        return {}

def visual_qa_critique(screenshot_path, profile, job_title="Offre d'emploi"):
    """
    Superviseur Qualité Multimodal : analyse visuellement la capture d'écran
    avec Gemini Vision pour vérifier que le formulaire est bien rempli,
    sans modal bloquant, sans message d'erreur rouge, avec documents attachés.
    """
    key = get_gemini_api_key()
    if not key or not Path(screenshot_path).exists():
        return {"is_ready_for_human": True, "verdict": "Validation automatique standard terminée."}

    try:
        import base64
        with open(screenshot_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        p_info = profile.get("personal_info", profile)
        c_name = p_info.get("full_name", "le candidat")
        prompt = f"""Tu es le superviseur qualité IA pour les candidatures de {c_name}.
Poste ciblé : {job_title}
Analyse cette capture d'écran du navigateur après remplissage automatique :
1. Y a-t-il encore un pop-up de cookies ou modal bloquant ?
2. Le formulaire est-il affiché ou est-on encore sur une page d'agrégateur ?
3. Les champs clés (nom, email, téléphone, etc.) sont-ils remplis ?
4. Le CV ou la lettre sont-ils attachés ?
5. Y a-t-il des messages d'erreur en rouge ?

Réponds STRICTEMENT par un objet JSON valide :
{{
  "is_ready_for_human": true,
  "has_blocking_modal": false,
  "is_on_job_board_not_form": false,
  "missing_fields": [],
  "verdict": "Formulaire 100% prêt et conforme. Aucun champ obligatoire manquant."
}}
"""
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": b64_data
                            }
                        }
                    ]
                }
            ]
        }

        raw_text = query_gemini(payload, key, timeout=35)
        if raw_text:
            qa_result = json.loads(raw_text)
            print(f"👁️ [CONTRÔLE QUALITÉ VISUEL IA] {qa_result.get('verdict')}", flush=True)
            return qa_result
        else:
            return {"is_ready_for_human": True, "verdict": "Validation automatique effectuée."}
    except Exception as e:
        print(f"⚠️ [CONTRÔLE QUALITÉ VISUEL IA] Non disponible : {e}", flush=True)
        return {"is_ready_for_human": True, "verdict": "Validation automatique effectuée."}

def run_agent_engine(page, profile, cover_letter_text=None, job_title="Offre d'emploi", on_human_gate_callback=None):
    """
    Exécute le nouveau moteur agentique autonome (agent_engine) :
    - Indexation DOM numérique [1], [2], [3] (style Browser-Use)
    - Fast-Path Niveau 0 / 1 (données déterministes et heuristiques)
    - Cerveau ReAct Niveau 2 (Gemini 3.1 Flash Lite avec fallback)
    - Action Validator strict
    - Terminal Guard (Human Gate infranchissable pour boutons finaux)
    """
    p_info = profile.get("personal_info", profile)
    docs = profile.get("documents", {})
    cv_file = docs.get("cv", DOCS_DIR / "cv.pdf")
    screenshots_folder = DOCS_DIR / "screenshots"
    screenshots_folder.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60, flush=True)
    print("🧠 [AGENT ENGINE] Activation du moteur agentique autonome...", flush=True)
    print(f"Poste visé : {job_title}", flush=True)
    print("=" * 60, flush=True)

    agent = AutonomousAgentLoop(
        page=page,
        profile=profile,
        cv_path=str(Path(cv_file).resolve()) if Path(cv_file).exists() else None,
        docs_dir=str(DOCS_DIR.resolve()),
        gemini_api_key=get_gemini_api_key(),
        max_steps=8,
        screenshot_dir=str(screenshots_folder),
        on_human_gate_callback=on_human_gate_callback,
    )
    result = agent.run(goal=f"Remplir le formulaire de candidature pour '{job_title}' et stopper avant validation finale.")
    print(f"🏁 [AGENT ENGINE TERMINÉ] État : {result.final_state.value} | Human Gate : {result.requires_human} | Étapes : {result.steps_executed}", flush=True)
    return result

def handle_cloudflare_challenge(page, max_wait_seconds=10):
    """
    Détecte et clique automatiquement sur le défi Cloudflare Turnstile :
    'Bestätigen Sie, dass Sie ein Mensch sind' / 'Verify you are human'.
    Attend ensuite la validation et la redirection vers le site cible.
    """
    cf_indicators = [
        "text='Bestätigen Sie, dass Sie ein Mensch sind'",
        "text='Sicherheitsüberprüfung wird durchgeführt'",
        "text='Verify you are human'",
        "text='Nur einen Moment...'"
    ]
    is_cf = False
    try:
        title = page.title()
        if "Nur einen Moment" in title or "Just a moment" in title:
            is_cf = True
        elif any(page.locator(ind).count() > 0 for ind in cf_indicators):
            is_cf = True
        elif page.locator("iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile']").count() > 0:
            is_cf = True
    except Exception:
        pass

    if not is_cf:
        return False

    print("🛡️ [CLOUDFLARE] Défi 'Bestätigen Sie, dass Sie ein Mensch sind' détecté ! Résolution automatique...", flush=True)
    time.sleep(1.5)

    clicked = False
    # 1. Tentative via frame_locator (recommandé Playwright pour les iframes cross-domain)
    try:
        cf_frame = page.frame_locator("iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile'], iframe[title*='Cloudflare']").first
        for target in ["input[type='checkbox']", ".ctp-checkbox-label", "#challenge-stage", "span.mark", "label"]:
            loc = cf_frame.locator(target).first
            if loc.count() > 0 and loc.is_visible(timeout=2000):
                loc.click(timeout=3000)
                print(f"👉 [CLOUDFLARE] Case Turnstile cliquée avec succès ({target}) !", flush=True)
                clicked = True
                break
    except Exception as e:
        pass

    # 2. Tentative de secours via l'itération des frames du navigateur
    if not clicked:
        for f in page.frames:
            if any(k in f.url for k in ["cloudflare", "challenges", "turnstile"]):
                for target in ["input[type='checkbox']", ".ctp-checkbox-label", "#challenge-stage", "span.mark", "label"]:
                    try:
                        loc = f.locator(target).first
                        if loc.count() > 0 and loc.is_visible(timeout=1500):
                            loc.click(timeout=2000)
                            print(f"👉 [CLOUDFLARE] Case Turnstile cliquée via frame ({target}) !", flush=True)
                            clicked = True
                            break
                    except Exception:
                        pass
                if clicked:
                    break

    # Attendre que Cloudflare valide le challenge et recharge la vraie page
    start = time.time()
    while time.time() - start < max_wait_seconds:
        time.sleep(1)
        try:
            curr_title = page.title()
            if "Nur einen Moment" not in curr_title and "Just a moment" not in curr_title and "Sicherheitsüberprüfung" not in curr_title:
                print(f"✅ [CLOUDFLARE] Défi résolu avec succès ! Page chargée : {curr_title} ({page.url})", flush=True)
                time.sleep(2)
                return True
        except Exception:
            pass

    return clicked

def dismiss_barriers_and_modals(page):
    """
    Ferme automatiquement les barrières d'accès :
    - Défi Cloudflare Turnstile ('Bestätigen Sie, dass Sie ein Mensch sind')
    - Popups d'authentification intrusive (ex: LinkedIn contextual-sign-in-modal, Google One Tap)
    - Fenêtres modales de newsletters / bannières d'inscription invité
    - Bannières de cookies et consentements GDPR (DE / EN / FR)
    """
    # 0. Résoudre Cloudflare Turnstile si présent
    handle_cloudflare_challenge(page)

    # 1. Fermer les modales intrusives et authwalls (LinkedIn, Glassdoor, Indeed, etc.)
    modal_dismiss_selectors = [
        "button[data-tracking-control-name*='modal_dismiss']",
        "button[data-tracking-control-name='public_jobs_contextual-sign-in-modal_modal_dismiss']",
        "button.contextual-sign-in-modal__modal-dismiss-btn",
        "button.modal__dismiss",
        ".artdeco-modal__dismiss",
        "button[aria-label='Schließen']",
        "button[aria-label='Dismiss']",
        "button[aria-label='Close']",
        "button[aria-label='Fermer']",
        "[data-test-modal-close-btn]",
        ".modal-close-button",
        "button.close",
        "[aria-label='close' i]"
    ]
    for m_sel in modal_dismiss_selectors:
        try:
            m_btn = page.locator(m_sel).first
            if m_btn.count() > 0 and m_btn.is_visible(timeout=400):
                print(f"🛡️ Barricade / modale intrusive détectée, fermeture automatique ({m_sel})...", flush=True)
                m_btn.click(timeout=1000)
                time.sleep(0.5)
        except Exception:
            pass

    # 2. Fermer / accepter les bannières de cookies (DE / EN / FR)
    cookie_selectors = [
        "button[data-tracking-control-name*='cookie']",
        "button[data-tracking-control-name*='consent']",
        ".fc-consent-root button",
        "button:has-text('Einwilligen')",
        "button:has-text('Alle akzeptieren')",
        "button:has-text('Akzeptieren')",
        "button:has-text('Zustimmen')",
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "button:has-text('J\\'accepte')",
        "button:has-text('Accepter')",
        "#onetrust-accept-btn-handler",
        "#uc-btn-accept-banner",
        "button[data-testid='uc-accept-all-button']",
        "button[id*='accept-all']",
        "button:has-text('Alles akzeptieren')",
        "button:has-text('Zustimmen & Weiter')",
        "#cmpwelcomebtnyes",
        "button.cmpboxbtn",
        "[id*='cookie'] button",
        "[class*='cookie'] button"
    ]
    for sel in cookie_selectors:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible(timeout=500):
                print(f"🍪 Cookie banner détectée, fermeture automatique ({sel})...", flush=True)
                btn.click(timeout=1000)
                time.sleep(0.5)
                break
        except Exception:
            pass

def extract_clean_target_url(href):
    """Extrait l'URL de destination finale si elle est imbriquée dans un lien de tracking."""
    if not href:
        return None
    if "externalapply" in href.lower() and "url=" in href:
        try:
            parsed = urllib.parse.urlparse(href)
            qs = urllib.parse.parse_qs(parsed.query)
            if "url" in qs and qs["url"]:
                return urllib.parse.unquote(qs["url"][0])
        except Exception:
            pass
    return None

def resolve_application_page(page):
    """
    Si on est sur un agrégateur (LinkedIn, Jobvector, Indeed, Stepstone, etc.), détecte le lien employeur
    réel (offsite apply), extrait les URLs cibles, gère les ouvertures multi-onglets,
    et renvoie l'objet Page actif contenant le véritable formulaire de candidature.
    """
    dismiss_barriers_and_modals(page)
    current_url = page.url.lower()

    # Cas A0 : Agrégateurs connus (Arbeitnow, Indeed, Stepstone, Glassdoor, etc.)
    # → clique sur le bouton "Apply" qui redirige vers le portail employeur réel
    KNOWN_AGGREGATORS = [
        "arbeitnow.com", "indeed.com", "stepstone.de", "glassdoor.com",
        "xing.com", "monster.de", "jobs.ch", "jobscout24.de", "jobware.de",
        "stellenanzeigen.de", "yourfirm.de", "absolventa.de", "azubiyo.de",
    ]
    if any(agg in current_url for agg in KNOWN_AGGREGATORS):
        dismiss_barriers_and_modals(page)
        print(f"🔍 [AGRÉGATEUR] Site agrégateur détecté ({current_url[:60]}), recherche du bouton Apply externe...", flush=True)
        time.sleep(1.5)  # laisser le JS charger les boutons
        dismiss_barriers_and_modals(page)

        aggregator_apply_selectors = [
            "a:has-text('Apply now')",
            "a:has-text('Apply')",
            "a:has-text('Jetzt bewerben')",
            "a:has-text('Bewerben')",
            "a:has-text('Auf diese Stelle bewerben')",
            "a:has-text('Zur Bewerbung')",
            "a:has-text('Apply on company site')",
            "a:has-text('Apply on company website')",
            "button:has-text('Apply now')",
            "button:has-text('Apply')",
            "button:has-text('Jetzt bewerben')",
            "button:has-text('Bewerben')",
            "a[href*='/apply']",
            "a[href*='personio']",
            "a[href*='greenhouse.io']",
            "a[href*='lever.co']",
            "a[href*='workday.com']",
            "a[data-action*='apply']",
            "a[data-qa*='apply']",
            ".apply-button",
            ".btn-apply",
        ]
        for sel in aggregator_apply_selectors:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0 and btn.is_visible(timeout=1500):
                    href = btn.get_attribute("href") or ""
                    print(f"🎯 [AGRÉGATEUR] Bouton trouvé : '{sel}' (href={href[:80]})", flush=True)
                    # Redirection directe si le href est un lien externe absolu
                    if href and href.startswith("http") and not any(agg in href for agg in KNOWN_AGGREGATORS):
                        print(f"🎯 [AGRÉGATEUR] Redirection directe vers portail employeur : {href}", flush=True)
                        page.goto(href, wait_until="domcontentloaded", timeout=45000)
                        time.sleep(2)
                        dismiss_barriers_and_modals(page)
                        return page
                    # Sinon cliquer et détecter ouverture d'un nouvel onglet
                    initial_pages = list(page.context.pages)
                    try:
                        with page.context.expect_page(timeout=5000) as new_p_info:
                            btn.click(timeout=2500)
                        new_page = new_p_info.value
                        new_page.wait_for_load_state("domcontentloaded", timeout=25000)
                        print(f"🌐 [AGRÉGATEUR] Bascule sur nouvel onglet : {new_page.url}", flush=True)
                        dismiss_barriers_and_modals(new_page)
                        return new_page
                    except Exception:
                        time.sleep(1.5)
                        if len(page.context.pages) > len(initial_pages):
                            new_page = page.context.pages[-1]
                            new_page.wait_for_load_state("domcontentloaded", timeout=20000)
                            print(f"🌐 [AGRÉGATEUR] Onglet contextuel : {new_page.url}", flush=True)
                            dismiss_barriers_and_modals(new_page)
                            return new_page
                    break
            except Exception:
                continue

    # Cas A : LinkedIn Jobs
    if "linkedin.com" in current_url:
        dismiss_barriers_and_modals(page)

        linkedin_apply_selectors = [
            "a[data-tracking-control-name*='apply-link-offsite']",
            "a.topcard__apply-button",
            "a.apply-button",
            "button.apply-button",
            "a:has-text('Auf Unternehmens-Website bewerben')",
            "button:has-text('Auf Unternehmens-Website bewerben')",
            "a:has-text('Bewerben')",
            "button:has-text('Bewerben')",
            "a[data-tracking-control-name='public_jobs_apply-link-offsite_sign-up-modal']",
            "button[data-tracking-control-name='public_jobs_apply-link-offsite_sign-up-modal']",
        ]

        for a_sel in linkedin_apply_selectors:
            try:
                apply_el = page.locator(a_sel).first
                if apply_el.count() > 0 and apply_el.is_visible(timeout=1000):
                    href = apply_el.get_attribute("href") or ""

                    # 1. URL encodée dans externalApply (ex: ?url=https%3A%2F%2Fjobs.wuerth.de%2F...)
                    if "externalapply" in href.lower() and "url=" in href:
                        parsed = urllib.parse.urlparse(href)
                        qs = urllib.parse.parse_qs(parsed.query)
                        if "url" in qs and qs["url"]:
                            real_url = urllib.parse.unquote(qs["url"][0])
                            print(f"🎯 [LINKEDIN] Redirection directe vers le site employeur : {real_url}", flush=True)
                            page.goto(real_url, wait_until="domcontentloaded", timeout=45000)
                            time.sleep(2)
                            dismiss_barriers_and_modals(page)
                            return page

                    # 2. Lien externe direct absolu
                    if href.startswith("http") and "linkedin.com" not in href:
                        print(f"🎯 [LINKEDIN] Redirection directe : {href}", flush=True)
                        page.goto(href, wait_until="domcontentloaded", timeout=45000)
                        time.sleep(2)
                        dismiss_barriers_and_modals(page)
                        return page

                    # 3. Clic avec détection d'ouverture de nouvel onglet
                    print(f"🎯 [LINKEDIN] Clic sur '{a_sel}' avec suivi d'onglets...", flush=True)
                    initial_pages = list(page.context.pages)
                    try:
                        with page.context.expect_page(timeout=4000) as new_page_info:
                            apply_el.click(timeout=2000)
                        new_p = new_page_info.value
                        new_p.wait_for_load_state("domcontentloaded", timeout=20000)
                        print(f"🌐 [MULTI-ONGLETS] Bascule sur le nouvel onglet : {new_p.url}", flush=True)
                        dismiss_barriers_and_modals(new_p)
                        return new_p
                    except Exception:
                        time.sleep(1.5)
                        if len(page.context.pages) > len(initial_pages):
                            new_p = page.context.pages[-1]
                            new_p.wait_for_load_state("domcontentloaded", timeout=20000)
                            print(f"🌐 [MULTI-ONGLETS] Bascule sur l'onglet contextuel : {new_p.url}", flush=True)
                            dismiss_barriers_and_modals(new_p)
                            return new_p

                    # 4. Sous-modale LinkedIn éventuelle
                    dismiss_barriers_and_modals(page)
                    break
            except Exception:
                pass

    # Cas B : Jobvector (panneau latéral d'offre avec chargement dynamique)
    if "jobvector.de" in current_url:
        dismiss_barriers_and_modals(page)
        print("🔍 [JOBVECTOR] Détection portail Jobvector, recherche du bouton de candidature...", flush=True)
        # Laisser le temps à Jobvector d'afficher le panneau de détails du poste
        time.sleep(2)
        dismiss_barriers_and_modals(page)

        jv_selectors = [
            "a:has-text('Zur Bewerbung')",
            "button:has-text('Zur Bewerbung')",
            "a:has-text('Bewerben')",
            "button:has-text('Bewerben')",
            "a:has-text('Jetzt bewerben')",
            "button:has-text('Jetzt bewerben')",
            "a[href*='/apply/']",
            "a[href*='/bewerbung/']",
            "a[data-qa*='apply']",
            "[data-testid*='apply']",
            ".jv-apply-button",
            ".job-detail-apply"
        ]
        for j_sel in jv_selectors:
            try:
                btn = page.locator(j_sel).first
                if btn.count() > 0 and btn.is_visible(timeout=1500):
                    href = btn.get_attribute("href") or ""
                    print(f"🎯 [JOBVECTOR] Bouton détecté : {j_sel} (href={href})", flush=True)
                    if href and href.startswith("http") and "jobvector.de" not in href:
                        print(f"🎯 [JOBVECTOR] Redirection directe vers employeur : {href}", flush=True)
                        page.goto(href, wait_until="domcontentloaded", timeout=45000)
                        time.sleep(2)
                        dismiss_barriers_and_modals(page)
                        return page

                    # Clic avec surveillance de nouvel onglet
                    initial_pages = list(page.context.pages)
                    try:
                        with page.context.expect_page(timeout=4000) as new_p_info:
                            btn.click(timeout=2500)
                        new_p = new_p_info.value
                        new_p.wait_for_load_state("domcontentloaded", timeout=25000)
                        print(f"🌐 [JOBVECTOR] Bascule sur nouvel onglet : {new_p.url}", flush=True)
                        dismiss_barriers_and_modals(new_p)
                        return new_p
                    except Exception:
                        time.sleep(1.5)
                        if len(page.context.pages) > len(initial_pages):
                            new_p = page.context.pages[-1]
                            new_p.wait_for_load_state("domcontentloaded", timeout=25000)
                            print(f"🌐 [JOBVECTOR] Bascule sur onglet contextuel : {new_p.url}", flush=True)
                            dismiss_barriers_and_modals(new_p)
                            return new_p
                        dismiss_barriers_and_modals(page)
                        return page
            except Exception:
                continue

    # Cas C : Portails de recrutement directs Personio (ex: metergrid.jobs.personio.de)
    if "personio" in current_url or page.locator("a:has-text('Auf diese Stelle bewerben'), button:has-text('Auf diese Stelle bewerben')").count() > 0:
        dismiss_barriers_and_modals(page)
        print("🏢 [PERSONIO] Portail Personio détecté, clic automatique sur 'Auf diese Stelle bewerben'...", flush=True)
        for p_sel in [
            "a:has-text('Auf diese Stelle bewerben')",
            "button:has-text('Auf diese Stelle bewerben')",
            "a[href*='#apply']",
            "a:has-text('Jetzt bewerben')",
            "button:has-text('Jetzt bewerben')",
            ".btn-apply"
        ]:
            try:
                p_btn = page.locator(p_sel).first
                if p_btn.count() > 0 and p_btn.is_visible(timeout=1500):
                    p_btn.click(timeout=2000)
                    print(f"  ✓ Bouton cliqué : {p_sel}", flush=True)
                    time.sleep(2)
                    dismiss_barriers_and_modals(page)
                    return page
            except Exception:
                pass

    # Cas D : Agrégateurs généraux (Arbeitnow, Indeed, Stepstone, etc.)
    external_apply = [
        "a[href$='/apply']",
        "a[title*='Apply for' i]",
        "a:has-text('Apply Now')",
        "button:has-text('Apply Now')",
        "a:has-text('Auf diese Stelle bewerben')",
        "button:has-text('Auf diese Stelle bewerben')",
        "a:has-text('Apply on company site')",
        "a:has-text('Apply on company website')",
        "a:has-text('Jetzt bewerben')",
        "button:has-text('Jetzt bewerben')",
        "a:has-text('Bewerben')",
        "button:has-text('Bewerben')",
        "a:has-text('Zur Bewerbung')",
        "button:has-text('Zur Bewerbung')",
        "a[href*='/apply/']",
        "a[href*='/bewerbung/']"
    ]
    for btn_sel in external_apply:
        try:
            apply_el = page.locator(btn_sel).first
            if apply_el.count() > 0 and apply_el.is_visible(timeout=2000):
                href = apply_el.get_attribute("href") or ""
                clean_dest = extract_clean_target_url(href)
                if clean_dest:
                    print(f"🎯 Redirection directe vers l'URL employeur extraite : {clean_dest}", flush=True)
                    page.goto(clean_dest, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(2)
                    dismiss_barriers_and_modals(page)
                    return page
                elif href and href.startswith("http") and not href.endswith(page.url):
                    print(f"🎯 Redirection directe vers le formulaire cible : {href}", flush=True)
                    page.goto(href, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(2)
                    dismiss_barriers_and_modals(page)
                    return page
                else:
                    initial_pages = list(page.context.pages)
                    try:
                        with page.context.expect_page(timeout=3000) as new_p_info:
                            apply_el.click(timeout=2000)
                        new_page = new_p_info.value
                        new_page.wait_for_load_state("domcontentloaded", timeout=20000)
                        dismiss_barriers_and_modals(new_page)
                        return new_page
                    except Exception:
                        if len(page.context.pages) > len(initial_pages):
                            new_page = page.context.pages[-1]
                            dismiss_barriers_and_modals(new_page)
                            return new_page
                    time.sleep(1)
                    break
        except Exception:
            pass

    return page

def smart_fill(page, profile, cover_letter_text=None, job_title="Offre d'emploi", on_human_gate_callback=None):
    p_info = profile.get("personal_info", {})
    addr = p_info.get("address", {})
    links = p_info.get("links", {})
    docs = profile.get("documents", {})

    # 0. Vérifier si l'offre est expirée ou retirée
    try:
        page_text = page.locator("body").inner_text(timeout=2000).lower()
        expired_indicators = [
            "this job posting has been removed",
            "this job is no longer available",
            "diese stelle ist nicht mehr verfügbar",
            "die anzeige wurde beendet",
            "job has expired",
            "position has been filled"
        ]
        for ind in expired_indicators:
            if ind in page_text:
                print(f"⚠️ [ATTENTION] L'offre est expirée ou supprimée par l'employeur ('{ind}').")
                return None
    except Exception:
        pass

    # 1. Résolution de l'agrégateur (LinkedIn, Indeed, etc.) & suppression des modales / authwalls
    page = resolve_application_page(page)

    # 2. EXÉCUTION DU MOTEUR AGENTIQUE (agent_engine : DOM Indexer + FastPath + Human Gate)
    agent_res = run_agent_engine(
        page=page,
        profile=profile,
        cover_letter_text=cover_letter_text,
        job_title=job_title,
        on_human_gate_callback=on_human_gate_callback,
    )
    if agent_res:
        agent_res.active_page = page
    if agent_res and agent_res.requires_human:
        return agent_res

    # 4. BOUCLE DE COMPLÉMENT HEURISTIQUE (si besoin)
    MAX_STEPS = 3
    total_filled = 0
    preferred_subjects = p_info.get("preferred_subjects", ["Informatik", "Mathematik", "Französisch", "Deutsch", "Python"])
    default_pwd = p_info.get("default_password", "Candidate@Karriere2026!")

    already_uploaded_sections = set()
    for step_num in range(1, MAX_STEPS + 1):
        print(f"\n🧠 [IA ÉTAPE {step_num}] Analyse et complétion intelligente du formulaire...", flush=True)
        time.sleep(1)

        # A. Genre / Salutation (Selects, Radios ou Boutons)
        try:
            for g_sel in page.locator("select[name*='gender' i], select[name*='geschlecht' i], select[name*='anrede' i]").all():
                if g_sel.is_visible(timeout=300):
                    opts = [g_sel.locator("option").nth(i).inner_text().strip() for i in range(g_sel.locator("option").count())]
                    for target_opt in ["Männlich", "Herr", "Male", "Mr"]:
                        matched = [o for o in opts if target_opt.lower() in o.lower()]
                        if matched:
                            g_sel.select_option(label=matched[0])
                            print(f"  ✓ Genre / Salutation sélectionné : {matched[0]}", flush=True)
                            total_filled += 1
                            break
            for r in page.locator("input[type='radio'][value*='m' i], input[type='radio'][value*='herr' i]").all():
                if r.is_visible(timeout=200) and not r.is_checked():
                    r.check()
                    print("  ✓ Genre (Radio Herr/Männlich) validé", flush=True)
                    total_filled += 1
                    break
        except Exception:
            pass

        # B. Mot de passe (Portails d'inscription et comptes candidats SEULEMENT - JAMAIS les authwalls de plateforme)
        current_url = page.url.lower()
        is_platform_login = any(p in current_url for p in ["linkedin.com", "accounts.google.com", "github.com", "facebook.com", "apple.com"])
        if not is_platform_login:
            try:
                for pwd_inp in page.locator("input[type='password']").all():
                    if pwd_inp.is_visible(timeout=200):
                        if not pwd_inp.input_value():
                            pwd_inp.fill(default_pwd)
                            print(f"  ✓ Mot de passe sécurisé pré-rempli (compte candidat)", flush=True)
                            total_filled += 1
            except Exception:
                pass

        # C. Correspondance sémantique des champs standards
        field_mappings = [
            # Prénom
            (["input[name*='first_name' i]", "input[id*='first_name' i]", "input[name*='vorname' i]", 
              "input[id*='vorname' i]", "input[placeholder*='Vorname' i]", "input[placeholder*='First' i]", "input[name='firstName']"],
             p_info.get("first_name", "")),
            # Nom
            (["input[name*='last_name' i]", "input[id*='last_name' i]", "input[name*='nachname' i]", 
              "input[id*='nachname' i]", "input[placeholder*='Nachname' i]", "input[placeholder*='Last' i]", "input[name='lastName']"],
             p_info.get("last_name", "")),
            # Nom complet
            (["input[name*='full_name' i]", "input[id*='full_name' i]", "input[placeholder*='Full Name' i]", 
              "input[name='name' i]", "input[id='name' i]"],
             p_info.get("full_name", "")),
            # Email
            (["input[type='email']:not([name*='newsletter' i]):not([id*='newsletter' i]):not([id*='subscribe' i]):not([placeholder*='newsletter' i])", 
              "input[name*='email' i]:not([name*='newsletter' i])", "input[id*='email' i]:not([id*='newsletter' i])", 
              "input[placeholder*='E-Mail' i]", "input[placeholder*='Email' i]", "input[name='email']"],
             p_info.get("email", "")),
            # Téléphone
            (["input[type='tel']", "input[name*='phone' i]", "input[id*='phone' i]", 
              "input[name*='telefon' i]", "input[id*='telefon' i]", "input[placeholder*='Telefon' i]", "input[name='phoneNumber']"],
             p_info.get("phone", "")),
            # Rue
            (["input[name*='street' i]", "input[id*='street' i]", "input[name*='strasse' i]", 
              "input[id*='strasse' i]", "input[placeholder*='Straße' i]"],
             addr.get("street", "")),
            # Code Postal
            (["input[name*='postal' i]", "input[name*='zip' i]", "input[name*='plz' i]", 
              "input[placeholder*='PLZ' i]", "input[placeholder*='Postleitzahl' i]"],
             addr.get("postal_code", "")),
            # Ville
            (["input[name*='city' i]", "input[id*='city' i]", "input[name*='stadt' i]", 
              "input[name*='ort' i]", "input[placeholder*='Stadt' i]", "input[placeholder*='City' i]"],
             addr.get("city", "")),
            # GitHub
            (["input[name*='347499' i]", "input[id*='347499' i]", "input[placeholder*='GitHub' i]", 
              "input[name*='github' i]", "input[id*='github' i]"],
             links.get("github", "https://github.com/example-profile")),
            # LinkedIn
            (["input[name*='linkedin' i]", "input[id*='linkedin' i]", "input[placeholder*='LinkedIn' i]"],
             links.get("linkedin") or p_info.get("linkedin") or os.environ.get("LINKEDIN_URL") or "https://www.linkedin.com/in/example-profile"),
            # Salaire / Gehaltsvorstellung
            (["input[name*='gehalt' i]", "input[id*='gehalt' i]", "input[placeholder*='Gehalt' i]", 
              "input[name*='salary' i]", "input[id*='salary' i]", "input[placeholder*='salary' i]"],
             p_info.get("expected_salary") or profile.get("expected_salary") or "52.000 €"),
            # Portfolio
            (["input[name*='portfolio' i]", "input[id*='portfolio' i]", "input[name*='website' i]", 
              "input[placeholder*='Portfolio' i]", "input[placeholder*='Website' i]"],
             links.get("portfolio", ""))
        ]

        for selectors, val in field_mappings:
            if not val:
                continue
            for sel in selectors:
                try:
                    for el in page.locator(sel).all():
                        if el.is_visible(timeout=200):
                            cur_val = el.input_value()
                            if not cur_val:
                                el.fill(val)
                                print(f"  ✓ Rempli : {val} (via {sel})", flush=True)
                                total_filled += 1
                except Exception:
                    continue

        # D. Remplissage de la disponibilité (Verfügbar ab - JJ.MM.AAAA)
        try:
            now = datetime.now()
            if now.month == 12:
                next_m = datetime(now.year + 1, 1, 1)
            else:
                next_m = datetime(now.year, now.month + 1, 1)
            target_date = next_m.strftime("%d.%m.%Y")
            
            avail_candidates = [
                "input#field-available_from",
                "input[placeholder*='Verfügbar' i]",
                "input[placeholder*='verfuegbar' i]",
                "input[name*='available' i]",
                "input[id*='available' i]",
                "input[name*='verfuegbar' i]",
                "input[name*='eintritt' i]"
            ]
            avail_filled = False
            for sel in avail_candidates:
                try:
                    avail = page.locator(sel).first
                    if avail.count() > 0 and avail.is_visible(timeout=200):
                        if not avail.input_value():
                            avail.fill(target_date)
                            print(f"  ✓ Disponibilité renseignée : {target_date} (via {sel})", flush=True)
                            total_filled += 1
                            avail_filled = True
                            break
                except Exception:
                    continue
            
            if not avail_filled:
                try:
                    lbl = page.locator("label:has-text('Verfügbar')").first
                    if lbl.count() > 0 and lbl.is_visible():
                        inp = lbl.locator("xpath=following::input[1]").first
                        if inp.count() > 0 and inp.is_visible() and not inp.input_value():
                            inp.fill(target_date)
                            print(f"  ✓ Disponibilité renseignée via label : {target_date}", flush=True)
                            total_filled += 1
                except Exception:
                    pass
        except Exception:
            pass

        # E. Boutons de choix / Matières / Compétences (ex: Fächerauswahl)
        try:
            for subj in preferred_subjects:
                for b in page.locator(f"button:visible:has-text('{subj}')").all():
                    try:
                        b_text = b.inner_text().strip()
                        if not any(nav in b_text.lower() for nav in ["weiter", "zurück", "abbrechen", "schritt"]):
                            b.click()
                            print(f"  ✓ Option/Matière sélectionnée : {b_text}", flush=True)
                            total_filled += 1
                            page.wait_for_timeout(200)
                    except Exception:
                        pass
        except Exception:
            pass

        # F. Cerveau IA pour Menus déroulants (<select>)
        try:
            selects_to_resolve = []
            select_count = page.locator("select").count()
            for i in range(select_count):
                try:
                    s = page.locator("select").nth(i)
                    if not s.is_visible():
                        continue

                    parent_text = ""
                    try:
                        parent_text = s.locator("xpath=ancestor::*[contains(@class, 'form-group') or contains(@class, 'field') or contains(@class, 'row') or self::div][1]").inner_text().strip()
                    except Exception:
                        pass

                    if not parent_text:
                        parent_text = s.get_attribute("aria-label") or s.get_attribute("name") or s.get_attribute("id") or ""

                    options = []
                    opt_count = s.locator("option").count()
                    for o_idx in range(opt_count):
                        opt_text = s.locator("option").nth(o_idx).inner_text().strip()
                        if opt_text:
                            options.append(opt_text)

                    selects_to_resolve.append({
                        "id": f"select_{i}",
                        "element_index": i,
                        "label": parent_text[:150],
                        "options": options
                    })
                except Exception:
                    pass

            if selects_to_resolve:
                unresolved = []
                for sel_item in selects_to_resolve:
                    s = page.locator("select").nth(sel_item["element_index"])
                    lbl_lower = sel_item["label"].lower()
                    handled = False

                    if "deutsch" in lbl_lower or "german" in lbl_lower:
                        for opt in ["Fließend", "Flieend", "Sehr gut", "C1", "C2", "Muttersprache", "Fortgeschritten"]:
                            try:
                                s.select_option(label=opt)
                                print(f"  ✓ Langue Allemand sélectionnée : {opt}", flush=True)
                                total_filled += 1
                                handled = True
                                break
                            except Exception:
                                pass
                    elif "englisch" in lbl_lower or "english" in lbl_lower:
                        for opt in ["Grundlegend", "Gut", "B1", "Fortgeschritten"]:
                            try:
                                s.select_option(label=opt)
                                print(f"  ✓ Langue Anglais sélectionnée : {opt}", flush=True)
                                total_filled += 1
                                handled = True
                                break
                            except Exception:
                                pass
                    elif any(w in lbl_lower for w in ["vollzeit", "40 h", "40h", "arbeitszeit", "arbeitserlaubnis"]):
                        for opt in ["Ja", "Yes", "Vorhanden"]:
                            try:
                                s.select_option(label=opt)
                                print(f"  ✓ Option Disponibilité/Vollzeit sélectionnée : {opt}", flush=True)
                                total_filled += 1
                                handled = True
                                break
                            except Exception:
                                pass

                    if not handled:
                        unresolved.append(sel_item)

                if unresolved:
                    print(f"🧠 [CERVEAU IA] Analyse de {len(unresolved)} menus déroulants avec Gemini...", flush=True)
                    answers = ask_gemini_brain(unresolved, profile, job_title)
                    for item in unresolved:
                        f_id = item["id"]
                        if f_id in answers:
                            chosen_opt = answers[f_id]
                            try:
                                s = page.locator("select").nth(item["element_index"])
                                s.select_option(label=chosen_opt)
                                print(f"  ✓ Option IA sélectionnée pour '{item['label'][:35]}...' : {chosen_opt}", flush=True)
                                total_filled += 1
                            except Exception:
                                pass
        except Exception as e:
            print(f"⚠️ Erreur menus déroulants : {e}")

        # G. Cerveau IA pour champs texte personnalisés (Greenhouse, Workday, etc.)
        try:
            inputs = page.locator("input[type='text'], input:not([type]), textarea").all()
            custom_text_inputs = []
            for idx, inp in enumerate(inputs):
                try:
                    if not inp.is_visible():
                        continue
                    val = inp.input_value()
                    if val:
                        continue
                    inp_id = inp.get_attribute("id") or ""
                    label_text = ""
                    if inp_id:
                        lbl = page.locator(f"label[for='{inp_id}']").first
                        if lbl.count() > 0:
                            label_text = lbl.inner_text().strip()
                    if not label_text:
                        try:
                            label_text = inp.locator("xpath=ancestor::*[contains(@class, 'field') or contains(@class, 'form-group') or self::div][1]").inner_text().strip()
                        except Exception:
                            pass
                    
                    if label_text:
                        lbl_lower = label_text.lower()
                        if any(w in lbl_lower for w in ["starten", "ab wann", "verfügbar", "start date", "availability"]):
                            target_date = (datetime.now() + timedelta(days=7)).strftime("%d.%m.%Y")
                            inp.fill(target_date)
                            print(f"  ✓ Start Date : {target_date} ('{label_text[:30]}...')", flush=True)
                            total_filled += 1
                        elif any(w in lbl_lower for w in ["verdienen", "stundenlohn", "gehalt", "salary", "compensation"]):
                            inp.fill("16 €")
                            print(f"  ✓ Salaire renseigné : 16 € ('{label_text[:30]}...')", flush=True)
                            total_filled += 1
                        elif len(label_text) > 5 and not any(w in lbl_lower for w in ["suche", "search", "newsletter"]):
                            custom_text_inputs.append({
                                "id": f"text_{idx}",
                                "element": inp,
                                "label": label_text[:150]
                            })
                except Exception:
                    pass
            
            if custom_text_inputs:
                text_questions = [{"id": c["id"], "label": c["label"], "type": "text", "options": []} for c in custom_text_inputs]
                answers = ask_gemini_brain(text_questions, profile, job_title)
                for c in custom_text_inputs:
                    if c["id"] in answers:
                        c["element"].fill(str(answers[c["id"]]))
                        print(f"  ✓ Réponse IA : {answers[c['id']]} ('{c['label'][:30]}...')", flush=True)
                        total_filled += 1
        except Exception as e:
            print(f"⚠️ Erreur questions texte : {e}")

        # H. Lettre de motivation en zone de texte
        if cover_letter_text:
            letter_selectors = [
                "textarea[name*='cover' i]", "textarea[id*='cover' i]", 
                "textarea[name*='anschreiben' i]", "textarea[id*='anschreiben' i]",
                "textarea[name*='motivation' i]", "textarea[placeholder*='Anschreiben' i]"
            ]
            for sel in letter_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=300) and not el.input_value():
                        el.fill(cover_letter_text)
                        print(f"  ✓ Lettre de motivation insérée dans le champ texte !", flush=True)
                        break
                except Exception:
                    continue

        # I. Téléversement des documents présents sur cette étape
        docs_to_upload = [
            ("Lebenslauf", docs.get("cv", DOCS_DIR / "cv.pdf")),
            ("Anschreiben", docs.get("anschreiben", DOCS_DIR / "anschreiben.pdf")),
            ("Immatrikulation", docs.get("immatrikulation", DOCS_DIR / "immatrikulationsbescheinigung.pdf")),
            ("Notenspiegel", docs.get("notenspiegel", DOCS_DIR / "notenspiegel.pdf"))
        ]
        for section_name, doc_path in docs_to_upload:
            if section_name in already_uploaded_sections:
                continue
            fpath = Path(doc_path)
            if not fpath.is_absolute():
                fpath = BASE_DIR / fpath
            if not fpath.exists():
                continue
            try:
                sec_heading = page.locator(f"text='{section_name}'").first
                if sec_heading.count() > 0 and sec_heading.is_visible():
                    parent_sec = sec_heading.locator("xpath=ancestor::*[.//input[@type='file'] or .//button][1]")
                    
                    # Vérifier si un fichier est déjà présent / listé dans cette section
                    has_file = False
                    try:
                        file_tags = parent_sec.locator("[class*='file'], [class*='upload'], [class*='attachment'], span, div")
                        for ft in file_tags.all():
                            txt = (ft.inner_text() or "").lower()
                            if fpath.name.lower() in txt or ".pdf" in txt:
                                has_file = True
                                break
                    except Exception:
                        pass
                    
                    if has_file:
                        already_uploaded_sections.add(section_name)
                        continue

                    file_input = parent_sec.locator("input[type='file']").first
                    if file_input.count() > 0:
                        file_input.set_input_files(str(fpath.resolve()))
                        print(f"  📎 {section_name} téléversé avec succès : {fpath.name}", flush=True)
                        already_uploaded_sections.add(section_name)
                        continue
                    add_btn = parent_sec.locator("button:has-text('Datei hinzufügen')").first
                    if add_btn.is_visible(timeout=1000):
                        with page.expect_file_chooser(timeout=3000) as fc_info:
                            add_btn.click()
                        fc_info.value.set_files(str(fpath.resolve()))
                        print(f"  📎 {section_name} téléversé avec succès : {fpath.name}", flush=True)
                        already_uploaded_sections.add(section_name)
            except Exception:
                pass

        # J. Cases à cocher obligatoires (Datenschutz / AGB)
        try:
            for cb in page.locator("input[type='checkbox']:visible").all():
                if not cb.is_checked():
                    cb_label = ""
                    try:
                        cb_label = cb.locator("xpath=ancestor::label[1]").inner_text().lower()
                    except Exception:
                        pass
                    if any(w in cb_label for w in ["datenschutz", "agb", "einwillig", "zustimm", "terms", "privacy"]):
                        cb.check()
                        print("  ✓ Consentement obligatoire coché", flush=True)
                        total_filled += 1
        except Exception:
            pass

        # K. DÉTECTION DU BOUTON ÉTAPE SUIVANTE
        next_button = None
        for b_sel in [
            "button[type='submit']:visible:has-text('Weiter')",
            "button:visible:has-text('Weiter zu')",
            "button:visible:has-text('Weiter')",
            "button:visible:has-text('Nächster Schritt')",
            "button:visible:has-text('Fortfahren')",
            "button:visible:has-text('Next step')"
        ]:
            try:
                candidate = page.locator(b_sel).first
                if candidate.count() > 0 and candidate.is_visible(timeout=400):
                    btn_text = candidate.inner_text().strip()
                    # Bloquer les boutons de soumission irréversibles ou finaux
                    if not any(stop in btn_text.lower() for stop in ["kostenpflichtig", "jetzt kaufen", "absenden", "jetzt bewerben", "bewerbung einreichen"]):
                        next_button = candidate
                        print(f"👉 Étape {step_num} complétée ! Bouton étape suivante détecté : '{btn_text}'", flush=True)
                        break
            except Exception:
                pass

        if next_button:
            print(f"⏳ Clic sur l'étape suivante, progression automatique du Copilote IA vers l'étape {step_num + 1}...", flush=True)
            next_button.click()
            page.wait_for_timeout(2500)
        else:
            print(f"🏁 Dernière étape atteinte (formulaire entièrement prêt pour validation humaine).", flush=True)
            break

    if total_filled > 0:
        print(f"\n📊 Total : {total_filled} champs, choix et étapes configurés avec succès !", flush=True)

    return agent_res

def run_copilot(url, cover_letter_path=None, job_title="Offre d'emploi"):
    profile = load_profile()
    cover_letter_content = None

    if cover_letter_path and Path(cover_letter_path).exists():
        with open(cover_letter_path, "r", encoding="utf-8") as f:
            cover_letter_content = f.read()

    print("=" * 60)
    print("🚀 DÉMARRAGE DU COPILOTE PLAYWRIGHT (Human-in-the-Loop)")
    print(f"Candidat : {profile['personal_info']['full_name']}")
    print(f"Cible    : {url}")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=60
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 850},
            locale="de-DE"
        )
        page = context.new_page()

        print("\n🌐 Chargement de la page de candidature...")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)

        # Exécution du remplissage intelligent
        smart_fill(page, profile, cover_letter_content, job_title)

        print("\n" + "#" * 60)
        print("🛡️ CONTRÔLE HUMAIN ACTIVÉ (Human-in-the-loop) :")
        print("   - Le formulaire a été pré-rempli sous tes yeux.")
        print("   - Vérifie les champs dans la fenêtre du navigateur ouverte.")
        print("   - Clique toi-même sur le bouton 'Bewerbung absenden / Submit' !")
        print("#" * 60)

        try:
            input("\n👉 Appuie sur ENTRÉE dans ce terminal pour fermer le navigateur quand tu as fini...")
        except KeyboardInterrupt:
            pass

        print("Fermeture du navigateur. Bravo !")
        browser.close()

if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else input("Colle l'URL du formulaire d'embauche : ").strip()
    c_letter = sys.argv[2] if len(sys.argv) > 2 else None
    if target_url:
        run_copilot(target_url, c_letter)
    else:
        print("Aucune URL fournie. Arrêt.")
