import pandas as pd
import pytest

from hcm import contract, modelkit, paths

pytestmark = pytest.mark.skipif(not (paths.PROCESSED / "panel_wide.parquet").exists(),
                                reason="panel not built")


def test_training_data_is_odisha_and_before_cutoff():
    d = modelkit.load_training_data()
    assert d["census2011_code"].between(370, 399).all()
    assert d["year"].max() <= paths.training_cutoff_year()


def test_write_outputs_round_trip(tmp_path):
    codes = list(range(370, 400))
    est = pd.DataFrame({"census2011_code": codes, "est_rate": 0.2, "est_lo": 0.1, "est_hi": 0.3,
                        "detection_prob": 0.05, "flag": [i == 370 for i in codes],
                        "reason_code": ["X" if i == 370 else "" for i in codes]})
    rc = pd.DataFrame({"reason_code": ["X"], "text_en": ["x"], "text_hi": ["x"], "text_or": ["x"],
                       "odia_checked": [False]})
    out = modelkit.write_outputs(est, rc, out_dir=tmp_path, model_run_id="test")
    e, r = contract.load(out / "district_estimates.csv", out / "reason_codes.csv")
    assert len(e) == 30 and e["district"].notna().all()


def test_write_outputs_refuses_bad_proportions(tmp_path):
    est = pd.DataFrame({"census2011_code": [370], "est_rate": [20.0], "est_lo": [0.1], "est_hi": [0.3],
                        "detection_prob": [0.1], "flag": [False], "reason_code": [""]})
    rc = pd.DataFrame(columns=contract.REASON_COLS)
    with pytest.raises(contract.ContractError):
        modelkit.write_outputs(est, rc, out_dir=tmp_path, model_run_id="test")
    assert not (tmp_path / "district_estimates.csv").exists()
