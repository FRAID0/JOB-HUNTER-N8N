"""
Unit tests for Action Validator
"""
import unittest
from agent_engine.action_schema import IndexedElement, Action, ActionType
from agent_engine.action_validator import ActionValidator


class TestActionValidator(unittest.TestCase):
    def setUp(self):
        self.validator = ActionValidator()
        self.elements = [
            IndexedElement(id=1, tag="input", element_type="text", name="vorname", is_visible=True),
            IndexedElement(id=2, tag="input", element_type="file", name="resume", is_visible=True),
            IndexedElement(id=3, tag="button", text="Weiter", is_visible=True),
            IndexedElement(id=4, tag="button", text="Jetzt bewerben", is_terminal=True, is_visible=True),
            IndexedElement(id=5, tag="input", element_type="text", name="hidden_field", is_visible=False),
        ]

    def test_valid_type_action(self):
        action = Action(action_type=ActionType.TYPE, element_id=1, value="Wilfried")
        res = self.validator.validate(action, self.elements)
        self.assertTrue(res.is_valid)
        self.assertFalse(res.requires_human)

    def test_reject_nonexistent_id(self):
        action = Action(action_type=ActionType.TYPE, element_id=999, value="Test")
        res = self.validator.validate(action, self.elements)
        self.assertFalse(res.is_valid)
        self.assertIn("does not exist", res.error)

    def test_reject_hidden_element(self):
        action = Action(action_type=ActionType.TYPE, element_id=5, value="Test")
        res = self.validator.validate(action, self.elements)
        self.assertFalse(res.is_valid)
        self.assertIn("hidden or not visible", res.error)

    def test_type_compatibility_rejects_type_on_button(self):
        action = Action(action_type=ActionType.TYPE, element_id=3, value="Test")
        res = self.validator.validate(action, self.elements)
        self.assertFalse(res.is_valid)
        self.assertIn("non-editable", res.error)

    def test_type_compatibility_rejects_upload_on_text_input(self):
        action = Action(action_type=ActionType.UPLOAD, element_id=1, value="cv.pdf")
        res = self.validator.validate(action, self.elements)
        self.assertFalse(res.is_valid)
        self.assertIn("Target must be <input type='file'>", res.error)

    def test_valid_upload_on_file_input(self):
        action = Action(action_type=ActionType.UPLOAD, element_id=2, value="cv.pdf")
        res = self.validator.validate(action, self.elements)
        self.assertTrue(res.is_valid)

    def test_terminal_button_triggers_human_gate(self):
        action = Action(action_type=ActionType.CLICK, element_id=4)
        res = self.validator.validate(action, self.elements)
        self.assertFalse(res.is_valid)
        self.assertTrue(res.requires_human)
        self.assertIn("TERMINAL action", res.reason)

    def test_non_terminal_button_allowed(self):
        action = Action(action_type=ActionType.CLICK, element_id=3)
        res = self.validator.validate(action, self.elements)
        self.assertTrue(res.is_valid)
        self.assertFalse(res.requires_human)


if __name__ == "__main__":
    unittest.main()
