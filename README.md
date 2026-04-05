# Agenvia Python SDK

3-tier AI governance for autonomous agents — intent classification, PII vault, and tool authorization in one SDK.

```
pip install agenvia
```

---

## How the tiers work

Every request flows through the tiers that apply to it. They are **additive layers**, not alternatives — an autonomous customer-facing agent needs all three simultaneously.

```
User message
    │
    ▼
[ Tier 1: evaluate() ]        ← always — intent + injection + policy
    │
    ▼
[ Tier 2: sanitize() ]        ← when handling personal data
    │
    ▼
[ Your LLM ]
    │
    ▼
[ Tier 2: scrub_output() ]    ← mirrors sanitize(), runs on every response
    │
    ▼
[ Tier 3: authorize_tool() ]  ← before every tool call
    │
    ▼
Response
```

---

## Quickstart

```python
from agenvia import Agenvia, Action

client = Agenvia(api_key="av_...", tenant_id="acme-corp")

decision = client.evaluate("What are Q3 sales?", user_id="analyst-001")

if decision.action == Action.BLOCK:
    return decision.policy_reasons[0]
elif decision.action in (Action.MINIMIZE, Action.SANITIZE):
    response = llm(decision.safe_prompt)   # never use original on sanitize
else:
    response = llm(prompt)
```

Run the full example:

```bash
AGENVIA_KEY=av_... python examples/quickstart.py

# Offline / CI — no network, no real key
AGENVIA_KEY=off python examples/quickstart.py
```

---

## Authentication

```python
from agenvia import Agenvia

client = Agenvia(
    api_key="av_...",       # must start with av_ — get yours at https://app.agenvia.io/settings/api-keys
    tenant_id="acme-corp",  # your organisation identifier
)
```

Invalid key format raises `ValueError` immediately — before any network call:

```python
Agenvia(api_key="wrong_key", tenant_id="acme")
# ValueError: Invalid API key format 'wrong_ke...'. Agenvia keys start with 'av_'.
# Get yours at https://app.agenvia.io/settings/api-keys
```

### Offline / CI mode

Never hardcode real keys in CI. Use an environment variable with a sentinel value:

```python
import os
from agenvia import Agenvia

key = os.environ["AGENVIA_KEY"]

if key == "off":
    # Return a stub result — no network call
    ...
else:
    client = Agenvia(api_key=key, tenant_id="acme-corp")
```

In CI: `AGENVIA_KEY=off`  
In production: `AGENVIA_KEY=av_...`

---

## Tier 1 — evaluate()

Run before every prompt. Returns intent classification, risk score, and policy decision.

```python
from agenvia import Action, TaskType

decision = client.evaluate(
    prompt,
    user_id="user-123",
    task_type=TaskType.FINANCIAL,   # improves policy accuracy
)
```

### Actions

All five possible actions and what you must do for each:

| Action | Meaning | What to do |
|--------|---------|------------|
| `allow` | Safe | Pass original prompt to LLM |
| `minimize` | Partially sensitive | Use `decision.safe_prompt` |
| `sanitize` | PII detected | **Must** use `decision.safe_prompt` — using the original sends raw PII to the LLM |
| `local-only` | Do not send to cloud LLM | Process locally. Check `decision.local_only_trigger` for reason |
| `block` | Stop immediately | Do not pass anywhere. Surface `decision.policy_reasons` to user |

```python
if decision.action == Action.BLOCK:
    return f"Blocked: {decision.policy_reasons[0]}"

elif decision.action == Action.LOCAL_ONLY:
    # decision.local_only_trigger explains why:
    # 'policy_rule:<name>' | 'risk_threshold:<score>' | 'model_decision'
    return run_local_model(decision.safe_prompt)

elif decision.action in (Action.MINIMIZE, Action.SANITIZE):
    # SANITIZE: using the original prompt is a data leak
    response = llm(decision.safe_prompt)

else:  # Action.ALLOW
    response = llm(prompt)
```

### task_type

Passing the correct `task_type` applies domain-specific policies and improves accuracy:

| Value | Use for |
|-------|---------|
| `general_analysis` | Default — generic fallback |
| `hr_review` | HR workflows, employee data |
| `medical_query` | Healthcare, patient records |
| `financial_analysis` | Finance, revenue, trading |
| `customer_support` | Customer-facing agents |
| `legal_review` | Legal research, court documents |

```python
from agenvia import TaskType

decision = client.evaluate(prompt, user_id="u1", task_type=TaskType.HR)
```

### Decision fields

```python
decision.request_id       # str  — store for audit trail and feedback
decision.action           # str  — one of the 5 actions above
decision.risk_score       # float 0.0–1.0 — higher = more sensitive
decision.safe_prompt      # str  — use this instead of original on minimize/sanitize
decision.findings         # list[Finding] — individual detections
decision.policy_reasons   # list[str] — human-readable reasons, surface on block
decision.local_only_trigger  # str | None — why local-only was triggered
decision.policy_trace     # list[dict] — full trace for debugging
```

---

## Tier 2 — sanitize() + scrub_output()

Use when prompts contain or may contain personal data (names, SSNs, dates of birth, emails).

### sanitize()

```python
safe = client.sanitize(
    "Patient Jane Doe, DOB 1990-01-15, SSN 123-45-6789",
    user_id="nurse-001",
    task_type=TaskType.MEDICAL,
)

# IMPORTANT: persist session_id to your database before calling the LLM
# Storing it in a local variable loses it on server restart
db.save_session(request_id=request_id, session_id=safe.session_id)

response = llm(safe.safe_prompt)   # real values replaced with placeholders
```

### SanitizedPrompt fields

