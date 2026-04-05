"""
Basic SDK tests — run with pytest.

Uses pytest-httpx to intercept HTTP calls so no real API key is needed.
"""

import warnings
import pytest

from agenvia import Agenvia, Action, AgenviaError, AuthError, RateLimitError
from agenvia.models import Decision


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return Agenvia(api_key="av_test_key", tenant_id="test-tenant")


# ---------------------------------------------------------------------------
# Init validation
# ---------------------------------------------------------------------------

def test_invalid_key_prefix_raises():
    with pytest.raises(ValueError, match="av_"):
        Agenvia(api_key="tp_wrong", tenant_id="test")


def test_empty_key_raises():
    with pytest.raises(ValueError):
        Agenvia(api_key="", tenant_id="test")


def test_valid_key_accepted():
    c = Agenvia(api_key="av_validkey123", tenant_id="test")
    assert c is not None


# ---------------------------------------------------------------------------
# Action enum
# ---------------------------------------------------------------------------

def test_action_string_comparison():
    assert Action.ALLOW == "allow"
    assert Action.SANITIZE == "sanitize"
    assert Action.LOCAL_ONLY == "local-only"
    assert Action.BLOCK == "block"
    assert Action.MINIMIZE == "minimize"


def test_action_in_check():
    action = "sanitize"
    assert action in (Action.MINIMIZE, Action.SANITIZE)


# ---------------------------------------------------------------------------
# scrub_output — keyword-only deprecation warning
# ---------------------------------------------------------------------------

def test_scrub_output_positional_session_id_warns(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url__regex=r".*/gateway/output_sanitize",
        json={
            "scrubbed_answer": "safe response",
            "findings": [],
            "vault_replacements": [],
            "allowed_fields": [],
            "intent_type": "task_request",
        },
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client.scrub_output(
            "some response",
            "session-123",   # positional — should warn
            user_id="u1",
        )

    dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(dep_warnings) == 1
    assert "session_id" in str(dep_warnings[0].message)
    assert "v0.2" in str(dep_warnings[0].message)


def test_scrub_output_keyword_session_id_no_warning(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url__regex=r".*/gateway/output_sanitize",
        json={
            "scrubbed_answer": "safe response",
            "findings": [],
            "vault_replacements": [],
            "allowed_fields": [],
            "intent_type": "task_request",
        },
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client.scrub_output(
            "some response",
            session_id="session-123",   # keyword — no warning
            user_id="u1",
        )

    dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(dep_warnings) == 0


# ---------------------------------------------------------------------------
# evaluate() — sanitize action warning
# ---------------------------------------------------------------------------

def test_evaluate_sanitize_action_emits_user_warning(client, httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url__regex=r".*/gateway/prompt",
        json={
            "request_id": "req-1",
            "action": "sanitize",
            "risk_level": "sanitize",
            "risk_score": 0.7,
            "exposure_risk": "high",
            "recommended_route": "sanitize",
            "findings": [],
            "sanitized_prompt": "safe prompt",
            "minimized_prompt": "safe prompt",
            "retrieved_context": [],
            "outbound_prompt": "safe prompt",
            "outbound_context": [],
            "output_blocked": False,
            "output_findings": [],
            "policy_reasons": ["PII detected"],
            "policy_trace": [],
            "policy_version": "v1",
            "tenant_id": "test-tenant",
            "actor_id": "u1",
            "created_at": "2026-01-01T00:00:00Z",
        },
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        decision = client.evaluate("some prompt with SSN", user_id="u1")

    assert decision.action == Action.SANITIZE
    user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
    assert len(user_warnings) == 1
    assert "safe_prompt" in str(user_warnings[0].message)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_auth_error_on_401(client, httpx_mock):
    httpx_mock.add_response(status_code=401, json={"detail": "invalid api key"})
    with pytest.raises(AuthError) as exc:
        client.evaluate("prompt", user_id="u1")
    assert exc.value.status_code == 401


def test_rate_limit_error_on_429(client, httpx_mock):
    httpx_mock.add_response(status_code=429, json={"detail": "rate limit exceeded"})
    with pytest.raises(RateLimitError):
        client.evaluate("prompt", user_id="u1")


def test_generic_agenvia_error_catches_all(client, httpx_mock):
    httpx_mock.add_response(status_code=500, json={"detail": "server error"})
    with pytest.raises(AgenviaError):
        client.evaluate("prompt", user_id="u1")
