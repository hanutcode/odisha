"""Project paths and config loading."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("HCM_ROOT", Path(__file__).resolve().parents[2]))

CONFIG = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
MANUAL = DATA / "manual"
GEO = DATA / "geo"
SEALED = DATA / "sealed"
UNSEALED = DATA / "unsealed"
OUTPUTS = ROOT / "outputs"
DOCS = ROOT / "docs"
SEAL_LOG = DOCS / "seal_log.jsonl"


@lru_cache
def sources() -> dict:
    with open(CONFIG / "sources.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def training_cutoff_year() -> int:
    return int(sources()["training_cutoff_year"])


def sealed_rounds() -> set[int]:
    """NFHS rounds that stay sealed until the model freeze (NFHS-6; NFHS-5 in the no-go fallback)."""
    return {int(r) for r, i in sources()["nfhs_rounds"].items() if i.get("sealed")}


def ensure_dirs() -> None:
    for p in (RAW, INTERIM, PROCESSED, MANUAL, GEO, SEALED, OUTPUTS, DOCS):
        p.mkdir(parents=True, exist_ok=True)
