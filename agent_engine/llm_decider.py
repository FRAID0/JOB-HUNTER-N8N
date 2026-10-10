"""
LLM Decider (Level 2 Reasoning)
Uses Gemini 3.1 Flash Lite (with fallback) to decide actions on complex,
custom, or multi-step wizard elements when Fast Path does not suffice.
"""
import json
import logging
import os
import re
from typing import Any, List, Optional
import urllib.request
import urllib.error
from .action_schema import Action, ActionType, IndexedElement

logger = logging.getLogger("agent_engine.llm_decider")

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-flash-latest",
]


class LLMDecider:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    def _call_gemini(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")

        import time
        last_error = None
        for model in GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            # Try up to 2 times per model with backoff
            for attempt in range(2):
                try:
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return text
                except Exception as e:
                    last_error = e
                    err_msg = str(e)
                    if "503" in err_msg or "429" in err_msg or "unavailable" in err_msg.lower():
                        time.sleep(1.0 * (attempt + 1))
                        continue
                    else:
                        break
            logger.warning(f"Model {model} failed: {last_error}. Trying next fallback model...")
        raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")

    def decide(
        self,
        goal: str,
        profile_context: str,
        elements_summary: str,
        step_history: Optional[List[str]] = None,
    ) -> List[Action]:
        """
        Asks Gemini to analyze current page elements and decide next action(s).
        Returns a list of parsed Action objects.
        """
        history_txt = "\n".join(step_history) if step_history else "None yet."

        prompt = f"""You are the Action Decision Unit of an Autonomous Job Application Engine.
Your goal: "{goal}"

=== CANDIDATE PROFILE CONTEXT ===
{profile_context}

=== ACTION HISTORY ===
{history_txt}

=== CURRENT PAGE INDEXED ELEMENTS ===
{elements_summary}

=== STRICT INSTRUCTIONS ===
1. Examine the elements above identified by their numeric IDs [1], [2], etc.
2. RESOLVE VALIDATION ERRORS FIRST: If active errors ("Diese Angabe ist erforderlich", "Pflichtfeld", etc.) are displayed, fulfilling those fields is your #1 priority!
3. REASON WITH CANDIDATE KNOWLEDGE:
   - For dropdowns (<select>): match the question label to the Candidate Facts. When options=[...] are visible, pick the exact option matching candidate knowledge:
     * Salutation / Anrede: "Herr"
     * Country / Land: "Deutschland"
     * Dialing Code / Vorwahl: "Deutschland (49)"
     * German Level: "Sehr Gute Kenntnisse" or "Fließend"
     * English Level: "B1 — Fortgeschrittene Sprachverwendung" or "Grundlegende Kenntnisse"
     * Referral channel: "Jobbörse (z. B. StepStone, LinkedIn, Indeed)" or "Internetrecherche/Würth Homepage"
   - For radio buttons and checkboxes:
     * "Handelt es sich um ein Pflichtpraktikum?" -> Select "Ja"
     * "Dauer des Pflichtpraktikums" -> Type "5–6 Monate" (or "6 Monate")
     * Talent Pool / Alternative Stellen consent -> Select "Ja" / consent option ("Mein Profil kann für alternative Stellen... zugänglich gemacht werden")
     * Privacy / Datenschutzerklärung -> Check the consent checkbox
     * Currently employed at company? -> Leave unchecked or "Nein"
     * Referred by internal employee? -> Leave unchecked or "Nein"
   - For text inputs:
     * Preferred locations / Einsatzort / Regionen -> Type "Künzelsau, Baden-Württemberg (mobil & flexibel)"
     * Mandatory internship duration -> Type "5–6 Monate"
4. MULTI-ACTION BATCHING: You can propose MULTIPLE actions in a single response to fill all empty fields, dropdowns, and radios on the current step at once.
5. STEP PROGRESSION & FORM REVEAL:
   - If form input fields (Name, Email, etc.) are NOT yet visible on the page, but an entry button like "Auf diese Stelle bewerben", "Jetzt bewerben", "Bewerben", or "Apply now" is visible, your IMMEDIATE action is to CLICK IT to reveal the application form!
   - When all required fields on the current step are fulfilled, click the Next/Forward button (e.g. "Weiter", "Next", "Fortfahren").
6. CRITICAL RULE (HUMAN GATE): NEVER trigger final submission buttons ("Bewerbung absenden", "Bewerbung abschicken", "Submit application").
   If only terminal buttons remain AND all fields are complete, respond with action_type="request_human_approval".
   NEVER respond with "request_human_approval" if validation errors or unfilled mandatory fields are still visible on screen!
7. Allowed action_types: "type", "click", "select", "upload", "wait", "request_human_approval".
8. Respond ONLY with a valid JSON array of action objects. No markdown ticks, no preamble.

JSON Schema:
[
  {{
    "action_type": "type" | "click" | "select" | "upload" | "wait" | "request_human_approval",
    "element_id": <int or null>,
    "value": "<text to type, option to select, or file path>",
    "reasoning": "<short explanation>"
  }}
]
"""
        try:
            response_text = self._call_gemini(prompt)
        except Exception as err:
            logger.warning(f"LLM Decider unavailable ({err}). Returning empty actions to let FastPath/Human Gate handle.")
            return []

        # Clean JSON markdown fences if present
        clean_text = re.sub(r"^```json\s*", "", response_text.strip(), flags=re.MULTILINE)
        clean_text = re.sub(r"^```\s*", "", clean_text, flags=re.MULTILINE)
        clean_text = clean_text.strip()

        try:
            items = json.loads(clean_text)
            if isinstance(items, dict):
                items = [items]
            actions: List[Action] = []
            for it in items:
                actions.append(Action(
                    action_type=ActionType(it["action_type"]),
                    element_id=it.get("element_id"),
                    value=it.get("value"),
                    reasoning=it.get("reasoning", ""),
                ))
            return actions
        except Exception as e:
            logger.error(f"Failed to parse LLM response into actions: {response_text} | Error: {e}")
            return []
