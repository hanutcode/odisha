"""District crosswalk: Census 2011 (640) -> NFHS-5 (~707) -> NFHS-6 / LGD (~715).

Approach
--------
1. Every LGD district carries its Census 2011 code if it existed in 2011.
   Districts created later are linked to their parent(s) in
   data/manual/district_splits.csv (child_lgd_code, parent_census2011_code, pop_share).
2. Census and LGD districts form a bipartite graph. Each connected component
   is a *harmonised unit*: a fixed piece of territory that exists in every
   year, whatever the boundaries were. Splits fold back into their parent,
   so every source maps to exactly one unit and nothing is double counted.
3. Sources that publish names, not codes (NFHS fact sheets, NCRB, UDISE+),
   are matched by name within state: exact -> alias -> fuzzy. Anything
   below the fuzzy threshold goes to a review queue for an engineer, and a
   random sample goes to Hanut for spot checks.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

from . import paths

# ---------------------------------------------------------------- names
_STATE_FIX = {
    "orissa": "odisha", "uttaranchal": "uttarakhand", "pondicherry": "puducherry",
    "nct of delhi": "delhi", "arunanchal pradesh": "arunachal pradesh",
    "andaman nicobar island": "andaman nicobar islands",
    "dadara nagar havelli": "dadra nagar haveli",
    # NCRB spellings
    "delhi ut": "delhi", "a n islands": "andaman nicobar islands", "d n haveli": "dadra nagar haveli",
    "d n haveli daman diu": "the dadra nagar haveli daman diu",
    "dadra nagar haveli daman diu": "the dadra nagar haveli daman diu",
}


def norm(name: str) -> str:
    """Lower-case, strip accents/punctuation and filler words for matching."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ")
    s = re.sub(r"\([^)]*\)", " ", s)  # "Saran (Chhapra)" -> "saran"
    s = re.sub(r"\b(district|dist|distt|zila|zilla)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_state(name: str) -> str:
    s = re.sub(r"\s+", " ", norm(name).replace(" and ", " ")).strip()
    return _STATE_FIX.get(s, s)


def load_aliases(path: Path | None = None) -> dict[tuple[str, str], str]:
    """Spelling variants -> one canonical key per (state, district).

    data/manual/district_aliases.csv has columns state, alias, canonical. Both
    the source names and the reference names are passed through this map, so
    it does not matter which spelling the reference file uses.
    """
    path = path or paths.MANUAL / "district_aliases.csv"
    if not Path(path).exists():
        return {}
    a = pd.read_csv(path, comment="#")
    return {(norm_state(r.state), norm(r.alias)): norm(r.canonical) for r in a.itertuples()}


def _canon(state_key: str, name: str, aliases: dict) -> str:
    d = norm(name)
    return aliases.get((state_key, d), d)


def _spelling_score(a: str, b: str, **_) -> float:
    """Similarity of spellings, ignoring spaces. Plain ratio, not partial matching,
    so a new district ("South Salmara Mancachar") is not matched to a shorter
    old one ("Cachar") just because it contains its name."""
    return fuzz.ratio(a.replace(" ", ""), b.replace(" ", ""))


def match_names(df: pd.DataFrame, reference: pd.DataFrame, key: str,
                aliases: dict | None = None, threshold: int = 90,
                overrides: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach `key` from `reference` (columns state, district, key) to df by name.

    Returns df with columns key, match_method, match_score, matched_name.
    """
    aliases = load_aliases() if aliases is None else aliases
    ref = reference.copy()
    ref["_s"] = ref["state"].map(norm_state)
    ref["_d"] = [_canon(st, d, aliases) for st, d in zip(ref["_s"], ref["district"])]
    by_state = {s: g for s, g in ref.groupby("_s")}
    ov = {}
    if overrides is not None and len(overrides):
        ov = {(norm_state(r.state), norm(r.district)): r[key] for _, r in overrides.iterrows()}

    pairs = df[["state", "district"]].drop_duplicates()
    rows = []
    for st, dist in pairs.itertuples(index=False):
        s = norm_state(st)
        d = _canon(s, dist, aliases)
        cand = by_state.get(s)
        res = {"state": st, "district": dist, key: None, "match_method": "unmatched",
               "match_score": 0.0, "matched_name": None}
        if (s, norm(dist)) in ov:
            res.update({key: ov[(s, norm(dist))], "match_method": "override", "match_score": 100.0})
        elif cand is not None:
            exact = cand[cand["_d"] == d].drop_duplicates(["_d", key])
            if len(exact) == 1:
                method = "exact" if norm(dist) == norm(exact["district"].iat[0]) else "alias"
                res.update({key: exact[key].iat[0], "match_method": method, "match_score": 100.0,
                            "matched_name": exact["district"].iat[0]})
            elif len(exact) > 1:
                res.update({"match_method": "ambiguous", "match_score": 100.0,
                            "matched_name": ";".join(exact["district"])})
            else:
                best = process.extractOne(d, cand["_d"].tolist(), scorer=_spelling_score)
                if best:
                    hit = cand.iloc[best[2]]
                    res.update({"match_score": float(best[1]), "matched_name": hit["district"]})
                    if best[1] >= threshold:
                        res.update({key: hit[key], "match_method": "fuzzy"})
        rows.append(res)
    m = pd.DataFrame(rows)
    return df.merge(m, on=["state", "district"], how="left")


# ----------------------------------------------------------- reference tables
def census2011_reference(geojson: Path | None = None) -> pd.DataFrame:
    """640/641 Census 2011 districts from the DataMeet boundary file."""
    import geopandas as gpd

    geojson = geojson or paths.GEO / "india_districts_2011.geojson"
    g = gpd.read_file(geojson)
    code = "censuscode" if "censuscode" in g else "dt_code"
    ref = pd.DataFrame({
        "state": g["ST_NM"] if "ST_NM" in g else g["st_nm"],
        "district": g["DISTRICT"] if "DISTRICT" in g else g["district"],
        "census2011_code": pd.to_numeric(g[code], errors="coerce").astype("Int64"),
    }).dropna(subset=["census2011_code"])
    return ref.drop_duplicates("census2011_code").reset_index(drop=True)


def load_lgd(path: Path | None = None) -> pd.DataFrame:
    """LGD district export (lgd_code, state, district, census2011_code)."""
    path = path or paths.MANUAL / "lgd_districts.csv"
    df = pd.read_csv(path, comment="#")
    df["lgd_code"] = pd.to_numeric(df["lgd_code"], errors="coerce").astype("Int64")
    df["census2011_code"] = pd.to_numeric(df["census2011_code"], errors="coerce").astype("Int64")
    return df


def load_splits(path: Path | None = None) -> pd.DataFrame:
    path = path or paths.MANUAL / "district_splits.csv"
    if not Path(path).exists():
        return pd.DataFrame(columns=["child_lgd_code", "parent_census2011_code", "pop_share"])
    df = pd.read_csv(path, comment="#")
    for c in ("child_lgd_code", "parent_census2011_code"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    return df


# ------------------------------------------------------------- the crosswalk
class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def build(census: pd.DataFrame, lgd: pd.DataFrame, splits: pd.DataFrame
          ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (crosswalk, problems, census_units).

    crosswalk: one row per (lgd_code, census2011_code) link with
      weight     = share of the LGD district's population from that census district
      unit_id    = harmonised unit (stable territory)
    """
    links = []
    for r in lgd.itertuples():
        if pd.notna(r.census2011_code):
            links.append((r.lgd_code, r.census2011_code, 1.0, "census_code"))
    for r in splits.itertuples():
        share = float(r.pop_share) if pd.notna(getattr(r, "pop_share", None)) else None
        links.append((r.child_lgd_code, r.parent_census2011_code, share, "split"))
    xw = pd.DataFrame(links, columns=["lgd_code", "census2011_code", "weight", "link"])

    problems = []
    known_lgd = set(lgd["lgd_code"].dropna())
    linked = set(xw["lgd_code"].dropna())
    for c in sorted(known_lgd - linked):
        nm = lgd.loc[lgd.lgd_code == c, "district"].iat[0]
        problems.append({"issue": "lgd_without_parent", "code": int(c), "name": nm,
                         "fix": "add a row to data/manual/district_splits.csv"})
    bad_parent = set(xw["census2011_code"]) - set(census["census2011_code"])
    for c in sorted(x for x in bad_parent if pd.notna(x)):
        problems.append({"issue": "unknown_census_code", "code": int(c), "name": None,
                         "fix": "check census2011_code against the 2011 boundary file"})
    for c in sorted(set(census["census2011_code"]) - set(xw["census2011_code"])):
        nm = census.loc[census.census2011_code == c, "district"].iat[0]
        problems.append({"issue": "census_district_unlinked", "code": int(c), "name": nm,
                         "fix": "LGD row missing its census2011_code?"})

    # Missing split shares -> equal shares, flagged
    miss = xw["weight"].isna()
    if miss.any():
        n = xw[miss].groupby("lgd_code")["census2011_code"].transform("count")
        xw.loc[miss, "weight"] = 1.0 / n
        for c in xw.loc[miss, "lgd_code"].unique():
            problems.append({"issue": "split_share_assumed_equal", "code": int(c), "name": None,
                             "fix": "add pop_share from Census/LGD notification"})

    uf = _UF()
    for c in census["census2011_code"]:
        uf.find(("C", int(c)))
    for r in xw.itertuples():
        uf.union(("C", int(r.census2011_code)), ("L", int(r.lgd_code)))
    # unit id = U + smallest census code in the component (stable and readable)
    comp_min = {}
    for node in uf.p:
        if node[0] == "C":
            root = uf.find(node)
            comp_min[root] = min(comp_min.get(root, node[1]), node[1])
    xw["unit_id"] = [f"U{comp_min[uf.find(('C', int(c)))]:04d}" for c in xw["census2011_code"]]

    census_units = census.assign(
        unit_id=[f"U{comp_min[uf.find(('C', int(c)))]:04d}" for c in census["census2011_code"]])
    return xw, pd.DataFrame(problems), census_units


def unit_table(census_units: pd.DataFrame, xw: pd.DataFrame, lgd: pd.DataFrame) -> pd.DataFrame:
    """One row per harmonised unit with its member districts, for reports and the demo."""
    cen = census_units.groupby("unit_id").agg(
        state=("state", "first"),
        census2011_codes=("census2011_code", lambda s: ";".join(map(str, sorted(s)))),
        census2011_names=("district", lambda s: ";".join(sorted(s))),
        n_census=("census2011_code", "count"))
    lg = xw.merge(lgd[["lgd_code", "district"]], on="lgd_code", how="left").groupby("unit_id").agg(
        lgd_codes=("lgd_code", lambda s: ";".join(map(str, sorted(set(s))))),
        lgd_names=("district", lambda s: ";".join(sorted(set(map(str, s))))),
        n_lgd=("lgd_code", "nunique"))
    out = cen.join(lg, how="left").reset_index()
    out["unit_name"] = out["census2011_names"].str.replace(";", " + ")
    out["stable"] = (out["n_census"] == 1) & (out["n_lgd"].fillna(1) == 1)
    return out


def spot_check_sample(matches: pd.DataFrame, n: int = 20, seed: int = 2026) -> pd.DataFrame:
    """Sample for Hanut's 20 spot checks: all fuzzy matches first, then random others."""
    fuzzy = matches[matches["match_method"] == "fuzzy"]
    rest = matches[matches["match_method"].isin(["exact", "alias"])]
    k = max(0, n - len(fuzzy))
    s = pd.concat([fuzzy.head(n), rest.sample(min(k, len(rest)), random_state=seed)])
    s = s.assign(hanut_ok="", hanut_note="")
    return s.reset_index(drop=True)
