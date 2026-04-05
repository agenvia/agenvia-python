"""
Agenvia SDK — Quickstart
========================
Covers all three governance tiers in under 80 lines.
Run with a real API key:

    AGENVIA_KEY=av_... python examples/quickstart.py

Offline / CI mode (no network call, no real key needed):

    AGENVIA_KEY=off python examples/quickstart.py
"""

import os
import sys

# ---------------------------------------------------------------------------
# Offline / CI stub — set AGENVIA_KEY=off to skip all network calls
# ---------------------------------------------------------------------------
AGENVIA_KEY = os.getenv("AGENVIA_KEY", "")
OFFLINE = AGENVIA_KEY == "off"

if OFFLINE:
    print("Running in offline/CI mode — no network calls will be made.\n")

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
from agenvia import (
    Action,
    Agenvia,
    AgenviaError,
    SensitivityTier,
    TaskType,
)

# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------
if not OFFLINE:
    client = Agenvia(
        api_key=AGENVIA_KEY,
        tenant_id="acme-corp",
    )

# ---------------------------------------------------------------------------
# Tier 1 — evaluate()
# ---------------------------------------------------------------------------
print("=" * 60)
print("Tier 1 — evaluate()")
print("=" * 60)

prompt = "What is our Q3 revenue for client Margaret Chen, SSN 456-78-9012?"

if OFFLINE:
    print(f"[offline] Would evaluate: {prompt[:60]}...")
else:
    try:
        decision = client.evaluate(
            prompt,
            user_id="analyst-001",
            task_type=TaskType.FINANCIAL,
        )
        print(f"action      : {decision.action}")
        print(f"risk_score  : {decision.risk_score:.2f}")
        print(f"findings    : {len(decision.findings)} detected")
        if decision.findings:
            top = decision.findings[0]
            print(f"top finding : [{top.label}] '{top.text}' ({top.confidence:.0%} conf)")

        # Branch on action
        if decision.action == Action.BLOCK:
            print(f"BLOCKED: {decision.policy_reasons[0]}")
            sys.exit(0)
        elif decision.action == Action.LOCAL_ONLY:
            print(f"LOCAL ONLY — trigger: {decision.local_only_trigger}")
            sys.exit(0)
        elif decision.action in (Action.MINIMIZE, Action.SANITIZE):
            prompt_to_llm = decision.safe_prompt
            print(f"safe_prompt : {prompt_to_llm[:60]}...")
        else:
            prompt_to_llm = prompt

    except AgenviaError as e:
        print(f"Error ({e.status_code}): {e.message}")
        sys.exit(1)

# ---------------------------------------------------------------------------
# Tier 2 — sanitize() + scrub_output()
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("Tier 2 — sanitize() + scrub_output()")
print("=" * 60)

pii_prompt = "Draft a summary for patient Jane Doe, DOB 1990-01-15, SSN 123-45-6789."

if OFFLINE:
    print(f"[offline] Would sanitize: {pii_prompt[:60]}...")
    print("[offline] session_id would be saved to database here")
    print("[offline] LLM would receive redacted prompt")
    print("[offline] scrub_output() would restore safe values in response")
else:
    try:
        safe = client.sanitize(
            pii_prompt,
            user_id="nurse-001",
            task_type=TaskType.MEDICAL,
        )
        print(f"session_id  : {safe.session_id}")
        print(f"safe_prompt : {safe.safe_prompt[:80]}...")
        print(f"action      : {safe.action}")
        print(f"risk_score  : {safe.risk_score:.2f}")

        # IMPORTANT: in production, save session_id to your database here
        # db.save_session(request_id=..., session_id=safe.session_id)

        # Simulate LLM response (replace with real LLM call)
        mock_llm_response = f"Summary prepared for {safe.safe_prompt[:40]}..."

        # Scrub the output — session_id is keyword-only
        clean = client.scrub_output(
            mock_llm_response,
            session_id=safe.session_id,   # keyword-only — never pass positionally
            user_id="nurse-001",
            task_type=TaskType.MEDICAL,
        )
        print(f"scrubbed    : {clean.scrubbed_answer[:80]}...")

    except AgenviaError as e:
        print(f"Error ({e.status_code}): {e.message}")

# ---------------------------------------------------------------------------
# Tier 3 — authorize_tool()
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("Tier 3 — authorize_tool()")
print("=" * 60)

if OFFLINE:
    print("[offline] Would authorize: CaseFiler with sensitivity_tier=3")
    print("[offline] High-risk tools may return pending_approval")
    print("[offline] approval_id must be saved to database, not memory")
else:
    try:
        auth = client.authorize_tool(
            "CaseFiler",
            target="Chen Holdings v. Meridian Capital — 2024-CV-8821",
            task_type=TaskType.LEGAL,
            sensitivity_tier=SensitivityTier.WRITE_ACTION,  # tier 3 — required for court filings
        )
        print(f"decision    : {auth.decision}")
        print(f"reason      : {auth.reason}")

        if auth.decision == "allow":
            print("Tool authorized — proceed with execution")
        elif auth.decision == "deny":
            print(f"Tool denied: {auth.reason}")
        elif auth.decision == "pending_approval":
            print(f"Awaiting approval. ID: {auth.approval_id}")
            print("Save approval_id to database — not a local variable")
            # db.save_approval(approval_id=auth.approval_id)

    except AgenviaError as e:
        print(f"Error ({e.status_code}): {e.message}")

print()
print("Done.")
