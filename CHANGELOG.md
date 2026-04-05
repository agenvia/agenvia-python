# Changelog

## [0.2.0] — Planned

### Breaking changes
- `scrub_output()`: positional `session_id` removed. Use keyword argument only:
  ```python
  # v0.1.x — works but emits DeprecationWarning
  client.scrub_output(response, safe.session_id, user_id="u1")

  # v0.2.0 — only this form is accepted
  client.scrub_output(response, session_id=safe.session_id, user_id="u1")
  ```

### Migration guide
Search your codebase for `scrub_output(` and verify all calls use `session_id=` as a keyword argument before upgrading.

---

## [0.1.0] — Initial release

### Added
- `Agenvia` client with full Tier 1/2/3 governance
- `Action` enum — all 5 actions: `allow`, `minimize`, `sanitize`, `local-only`, `block`
- `TaskType` enum — domain-specific policy context
- `SensitivityTier` enum — `READ_ONLY=1`, `PERSONAL=2`, `WRITE_ACTION=3`
- `Decision`, `SanitizedPrompt`, `ScrubbedOutput`, `ToolDecision`, `ApprovalStatus` models
- `AgenviaError` exception hierarchy — `AuthError`, `RateLimitError`, `ServerError`, etc.
- `py.typed` marker for IDE type information
- `examples/quickstart.py` with offline/CI mode support
- `UserWarning` when `evaluate()` returns `sanitize` action
- `DeprecationWarning` when `session_id` passed positionally to `scrub_output()`
- `local_only_trigger` field on `Decision` explaining why `local-only` was returned
- `ToolDecision.reason` field — always present, surface to users on deny/pending
