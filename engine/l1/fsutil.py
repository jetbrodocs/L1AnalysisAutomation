"""Filesystem primitives that treat the filesystem as hostile (PRD 06 §6.6).

Three concrete hazards this module exists to defend against:

1. macOS APFS is case-insensitive. `Report.pdf` and `report.pdf` are one file,
   and `os.rename` overwrites the loser without raising. Therefore nothing here
   trusts a supplied filename as an identity — content hash is the identity.
2. A partially-written artifact is indistinguishable from a complete one once
   the process dies. Therefore every write is temp-then-rename, and the temp
   file is created in the *destination directory* so the rename is same-device
   and atomic. `/tmp` is a different filesystem; renaming across it is a copy
   and loses atomicity.
3. Sync clients (Dropbox/iCloud/Drive) write conflicted copies as new files and
   can leave dataless placeholders where stat() succeeds but read() blocks.
   Therefore we warn when the output directory is inside a known sync tree.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

# Substrings that indicate a sync-client-watched tree. Matched case-insensitively
# against the resolved absolute path.
SYNC_MARKERS = (
    "/dropbox/",
    "/library/mobile documents/",  # iCloud Drive
    "/icloud drive/",
    "/google drive/",
    "/googledrive/",
    "/onedrive/",
    "/box sync/",
    "/pcloud/",
    "/sync.com/",
    "/documentspaces/",  # Claude Document Spaces — also a synced tree
)


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Content hash of a file, streamed so a 500MB PPM does not land in RAM."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def detect_sync_path(path: Path) -> str | None:
    """Return the sync marker matched, or None. Advisory only — we warn, never block.

    Blocking would be wrong: a user may legitimately want output in a synced
    folder and accept the risk. Silence would also be wrong, because the failure
    mode (a dataless placeholder that stat()s fine and then hangs on read) is
    extremely hard to diagnose from the symptom.
    """
    probe = str(path.resolve()).lower()
    if not probe.endswith("/"):
        probe += "/"
    for marker in SYNC_MARKERS:
        if marker in probe:
            return marker.strip("/")
    return None


def atomic_write_bytes(dest: Path, data: bytes) -> None:
    """Write bytes to dest atomically via temp-then-rename in the same directory.

    fsync before rename: without it, a crash can leave a renamed-but-empty file,
    which is the exact 'looks complete, is not' failure the invariant forbids.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(dest.parent), prefix=f".{dest.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, dest)  # atomic within one filesystem
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def atomic_write_text(dest: Path, text: str) -> None:
    atomic_write_bytes(dest, text.encode("utf-8"))


def atomic_write_json(dest: Path, obj, *, indent: int = 2) -> None:
    """Serialise fully before opening the destination.

    Deliberate ordering: if the object is not serialisable we raise before any
    file exists, rather than leaving a truncated artifact behind.
    """
    payload = json.dumps(obj, indent=indent, ensure_ascii=False, sort_keys=False)
    atomic_write_text(dest, payload + "\n")


def append_jsonl(dest: Path, obj) -> None:
    """Append one JSON object as a line.

    Not atomic by design — status.jsonl and errors.jsonl are append-only streams
    that a worker tails live. Small appends under O_APPEND are effectively atomic
    for line-sized writes on local filesystems, and a torn final line on crash is
    acceptable for a progress stream in a way it is not for an artifact.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, sort_keys=False)
    with open(dest, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def copy_file_atomic(src: Path, dest: Path, chunk_size: int = 1 << 20) -> None:
    """Copy src to dest atomically, streaming.

    Used to place the content-addressed 00-source.pdf. The source path is never
    a destination path (PRD §6.6): we always write into the run directory under
    a name the engine chose, never the name the user supplied.
    """
    src, dest = Path(src), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(dest.parent), prefix=f".{dest.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as out, open(src, "rb") as inp:
            while chunk := inp.read(chunk_size):
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp_path, dest)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
