import shutil

import pandas as pd
import pytest

from hcm import cli, contract, panel, seal


def _odisha_geo_as_india(project):
    """The crosswalk reads the all-India 2011 file; in tests the Odisha file stands in."""
    shutil.copy(project / "data/geo/odisha_districts_2011.geojson",
                project / "data/geo/india_districts_2011.geojson")


def _interim(project, rows, name):
    pd.DataFrame(rows, columns=["state", "district", "year", "variable", "value", "source", "nfhs_round"]
                 ).to_parquet(project / "data/interim" / f"{name}.parquet", index=False)


def test_panel_end_to_end(project):
    _odisha_geo_as_india(project)
    cli.main(["crosswalk"])
    _interim(project, [
        ("Orissa", "Khurda", 2016, "cm_20_24_before18", 15.9, "NFHS-4", 4),
        ("Odisha", "Khordha", 2020, "cm_20_24_before18", 12.4, "NFHS-5", 5),
    ], "nfhs")
    _interim(project, [
        ("Odisha", "Khurda", 2021, "ncrb_pcma_cases", 3, "NCRB", None),
        ("Odisha", "Keonjhar", 2021, "ncrb_pcma_cases", 5, "NCRB", None),
    ], "ncrb")
    r = panel.build()
    assert r["units"] == 30 and r["unmatched_names"] == 0
    w = pd.read_parquet(project / "data/processed/panel_wide.parquet")
    assert len(w) == 30 * 10
    k = w[(w.unit_name == "Khordha")].set_index("year")
    assert k.loc[2016, "cm_20_24_before18"] == 15.9 and k.loc[2021, "ncrb_pcma_cases"] == 3
    assert k.loc[2021, "in_training_window"] and not k.loc[2024, "in_training_window"]
    assert (project / "docs/crosswalk_spot_checks.csv").exists()


def test_nfhs6_enters_panel_now_seal_is_removed(project):
    _odisha_geo_as_india(project)
    cli.main(["crosswalk"])
    _interim(project, [("Odisha", "Puri", 2024, "cm_20_24_before18", 9.0, "NFHS-6", 6)], "nfhs6")
    panel.build()
    w = pd.read_parquet(project / "data/processed/panel_wide.parquet")
    assert w[(w.unit_name == "Puri") & (w.year == 2024)]["cm_20_24_before18"].iat[0] == 9.0


def test_lift_seal_opens_bundle_and_logs(project, tmp_path):
    import io, json, tarfile
    from cryptography.fernet import Fernet
    key = tmp_path / "nfhs6.key"; key.write_bytes(Fernet.generate_key())
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        data = b"%PDF fake nfhs6"
        info = tarfile.TarInfo("Puri.pdf"); info.size = len(data); tar.addfile(info, io.BytesIO(data))
    token = Fernet(key.read_bytes()).encrypt(buf.getvalue())
    (project / "data/sealed").mkdir(parents=True, exist_ok=True)
    (project / "data/sealed" / seal.BUNDLE).write_bytes(token)
    seal.log("seal", actor="t", bundle_sha256=seal._sha(token))
    e = seal.lift_seal(key, actor="t")
    assert (project / "data/raw/nfhs/round6/Puri.pdf").read_bytes() == b"%PDF fake nfhs6"
    assert [x["event"] for x in seal.read_log()] == ["seal", "seal_lifted"] and e["files"][0]["file"] == "Puri.pdf"
    (project / "data/sealed" / seal.BUNDLE).write_bytes(b"tampered")
    with pytest.raises(seal.SealError):          # hash check still guards the old bundle
        seal.lift_seal(key)


def test_mock_outputs_pass_contract_and_build_demo(project):
    import make_mock_outputs
    import build_static
    make_mock_outputs.main()
    est, rc = contract.load()
    assert len(est) == 30 and contract.is_mock(est)
    out = build_static.build(project / "dist/demo.html")
    html = out.read_text(encoding="utf-8")
    assert "MOCK" in html and "ଓଡ଼ିଆ" in html and "/*__DATA__*/" not in html


def test_contract_rejects_bad_outputs(project):
    est = pd.DataFrame([{"census2011_code": 387, "district": "Puri", "est_rate": 1.4, "est_lo": 0.1, "est_hi": 0.2,
                         "recorded_cases": 3, "detection_prob": 0.1, "flag": True, "reason_code": "X",
                         "model_run_id": "abc"}])
    rc = pd.DataFrame(columns=contract.REASON_COLS)
    with pytest.raises(contract.ContractError) as e:
        contract.validate(est, rc)
    assert "est_rate" in str(e.value) and "reason codes" in str(e.value)
