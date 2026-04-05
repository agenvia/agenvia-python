"""
Agenvia Python SDK
~~~~~~~~~~~~~~~~~~
3-tier AI governance for autonomous agents.

    from agenvia import Agenvia, Action, TaskType, SensitivityTier

Basic usage::

    client = Agenvia(api_key="av_...", tenant_id="your_tenant_id")

    decision = client.evaluate(prompt, user_id="your_user_id")

    if decision.action == Action.BLOCK:
        return decision.policy_reasons[0]
    elif decision.action in (Action.MINIMIZE, Action.SANITIZE):
        response = llm(decision.safe_prompt)
    else:
        response = llm(prompt)
"""

from .client import Agenvia
from .enums import Action, ApprovalDecision, SensitivityTier, TaskType
from .exceptions import (
    AgenviaError,
    AuthError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .models import (
    ApprovalStatus,
    Decision,
    Finding,
    SanitizedPrompt,
    ScrubbedOutput,
    ToolDecision,
)

__version__ = "0.1.1"
__all__ = [
    # Client
    "Agenvia",
    # Enums
    "Action",
    "ApprovalDecision",
    "SensitivityTier",
    "TaskType",
    # Models
    "Decision",
    "Finding",
    "SanitizedPrompt",
    "ScrubbedOutput",
    "ToolDecision",
    "ApprovalStatus",
    # Exceptions
    "AgenviaError",
    "AuthError",
    "PermissionError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
]
