"""Write MOCK model outputs so the demo tool can be built before the model exists.

These numbers are random. They are labelled MOCK everywhere (file, run id,
demo banner) and must never appear in the paper, the video or at the fair.
Hanut's real model overwrites outputs/district_estimates.csv and
outputs/reason_codes.csv using the contract in src/hcm/contract.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hcm import paths  # noqa: E402


def main(seed: int = 7) -> None:
    rng = np.random.default_rng(seed)
    gj = json.loads((paths.GEO / "odisha_districts_2011.geojson").read_text(encoding="utf-8"))
    rows = []
    for f in gj["features"]:
        p = f["properties"]
        rate = float(np.clip(rng.beta(4, 14), 0.04, 0.45))
        det = float(np.clip(rng.beta(2, 30), 0.005, 0.2))
        width = rate * rng.uniform(0.25, 0.45)
        rows.append({
            "census2011_code": int(p["dt_code"]), "district": p["district"],
            "est_rate": round(rate, 4), "est_lo": round(max(rate - width, 0), 4),
            "est_hi": round(min(rate + width, 1), 4),
            "recorded_cases": int(rng.poisson(rate * det * 4000)),
            "detection_prob": round(det, 4),
        })
    df = pd.DataFrame(rows)
    # flag the 8 districts with the largest gap between estimated risk and detection
    gap = df["est_rate"].rank(pct=True) - df["detection_prob"].rank(pct=True)
    top = gap.nlargest(8).index
    df["flag"] = False
    df.loc[top, "flag"] = True
    codes = ["MOCK_LOW_DETECTION", "MOCK_SCHOOL_DROPOUT", "MOCK_RAIN_SHOCK"]
    df["reason_code"] = ""
    df.loc[top, "reason_code"] = [codes[i % 3] for i in range(len(top))]
    df["model_run_id"] = "MOCK-not-real-data"
    paths.OUTPUTS.mkdir(exist_ok=True)
    df.to_csv(paths.OUTPUTS / "district_estimates.csv", index=False)

    # Placeholder wording only. Hanut writes the real reason codes; the Odia
    # speaker checks them (odia_checked stays False until then).
    pd.DataFrame([
        {"reason_code": "MOCK_LOW_DETECTION",
         "text_en": "[MOCK] Estimated risk is high but very few cases are recorded.",
         "text_hi": "[MOCK] अनुमानित जोखिम अधिक है, पर बहुत कम मामले दर्ज होते हैं।",
         "text_or": "[MOCK] ଆନୁମାନିକ ବିପଦ ଅଧିକ, କିନ୍ତୁ ବହୁତ କମ୍ ମାମଲା ଲିପିବଦ୍ଧ ହୁଏ।",
         "odia_checked": False},
        {"reason_code": "MOCK_SCHOOL_DROPOUT",
         "text_en": "[MOCK] Many girls leave school between Grades 8 and 10.",
         "text_hi": "[MOCK] कक्षा 8 से 10 के बीच कई लड़कियाँ स्कूल छोड़ देती हैं।",
         "text_or": "[MOCK] ଅଷ୍ଟମରୁ ଦଶମ ଶ୍ରେଣୀ ମଧ୍ୟରେ ଅନେକ ଝିଅ ସ୍କୁଲ ଛାଡ଼ନ୍ତି।",
         "odia_checked": False},
        {"reason_code": "MOCK_RAIN_SHOCK",
         "text_en": "[MOCK] Recent drought years, which are linked to more early marriages.",
         "text_hi": "[MOCK] हाल के सूखे वर्ष, जिनका संबंध अधिक बाल विवाह से है।",
         "text_or": "[MOCK] ସାମ୍ପ୍ରତିକ ମରୁଡ଼ି ବର୍ଷ, ଯାହା ଅଧିକ ବାଲ୍ୟ ବିବାହ ସହ ଜଡ଼ିତ।",
         "odia_checked": False},
    ]).to_csv(paths.OUTPUTS / "reason_codes.csv", index=False)
    print(f"Wrote MOCK outputs for {len(df)} districts to {paths.OUTPUTS}")


if __name__ == "__main__":
    main()
