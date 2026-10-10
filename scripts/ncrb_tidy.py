"""Turn NCRB 'District-wise Crime against Children' workbooks into tidy CSVs.

    python3 scripts/ncrb_tidy.py   # reads data/raw/ncrb_all/**/ncrb_children_YYYY.xlsx

NCRB sheets list states as section rows ("State: Odisha") followed by their
districts. Output: data/raw/ncrb/ncrb_pcma_YYYY.csv with State, District, Year
and the Prohibition of Child Marriage Act column (cases registered).
"""
import glob
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/raw/ncrb_all"
OUT = ROOT / "data/raw/ncrb"


# Known errors in the NCRB workbooks: (year, header as printed, nth time it appears) -> real state.
# 2017: the Chhattisgarh section is headed "State : Bihar" a second time (its districts are
# Balod, Balodbazar, ... Surajpur, and it sits where Chhattisgarh belongs alphabetically).
ERRATA = {(2017, "Bihar", 2): "Chhattisgarh"}


def tidy(path: Path) -> pd.DataFrame:
    year = int(re.search(r"(20\d{2})", path.name).group(1))
    df = pd.read_excel(path, header=1, dtype=object)
    sl, dist = df.columns[0], df.columns[1]
    pc = next(c for c in df.columns if re.search(r"prohibition of child marriage", str(c), re.I))
    rows, state, seen = [], None, {}
    for _, r in df.iterrows():
        a, d = str(r[sl]).strip(), r[dist]
        m = re.match(r"(?:State|UT)\s*:\s*(.+)", a, re.I)
        if m:
            state = m.group(1).strip()
            seen[state] = seen.get(state, 0) + 1
            state = ERRATA.get((year, state, seen[state]), state)
            continue
        if state is None or pd.isna(d):
            continue
        d = str(d).strip()
        if not d or re.match(r"(total|grand total)", d, re.I) or d.isdigit():
            continue
        v = pd.to_numeric(str(r[pc]).replace(",", ""), errors="coerce")
        rows.append({"State": state, "District": d, "Year": year,
                     "Prohibition of Child Marriage Act": v})
    return pd.DataFrame(rows)


def main():
    files = sorted(glob.glob(str(SRC / "**/ncrb_children_*.xlsx"), recursive=True))
    if not files:
        sys.exit(f"No ncrb_children_*.xlsx under {SRC}")
    OUT.mkdir(parents=True, exist_ok=True)
    for f in files:
        t = tidy(Path(f))
        y = int(t["Year"].iloc[0])
        t.to_csv(OUT / f"ncrb_pcma_{y}.csv", index=False)
        od = t[t["State"].str.lower().isin(["odisha", "orissa"])]
        print(f"{y}: {len(t)} rows, {t['State'].nunique()} states; Odisha {len(od)} units, "
              f"PCMA cases {int(od['Prohibition of Child Marriage Act'].sum())}")


if __name__ == "__main__":
    main()
