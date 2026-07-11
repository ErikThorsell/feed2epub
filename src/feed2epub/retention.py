"""Prune old feed EPUBs from the output directory.

Safety is the whole point of this module: it must delete *only* files that match the exact name shape this project
emits -- ``<slug>-YYYY-MM-DD.epub`` with ``slug`` drawn from :func:`feed2epub.epub.slugify`'s ``[a-z0-9-]`` charset.
Anything else in the directory (the real library, hand-dropped books, ``.tmp`` fragments) is invisible to the pruner
by construction. The cutoff date is parsed from the filename, never from ``stat``: mtime is unreliable -- a copy,
backup, or the OPDS server's own folder scan can bump it, which would keep stale EPUBs alive indefinitely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

# Slug is greedy but backtracks so the trailing YYYY-MM-DD always binds to the date group. Requires a non-empty slug
# and the separating '-', so a bare ``2026-07-11.epub`` (which we never emit) cannot match.
_EPUB_RE = re.compile(r"^[a-z0-9-]+-(\d{4}-\d{2}-\d{2})\.epub$")


@dataclass(frozen=True)
class PruneResult:
    """Outcome of a prune pass. ``deleted``/``kept`` are filenames; ``errors`` pairs a filename with its error text."""

    deleted: list[str]
    kept: list[str]
    errors: list[tuple[str, str]]


def _embedded_date(name: str) -> date | None:
    """Return the date embedded in ``name`` if it matches our exact filename shape and is a real calendar date."""
    match = _EPUB_RE.match(name)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        # Shape matched but the date is impossible (e.g. month 13): not something we emitted -- leave it alone.
        return None


def prune(output_dir: Path, retention_days: int, *, today: date) -> PruneResult:
    """Delete feed EPUBs in ``output_dir`` whose embedded date is more than ``retention_days`` old.

    A file dated exactly ``retention_days`` ago is kept; only strictly older ones are removed. Non-matching files are
    ignored entirely. Per-file deletion errors are collected rather than raised, so one stuck file cannot abort the run.
    """
    cutoff = today - timedelta(days=retention_days)
    deleted: list[str] = []
    kept: list[str] = []
    errors: list[tuple[str, str]] = []

    for path in sorted(output_dir.glob("*.epub")):
        if not path.is_file():
            continue
        embedded = _embedded_date(path.name)
        if embedded is None:
            continue
        if embedded >= cutoff:
            kept.append(path.name)
            continue
        try:
            path.unlink()
        except OSError as exc:
            errors.append((path.name, str(exc)))
            continue
        deleted.append(path.name)

    return PruneResult(deleted=deleted, kept=kept, errors=errors)
