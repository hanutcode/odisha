"""Generic loaders for district tables published as CSV/XLSX
(NCRB Crime in India, UDISE+, Odisha WCD, detection-capacity templates).

Column names differ year to year, so columns are found by regex rather than
by exact name. Add patterns here when a new file layout turns up.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

STATE_COL = r"^(state|state[\s/_-]*ut|state_name|states?/uts?)$"
DISTRICT_COL = r"^(district|district[\s_]*name|districts?)$"
YEAR_COL = r"^(year|academic[\s_]*year)$"


def read_any(path: Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path, encoding_errors="replace")


def find_col(df: pd.DataFrame, pattern: str, required: bool = True) -> str | None:
    rx = re.compile(pattern, re.I)
    norm = {c: re.sub(r"\s+", " ", str(c)).strip() for c in df.columns}
    hits = [c for c, n in norm.items() if rx.search(n)]
    if not hits:
        if required:
            raise KeyError(f"No column matches /{pattern}/. Columns: {list(df.columns)}")
        return None
    return hits[0]


def _year_from(value, fallback: int | None) -> int | None:
    m = re.search(r"(20\d{2})", str(value))
    return int(m.group(1)) if m else fallback


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")


def _drop_totals(df: pd.DataFrame, dcol: str) -> pd.DataFrame:
    bad = df[dcol].astype(str).str.contains(r"^\s*(?:total|grand total|all)\b", case=False, regex=True)
    return df[~bad & df[dcol].notna()]


# --------------------------------------------------------------------- NCRB
PCMA_COL = r"(prohibition\s+of\s+child\s+marriage|child\s+marriage\s+restraint|pcma|\bcmra\b)"


def load_ncrb(path: Path, year: int | None = None) -> pd.DataFrame:
    """District-wise SLL table -> cases registered under the PCM Act."""
    df = read_any(path)
    scol, dcol = find_col(df, STATE_COL), find_col(df, DISTRICT_COL)
    ycol = find_col(df, YEAR_COL, required=False)
    vcol = find_col(df, PCMA_COL)
    df = _drop_totals(df, dcol)
    out = pd.DataFrame({
        "state": df[scol].astype(str).str.strip(),
        "district": df[dcol].astype(str).str.strip(),
        "year": df[ycol].map(lambda v: _year_from(v, year)) if ycol else year,
        "variable": "ncrb_pcma_cases",
        "value": _num(df[vcol]),
        "source": f"NCRB Crime in India ({Path(path).name})",
    })
    if out["year"].isna().any():
        raise ValueError(f"{path}: no year column; pass year=")
    # NCRB lists railway/CID/specialised units as districts; keep them flagged, not dropped.
    # The panel leaves flagged rows out of the district totals (they have no territory).
    out = out[~out["district"].str.startswith("#")]  # footnote rows ("# Clarifications are pending")
    out["non_territorial"] = out["district"].map(is_non_territorial)
    return out


NON_TERRITORIAL = re.compile(
    r"\b(?:grp|srp|rpo|hrpc|railways?|rly|crime|cid|c ?b|stf|special task force|cyber|eow|"
    r"economic offences?|anti terrorist|narcotics?|sog|scrb|ssb|intelligence|vigilance|spl|special|"
    r"metro|igi airport|bieo|sou|nri wing|bureau of investigation|irrigation|other units|spuwac|cice)\b",
    re.I)


def is_non_territorial(name: str) -> bool:
    """Police units with no district territory (railway, CID, cyber, STF, ...).

    Dots and spaces are removed between initials first, so "G. R. P." reads as "grp".
    "Jaipur Metro" is a city police district, so it is kept.
    """
    s = re.sub(r"\b([A-Za-z])\.\s*(?=[A-Za-z]\b)", r"\1", str(name))   # G. R. P. -> GRP.
    s = s.replace(".", " ").replace(",", " ")
    if re.search(r"jaipur metro", s, re.I):
        return False
    return bool(NON_TERRITORIAL.search(s))


# -------------------------------------------------------------------- UDISE+
def load_udise(path: Path, year: int | None = None) -> pd.DataFrame:
    """UDISE+ district enrolment -> girls enrolled in Grades 8, 9, 10."""
    df = read_any(path)
    scol, dcol = find_col(df, STATE_COL), find_col(df, DISTRICT_COL)
    ycol = find_col(df, YEAR_COL, required=False)
    df = _drop_totals(df, dcol)
    rows = []
    for g in (8, 9, 10):
        c = find_col(df, rf"(class|grade|c)[\s_]*{g}\b.*(girl|female|_g$|\bg\b)|"
                         rf"(girl|female).*(class|grade|c)[\s_]*{g}\b")
        rows.append(pd.DataFrame({
            "state": df[scol].astype(str).str.strip(),
            "district": df[dcol].astype(str).str.strip(),
            "year": df[ycol].map(lambda v: _year_from(v, year)) if ycol else year,
            "variable": f"udise_girls_g{g}",
            "value": _num(df[c]),
        }))
    out = pd.concat(rows, ignore_index=True)
    out["source"] = f"UDISE+ ({Path(path).name})"
    return out


def udise_transition(long: pd.DataFrame) -> pd.DataFrame:
    """Girls' transition ratios: Grade 9 in year t / Grade 8 in year t-1, and 10/9.

    The dropout signal in the model is 1 - transition. Ratios above 1.2 are
    usually migration or data errors and are set to NaN with a flag.
    """
    w = long.pivot_table(index=["state", "district", "year"], columns="variable",
                         values="value", aggfunc="sum").reset_index()
    w = w.sort_values(["state", "district", "year"])
    out = []
    for (lo, hi) in ((8, 9), (9, 10)):
        prev = w[["state", "district", "year", f"udise_girls_g{lo}"]].copy()
        prev["year"] += 1
        m = w[["state", "district", "year", f"udise_girls_g{hi}"]].merge(
            prev, on=["state", "district", "year"], how="inner")
        ratio = m[f"udise_girls_g{hi}"] / m[f"udise_girls_g{lo}"].replace(0, np.nan)
        out.append(pd.DataFrame({
            "state": m["state"], "district": m["district"], "year": m["year"],
            "variable": f"udise_transition_g{lo}_g{hi}",
            "value": ratio.where(ratio <= 1.2),
            "implausible": ratio > 1.2,
            "source": "UDISE+ derived",
        }))
    return pd.concat(out, ignore_index=True)


# ------------------------------------------------- manual templates (CSV)
def load_long_template(path: Path, source: str) -> pd.DataFrame:
    """Templates in data/manual/ are already long: state,district,year,variable,value,source_ref."""
    df = pd.read_csv(path, comment="#")
    need = {"state", "district", "year", "variable", "value"}
    missing = need - set(df.columns)
    if missing:
        raise KeyError(f"{path} is missing columns {missing}")
    df["value"] = _num(df["value"])
    df["source"] = source + (" — " + df["source_ref"].astype(str) if "source_ref" in df else "")
    return df.dropna(subset=["value"])
