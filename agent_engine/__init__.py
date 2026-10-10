"""
Autonomous Job Application Agent Engine
Combines DOM Indexing, 4-Tier Filling (Fast-Path L0/L1, LLM L2),
Strict Validator and Architectural Terminal Guard (Human Gate).
"""
from .action_schema import Action, ActionType, IndexedElement, ValidationResult
from .terminal_guard import HumanApprovalRequired, is_terminal_element, verify_non_terminal_action
from .state_machine import ApplicationState, ApplicationStateMachine, StateMachineError
from .action_validator import ActionValidator
from .dom_indexer import DOMIndexer
from .observation import PageObservation
from .executor import ActionExecutor, ExecutionError
from .fast_path import FastPathEngine
from .document_hub import DocumentHub
from .llm_decider import LLMDecider
from .candidate_knowledge import CandidateKnowledgeBase
from .agent_loop import AutonomousAgentLoop, AgentExecutionResult

__all__ = [
    "Action",
    "ActionType",
    "IndexedElement",
    "ValidationResult",
    "HumanApprovalRequired",
    "is_terminal_element",
    "verify_non_terminal_action",
    "ApplicationState",
    "ApplicationStateMachine",
    "StateMachineError",
    "ActionValidator",
    "DOMIndexer",
    "PageObservation",
    "ActionExecutor",
    "ExecutionError",
    "FastPathEngine",
    "DocumentHub",
    "LLMDecider",
    "CandidateKnowledgeBase",
    "AutonomousAgentLoop",
    "AgentExecutionResult",
]
