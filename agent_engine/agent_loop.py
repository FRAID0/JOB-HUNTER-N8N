"""
Agent Loop Engine
Coordinates observation, DOM indexing, state machine, Fast-Path (L0/L1),
LLM reasoning (L2), strict validation, and the Human Gate (L3).
"""
import logging
import os
import time
from typing import Callable, Optional
from .action_schema import Action, ActionType, IndexedElement, ValidationResult
from .terminal_guard import HumanApprovalRequired
from .state_machine import ApplicationState, ApplicationStateMachine
from .action_validator import ActionValidator
from .dom_indexer import DOMIndexer
from .observation import PageObservation
from .executor import ActionExecutor
from .fast_path import FastPathEngine
from .llm_decider import LLMDecider
from .candidate_knowledge import CandidateKnowledgeBase

logger = logging.getLogger("agent_engine.loop")


class AgentExecutionResult:
    def __init__(
        self,
        final_state: ApplicationState,
        steps_executed: int,
        requires_human: bool,
        screenshot_path: Optional[str] = None,
        human_gate_reason: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.final_state = final_state
        self.steps_executed = steps_executed
        self.requires_human = requires_human
        self.screenshot_path = screenshot_path
        self.human_gate_reason = human_gate_reason
        self.error = error

    def __repr__(self) -> str:
        return (
            f"<AgentExecutionResult state={self.final_state.value} steps={self.steps_executed} "
            f"requires_human={self.requires_human}>"
        )


class AutonomousAgentLoop:
    def __init__(
        self,
        page,
        profile: dict,
        cv_path: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        max_steps: int = 12,
        screenshot_dir: str = "screenshots",
        docs_dir: str = "d:/N8N/documents",
        on_human_gate_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.page = page
        self.profile = profile
        self.cv_path = cv_path
        self.docs_dir = docs_dir
        self.max_steps = max_steps
        self.screenshot_dir = screenshot_dir
        self.on_human_gate_callback = on_human_gate_callback

        os.makedirs(screenshot_dir, exist_ok=True)

        # Core Engine Components
        self.state_machine = ApplicationStateMachine(ApplicationState.OPENED)
        self.indexer = DOMIndexer()
        self.validator = ActionValidator()
        self.executor = ActionExecutor(page)
        self.fast_path = FastPathEngine(profile, cv_path, docs_dir=docs_dir)
        self.candidate_kb = CandidateKnowledgeBase(profile_data=profile)
        self.llm_decider = LLMDecider(api_key=gemini_api_key)
        self.history: list[str] = []

    def observe(self, step_num: int) -> PageObservation:
        """Indexes DOM, takes snapshot, and structures the observation."""
        elements, validation_errors = self.indexer.index_page(self.page)
        serialized = self.indexer.serialize_for_observation(elements, validation_errors)
        terminals = [el for el in elements if el.is_terminal]

        return PageObservation(
            url=self.page.url,
            title=self.page.title(),
            state=self.state_machine.current_state,
            elements=elements,
            serialized_dom=serialized,
            step_number=step_num,
            terminal_elements=terminals,
            validation_errors=validation_errors,
        )

    def run(self, goal: str = "Complete job application up to final review") -> AgentExecutionResult:
        """
        Executes the main autonomous loop with strict Human Gate.
        """
        logger.info(f"Starting Autonomous Agent Loop. Goal: {goal}")

        for step in range(1, self.max_steps + 1):
            logger.info(f"--- [STEP {step}/{self.max_steps}] State: {self.state_machine.current_state.value} ---")
            obs = self.observe(step)

            # Update State Machine
            if self.state_machine.current_state == ApplicationState.OPENED:
                if len(obs.elements) > 0:
                    self.state_machine.transition_to(ApplicationState.FORM_DETECTED, "Form elements indexed")
                    self.state_machine.transition_to(ApplicationState.FILLING, "Commencing auto-fill")

            # 1. Check if we already reached a state where only terminal buttons remain
            empty_inputs = [
                el for el in obs.elements
                if el.tag in ("input", "textarea") and (not el.value or el.value.strip() == "") and not el.is_terminal
            ]
            
            if obs.has_terminal_button and len(empty_inputs) == 0 and not obs.has_validation_errors and step > 1:
                # All inputs filled, no errors, only terminal submission remains!
                return self._trigger_human_gate(
                    reason="All candidate fields completed without errors. Final submission button reached.",
                    step=step,
                )

            # 2. Level 0 & Level 1: Fast-Path Deterministic / Heuristic Fill
            fast_actions = self.fast_path.plan_fast_actions(obs.elements)
            executed_any_fast = False

            if fast_actions:
                logger.info(f"Fast-Path proposed {len(fast_actions)} actions.")
                for action in fast_actions:
                    val_res = self.validator.validate(action, obs.elements)
                    if val_res.requires_human:
                        return self._trigger_human_gate(val_res.reason or "Terminal button encountered.", step)
                    
                    if val_res.is_valid:
                        target_el = obs.get_element(action.element_id) if action.element_id else None
                        try:
                            self.executor.execute(action, target_el)
                            self.history.append(f"FastPath: {action.reasoning}")
                            executed_any_fast = True
                            if action.action_type == ActionType.UPLOAD and action.element_id:
                                self.fast_path.uploaded_element_ids.add(action.element_id)
                                val_lower = str(action.value or "").lower()
                                if "cv" in val_lower or "lebenslauf" in val_lower:
                                    self.fast_path.uploaded_categories.add("cv")
                        except HumanApprovalRequired:
                            raise
                        except Exception as ex:
                            logger.warning(f"FastPath action on [{action.element_id}] failed non-fatally: {ex}")
                    else:
                        logger.warning(f"FastPath action rejected by validator: {val_res.error}")

            if executed_any_fast:
                # Let DOM settle and re-evaluate next step
                self.page.wait_for_timeout(800)
                continue

            # 3. Level 2: LLM Reasoning for complex or multi-step progression
            logger.info("Engaging Level 2 LLM Decider with Candidate Knowledge Base...")
            profile_summary = self.candidate_kb.to_reasoning_prompt(target_job=goal)
            
            llm_actions = self.llm_decider.decide(
                goal=goal,
                profile_context=profile_summary,
                elements_summary=obs.serialized_dom,
                step_history=self.history[-5:],
            )

            if not llm_actions:
                logger.info("LLM proposed no further actions. Checking page state.")
                if obs.has_terminal_button and not obs.has_validation_errors:
                    return self._trigger_human_gate("LLM completed all steps. Terminal button reached.", step)
                break

            executed_llm = False
            for action in llm_actions:
                val_res = self.validator.validate(action, obs.elements)
                
                # Check for Human Gate trigger from validator (actual terminal element)
                if val_res.requires_human:
                    return self._trigger_human_gate(
                        reason=val_res.reason or "Terminal button encountered.",
                        step=step,
                    )

                # If LLM self-requests approval, allow Human Gate so user can inspect
                if action.action_type == ActionType.REQUEST_HUMAN_APPROVAL:
                    if obs.has_validation_errors:
                        logger.warning(f"LLM requested human approval, but validation errors exist: {obs.validation_errors}. Rejecting!")
                        self.history.append(f"System: Active validation error must be resolved: {', '.join(obs.validation_errors)}")
                        continue
                    return self._trigger_human_gate(
                        reason=action.reasoning or "L'agent sollicite une vérification humaine pour cette étape.",
                        step=step,
                    )

                if val_res.is_valid:
                    target_el = obs.get_element(action.element_id) if action.element_id else None
                    try:
                        self.executor.execute(action, target_el)
                        self.history.append(f"LLM Action: {action.action_type} on [{action.element_id}] - {action.reasoning}")
                        executed_llm = True
                    except HumanApprovalRequired as e:
                        return self._trigger_human_gate(str(e), step)
                    except Exception as e:
                        logger.error(f"Executor failed: {e}")
                else:
                    logger.warning(f"Validator rejected LLM action: {val_res.error}")

            if not executed_llm:
                logger.warning("No LLM actions could be executed this turn.")
                break

            self.page.wait_for_timeout(1000)

        # Reached end of loop: Trigger Human Gate so Chromium stays open on user's screen
        return self._trigger_human_gate(
            reason="Formulaire ou page en attente de vérification humaine finale.",
            step=self.max_steps,
        )

    def _trigger_human_gate(self, reason: str, step: int) -> AgentExecutionResult:
        """Freezes loop, transitions state to VALIDATION_REQUIRED, and takes proof screenshot."""
        logger.info(f"🛑 [HUMAN GATE TRIGGERED]: {reason}")
        
        # State Machine Transition
        if self.state_machine.current_state in (ApplicationState.FILLING, ApplicationState.FORM_DETECTED):
            self.state_machine.transition_to(ApplicationState.FILLED, "Form filling completed")
        
        if self.state_machine.current_state == ApplicationState.FILLED:
            self.state_machine.transition_to(ApplicationState.VALIDATION_REQUIRED, reason)

        # Capture Verification Screenshot
        screenshot_path = os.path.join(self.screenshot_dir, f"verification_step_{step}_{int(time.time())}.png")
        try:
            self.page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Proof screenshot saved: {screenshot_path}")
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            screenshot_path = None

        if self.on_human_gate_callback and screenshot_path:
            try:
                self.on_human_gate_callback(screenshot_path, reason)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return AgentExecutionResult(
            final_state=self.state_machine.current_state,
            steps_executed=step,
            requires_human=True,
            screenshot_path=screenshot_path,
            human_gate_reason=reason,
        )
