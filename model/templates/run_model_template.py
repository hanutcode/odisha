"""STARTER FILE for Hanut. Copy it to model/run_model.py and fill in the TODOs.

    cp model/templates/run_model_template.py model/run_model.py
    .venv/bin/python model/run_model.py --check      # data only, writes nothing
    .venv/bin/python model/run_model.py              # fit and write outputs/

The engineer wrote only the plumbing (loading data, writing and checking the
two output files, in src/hcm/modelkit.py). Every modelling decision below is
yours: model structure, priors, likelihood, inference library, flag rule and
reason codes. Record those choices in the OSF pre-registration before freeze
(Thu 8 Oct), and list the plumbing as engineer help in the contribution log.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from hcm import modelkit  # noqa: E402


def prepare(d: pd.DataFrame):
    """TODO (Hanut): turn the district x year table into model inputs.

    You have, per Odisha district (30) and year (2015-2021):
      cm_20_24_before18  NFHS survey estimate, % (2016 and 2020 only)
      ncrb_pcma_cases    police-recorded cases under the PCM Act
      udise_*            girls' enrolment and Class 8->9, 9->10 transition
      (detection_capacity / odisha_reports columns appear once those CSVs are filled)
    Decide: which years, which covariates, how to scale them, how to treat gaps.
    Note: there is no population column yet; think about what exposure the case
    counts need (e.g. girls' enrolment, or Census 2011 population you add).
    """
    raise NotImplementedError("prepare(): your choice of inputs")


def fit(inputs):
    """TODO (Hanut): the detection-aware model.

    The idea from your sprint plan: keep *occurrence* (how many child marriages
    happen) separate from *detection* (the chance one is recorded), so that a
    district with few recorded cases is not automatically a low-risk district.
    Write down: what drives occurrence, what drives detection, how the survey
    figures and the recorded counts each link to them, and your priors.
    Library is up to you (PyMC or NumPyro; see requirements-model.txt).
    Return whatever your summarise() needs (e.g. posterior draws).
    """
    raise NotImplementedError("fit(): your model")


def summarise(result) -> pd.DataFrame:
    """TODO (Hanut): one row per district with these columns (proportions in 0-1):

      census2011_code, est_rate, est_lo, est_hi, detection_prob, flag, reason_code

    est_rate = estimated true share of women 20-24 married before 18,
    est_lo/est_hi = your credible interval (state which one, e.g. 90%),
    flag/reason_code = your pre-registered outreach rule.
    district names and recorded_cases are filled in for you.
    """
    raise NotImplementedError("summarise(): your estimates and flag rule")


def reasons() -> pd.DataFrame:
    """TODO (Hanut): one row per reason_code you use. Hindi and Odia text must be
    checked by a native speaker before the fair (set odia_checked True only then)."""
    raise NotImplementedError("reasons(): your reason codes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="load and describe the data, write nothing")
    a = ap.parse_args()
    d = modelkit.load_training_data()
    print(f"{d['census2011_code'].nunique()} districts, years {d['year'].min()}-{d['year'].max()}")
    print(modelkit.describe(d).to_string())
    if a.check:
        return
    est = summarise(fit(prepare(d)))
    out = modelkit.write_outputs(est, reasons())
    print(f"Wrote and checked outputs in {out}. Next: python -m hcm demo  (or refresh /fair/)")


if __name__ == "__main__":
    main()
