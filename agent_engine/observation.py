"""
Observation Model
Encapsulates current state of the page: URL, title, indexed elements,
detected forms, and terminal elements.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .action_schema import IndexedElement
from .state_machine import ApplicationState


@dataclass
class PageObservation:
    url: str
    title: str
    state: ApplicationState
    elements: List[IndexedElement]
    serialized_dom: str
    step_number: int = 1
    screenshot_path: Optional[str] = None
    terminal_elements: List[IndexedElement] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)

    @property
    def has_validation_errors(self) -> bool:
        return len(self.validation_errors) > 0

    @property
    def has_terminal_button(self) -> bool:
        return len(self.terminal_elements) > 0

    @property
    def elements_map(self) -> Dict[int, IndexedElement]:
        return {el.id: el for el in self.elements}

    def get_element(self, element_id: int) -> Optional[IndexedElement]:
        return self.elements_map.get(element_id)
