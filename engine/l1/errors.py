"""Exit codes and the exception hierarchy that maps onto them.

Exit codes are the contract with the Phlo worker (PRD 06 §2). They are not
internal detail: the worker branches on them. Every exception here carries the
code it exits with, so there is exactly one place that decides.
"""

from __future__ import annotations


class ExitCode:
    SUCCESS = 0
    DOCUMENT_REJECTED = 10
    VETOED = 11
    STAGE_FAILURE = 20
    BUDGET_EXCEEDED = 21
    INVALID_INPUT = 30
    TERMINATED = 143


class L1Error(Exception):
    """Base for every engine error that maps to a specific exit code."""

    exit_code = ExitCode.STAGE_FAILURE

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class InvalidInputError(L1Error):
    """Bad PDF, malformed criteria, unreadable path. Do not retry."""

    exit_code = ExitCode.INVALID_INPUT


class DocumentRejectedError(L1Error):
    """Classified as a non-analysable document type. Do not retry."""

    exit_code = ExitCode.DOCUMENT_REJECTED


class VetoError(L1Error):
    """A veto-tier criterion fired. This is a successful analysis with a
    terminal finding, not a failure — but the worker must treat it distinctly."""

    exit_code = ExitCode.VETOED


class StageFailureError(L1Error):
    """Recoverable stage failure. Retry permitted."""

    exit_code = ExitCode.STAGE_FAILURE


class BudgetExceededError(L1Error):
    """Hard spend ceiling hit. Do not retry without a higher budget."""

    exit_code = ExitCode.BUDGET_EXCEEDED


class InvariantViolation(StageFailureError):
    """A PRD §6 invariant was violated.

    This is deliberately a subclass of StageFailureError (exit 20) rather than a
    warning path. The whole point of the invariants is that they fail loudly
    instead of degrading silently, so there is no 'continue anyway' branch.
    """

    def __init__(self, invariant: str, message: str, detail: dict | None = None):
        super().__init__(f"[{invariant}] {message}", detail)
        self.invariant = invariant


class MissingInputError(InvariantViolation):
    """PRD §6.1 — a stage's declared input is absent or schema-invalid.

    Never a null-tolerant continue. This is the single highest-value invariant
    in the engine design (overview §6.3).
    """

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__("6.1-missing-input", message, detail)
