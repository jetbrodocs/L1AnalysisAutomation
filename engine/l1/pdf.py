"""PDF ingestion and page-text extraction.

Page numbers here are 1-based and are the citation currency of the entire
engine. Every finding cites a page; if page numbering drifts between extraction
and citation, every citation in the run is silently wrong. So the page number is
derived once, from the physical page index, and never renumbered.

Known limitation (PRD §9 open question, unresolved): text extracted from
PowerPoint-derived PDFs loses spatial layout, so a "page 37" citation points at
a slide whose meaning may depend on a chart the text layer does not capture.
This engine cites page-level and does not attempt to resolve that.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .errors import InvalidInputError
from .fsutil import atomic_write_text

PDF_MAGIC = b"%PDF-"


def assert_readable_pdf(path: Path) -> int:
    """Validate the file is a readable PDF and return its size in bytes.

    Checks magic bytes rather than the extension: the extension is a claim by
    whoever named the file, the magic bytes are a property of the content.
    """
    path = Path(path)
    if not path.exists():
        raise InvalidInputError(f"PDF not found: {path}")
    if not path.is_file():
        raise InvalidInputError(f"not a regular file: {path}")

    size = path.stat().st_size
    if size == 0:
        raise InvalidInputError(f"PDF is zero bytes: {path}")

    try:
        with open(path, "rb") as fh:
            head = fh.read(len(PDF_MAGIC))
    except OSError as exc:
        # A dataless sync placeholder can stat() fine and fail or block here.
        raise InvalidInputError(
            f"PDF exists but could not be read: {path} ({exc}). "
            "If this file is in a sync client's folder it may be a dataless placeholder."
        ) from exc

    if head != PDF_MAGIC:
        raise InvalidInputError(
            f"file does not begin with the PDF magic bytes: {path} (got {head!r})"
        )
    return size


def _extract_with_pdftotext(pdf_path: Path, page_count: int) -> list[str] | None:
    """Preferred extractor. Returns None if pdftotext is unavailable.

    pdftotext -layout preserves column and table structure, which matters
    materially for a terms table like the Neo deck's page 37 where label/value
    pairs are spatially adjacent. Without -layout they interleave into
    unreadable order.
    """
    if not shutil.which("pdftotext"):
        return None
    pages: list[str] = []
    for n in range(1, page_count + 1):
        proc = subprocess.run(
            ["pdftotext", "-layout", "-f", str(n), "-l", str(n), str(pdf_path), "-"],
            capture_output=True,
            timeout=120,
        )
        if proc.returncode != 0:
            return None
        pages.append(proc.stdout.decode("utf-8", errors="replace"))
    return pages


def _extract_with_pypdf(pdf_path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise InvalidInputError(
            "neither pdftotext nor pypdf is available; cannot extract page text"
        ) from exc
    reader = PdfReader(str(pdf_path))
    return [(p.extract_text() or "") for p in reader.pages]


def page_count_of(pdf_path: Path) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(pdf_path)).pages)
    except Exception:
        pass
    if shutil.which("pdfinfo"):
        proc = subprocess.run(
            ["pdfinfo", str(pdf_path)], capture_output=True, timeout=60
        )
        if proc.returncode == 0:
            for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
                if line.lower().startswith("pages:"):
                    return int(line.split(":", 1)[1].strip())
    raise InvalidInputError(f"could not determine page count for {pdf_path}")


def extract_pages(pdf_path: Path, pages_dir: Path) -> list[str]:
    """Extract per-page text to <out>/00-pages/page-NNN.txt and return the texts.

    Writes even empty pages. A page that yields no text is information — it
    usually means an image-only slide — and omitting the file would make the
    page numbering of the directory listing disagree with the PDF.
    """
    pdf_path = Path(pdf_path)
    count = page_count_of(pdf_path)
    if count < 1:
        raise InvalidInputError(f"PDF reports {count} pages: {pdf_path}")

    pages = _extract_with_pdftotext(pdf_path, count)
    if pages is None:
        pages = _extract_with_pypdf(pdf_path)

    if len(pages) != count:
        raise InvalidInputError(
            f"page extraction produced {len(pages)} pages but PDF reports {count}"
        )

    pages_dir = Path(pages_dir)
    pages_dir.mkdir(parents=True, exist_ok=True)
    for i, text in enumerate(pages, start=1):
        atomic_write_text(pages_dir / f"page-{i:03d}.txt", text)

    if sum(len(p.strip()) for p in pages) == 0:
        raise InvalidInputError(
            f"PDF yielded no extractable text on any of {count} pages: {pdf_path}. "
            "This engine requires a text layer; scanned documents need OCR first."
        )
    return pages


def load_pages(pages_dir: Path) -> list[str]:
    """Re-read previously extracted pages, for --resume and single-stage runs."""
    pages_dir = Path(pages_dir)
    files = sorted(pages_dir.glob("page-*.txt"))
    if not files:
        raise InvalidInputError(f"no extracted page text found in {pages_dir}")
    return [f.read_text(encoding="utf-8") for f in files]


def render_pages_for_prompt(
    pages: list[str], first: int = 1, last: int | None = None
) -> str:
    """Render page text with explicit page markers for the model prompt.

    The markers are load-bearing, not decoration. The model is asked to cite page
    numbers, and this is the only signal it has for which page it is reading.
    Format is deliberately unambiguous and unlikely to occur in deck text.
    """
    last = last or len(pages)
    chunks = []
    for i in range(first, min(last, len(pages)) + 1):
        text = pages[i - 1].strip()
        chunks.append(
            f"<<<PAGE {i}>>>\n{text if text else '[no extractable text on this page]'}"
        )
    return "\n\n".join(chunks)
