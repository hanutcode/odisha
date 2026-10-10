# Submission status (10 Oct 2026)

IRIS deadline: noon, Tue 13 Oct 2026. Legend: ✅ done · ⚠️ needs a decision · ❌ not done.

## Engineering (finished)

| Item | Status | Where |
|---|---|---|
| District panel 2015–2024 (NFHS-4/5, NCRB, UDISE+, CHIRPS), Odisha 30/30 districts | ✅ | `data/processed/` |
| All-India crosswalk (785 LGD → 613 units), review queue 0 | ✅ | `data/manual/`, `data/interim/` |
| Data audit | ✅ | `docs/data_audit.md` |
| Engineering technical report v1.1 (updated for the seal removal, new data, roles) | ✅ | `docs/IRIS_Technical_Report.docx` |
| Fair map from real model outputs (offline, EN/HI/OR); MOCK outputs moved out of the way | ✅ | `dist/odisha_demo.html`, `/fair/map/` |
| Hindi and Odia reason text checked by a native speaker | ❌ drafts only (`odia_checked = False`) | `outputs/reason_codes.csv` |
| Tests: 25 pipeline + 14 workspace, all passing | ✅ | `make test`, `manage.py test workspace` |
| Archive for Zenodo with checksums | ✅ built, ❌ not uploaded | `dist/code.zip`, `dist/processed_data.zip` (`make archive`) |
| Production server updated | ✅ updated manually 11 Oct (Hanut) | Public fair page: http://167.172.152.167/cm/fair · Workspace login: http://167.172.152.167/cm/login/ |

## Research and forms (the student's / team's work, not engineering)

| Item | Status |
|---|---|
| Model code (`model/run_model.py`) and real outputs | ✅ written and run 10 Oct: 30 districts, 4 flagged, contract check passes. Committed as `c503c28` and pushed to github.com/hanutcode/odisha; outputs re-run with `model_run_id = c503c28` (validate OK) |
| Synopsis, research paper, 90-second video | ❌ text not in the project. Silent 90 s visual video made (AI-assisted, labels only); Hanut records his own narration |
| OSF pre-registration link | ❌ not recorded |
| Go/no-go decision (NFHS-6 has no district data) | ⚠️ `docs/data_audit.md`, Decision line |
| ISEF forms 1, 1A, research plan, 1B (and 2) | ❌ not in the project |
| Contribution log matching the forms; declare AI-assisted engineering and the seal removal | ⚠️ `docs/contribution_log.md` |
| Zenodo DOI linked in the paper | ❌ after upload |

The seal removal means results cannot be described as a sealed, pre-registered
out-of-time test against NFHS-6 (`docs/INTEGRITY.md`).
