"""Fetch the sources in config/sources.yaml that have a URL.

Every downloaded file gets a SHA-256 entry in data/raw/MANIFEST.csv so the
paper can state exactly which files were used.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import paths


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch(url: str, dest: Path, force: bool = False) -> str:
    if dest.exists() and not force:
        return "exists"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.replace(dest)
    return "downloaded"


def _record(dest: Path, url: str, status: str) -> None:
    manifest = paths.RAW / "MANIFEST.csv"
    new = not manifest.exists()
    with open(manifest, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["file", "url", "sha256", "status", "checked_utc"])
        w.writerow([
            str(dest.relative_to(paths.ROOT)), url, sha256(dest), status,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ])


def run(only: list[str] | None = None, force: bool = False) -> list[tuple[str, str, str]]:
    """Download all URL-backed sources. Returns (name, dest, status) rows."""
    results = []
    for name, spec in paths.sources()["downloads"].items():
        if only and name not in only:
            continue
        if spec.get("manual"):
            results.append((name, spec["dest"], "MANUAL - " + spec.get("note", "").strip()[:80]))
            continue
        jobs = []
        if "url" in spec:
            jobs.append((spec["url"], paths.ROOT / spec["dest"]))
        for year in spec.get("years", []):
            jobs.append((spec["url_template"].format(year=year),
                         paths.ROOT / spec["dest_template"].format(year=year)))
        for url, dest in jobs:
            try:
                status = _fetch(url, dest, force)
                _record(dest, url, status)
            except Exception as e:  # report and carry on; Day-1 audit needs the full list
                status = f"FAILED - {type(e).__name__}: {e}"[:160]
            results.append((name, str(dest.relative_to(paths.ROOT)), status))
    return results
