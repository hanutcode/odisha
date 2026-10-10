"""Bridge between the web app and the hcm pipeline package.

The web app never reimplements pipeline logic: every action calls the same
functions as the command line, so both give identical results.
"""

from __future__ import annotations

import contextlib
import csv
import io
import shutil
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.utils import timezone
from django.utils.text import get_valid_filename

from hcm import cli, contract, paths

from .models import ContributionEntry, PipelineRun
from .roles import primary_role


# ------------------------------------------------------------------ uploads
@dataclass(frozen=True)
class Target:
    key: str
    label: str
    folder: str           # relative to project root
    exts: tuple[str, ...]
    multiple: bool = True
    replace_name: str | None = None   # single file that is replaced (manual templates)
    sealed: bool = False
    help: str = ""


TARGETS = [
    Target("nfhs4", "NFHS-4 district fact sheets", "data/raw/nfhs/round4", (".pdf",),
           help="One District Fact Sheet PDF per district from nfhsiips.in (Publications, Round NFHS-4, Type: District Fact Sheet). rchiips.org has moved there."),
    Target("nfhs5", "NFHS-5 district fact sheets", "data/raw/nfhs/round5", (".pdf",),
           help="One District Fact Sheet PDF per district from nfhsiips.in (Publications, Round NFHS-5, Type: District Fact Sheet). rchiips.org has moved there."),
    Target("nfhs_csv", "NFHS-4/5 fact sheets as CSV", "data/raw/nfhs/csv", (".csv",),
           help="Columns State, District, Indicator, NFHS-5, NFHS-4 (github.com/pratapvardhan/NFHS-5 format). "),
    Target("nfhs6", "NFHS-6 fact sheets", "data/raw/nfhs/round6", (".pdf",),
           help="District Fact Sheet PDFs from nfhsiips.in (Round NFHS-6). The seal was removed on 10 Oct 2026; these load like NFHS-4/5."),
    Target("ncrb", "NCRB Crime in India — PCM Act, district", "data/raw/ncrb", (".csv", ".xlsx", ".xls"),
           help="One file per year. Name files with the year, e.g. ncrb_2021.csv, if there is no Year column."),
    Target("udise", "UDISE+ enrolment by grade and gender", "data/raw/udise", (".csv", ".xlsx", ".xls"),
           help="One file per academic year."),
    Target("chirps", "CHIRPS annual rainfall rasters", "data/raw/chirps", (".tif", ".tiff"),
           help="Files must have the year in the name, e.g. chirps-v2.0.2019.tif."),
    Target("viirs", "VIIRS annual night lights", "data/raw/viirs", (".tif", ".tiff"),
           help="Files must have the year in the name, e.g. viirs_2019.tif."),
    Target("india_geo", "Census 2011 district boundaries (all-India)", "data/geo", (".geojson", ".json"),
           multiple=False, replace_name="india_districts_2011.geojson",
           help="DataMeet dists11.geojson. Needed for the crosswalk and rasters."),
    Target("lgd", "LGD district export", "data/manual", (".csv",), multiple=False, replace_name="lgd_districts.csv",
           help="Columns: lgd_code, state, district, census2011_code."),
    Target("splits", "District splits (new → parent)", "data/manual", (".csv",), multiple=False,
           replace_name="district_splits.csv",
           help="Columns: child_lgd_code, parent_census2011_code, pop_share, source_ref."),
    Target("aliases", "District spelling aliases", "data/manual", (".csv",), multiple=False,
           replace_name="district_aliases.csv", help="Columns: state, alias, canonical."),
    Target("odisha", "Odisha WCD reports", "data/manual", (".csv",), multiple=False,
           replace_name="odisha_reports.csv", help="Columns: state, district, year, variable, value, source_ref."),
    Target("capacity", "Detection capacity", "data/manual", (".csv",), multiple=False,
           replace_name="detection_capacity.csv", help="Columns: state, district, year, variable, value, source_ref."),
]
TARGET_BY_KEY = {t.key: t for t in TARGETS}


