# Contribution log (dated lab notebook)

ISEF forms need a per-person, per-day record. The workspace adds entries automatically; export from the Contribution log page.

| Date | Person | Role | What was done | Entry |
|---|---|---|---|---|

| 2026-10-09 | Codex (AI-assisted engineering) | Engineering | Prepared fresh code-only Docker/Apache deployment at /cm/, corrected subpath URLs and cookie scope, configured production static serving, and verified 12 web tests plus authenticated production page checks. No model code or research data changed. |

| 2026-10-09 | Codex (AI-assisted engineering) | Engineering | Enabled deployed fair survey map with the existing 60 NFHS-4/5 district observations and Odisha boundaries; verified public response uses survey mode with mock=false. |

| 2026-10-09 | Codex (AI-assisted engineering) | Engineering | Migrated approved local source files and workspace records to production, preserved encrypted NFHS-6 seal and local key custody, verified matching source counts and unchanged production passwords. |

| 2026-10-09 | Claude (AI-assisted engineering) | Engineering | Demo tool only: MOCK model outputs can no longer appear on the public fair page or on production (HCM_ALLOW_MOCK, off when DEBUG is off); mock button hidden there; tests updated (13 web tests pass). No model code or research data changed. | manual |

| 2026-10-10 | Claude (AI-assisted engineering) | Engineering | Data plumbing only, no model code: added CHIRPS rainfall 2000–2024 (rain_mm, rain_shock_z); filled LGD districts (785) and district splits (145) from a public LGD concordance; fixed the NCRB 2017 Chhattisgarh/Bihar header erratum; left railway/CID/cyber police units out of district totals; added 260 reviewed district aliases (review queue now 0); protected Hanut's spot-check ticks from being overwritten; production security settings and a sync script; filled docs/data_audit.md. Odisha NFHS/NCRB/UDISE values unchanged. 25 pipeline + 13 web tests pass. | manual |

| 2026-10-10 | Claude (AI-assisted engineering) | Engineering | At Pankaj Jha's request: removed the NFHS-6 seal/freeze/witness/unseal workflow (CLI, Seal page, sealed upload) and the hanut/sweksha accounts and student/mentor roles; their pages now belong to the engineer/admin. Opened the sealed NFHS-6 bundle with the existing key (`hcm lift-seal`; SHA-256 matches the 9 Oct seal) into data/raw/nfhs/round6/ — it is the Odisha state fact sheet only, so no district NFHS-6 values enter the panel. Seal log history kept, new `seal_lifted` event appended; INTEGRITY.md notes the change. 25 pipeline + 14 web tests pass. | manual |

| 2026-10-10 | Claude (AI-assisted engineering) | Engineering | Added the Insights dashboard to the workspace (/insights/, public copy /fair/insights/): headline figures, district map, survey rate vs police records, yearly cases, rainfall and Class 9→10 charts, sortable table, built live from the district panel; d3 v7.9.0 vendored for offline use. Published figures only, no model estimates. 16 web tests pass. | manual |

| 2026-10-10 | Claude (AI-assisted engineering) | Engineering | Made the Insights dashboard the fair page at /fair/; the trilingual map moved to /fair/map/ (/fair/insights/ redirects to /fair/). 16 web tests pass. | manual |

| 2026-10-10 | Claude (AI-assisted, tutoring and review) | Model support | Explained the occurrence-versus-recording idea and asked design questions; reviewed model design, priors and code; ran review copies of the fit; advised on the recovery test and sensitivity checks; fixed environment issues (PyMC/SciPy versions). At Hanut's request, added the setup lines at the start of summarise() (copied from his fit(); marked with a comment in the code). Built the offline map from the real outputs. | manual |
| 2026-10-10 | Hanut | Model | Model decisions recorded in chat: survey-anchored annual risk with 1-(1-h)^8 link, Class 8 girls x 8 as exposure, pooled district recording, simplified to constant recording after recovery tests (3 seeds); sensitivity checks (survey SE 0.06, recording prior 0.0003); flag rule: lower 90% bound > 23.3% and recording in bottom third. Final fit: 4 districts flagged. NOTE for the forms: parts of model/run_model.py were brought in from outside this workspace; declare any AI-tool code generation accurately. | manual |
| 2026-10-10 | Claude (AI-assisted, presentation support) | Presentation | Made two silent motion videos from the real outputs: a 90-second map video with factual labels only (no narration; Hanut narrates in his own words) and a 30-second coach progress video labelled "prepared with AI assistance, not the IRIS submission". Wrote a coach progress-summary doc with the same label. No model code, data or submission text written. | manual |
