"""Small, dependency-free request-security helpers."""

from collections import defaultdict, deque
from hmac import compare_digest
from secrets import token_urlsafe
from threading import Lock
from time import monotonic

from flask import abort, request, session


CSRF_SESSION_KEY = "_csrf_token"
CSRF_FORM_FIELD = "_csrf_token"


def client_ip():
    """Return the client address after trusted ProxyFix processing."""
    return request.remote_addr or "unknown"


def csrf_token():
    """Return the current session's CSRF token, creating it when needed."""
    token = session.get(CSRF_SESSION_KEY)
    if token is None:
        token = token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf_request():
    """Reject every unsafe request unless it contains the session CSRF token."""
    expected = session.get(CSRF_SESSION_KEY)
    supplied = request.form.get(CSRF_FORM_FIELD, "")
    if not expected or not supplied or not compare_digest(expected, supplied):
        abort(400, description="Invalid or missing CSRF token.")


class LoginRateLimiter:
    """Thread-safe, in-process protection for login attempts.

    This deliberately keeps the policy small and predictable. For a multi-worker
    production deployment, configure an equivalent shared limiter at the reverse
    proxy or replace this store with Redis-backed rate limiting.
    """

    def __init__(self, max_attempts=5, window_seconds=60, max_ip_attempts=20):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.max_ip_attempts = max_ip_attempts
        self._attempts = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, key, now):
        attempts = self._attempts[key]
        cutoff = now - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if not attempts:
            self._attempts.pop(key, None)
            return deque()
        return attempts

    def is_limited(self, ip_address, username):
        with self._lock:
            now = monotonic()
            account_attempts = self._prune(("account", ip_address, username), now)
            ip_attempts = self._prune(("ip", ip_address), now)
            return (
                len(account_attempts) >= self.max_attempts
                or len(ip_attempts) >= self.max_ip_attempts
            )

    def register_failure(self, ip_address, username):
        with self._lock:
            now = monotonic()
            self._prune(("account", ip_address, username), now).append(now)
            self._prune(("ip", ip_address), now).append(now)

    def reset_account(self, ip_address, username):
        with self._lock:
            self._attempts.pop(("account", ip_address, username), None)


login_rate_limiter = LoginRateLimiter()