def target_files(t: Target) -> list[dict]:
    folder = paths.ROOT / t.folder
    if t.replace_name:
        files = [folder / t.replace_name] if (folder / t.replace_name).exists() else []
    else:
        files = sorted(p for p in folder.glob("*") if p.is_file() and p.suffix.lower() in t.exts) if folder.exists() else []
    out = []
    for f in files:
        st = f.stat()
        rows = None
        if f.suffix == ".csv":
            with open(f, encoding="utf-8", errors="replace") as fh:
                rows = max(sum(1 for line in fh if line.strip() and not line.startswith("#")) - 1, 0)
        out.append({"name": f.name, "kb": st.st_size / 1024, "modified": datetime.fromtimestamp(st.st_mtime),
                    "rows": rows})
    return out


def save_upload(t: Target, files, user) -> str:
    folder = paths.ROOT / t.folder
    folder.mkdir(parents=True, exist_ok=True)
    bad = [f.name for f in files if Path(f.name).suffix.lower() not in t.exts]
    if bad:
        raise ValueError(f"Wrong file type: {', '.join(bad)}. Allowed: {', '.join(t.exts)}")
    saved = []
    for f in files:
        name = t.replace_name or get_valid_filename(Path(f.name).name)
        dest = folder / name
        if t.replace_name and dest.exists():  # keep the previous version
            backup = folder / "_previous"
            backup.mkdir(exist_ok=True)
            shutil.copy2(dest, backup / f"{dest.stem}.{timezone.now():%Y%m%d-%H%M%S}{dest.suffix}")
        with open(dest, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)
        saved.append(dest)
    note(user, f"Uploaded {len(saved)} file(s) to {t.label}")
    return f"Saved {len(saved)} file(s) to {t.label}."


# ----------------------------------------------------------------- pipeline
def run_step(step: str, user) -> PipelineRun:
    buf = io.StringIO()
    t0 = time.time()
    ok = True
    with contextlib.redirect_stdout(buf):
        try:
            paths.sources.cache_clear()
            if step == "extract":
                cli.main(["extract"])
            elif step == "extract_rasters":
                cli.main(["extract", "--rasters"])
            elif step == "crosswalk":
                cli.main(["crosswalk"])
            elif step == "panel":
                cli.main(["crosswalk"])
                cli.main(["panel"])
            elif step == "demo":
                cli.main(["demo"])
            else:
                raise ValueError(f"Unknown step {step}")
        except SystemExit as e:
            ok = e.code in (0, None)
        except Exception as e:  # show the error on the page instead of a 500
            ok = False
            print(f"\nERROR: {type(e).__name__}: {e}")
            print(traceback.format_exc(limit=3))
    run = PipelineRun.objects.create(step=step, user=user, ok=ok, seconds=time.time() - t0,
                                     log=buf.getvalue()[-20000:])
    note(user, f"Ran pipeline step '{run.get_step_display()}' — {'OK' if ok else 'FAILED'}")
    return run


# ------------------------------------------------------------- csv helpers
def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, comment="#").fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def append_override(state: str, district: str, unit_id: str) -> None:
    f = paths.MANUAL / "match_overrides.csv"
    new = not f.exists()
    with open(f, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["state", "district", "unit_id"])
        w.writerow([state, district, unit_id])


def units() -> pd.DataFrame:
    p = paths.PROCESSED / "units.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def panel_wide() -> pd.DataFrame:
    p = paths.PROCESSED / "panel_wide.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


# --------------------------------------------------------------- outputs
def save_outputs(est_file, rc_file, user) -> str:
    """Validate Hanut's model outputs against the contract before replacing anything."""
    est = pd.read_csv(est_file)
    rc = pd.read_csv(rc_file).fillna("")
    contract.validate(est, rc)
    paths.OUTPUTS.mkdir(exist_ok=True)
    est.to_csv(paths.OUTPUTS / "district_estimates.csv", index=False)
    rc.to_csv(paths.OUTPUTS / "reason_codes.csv", index=False)
    run_step("demo", user)
    mock = contract.is_mock(est)
    note(user, f"Uploaded model outputs (run {est['model_run_id'].iat[0]}){' [MOCK]' if mock else ''}")
    return f"Outputs accepted: {len(est)} districts, {int(contract._bool(est['flag']).sum())} flagged."


