"""Agregação zonal de um raster por polígonos (setores censitários)."""

import numpy as np
from rasterio import features
from rasterio.transform import Affine


def zonal_stats(
    array: np.ndarray,
    transform: Affine,
    geometries: list,
    percentile: float = 90.0,
) -> list[dict[str, float]]:
    """Média, percentil e contagem de pixels válidos por geometria.

    Um pixel pertence ao polígono se o centro dele cair dentro (``all_touched=False``).
    Polígonos sem pixel válido retornam NaN e ``n=0``.
    """
    results = []
    for geom in geometries:
        mask = features.geometry_mask(
            [geom], out_shape=array.shape, transform=transform, invert=True, all_touched=False
        )
        values = array[mask]
        values = values[np.isfinite(values)]
        if values.size == 0:
            results.append({"mean": np.nan, "p": np.nan, "n": 0})
        else:
            results.append(
                {
                    "mean": float(values.mean()),
                    "p": float(np.percentile(values, percentile)),
                    "n": int(values.size),
                }
            )
    return results
