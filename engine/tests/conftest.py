"""Shared fixtures for the live acceptance suite.

WHY THIS FILE EXISTS — a real bug it fixes:

The pipeline fixtures were originally defined with `scope="class"` inside the
test class that first used them: `scored` in `TestScoringAcceptance`, `memoed`
in `TestMemoAcceptance`. A class-scoped fixture is only visible inside the class
that defines it, so `memoed` requesting `scored` could never resolve:

    E  fixture 'scored' not found

Both memo acceptance tests ERRORED rather than ran — including
`test_a_fabricated_number_would_still_fail`, the one test whose entire purpose is
to prove invariant §6.4 was widened rather than weakened. **A test that errors
proves nothing**, and an ERROR is easy to skim past in a suite summary that
reports a nonzero pass count on the same line.

Defining them here at session scope fixes visibility AND cost: the whole
acceptance suite now shares ONE pipeline run instead of re-running the
classification→extraction→diligence→scoring chain per class. That is the
difference between roughly $4 and roughly $12 per full acceptance run.

The fixtures are chained (`classified` → `extracted` → `diligenced` → `scored`
→ `memoed`) and each returns the same run directory, so a test can depend on the
furthest stage it needs and get everything before it for free.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from l1.cli import main

ENGINE_ROOT = Path(__file__).resolve().parents[1]
CRITERIA = ENGINE_ROOT / "criteria" / "default"

# PORTABILITY: this engine is designed to be lifted into its own repository
# (see README "Portability"). Nothing under l1/ reaches outside ENGINE_ROOT, and
# the tests must not either. The reference deck is a 5.4MB third-party document
# that does not belong in the engine repo, so its location is configurable:
#
#   L1_REFERENCE_DECK=/path/to/deck.pdf pytest -m slow
#
# Fallbacks, in order: the env var, a local tests/fixtures/ copy, then the
# sibling-repo path that works in the original monorepo layout. Slow tests skip
# with a clear message when none resolve, rather than failing with a confusing
# FileNotFoundError in a fresh checkout.
_DECK_NAME = "Neo Infra Income Opportunities Fund-II Feb'26.pdf"


def _resolve_deck() -> Path | None:
    env = os.environ.get("L1_REFERENCE_DECK")
    if env:
        p = Path(env).expanduser().resolve()
        return p if p.is_file() else None
    local = ENGINE_ROOT / "tests" / "fixtures" / _DECK_NAME
    if local.is_file():
        return local
    sibling = ENGINE_ROOT.parent / "00-inbox" / _DECK_NAME
    return sibling if sibling.is_file() else None


DECK = _resolve_deck()

requires_deck = pytest.mark.skipif(
    DECK is None,
    reason=(
        "reference deck not found. Set L1_REFERENCE_DECK=/path/to/deck.pdf, or "
        f"place it at tests/fixtures/{_DECK_NAME}"
    ),
)


def _run(out: Path, *extra: str) -> int:
    return main(
        ["analyze", str(DECK), "--criteria", str(CRITERIA), "--out", str(out), *extra]
    )


@pytest.fixture(scope="session")
def run_dir(tmp_path_factory) -> Path:
    """One directory for the whole acceptance session."""
    if not DECK.exists():
        pytest.skip(f"reference deck not present: {DECK}")
    return tmp_path_factory.mktemp("neo-acceptance")


@pytest.fixture(scope="session")
def classified(run_dir: Path) -> Path:
    code = _run(run_dir, "--stage", "classification")
    assert code == 0, f"classification exited {code}"
    return run_dir


@pytest.fixture(scope="session")
def extracted(classified: Path) -> Path:
    code = _run(classified, "--stage", "extraction")
    assert code == 0, f"extraction exited {code}"
    return classified


@pytest.fixture(scope="session")
def diligenced(extracted: Path) -> Path:
    code = _run(extracted, "--stage", "diligence")
    assert code == 0, f"diligence exited {code}"
    return extracted


@pytest.fixture(scope="session")
def scored(diligenced: Path) -> Path:
    # 0 and 11 are both legitimate: 11 means a veto fired, which is a successful
    # analysis with a terminal finding, not a failure (PRD §2).
    code = _run(diligenced, "--stage", "scoring")
    assert code in (0, 11), f"scoring exited {code}"
    return diligenced


@pytest.fixture(scope="session")
def memoed(scored: Path) -> Path:
    code = _run(scored, "--stage", "memo")
    assert code in (0, 11), f"memo exited {code}"
    return scored
