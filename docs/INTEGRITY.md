# Integrity rules and who built what

> **Change on 10 Oct 2026.** At the project lead's (Pankaj Jha's) request, the NFHS-6 seal
> workflow (seal, model freeze, witness and unseal) and the student and mentor workspace
> accounts were removed. The sealed NFHS-6 file was opened without a model freeze
> (`seal_lifted` event in `docs/seal_log.jsonl`; its SHA-256 matches the 9 Oct seal). That
> file is the Odisha *state* fact sheet only, so no district NFHS-6 values exist yet.
> Consequence: results can no longer be reported as a sealed, pre-registered out-of-time
> test against NFHS-6. Earlier seal-log events are kept unchanged as history. Rule 2 below
> no longer applies; the other rules stand.

These rules come from the sprint plan and match what goes on the ISEF forms.

## Ownership

| Hanut owns | Engineers can do | Sweksha owns |
|---|---|---|
| Research question and hypotheses | Data scraping and cleaning (`src/hcm/extract/`) | IRIS registration and forms |
| Model design and model code (`model/`) | District crosswalk (`src/hcm/crosswalk.py`); Hanut checks it | Mentor and reviewer outreach |
| Identifiability proof | Code review and speed-ups | Pre-registration posting and the NFHS-6 seal witness |
| Analysis and interpretation | Demo-tool front end (`demo/`) | Line editing and the timeline |
| All writing: paper, synopsis, video script | Figures to Hanut's spec (`src/hcm/figures.py`) | Odia wording check |
| Field and pilot protocol | Archiving code and data | |

## Rules

1. Hanut writes the model code himself. Engineers review it but don't write it.
2. The pre-registration and the NFHS-6 seal are non-negotiable:
   - NFHS-6 files are sealed with `hcm seal` on the day they're downloaded. The key stays with an engineer, outside the repo.
   - `hcm panel` refuses to build if NFHS-6 rows appear anywhere outside the sealed bundle.
   - `hcm unseal` works only after `hcm freeze` has recorded the model commit and the OSF link, and only if `model/` still matches that commit.
   - Every event is time-stamped in `docs/seal_log.jsonl`. Commit that file and cite it in the paper.
3. Keep `docs/contribution_log.md` up to date every day.
4. Hanut enters as an individual project.
5. Mock model outputs (`make mock`) are only for building the demo. They're labelled MOCK and must never appear in the paper, the video or at the fair.

## Declaring AI-assisted engineering

Part of the engineer-side plumbing in this repository (the pipeline,
crosswalk, seal tooling and demo tool) was drafted with an AI coding
assistant and then reviewed by the engineering team. Declare this on the
ISEF forms alongside the engineers' help. None of `model/` was produced
this way.
