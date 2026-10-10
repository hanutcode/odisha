"""NCRB police units: non-territorial units are flagged, state spellings normalise."""
from hcm import crosswalk as cw
from hcm.extract.tables import is_non_territorial


def test_non_territorial_units_flagged():
    for name in ["G. R. P.", "GRP Raipur", "CID, CB", "SRP(Cuttack)", "Cyber Ahmedabad Range",
                 "W.Rly Ahmedabad", "Spl Cell", "Anti Terrorist Squad", "S. T. F.", "IGI Airport"]:
        assert is_non_territorial(name), name


def test_real_districts_not_flagged():
    for name in ["Cuttack", "Jaipur Metro", "Kanchipuram", "Sukma", "Cachar", "Trichy City",
                 "Siddipet Commissionerate", "Khasi Hills Eastern West", "Nabarangpur"]:
        assert not is_non_territorial(name), name


def test_ncrb_state_spellings():
    assert cw.norm_state("Delhi UT") == "delhi"
    assert cw.norm_state("A & N Islands") == cw.norm_state("A&N Islands") == "andaman nicobar islands"
    assert cw.norm_state("D&N Haveli") == "dadra nagar haveli"
    assert cw.norm_state("Nagaland #") == "nagaland"


def test_ncrb_2017_erratum():
    import importlib.util, pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "ncrb_tidy.py"
    spec = importlib.util.spec_from_file_location("ncrb_tidy", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert m.ERRATA[(2017, "Bihar", 2)] == "Chhattisgarh"
