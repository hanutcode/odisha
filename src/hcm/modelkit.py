"""Engineer-provided plumbing for Hanut's model: data in, outputs out.

Nothing here estimates anything. It (1) assembles the Odisha training data
from the panel, and (2) writes and checks the two contract files. The model
itself lives in model/ and is written by Hanut (docs/INTEGRITY.md, rule 1).

    from hcm import modelkit
    d = modelkit.load_training_data()        # one row per district x year, years <= cutoff
    ...  your model ...
    modelkit.write_outputs(estimates_df, reasons_df)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd

from . import contract, paths

STATE = "Odisha"
ODISHA_CODES = range(370, 400)

# Columns the panel may contain, grouped by the part of the model they feed.
OCCURRENCE_VARS = ["cm_20_24_before18", "teen_pregnancy_15_19", "men_25_29_before21",
                   "udise_transition_g8_g9", "udise_transition_g9_g10",
                   "udise_girls_g8", "udise_girls_g9", "udise_girls_g10", "rain_shock_z"]
DETECTION_VARS = ["police_per_100k", "childline_1098_present", "cmpo_count", "anganwadi_per_1k"]
RECORDED_VARS = ["ncrb_pcma_cases", "odisha_marriages_prevented", "odisha_cmpo_cases"]


def load_training_data(state: str = STATE, through: int | None = None) -> pd.DataFrame:
    """District x year table for one state, restricted to the training window.

    Columns: census2011_code, district, year, then whichever OCCURRENCE / DETECTION /
    RECORDED variables exist in the panel (missing ones are simply absent).
    NFHS-6 is never here: it is sealed and is not in the panel.
    """
    w = pd.read_parquet(paths.PROCESSED / "panel_wide.parquet")
    through = through if through is not None else paths.training_cutoff_year()
    w = w[(w["state"].str.lower() == state.lower()) & (w["year"] <= through)].copy()
    w["census2011_code"] = w["unit_id"].str[1:].astype(int)
    keep = [c for c in OCCURRENCE_VARS + DETECTION_VARS + RECORDED_VARS if c in w.columns]
    out = w[["census2011_code", "unit_name", "year"] + keep].rename(columns={"unit_name": "district"})
    return out.sort_values(["census2011_code", "year"]).reset_index(drop=True)


def describe(d: pd.DataFrame) -> pd.DataFrame:
    """How many districts have a value, per variable and year. Use it to see the gaps."""
    vals = [c for c in d.columns if c not in ("census2011_code", "district", "year")]
    return d.groupby("year")[vals].apply(lambda g: g.notna().sum()).T


def recorded_cases(d: pd.DataFrame, years=range(2016, 2022)) -> pd.Series:
    """Recorded cases per district summed over `years`, all channels present in the data."""
    cols = [c for c in RECORDED_VARS if c in d.columns]
    sub = d[d["year"].isin(list(years))]
    return sub.groupby("census2011_code")[cols].sum(min_count=1).sum(axis=1, min_count=1)


def run_id() -> str:
    """Short git commit hash of the repo, for model_run_id. 'uncommitted' if none."""
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=paths.ROOT,
                           capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "status", "--porcelain", "model"], cwd=paths.ROOT,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip() + ("-dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        pass
    return "uncommitted"


def write_outputs(estimates: pd.DataFrame, reasons: pd.DataFrame, out_dir: Path | None = None,
                  model_run_id: str | None = None) -> Path:
    """Check both tables against the contract, then write them. Nothing is written if a check fails.

    `estimates` needs: census2011_code, est_rate, est_lo, est_hi, detection_prob, flag, reason_code.
    district, recorded_cases and model_run_id are filled in if absent.
    """
    est = estimates.copy()
    if "model_run_id" not in est:
        est["model_run_id"] = model_run_id or run_id()
    if "district" not in est or "recorded_cases" not in est:
        d = load_training_data()
        names = d.drop_duplicates("census2011_code").set_index("census2011_code")["district"]
        if "district" not in est:
            est["district"] = est["census2011_code"].map(names)
        if "recorded_cases" not in est:
            est["recorded_cases"] = est["census2011_code"].map(recorded_cases(d))
    est["reason_code"] = est["reason_code"].fillna("").astype(str)
    est = est[list(contract.ESTIMATE_COLS)]
    rc = reasons[contract.REASON_COLS].copy()
    contract.validate(est, rc)
    if str(est["model_run_id"].iat[0]).upper().startswith("MOCK"):
        raise contract.ContractError("model_run_id starts with MOCK; that prefix is reserved for mock data")
    out = Path(out_dir or paths.OUTPUTS)
    out.mkdir(parents=True, exist_ok=True)
    est.to_csv(out / "district_estimates.csv", index=False)
    rc.to_csv(out / "reason_codes.csv", index=False)
    return out
