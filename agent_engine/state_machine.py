"""
Application State Machine
Maintains deterministic progression through application phases and enforces
that SUBMITTED is strictly impossible without VALIDATION_REQUIRED -> HUMAN_APPROVED.
"""
from enum import Enum
from typing import Optional, Set


class ApplicationState(str, Enum):
    DISCOVERED = "DISCOVERED"
    OPENED = "OPENED"
    FORM_DETECTED = "FORM_DETECTED"
    FILLING = "FILLING"
    FILLED = "FILLED"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    SUBMITTED = "SUBMITTED"
    FAILED = "FAILED"


# Allowed state transitions
VALID_TRANSITIONS: dict[ApplicationState, Set[ApplicationState]] = {
    ApplicationState.DISCOVERED: {ApplicationState.OPENED, ApplicationState.FAILED},
    ApplicationState.OPENED: {ApplicationState.FORM_DETECTED, ApplicationState.FAILED},
    ApplicationState.FORM_DETECTED: {ApplicationState.FILLING, ApplicationState.FAILED},
    ApplicationState.FILLING: {ApplicationState.FILLING, ApplicationState.FILLED, ApplicationState.VALIDATION_REQUIRED, ApplicationState.FAILED},
    ApplicationState.FILLED: {ApplicationState.VALIDATION_REQUIRED, ApplicationState.FAILED},
    ApplicationState.VALIDATION_REQUIRED: {ApplicationState.HUMAN_APPROVED, ApplicationState.FAILED},
    ApplicationState.HUMAN_APPROVED: {ApplicationState.SUBMITTED, ApplicationState.FAILED},
    ApplicationState.SUBMITTED: set(),
    ApplicationState.FAILED: {ApplicationState.OPENED, ApplicationState.DISCOVERED},
}


class StateMachineError(Exception):
    pass


class ApplicationStateMachine:
    def __init__(self, initial_state: ApplicationState = ApplicationState.DISCOVERED):
        self._current_state: ApplicationState = initial_state
        self._history: list[tuple[ApplicationState, str]] = [(initial_state, "Initialized")]
        self._human_approver: Optional[str] = None

    @property
    def current_state(self) -> ApplicationState:
        return self._current_state

    @property
    def history(self) -> list[tuple[ApplicationState, str]]:
        return list(self._history)

    def transition_to(self, target_state: ApplicationState, reason: str = "", approved_by: Optional[str] = None) -> None:
        """
        Validates and executes a state transition.
        Enforces that SUBMITTED requires HUMAN_APPROVED with an identified approver.
        """
        valid_next_states = VALID_TRANSITIONS.get(self._current_state, set())
        if target_state not in valid_next_states:
            raise StateMachineError(
                f"Invalid state transition from '{self._current_state.value}' to '{target_state.value}'. "
                f"Allowed transitions: {[s.value for s in valid_next_states]}"
            )

        if target_state == ApplicationState.HUMAN_APPROVED:
            if not approved_by:
                raise StateMachineError("Transition to HUMAN_APPROVED requires explicit 'approved_by' identity.")
            self._human_approver = approved_by

        if target_state == ApplicationState.SUBMITTED:
            if self._current_state != ApplicationState.HUMAN_APPROVED:
                raise StateMachineError("State SUBMITTED can ONLY be transitioned to from HUMAN_APPROVED.")

        self._current_state = target_state
        self._history.append((target_state, reason))

    def reset_to(self, state: ApplicationState, reason: str = "Manual recovery") -> None:
        """Emergency reset for recovery loops."""
        self._current_state = state
        self._history.append((state, reason))
