"""
Unit tests for Fast-Path Engine (Level 0 Deterministic & Level 1 Heuristic)
"""
import unittest
from agent_engine.action_schema import IndexedElement, ActionType
from agent_engine.fast_path import FastPathEngine


class TestFastPathEngine(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "first_name": "Alex",
            "last_name": "Dupont",
            "email": "alex.dupont@example.com",
            "phone": "+49 176 12345678",
            "city": "Berlin",
            "linkedin": "https://linkedin.com/in/alexdupont",
            "birthdate": "15.04.1994",
        }
        self.cv_path = "d:/N8N/documents/cv.pdf"
        self.fast_path = FastPathEngine(self.profile, self.cv_path)

    def test_level_0_deterministic_fields(self):
        elements = [
            IndexedElement(id=1, tag="input", element_type="text", name="vorname"),
            IndexedElement(id=2, tag="input", element_type="text", placeholder="Ihr Nachname"),
            IndexedElement(id=3, tag="input", element_type="email", name="email"),
            IndexedElement(id=4, tag="input", element_type="tel", name="phone_number"),
            IndexedElement(id=5, tag="input", element_type="file", name="resume"),
        ]

        actions = self.fast_path.plan_fast_actions(elements)
        self.assertEqual(len(actions), 5)

        # Check values
        actions_by_id = {a.element_id: a for a in actions}
        self.assertEqual(actions_by_id[1].value, "Alex")
        self.assertEqual(actions_by_id[2].value, "Dupont")
        self.assertEqual(actions_by_id[3].value, "alex.dupont@example.com")
        self.assertEqual(actions_by_id[4].value, "+49 176 12345678")
        self.assertEqual(actions_by_id[5].action_type, ActionType.UPLOAD)
        self.assertEqual(str(actions_by_id[5].value).replace('\\', '/').lower(), str(self.cv_path).replace('\\', '/').lower())

    def test_level_1_heuristic_fields(self):
        elements = [
            IndexedElement(id=10, tag="input", element_type="text", placeholder="LinkedIn Profil-URL"),
            IndexedElement(id=11, tag="input", element_type="text", name="geburtsdatum"),
        ]

        actions = self.fast_path.plan_fast_actions(elements)
        self.assertEqual(len(actions), 2)
        actions_by_id = {a.element_id: a for a in actions}
        self.assertEqual(actions_by_id[10].value, "https://linkedin.com/in/alexdupont")
        self.assertEqual(actions_by_id[11].value, "15.04.1994")

    def test_skips_already_filled_inputs(self):
        elements = [
            IndexedElement(id=1, tag="input", element_type="text", name="vorname", value="AlreadyFilled"),
        ]
        actions = self.fast_path.plan_fast_actions(elements)
        self.assertEqual(len(actions), 0)

    def test_pill_buttons_selection(self):
        elements = [
            IndexedElement(id=20, tag="button", text="Informatik", is_selected=False),
            IndexedElement(id=21, tag="button", text="Französisch", is_selected=True),  # already selected, must be skipped
            IndexedElement(id=22, tag="button", text="Altgriechisch", is_selected=False), # not in profile, must be skipped
            IndexedElement(id=23, tag="button", text="Weiter", is_selected=False),        # navigation, must be skipped
        ]
        actions = self.fast_path.plan_fast_actions(elements)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].element_id, 20)
        self.assertEqual(actions[0].action_type, ActionType.CLICK)

    def test_prevents_duplicate_uploads(self):
        elements = [
            IndexedElement(id=5, tag="input", element_type="file", name="resume"),
        ]
        actions1 = self.fast_path.plan_fast_actions(elements)
        self.assertEqual(len(actions1), 1)
        self.assertEqual(actions1[0].action_type, ActionType.UPLOAD)

        # Second call with the same element: must be skipped!
        actions2 = self.fast_path.plan_fast_actions(elements)
        self.assertEqual(len(actions2), 0)

    def test_salary_and_availability_heuristics(self):
        self.profile["expected_salary"] = "52.000 €"
        elements = [
            IndexedElement(id=40, tag="input", element_type="text", name="gehalt"),
            IndexedElement(id=41, tag="input", element_type="text", placeholder="Verfügbar ab"),
        ]
        actions = self.fast_path.plan_fast_actions(elements)
        actions_by_id = {a.element_id: a for a in actions}
        self.assertEqual(actions_by_id[40].value, "52.000 €")
        self.assertRegex(actions_by_id[41].value, r"\d{2}\.\d{2}\.\d{4}")


if __name__ == "__main__":
    unittest.main()
