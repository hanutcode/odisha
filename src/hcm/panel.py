"""Master district panel, 2015-2024, on harmonised units.

Input : every data/interim/*.parquet long table (state, district, year, variable, value, source)
Output: data/processed/panel_long.parquet, panel_wide.parquet, panel.duckdb
        data/interim/match_review.csv   (names that need an engineer)
        docs/crosswalk_spot_checks.csv  (Hanut's 20 spot checks)

The NFHS-6 outcome can never enter the panel: build() raises SealViolation
if it finds it. NFHS-6 lives only in data/sealed/ until the model freeze.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import crosswalk as cw
from . import paths

COUNT_PREFIXES = ("ncrb_", "udise_girls_", "odisha_", "cmpo_count")
COUNT_EXCEPTIONS = ("_rate", "_share", "_per_")
PANEL_YEARS = range(2015, 2025)


class SealViolation(RuntimeError):
    """NFHS-6 data found outside the sealed folder before the model freeze."""


def is_count(var: str) -> bool:
    return var.startswith(COUNT_PREFIXES) and not any(x in var for x in COUNT_EXCEPTIONS)


def check_seal(df: pd.DataFrame, where: str) -> None:
    sealed = paths.sealed_rounds()
    if "nfhs_round" in df and pd.to_numeric(df["nfhs_round"], errors="coerce").isin(sealed).any():
        raise SealViolation(
            f"Sealed NFHS round {sorted(sealed)} rows found in {where}. Move the file to data/raw/nfhs/round6/, "
            "run `hcm seal`, and rebuild. The panel must not contain NFHS-6 before the freeze.")


def reference_names(census_units: pd.DataFrame, xw: pd.DataFrame, lgd: pd.DataFrame) -> pd.DataFrame:
    """All known names (2011 and LGD) for each harmonised unit."""
    a = census_units[["state", "district", "unit_id"]]
    b = lgd.merge(xw[["lgd_code", "unit_id"]].drop_duplicates(), on="lgd_code")[["state", "district", "unit_id"]]
    return pd.concat([a, b], ignore_index=True).drop_duplicates()


def attach_units(df: pd.DataFrame, ref: pd.DataFrame, census_units: pd.DataFrame,
                 xw: pd.DataFrame, overrides: pd.DataFrame | None = None) -> pd.DataFrame:
    df = df.copy()
    if "unit_id" in df and df["unit_id"].notna().all():
        df["match_method"] = "code"
        return df
    if "census2011_code" in df:
        m = census_units.set_index("census2011_code")["unit_id"]
        df["unit_id"] = pd.to_numeric(df["census2011_code"], errors="coerce").map(m)
        df["match_method"] = "code"
        return df
    if "lgd_code" in df:
        m = xw.drop_duplicates("lgd_code").set_index("lgd_code")["unit_id"]
        df["unit_id"] = pd.to_numeric(df["lgd_code"], errors="coerce").map(m)
        df["match_method"] = "code"
        return df

    is_all = df["district"].astype(str).str.strip().str.upper().eq("ALL")
    by_name = cw.match_names(df[~is_all], ref, key="unit_id", overrides=overrides)
    # state-level rows -> every unit in that state
    st = df[is_all].copy()
    if len(st):
        units = census_units.assign(_s=census_units["state"].map(cw.norm_state))[["_s", "unit_id"]].drop_duplicates()
        st["_s"] = st["state"].map(cw.norm_state)
        st = st.merge(units, on="_s", how="left").drop(columns="_s")
        st["match_method"] = "state_broadcast"
    return pd.concat([by_name, st], ignore_index=True)


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["unit_id", "value"])
    keys = ["unit_id", "year", "variable"]
    parts = []
    for var, g in df.groupby("variable"):
        agg = "sum" if is_count(var) else "mean"
        a = g.groupby(keys).agg(value=("value", agg), n_source_rows=("value", "size"),
                                source=("source", lambda s: "; ".join(sorted(set(map(str, s))))[:300]))
        a["aggregation"] = agg
        parts.append(a.reset_index())
    out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=keys + ["value"])
    out["year"] = out["year"].astype(int)
    out["in_training_window"] = out["year"] <= paths.training_cutoff_year()
    return out


def build(interim: Path | None = None, processed: Path | None = None) -> dict:
    interim = Path(interim or paths.INTERIM)
    processed = Path(processed or paths.PROCESSED)
    processed.mkdir(parents=True, exist_ok=True)

    xw = pd.read_parquet(processed / "crosswalk.parquet")
    census_units = pd.read_parquet(processed / "census_units.parquet")
    units = pd.read_parquet(processed / "units.parquet")
    lgd = pd.read_parquet(processed / "lgd.parquet")
    ref = reference_names(census_units, xw, lgd)
    ov_path = paths.MANUAL / "match_overrides.csv"
    overrides = pd.read_csv(ov_path, comment="#") if ov_path.exists() else None

    frames, review, nonterr_rows = [], [], 0
    for f in sorted(interim.glob("*.parquet")):
        df = pd.read_parquet(f)
        check_seal(df, f.name)
        if "non_territorial" in df:  # railway/CID/cyber police units: no district territory
            nonterr = df[df["non_territorial"].fillna(False).astype(bool)]
            nonterr_rows += len(nonterr)
            df = df.drop(index=nonterr.index)
        df = attach_units(df, ref, census_units, xw, overrides)
        df["input_file"] = f.name
        frames.append(df)
        if "match_method" in df:
            bad = df[df["unit_id"].isna() | df["match_method"].isin(["fuzzy", "ambiguous"])]
            if len(bad):
                review.append(bad.reindex(columns=["state", "district", "match_method", "match_score",
                                                   "matched_name", "input_file"]).drop_duplicates())
    if not frames:
        raise FileNotFoundError(f"No interim tables in {interim}. Run the extract step first.")

    allrows = pd.concat(frames, ignore_index=True)
    long = aggregate(allrows)
    long = long[long["year"].isin(PANEL_YEARS)]
    check_seal(long, "panel")

    wide = long.pivot_table(index=["unit_id", "year"], columns="variable", values="value").reset_index()
    grid = pd.MultiIndex.from_product([units["unit_id"], list(PANEL_YEARS)],
                                      names=["unit_id", "year"]).to_frame(index=False)
    wide = grid.merge(wide, on=["unit_id", "year"], how="left").merge(
        units[["unit_id", "state", "unit_name", "stable"]], on="unit_id", how="left")
    wide["in_training_window"] = wide["year"] <= paths.training_cutoff_year()

    long.to_parquet(processed / "panel_long.parquet", index=False)
    wide.to_parquet(processed / "panel_wide.parquet", index=False)
    wide.to_csv(processed / "panel_wide.csv", index=False)

    import duckdb
    db = processed / "panel.duckdb"
    with duckdb.connect(str(db)) as con:
        for name, frame in {"panel_long": long, "panel_wide": wide, "units": units, "crosswalk": xw}.items():
            con.register("tmp", frame)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp")
            con.unregister("tmp")

    matched = allrows[allrows["match_method"].notna()]
    rv = pd.concat(review, ignore_index=True) if review else pd.DataFrame()
    rv.to_csv(paths.INTERIM / "match_review.csv", index=False)
    named = matched[~matched["match_method"].isin(["code", "state_broadcast"])]
    spot = paths.DOCS / "crosswalk_spot_checks.csv"
    ticked = spot.exists() and pd.read_csv(spot, dtype=str)["hanut_ok"].fillna("").str.strip().ne("").any() \
        if spot.exists() and "hanut_ok" in pd.read_csv(spot, nrows=0).columns else False
    if len(named) and not ticked:  # never overwrite checks Hanut has started
        cw.spot_check_sample(named.drop_duplicates(["state", "district"])[
            ["state", "district", "matched_name", "match_method", "match_score", "unit_id"]]
        ).to_csv(paths.DOCS / "crosswalk_spot_checks.csv", index=False)

    return {
        "units": int(units["unit_id"].nunique()),
        "rows_long": len(long),
        "variables": sorted(long["variable"].unique()),
        "unmatched_names": int(rv["district"].nunique()) if len(rv) else 0,
        "non_territorial_rows_left_out": nonterr_rows,
        "match_methods": matched["match_method"].value_counts().to_dict(),
    }
