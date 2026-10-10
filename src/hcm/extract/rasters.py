"""District zonal statistics from rasters (CHIRPS rainfall, VIIRS night lights).

Rainfall shock = z-score of a district's annual rainfall against its own
2000-2024 (or available) mean, so negative values mean drought years.
"""

from __future__ import annotations

import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


def zonal_mean(raster_path: Path, districts: gpd.GeoDataFrame, id_col: str,
               nodata_below: float | None = None) -> pd.DataFrame:
    import rasterio
    from rasterio.mask import mask

    out = []
    with rasterio.open(raster_path) as src:
        g = districts.to_crs(src.crs) if districts.crs and src.crs else districts
        for _, row in g.iterrows():
            try:
                arr, _ = mask(src, [row.geometry], crop=True, filled=False)
            except ValueError:  # polygon outside raster extent
                out.append((row[id_col], np.nan))
                continue
            a = arr[0].astype("float64").filled(np.nan) if np.ma.isMaskedArray(arr) else arr[0].astype("float64")
            if src.nodata is not None:
                a[a == src.nodata] = np.nan
            if nodata_below is not None:
                a[a < nodata_below] = np.nan
            out.append((row[id_col], float(np.nanmean(a)) if np.isfinite(a).any() else np.nan))
    return pd.DataFrame(out, columns=[id_col, "value"])


def yearly_zonal(folder: Path, pattern: str, districts: gpd.GeoDataFrame, id_col: str,
                 variable: str, nodata_below: float | None = None) -> pd.DataFrame:
    """Run zonal_mean over every raster whose name contains a year, e.g. chirps-v2.0.2019.tif."""
    frames = []
    for f in sorted(Path(folder).glob(pattern)):
        m = re.search(r"(20\d{2})", f.name)
        if not m:
            continue
        df = zonal_mean(f, districts, id_col, nodata_below)
        df["year"] = int(m.group(1))
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=[id_col, "year", "variable", "value"])
    df = pd.concat(frames, ignore_index=True)
    df["variable"] = variable
    return df


def rainfall_shock(rain: pd.DataFrame, id_col: str) -> pd.DataFrame:
    g = rain.groupby(id_col)["value"]
    z = (rain["value"] - g.transform("mean")) / g.transform("std").replace(0, np.nan)
    out = rain[[id_col, "year"]].copy()
    out["variable"] = "rain_shock_z"
    out["value"] = z
    return out
