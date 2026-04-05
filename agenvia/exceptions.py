"""
agenvia.exceptions
~~~~~~~~~~~~~~~~~~
Exception hierarchy for the Agenvia SDK.

Catch AgenviaError to handle all SDK errors in one place:

    try:
        decision = client.evaluate(prompt, user_id="u1", tenant_id="your_tenant_id")
    except AuthError:
        # bad or expired API key
    except RateLimitError:
        # back off and retry
    except AgenviaError as e:
        # catch-all
        print(e.status_code, e.message)
"""


class AgenviaError(Exception):
    """Base class for all Agenvia SDK errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(status_code={self.status_code!r}, message={self.message!r})"


class AuthError(AgenviaError):
    """Raised when the API key is missing, invalid, or expired (HTTP 401)."""


class PermissionError(AgenviaError):
    """Raised when the API key lacks permission for the requested operation (HTTP 403)."""


class NotFoundError(AgenviaError):
    """Raised when a requested resource does not exist (HTTP 404)."""


class RateLimitError(AgenviaError):
    """Raised when the rate limit is exceeded (HTTP 429). Back off and retry."""


class ServerError(AgenviaError):
    """Raised when the Agenvia API returns an unexpected server error (HTTP 5xx)."""


class ValidationError(AgenviaError):
    """Raised when the request payload fails server-side validation (HTTP 422)."""
