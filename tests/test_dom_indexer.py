"""
Unit tests for DOM Indexer representation and serialization
"""
import unittest
from agent_engine.action_schema import IndexedElement
from agent_engine.dom_indexer import DOMIndexer


class TestDOMIndexer(unittest.TestCase):
    def test_element_summary(self):
        el = IndexedElement(
            id=1,
            tag="input",
            element_type="text",
            name="vorname",
            placeholder="Ihr Vorname",
        )
        s = el.summary()
        self.assertIn("[1]", s)
        self.assertIn("vorname", s)
        self.assertIn("Ihr Vorname", s)

    def test_terminal_element_summary_flag(self):
        el = IndexedElement(
            id=7,
            tag="button",
            text="Jetzt bewerben",
            is_terminal=True,
        )
        s = el.summary()
        self.assertIn("🛑 [TERMINAL BUTTON]", s)

    def test_serialization(self):
        elements = [
            IndexedElement(id=1, tag="input", element_type="text", name="email"),
            IndexedElement(id=2, tag="button", text="Weiter"),
        ]
        text = DOMIndexer.serialize_for_observation(elements)
        lines = text.strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertIn("[1]", lines[0])
        self.assertIn("[2]", lines[1])

    def test_serialization_with_errors(self):
        elements = [IndexedElement(id=1, tag="button", text="Weiter")]
        errors = ["Diese Angabe ist erforderlich"]
        text = DOMIndexer.serialize_for_observation(elements, errors)
        self.assertIn("ACTIVE VALIDATION ERRORS", text)
        self.assertIn("Diese Angabe ist erforderlich", text)


if __name__ == "__main__":
    unittest.main()
