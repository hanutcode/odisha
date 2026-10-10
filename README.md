# Reports Measure the Watchers, Not the Harm

Engineering repo for Hanut Lal's IRIS 2026 entry (Behavioral & Social Sciences): finding hidden child marriages when official data is biased.

Everything here is **Python**. The repo holds the engineer-owned plumbing from the sprint plan, plus an empty `model/` folder for Hanut's own code:

| Part | Where | Owner |
|---|---|---|
| Data download and extraction (NFHS fact sheets, NCRB, UDISE+, Odisha WCD, CHIRPS/VIIRS) | `src/hcm/extract/`, `src/hcm/download.py` | Engineers |
| District crosswalk 640 → 707 → 715 (LGD codes, harmonised units, spelling aliases) | `src/hcm/crosswalk.py` | Engineers (incl. the 20 spot checks) |
| Master district panel 2015–2024 (Parquet + DuckDB) | `src/hcm/panel.py` | Engineers |
| NFHS-6 seal history (workflow removed 10 Oct) | `src/hcm/seal.py` | Engineers |
| Model, simulation, baselines, out-of-time test | `model/` | **Hanut only** |
| Odisha demo tool (offline HTML, Odia/Hindi/English) | `demo/` | Engineers |
| Figure style and templates | `src/hcm/figures.py` | Engineers, to Hanut's spec |

Read `docs/INTEGRITY.md` before writing any code.

## Web workspace (recommended)

The whole team works in a browser at **http://localhost:8000**:

```bash
./run_web.sh          # first run installs everything and prints each person's login
```

| Page | Who | What |
|---|---|---|
| Dashboard | Everyone | 11-day plan, status of every gate, IRIS checklist |
| Data sources | Engineer uploads | Upload each source, NFHS-6 included |
| Pipeline | Engineer | Run extract, crosswalk, panel and map with one click; full logs |
| Crosswalk review | Engineer | Unmatched names, overrides, crosswalk problems, the 20 spot checks |
| District panel | Everyone | Coverage by year, browse any variable, download CSV |
| Insights | Everyone | District dashboard of the published figures (map, survey vs police records, yearly trends, sortable table); public copy at `/fair/` |
| Odisha map | Engineer uploads outputs and checks wording | Model outputs, reason wording, embedded map, offline download |
| Contribution log | Everyone | Dated lab notebook (auto + manual), export for the ISEF forms |

Fair visitors open **http://localhost:8000/fair/** (dashboard) and **/fair/map/** (trilingual map). Neither needs a sign-in.

To reach the workspace from other laptops on the same Wi-Fi, run `HOST=0.0.0.0 ./run_web.sh` and add this Mac's IP address to `HCM_ALLOWED_HOSTS`.

## Command-line setup

```bash
make setup                 # creates .venv and installs requirements
source .venv/bin/activate
make test                  # 16 tests, about 2 seconds
```

Python 3.10 or newer is needed. Every command also works as `PYTHONPATH=src python -m hcm <command>`.

## Day-by-day commands

| Day | Command | What it does |
|---|---|---|
| Sat 3 | `make download` | Fetches the URL-backed sources and lists the manual ones. Record results in `docs/data_audit.md`. |
| Sun 4 | `make crosswalk` | Builds harmonised units. Fix everything listed in `data/interim/crosswalk_problems.csv`. |
| Sun 4–Mon 5 | `make extract` then `make panel` | Builds the panel. Clear `data/interim/match_review.csv`; tick `docs/crosswalk_spot_checks.csv`. |
| Wed 7 | `make mock` then `make serve` | Builds the demo on MOCK outputs while the model runs. |
| Fri 9–Sat 10 | `make demo` | Builds `dist/odisha_demo.html` from Hanut's real outputs. It runs offline, so put it on a USB stick too. |
| Tue 13 | `make archive` | Zips the code and processed data for the Zenodo DOI. |

The seal workflow was removed on 10 Oct 2026 (see `docs/INTEGRITY.md`). `make seal-status` prints the history.

## Manual inputs (`data/manual/`)

These files are templates. Paste in the real data and keep `source_ref` filled:

- `lgd_districts.csv`: the LGD district export, with Census 2011 codes.
- `district_splits.csv`: new districts and their parent 2011 districts.
- `district_aliases.csv`: spelling variants. Odisha's are already seeded.
- `odisha_reports.csv`: Odisha WCD reports and Assembly answers (reporting channel 3).
- `detection_capacity.csv`: police per capita, Childline 1098 and CMPOs.
- `match_overrides.csv` (optional): `state,district,unit_id` for names the matcher can't resolve.

If `lgd_districts.csv` is empty, the crosswalk falls back to Census 2011 districts. That works for Odisha, whose 30 districts are unchanged since 1993, but not for the all-India test.

## Model ↔ demo contract

Hanut's model writes `outputs/district_estimates.csv` and `outputs/reason_codes.csv`. The columns are listed in `src/hcm/contract.py`. Run `make validate` to check them. The demo reads nothing else.

## No-go fallback

If NFHS-6 has no district-level child-marriage data, edit `config/sources.yaml`:

- set `training_cutoff_year: 2016`
- mark round 5 `sealed: true` and round 6 not sealed

Seal the NFHS-5 sheets instead. Every guard follows the config.
