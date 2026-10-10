"""NFHS-6 seal record (history only).

The seal / freeze / witness / unseal workflow was removed on 10 Oct 2026 at the
project lead's request. What remains:

  hcm lift-seal --key ~/nfhs6.key   one-off: decrypt the existing sealed bundle into
                                    data/raw/nfhs/round6/ and log a "seal_lifted" event
  hcm seal-status                   print the historical record in docs/seal_log.jsonl

docs/seal_log.jsonl is kept unchanged as the historical record; new events are appended.
"""

from __future__ import annotations

import getpass
import hashlib
import io
import json
import os
import platform
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet

from . import paths

BUNDLE = "nfhs6.tar.enc"


class SealError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def log(event: str, actor: str | None = None, **fields) -> dict:
    entry = {"event": event, "utc": _now(), "by": actor or getpass.getuser(),
             "host": platform.node(), **fields}
    paths.SEAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(paths.SEAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_log() -> list[dict]:
    if not paths.SEAL_LOG.exists():
        return []
    return [json.loads(l) for l in paths.SEAL_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]



# ------------------------------------------------------------- lift seal
def lift_seal(key_path: Path, actor: str | None = None, reason: str = "") -> dict:
    """Decrypt the sealed NFHS-6 bundle into data/raw/nfhs/round6/ (no freeze needed).

    Checks the bundle against the hash in the seal log first, logs a "seal_lifted"
    event. The encrypted bundle is left in data/sealed/ as part of the record.
    """
    bundle = paths.SEALED / BUNDLE
    if not bundle.exists():
        raise SealError(f"No sealed bundle at {bundle}.")
    token = bundle.read_bytes()
    seals = [e for e in read_log() if e["event"] == "seal"]
    if seals and _sha(token) != seals[-1]["bundle_sha256"]:
        raise SealError("Sealed bundle hash does not match the seal log. Stop and investigate.")
    data = Fernet(Path(key_path).expanduser().read_bytes()).decrypt(token)
    dest = paths.RAW / "nfhs" / "round6"
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        names = tar.getnames()
        try:
            tar.extractall(dest, filter="data")
        except TypeError:  # Python without the tarfile filter backport
            tar.extractall(dest)
    files = [{"file": n, "sha256": _sha((dest / n).read_bytes())} for n in names]
    entry = log("seal_lifted", actor=actor, bundle_sha256=_sha(token), to=str(dest.relative_to(paths.ROOT)),
                files=files, note=reason or "Seal workflow removed at the project lead's request; "
                "NFHS-6 opened without a model freeze.")
    return entry


def status() -> str:
    ev = read_log()
    lines = [f"{e['utc']}  {e['event']:<11} {e.get('by','')}  "
             f"{e.get('commit', e.get('bundle_sha256', ''))[:12]}" for e in ev]
    state = ("seal lifted (workflow removed)" if any(e["event"] == "seal_lifted" for e in ev) else
             "SEALED" if (paths.SEALED / BUNDLE).exists() else "not sealed")
    return "\n".join([f"NFHS-6 status: {state}", *lines])
