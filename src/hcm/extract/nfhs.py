"""Parse NFHS district fact sheets (PDF) for the child-marriage indicator.

Indicator: "Women age 20-24 years married before age 18 years (%)".
District sheets print the current round first and the previous round second,
e.g. "23. Women age 20-24 years married before age 18 years (%) 20.1 27.4".

Conventions in the sheets:
  (12.3)  based on 25-49 unweighted cases  -> value kept, small_n=True
  *       fewer than 25 cases, suppressed  -> value NaN, suppressed=True
  na      not available                    -> value NaN
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

INDICATOR_PATTERNS = {
    "cm_20_24_before18": re.compile(
        r"women\s+age\s+20\s*[-–]\s*24\s+years\s+married\s+before\s+age\s+18", re.I),
    "men_25_29_before21": re.compile(
        r"men\s+age\s+25\s*[-–]\s*29\s+years\s+married\s+before\s+age\s+21", re.I),
    "teen_pregnancy_15_19": re.compile(
        r"women\s+age\s+15\s*[-–]\s*19\s+years\s+who\s+were\s+already\s+mothers\s+or\s+pregnant", re.I),
}

_VALUE = re.compile(r"(\(\s*\d+(?:\.\d+)?\s*\)|\d+(?:\.\d+)?|\*|na)\s*", re.I)
_HEADER = re.compile(r"District\s+Fact\s+Sheet\s*[:\-]?\s*(.+)", re.I)


def _parse_value(tok: str) -> tuple[float | None, bool, bool]:
    tok = tok.strip()
    if tok == "*":
        return None, False, True
    if tok.lower() == "na":
        return None, False, False
    if tok.startswith("("):
        return float(tok.strip("() ")), True, False
    return float(tok), False, False


def _trailing_values(line: str, after: int) -> list[str]:
    """Value tokens after the indicator label (skips the '(%)' unit marker)."""
    tail = line[after:]
    tail = re.sub(r"\(\s*%\s*\)", " ", tail)
    tail = re.sub(r"^[^\d(*n]*", "", tail)  # drop leftover label words
    toks = []
    pos = 0
    while pos < len(tail):
        m = _VALUE.match(tail, pos)
        if not m:
            break
        toks.append(m.group(1))
        pos = m.end()
    return toks


def parse_text(text: str, round_: int, district: str | None = None,
               state: str | None = None) -> list[dict]:
    """Extract indicator rows from the text of one district fact sheet."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if district is None:
        m = re.search(r"trends for ([^.\n]+)\.", text)
        if m:
            district = m.group(1).strip()
    if district is None or state is None:
        m = re.search(r"^\s*([^,\n]+),\s*([^\n-]+?)\s*-\s*Key Indicators", text, re.M)
        if m:
            district = district or m.group(1).strip()
            state = state or m.group(2).strip()
    if district is None or state is None:
        for i, ln in enumerate(lines[:15]):
            m = _HEADER.search(ln)
            if m:
                rest = m.group(1).strip() or (lines[i + 1] if i + 1 < len(lines) else "")
                parts = [p.strip() for p in re.split(r",|\s{2,}|\s[-\u2013]\s", rest) if p.strip()]
                if parts:
                    district = district or parts[0]
                    if len(parts) > 1:
                        state = state or parts[-1]
                break

    rows = []
    for i, ln in enumerate(lines):
        for var, pat in INDICATOR_PATTERNS.items():
            m = pat.search(ln)
            if not m:
                continue
            toks = _trailing_values(ln, m.end())
            if not toks and i + 1 < len(lines):  # values wrapped to next line
                toks = _trailing_values(lines[i + 1], 0)
            if round_ <= 4:
                # NFHS-4 district sheets print [Urban, Rural,] Total for NFHS-4 only:
                # the district value is the last number.
                picked = [(toks[-1], round_)] if toks else []
            else:
                # NFHS-5 and later: current round first, previous round second
                picked = [(tok, round_ - k) for k, tok in enumerate(toks[:2])]
            for tok, rnd in picked:
                value, small_n, suppressed = _parse_value(tok)
                rows.append({
                    "state": state, "district": district, "variable": var,
                    "nfhs_round": rnd, "value": value,
                    "small_n": small_n, "suppressed": suppressed,
                    "reported_in_round": round_,
                })
    return rows


def parse_pdf(pdf_path: Path, round_: int, state: str | None = None) -> list[dict]:
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages[:4])
    rows = parse_text(text, round_, state=state)
    m = re.match(r"NFHS-\d+_DistFact_([^_]+)_([^_]+)__", Path(pdf_path).name)
    district = m.group(2).replace("-", " ") if m else Path(pdf_path).stem.replace("_", " ")
    if m and state is None:
        state = m.group(1).replace("-", " ")
    for r in rows:
        r["district"] = r["district"] or district
        r["file"] = Path(pdf_path).name
    if not rows:
        rows.append({"state": state, "district": district, "variable": None,
                     "nfhs_round": round_, "value": None, "file": Path(pdf_path).name,
                     "parse_error": "indicator not found"})
    return rows


def extract_round(folder: Path, round_: int, state: str | None = None) -> pd.DataFrame:
    rows = []
    for pdf in sorted(Path(folder).rglob("*.pdf")):
        rows.extend(parse_pdf(pdf, round_, state=state))
    df = pd.DataFrame(rows)
    if df.empty or "reported_in_round" not in df:  # no district sheets (e.g. only a state fact sheet)
        return df.iloc[0:0]
    # The same round appears twice (as 'current' in its own sheet and as
    # 'previous' in the next round's sheet). Prefer the value from its own sheet.
    df = df.sort_values("reported_in_round").drop_duplicates(
        ["state", "district", "variable", "nfhs_round"], keep="first")
    df["source"] = f"NFHS-{round_} district fact sheet"
    return df.reset_index(drop=True)


# ------------------------------------------------------------- CSV fact sheets
def load_csv(path: Path) -> pd.DataFrame:
    """Fact sheets already converted to CSV (e.g. github.com/pratapvardhan/NFHS-5, CC BY 4.0).

    Expected columns: State, District, Indicator, NFHS-5, NFHS-4 (and optionally NFHS-6).
    Columns for sealed rounds are dropped here, so they can never reach the panel.
    """
    from .. import paths

    df = pd.read_csv(path)
    need = {"State", "District", "Indicator"}
    if need - set(df.columns):
        raise KeyError(f"{path}: needs columns {sorted(need)}; has {list(df.columns)}")
    sealed = paths.sealed_rounds()
    rows = []
    for var, pat in INDICATOR_PATTERNS.items():
        sub = df[df["Indicator"].astype(str).str.contains(pat)]
        for col in sub.columns:
            m = re.fullmatch(r"NFHS-(\d)", str(col))
            if not m or int(m.group(1)) in sealed:
                continue
            rnd = int(m.group(1))
            for r in sub.itertuples(index=False):
                raw = str(r[sub.columns.get_loc(col)]).strip()
                if raw in ("", "nan", "None"):
                    continue
                try:
                    value, small_n, suppressed = _parse_value(raw)
                except ValueError:
                    continue
                rows.append({"state": r[sub.columns.get_loc("State")], "district": r[sub.columns.get_loc("District")],
                             "variable": var, "nfhs_round": rnd, "value": value, "small_n": small_n,
                             "suppressed": suppressed, "suspect_zero": value == 0.0,
                             "file": Path(path).name})
    out = pd.DataFrame(rows)
    if len(out):
        out["source"] = f"NFHS fact sheet CSV ({Path(path).name})"
    return out
