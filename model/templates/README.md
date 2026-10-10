# Model output templates

Hanut's model fills these two files, then uploads them on the workspace's Odisha map page.

## district_estimates.csv (one row per Odisha district, 30 rows; codes and names are pre-filled)

| Column | Meaning | Example |
|---|---|---|
| census2011_code | District code (pre-filled, do not change) | 386 |
| district | District name (pre-filled) | Khordha |
| est_rate | Estimated share of women 20-24 married before 18, as a proportion 0-1 | 0.171 |
| est_lo, est_hi | Lower and upper end of the 90% credible interval, 0-1 | 0.12, 0.22 |
| recorded_cases | Officially recorded child-marriage cases, same period | 14 |
| detection_prob | Estimated chance a child marriage is recorded, 0-1 | 0.03 |
| flag | TRUE if the district is flagged for welfare outreach, else FALSE | TRUE |
| reason_code | Key from reason_codes.csv if flagged, else blank | LOW_DETECTION |
| model_run_id | Git commit hash of the model that produced the numbers | 3f2a9c1 |

## reason_codes.csv (one row per reason)

| Column | Meaning |
|---|---|
| reason_code | Short key used in district_estimates.csv |
| text_en / text_hi / text_or | One-sentence explanation in English, Hindi, Odia |
| odia_checked | TRUE once a native Odia speaker has checked text_or |

The three reason codes are examples; rename or add your own.