def outputs_state() -> dict:
    try:
        est, rc = contract.load()
    except FileNotFoundError:
        return {"present": False}
    except contract.ContractError as e:
        return {"present": True, "error": str(e)}
    return {"present": True, "mock": contract.is_mock(est), "mock_hidden": contract.is_mock(est) and not mock_allowed(),
            "districts": len(est),
            "flagged": int(est["flag"].sum()), "run": str(est["model_run_id"].iat[0]),
            "odia_unchecked": int((~rc["odia_checked"]).sum())}


def mock_allowed() -> bool:
    """MOCK outputs are for building the demo only (INTEGRITY rule 5): never in production."""
    from django.conf import settings
    return bool(getattr(settings, "HCM_ALLOW_MOCK", False))


def outputs_are_mock() -> bool:
    try:
        est, _ = contract.load()
    except (FileNotFoundError, contract.ContractError):
        return False
    return bool(contract.is_mock(est))


def demo_html(allow_mock: bool | None = None) -> Path | None:
    """The map page: real model outputs when they exist, otherwise the NFHS survey map.

    MOCK outputs are shown only when allowed (local development); the public fair
    view and production always fall back to the published survey figures.
    """
    if allow_mock is None:
        allow_mock = mock_allowed()
    out = paths.ROOT / "dist" / "odisha_demo.html"
    tpl = [paths.ROOT / "demo" / "i18n.yaml", paths.ROOT / "demo" / "template.html"]
    src = [paths.OUTPUTS / "district_estimates.csv", paths.OUTPUTS / "reason_codes.csv"] + tpl
    import build_static
    if src[0].exists() and (allow_mock or not outputs_are_mock()):
        try:
            if not out.exists() or out.stat().st_mtime < max(s.stat().st_mtime for s in src if s.exists()):
                build_static.build(out)
            return out
        except (contract.ContractError, FileNotFoundError, SystemExit):
            pass  # broken outputs: fall back to the survey map
    return survey_html()


def survey_html() -> Path | None:
    out = paths.ROOT / "dist" / "odisha_survey.html"
    src = [paths.PROCESSED / "panel_wide.parquet", paths.ROOT / "demo" / "i18n.yaml", paths.ROOT / "demo" / "template.html"]
    if not src[0].exists():
        return None
    if not out.exists() or out.stat().st_mtime < max(s.stat().st_mtime for s in src if s.exists()):
        import build_static
        return build_static.build_survey(out)
    return out


# --------------------------------------------------------------- notebook
def note(user, text: str) -> None:
    if user is None or not user.is_authenticated:
        return
    ContributionEntry.objects.create(
        date=timezone.localdate(), user=user, person=user.get_full_name() or user.username,
        role=primary_role(user), text=text, automatic=True)


def export_log() -> Path:
    lines = ["# Contribution log (dated lab notebook)", "",
             "Exported from the team workspace. One row per task, newest first.", "",
             "| Date | Person | Role | What was done | Entry |", "|---|---|---|---|---|"]
    for e in ContributionEntry.objects.all():
        text = e.text.replace("|", "/").replace("\n", " ")
        lines.append(f"| {e.date} | {e.person} | {e.role} | {text} | {'auto' if e.automatic else 'manual'} |")
    out = paths.DOCS / "contribution_log.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


# --------------------------------------------------------------- dashboard
SPRINT = [
    ("2026-10-03", "Sat 3 Oct", "Go/no-go decided. Hypotheses written.", True),
    ("2026-10-04", "Sun 4 Oct", "Crosswalk v1 done. Pre-registration drafted.", False),
    ("2026-10-05", "Mon 5 Oct", "Panel complete. First chart shows the reporting gap.", False),
    ("2026-10-06", "Tue 6 Oct", "Pre-registration time-stamped. Model recovers known values on synthetic data.", False),
    ("2026-10-07", "Wed 7 Oct", "All models fitted. Proof reviewed.", False),
    ("2026-10-08", "Thu 8 Oct", "Headline result in hand.", True),
    ("2026-10-09", "Fri 9 Oct", "Results section numbers final.", False),
    ("2026-10-10", "Sat 10 Oct", "Demo tool works end to end. Protocol written.", False),
    ("2026-10-11", "Sun 11 Oct", "Full paper draft.", False),
    ("2026-10-12", "Mon 12 Oct", "Everything final except proofreading.", False),
    ("2026-10-13", "Tue 13 Oct", "Submitted.", True),
]


