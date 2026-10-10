"""
Action Schema & Data Models for Agent Engine
Defines elements, action types, action payloads, and validation results.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    TYPE = "type"
    SELECT = "select"
    UPLOAD = "upload"
    CLICK = "click"
    CLICK_NON_TERMINAL = "click_non_terminal"
    SCROLL = "scroll"
    WAIT = "wait"
    REQUEST_HUMAN_APPROVAL = "request_human_approval"


@dataclass
class IndexedElement:
    id: int
    tag: str
    element_type: Optional[str] = None
    name: Optional[str] = None
    placeholder: Optional[str] = None
    text: str = ""
    role: Optional[str] = None
    aria_label: Optional[str] = None
    value: Optional[str] = None
    is_visible: bool = True
    is_interactive: bool = True
    is_terminal: bool = False
    is_selected: bool = False
    options: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        parts = [f"[{self.id}] <{self.tag}"]
        if self.element_type:
            parts.append(f'type="{self.element_type}"')
        if self.name:
            parts.append(f'name="{self.name}"')
        if self.placeholder:
            parts.append(f'placeholder="{self.placeholder}"')
        if self.role:
            parts.append(f'role="{self.role}"')
        if self.aria_label:
            parts.append(f'aria-label="{self.aria_label}"')
        if self.value:
            parts.append(f'value="{self.value[:30]}"')
        parts.append(">")
        if self.text and len(self.text.strip()) > 0:
            cleaned_text = " ".join(self.text.split())[:120]
            parts.append(f'"{cleaned_text}"')
        if self.options:
            opts_summary = [o[:65] for o in self.options[:10]]
            if len(self.options) > 10:
                opts_summary.append(f"...+{len(self.options)-10} more")
            parts.append(f"options={opts_summary}")
        if self.is_selected:
            parts.append("✓ [SELECTED/ACTIVE]")
        if self.is_terminal:
            parts.append("🛑 [TERMINAL BUTTON]")
        return " ".join(parts)


@dataclass
class Action:
    action_type: ActionType
    element_id: Optional[int] = None
    value: Optional[str] = None
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    is_valid: bool
    requires_human: bool = False
    error: Optional[str] = None
    reason: Optional[str] = None
    action: Optional[Action] = None
