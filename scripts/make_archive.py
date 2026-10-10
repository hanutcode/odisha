"""Build the Zenodo archive: dist/code.zip and dist/processed_data.zip (with SHA256SUMS).

    python3 scripts/make_archive.py

code.zip holds every file git would track (it honours .gitignore, so no raw data, secrets,
password files, keys, databases or MOCK outputs). processed_data.zip holds the processed
panel plus the manual crosswalk inputs, the data audit and the seal history.
"""
import hashlib
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK = (".key", "sqlite3", "initial_passwords", "deploy-logins", "secret_key", "MOCK")


def main():
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    files = sorted(f for f in set(files) if not any(b in f for b in BLOCK) and (ROOT / f).is_file())
    (ROOT / "dist").mkdir(exist_ok=True)
    with zipfile.ZipFile(ROOT / "dist/code.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(ROOT / f, "iris-hidden-cm/" + f)
    proc = sorted(p for p in (ROOT / "data/processed").glob("*") if p.suffix in (".parquet", ".csv", ".duckdb"))
    sums = ROOT / "data/processed/SHA256SUMS"
    sums.write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in proc))
    extra = ["data/manual/lgd_districts.csv", "data/manual/district_splits.csv", "data/manual/district_aliases.csv",
             "data/raw/chirps/README.md", "docs/data_audit.md", "docs/seal_log.jsonl"]
    with zipfile.ZipFile(ROOT / "dist/processed_data.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in proc + [sums]:
            z.write(p, "processed/" + p.name)
        for f in extra:
            z.write(ROOT / f, f)
    for f in ("dist/code.zip", "dist/processed_data.zip"):
        b = (ROOT / f).read_bytes()
        print(f"{f}: {len(b)/1e6:.2f} MB  sha256 {hashlib.sha256(b).hexdigest()}")
    print(f"{len(files)} code files. Upload both zips to Zenodo with .zenodo.json.")


if __name__ == "__main__":
    main()
