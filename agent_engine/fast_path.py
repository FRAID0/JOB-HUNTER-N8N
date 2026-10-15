"""
Fast-Path Engine (Level 0 & Level 1)
Implements deterministic and heuristic auto-filling without consuming LLM tokens.

Level 0 - Deterministic: Vorname, Nachname, E-Mail, Telefon, Adresse, CV upload.
Level 1 - Smart DOM Heuristics: Geburtsdatum, LinkedIn, Eintrittstermin, Erfahrung.
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from .action_schema import Action, ActionType, IndexedElement
from .document_hub import DocumentHub


# Level 0 Deterministic Field Matchers
LEVEL_0_PATTERNS = {
    "first_name": [r"vorname", r"first[\s_-]?name", r"pr(é|e)nom", r"given[\s_-]?name"],
    "last_name": [r"nachname", r"last[\s_-]?name", r"nom\s*(\b|de\s*famille)", r"family[\s_-]?name", r"surename"],
    "full_name": [r"^name$", r"voller\s+name", r"full[\s_-]?name", r"nom\s+complet"],
    "email": [r"e[\s_-]?mail", r"courriel"],
    "phone": [r"telefon", r"telephone", r"phone", r"mobil(?!ity)", r"handy", r"contact[\s_-]?number"],
    "mobility": [r"mobility", r"arbeitsst(ä|ae)tte", r"regionen", r"einsatzort"],
    "internship_duration": [r"dauer.*praktikum", r"praktikumsdauer", r"duration"],
    "street": [r"stra(ss|ß)e", r"street", r"rue", r"address[\s_-]?line"],
    "zip": [r"plz", r"postleitzahl", r"zip", r"postal[\s_-]?code", r"code[\s_-]?postal"],
    "city": [r"stadt", r"ort", r"city", r"ville"],
    "start_date": [r"available", r"verf(ü|ue)g", r"eintritt", r"start[\s_-]?date", r"ab\s+wann", r"disponib"],
    "salary": [r"gehalt", r"salary", r"verg(ü|ue)tung", r"remuneration", r"stundenlohn", r"compensation"],
    "cv_upload": [r"lebenslauf", r"cv", r"resume", r"curriculum", r"bewerbungsunterlagen"],
}

# Level 1 Smart Heuristic Matchers
LEVEL_1_PATTERNS = {
    "linkedin": [r"linkedin", r"profil[\s_-]?link"],
    "github": [r"github", r"portfolio"],
    "birthdate": [r"geburtsdatum", r"birth[\s_-]?date", r"date\s+de\s+naissance"],
    "start_date": [r"available", r"eintritt", r"start[\s_-]?date", r"verf(ü|ue)g", r"ab\s+wann", r"disponibilit(é|e)"],
    "salary": [r"gehalt", r"salary", r"verg(ü|ue)tung", r"remuneration", r"stundenlohn", r"compensation"],
    "experience_years": [r"berufserfahrung", r"years\s+of\s+experience", r"ann(é|e)es\s+d'exp(é|e)rience"],
}


class FastPathEngine:
    def __init__(self, profile_data: dict, cv_path: Optional[str] = None, docs_dir: str = "d:/N8N/documents"):
        self.profile = profile_data
        self.cv_path = cv_path
        self.docs_dir = docs_dir
        self.doc_hub = DocumentHub(docs_dir=docs_dir)
        self.uploaded_element_ids: set[int] = set()
        self.uploaded_categories: set[str] = set()

    def _match_field(self, element: IndexedElement, pattern_dict: dict) -> Optional[str]:
        target_texts = [
            element.name or "",
            element.placeholder or "",
            element.aria_label or "",
            str(element.attributes.get("id", "")),
            element.text or "",
        ]
        combined = " ".join(target_texts).lower()

        for field_key, regex_list in pattern_dict.items():
            for rx_pattern in regex_list:
                if re.search(rx_pattern, combined, re.IGNORECASE):
                    return field_key
        return None

    def plan_fast_actions(self, elements: List[IndexedElement]) -> List[Action]:
        """
        Analyzes interactive elements and produces a list of deterministic (L0)
        and heuristic (L1) actions for matching empty fields.
        """
        actions: List[Action] = []
        already_handled_elements = set()

        # --- LEVEL 0: Form Entry Button (e.g. 'Auf diese Stelle bewerben' on Personio) ---
        # When no inputs/textareas are present on the current view, click the entry button to reveal the form
        has_form_fields = any(
            el.tag.lower() in ["input", "textarea"] and (el.element_type or "").lower() not in ["hidden", "submit", "button"]
            for el in elements
        )
        if not has_form_fields:
            for el in elements:
                if el.is_visible and not el.is_terminal and el.tag.lower() in ["button", "a"]:
                    txt = (el.text or "").strip().lower()
                    if any(p in txt for p in ["auf diese stelle bewerben", "jetzt bewerben", "bewerben", "apply now", "zur bewerbung", "apply for this job"]):
                        return [Action(
                            action_type=ActionType.CLICK,
                            element_id=el.id,
                            reasoning=f"Level 0 Deterministic: Click entry button '{el.text.strip()}' to reveal application form",
                        )]

        for el in elements:
            if not el.is_visible or el.is_terminal:
                continue

            # Skip inputs that are already filled
            if el.value and len(str(el.value).strip()) > 0:
                continue

            tag = el.tag.lower()
            el_type = (el.element_type or "").lower()

            # --- LEVEL 0: File Uploads (Lebenslauf, Zeugnisse, Anschreiben) ---
            if tag == "input" and el_type == "file":
                if el.id in self.uploaded_element_ids:
                    continue
                doc_path = self._resolve_file_upload(el)
                if doc_path and os.path.exists(doc_path):
                    doc_fname = os.path.basename(doc_path).lower()
                    is_cv = "cv" in doc_fname or "lebenslauf" in doc_fname
                    if is_cv and "cv" in self.uploaded_categories:
                        # Un CV a déjà été uploadé : ne jamais le dupliquer !
                        continue

                    actions.append(Action(
                        action_type=ActionType.UPLOAD,
                        element_id=el.id,
                        value=doc_path,
                        reasoning=f"Level 0 Deterministic: Upload {os.path.basename(doc_path)} into [{el.id}]",
                    ))
                    self.uploaded_element_ids.add(el.id)
                    already_handled_elements.add(el.id)
                    if is_cv:
                        self.uploaded_categories.add("cv")
                    if "anschreiben" in doc_fname or "cover" in doc_fname:
                        self.uploaded_categories.add("anschreiben")
                    el_combined = f"{el.name or ''} {el.placeholder or ''} {el.aria_label or ''} {el.text or ''}".lower()
                    if any(w in el_combined for w in ["andere", "sonstige", "optional", "other"]):
                        self.uploaded_categories.add("andere")
                    self.uploaded_categories.add(doc_fname)
                    continue

            # --- LEVEL 0: Textarea (Motivation / Kurz zu dir) ---
            if tag == "textarea":
                t_match = self._match_field(el, {
                    "short_bio": [r"kurz\s+zu\s+dir", r"unterrichtserfahrung", r"motivation", r"warum", r"beschreibung", r"über\s+dich", r"about\s+you"]
                })
                if t_match:
                    bio = (
                        "Als engagierter Student der Angewandten Informatik bringe ich fundierte Kenntnisse "
                        "in Informatik, Mathematik und Sprachen mit. Dank meiner geduldigen und strukturierten "
                        "Arbeitsweise kann ich Lerninhalte verständlich vermitteln und Schüler nachhaltig motivieren."
                    )
                    actions.append(Action(
                        action_type=ActionType.TYPE,
                        element_id=el.id,
                        value=bio,
                        reasoning=f"Level 0 Deterministic: Pre-filled short bio/motivation into [{el.id}]",
                    ))
                    already_handled_elements.add(el.id)
                    continue

            # --- LEVEL 0: Password fields (Candidate account portals only, never platform logins) ---
            if tag == "input" and el_type == "password":
                el_ctx = f"{el.name} {el.placeholder} {el.aria_label}".lower()
                if not any(ign in el_ctx for ign in ["current-password", "session_password", "login-password", "login_password"]):
                    pwd = self.profile.get("default_password", "Candidate@Secure2026!")
                    actions.append(Action(
                        action_type=ActionType.TYPE,
                        element_id=el.id,
                        value=pwd,
                        reasoning=f"Level 0 Deterministic: Pre-filled default password into element [{el.id}]",
                    ))
                    already_handled_elements.add(el.id)
                    continue

            # --- LEVEL 0: Pill / Option Buttons (Subjects, Languages, Preferences) ---
            if tag == "button" and not el.is_terminal and not el.is_selected:
                btn_class = str(el.attributes.get("class", "")).lower()
                if any(ign in btn_class for ign in ["localeswitcher", "language", "sprachauswahl", "header", "nav", "dropdown"]):
                    continue
                btn_txt = el.text.strip()
                if btn_txt and not any(nav in btn_txt.lower() for nav in ["weiter", "zurück", "abbrechen", "schritt", "next", "continue", "speichern"]):
                    subj_targets = [s.lower() for s in self.profile.get("preferred_subjects", [])]
                    lang_targets = [l.lower() for l in self.profile.get("teaching_languages", [])]
                    qual_targets = ["student:in", "student", "bachelor student", "immatrikulierter student"]
                    all_targets = set(subj_targets + lang_targets + qual_targets + ["informatik", "mathematik", "französisch", "deutsch", "englisch"])
                    if btn_txt.lower() in all_targets:
                        actions.append(Action(
                            action_type=ActionType.CLICK,
                            element_id=el.id,
                            reasoning=f"Level 0 Deterministic: Selected skill/language/qualification pill '{btn_txt}' [{el.id}]",
                        ))
                        already_handled_elements.add(el.id)
                        continue

            # --- LEVEL 0: Select Menus (Salutation, Country, Phone Prefix, Wohnort, German Level) ---
            if tag == "select":
                combined = f"{el.name or ''} {el.aria_label or ''} {el.text or ''}".lower()
                if any(w in combined for w in ["anrede", "salutation", "geschlecht"]):
                    actions.append(Action(
                        action_type=ActionType.SELECT,
                        element_id=el.id,
                        value="Herr",
                        reasoning=f"Level 0 Deterministic: Selected 'Herr' for [{el.id}]",
                    ))
                    already_handled_elements.add(el.id)
                    continue
                if any(w in combined for w in ["wohnort", "wohnsitz", "leben sie in deutschland"]):
                    actions.append(Action(
                        action_type=ActionType.SELECT,
                        element_id=el.id,
                        value="Ja",
                        reasoning=f"Level 0 Deterministic: Selected 'Ja' for Wohnort Deutschland [{el.id}]",
                    ))
                    already_handled_elements.add(el.id)
                    continue
                if any(w in combined for w in ["deutsch", "german"]) and any(w in combined for w in ["sprach", "kenntnis", "level", "niveau"]):
                    chosen_de = "Fachkundige Sprachkenntnisse (C1)"
                    for opt in (el.options or []):
                        if any(k in opt.lower() for k in ["c1", "fachkundig", "fließend", "flieend", "sehr gut"]):
                            chosen_de = opt
                            break
                    actions.append(Action(
                        action_type=ActionType.SELECT,
                        element_id=el.id,
                        value=chosen_de,
                        reasoning=f"Level 0 Deterministic: Selected '{chosen_de}' for German proficiency [{el.id}]",
                    ))
                    already_handled_elements.add(el.id)
                    continue
                if any(w in combined for w in ["country", "land", "staat"]) and "code" not in combined:
                    actions.append(Action(
                        action_type=ActionType.SELECT,
                        element_id=el.id,
                        value="Deutschland",
                        reasoning=f"Level 0 Deterministic: Selected 'Deutschland' for [{el.id}]",
                    ))
                    already_handled_elements.add(el.id)
                    continue
                if any(w in combined for w in ["countrycode", "vorwahl", "dialing"]):
                    actions.append(Action(
                        action_type=ActionType.SELECT,
                        element_id=el.id,
                        value="Deutschland (49)",
                        reasoning=f"Level 0 Deterministic: Selected country dialing prefix for [{el.id}]",
                    ))
                    already_handled_elements.add(el.id)
                    continue

            # --- LEVEL 0: Checkboxes (Mandatory Privacy / Terms) ---
            if tag == "input" and el_type == "checkbox" and not el.is_selected:
                combined = f"{el.name or ''} {el.aria_label or ''} {el.text or ''}".lower()
                if any(w in combined for w in ["datenschutz", "privacy", "agb", "terms", "einwillig", "zustimm"]):
                    actions.append(Action(
                        action_type=ActionType.CLICK,
                        element_id=el.id,
                        reasoning=f"Level 0 Deterministic: Checked mandatory consent [{el.id}]",
                    ))
                    already_handled_elements.add(el.id)
                    continue

            # --- LEVEL 0: Radio Buttons (Languages, Internship, Channel, Talentpool) ---
            if tag == "input" and el_type == "radio" and not el.is_selected:
                txt = (el.text or "").lower()

                # Questions about current employment / employee referral -> Answer "Nein"
                if any(w in txt for w in ["aktuell bei", "bereits beschäftigt", "belegschaft", "empfehlung durch (ehemaligen)"]):
                    if any(w in txt for w in ["nein", "no"]):
                        actions.append(Action(
                            action_type=ActionType.CLICK,
                            element_id=el.id,
                            reasoning=f"Level 0 Deterministic: Not currently employed / internal referral [{el.id}]",
                        ))
                        already_handled_elements.add(el.id)
                        continue

                # Pflichtpraktikum -> Ja
                if any(w in txt for w in ["pflichtpraktikum", "pflicht-praktikum", "mandatory internship"]):
                    if any(w in txt for w in ["ja", "yes"]):
                        actions.append(Action(
                            action_type=ActionType.CLICK,
                            element_id=el.id,
                            reasoning=f"Level 0 Deterministic: Confirmed Pflichtpraktikum 'Ja' [{el.id}]",
                        ))
                        already_handled_elements.add(el.id)
                        continue

                # English level (B1/B2)
                if any(lvl in txt for lvl in ["b1 — fortgeschrittene", "b1", "b2", "fortgeschrittene sprachverwendung"]):
                    actions.append(Action(
                        action_type=ActionType.CLICK,
                        element_id=el.id,
                        reasoning=f"Level 0 Deterministic: Selected English proficiency [{el.id}]",
                    ))
                    already_handled_elements.add(el.id)
                    continue

                # German level (Sehr gut / Fließend / TestDaF)
                if any(lvl in txt for lvl in ["sehr gute kenntnisse", "sehr gut", "fließend", "verhandlungssicher"]):
                    actions.append(Action(
                        action_type=ActionType.CLICK,
                        element_id=el.id,
                        reasoning=f"Level 0 Deterministic: Selected German proficiency [{el.id}]",
                    ))
                    already_handled_elements.add(el.id)
                    continue

                # Source / Referral -> LinkedIn / Jobbörse / Homepage
                if any(src in txt for src in ["jobbörse", "linkedin", "homepage", "internetrecherche"]):
                    actions.append(Action(
                        action_type=ActionType.CLICK,
                        element_id=el.id,
                        reasoning=f"Level 0 Deterministic: Selected referral channel [{el.id}]",
                    ))
                    already_handled_elements.add(el.id)
                    continue

                # Alternative jobs pool / Talentpool -> Consent
                if any(p in txt for p in ["alternative stellen", "konzernweit", "talentpool", "talent-pool"]):
                    if not any(neg in txt for neg in ["nur für die stelle", "keine prüfung", "nicht zugänglich"]):
                        actions.append(Action(
                            action_type=ActionType.CLICK,
                            element_id=el.id,
                            reasoning=f"Level 0 Deterministic: Selected talentpool consent [{el.id}]",
                        ))
                        already_handled_elements.add(el.id)
                        continue

            # --- LEVEL 0: Text Inputs ---
            if tag in ("input", "textarea") and el_type not in ("file", "checkbox", "radio", "submit", "button", "password"):
                l0_match = self._match_field(el, LEVEL_0_PATTERNS)
                if l0_match:
                    val = self._resolve_l0_value(l0_match)
                    if val:
                        actions.append(Action(
                            action_type=ActionType.TYPE,
                            element_id=el.id,
                            value=val,
                            reasoning=f"Level 0 Deterministic: Filled '{l0_match}' into element [{el.id}]",
                        ))
                        already_handled_elements.add(el.id)
                        continue

                # --- LEVEL 1: Smart Heuristics ---
                l1_match = self._match_field(el, LEVEL_1_PATTERNS)
                if l1_match:
                    val = self._resolve_l1_value(l1_match)
                    if val:
                        actions.append(Action(
                            action_type=ActionType.TYPE,
                            element_id=el.id,
                            value=val,
                            reasoning=f"Level 1 Heuristic: Filled '{l1_match}' into element [{el.id}]",
                        ))
                        already_handled_elements.add(el.id)
                        continue

        return actions

    def _resolve_file_upload(self, el: IndexedElement) -> Optional[str]:
        combined = f"{el.name or ''} {el.placeholder or ''} {el.aria_label or ''} {el.text or ''}".lower()

        # Si c'est un champ additionnel ("Andere", "Sonstige", "Optional", "Other", "Weitere", etc.) :
        # On téléverse la lettre de motivation personnalisée (anschreiben.pdf) si disponible, sinon les diplômes (zeugnisse).
        if any(w in combined for w in ["andere", "sonstige", "optional", "weitere", "zusatz", "other"]):
            if "andere" in self.uploaded_categories:
                return None
            docs = self.profile.get("documents", {})
            # 1. Priorité absolue : Anschreiben (lettre de motivation personnalisée DIN 5008)
            ans = docs.get("anschreiben") or (Path(self.docs_dir) / "anschreiben.pdf")
            if ans and os.path.exists(ans) and "anschreiben" not in self.uploaded_categories:
                return str(Path(ans).resolve())
            # 2. Deuxième choix : Zeugnisse / Notenspiegel (si pas d'anschreiben)
            for key in ["zeugnisse", "notenspiegel"]:
                target = docs.get(key)
                if target and os.path.exists(target) and "zeugnisse" not in self.uploaded_categories:
                    return str(Path(target).resolve())
            return None

        # 1. Primary: Semantic DocumentHub resolution across all indexed files
        resolved = self.doc_hub.resolve_document(combined)
        if resolved and resolved.exists():
            fname = resolved.name.lower()
            if "cv" in fname or "lebenslauf" in fname:
                if "cv" in self.uploaded_categories:
                    return None
                return str(resolved.resolve())
            elif fname not in self.uploaded_categories:
                return str(resolved.resolve())

        # 2. Direct dictionary fallback pour Zeugnisse / Notenspiegel
        docs = self.profile.get("documents", {})
        if any(w in combined for w in ["zeugnis", "notenspiegel", "qualifikation", "transcript"]):
            if "zeugnisse" not in self.uploaded_categories:
                target = docs.get("zeugnisse") or docs.get("notenspiegel")
                if target and os.path.exists(target):
                    return str(Path(target).resolve())

        # 3. Direct dictionary fallback pour Anschreiben
        if any(w in combined for w in ["anschreiben", "cover", "motivation", "letter"]):
            if "anschreiben" not in self.uploaded_categories:
                ans = docs.get("anschreiben") or (Path(self.docs_dir) / "anschreiben.pdf")
                if ans and os.path.exists(ans):
                    return str(Path(ans).resolve())

        # 4. CV UNIQUEMENT si le champ demande explicitement le CV et qu'il n'a pas encore été envoyé
        if any(w in combined for w in ["cv", "lebenslauf", "resume", "curriculum", "werdegang", "profil", "bewerbungsunterlagen"]):
            if "cv" not in self.uploaded_categories:
                if self.cv_path and os.path.exists(self.cv_path):
                    return str(Path(self.cv_path).resolve())
                if docs.get("cv") and os.path.exists(docs.get("cv")):
                    return str(Path(docs.get("cv")).resolve())

        return None

    def _resolve_l0_value(self, field_key: str) -> Optional[str]:
        p = self.profile.get("personal_info", self.profile)
        addr = p.get("address", {})
        cand_k = self.profile.get("candidate_knowledge", {})
        if field_key == "first_name":
            return p.get("first_name") or p.get("vorname") or "Alex"
        if field_key == "last_name":
            return p.get("last_name") or p.get("nachname") or "Dupont"
        if field_key == "full_name":
            return p.get("full_name") or p.get("name") or "Alex Dupont"
        if field_key == "email":
            return p.get("email") or os.environ.get("CANDIDATE_EMAIL") or "candidate@example.com"
        if field_key == "phone":
            return p.get("phone") or p.get("telefon") or os.environ.get("CANDIDATE_PHONE") or "+49 170 0000000"
        if field_key == "street":
            return addr.get("street") or p.get("street") or "Musterstrasse 1"
        if field_key == "zip":
            return addr.get("postal_code") or addr.get("zip") or p.get("postal_code") or p.get("zip") or "10115"
        if field_key == "city":
            return addr.get("city") or p.get("city") or "Berlin"
        if field_key == "mobility":
            return cand_k.get("mobility_locations") or "Flexibel"
        if field_key == "internship_duration":
            return cand_k.get("internship_duration") or "5–6 Monate"
        if field_key == "start_date":
            from datetime import datetime
            now = datetime.now()
            if now.month == 12:
                next_month = datetime(now.year + 1, 1, 1)
            else:
                next_month = datetime(now.year, now.month + 1, 1)
            return next_month.strftime("%d.%m.%Y")
        if field_key == "salary":
            return p.get("expected_salary") or cand_k.get("expected_salary") or "52.000 €"
        return None

    def _resolve_l1_value(self, field_key: str) -> Optional[str]:
        p = self.profile.get("personal_info", self.profile)
        links = p.get("links", {})
        cand_k = self.profile.get("candidate_knowledge", {})
        if field_key == "linkedin":
            return links.get("linkedin") or p.get("linkedin") or os.environ.get("LINKEDIN_URL") or "https://www.linkedin.com/in/example-profile"
        if field_key == "github":
            return links.get("github") or p.get("github") or "https://github.com/example-profile"
        if field_key == "birthdate":
            return p.get("birthdate") or "01.01.1995"
        if field_key == "start_date":
            from datetime import datetime, timedelta
            now = datetime.now()
            # 1er du mois suivant pour format date standard allemand
            if now.month == 12:
                next_month = datetime(now.year + 1, 1, 1)
            else:
                next_month = datetime(now.year, now.month + 1, 1)
            return next_month.strftime("%d.%m.%Y")
        if field_key == "salary":
            return p.get("expected_salary") or cand_k.get("expected_salary") or "52.000 €"
        if field_key == "experience_years":
            return p.get("experience_years") or "3+"
        return None
