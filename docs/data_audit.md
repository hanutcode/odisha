# Data audit — go/no-go

Filled 10 Oct 2026 from what is actually in the project (engineering, AI-assisted; see INTEGRITY.md).
The go/no-go decision in the last section is the team's, not engineering's.

| Data | Check | Result | Checked by | Date |
|---|---|---|---|---|
| NFHS-6 district fact sheets | Out, with "women 20–24 married before 18"? | **Not yet.** The sealed bundle holds one file: the NFHS-6 *state* fact sheet/compendium for Odisha (`NFHS-6_StateFact_Odisha__Odisha_Compendium.pdf`, sealed 9 Oct 07:16 UTC, witnessed by Sweksha). No district sheets. Seal removed 10 Oct: the file is now in `data/raw/nfhs/round6/` (see INTEGRITY.md). See Decision. | Engineering | 10 Oct |
| NFHS-4 / NFHS-5 district fact sheets | All Odisha districts? | Yes, 30 + 30 PDFs. `cm_20_24_before18` and `teen_pregnancy_15_19` for all 30 districts in 2016 and 2020. `men_25_29_before21` only 7 districts in NFHS-4 (the rest are not reported in the sheets) and none in NFHS-5. | Engineering | 10 Oct |
| NFHS-5 unit-level (DHS) | Access requested? | Not in the project. | — | — |
| NCRB PCMA cases | District tables available? Which years? | Yes, 2014–2022, all India (NCRB *Crime in India* district tables). 2023 not published yet. Odisha totals: 2014 0, 2015 1, 2016 15, 2017 17, 2018 22, 2019 22, 2020 24, 2021 64, 2022 46. 724 rows from railway/CID/cyber/STF units are left out (no district territory). Fixed: the 2017 workbook heads Chhattisgarh as "Bihar" (erratum in `scripts/ncrb_tidy.py`). | Engineering | 10 Oct |
| UDISE+ girls' enrolment, Grades 8–10 | Downloaded 2015–2024? | Yes for Odisha, school years 2015-16 to 2024-25 (all 30 districts). Not collected for other states. | Engineering | 7 Oct |
| CHIRPS rainfall | URL works? | Yes. Annual CHIRPS v2.0, 2000–2024, India window, in `data/raw/chirps/`. `rain_mm` and `rain_shock_z` (25-year baseline) for 612 of 613 units, every panel year. Odisha mean: 2015 1,315 mm (shock −1.05), 2020 1,667 mm (+0.71). | Engineering | 9 Oct |
| LGD district export | Exported, with Census 2011 codes? | Yes: 785 districts with Census 2011 codes, from a public concordance of the LGD export (github.com/vijayshree-jayaraman/District-mapping-2001-2011-with-LGD-codes, Aug 2025). 145 post-2011 districts linked to parents in `district_splits.csv`; 22 have several parents, with unknown population shares (assumed equal, listed in `crosswalk_problems.csv`). 613 harmonised units. Odisha's 30 units are unchanged. | Engineering | 9 Oct |
| District name matching | Review queue clear? | Yes: 0 unmatched. 260 aliases added for NCRB police districts, commissionerates and spellings (`district_aliases.csv`). Approximations: Mumbai Commr. → Mumbai; Navi Mumbai and MBVV → Thane; Siliguri PC → Darjiling; Rachakonda → Ranga Reddy. Hanut's 20 spot checks are in `docs/crosswalk_spot_checks.csv` and are still unticked. | Engineering | 10 Oct |
| VIIRS night lights | Downloaded? | **No.** EOG needs a personal login. | — | — |
| SHRUG / Census 2011 | Downloaded? | **No.** There is no population or exposure column yet. | — | — |
| Odisha WCD reports | Public district reports / Assembly answers found? | **Not filled.** No district × year table found online. Leads: an Odisha Assembly reply (15 Feb 2025, Dy CM Pravati Parida, to Badri Narayan Patra) gives 8,159 child-marriage cases from 2019 to Feb 2025, highest in Nabarangpur (1,347), Ganjam (966) and Koraput (636) (Hindustan Times and PTI, Feb–Mar 2025). The full district table is in the Assembly paper, but the Assembly site's question search returned nothing. The state-level count of marriages prevented was 324 (2017), 411 (2018), 657 (2019) and 1,108 (2020) (Odisha WCD entry on SKOCH; 2020 figure from the CMO post of 5 Jul 2021, reported by NEXT IAS). This is state-level only, so it can't go in the district file as a count. | Engineering | 10 Oct |
| Police per capita, Childline 1098, CMPOs | Sources found? | **Not filled.** BPR&D *Data on Police Organisations* is state-level, so it would only add a year trend within Odisha. District-level counts of Childline and CMPOs need WCD/DSWO records or an RTI request. | Engineering | 10 Oct |

## Decision

- **Go** if NFHS-6 has district-level child-marriage data **and** at least two reporting channels exist at district level.
- **No-go fallback:** run the out-of-time test one round earlier (fit on NFHS-4-era data and reports up to 2016, then predict NFHS-5). Set `training_cutoff_year: 2016` in `config/sources.yaml` and treat NFHS-5 as the sealed round.

Facts for the decision (10 Oct): the sealed NFHS-6 file is state-level only. Two reporting channels exist at district level for Odisha: NCRB police cases and UDISE+ school drop-off. The third (Odisha WCD) is not filled.

Decision: ______  Time: ______  Recorded by: ______
