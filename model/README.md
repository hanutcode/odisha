# model/ — Hanut's code only

Everything in this folder is written by Hanut: the detection-aware Bayesian
model (PyMC or NumPyro), the synthetic-district simulation, the three
baselines and the out-of-time test. Engineers review it but don't write it
(integrity rule 1 in `docs/INTEGRITY.md`).

## What the pipeline gives you

- `data/processed/panel_wide.parquet`: one row per harmonised district unit
  and year (2015–2024). Columns are variables (`cm_20_24_before18`,
  `ncrb_pcma_cases`, `udise_transition_g8_g9`, `rain_shock_z`, ...), plus
  `unit_id`, `state`, `unit_name`, `stable` and `in_training_window`
  (year ≤ 2021).
- `data/processed/panel.duckdb`: the same tables, for SQL queries.
- `data/processed/units.csv`: what each `unit_id` contains.

NFHS-6 is **not** in the panel. It stays sealed until you run `hcm freeze`.

## Starting point (engineer plumbing, 7 Oct)

- `cp model/templates/run_model_template.py model/run_model.py`, then fill in its four
  TODO functions: `prepare`, `fit`, `summarise`, `reasons`. Every modelling choice is yours.
- `.venv/bin/python model/run_model.py --check` shows what data you have (30 Odisha
  districts, 2015–2021: NFHS 2016/2020, NCRB cases every year, UDISE+ 2016–2021).
- `src/hcm/modelkit.py` (engineer code) loads the data and writes/checks the two output
  files for you: `modelkit.write_outputs(estimates, reasons)`. List it as engineer help.
- Inference library: `.venv/bin/python -m pip install -r requirements-model.txt` (PyMC),
  or NumPyro if you prefer.

## What the demo tool needs from you

Write two files in `outputs/`, following the contract in
`src/hcm/contract.py`:

- `outputs/district_estimates.csv`
- `outputs/reason_codes.csv`

Set `model_run_id` to your model's commit hash. Then run `make demo`.

## Freeze day (Thu 8 Oct)

1. Commit everything in `model/`.
2. Run `python -m hcm freeze --prereg-url <OSF link>`. This tags the commit and logs it.
3. The engineer runs `python -m hcm unseal --key <key>`. This only works if
   `model/` matches the frozen commit.
