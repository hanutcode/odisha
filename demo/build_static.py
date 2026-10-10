"""Build the offline demo: one self-contained HTML file, no internet needed.

    python demo/build_static.py            -> dist/odisha_demo.html

Reads only the contract files (outputs/district_estimates.csv,
outputs/reason_codes.csv), the Odisha boundary file and demo/i18n.yaml.
Open the HTML in any browser; it also works from a USB stick at the fair.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import yaml
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hcm import contract, paths  # noqa: E402

TEMPLATE = Path(__file__).with_name("template.html")


def svg_paths(geojson: Path, tolerance: float = 0.004, width: float = 1000.0):
    gj = json.loads(geojson.read_text(encoding="utf-8"))
    feats = []
    for f in gj["features"]:
        geom = shape(f["geometry"]).simplify(tolerance, preserve_topology=True)
        feats.append((int(f["properties"]["dt_code"]), geom))
    minx = min(g.bounds[0] for _, g in feats); maxx = max(g.bounds[2] for _, g in feats)
    miny = min(g.bounds[1] for _, g in feats); maxy = max(g.bounds[3] for _, g in feats)
    k = math.cos(math.radians((miny + maxy) / 2))
    scale = width / ((maxx - minx) * k)
    height = (maxy - miny) * scale

    def pt(x, y):
        return f"{(x - minx) * k * scale:.1f},{(maxy - y) * scale:.1f}"

    out = {}
    for code, geom in feats:
        polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        d = []
        for p in polys:
            for ring in [p.exterior, *p.interiors]:
                c = list(ring.coords)
                d.append("M" + "L".join(pt(x, y) for x, y in c) + "Z")
        cx, cy = geom.representative_point().coords[0]
        out[code] = {"d": "".join(d), "cx": pt(cx, cy)}
    return out, width, height


def build(out: Path | None = None) -> Path:
    est, rc = contract.load()
    i18n = yaml.safe_load((Path(__file__).with_name("i18n.yaml")).read_text(encoding="utf-8"))
    shapes, w, h = svg_paths(paths.GEO / "odisha_districts_2011.geojson")
    names = i18n.get("district_names", {})

    districts = []
    for r in est.itertuples():
        code = int(r.census2011_code)
        if code not in shapes:
            raise SystemExit(f"census2011_code {code} ({r.district}) is not an Odisha district in the map file")
        nm = names.get(code, {})
        districts.append({
            "code": code, "name": {"en": r.district, "hi": nm.get("hi", r.district), "or": nm.get("or", r.district)},
            "est": float(r.est_rate), "lo": float(r.est_lo), "hi": float(r.est_hi),
            "rec": float(r.recorded_cases), "det": float(r.detection_prob), "flag": bool(r.flag), "reason": str(r.reason_code),
            "d": shapes[code]["d"], "c": shapes[code]["cx"],
        })
    reasons = {r.reason_code: {"en": r.text_en, "hi": r.text_hi, "or": r.text_or} for r in rc.itertuples()}
    payload = {
        "districts": districts, "reasons": reasons,
        "ui": {k: i18n[k] for k in ("en", "hi", "or")},
        "mock": bool(contract.is_mock(est)), "run": str(est["model_run_id"].iat[0]),
        "w": w, "h": h,
    }
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "/*__DATA__*/null", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    out = Path(out or ROOT / "dist" / "odisha_demo.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def build_survey(out: Path | None = None) -> Path | None:
    """Map of published NFHS district figures, used until the model writes its outputs.

    Shows NFHS-5 (2019-21) and NFHS-4 (2015-16) for women 20-24 married before 18, and
    the change between them. These are survey figures, never presented as model results.
    """
    import pandas as pd

    pw = paths.PROCESSED / "panel_wide.parquet"
    if not pw.exists():
        return None
    w = pd.read_parquet(pw)
    if "cm_20_24_before18" not in w:
        return None
    rounds = paths.sources()["nfhs_rounds"]
    y4, y5 = int(rounds[4]["panel_year"]), int(rounds[5]["panel_year"])
    v = w.pivot_table(index="unit_id", columns="year", values="cm_20_24_before18")
    i18n = yaml.safe_load((Path(__file__).with_name("i18n.yaml")).read_text(encoding="utf-8"))
    shapes, wd, ht = svg_paths(paths.GEO / "odisha_districts_2011.geojson")
    gj = json.loads((paths.GEO / "odisha_districts_2011.geojson").read_text(encoding="utf-8"))
    names = i18n.get("district_names", {})

    def series(var):
        return w.pivot_table(index="unit_id", columns="year", values=var) if var in w else None

    rec_t = series("ncrb_pcma_cases")
    tr_t = series("udise_transition_g9_g10")
    REC_YEARS, DROP_YEARS = range(2016, 2022), range(2017, 2022)   # training window only

    def rec_sum(code):
        uid = f"U{code:04d}"
        if rec_t is None or uid not in rec_t.index:
            return None
        s_ = rec_t.loc[uid, [y for y in REC_YEARS if y in rec_t.columns]]
        return int(s_.sum()) if s_.notna().any() else None

    def drop(code):
        uid = f"U{code:04d}"
        if tr_t is None or uid not in tr_t.index:
            return None
        s_ = tr_t.loc[uid, [y for y in DROP_YEARS if y in tr_t.columns]].dropna()
        return round(float((1 - s_.mean()) * 100), 1) if len(s_) else None

    def val(code, year):
        uid = f"U{code:04d}"
        if uid in v.index and year in v.columns and pd.notna(v.at[uid, year]):
            return round(float(v.at[uid, year]), 1)
        return None

    districts = []
    for f in gj["features"]:
        code = int(f["properties"]["dt_code"])
        en = f["properties"]["district"]
        nm = names.get(code, {})
        n4, n5 = val(code, y4), val(code, y5)
        districts.append({
            "code": code, "name": {"en": en, "hi": nm.get("hi", en), "or": nm.get("or", en)},
            "n4": n4, "n5": n5, "chg": round(n5 - n4, 1) if n4 is not None and n5 is not None else None,
            "rec": rec_sum(code), "drop": drop(code),
            "flag": False, "d": shapes[code]["d"], "c": shapes[code]["cx"],
        })
    if not any(d["n5"] is not None or d["n4"] is not None for d in districts):
        return None
    payload = {"mode": "survey", "districts": districts, "reasons": {},
               "ui": {k: i18n[k] for k in ("en", "hi", "or")}, "mock": False, "run": "", "w": wd, "h": ht}
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "/*__DATA__*/null", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    out = Path(out or ROOT / "dist" / "odisha_survey.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build()
    print(f"Wrote {p} ({p.stat().st_size / 1024:.0f} KB)")
