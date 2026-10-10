# IRIS data kit: NCRB, UDISE+, Odisha WCD

The government portals put every file behind a download form with a picture code (CAPTCHA),
so these files must be downloaded by a person. Each takes about a minute.
Put each file in the folder shown, named as shown (the year in the name is how the loader knows the year).

## 1. NCRB: crimes against children, district-wise  ->  iris-hidden-cm/data/raw/ncrb/

On each page: Download File -> Non Commercial -> Academia -> type the picture code -> Download.
Name, mobile and e-mail are optional.

| Year | Page | Save as |
|---|---|---|
| 2013 | https://www.data.gov.in/resource/district-wise-crimes-committed-against-children-during-2013 | ncrb_2013.csv |
| 2015 | https://www.data.gov.in/resource/district-area-wise-crimes-committed-against-children-during-2015 | ncrb_2015.csv |
| 2022 | https://www.data.gov.in/resource/district-wise-number-crime-against-children-during-2022 | ncrb_2022.csv |
| 2022 (SLL, backup) | https://www.data.gov.in/resource/district-wise-number-special-and-local-laws-sll-crimes-during-2022 | ncrb_sll_2022.csv (keep outside the folder unless the children table lacks a PCMA column) |

2016 to 2021: data.gov.in has no district table. Get them from NCRB "Crime in India" volumes,
https://www.ncrb.gov.in/crime-in-india.html -> year -> District-wise tables (Crime against Children),
saved as ncrb_2016.xlsx ... ncrb_2021.xlsx. The training cutoff is 2021, so 2016-2021 matter most.

The loader needs three columns: State/UT, District, and a column whose name contains
"Prohibition of Child Marriage" (or PCMA / Child Marriage Restraint).

## 2. UDISE+: girls' enrolment, Grades 8-10  ->  iris-hidden-cm/data/raw/udise/

https://udiseplus.gov.in -> Reports -> Enrolment -> "Enrolment by grade and gender" -> State: Odisha,
Level: District -> one year at a time, 2015-16 to 2021-22 (later years only if allowed by the cutoff).
Export Excel. Save as udise_2016.xlsx for 2015-16, udise_2017.xlsx for 2016-17, and so on
(use the year the school year ends).
Columns needed: State, District, and girls in Class 8, 9 and 10 (e.g. "Class 8 Girls").

## 3. Odisha WCD reports  ->  iris-hidden-cm/data/manual/

No downloadable table exists. Fill odisha_wcd/odisha_reports.csv by hand from:
- Odisha WCD & Mission Shakti annual reports: https://wcdodisha.gov.in (Publications / Annual Report)
- Odisha Assembly answers on child marriages prevented (district-wise)
- "Action Plan to End Child Marriage" (Odisha, 2019) progress notes
One row per district, year and variable; source_ref = document title + page.
detection_capacity.csv (police per 100k, Childline, CMPO count) is filled the same way.

## 4. After the files are in place

Workspace -> Data -> Run extract, then Build panel. Or in Terminal, from iris-hidden-cm:
  .venv/bin/python -m hcm.cli extract && .venv/bin/python -m hcm.cli panel

## NFHS-6

Not in this kit on purpose. NFHS-6 district sheets go only through the sealed upload on the
workspace Seal page (key first, then upload). Hanut must not open them before the freeze.
