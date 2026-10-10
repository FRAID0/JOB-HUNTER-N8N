import unittest
from agent_engine.candidate_knowledge import CandidateKnowledgeBase
from agent_engine.action_schema import IndexedElement, Action, ActionType
from agent_engine.fast_path import FastPathEngine


class TestCandidateKnowledgeBase(unittest.TestCase):
    def setUp(self):
        self.kb = CandidateKnowledgeBase(profile_path="d:/N8N/profil.json")

    def test_knowledge_base_loading(self):
        self.assertEqual(self.kb.personal_info.get("first_name"), "Wilfried")
        self.assertEqual(self.kb.education.get("degree"), "Bachelor of Science")
        self.assertTrue(self.kb.knowledge.get("is_mandatory_internship"))

    def test_reasoning_prompt_generation(self):
        prompt = self.kb.to_reasoning_prompt(target_job="Praktikum IoT und KI")
        self.assertIn("Wilfried Manfouo Fomekong", prompt)
        self.assertIn("Pflichtpraktikum", prompt)
        self.assertIn("5–6 Monate", prompt)
        self.assertIn("Sehr Gute Kenntnisse", prompt)
        self.assertIn("B1 — Fortgeschrittene Sprachverwendung", prompt)
        self.assertIn("Jobbörse", prompt)
        self.assertIn("Datenschutzerklärung", prompt)

    def test_indexed_element_with_options(self):
        el = IndexedElement(
            id=15,
            tag="select",
            name="englishLevel",
            aria_label="Welches Sprachniveau hat dein Englisch?",
            options=["A1 — Anfänger", "A2", "B1 — Fortgeschrittene Sprachverwendung", "B2", "C1", "C2"]
        )
        summary = el.summary()
        self.assertIn("[15] <select", summary)
        self.assertIn("options=", summary)
        self.assertIn("B1 — Fortgeschrittene Sprachverwendung", summary)

    def test_fast_path_with_knowledge_base_profile(self):
        engine = FastPathEngine(self.kb.data)
        elements = [
            IndexedElement(id=1, tag="input", element_type="text", name="firstName"),
            IndexedElement(id=2, tag="input", element_type="text", name="mobility"),
            IndexedElement(id=3, tag="input", element_type="radio", text="Handelt es sich um ein Pflichtpraktikum? -> Ja"),
            IndexedElement(id=4, tag="input", element_type="radio", text="Handelt es sich um ein Pflichtpraktikum? -> Nein"),
            IndexedElement(id=5, tag="input", element_type="radio", text="Ich bin aktuell bei Würth beschäftigt -> Ja"),
            IndexedElement(id=6, tag="input", element_type="radio", text="Ich bin aktuell bei Würth beschäftigt -> Nein"),
        ]
        actions = engine.plan_fast_actions(elements)
        # Should fill firstName
        type_actions = [a for a in actions if a.action_type == ActionType.TYPE]
        self.assertTrue(any(a.element_id == 1 and a.value == "Wilfried" for a in type_actions))
        # Should click Ja for Pflichtpraktikum (element 3)
        click_actions = [a for a in actions if a.action_type == ActionType.CLICK]
        self.assertTrue(any(a.element_id == 3 for a in click_actions))
        # Should NOT click Ja for already employed (element 5)
        self.assertFalse(any(a.element_id == 5 for a in click_actions))
        # Should click Nein for already employed (element 6)
        self.assertTrue(any(a.element_id == 6 for a in click_actions))


if __name__ == "__main__":
    unittest.main()
