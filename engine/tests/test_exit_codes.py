"""Exit codes are the contract with the Phlo worker (PRD §2), which branches on
them. A wrong exit code causes the wrong retry behaviour, so they are pinned.

These are fast: none of them reaches a `claude` call.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from l1.artifacts import ARTIFACT_FILENAMES
from l1.cli import main
from l1.errors import ExitCode
from l1.fsutil import atomic_write_json

CRITERIA = Path(__file__).resolve().parents[1] / "criteria" / "default"

# Enough of a PDF to fail the *magic bytes* check meaningfully, but NOT parseable
# as a page tree. Used only where the engine should reject before page counting.
MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


@pytest.fixture(scope="session")
def real_pdf(tmp_path_factory):
    """A genuinely parseable single-page PDF.

    The stage-failure tests need to get PAST ingestion to reach the invariant
    check, so a stub whose page tree pypdf cannot read would exit 30 (invalid
    input) before the invariant ever runs — testing the wrong thing.
    """
    pypdf = pytest.importorskip("pypdf")
    path = tmp_path_factory.mktemp("pdf") / "one-page.pdf"
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


_UNSET = object()


def _envelope(stage, result=_UNSET):
    """Build a stage envelope.

    `result` uses a sentinel default, not None: passing result=None must be able
    to produce a genuinely null result, since that is exactly the corrupt-input
    case invariant 6.1 has to reject. An `if result is not None` default silently
    substituted a valid body and made the test assert nothing.
    """
    return {
        "stage": stage, "schema_version": 1, "generated_at": "2026-07-20T00:00:00Z",
        "inputs_hash": None,
        "result": {"ok": True} if result is _UNSET else result,
        "unresolved": [], "citations": [],
    }


class TestInvalidInputExit30:

    def test_missing_pdf(self, tmp_path):
        assert main(["analyze", str(tmp_path / "nope.pdf"), "--criteria", str(CRITERIA),
                     "--out", str(tmp_path / "o")]) == ExitCode.INVALID_INPUT

    def test_file_without_pdf_magic_bytes(self, tmp_path):
        """The extension is a claim by whoever named the file; the magic bytes
        are a property of the content."""
        fake = tmp_path / "deck.pdf"
        fake.write_bytes(b"this is not a PDF")
        assert main(["analyze", str(fake), "--criteria", str(CRITERIA),
                     "--out", str(tmp_path / "o")]) == ExitCode.INVALID_INPUT

    def test_zero_byte_pdf(self, tmp_path):
        empty = tmp_path / "empty.pdf"
        empty.write_bytes(b"")
        assert main(["analyze", str(empty), "--criteria", str(CRITERIA),
                     "--out", str(tmp_path / "o")]) == ExitCode.INVALID_INPUT

    def test_missing_criteria_dir(self, tmp_path):
        pdf = tmp_path / "d.pdf"
        pdf.write_bytes(MINIMAL_PDF)
        assert main(["analyze", str(pdf), "--criteria", str(tmp_path / "nope"),
                     "--out", str(tmp_path / "o")]) == ExitCode.INVALID_INPUT

    def test_criteria_set_with_no_criteria(self, tmp_path):
        d = tmp_path / "crit"
        d.mkdir()
        (d / "set.yaml").write_text("set_id: x\nset_code: y\nname: z\nschema_version: 1\n")
        (d / "criteria.yaml").write_text("criteria: []\n")
        assert main(["validate", str(d)]) == ExitCode.INVALID_INPUT

    def test_unknown_stage_name(self, tmp_path):
        pdf = tmp_path / "d.pdf"
        pdf.write_bytes(MINIMAL_PDF)
        assert main(["analyze", str(pdf), "--criteria", str(CRITERIA),
                     "--out", str(tmp_path / "o"), "--stage", "nonsense"]) == ExitCode.INVALID_INPUT

    def test_unimplemented_stage_is_rejected_not_silently_skipped(self, tmp_path):
        """Asking for a PRD-specified but unbuilt stage must say so, not no-op."""
        pdf = tmp_path / "d.pdf"
        pdf.write_bytes(MINIMAL_PDF)
        assert main(["analyze", str(pdf), "--criteria", str(CRITERIA),
                     "--out", str(tmp_path / "o"), "--stage", "memo"]) == ExitCode.INVALID_INPUT


class TestStageFailureExit20:

    @staticmethod
    def _prepared_out(tmp_path, real_pdf):
        """A run directory that has already ingested, so the next thing to run is
        the stage's input assertion and nothing else."""
        out = tmp_path / "out"
        pages = out / "00-pages"
        pages.mkdir(parents=True)
        (pages / "page-001.txt").write_text("some text")
        (out / "00-source.pdf").write_bytes(real_pdf.read_bytes())
        return out

    def test_missing_upstream_artifact_is_20_not_30(self, tmp_path, real_pdf):
        """A missing input is RECOVERABLE (the worker may retry after the upstream
        stage is re-run), which is why it is 20 and not 30. Invariant 6.1."""
        out = self._prepared_out(tmp_path, real_pdf)
        assert main(["analyze", str(real_pdf), "--criteria", str(CRITERIA),
                     "--out", str(out), "--stage", "extraction",
                     "--resume"]) == ExitCode.STAGE_FAILURE

    def test_corrupt_upstream_artifact_is_20(self, tmp_path, real_pdf):
        out = self._prepared_out(tmp_path, real_pdf)
        (out / ARTIFACT_FILENAMES["classification"]).write_text("{ not json")
        assert main(["analyze", str(real_pdf), "--criteria", str(CRITERIA), "--out", str(out),
                     "--stage", "extraction", "--resume"]) == ExitCode.STAGE_FAILURE

    def test_null_result_upstream_is_20(self, tmp_path, real_pdf):
        out = self._prepared_out(tmp_path, real_pdf)
        atomic_write_json(out / ARTIFACT_FILENAMES["classification"],
                          _envelope("classification", result=None))
        assert main(["analyze", str(real_pdf), "--criteria", str(CRITERIA), "--out", str(out),
                     "--stage", "extraction", "--resume"]) == ExitCode.STAGE_FAILURE


class TestSuccessExit0:

    def test_validate_on_the_seed_set(self):
        assert main(["validate", str(CRITERIA)]) == ExitCode.SUCCESS

    def test_version(self):
        assert main(["version"]) == ExitCode.SUCCESS

    def test_inspect_a_run_directory(self, tmp_path):
        atomic_write_json(tmp_path / "run.json", {
            "run_id": "r", "engine_version": "0.1.0", "schema_version": 1,
            "source": {"filename": "f.pdf", "sha256": "abc", "page_count": 1, "bytes": 1},
            "criteria": {"set_id": "s", "set_code": "CS", "version": 1, "content_hash": "sha256:x"},
            "model": "m", "started_at": "t", "completed_at": "t", "status": "completed",
            "stages_completed": [], "cost_usd": 0.0,
        })
        assert main(["inspect", str(tmp_path)]) == ExitCode.SUCCESS

    def test_inspect_without_run_json_is_30(self, tmp_path):
        assert main(["inspect", str(tmp_path)]) == ExitCode.INVALID_INPUT


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
