"""
agenvia.client
~~~~~~~~~~~~~~
Main Agenvia client. All API calls go through this class.
"""

from __future__ import annotations

import warnings
from typing import Any

import httpx

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

_UNSET = object()

_BASE_URL = "https://promptrak-api-production.up.railway.app"


def _parse_findings(raw: list[dict]) -> list[Finding]:
    return [
        Finding(
            label=f["label"],
            text=f["text"],
            confidence=f["confidence"],
            sensitivity_tier=f.get("sensitivity_tier", 1),
            start=f.get("start", 0),
            end=f.get("end", 0),
        )
        for f in (raw or [])
    ]


class Agenvia:
    """
    Agenvia governance client.

    Parameters
    ----------
    api_key : str
        Your Agenvia API key. Must start with 'av_'.
        Get yours at https://app.agenvia.io/settings/api-keys
    tenant_id : str
        Your organisation identifier, e.g. "acme-corp".
    base_url : str, optional
        Override the API base URL. Defaults to the Agenvia cloud.
    timeout : float, optional
        Request timeout in seconds. Default 30.

    Raises
    ------
    ValueError
        If the API key format is invalid.

    Examples
    --------
    Basic setup::

        from agenvia import Agenvia

        client = Agenvia(api_key="av_...", tenant_id="your_tenant_id")

    Offline / CI mode — set AGENVIA_KEY=off in your environment::

        import os
        from agenvia import Agenvia, Action

        if os.getenv("AGENVIA_KEY") == "off":
            # Return a stub decision — no network call
            ...
        else:
            client = Agenvia(api_key=os.environ["AGENVIA_KEY"], tenant_id="your_tenant_id")
    """

    def __init__(
        self,
        api_key: str,
        tenant_id: str,
        *,
        base_url: str = _BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        if not api_key or not api_key.startswith("av_"):
            raise ValueError(
                f"Invalid API key format '{api_key[:8]}...'. "
                "Agenvia keys start with 'av_'. "
                "Get yours at https://app.agenvia.io/settings/api-keys"
            )
        self._api_key = api_key
        self._tenant_id = tenant_id
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, body: dict) -> dict:
        try:
            r = self._http.post(path, json=body)
        except httpx.TimeoutException as exc:
            raise AgenviaError(f"Request timed out: {exc}") from exc
        except httpx.RequestError as exc:
            raise AgenviaError(f"Network error: {exc}") from exc
        return self._handle(r)

    def _get(self, path: str) -> dict:
        try:
            r = self._http.get(path)
        except httpx.RequestError as exc:
            raise AgenviaError(f"Network error: {exc}") from exc
        return self._handle(r)

    @staticmethod
    def _handle(r: httpx.Response) -> dict:
        if r.status_code == 200 or r.status_code == 201:
            return r.json()
        detail = ""
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        if r.status_code == 401:
            raise AuthError(f"Authentication failed: {detail}", status_code=401)
        if r.status_code == 403:
            raise PermissionError(f"Permission denied: {detail}", status_code=403)
        if r.status_code == 404:
            raise NotFoundError(f"Not found: {detail}", status_code=404)
        if r.status_code == 422:
            raise ValidationError(f"Validation error: {detail}", status_code=422)
        if r.status_code == 429:
            raise RateLimitError(
                "Rate limit exceeded. Back off and retry.", status_code=429
            )
        if r.status_code >= 500:
            raise ServerError(
                f"Agenvia server error ({r.status_code}): {detail}",
                status_code=r.status_code,
            )
        raise AgenviaError(f"Unexpected response ({r.status_code}): {detail}", status_code=r.status_code)

    # ------------------------------------------------------------------
    # Tier 1 — evaluate()
    # ------------------------------------------------------------------

    def evaluate(
        self,
        prompt: str,
        *,
        user_id: str,
        tenant_id: str | None = None,
        task_type: str | TaskType = TaskType.GENERAL,
        context_tags: list[str] | None = None,
        detect_only: bool = False,
    ) -> Decision:
        """
        Evaluate a prompt through Tier 1 governance.

        Runs intent classification, injection detection, and policy rules.
        Always call this before passing a prompt to your LLM.

        Parameters
        ----------
        prompt : str
            The user's raw prompt. Max 12,000 characters.
        user_id : str
            Identifier for the user making the request. Used for audit trail.
        tenant_id : str, optional
            Override the client-level tenant_id for this request.
        task_type : str or TaskType, optional
            Domain context for policy accuracy. Default: 'general_analysis'.
            Use TaskType enum for valid values: TaskType.HR, TaskType.LEGAL, etc.
        context_tags : list[str], optional
            Additional tags passed to policy rules.
        detect_only : bool, optional
            If True, runs detection only — no metrics recorded, no rate limit.
            Useful for testing. Default: False.

        Returns
        -------
        Decision
            Structured response. Always branch on decision.action first.

        Raises
        ------
        AuthError
            Invalid or expired API key.
        RateLimitError
            Request rate limit exceeded.
        AgenviaError
            Any other API error.

        Examples
        --------
        ::

            from agenvia import Agenvia, Action

            client = Agenvia(api_key="av_...", tenant_id="your_tenant_id")
            decision = client.evaluate(
                "What are Q3 sales figures?",
                user_id="your_user_id",
                task_type="financial_analysis",
            )

            if decision.action == Action.BLOCK:
                return f"Request blocked: {decision.policy_reasons[0]}"
            elif decision.action in (Action.MINIMIZE, Action.SANITIZE):
                prompt_to_send = decision.safe_prompt  # use this, not the original
            elif decision.action == Action.LOCAL_ONLY:
                # do not send to cloud LLM
                return run_local_model(decision.safe_prompt)
            else:  # Action.ALLOW
                prompt_to_send = prompt

        Notes
        -----
        When action == SANITIZE, you MUST use decision.safe_prompt.
        Using the original prompt will send raw PII to your LLM.
        A UserWarning is emitted as a reminder when this action is returned.
        """
        body: dict[str, Any] = {
            "prompt": prompt,
            "user_id": user_id,
            "organization": tenant_id or self._tenant_id,
            "task_type": str(task_type),
            "context_tags": context_tags or [],
            "detect_only": detect_only,
        }
        raw = self._post("/gateway/prompt", body)

        # Determine local_only_trigger
        local_only_trigger: str | None = None
        if raw.get("action") == "local-only":
            trace = raw.get("policy_trace", [])
            for entry in trace:
                if "local_only" in str(entry).lower() or "local-only" in str(entry).lower():
                    local_only_trigger = str(entry.get("reason", "policy_rule:unknown"))
                    break
            if local_only_trigger is None:
                score = raw.get("risk_score", 0)
                local_only_trigger = f"risk_threshold:{score:.2f}"

        decision = Decision(
            request_id=raw["request_id"],
            action=raw["action"],
            risk_score=raw["risk_score"],
            risk_level=raw["risk_level"],
            safe_prompt=raw.get("minimized_prompt") or raw.get("sanitized_prompt") or prompt,
            findings=_parse_findings(raw.get("findings", [])),
            policy_reasons=raw.get("policy_reasons", []),
            policy_trace=raw.get("policy_trace", []),
            local_only_trigger=local_only_trigger,
            tenant_id=raw.get("tenant_id", tenant_id or self._tenant_id),
            actor_id=raw.get("actor_id", user_id),
            created_at=str(raw.get("created_at", "")),
        )

        # Warn when sanitize is returned — caller must use safe_prompt
        if decision.action == Action.SANITIZE:
            warnings.warn(
                "evaluate() returned action='sanitize'. "
                "You MUST use decision.safe_prompt when calling your LLM — "
                "using the original prompt will send raw PII to the model.",
                UserWarning,
                stacklevel=2,
            )

        return decision

    # ------------------------------------------------------------------
    # Tier 2 — sanitize() + scrub_output()
    # ------------------------------------------------------------------

    def sanitize(
        self,
        prompt: str,
        *,
        user_id: str,
        tenant_id: str | None = None,
        task_type: str | TaskType = TaskType.GENERAL,
        ttl_seconds: int = 300,
    ) -> SanitizedPrompt:
        """
        Sanitize a prompt through Tier 2 PII vault.

        Detects and replaces sensitive values with placeholders. Real values
        are stored in an encrypted vault session, not returned. Use
        scrub_output() after the LLM responds to restore safe values.

        Parameters
        ----------
        prompt : str
            The user's raw prompt. Max 12,000 characters.
        user_id : str
            Identifier for the user making the request.
        tenant_id : str, optional
            Override the client-level tenant_id.
        task_type : str or TaskType, optional
            Domain context. Default: 'general_analysis'.
        ttl_seconds : int, optional
            Vault session lifetime in seconds. Min 30, max 3600. Default 300.
            The session_id is invalid after this period.

        Returns
        -------
        SanitizedPrompt
            Contains safe_prompt (pass to LLM) and session_id (persist to DB).

        Examples
        --------
        ::

            safe = client.sanitize(
                "Patient Jane Doe, DOB 1990-01-15, SSN 123-45-6789",
                user_id="your_user_id",
                task_type="medical_query",
            )

            # IMPORTANT: persist session_id to database before LLM call
            db.save_session(safe.session_id)

            llm_response = llm.complete(safe.safe_prompt)

            clean = client.scrub_output(
                llm_response,
                session_id=safe.session_id,  # keyword-only — do not pass positionally
                user_id="your_user_id",
            )
            return clean.scrubbed_answer

        Notes
        -----
        session_id must be persisted to a database. Storing it only in memory
        means it is lost on server restart and scrub_output() will fail.
        """
        body: dict[str, Any] = {
            "prompt": prompt,
            "user_id": user_id,
            "organization": tenant_id or self._tenant_id,
            "task_type": str(task_type),
            "ttl_seconds": ttl_seconds,
        }
        raw = self._post("/gateway/sanitize", body)
        return SanitizedPrompt(
            session_id=raw["session_id"],
            safe_prompt=raw["sanitized_prompt"],
            action=raw["action"],
            risk_score=raw["risk_score"],
            findings=_parse_findings(raw.get("findings", [])),
            policy_reasons=raw.get("policy_reasons", []),
            allowed_fields=raw.get("allowed_fields", []),
            tenant_id=raw.get("tenant_id", tenant_id or self._tenant_id),
            actor_id=raw.get("actor_id", user_id),
            created_at=str(raw.get("created_at", "")),
        )

    def scrub_output(
        self,
        output: str,
        # Accept positionally for backwards compat — deprecated, remove in v0.2
        session_id: Any = _UNSET,
        *,
        user_id: str,
        tenant_id: str | None = None,
        task_type: str | TaskType = TaskType.GENERAL,
        session_id_kw: str = _UNSET,  # type: ignore[assignment]
    ) -> ScrubbedOutput:
        """
        Scrub an LLM response before returning it to the caller.

        Retrieves field policy from the vault session automatically.
        Pass only the LLM response text and the session_id from sanitize().

        Parameters
        ----------
        output : str
            The raw LLM response. Max 32,000 characters.
        session_id : str
            The session_id returned by sanitize(). KEYWORD-ONLY.
            Passing it positionally is deprecated and will raise TypeError in v0.2.

            Correct::

                client.scrub_output(response, session_id=safe.session_id, user_id="your_user_id")

            Wrong — raises TypeError in v0.2::

                client.scrub_output(response, safe.session_id, user_id="your_user_id")

        user_id : str
            Identifier for the user making the request.
        tenant_id : str, optional
            Override the client-level tenant_id.
        task_type : str or TaskType, optional
            Domain context. Default: 'general_analysis'.

        Returns
        -------
        ScrubbedOutput
            scrubbed_answer is safe to return to the caller.
        """
        # Handle deprecated positional session_id
        if session_id is not _UNSET:
            warnings.warn(
                "Passing session_id positionally to scrub_output() is deprecated "
                "and will be removed in v0.2. "
                "Use: scrub_output(output, session_id=..., user_id=...)",
                DeprecationWarning,
                stacklevel=2,
            )
            resolved_session_id = session_id
        elif session_id_kw is not _UNSET:
            resolved_session_id = session_id_kw
        else:
            raise TypeError("scrub_output() missing required keyword argument: 'session_id'")

        body: dict[str, Any] = {
            "session_id": resolved_session_id,
            "answer": output,
            "user_id": user_id,
            "organization": tenant_id or self._tenant_id,
            "task_type": str(task_type),
        }
        raw = self._post("/gateway/output_sanitize", body)
        return ScrubbedOutput(
            scrubbed_answer=raw["scrubbed_answer"],
            findings=_parse_findings(raw.get("findings", [])),
            vault_replacements=[
                (pair[0], pair[1]) for pair in raw.get("vault_replacements", [])
            ],
            allowed_fields=raw.get("allowed_fields", []),
        )

    # ------------------------------------------------------------------
    # Tier 3 — authorize_tool() + approval flow
    # ------------------------------------------------------------------

    def authorize_tool(
        self,
        tool_name: str,
        target: str,
        *,
        tenant_id: str | None = None,
        task_type: str | TaskType = TaskType.GENERAL,
        sensitivity_tier: int | SensitivityTier = SensitivityTier.READ_ONLY,
        resource_class: str | None = None,
        scope_tag: str | None = None,
    ) -> ToolDecision:
        """
        Authorize a tool call through Tier 3 governance.

        Call before every tool execution. High-risk tools may require
        human approval (pending_approval) before proceeding.

        Parameters
        ----------
        tool_name : str
            Name of the tool being authorized, e.g. 'CaseFiler', 'EmailSender'.
        target : str
            The target resource, e.g. a case number, email address, or file path.
        tenant_id : str, optional
            Override the client-level tenant_id.
        task_type : str or TaskType, optional
            Domain context. Default: 'general_analysis'.
        sensitivity_tier : int or SensitivityTier, optional
            Risk level of the tool. This directly affects the authorization decision.

            ============  ===  =============================================
            Tier          Int  Examples
            ============  ===  =============================================
            READ_ONLY       1  LegalSearch, Calculator, KnowledgeBase
            PERSONAL        2  UserLookup, CRMLookup, PatientRecord
            WRITE_ACTION    3  CaseFiler, EmailSender, DatabaseWrite
            ============  ===  =============================================

            Default is 1. Pass the correct tier — passing 1 for a
            WRITE_ACTION tool means Tier 3 protection is effectively off.
        resource_class : str, optional
            Resource classification, e.g. 'court_document', 'patient_record'.
        scope_tag : str, optional
            Scope restriction tag applied to this authorization.

        Returns
        -------
        ToolDecision
            Check decision.decision before executing the tool:
              'allow'            — proceed
              'deny'             — surface decision.reason to the user
              'pending_approval' — store decision.approval_id and wait

        Examples
        --------
        ::

            from agenvia import Agenvia, SensitivityTier

            auth = client.authorize_tool(
                "CaseFiler",
                target="your_target",
                task_type="legal_review",
                sensitivity_tier=SensitivityTier.WRITE_ACTION,  # tier 3
            )

            if auth.decision == "allow":
                case_filer.submit(...)
            elif auth.decision == "deny":
                return f"Tool denied: {auth.reason}"
            elif auth.decision == "pending_approval":
                # IMPORTANT: persist approval_id to database
                db.save_approval(auth.approval_id)
                return f"Awaiting manager approval. ID: {auth.approval_id}"
        """
        body: dict[str, Any] = {
            "tenant_id": tenant_id or self._tenant_id,
            "tool_name": tool_name,
            "target": target,
            "task_type": str(task_type),
            "sensitivity_tier": int(sensitivity_tier),
            "resource_class": resource_class,
            "scope_tag": scope_tag,
        }
        raw = self._post("/gateway/tools/authorize", body)
        return ToolDecision(
            decision=raw.get("decision", "deny"),
            reason=raw.get("reason", ""),
            approval_id=raw.get("approval_id"),
            tool_name=tool_name,
            tenant_id=tenant_id or self._tenant_id,
        )

    def get_approval(self, approval_id: str) -> ApprovalStatus:
        """
        Check the status of a pending tool approval.

        Poll this until status is 'approved', 'rejected', or 'expired'.
        Do not poll more than once every 10 seconds.

        Parameters
        ----------
        approval_id : str
            The approval_id returned by authorize_tool() when
            decision == 'pending_approval'.

        Returns
        -------
        ApprovalStatus
            Current status and decision.

        Examples
        --------
        ::

            import time

            status = client.get_approval(approval_id)
            while status.status == "pending":
                time.sleep(10)
                status = client.get_approval(approval_id)

            if status.decision == "approved":
                case_filer.submit(...)
        """
        raw = self._get(f"/gateway/approvals/{approval_id}")
        return ApprovalStatus(
            approval_id=raw["approval_id"],
            status=raw.get("status", "pending"),
            decision=raw.get("decision"),
            tool_name=raw.get("tool_name", ""),
            target=raw.get("target", ""),
            reason=raw.get("reason", ""),
            created_at=str(raw.get("created_at", "")),
            decided_at=str(raw.get("decided_at")) if raw.get("decided_at") else None,
        )

    def submit_approval(
        self,
        approval_id: str,
        decision: str | ApprovalDecision,
    ) -> ApprovalStatus:
        """
        Submit an approval decision (manager / admin action).

        This is the manager-side call. Retrieve pending approvals from your
        notification system, present the tool name and reason to the manager,
        then call this with their decision.

        Parameters
        ----------
        approval_id : str
            The approval_id from authorize_tool() or get_approval().
            Must be retrieved from your database — not a local variable.
        decision : str or ApprovalDecision
            'approved' or 'rejected'.

        Returns
        -------
        ApprovalStatus
            Final status with decision recorded.

        Examples
        --------
        Full pending_approval loop::

            # --- Agent side (at tool authorization time) ---
            auth = client.authorize_tool(
                "CaseFiler", target=case_ref,
                sensitivity_tier=SensitivityTier.WRITE_ACTION,
            )
            if auth.decision == "pending_approval":
                db.save(approval_id=auth.approval_id, tool=auth.tool_name)
                notify_manager(auth.approval_id, auth.reason)
                return "Awaiting approval"

            # --- Manager side (in your approval webhook/UI) ---
            # Manager reviews the request and clicks Approve or Reject
            result = client.submit_approval(
                approval_id=db.get_approval_id(request_id),  # from database
                decision="approved",
            )
            if result.decision == "approved":
                # Resume agent — re-call authorize_tool() which will now allow
                auth = client.authorize_tool("CaseFiler", target=case_ref, ...)
        """
        body = {"decision": str(decision)}
        raw = self._post(f"/gateway/approvals/{approval_id}/decision", body)
        return ApprovalStatus(
            approval_id=approval_id,
            status=raw.get("status", "decided"),
            decision=raw.get("decision"),
            tool_name=raw.get("tool_name", ""),
            target=raw.get("target", ""),
            reason=raw.get("reason", ""),
            created_at=str(raw.get("created_at", "")),
            decided_at=str(raw.get("decided_at")) if raw.get("decided_at") else None,
        )

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> "Agenvia":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
