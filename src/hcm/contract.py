"""The hand-off contract between Hanut's model and the demo tool.

Hanut's model writes two files; the demo tool and the figure scripts read
only these, so the model can change freely as long as the contract holds.

outputs/district_estimates.csv  — one row per district (Odisha: 30 rows)
  census2011_code   int    district code (Odisha: 370-399)
  district          str    display name (English)
  est_rate          float  estimated true share of women 20-24 married before 18 (0-1)
  est_lo, est_hi    float  credible interval (default 90%)
  recorded_cases    float  recorded cases, all channels, same period
  detection_prob    float  estimated probability a child marriage is recorded (0-1)
  flag              bool   flagged for welfare outreach
  reason_code       str    key into reason_codes.csv (blank if not flagged)
  model_run_id      str    commit hash of the model; starts with MOCK for mock data

outputs/reason_codes.csv — one row per reason
  reason_code, text_en, text_hi, text_or, odia_checked (bool)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import paths

ESTIMATE_COLS = {
    "census2011_code": "int", "district": "str", "est_rate": "float", "est_lo": "float",
    "est_hi": "float", "recorded_cases": "float", "detection_prob": "float",
    "flag": "bool", "reason_code": "str", "model_run_id": "str",
}
REASON_COLS = ["reason_code", "text_en", "text_hi", "text_or", "odia_checked"]


class ContractError(ValueError):
    pass


def _bool(s: pd.Series) -> pd.Series:
    return s.map(lambda v: str(v).strip().lower() in ("true", "1", "yes"))


def load(estimates: Path | None = None, reasons: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    est = pd.read_csv(estimates or paths.OUTPUTS / "district_estimates.csv")
    rc = pd.read_csv(reasons or paths.OUTPUTS / "reason_codes.csv").fillna("")
    validate(est, rc)
    est["flag"] = _bool(est["flag"])
    est["reason_code"] = est["reason_code"].fillna("").astype(str)
    rc["odia_checked"] = _bool(rc["odia_checked"])
    return est, rc


def validate(est: pd.DataFrame, rc: pd.DataFrame) -> None:
    errs = []
    miss = set(ESTIMATE_COLS) - set(est.columns)
    if miss:
        errs.append(f"district_estimates.csv missing columns: {sorted(miss)}")
    miss = set(REASON_COLS) - set(rc.columns)
    if miss:
        errs.append(f"reason_codes.csv missing columns: {sorted(miss)}")
    if errs:
        raise ContractError("; ".join(errs))
    for c in ("est_rate", "est_lo", "est_hi", "detection_prob"):
        v = pd.to_numeric(est[c], errors="coerce")
        if v.isna().any() or ((v < 0) | (v > 1)).any():
            errs.append(f"{c} must be a proportion in [0, 1]")
    if (pd.to_numeric(est["est_lo"]) > pd.to_numeric(est["est_hi"])).any():
        errs.append("est_lo > est_hi in some rows")
    if est["census2011_code"].duplicated().any():
        errs.append("duplicate census2011_code rows")
    flagged = _bool(est["flag"])
    codes = set(rc["reason_code"].astype(str))
    bad = set(est.loc[flagged, "reason_code"].fillna("").astype(str)) - codes
    if bad:
        errs.append(f"flagged rows use reason codes not in reason_codes.csv: {sorted(bad)}")
    if errs:
        raise ContractError("; ".join(errs))


def is_mock(est: pd.DataFrame) -> bool:
    return est["model_run_id"].astype(str).str.upper().str.startswith("MOCK").any()
