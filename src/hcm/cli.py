"""Command line: `python -m hcm <command>` (or `make <target>`).

  download            fetch URL-backed sources, list the manual ones
  extract             raw files -> data/interim/*.parquet
  crosswalk           build harmonised district units from LGD + splits
  panel               master district panel 2015-2024
  lift-seal / seal-status   open the old NFHS-6 sealed bundle; print the seal history
  validate-outputs    check Hanut's model outputs against the contract
  demo                build the offline demo HTML
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from . import paths


def cmd_download(a):
    from . import download
    for name, dest, status in download.run(a.only, a.force):
        print(f"{name:<32} {status:<12.80} {dest}")


def cmd_extract(a):
    from .extract import nfhs, tables
    paths.ensure_dirs()
    cfg = paths.sources()
    done = []
    for rnd, info in cfg["nfhs_rounds"].items():
        folder = paths.RAW / "nfhs" / f"round{rnd}"
        if info.get("sealed"):
            continue  # a round marked sealed in config/sources.yaml is skipped
        if folder.exists():
            df = nfhs.extract_round(folder, int(rnd))
            if len(df):
                df = df[~df["nfhs_round"].isin(paths.sealed_rounds())]
                df["year"] = df["nfhs_round"].map(lambda r: cfg["nfhs_rounds"][int(r)]["panel_year"])
                df.to_parquet(paths.INTERIM / f"nfhs{rnd}.parquet", index=False)
                done.append((f"nfhs{rnd}", len(df), int(df["value"].isna().sum())))
    csv_files = sorted((paths.RAW / "nfhs" / "csv").glob("*.csv"))
    if csv_files:
        df = pd.concat([nfhs.load_csv(f) for f in csv_files], ignore_index=True)
        if len(df):
            df = df[~df["nfhs_round"].isin(paths.sealed_rounds())]
            df["year"] = df["nfhs_round"].map(lambda r: cfg["nfhs_rounds"][int(r)]["panel_year"])
            df.to_parquet(paths.INTERIM / "nfhs_csv.parquet", index=False)
            done.append(("nfhs_csv", len(df), int(df["value"].isna().sum())))
    for src, loader, sub in (("ncrb", tables.load_ncrb, "ncrb"), ("udise", tables.load_udise, "udise")):
        files = sorted((paths.RAW / sub).glob("*.[cx][sl]*"))
        if not files:
            continue
        df = pd.concat([loader(f, year=tables._year_from(f.name, None)) for f in files], ignore_index=True)
        if src == "udise":
            df = pd.concat([df, tables.udise_transition(df)], ignore_index=True)
        df.to_parquet(paths.INTERIM / f"{src}.parquet", index=False)
        done.append((src, len(df), int(df["value"].isna().sum())))
    for name, label in (("odisha_reports", "Odisha WCD"), ("detection_capacity", "Detection capacity")):
        f = paths.MANUAL / f"{name}.csv"
        df = tables.load_long_template(f, label) if f.exists() else pd.DataFrame()
        if len(df):
            df.to_parquet(paths.INTERIM / f"{name}.parquet", index=False)
            done.append((name, len(df), 0))
    if a.rasters:
        _extract_rasters(done)
    for name, n, nmiss in done:
        print(f"{name:<22} {n:>7} rows  {nmiss:>5} missing values")
    if not done:
        print("Nothing to extract yet. Put raw files in data/raw/ (see config/sources.yaml).")


def _extract_rasters(done):
    import geopandas as gpd
    from .extract import rasters
    g = gpd.read_file(paths.GEO / "india_districts_2011.geojson")
    code = "censuscode" if "censuscode" in g else "dt_code"
    g["census2011_code"] = pd.to_numeric(g[code], errors="coerce").astype("Int64")
    frames = []
    for sub, pat, var, floor in (("chirps", "*.tif", "rain_mm", 0), ("viirs", "*.tif", "night_lights", 0)):
        df = rasters.yearly_zonal(paths.RAW / sub, pat, g, "census2011_code", var, floor)
        if len(df):
            frames.append(df)
            if var == "rain_mm":
                frames.append(rasters.rainfall_shock(df, "census2011_code"))
    if frames:
        df = pd.concat(frames, ignore_index=True)
        df["source"] = "zonal stats"
        df["state"] = df["district"] = None
        df.to_parquet(paths.INTERIM / "rasters.parquet", index=False)
        done.append(("rasters", len(df), int(df["value"].isna().sum())))


def cmd_crosswalk(a):
    from . import crosswalk as cw
    paths.ensure_dirs()
    census = cw.census2011_reference()
    lgd = cw.load_lgd()
    splits = cw.load_splits()
    if lgd.empty:
        print("data/manual/lgd_districts.csv is empty: using Census 2011 districts only "
              "(fine for Odisha, whose 30 districts have not changed since 1993).")
        lgd = census.rename(columns={"census2011_code": "lgd_code"}).assign(
            census2011_code=census["census2011_code"])
    xw, problems, census_units = cw.build(census, lgd, splits)
    units = cw.unit_table(census_units, xw, lgd)
    xw.to_parquet(paths.PROCESSED / "crosswalk.parquet", index=False)
    census_units.to_parquet(paths.PROCESSED / "census_units.parquet", index=False)
    units.to_parquet(paths.PROCESSED / "units.parquet", index=False)
    lgd.to_parquet(paths.PROCESSED / "lgd.parquet", index=False)
    units.to_csv(paths.PROCESSED / "units.csv", index=False)
    problems.to_csv(paths.INTERIM / "crosswalk_problems.csv", index=False)
    print(f"Census 2011 districts: {len(census)}   LGD districts: {lgd['lgd_code'].nunique()}   "
          f"harmonised units: {units['unit_id'].nunique()} ({int(units['stable'].sum())} unchanged)")
    if len(problems):
        print(f"{len(problems)} problems -> data/interim/crosswalk_problems.csv")
        print(problems["issue"].value_counts().to_string())


def cmd_panel(a):
    from . import panel
    r = panel.build()
    for k, v in r.items():
        print(f"{k:<16} {v}")


def cmd_lift_seal(a):
    from . import seal
    e = seal.lift_seal(Path(a.key), reason=a.reason or "")
    print(f"NFHS-6 opened: {len(e['files'])} file(s) -> {e['to']}. Logged at {e['utc']}.")


def cmd_seal_status(a):
    from . import seal
    print(seal.status())


def cmd_validate(a):
    from . import contract
    est, rc = contract.load()
    print(f"OK: {len(est)} districts, {int(est['flag'].sum())} flagged, {len(rc)} reason codes"
          + ("  [MOCK DATA]" if contract.is_mock(est) else ""))


def cmd_demo(a):
    sys.path.insert(0, str(paths.ROOT / "demo"))
    import build_static
    p = build_static.build()
    print(f"Offline demo: {p}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="hcm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("download"); s.add_argument("--only", nargs="*"); s.add_argument("--force", action="store_true")
    s.set_defaults(f=cmd_download)
    s = sub.add_parser("extract"); s.add_argument("--rasters", action="store_true"); s.set_defaults(f=cmd_extract)
    sub.add_parser("crosswalk").set_defaults(f=cmd_crosswalk)
    sub.add_parser("panel").set_defaults(f=cmd_panel)
    s = sub.add_parser("lift-seal"); s.add_argument("--key", required=True); s.add_argument("--reason")
    s.set_defaults(f=cmd_lift_seal)
    sub.add_parser("seal-status").set_defaults(f=cmd_seal_status)
    sub.add_parser("validate-outputs").set_defaults(f=cmd_validate)
    sub.add_parser("demo").set_defaults(f=cmd_demo)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
