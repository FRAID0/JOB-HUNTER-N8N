"""
Unit tests for Application State Machine
"""
import unittest
from agent_engine.state_machine import (
    ApplicationState,
    ApplicationStateMachine,
    StateMachineError,
)


class TestStateMachine(unittest.TestCase):
    def test_nominal_flow(self):
        sm = ApplicationStateMachine()
        self.assertEqual(sm.current_state, ApplicationState.DISCOVERED)

        sm.transition_to(ApplicationState.OPENED, "Page loaded")
        self.assertEqual(sm.current_state, ApplicationState.OPENED)

        sm.transition_to(ApplicationState.FORM_DETECTED, "Inputs found")
        self.assertEqual(sm.current_state, ApplicationState.FORM_DETECTED)

        sm.transition_to(ApplicationState.FILLING, "Fast-path starting")
        self.assertEqual(sm.current_state, ApplicationState.FILLING)

        sm.transition_to(ApplicationState.FILLED, "All inputs complete")
        self.assertEqual(sm.current_state, ApplicationState.FILLED)

        sm.transition_to(ApplicationState.VALIDATION_REQUIRED, "Final submit button detected")
        self.assertEqual(sm.current_state, ApplicationState.VALIDATION_REQUIRED)

        sm.transition_to(ApplicationState.HUMAN_APPROVED, "User clicked approve", approved_by="User")
        self.assertEqual(sm.current_state, ApplicationState.HUMAN_APPROVED)

        sm.transition_to(ApplicationState.SUBMITTED, "Submitted")
        self.assertEqual(sm.current_state, ApplicationState.SUBMITTED)

    def test_illegal_direct_submit_fails(self):
        sm = ApplicationStateMachine()
        sm.transition_to(ApplicationState.OPENED)
        sm.transition_to(ApplicationState.FORM_DETECTED)
        sm.transition_to(ApplicationState.FILLING)

        # Attempt to jump straight to SUBMITTED without human gate
        with self.assertRaises(StateMachineError):
            sm.transition_to(ApplicationState.SUBMITTED)

    def test_human_approved_requires_identity(self):
        sm = ApplicationStateMachine()
        sm.transition_to(ApplicationState.OPENED)
        sm.transition_to(ApplicationState.FORM_DETECTED)
        sm.transition_to(ApplicationState.FILLING)
        sm.transition_to(ApplicationState.FILLED)
        sm.transition_to(ApplicationState.VALIDATION_REQUIRED)

        # Missing approved_by
        with self.assertRaises(StateMachineError):
            sm.transition_to(ApplicationState.HUMAN_APPROVED, "Approval")


if __name__ == "__main__":
    unittest.main()
