"""Circuit breaker for Ollama — fails fast after consecutive failures."""

from __future__ import annotations

import time


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open and calls should not proceed."""


class CircuitBreaker:
    """Simple circuit breaker with three states: CLOSED, OPEN, HALF_OPEN.

    - CLOSED: Normal operation. Failures are counted.
    - OPEN: After ``failure_threshold`` consecutive failures, all calls are
      rejected immediately via :exc:`CircuitBreakerOpen`.
    - HALF_OPEN: After ``reset_timeout`` seconds in OPEN state, one probe
      call is allowed. Success resets to CLOSED; failure returns to OPEN.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._consecutive_failures = 0
        self._state = "closed"  # "closed" | "open" | "half_open"
        self._opened_at: float = 0.0

    @property
    def state(self) -> str:
        """Current state, accounting for reset timeout transitions."""
        if self._state == "open" and (time.monotonic() - self._opened_at) >= self.reset_timeout:
            self._state = "half_open"
        return self._state

    def is_open(self) -> bool:
        """Return True if the breaker is tripped (OPEN state)."""
        return self.state == "open"

    def check(self) -> None:
        """Raise :exc:`CircuitBreakerOpen` if calls should not proceed."""
        s = self.state
        if s == "open":
            raise CircuitBreakerOpen(
                f"Circuit breaker open after {self._consecutive_failures} consecutive failures"
            )
        # In half_open or closed, allow the call through

    def record_success(self) -> None:
        """Record a successful call — reset to CLOSED."""
        self._consecutive_failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        """Record a failed call — trip to OPEN if threshold reached."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._state = "open"
            self._opened_at = time.monotonic()
