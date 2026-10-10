"""Extractors: turn each raw source into a tidy long table.

Every extractor returns columns: state, district, year, variable, value,
source, plus any source-specific extras. District names are left as
published; src/hcm/crosswalk.py matches them to LGD codes.
"""
