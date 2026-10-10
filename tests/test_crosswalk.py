import pandas as pd

from hcm import crosswalk as cw
from hcm import paths


def toy():
    census = pd.DataFrame({"state": ["S"] * 3, "district": ["Alpha", "Beta", "Gamma"],
                           "census2011_code": pd.array([1, 2, 3], dtype="Int64")})
    lgd = pd.DataFrame({"lgd_code": pd.array([10, 20, 30, 40], dtype="Int64"), "state": ["S"] * 4,
                        "district": ["Alpha", "Beta", "Gamma", "Delta"],
                        "census2011_code": pd.array([1, 2, 3, None], dtype="Int64")})
    # Delta (2016) was carved out of Beta and Gamma
    splits = pd.DataFrame({"child_lgd_code": pd.array([40, 40], dtype="Int64"),
                           "parent_census2011_code": pd.array([2, 3], dtype="Int64"),
                           "pop_share": [0.7, 0.3]})
    return census, lgd, splits


def test_split_folds_into_one_harmonised_unit():
    census, lgd, splits = toy()
    xw, problems, cu = cw.build(census, lgd, splits)
    units = cu.set_index("district")["unit_id"]
    assert units["Beta"] == units["Gamma"] != units["Alpha"]
    assert set(xw.loc[xw.lgd_code == 40, "unit_id"]) == {units["Beta"]}
    assert problems.empty
    ut = cw.unit_table(cu, xw, lgd).set_index("unit_id")
    assert ut.loc[units["Alpha"], "stable"] and not ut.loc[units["Beta"], "stable"]


def test_missing_parent_is_reported():
    census, lgd, _ = toy()
    _, problems, _ = cw.build(census, lgd, pd.DataFrame(columns=["child_lgd_code", "parent_census2011_code", "pop_share"]))
    assert "lgd_without_parent" in set(problems.issue)


def test_missing_share_assumed_equal_and_flagged():
    census, lgd, splits = toy()
    splits["pop_share"] = None
    xw, problems, _ = cw.build(census, lgd, splits)
    assert xw.loc[xw.lgd_code == 40, "weight"].tolist() == [0.5, 0.5]
    assert "split_share_assumed_equal" in set(problems.issue)


def test_odisha_spelling_variants_all_match():
    ref = cw.census2011_reference(paths.GEO / "odisha_districts_2011.geojson")
    assert len(ref) == 30
    variants = ["Khurda", "Baleswar", "Keonjhar", "Sonepur", "Bolangir", "Nabarangpur", "Jajapur",
                "Debagarh", "Anugul", "Baudh", "Kendrapada", "Malkanagiri", "Sundergarh", "Jagatsinghapur"]
    df = pd.DataFrame({"state": ["Orissa"] * len(variants), "district": variants})
    m = cw.match_names(df, ref, key="census2011_code")
    assert m["census2011_code"].notna().all(), m[m.census2011_code.isna()]
    assert m.set_index("district").loc["Khurda", "census2011_code"] == 386


def test_unknown_name_goes_to_review():
    ref = cw.census2011_reference(paths.GEO / "odisha_districts_2011.geojson")
    m = cw.match_names(pd.DataFrame({"state": ["Odisha"], "district": ["Atlantis"]}), ref, key="census2011_code")
    assert m.match_method.iat[0] == "unmatched" and pd.isna(m.census2011_code.iat[0])
