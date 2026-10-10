import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "demo"))
sys.path.insert(0, str(REPO / "scripts"))

from hcm import paths  # noqa: E402


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A throwaway copy of the project layout, with every path pointed at it."""
    root = tmp_path / "proj"
    for sub in ("config", "data/manual", "demo"):
        shutil.copytree(REPO / sub, root / sub)
    (root / "data/geo").mkdir(parents=True)
    shutil.copy(REPO / "data/geo/odisha_districts_2011.geojson", root / "data/geo")
    mapping = {
        "ROOT": root, "CONFIG": root / "config", "DATA": root / "data", "RAW": root / "data/raw",
        "INTERIM": root / "data/interim", "PROCESSED": root / "data/processed",
        "MANUAL": root / "data/manual", "GEO": root / "data/geo", "SEALED": root / "data/sealed",
        "UNSEALED": root / "data/unsealed", "OUTPUTS": root / "outputs", "DOCS": root / "docs",
        "SEAL_LOG": root / "docs/seal_log.jsonl",
    }
    for k, v in mapping.items():
        monkeypatch.setattr(paths, k, v)
    paths.sources.cache_clear()
    paths.ensure_dirs()
    yield root
    paths.sources.cache_clear()
