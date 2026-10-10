# Run from the project folder. `make all` rebuilds everything from data/raw.
PY ?= python3
export PYTHONPATH := src
HCM = $(PY) -m hcm

.PHONY: setup download extract crosswalk panel mock demo serve validate test all archive seal-status

setup:            ## create .venv and install everything
	$(PY) -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -r requirements.txt

download:         ## fetch URL-backed sources; lists the manual ones
	$(HCM) download

extract:          ## raw -> data/interim (add RASTERS=1 for CHIRPS/VIIRS zonal stats)
	$(HCM) extract $(if $(RASTERS),--rasters,)

crosswalk:        ## harmonised district units
	$(HCM) crosswalk

panel: crosswalk  ## master district panel 2015-2024
	$(HCM) panel

mock:             ## MOCK model outputs for building the demo
	$(PY) scripts/make_mock_outputs.py

validate:         ## check model outputs against the contract
	$(HCM) validate-outputs

demo: validate    ## offline demo -> dist/odisha_demo.html
	$(HCM) demo

serve:            ## live demo for development
	streamlit run demo/app.py

seal-status:
	$(HCM) seal-status

test:
	$(PY) -m pytest -q

all: download extract panel

archive:          ## zip code + processed data with checksums for Zenodo
	$(PY) scripts/make_archive.py
