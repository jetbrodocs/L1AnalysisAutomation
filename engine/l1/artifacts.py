"""Stage artifact envelope, and the invariant checks that gate every write.

This module is where PRD §6.1 and §6.3 actually live. Everything else in the
engine is plumbing around these assertions.

The design rule: an artifact is validated *before* it is written, and its inputs
are validated *before* the stage does any work. There is no path that writes a
non-conforming artifact and no path that starts a stage on absent input.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import SCHEMA_VERSION
from .unresolved import assert_entries_valid
from .errors import InvariantViolation, MissingInputError
from .fsutil import atomic_write_json, read_json, sha256_text

STAGES = ("classification", "extraction", "diligence", "scoring", "memo")

ARTIFACT_FILENAMES = {
    "classification": "01-classification.json",
    "extraction": "02-extraction.json",
    "diligence": "03-diligence.json",
    "scoring": "04-scoring.json",
    "memo": "05-memo.json",
}

# Declared input contract per stage (PRD §5). The memo stage receives *all*
# prior artifacts — that is the documented failure this invariant exists to
# prevent (a memo generated from document grounding alone, contradicting the
# scorecard printed inside it).
STAGE_INPUTS: dict[str, tuple[str, ...]] = {
    "classification": (),
    "extraction": ("classification",),
    "diligence": ("classification", "extraction"),
    "scoring": ("classification", "extraction", "diligence"),
    "memo": ("classification", "extraction", "diligence", "scoring"),
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_envelope(
    stage: str,
    result: Any,
    unresolved: list[dict],
    citations: list[dict] | None = None,
    inputs_hash: str | None = None,
) -> dict:
    """Construct the common stage envelope (PRD §3).

    `unresolved` is passed positionally and required — not defaulted to []. A
    caller that has not thought about what the stage failed to determine should
    not be able to omit the field by accident, because silently dropping what
    could not be found is precisely the failure mode the field exists to prevent.
    """
    if stage not in STAGES:
        raise InvariantViolation("envelope", f"unknown stage {stage!r}")
    if unresolved is None:
        raise InvariantViolation(
            "6.x-unresolved-mandatory",
            f"stage {stage!r} passed unresolved=None; must be a list, empty if nothing unresolved",
        )
    return {
        "stage": stage,
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "inputs_hash": inputs_hash,
        "result": result,
        "unresolved": list(unresolved),
        "citations": list(citations or []),
    }


# --------------------------------------------------------------------------
# Invariant 6.1 — no stage proceeds on missing input
# --------------------------------------------------------------------------

def validate_envelope(obj: Any, expected_stage: str, source: str) -> dict:
    """Assert an object is a schema-valid envelope for `expected_stage`.

    Raises MissingInputError (exit 20) on any deviation. This is intentionally
    strict about `unresolved`: a stage artifact that omits the key is treated as
    invalid input, not as 'nothing unresolved'.
    """
    if not isinstance(obj, dict):
        raise MissingInputError(
            f"{source}: expected a JSON object envelope, got {type(obj).__name__}"
        )

    stage = obj.get("stage")
    if stage != expected_stage:
        raise MissingInputError(
            f"{source}: envelope declares stage {stage!r}, expected {expected_stage!r}",
            {"found": stage, "expected": expected_stage},
        )

    sv = obj.get("schema_version")
    if sv != SCHEMA_VERSION:
        raise MissingInputError(
            f"{source}: schema_version {sv!r} is not the supported version {SCHEMA_VERSION}",
            {"found": sv, "expected": SCHEMA_VERSION},
        )

    if "result" not in obj:
        raise MissingInputError(f"{source}: envelope has no 'result' key")
    if obj["result"] is None:
        raise MissingInputError(
            f"{source}: envelope 'result' is null — a null result is not a valid input"
        )

    # Mandatory even when empty (PRD §3).
    if "unresolved" not in obj:
        raise MissingInputError(
            f"{source}: envelope omits mandatory 'unresolved' key "
            "(must be present even when empty)"
        )
    if not isinstance(obj["unresolved"], list):
        raise MissingInputError(
            f"{source}: 'unresolved' must be a list, got {type(obj['unresolved']).__name__}"
        )

    if not isinstance(obj.get("citations", []), list):
        raise MissingInputError(f"{source}: 'citations' must be a list when present")

    return obj


def load_stage_artifact(out_dir: Path, stage: str) -> dict:
    """Load and validate one stage artifact from disk."""
    path = Path(out_dir) / ARTIFACT_FILENAMES[stage]
    if not path.exists():
        raise MissingInputError(
            f"required input artifact for stage '{stage}' is absent: {path}",
            {"stage": stage, "path": str(path)},
        )
    try:
        obj = read_json(path)
    except Exception as exc:
        raise MissingInputError(
            f"required input artifact for stage '{stage}' is not readable JSON: {path} ({exc})",
            {"stage": stage, "path": str(path)},
        ) from exc
    return validate_envelope(obj, stage, str(path))


def assert_inputs_present(out_dir: Path, stage: str) -> dict[str, dict]:
    """PRD §6.1 — assert presence and schema-validity of every declared input.

    Called at the top of every stage, before any work. Returns the loaded inputs
    so the caller cannot accidentally re-read them unvalidated.

    There is deliberately no `strict=False` parameter. A caller that wants to
    proceed on missing input is asking for the failure mode this prevents.
    """
    required = STAGE_INPUTS.get(stage)
    if required is None:
        raise InvariantViolation("6.1-missing-input", f"unknown stage {stage!r}")
    return {name: load_stage_artifact(out_dir, name) for name in required}


def inputs_hash_of(inputs: dict[str, dict]) -> str:
    """Hash of the exact input artifacts a stage consumed.

    Makes 'which inputs produced this output' provable rather than inferred, and
    lets --resume detect that an upstream artifact changed under a downstream one.
    """
    import json as _json

    parts = [
        f"{name}:{sha256_text(_json.dumps(inputs[name], sort_keys=True))}"
        for name in sorted(inputs)
    ]
    return "sha256:" + sha256_text("|".join(parts))


# --------------------------------------------------------------------------
# Invariant 6.3 — every finding cites evidence
# --------------------------------------------------------------------------

def validate_finding_evidence(findings: Iterable[dict], source: str) -> None:
    """PRD §6.3 — a fired finding with empty `evidence` and no `absence_evidence`
    is invalid. Checked in code before the artifact is written.

    Only *fired* findings are checked. A criterion that did not fire has nothing
    to evidence; requiring evidence for a non-event would be incoherent.
    """
    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise InvariantViolation(
                "6.3-evidence-required",
                f"{source}: finding at index {idx} is not an object",
            )
        code = finding.get("criterion_code", f"<index {idx}>")
        if not finding.get("fired"):
            continue

        evidence = finding.get("evidence") or []
        absence = (finding.get("absence_evidence") or "").strip()

        if not isinstance(evidence, list):
            raise InvariantViolation(
                "6.3-evidence-required",
                f"{source}: {code} 'evidence' must be a list",
            )

        if not evidence and not absence:
            raise InvariantViolation(
                "6.3-evidence-required",
                f"{source}: {code} fired with empty evidence and no absence_evidence. "
                "A finding without a source page is a bug, not a low-confidence result.",
                {"criterion_code": code},
            )

        # Each evidence item must carry a page and a quote. A citation without a
        # page is not a citation.
        for e_idx, item in enumerate(evidence):
            if not isinstance(item, dict):
                raise InvariantViolation(
                    "6.3-evidence-required",
                    f"{source}: {code} evidence[{e_idx}] is not an object",
                )
            page = item.get("page")
            quote = (item.get("quote") or "").strip()
            if not isinstance(page, int) or page < 1:
                raise InvariantViolation(
                    "6.3-evidence-required",
                    f"{source}: {code} evidence[{e_idx}] has no valid page number "
                    f"(got {page!r})",
                    {"criterion_code": code},
                )
            if not quote:
                raise InvariantViolation(
                    "6.3-evidence-required",
                    f"{source}: {code} evidence[{e_idx}] (page {page}) has an empty quote",
                    {"criterion_code": code},
                )


def validate_extraction_fields(result: Any, source: str) -> None:
    """Every extracted field carries {value, page, quote, confidence}.
    A field with no page reference is invalid output (PRD §5 stage 2).

    Walks the result tree looking for anything shaped like an extraction field —
    i.e. any object carrying a 'value' key — and enforces the contract on it.
    Fields whose value is null are exempt from the page requirement: 'we looked
    and it is not there' is a legitimate result, and it belongs in `unresolved`.
    """

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if "value" in node and ("page" in node or "quote" in node):
                if node.get("value") is None:
                    return  # not-found is legitimate; recorded in unresolved
                page = node.get("page")
                if not isinstance(page, int) or page < 1:
                    raise InvariantViolation(
                        "6.3-evidence-required",
                        f"{source}: extracted field '{path}' has value "
                        f"{node.get('value')!r} but no valid page reference (got {page!r})",
                        {"field": path},
                    )
                if not (node.get("quote") or "").strip():
                    raise InvariantViolation(
                        "6.3-evidence-required",
                        f"{source}: extracted field '{path}' (page {page}) has an empty quote",
                        {"field": path},
                    )
                return
            for key, val in node.items():
                walk(val, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for i, val in enumerate(node):
                walk(val, f"{path}[{i}]")

    walk(result, "")


def write_artifact(
    out_dir: Path,
    stage: str,
    envelope: dict,
) -> Path:
    """Validate then write. Validation is not optional and not a flag.

    The ordering matters: we validate the envelope we are about to write against
    the same rules we apply to inputs we read. An artifact this engine produces
    must be one this engine would accept.
    """
    validate_envelope(envelope, stage, f"<outgoing {stage} artifact>")

    # PRD §3 — `unresolved` entries are structured objects, validated here for the
    # same reason §6.3 is: an artifact that fails the contract must never reach
    # disk, where the next stage would read it as valid. A downstream consumer
    # routes each entry by `kind`, so a malformed entry is a routing failure
    # waiting to happen rather than a cosmetic problem.
    assert_entries_valid(envelope.get("unresolved"), f"<outgoing {stage} artifact>")

    result = envelope["result"]
    if stage == "extraction":
        validate_extraction_fields(result, f"<outgoing {stage} artifact>")
    if stage == "scoring":
        findings = result.get("findings", []) if isinstance(result, dict) else []
        validate_finding_evidence(findings, f"<outgoing {stage} artifact>")

    path = Path(out_dir) / ARTIFACT_FILENAMES[stage]
    atomic_write_json(path, envelope)
    return path
