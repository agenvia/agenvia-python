"""
agenvia.models
~~~~~~~~~~~~~~
Typed response objects returned by the Agenvia SDK.

All fields are documented. Use your IDE's hover/autocomplete to explore
available data — the package ships with py.typed so type information
is always available.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Finding:
    """A single detection finding within a prompt or response."""

    label: str
    """Category of sensitive content, e.g. 'ssn', 'email', 'injection', 'dob'."""

    text: str
    """The matched text excerpt."""

    confidence: float
    """Model confidence in the detection, 0.0–1.0."""

    sensitivity_tier: int
    """
    Tier of the finding:
      1 = low risk (general PII)
      2 = medium risk (personal data)
      3 = high risk (financial, medical, injection)
    """

    start: int
    """Start character offset in the original prompt."""

    end: int
    """End character offset in the original prompt."""


@dataclass
class Decision:
    """
    Response from evaluate().

    Always check ``action`` first and branch accordingly.
    See Action enum for what each value requires you to do.
    """

    request_id: str
    """Unique ID for this evaluation. Store for audit trail and feedback."""

    action: str
    """
    One of: allow | minimize | sanitize | local-only | block

    Use the Action enum for safe comparisons:
        from agenvia import Action
        if decision.action == Action.SANITIZE:
            prompt_to_send = decision.safe_prompt   # MUST use this
    """

    risk_score: float
    """Numeric risk score, 0.0–1.0. Higher = more sensitive."""

    risk_level: str
    """Human-readable risk level: safe | minimize | sanitize | local-only | block."""

    safe_prompt: str
    """
    Redacted prompt with sensitive content replaced by placeholders.
    Use this instead of the original when action is MINIMIZE or SANITIZE.
    Using the original prompt when action == SANITIZE sends raw PII to the LLM.
    """

    findings: list[Finding]
    """List of individual detections. Empty when action is ALLOW."""

    policy_reasons: list[str]
    """Human-readable reasons for the decision. Surface to users on BLOCK."""

    policy_trace: list[dict]
    """Full policy evaluation trace for debugging. Not for production display."""

    local_only_trigger: str | None
    """
    Populated when action == LOCAL_ONLY. Explains why cloud LLM is forbidden:
      'policy_rule:<rule_name>'  — a policy rule explicitly forbids cloud routing
      'risk_threshold:<score>'   — risk score exceeded the local-only threshold
      'model_decision'           — the model determined cloud routing is unsafe
    """

    tenant_id: str
    actor_id: str
    created_at: str


@dataclass
class SanitizedPrompt:
    """
    Response from sanitize().

    The vault session is valid for ttl_seconds (default 300s).
    Pass session_id to scrub_output() after the LLM responds.

    IMPORTANT: store session_id in your database, not in memory.
    Server restarts will lose in-memory state; the vault persists
    across restarts but your session_id must survive too.
    """

    session_id: str
    """
    Vault session handle. Required for scrub_output().
    Persist this to your database — do not store in a local variable.
    """

    safe_prompt: str
    """Redacted prompt. Pass this to your LLM — real values are in the vault."""

    action: str
    """Action determined during sanitization (same values as Decision.action)."""

    risk_score: float
    """Numeric risk score for the prompt, 0.0–1.0."""

    findings: list[Finding]
    """Individual detections that caused sanitization."""

    policy_reasons: list[str]
    """Human-readable policy reasons."""

    allowed_fields: list[str]
    """Field labels permitted to be returned in the LLM response."""

    tenant_id: str
    actor_id: str
    created_at: str


@dataclass
class ScrubbedOutput:
    """Response from scrub_output()."""

    scrubbed_answer: str
    """Safe answer to return to the caller. Real PII values are replaced."""

    findings: list[Finding]
    """Detections found in the LLM response before scrubbing."""

    vault_replacements: list[tuple[str, str]]
    """Pairs of (real_value, placeholder) that were substituted."""

    allowed_fields: list[str]
    """Fields the policy permitted to appear in the response."""


@dataclass
class ToolDecision:
    """
    Response from authorize_tool().

    Always check ``decision`` before executing the tool.
    """

    action: str
    """
    One of:
      'allow'            — proceed with tool execution
      'deny'             — do not execute; surface reason to user
      'pending_approval' — store approval_id and wait for human approval
    """

    reason: str
    """
    Human-readable explanation of the decision.
    Surface this to the user when decision is 'deny' or 'pending_approval'.
    Example: "CaseFiler requires admin approval for external court filings."
    """

    approval_id: str | None
    """
    Populated when decision == 'pending_approval'.
    Store this in your database — it is required to call submit_approval()
    and to resume execution after approval is granted.
    Expires after sensitivity_tier × 10 minutes.
    """

    tool_name: str
    tenant_id: str


@dataclass
class ApprovalStatus:
    """Response from get_approval() and submit_approval()."""

    approval_id: str
    status: str
    """One of: pending | approved | rejected | expired."""

    decision: str | None
    """The manager's decision: 'approved' or 'rejected'. None while pending."""

    tool_name: str
    target: str
    reason: str
    created_at: str
    decided_at: str | None
