"""
agenvia.enums
~~~~~~~~~~~~~
Typed constants for values returned by the Agenvia API.

Using ``str, Enum`` means string comparisons still work:

    decision.action == "allow"          # True — backwards compatible
    decision.action == Action.ALLOW     # True — IDE-friendly

Import directly from the top-level package:

    from agenvia import Action
"""

from enum import Enum


class Action(str, Enum):
    """
    All possible actions returned by evaluate() and sanitize().

    What to do for each action
    --------------------------
    ALLOW       Safe — pass the original prompt to your LLM.
    MINIMIZE    Partially sensitive — pass decision.safe_prompt to your LLM
                instead of the original. Contains redacted content.
    SANITIZE    PII detected — you MUST pass decision.safe_prompt to your LLM.
                Using the original prompt will send raw PII to the model.
    LOCAL_ONLY  Do not send to any cloud LLM. Process locally only.
                Check decision.local_only_trigger for the reason.
    BLOCK       Stop immediately — do not pass the prompt anywhere.
                Surface decision.policy_reasons to the user.
    """

    ALLOW      = "allow"
    MINIMIZE   = "minimize"
    SANITIZE   = "sanitize"
    LOCAL_ONLY = "local-only"
    BLOCK      = "block"


class TaskType(str, Enum):
    """
    Valid values for the task_type parameter accepted by evaluate(),
    sanitize(), scrub_output(), and authorize_tool().

    Passing the correct task_type improves policy accuracy — the gateway
    applies domain-specific rules rather than the generic fallback.
    """

    GENERAL          = "general_analysis"
    HR               = "hr_review"
    MEDICAL          = "medical_query"
    FINANCIAL        = "financial_analysis"
    CUSTOMER_SUPPORT = "customer_support"
    LEGAL            = "legal_review"


class SensitivityTier(int, Enum):
    """
    Sensitivity tier for tools and context passed to authorize_tool().

    Tier determines which authorization policy applies:

    READ_ONLY    (1)  Low risk — read-only knowledge base lookups, search,
                      calculations. Typically auto-approved.
    PERSONAL     (2)  Medium risk — accesses or returns personal data (names,
                      emails, dates of birth). Requires Tier 2 policy clearance.
    WRITE_ACTION (3)  High risk — writes data, files documents, sends external
                      messages, or executes irreversible actions. May require
                      human approval (pending_approval).
    """

    READ_ONLY    = 1
    PERSONAL     = 2
    WRITE_ACTION = 3


class ApprovalDecision(str, Enum):
    """Valid decisions for submit_approval()."""

    APPROVED = "approved"
    REJECTED = "rejected"