```python
safe.session_id      # str   — vault handle, persist to database
safe.safe_prompt     # str   — pass to LLM
safe.action          # str   — action for this prompt (same values as evaluate)
safe.risk_score      # float — 0.0–1.0
safe.findings        # list[Finding]
safe.allowed_fields  # list[str] — field labels permitted in the response
```

### scrub_output()

```python
clean = client.scrub_output(
    llm_response,
    session_id=safe.session_id,   # keyword-only — do not pass positionally
    user_id="nurse-001",
)

return clean.scrubbed_answer   # safe to return to caller
```

> **`session_id` is keyword-only.** Passing it positionally works in v0.1 but raises `DeprecationWarning` and will raise `TypeError` in v0.2:
>
> ```python
> # WRONG — deprecated, breaks in v0.2
> client.scrub_output(response, safe.session_id, user_id="u1")
>
> # CORRECT
> client.scrub_output(response, session_id=safe.session_id, user_id="u1")
> ```

### ScrubbedOutput fields

```python
clean.scrubbed_answer      # str — safe to return to caller
clean.findings             # list[Finding] — detections in LLM response
clean.vault_replacements   # list[tuple] — (real_value, placeholder) pairs replaced
clean.allowed_fields       # list[str] — fields policy permitted in response
```

---

## Tier 3 — authorize_tool()

Call before every tool execution. High-risk tools may require human approval.

### sensitivity_tier

This parameter directly affects the authorization decision. **Always pass the correct tier** — passing tier 1 for a write-action tool disables Tier 3 protection.

| Tier | Constant | Int | Examples |
|------|----------|-----|---------|
| Read-only | `SensitivityTier.READ_ONLY` | 1 | LegalSearch, Calculator, KnowledgeBase |
| Personal data | `SensitivityTier.PERSONAL` | 2 | UserLookup, CRMLookup, PatientRecord |
| Write / action | `SensitivityTier.WRITE_ACTION` | 3 | CaseFiler, EmailSender, DatabaseWrite |

```python
from agenvia import SensitivityTier

auth = client.authorize_tool(
    "CaseFiler",
    target="Chen Holdings v. Meridian Capital — 2024-CV-8821",
    task_type=TaskType.LEGAL,
    sensitivity_tier=SensitivityTier.WRITE_ACTION,
)

if auth.decision == "allow":
    case_filer.submit(...)

elif auth.decision == "deny":
    return f"Tool denied: {auth.reason}"   # auth.reason is always present

elif auth.decision == "pending_approval":
    # IMPORTANT: persist to database — not a local variable
    db.save_approval(approval_id=auth.approval_id)
    notify_manager(auth.approval_id, auth.reason)
    return f"Awaiting manager approval"
```

### ToolDecision fields

```python
auth.decision      # str — 'allow' | 'deny' | 'pending_approval'
auth.reason        # str — always present, surface to user on deny/pending
auth.approval_id   # str | None — present only on pending_approval
auth.tool_name     # str
```

---

## Human-in-the-loop approval (full loop)

```python
# --- Step 1: Agent requests tool authorization ---
auth = client.authorize_tool(
    "EmailSender",
    target="client@example.com",
    sensitivity_tier=SensitivityTier.WRITE_ACTION,
)

if auth.decision == "pending_approval":
    db.save(approval_id=auth.approval_id, tool=auth.tool_name)
    notify_manager(approval_id=auth.approval_id, reason=auth.reason)
    return "Awaiting manager approval. You will be notified."

# --- Step 2: Manager reviews in your UI / webhook ---
# Show manager: auth.tool_name, auth.reason, auth.target

result = client.submit_approval(
    approval_id=db.get(request_id),   # from database — not local variable
    decision="approved",              # or "rejected"
)

# --- Step 3: Resume agent after approval ---
if result.decision == "approved":
    auth = client.authorize_tool("EmailSender", target=..., sensitivity_tier=...)
    # now returns allow — proceed with execution

# --- Step 4: Poll for status (alternative to webhook) ---
status = client.get_approval(approval_id)
# status.status: 'pending' | 'approved' | 'rejected' | 'expired'
# status.decision: 'approved' | 'rejected' | None
```

---

## Error handling

```python
from agenvia import AgenviaError, AuthError, RateLimitError

try:
    decision = client.evaluate(prompt, user_id="u1")
except AuthError:
    # Invalid or expired API key
    redirect_to_login()
except RateLimitError:
    # Back off and retry
    time.sleep(5)
    retry()
except AgenviaError as e:
    # All other API errors
    log.error("Agenvia error %s: %s", e.status_code, e.message)
```

### Exception hierarchy

| Exception | HTTP | When |
|-----------|------|------|
| `AuthError` | 401 | Invalid or expired API key |
| `PermissionError` | 403 | Key lacks permission for this operation |
| `NotFoundError` | 404 | Approval or resource not found |
| `ValidationError` | 422 | Request payload failed validation |
| `RateLimitError` | 429 | Rate limit exceeded |
| `ServerError` | 5xx | Unexpected server error |
| `AgenviaError` | any | Base class — catches all of the above |

---

## Finding fields

Each `Finding` object in `decision.findings`:

```python
finding.label            # str   — category: 'ssn', 'email', 'dob', 'injection', etc.
finding.text             # str   — matched text excerpt
finding.confidence       # float — 0.0–1.0
finding.sensitivity_tier # int   — 1=low, 2=medium, 3=high
finding.start            # int   — start character offset in prompt
finding.end              # int   — end character offset in prompt
```

---

## Context manager

```python
with Agenvia(api_key="av_...", tenant_id="acme") as client:
    decision = client.evaluate(prompt, user_id="u1")
# HTTP connection closed automatically
```

---

## Requirements

- Python 3.10+
- `httpx>=0.27`