def sprint_days() -> list[dict]:
    today = timezone.localdate().isoformat()
    return [{"date": d, "label": lbl, "goal": goal, "gate": gate,
             "state": "past" if d < today else "today" if d == today else "future"}
            for d, lbl, goal, gate in SPRINT]


def status_summary() -> dict:
    raw_counts = {t.key: len([f for f in target_files(t) if f["rows"] != 0]) for t in TARGETS}
    problems = read_csv(paths.INTERIM / "crosswalk_problems.csv")
    review = read_csv(paths.INTERIM / "match_review.csv")
    pw = paths.PROCESSED / "panel_wide.parquet"
    n6 = raw_counts.get("nfhs6", 0)
    seal_state = f"{n6} file{'s' if n6 != 1 else ''} (not sealed)"
    return {
        "raw_counts": raw_counts,
        "sources_with_files": sum(1 for v in raw_counts.values() if v),
        "sources_total": len(TARGETS),
        "crosswalk_problems": len(problems),
        "review_names": review["district"].nunique() if len(review) else 0,
        "panel_built": pw.exists(),
        "panel_time": datetime.fromtimestamp(pw.stat().st_mtime) if pw.exists() else None,
        "seal_state": seal_state,
        "outputs": outputs_state(),
    }


# --------------------------------------------------------------- insights
def insights_data() -> dict | None:
    """Odisha tables for the Insights page, from the district panel (published figures only).

    odisha_districts: one row per district; district_year: district x year 2015-2024;
    pcma_by_year: PCM Act cases per year, Odisha and all India (district units);
    odisha_map: simplified SVG outlines by Census 2011 code.
    """
    pw = paths.PROCESSED / "panel_wide.parquet"
    if not pw.exists():
        return None
    import build_static
    w = pd.read_parquet(pw)
    o = w[w["state"].astype(str).str.contains("odisha", case=False)].copy()
    if o.empty:
        return None
    o["code"] = o["unit_id"].str[1:].astype(int)
    v = lambda x: None if pd.isna(x) else float(x)
    districts, dy = [], []
    for (code, name), g in o.groupby(["code", "unit_name"]):
        g = g.set_index("year")
        get = lambda col, y: v(g[col].get(y)) if col in g else None
        cases = [get("ncrb_pcma_cases", y) for y in range(2016, 2022)]
        drop = [1 - t for t in (get("udise_transition_g9_g10", y) for y in range(2017, 2022)) if t is not None]
        n4, n5 = get("cm_20_24_before18", 2016), get("cm_20_24_before18", 2020)
        districts.append({
            "code": int(code), "district": name, "nfhs4_pct": n4, "nfhs5_pct": n5,
            "change_pts": None if n4 is None or n5 is None else round(n5 - n4, 1),
            "teen_preg4_pct": get("teen_pregnancy_15_19", 2016), "teen_preg5_pct": get("teen_pregnancy_15_19", 2020),
            "cases_2016_2021": int(sum(c for c in cases if c is not None)),
            "g9_g10_dropoff_pct": round(100 * sum(drop) / len(drop), 1) if drop else None,
        })
        for y in range(2015, 2025):
            dy.append({"code": int(code), "district": name, "year": y, "cases": get("ncrb_pcma_cases", y),
                       "rain_mm": get("rain_mm", y), "rain_shock_z": get("rain_shock_z", y),
                       "g9_g10_transition": get("udise_transition_g9_g10", y)})
    by_year = w[w["year"].between(2015, 2022)].groupby("year")["ncrb_pcma_cases"].sum()
    od_year = o.groupby("year")["ncrb_pcma_cases"].sum()
    pcma = [{"year": int(y), "odisha": int(od_year.get(y, 0)), "india": int(by_year.get(y, 0))} for y in range(2015, 2023)]
    shapes, _, _ = build_static.svg_paths(paths.GEO / "odisha_districts_2011.geojson", tolerance=0.006, width=600)
    geo = [{"code": int(k), "d": (p["d"] if isinstance(p, dict) else p)} for k, p in shapes.items()]
    return {"odisha_districts": sorted(districts, key=lambda r: r["district"]), "district_year": dy,
            "pcma_by_year": pcma, "odisha_map": geo}
