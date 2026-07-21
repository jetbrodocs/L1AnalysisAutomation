"""Pipeline stages. Each stage is a separate `claude -p` invocation.

Stages never share memory; they communicate only through artifacts on disk
(PRD §5). That is what makes --resume and --stage work, and what structurally
prevents the context-loss failure described in §6.1: a stage cannot accidentally
read a value from a Python object that was never written to its input artifact.
"""

from .classification import run_classification
from .diligence import run_diligence
from .extraction import run_extraction
from .memo import run_memo
from .scoring import run_scoring

__all__ = [
    "run_classification",
    "run_extraction",
    "run_diligence",
    "run_scoring",
    "run_memo",
]
