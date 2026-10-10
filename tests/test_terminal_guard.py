"""
Unit tests for Terminal Guard (Architectural Human Gate)
"""
import unittest
from agent_engine.action_schema import IndexedElement, Action, ActionType
from agent_engine.terminal_guard import (
    is_terminal_element,
    verify_non_terminal_action,
    HumanApprovalRequired,
)


class TestTerminalGuard(unittest.TestCase):
    def test_german_terminal_buttons(self):
        buttons = [
            IndexedElement(id=1, tag="button", text="Jetzt bewerben"),
            IndexedElement(id=2, tag="button", text="Bewerbung absenden"),
            IndexedElement(id=3, tag="button", text="Bewerbung abschicken"),
            IndexedElement(id=4, tag="button", text="Kostenpflichtig bestellen"),
            IndexedElement(id=5, tag="input", element_type="submit", value="Absenden"),
        ]
        for btn in buttons:
            self.assertTrue(is_terminal_element(btn), f"Should detect terminal: {btn.text or btn.value}")

    def test_english_terminal_buttons(self):
        buttons = [
            IndexedElement(id=1, tag="button", text="Submit Application"),
            IndexedElement(id=2, tag="button", text="Apply Now"),
            IndexedElement(id=3, tag="button", text="Complete application"),
            IndexedElement(id=4, tag="button", text="Confirm and Submit"),
        ]
        for btn in buttons:
            self.assertTrue(is_terminal_element(btn), f"Should detect terminal: {btn.text}")

    def test_french_terminal_buttons(self):
        buttons = [
            IndexedElement(id=1, tag="button", text="Postuler maintenant"),
            IndexedElement(id=2, tag="button", text="Envoyer ma candidature"),
            IndexedElement(id=3, tag="button", text="Confirmer l'envoi"),
        ]
        for btn in buttons:
            self.assertTrue(is_terminal_element(btn), f"Should detect terminal: {btn.text}")

    def test_non_terminal_wizard_buttons(self):
        allowed_buttons = [
            IndexedElement(id=10, tag="button", text="Weiter"),
            IndexedElement(id=11, tag="button", text="Nächster Schritt"),
            IndexedElement(id=12, tag="button", text="Next Step"),
            IndexedElement(id=13, tag="button", text="Continue"),
            IndexedElement(id=14, tag="button", text="Étape suivante"),
            IndexedElement(id=15, tag="button", text="Zur Auswahl"),
        ]
        for btn in allowed_buttons:
            self.assertFalse(is_terminal_element(btn), f"Should NOT be terminal: {btn.text}")

    def test_verify_non_terminal_action_raises(self):
        terminal_btn = IndexedElement(id=99, tag="button", text="Jetzt bewerben", is_terminal=True)
        action = Action(action_type=ActionType.CLICK, element_id=99)

        with self.assertRaises(HumanApprovalRequired):
            verify_non_terminal_action(action, terminal_btn)


if __name__ == "__main__":
    unittest.main()
