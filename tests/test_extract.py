import math

import pandas as pd

from hcm.extract import nfhs, tables

SHEET = """
National Family Health Survey - 5
District Fact Sheet Khordha, Odisha
Marriage and Fertility NFHS-5 (2019-21) NFHS-4 (2015-16)
23. Women age 20-24 years married before age 18 years (%) 12.4 15.9
24. Men age 25-29 years married before age 21 years (%) (8.1) *
25. Women age 15-19 years who were already mothers or pregnant at the time of the survey (%) 4.1 na
"""


def test_nfhs_parse_current_and_previous_round():
    rows = pd.DataFrame(nfhs.parse_text(SHEET, round_=5))
    cm = rows[rows.variable == "cm_20_24_before18"].set_index("nfhs_round")["value"]
    assert cm[5] == 12.4 and cm[4] == 15.9
    assert set(rows.district) == {"Khordha"} and set(rows.state) == {"Odisha"}


def test_nfhs_small_n_and_suppressed():
    rows = pd.DataFrame(nfhs.parse_text(SHEET, round_=5)).set_index(["variable", "nfhs_round"])
    men5 = rows.loc[("men_25_29_before21", 5)]
    assert men5.value == 8.1 and men5.small_n
    men4 = rows.loc[("men_25_29_before21", 4)]
    assert math.isnan(men4.value) or men4.value is None
    assert men4.suppressed


def test_nfhs_values_wrapped_to_next_line():
    text = "District Fact Sheet Puri, Odisha\n23. Women age 20-24 years married before age 18 years (%)\n9.8 11.2\n"
    rows = nfhs.parse_text(text, round_=5)
    assert [r["value"] for r in rows] == [9.8, 11.2]


def test_ncrb_drops_totals_flags_grp(tmp_path):
    f = tmp_path / "ncrb_2021.csv"
    pd.DataFrame({
        "State/UT": ["Odisha"] * 4, "District": ["Khurda", "Puri", "GRP Cuttack", "Total Districts"],
        "Year": [2021] * 4, "Prohibition of Child Marriage Act": ["12", "1,204", "0", "1216"],
    }).to_csv(f, index=False)
    df = tables.load_ncrb(f)
    assert list(df.district) == ["Khurda", "Puri", "GRP Cuttack"]
    assert df.value.tolist() == [12, 1204, 0]
    assert df.non_territorial.tolist() == [False, False, True]


def test_udise_transition():
    long = pd.DataFrame([
        ("Odisha", "Puri", 2019, "udise_girls_g8", 1000.0),
        ("Odisha", "Puri", 2020, "udise_girls_g9", 900.0),
        ("Odisha", "Puri", 2019, "udise_girls_g9", 950.0),
        ("Odisha", "Puri", 2020, "udise_girls_g10", 2000.0),  # implausible jump
    ], columns=["state", "district", "year", "variable", "value"])
    t = tables.udise_transition(long).set_index("variable")
    assert t.loc["udise_transition_g8_g9", "value"] == 0.9
    assert pd.isna(t.loc["udise_transition_g9_g10", "value"])
    assert t.loc["udise_transition_g9_g10", "implausible"]


def test_raster_zonal_mean_and_shock(tmp_path):
    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import box

    from hcm.extract import rasters

    for year, level in ((2019, 100.0), (2020, 200.0), (2021, 300.0)):
        arr = np.full((10, 10), level, dtype="float32")
        arr[:, 5:] = level * 2  # right half wetter
        with rasterio.open(tmp_path / f"chirps-v2.0.{year}.tif", "w", driver="GTiff", height=10, width=10,
                           count=1, dtype="float32", crs="EPSG:4326",
                           transform=from_origin(80, 20, 1, 1), nodata=-9999) as dst:
            dst.write(arr, 1)
    g = gpd.GeoDataFrame({"code": [1, 2]}, geometry=[box(80, 10, 85, 20), box(85, 10, 90, 20)], crs="EPSG:4326")
    df = rasters.yearly_zonal(tmp_path, "*.tif", g, "code", "rain_mm")
    v = df.set_index(["code", "year"])["value"]
    assert v[(1, 2019)] == 100 and v[(2, 2019)] == 200
    z = rasters.rainfall_shock(df, "code").set_index(["code", "year"])["value"]
    assert z[(1, 2019)] < 0 < z[(1, 2021)]


def test_nfhs_csv_loader_keeps_nfhs6_now_unsealed(tmp_path, project):
    f = tmp_path / "n.csv"
    pd.DataFrame({
        "State": ["Bihar", "Bihar"], "District": ["Araria", "Araria"],
        "Indicator": ["16. Women age 20-24 years married before age 18 years (%)", "1. Female population"],
        "NFHS-5": ["43.5", "99"], "NFHS-4": ["(50.1)", "98"], "NFHS-6": ["40.0", "97"],
    }).to_csv(f, index=False)
    df = nfhs.load_csv(f).set_index("nfhs_round")
    assert set(df.index) == {4, 5, 6}           # the seal was removed: NFHS-6 loads like the others
    assert df.loc[5, "value"] == 43.5 and df.loc[4, "small_n"] and df.loc[6, "value"] == 40.0


def test_nfhs4_sheet_takes_total_column():
    text = ("This fact sheet provides information on key indicators and trends for Khordha. NFHS-4 fieldwork\n"
            "Khordha, Odisha - Key Indicators\n"
            "15. Women age 20-24 years married before age 18 years (%) 20.1 15.4 18.1\n")
    rows = nfhs.parse_text(text, round_=4)
    assert [(r["nfhs_round"], r["value"]) for r in rows] == [(4, 18.1)]
    assert rows[0]["district"] == "Khordha" and rows[0]["state"] == "Odisha"
