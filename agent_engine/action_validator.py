"""
Action Validator
Rigorous validation barrier executing between LLM decision and browser action.
Never trusts raw LLM outputs; checks ID existence, visibility, type compatibility,
policy permissions, and catches terminal buttons via Terminal Guard.
"""
from typing import Dict, List, Optional
from .action_schema import Action, ActionType, IndexedElement, ValidationResult
from .terminal_guard import is_terminal_element, HumanApprovalRequired

ALLOWED_ACTIONS = {
    ActionType.NAVIGATE,
    ActionType.TYPE,
    ActionType.SELECT,
    ActionType.UPLOAD,
    ActionType.CLICK,
    ActionType.CLICK_NON_TERMINAL,
    ActionType.SCROLL,
    ActionType.WAIT,
    ActionType.REQUEST_HUMAN_APPROVAL,
}


class ActionValidator:
    def __init__(self):
        pass

    def validate(
        self,
        action: Action,
        elements: List[IndexedElement],
    ) -> ValidationResult:
        """
        Validates an action against the indexed elements and strict security policy.
        """
        # 1. Action Authorization Check
        if action.action_type not in ALLOWED_ACTIONS:
            return ValidationResult(
                is_valid=False,
                error=f"Forbidden action type: '{action.action_type}' is not permitted in autonomous policy.",
                action=action,
            )

        # 2. Global Actions (no target element needed: NAVIGATE, SCROLL, WAIT)
        if action.action_type in (ActionType.NAVIGATE, ActionType.SCROLL, ActionType.WAIT):
            if action.action_type == ActionType.NAVIGATE and not action.value:
                return ValidationResult(
                    is_valid=False,
                    error="NAVIGATE action requires a valid URL in value.",
                    action=action,
                )
            return ValidationResult(is_valid=True, action=action)

        # 3. Element-Targeted Actions
        elements_map: Dict[int, IndexedElement] = {el.id: el for el in elements}

        if action.element_id is None:
            return ValidationResult(
                is_valid=False,
                error=f"Action '{action.action_type}' requires a target element_id.",
                action=action,
            )

        # ID existence check
        if action.element_id not in elements_map:
            return ValidationResult(
                is_valid=False,
                error=f"Element ID [{action.element_id}] does not exist in current DOM index (available: {list(elements_map.keys())[:15]}...).",
                action=action,
            )

        target_element = elements_map[action.element_id]

        # Visibility check (allow file inputs which are standardly styled behind dropzones)
        if not target_element.is_visible:
            if not (target_element.tag == "input" and target_element.element_type == "file"):
                return ValidationResult(
                    is_valid=False,
                    error=f"Element [{action.element_id}] is hidden or not visible on screen.",
                    action=action,
                )

        # 4. Terminal Button Check (HUMAN GATE)
        if target_element.is_terminal or is_terminal_element(target_element):
            return ValidationResult(
                is_valid=False,
                requires_human=True,
                reason=f"Element [{target_element.id}] ('{target_element.text or target_element.name}') is a TERMINAL action (Final Submission/Payment). Autonomous click strictly forbidden.",
                action=action,
            )

        # 5. Type Compatibility Check
        tag = target_element.tag.lower()
        el_type = (target_element.element_type or "").lower()

        if action.action_type == ActionType.TYPE:
            if tag not in ("input", "textarea") and target_element.attributes.get("contenteditable") != "true":
                return ValidationResult(
                    is_valid=False,
                    error=f"Cannot TYPE into non-editable element <{tag}> [{target_element.id}].",
                    action=action,
                )
            if el_type in ("file", "checkbox", "radio", "submit", "button"):
                return ValidationResult(
                    is_valid=False,
                    error=f"Cannot TYPE into input of type='{el_type}' [{target_element.id}].",
                    action=action,
                )

        elif action.action_type == ActionType.UPLOAD:
            if tag != "input" or el_type != "file":
                return ValidationResult(
                    is_valid=False,
                    error=f"Cannot UPLOAD into element <{tag} type='{el_type}'> [{target_element.id}]. Target must be <input type='file'>.",
                    action=action,
                )
            if not action.value:
                return ValidationResult(
                    is_valid=False,
                    error="UPLOAD action requires a local file path in value.",
                    action=action,
                )

        elif action.action_type == ActionType.SELECT:
            if tag not in ("select", "div", "span") and target_element.role not in ("combobox", "listbox", "select"):
                return ValidationResult(
                    is_valid=False,
                    error=f"Cannot SELECT on element <{tag}> [{target_element.id}] with role='{target_element.role}'.",
                    action=action,
                )

        elif action.action_type in (ActionType.CLICK, ActionType.CLICK_NON_TERMINAL):
            # Clicks are valid on interactive elements
            if not target_element.is_interactive:
                return ValidationResult(
                    is_valid=False,
                    error=f"Element <{tag}> [{target_element.id}] is marked as non-interactive.",
                    action=action,
                )

        # All checks passed!
        return ValidationResult(is_valid=True, requires_human=False, action=action)
