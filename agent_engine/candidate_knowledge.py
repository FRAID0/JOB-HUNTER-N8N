"""
Candidate Knowledge Base & Reasoning Profile
Structures candidate facts, university status, language proficiency,
legal requirements, and preferences to empower LLM reasoning on ATS questionnaires.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent_engine.candidate_knowledge")


class CandidateKnowledgeBase:
    """
    Centralized knowledge source for candidate reasoning.
    Supplies LLMDecider and FastPathEngine with factual candidate details.
    """

    def __init__(self, profile_data: Optional[Dict[str, Any]] = None, profile_path: str = "d:/N8N/profil.json"):
        if profile_data:
            self.data = profile_data
        else:
            p = Path(profile_path)
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            else:
                self.data = {}

        self.personal_info = self.data.get("personal_info", {})
        self.education = self.data.get("education", {})
        self.languages = self.data.get("languages", {})
        self.knowledge = self.data.get("candidate_knowledge", {})
        self.experience = self.data.get("key_experience", [])
        self.documents = self.data.get("documents", {})

    def to_reasoning_prompt(self, target_job: str = "") -> str:
        """
        Builds a comprehensive reasoning context in German and English
        explaining the candidate's answers to all standard ATS questions.
        """
        first_name = self.personal_info.get("first_name", "Max")
        last_name = self.personal_info.get("last_name", "Mustermann")
        full_name = self.personal_info.get("full_name", f"{first_name} {last_name}")
        salutation = self.knowledge.get("salutation", self.personal_info.get("salutation", "Herr"))
        email = self.personal_info.get("email", "candidate@example.com")
        phone = self.personal_info.get("phone", "+49 170 0000000")
        phone_nat = self.knowledge.get("phone_national", "1700000000")
        country = self.knowledge.get("country", "Deutschland")
        dial_code = self.knowledge.get("country_dial_code", "Deutschland (49)")

        addr = self.personal_info.get("address", {})
        street = addr.get("street", "Musterstrasse 1")
        zip_code = addr.get("postal_code", "10115")
        city = addr.get("city", "Berlin")

        degree = self.education.get("degree", "Bachelor of Science")
        field = self.education.get("field", "Angewandte Informatik")
        uni = self.education.get("university", "Hochschule Worms")
        edu_status = self.knowledge.get("status", "Immatrikulierter Student")

        is_pflicht = "Ja" if self.knowledge.get("is_mandatory_internship", True) else "Nein"
        dauer = self.knowledge.get("internship_duration", "5–6 Monate")
        availability = self.knowledge.get("start_availability", "Ab sofort / Nach Absprache")
        mobility = self.knowledge.get("mobility_locations", "Künzelsau, Region Heilbronn-Franken, Baden-Württemberg (mobil & flexibel)")

        # Languages
        de_info = self.knowledge.get("languages", {}).get("german", {})
        de_level = de_info.get("level_name", "Sehr Gute Kenntnisse")
        de_desc = de_info.get("description", "Sehr gut / Fließend (TestDaF 4)")

        en_info = self.knowledge.get("languages", {}).get("english", {})
        en_level = en_info.get("level_name", "B1 — Fortgeschrittene Sprachverwendung")
        en_desc = en_info.get("description", "Fortgeschrittene Sprachverwendung / Technisches Englisch")

        fr_info = self.knowledge.get("languages", {}).get("french", {})
        fr_level = fr_info.get("level_name", "Muttersprache")

        referral = self.knowledge.get("referral_channel", "Jobbörse (z. B. StepStone, LinkedIn, Indeed)")
        talent_pool = self.knowledge.get("talent_pool_choice_german", "Mein Profil kann für alternative Stellen innerhalb des Unternehmens und der Würth-Gruppe konzernweit zugänglich gemacht werden")
        pitch = self.knowledge.get("short_motivation_pitch", "")

        return f"""CANDIDATE FACTS & DECISION RULES:
1. PERSONAL DETAILS:
   - Full Name: {full_name} (First: {first_name}, Last: {last_name})
   - Salutation / Anrede: "{salutation}"
   - Email: {email}
   - Phone: {phone} (National without country code: {phone_nat})
   - Country / Land: "{country}"
   - Dialing Code / Ländervorwahl: "{dial_code}"
   - Address: {street}, {zip_code} {city}, {country}

2. EDUCATION & STUDENT STATUS:
   - Degree & Field: {degree} in {field} at {uni}
   - Current Status: {edu_status}
   - Handelt es sich um ein Pflichtpraktikum?: "{is_pflicht}" (ALWAYS answer 'Ja' / 'Yes' because the bachelor study regulations require a mandatory practical semester)
   - Dauer des Pflichtpraktikums: "{dauer}" (Fill '5–6 Monate' or '6 Monate')
   - Frühester Starttermin / Verfügbarkeit: "{availability}"

3. LANGUAGE PROFICIENCY (Match to dropdowns/radios):
   - German / Deutsch: "{de_level}" / "{de_desc}" (Select 'Sehr Gute Kenntnisse' or 'Fließend' or 'C1')
   - English / Englisch: "{en_level}" / "{en_desc}" (Select 'B1 — Fortgeschrittene Sprachverwendung' or 'B1' or 'Fortgeschrittene Kenntnisse')
   - French / Französisch: "{fr_level}" (Muttersprache / Native)

4. APPLICATION SPECIFIC QUESTIONS:
   - Wie bist du auf Würth / das Unternehmen aufmerksam geworden?:
     Select "{referral}" or "Internetrecherche/Würth Homepage"
   - Einsatzort / Folgende Orte/Regionen kommen als Arbeitsstätte infrage:
     Fill "{mobility}"
   - Aktuell bei diesem Unternehmen beschäftigt?: "Nein" (Leave unchecked or select 'Nein')
   - Von Person aus der Belegschaft aufmerksam gemacht?: "Nein" (Leave unchecked or select 'Nein')
   - Talentpool / Alternative Stellen consent:
     Consented. Pick option "{talent_pool}".
   - Privacy / Datenschutzerklärung:
     Consented. Check the checkbox for "Ich habe die Datenschutzerklärung gelesen".

5. SHORT MOTIVATION / PITCH:
   "{pitch}"
"""
