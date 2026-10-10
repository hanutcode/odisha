"""Steps 4–5: prepare inputs and fit the proposed detection-aware model.

Place this file at model/run_model.py in your existing project.
Run: .venv/bin/python model/run_model.py --check --class8-col COLUMN --transition-col COLUMN
Use --list-columns to inspect the input table's column names.
Omit --check to sample and print diagnostics; --noncentered improves recording geometry.
Install your project requirements-model.txt before fitting.
This file requires PyMC 5 or 6, PyTensor, ArviZ, NumPy and pandas.
Class 8 enrolment times eight is a temporary exposure proxy, not a Census count.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def prepare(d: pd.DataFrame, *, class8_col: str, transition_col: str):
    """Build aligned 2017–2021 inputs; reject gaps rather than impute silently."""
    required = ["census2011_code", "year", "rain_shock_z",
                "cm_20_24_before18", "ncrb_pcma_cases", class8_col, transition_col]
    missing = [c for c in required if c not in d.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    d = d.copy()
    if d[["census2011_code", "year"]].isna().any().any():
        raise ValueError("District codes and years cannot be missing.")
    d["year"] = pd.to_numeric(d["year"], errors="raise")
    if not np.isfinite(d["year"]).all() or (d["year"] % 1 != 0).any():
        raise ValueError("Years must be finite whole numbers.")
    d["year"] = d["year"].astype(int)
    if d.duplicated(["census2011_code", "year"]).any():
        raise ValueError("Expected one row per district per year.")
    for col in required[2:]:
        d[col] = pd.to_numeric(d[col], errors="raise")
    d = d.sort_values(["census2011_code", "year"])
    codes = pd.Index(sorted(d["census2011_code"].unique()), name="census2011_code")
    if len(codes) != 30:
        raise ValueError(f"Expected 30 districts; found {len(codes)}.")
    lookup = {code: i for i, code in enumerate(codes)}

    # Survey anchors must be extracted before filtering away 2016.
    def survey_for(year):
        values = (d.loc[d["year"].eq(year)]
                  .set_index("census2011_code")["cm_20_24_before18"]
                  .reindex(codes) / 100.0)
        if values.isna().any() or not values.between(0, 1).all():
            raise ValueError(f"Missing or invalid NFHS percentages for {year}.")
        return values.to_numpy()

    nfhs4, nfhs5 = survey_for(2016), survey_for(2020)
    grouped = d.groupby("census2011_code", sort=False)
    previous_year = grouped["year"].shift(1)
    previous_shock = grouped["rain_shock_z"].shift(1)
    # Do not mistake a previous observed row for the previous calendar year.
    previous_shock = previous_shock.where(previous_year.eq(d["year"] - 1))
    d["drought_lag"] = (-previous_shock).clip(lower=0)
    panel = d.loc[d["year"].between(2017, 2021)].copy()
    years = np.arange(2017, 2022)
    expected = pd.MultiIndex.from_product([codes, years],
                                          names=["census2011_code", "year"])
    actual = pd.MultiIndex.from_frame(panel[["census2011_code", "year"]])
    if len(expected.difference(actual)):
        raise ValueError("Missing district-year rows for 2017–2021.")
    needed = [class8_col, transition_col, "drought_lag", "ncrb_pcma_cases"]
    if not np.isfinite(panel[needed].to_numpy(dtype=float)).all():
        raise ValueError("Model inputs contain missing or non-finite values.")
    # Check the untransformed lag too: clipping could conceal an infinite shock.
    lag_used = previous_shock.loc[panel.index]
    if not np.isfinite(lag_used.to_numpy(dtype=float)).all():
        raise ValueError("Previous-year rainfall shocks must be finite.")
    if (panel[class8_col] <= 0).any():
        raise ValueError("Class 8 girls must be positive.")
    if (panel[transition_col] < 0).any():
        raise ValueError("Transition values cannot be negative.")
    counts = panel["ncrb_pcma_cases"]
    if ((counts < 0) | (counts % 1 != 0)).any():
        raise ValueError("Police cases must be non-negative integers.")
    panel["girls_at_risk"] = panel[class8_col] * 8
    transition_mean = float(panel[transition_col].mean())
    # Retain original units; zero now means the mean of the retained panel.
    panel["transition_centered"] = panel[transition_col] - transition_mean
    panel["district_idx"] = panel["census2011_code"].map(lookup).astype(int)
    panel["year_idx"] = panel["year"] - 2017
    panel = panel.reset_index(drop=True)
    return {
        "district_codes": codes.to_numpy(), "years": years,
        "district_idx": panel["district_idx"].to_numpy(),
        "year_idx": panel["year_idx"].to_numpy(),
        "girls_at_risk": panel["girls_at_risk"].to_numpy(),
        "drought_lag": panel["drought_lag"].to_numpy(),
        "transition_centered": panel["transition_centered"].to_numpy(),
        "transition_mean": transition_mean,
        "police_cases": panel["ncrb_pcma_cases"].to_numpy(dtype=int),
        "nfhs4": nfhs4, "nfhs5": nfhs5, "panel": panel,
    }


def fit(inputs, *, draws=500, tune=500, random_seed=20261010,
        survey_se=0.04, recording_center=0.0005, noncentered=False):
    """Fit the proposed Poisson model; return posterior draws, not output files.

    recording_center is data-informed. Survey SE and this centre require
    sensitivity checks. Survey anchors approximate historical cohort risk.
    noncentered=True preserves the prior but can improve sampling geometry.
    """
    import pymc as pm
    import pytensor.tensor as pt

    district_idx = np.asarray(inputs["district_idx"], dtype=int)
    year_idx = np.asarray(inputs["year_idx"], dtype=int)
    years = np.asarray(inputs["years"])[year_idx]
    girls = np.asarray(inputs["girls_at_risk"], dtype=float)
    drought = np.asarray(inputs["drought_lag"], dtype=float)
    transition = np.asarray(inputs["transition_centered"], dtype=float)
    cases = np.asarray(inputs["police_cases"], dtype=int)
    nfhs4 = np.asarray(inputs["nfhs4"], dtype=float)
    nfhs5 = np.asarray(inputs["nfhs5"], dtype=float)
    n_districts = len(inputs["district_codes"])
    if not np.array_equal(inputs["years"], np.arange(2017, 2022)):
        raise ValueError("fit expects model years 2017–2021.")
    if survey_se <= 0 or not 0 < recording_center < 1:
        raise ValueError("Invalid survey SE or recording prior centre.")
    rows2020 = np.flatnonzero(years == 2020)
    rows2020 = rows2020[np.argsort(district_idx[rows2020])]
    if not np.array_equal(district_idx[rows2020], np.arange(n_districts)):
        raise ValueError("Need exactly one 2020 row per district in survey order.")
    logit = lambda p: np.log(p / (1 - p))
    coords = {"district": inputs["district_codes"], "year": inputs["years"],
              "obs": np.arange(len(cases)), "increment": np.arange(2018, 2022)}
    with pm.Model(coords=coords) as model:
        a = pm.Normal("a", mu=logit(0.03), sigma=0.7, dims="district")
        b_trend = pm.Normal("b_trend", mu=0, sigma=0.15)
        b_drought = pm.Normal("b_drought", mu=0, sigma=0.5)
        b_trans = pm.Normal("b_trans", mu=0, sigma=2)
        logit_h = (a[district_idx] + b_trend * (years - 2019)
                   + b_drought * drought + b_trans * transition)
        h = pm.Deterministic("h", pm.math.invlogit(logit_h), dims="obs")
        h2016 = pm.math.invlogit(a + b_trend * (2016 - 2019))
        p2016 = pm.Deterministic("p2016", 1 - (1 - h2016)**8, dims="district")
        p2020 = pm.Deterministic("p2020", 1 - (1 - h[rows2020])**8, dims="district")
        pm.Normal("nfhs4_obs", mu=p2016, sigma=survey_se, observed=nfhs4, dims="district")
        pm.Normal("nfhs5_obs", mu=p2020, sigma=survey_se, observed=nfhs5, dims="district")
        mu_c = pm.Normal("mu_c", mu=logit(recording_center), sigma=1.5)
        sigma_c = pm.HalfNormal("sigma_c", sigma=1)
        if noncentered:
            c_raw = pm.Normal("c_raw", mu=0, sigma=1, dims="district")
            c = pm.Deterministic("c", mu_c + sigma_c * c_raw, dims="district")
        else:
            c = pm.Normal("c", mu=mu_c, sigma=sigma_c, dims="district")
        g_inc = pm.Normal("g_inc", mu=0, sigma=0.5, dims="increment")
        g = pm.Deterministic("g", pt.concatenate([pt.zeros(1), pt.cumsum(g_inc)]), dims="year")
        q = pm.Deterministic("q", pm.math.invlogit(c[district_idx] + g[year_idx]), dims="obs")
        pm.Poisson("cases_obs", mu=girls * h * q, observed=cases, dims="obs")
        idata = pm.sample(draws=draws, tune=tune, chains=2, cores=1,
                          nuts={"target_accept": 0.9}, random_seed=random_seed,
                          return_inferencedata=True)
    return idata


def recovery_test(inputs, *, seed=73, draws=1000, tune=1000):
    """Simulate conditional on real covariates; report central 94% intervals.

    One simulated dataset is illustrative, not a calibration or power study.
    Repeat with multiple seeds and report failures as well as successes.
    Survey values are untruncated Normal draws, matching the fitted likelihood.
    """
    from scipy.special import expit, logit
    rng = np.random.default_rng(seed)
    nd = len(inputs["district_codes"])
    di = np.asarray(inputs["district_idx"], dtype=int)
    yi = np.asarray(inputs["year_idx"], dtype=int)
    years = np.asarray(inputs["years"])[yi]
    truth = {"b_trend": 0.0, "b_drought": 0.4, "b_trans": -1.0,
             "mu_c": float(logit(0.0004)), "sigma_c": 0.8}
    a_true = rng.normal(logit(0.03), 0.7, nd)
    c_true = rng.normal(truth["mu_c"], truth["sigma_c"], nd)
    # Fixed, declared recording changes; g[2017] is anchored to zero.
    g_true = np.array([0.0, 0.10, -0.10, 0.05, 0.40])
    h_true = expit(a_true[di] + truth["b_trend"] * (years - 2019)
                  + truth["b_drought"] * inputs["drought_lag"]
                  + truth["b_trans"] * inputs["transition_centered"])
    q_true = expit(c_true[di] + g_true[yi])
    rows2020 = np.flatnonzero(years == 2020)
    rows2020 = rows2020[np.argsort(di[rows2020])]
    if not np.array_equal(di[rows2020], np.arange(nd)):
        raise ValueError("Need one aligned 2020 row per district.")
    h2016 = expit(a_true + truth["b_trend"] * (2016 - 2019))
    fake = dict(inputs)
    fake["nfhs4"] = rng.normal(1 - (1 - h2016)**8, 0.04)
    fake["nfhs5"] = rng.normal(1 - (1 - h_true[rows2020])**8, 0.04)
    fake["police_cases"] = rng.poisson(inputs["girls_at_risk"] * h_true * q_true)
    idata = fit(fake, draws=draws, tune=tune, random_seed=seed + 1,
                survey_se=0.04, recording_center=0.0005, noncentered=True)
    # Central equal-tailed 94% ranges: quantiles 0.03 and 0.97, not HDIs.
    rows = []
    for name, value in truth.items():
        samples = idata.posterior[name].values.ravel()
        lo, hi = np.quantile(samples, [0.03, 0.97])
        rows.append({"parameter": name, "true": value,
                     "posterior_mean": samples.mean(), "lo94": lo, "hi94": hi,
                     "covered": bool(lo <= value <= hi)})
    for name, values in [("a", a_true), ("c", c_true), ("g", g_true)]:
        for i, value in enumerate(values):
            samples = idata.posterior[name].values[:, :, i].ravel()
            lo, hi = np.quantile(samples, [0.03, 0.97])
            label = inputs["district_codes"][i] if name != "g" else inputs["years"][i]
            rows.append({"parameter": f"{name}[{label}]", "true": value,
                         "posterior_mean": samples.mean(), "lo94": lo, "hi94": hi,
                         "covered": bool(lo <= value <= hi)})
    return idata, pd.DataFrame(rows)


def summarise(result) -> pd.DataFrame:
    """TODO: census2011_code, est_rate, est_lo, est_hi, detection_prob,
    flag, reason_code. Rates and detection probabilities must be in 0–1.
    State the credible interval and pre-registered outreach rule.
    """
    raise NotImplementedError("summarise(): posterior estimates and flag rule")


def reasons() -> pd.DataFrame:
    """TODO: reason codes and translations. Native-speaker review is required
    before marking odia_checked True.
    """
    raise NotImplementedError("reasons(): reviewed reason codes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="prepare inputs; write nothing")
    ap.add_argument("--list-columns", action="store_true", help="list input columns; write nothing")
    ap.add_argument("--class8-col", help="exact column name for Class 8 girls enrolment")
    ap.add_argument("--transition-col", help="exact column name for Class 9-to-10 transition")
    ap.add_argument("--survey-se", type=float, default=0.04)
    ap.add_argument("--recording-center", type=float, default=0.0005)
    ap.add_argument("--noncentered", action="store_true")
    ap.add_argument("--recovery", action="store_true", help="simulate using real covariates and check recovery")
    ap.add_argument("--seed", type=int, default=73)
    ap.add_argument("--draws", type=int, default=500)
    ap.add_argument("--tune", type=int, default=500)
    a = ap.parse_args()
    # Deferred import lets prepare() be checked independently of project plumbing.
    from hcm import modelkit
    d = modelkit.load_training_data()
    print(f"{d['census2011_code'].nunique()} districts, years {d['year'].min()}–{d['year'].max()}")
    if a.list_columns:
        print("\n".join(d.columns.astype(str)))
        return
    print(modelkit.describe(d).to_string())
    if not a.class8_col or not a.transition_col:
        ap.error("Supply --class8-col and --transition-col; inspect --list-columns first.")
    inputs = prepare(d, class8_col=a.class8_col, transition_col=a.transition_col)
    if a.check:
        cols = ["census2011_code", "year", "district_idx", "girls_at_risk",
                "drought_lag", "transition_centered", "ncrb_pcma_cases"]
        print("\nPrepared rows:")
        print(inputs["panel"][cols].head(10).to_string(index=False))
        print("\nSurvey inputs (district order matches all model arrays):")
        print(pd.DataFrame({"census2011_code": inputs["district_codes"],
                            "nfhs4": inputs["nfhs4"], "nfhs5": inputs["nfhs5"]})
              .to_string(index=False))
        print("\nCheck Nabarangapur against NFHS-4 = 0.379 and NFHS-5 = 0.394.")
        print(f"Panel rows: {len(inputs['panel'])}; expected 150.")
        print(f"Centered transition mean: {inputs['transition_centered'].mean():.12f}")
        return
    import arviz as az
    if a.recovery:
        idata, recovery = recovery_test(inputs, seed=a.seed, draws=a.draws, tune=a.tune)
        print("SIMULATED DATA: central equal-tailed 94% recovery intervals")
        print(recovery.to_string(index=False))
        print("Recovery uses SE=0.04, prior centre=0.0005 and non-centred recording.")
    else:
        idata = fit(inputs, draws=a.draws, tune=a.tune, survey_se=a.survey_se,
                    recording_center=a.recording_center, noncentered=a.noncentered)
    print(az.summary(idata, var_names=["b_trend", "b_drought", "b_trans", "mu_c", "sigma_c"]).to_string())
    divergences = int(idata.sample_stats["diverging"].sum().item())
    print(f"Divergences: {divergences}")
    if divergences:
        print("Try --noncentered; rerun and check diagnostics before interpreting results.")
    weights = inputs["girls_at_risk"]
    for name in ["h", "q"]:
        values = idata.posterior[name].mean(dim=("chain", "draw")).values
        print(f"Exposure-weighted mean {name}: {np.average(values, weights=weights):.6f}")
    print("Step 5 only: no outreach output files written.")


if __name__ == "__main__":
    main()
