"""
Architectural Terminal Guard (Human Gate)
Ensures NO autonomous execution can click, submit, or commit an application
without explicit Human Approval. The LLM NEVER holds final submission authority.
"""
import re
from typing import Optional, Set
from .action_schema import IndexedElement, Action, ActionType


class HumanApprovalRequired(Exception):
    """Raised whenever an action attempts to trigger a terminal/final submission."""
    def __init__(self, message: str, element: Optional[IndexedElement] = None):
        super().__init__(message)
        self.element = element


# Terminal patterns (German, English, French) indicating irreversible submission, application dispatch, or purchase
TERMINAL_PATTERNS: Set[str] = {
    # German - Final Application & Legal Actions
    r"jetzt\s+bewerben",
    r"bewerbung\s+senden",
    r"bewerbung\s+absenden",
    r"bewerbung\s+abschicken",
    r"bewerbung\s+einreichen",
    r"unterlagen\s+senden",
    r"unterlagen\s+einreichen",
    r"kostenpflichtig\s+bestellen",
    r"kostenpflichtig\s+anmelden",
    r"zahlungspflichtig\s+bestellen",
    r"zahlungspflichtig\s+buchen",
    r"verbindlich\s+buchen",
    r"jetzt\s+kaufen",
    r"jetzt\s+registrieren\s+und\s+absenden",
    r"anmeldung\s+abschlie(ss|ß)en",
    r"registrierung\s+abschlie(ss|ß)en",
    r"profil\s+freigeben",
    r"absenden\s*$",
    r"^absenden",
    r"^bewerben\s*$",
    r"^senden\s*$",

    # English - Final Application & Submission
    r"submit\s+application",
    r"send\s+application",
    r"apply\s+now",
    r"complete\s+application",
    r"submit\s+my\s+application",
    r"place\s+order",
    r"confirm\s+and\s+submit",
    r"finish\s+and\s+submit",
    r"pay\s+now",
    r"^submit\s*$",

    # French - Final Application & Validation
    r"postuler\s+maintenant",
    r"envoyer\s+ma\s+candidature",
    r"envoyer\s+la\s+candidature",
    r"valider\s+la\s+candidature",
    r"soumettre\s+ma\s+candidature",
    r"soumettre\s+la\s+candidature",
    r"confirmer\s+l'envoi",
    r"valider\s+et\s+payer",
    r"^postuler\s*$",
}

COMPILED_TERMINAL_REGEXES = [re.compile(p, re.IGNORECASE) for p in TERMINAL_PATTERNS]

# Non-terminal transitional patterns (these are allowed for multi-step wizards)
NON_TERMINAL_STEP_PATTERNS = [
    r"weiter",
    r"n(ä|ae)chster\s+schritt",
    r"next",
    r"continue",
    r"suivant",
    r"étape\s+suivante",
    r"zur\s+auswahl",
    r"fortfahren",
    r"speichern\s+und\s+weiter",
]
COMPILED_NON_TERMINAL_REGEXES = [re.compile(p, re.IGNORECASE) for p in NON_TERMINAL_STEP_PATTERNS]


def is_terminal_element(element: IndexedElement) -> bool:
    """
    Evaluates whether an interactive element is a terminal (final submission) trigger.
    Inspects text, aria-label, name, value, and attributes.
    """
    combined_texts = [
        element.text or "",
        element.aria_label or "",
        element.name or "",
        element.value or "",
        str(element.attributes.get("id", "")),
        str(element.attributes.get("title", "")),
        str(element.attributes.get("data-testid", "")),
    ]
    full_string = " ".join(combined_texts).strip().lower()

    if not full_string:
        return False

    # 0. Entry buttons that reveal or scroll to the form are NEVER terminal
    if any(entry in full_string for entry in [
        "auf diese stelle bewerben",
        "zur bewerbung",
        "online-bewerbung",
        "start application",
        "#apply"
    ]):
        return False

    # 1. If it explicitly matches a forward-stepping wizard pattern (e.g. "Weiter zur nächsten Seite"), it is non-terminal
    for step_rx in COMPILED_NON_TERMINAL_REGEXES:
        if step_rx.search(full_string):
            # However, if it says "Weiter zur Bewerbung absenden", check terminal
            if not any(term_rx.search(full_string) for term_rx in COMPILED_TERMINAL_REGEXES):
                return False

    # 2. Check terminal patterns
    for term_rx in COMPILED_TERMINAL_REGEXES:
        if term_rx.search(full_string):
            return True

    # 3. Check submit button type with final phrasing (MUST be final submission, not entry)
    if element.element_type == "submit" or (element.tag == "button" and "type='submit'" in str(element.attributes)):
        if any(w in full_string for w in ["absenden", "abschicken", "einreichen", "submit application", "send application", "valider"]):
            return True

    return False


def verify_non_terminal_action(action: Action, element: Optional[IndexedElement] = None) -> None:
    """
    Hard verification: raises HumanApprovalRequired if action targets a terminal element.
    """
    if action.action_type in (ActionType.REQUEST_HUMAN_APPROVAL,):
        raise HumanApprovalRequired("Action is explicitly requesting human approval.", element)

    if element and is_terminal_element(element):
        reason = f"Element [{element.id}] ('{element.text or element.name}') is a TERMINAL submission button."
        raise HumanApprovalRequired(reason, element)
