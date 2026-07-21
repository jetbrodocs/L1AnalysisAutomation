"""Criteria set loading, validation, and content addressing (PRD 06 §4).

The criteria directory is produced either by Phlo (CRITERIA_SET_EXPORTED) or
hand-authored by a standalone user. Both must work, so this module validates
rather than trusts.

`content_hash` is the point of this module: it proves which exact rule text the
engine saw, independent of what the database says today. Without it a score six
months old is uninterpretable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .errors import InvalidInputError
from .fsutil import sha256_text

TIERS = ("GREEN_FLAG", "RED_FLAG", "VETO")
SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
MIN_GUIDANCE_CHARS = 40

# Heuristic for "this rule is too vague to apply". A detection guidance that
# names no concrete noun tends to be unusable ("bad disclosure" vs "no
# net-to-investor figure anywhere in the document"). Warning only, never fatal —
# an admin may legitimately author something this list does not anticipate.
CONCRETE_NOUNS = (
    "fee", "carry", "hurdle", "return", "irr", "auditor", "custodian", "registrar",
    "counsel", "valuation", "track record", "fund", "manager", "sponsor", "sebi",
    "registration", "commitment", "capital", "portfolio", "sector", "investor",
    "committee", "team", "document", "date", "distribution", "waterfall",
    "catch-up", "dpi", "exit", "clause", "succession", "enforcement", "aif",
    "number", "policy", "provider", "lp", "gp", "anchor", "position",
)


@dataclass
class Criterion:
    criterion_code: str
    name: str
    tier: str
    category: str
    severity: str
    weight: float
    detection_guidance: str
    evidence_requirement: str
    rationale: str
    remediation_prompt: str
    is_active: bool = True

    @property
    def is_veto(self) -> bool:
        return self.tier == "VETO"


@dataclass
class CriteriaSet:
    set_id: str
    set_code: str
    name: str
    version: int | None
    asset_class_scope: list[str]
    schema_version: int
    criteria: list[Criterion]
    content_hash: str
    description: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def active_criteria(self) -> list[Criterion]:
        return [c for c in self.criteria if c.is_active]

    def by_code(self, code: str) -> Criterion | None:
        for c in self.criteria:
            if c.criterion_code == code:
                return c
        return None

    def as_prompt_payload(self) -> list[dict]:
        """The rules as the model sees them.

        Deliberately excludes `rationale` — that is for the memo's justification
        of a finding, not an instruction for detecting one. Including it invites
        the model to fire a criterion because the rationale sounds persuasive
        rather than because the document evidences it.
        """
        return [
            {
                "criterion_code": c.criterion_code,
                "name": c.name,
                "tier": c.tier,
                "category": c.category,
                "severity": c.severity,
                "detection_guidance": c.detection_guidance.strip(),
                "evidence_requirement": c.evidence_requirement.strip(),
            }
            for c in self.active_criteria
        ]


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise InvalidInputError(f"criteria file missing: {path}")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise InvalidInputError(f"criteria file is not valid YAML: {path} ({exc})") from exc
    if not isinstance(data, dict):
        raise InvalidInputError(f"criteria file must contain a mapping at top level: {path}")
    return data


def load_criteria(criteria_dir: Path) -> CriteriaSet:
    """Load and validate a criteria directory. Raises InvalidInputError (exit 30)."""
    criteria_dir = Path(criteria_dir)
    if not criteria_dir.is_dir():
        raise InvalidInputError(f"criteria directory not found: {criteria_dir}")

    set_path = criteria_dir / "set.yaml"
    crit_path = criteria_dir / "criteria.yaml"
    set_meta = _load_yaml(set_path)
    crit_doc = _load_yaml(crit_path)

    for key in ("set_id", "set_code", "name", "schema_version"):
        if not set_meta.get(key):
            raise InvalidInputError(f"{set_path}: missing required field '{key}'")

    raw = crit_doc.get("criteria")
    if not isinstance(raw, list) or not raw:
        raise InvalidInputError(f"{crit_path}: 'criteria' must be a non-empty list")

    warnings: list[str] = []
    criteria: list[Criterion] = []
    seen: set[str] = set()

    for idx, row in enumerate(raw):
        loc = f"{crit_path}: criteria[{idx}]"
        if not isinstance(row, dict):
            raise InvalidInputError(f"{loc} is not a mapping")

        code = row.get("criterion_code")
        if not code:
            raise InvalidInputError(f"{loc}: missing 'criterion_code'")
        if code in seen:
            raise InvalidInputError(f"{loc}: duplicate criterion_code {code!r}")
        seen.add(code)

        tier = row.get("tier")
        if tier not in TIERS:
            raise InvalidInputError(
                f"{loc} ({code}): tier {tier!r} not one of {list(TIERS)}"
            )

        severity = row.get("severity")
        if severity not in SEVERITIES:
            raise InvalidInputError(
                f"{loc} ({code}): severity {severity!r} not one of {list(SEVERITIES)}"
            )

        try:
            weight = float(row.get("weight", 1.0))
        except (TypeError, ValueError):
            raise InvalidInputError(
                f"{loc} ({code}): weight {row.get('weight')!r} is not numeric"
            ) from None
        if weight <= 0:
            raise InvalidInputError(f"{loc} ({code}): weight must be > 0, got {weight}")

        guidance = (row.get("detection_guidance") or "").strip()
        if len(guidance) < MIN_GUIDANCE_CHARS:
            raise InvalidInputError(
                f"{loc} ({code}): detection_guidance is {len(guidance)} chars, "
                f"minimum {MIN_GUIDANCE_CHARS}. Vague rules produce vague findings."
            )
        if not any(noun in guidance.lower() for noun in CONCRETE_NOUNS):
            warnings.append(
                f"{code}: detection_guidance contains no concrete noun — "
                "likely unusable by the engine"
            )

        for req in ("name", "category", "evidence_requirement"):
            if not (row.get(req) or "").strip():
                raise InvalidInputError(f"{loc} ({code}): missing required field '{req}'")

        criteria.append(
            Criterion(
                criterion_code=code,
                name=row["name"].strip(),
                tier=tier,
                category=row["category"].strip(),
                severity=severity,
                weight=weight,
                detection_guidance=guidance,
                evidence_requirement=row["evidence_requirement"].strip(),
                rationale=(row.get("rationale") or "").strip(),
                remediation_prompt=(row.get("remediation_prompt") or "").strip(),
                is_active=bool(row.get("is_active", True)),
            )
        )

    if not any(c.is_active for c in criteria):
        raise InvalidInputError(f"{crit_path}: set contains no active criteria")

    # Content hash over the normalised rule text, not the raw file bytes.
    # Reformatting the YAML must not change the hash; changing a rule must.
    canonical = json.dumps(
        {
            "set_code": set_meta["set_code"],
            "version": set_meta.get("version"),
            "criteria": [
                {
                    "criterion_code": c.criterion_code,
                    "name": c.name,
                    "tier": c.tier,
                    "category": c.category,
                    "severity": c.severity,
                    "weight": c.weight,
                    "detection_guidance": c.detection_guidance,
                    "evidence_requirement": c.evidence_requirement,
                    "rationale": c.rationale,
                    "remediation_prompt": c.remediation_prompt,
                    "is_active": c.is_active,
                }
                for c in sorted(criteria, key=lambda x: x.criterion_code)
            ],
        },
        sort_keys=True,
        ensure_ascii=False,
    )

    return CriteriaSet(
        set_id=str(set_meta["set_id"]),
        set_code=str(set_meta["set_code"]),
        name=str(set_meta["name"]),
        version=set_meta.get("version"),
        asset_class_scope=list(set_meta.get("asset_class_scope") or []),
        schema_version=int(set_meta["schema_version"]),
        description=str(set_meta.get("description") or ""),
        criteria=criteria,
        content_hash="sha256:" + sha256_text(canonical),
        warnings=warnings,
    )
