"""NDVI mediano de verão a partir do Sentinel-2 L2A (Planetary Computer)."""

from __future__ import annotations

import numpy as np

from sombra.config import City

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"
# SCL: 3 sombra de nuvem, 8/9 nuvem média/alta, 10 cirrus, 1 saturado, 0 sem dado, 11 neve
SCL_BAD = (0, 1, 3, 8, 9, 10, 11)


BOA_OFFSET_BASELINE = 4.0  # a partir da baseline 04.00 o L2A traz BOA_ADD_OFFSET = -1000


def reflectance(dn: np.ndarray, baseline: float) -> np.ndarray:
    """Refletância de superfície (0–1) a partir do DN do L2A, aplicando o offset da baseline."""
    dn = dn.astype("float64")
    if baseline >= BOA_OFFSET_BASELINE:
        dn = dn - 1000.0
    return np.clip(dn / 10000.0, 0.0, None)


def ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDVI a partir de refletâncias (já com offset aplicado)."""
    red, nir = red.astype("float64"), nir.astype("float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (nir - red) / (nir + red)
    return np.where((nir + red) > 0, out, np.nan)


def scl_valid(scl: np.ndarray) -> np.ndarray:
    return ~np.isin(scl, SCL_BAD)


def summer_windows(city: City) -> list[str]:
    first = city.last_year - city.recent_summers + 1
    return [f"{y - 1}-12-01/{y}-03-31" for y in range(first, city.last_year + 1)]


def pick_scenes(items: list, per_summer: int) -> list:
    """As ``per_summer`` cenas menos nubladas de cada verão (determinístico), em ordem de data."""
    by_summer: dict[int, list] = {}
    for it in items:
        d = it.datetime
        by_summer.setdefault(d.year + (1 if d.month == 12 else 0), []).append(it)
    chosen = []
    for _, group in sorted(by_summer.items()):
        group.sort(key=lambda i: (i.properties.get("eo:cloud_cover", 100), i.datetime, i.id))
        chosen.extend(group[:per_summer])
    return sorted(chosen, key=lambda i: (i.datetime, i.id))


def median_ndvi(
    city: City, resolution_deg: float = 0.0003, max_cloud: int = 30, per_summer: int = 8
):
    """Mediana do NDVI nos verões recentes. Retorna (array 2D, transform, datas usadas)."""
    import odc.stac
    import planetary_computer
    from pystac_client import Client

    catalog = Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    items = []
    for window in summer_windows(city):
        items.extend(
            catalog.search(
                collections=[COLLECTION],
                bbox=city.bbox,
                datetime=window,
                query={"eo:cloud_cover": {"lt": max_cloud}},
            ).items()
        )
    if not items:
        raise RuntimeError("nenhuma cena Sentinel-2 encontrada")
    items = pick_scenes(items, per_summer)
    baseline_by_day: dict[str, float] = {}
    for it in items:
        day = it.datetime.date().isoformat()
        baseline_by_day[day] = max(
            baseline_by_day.get(day, 0.0), float(it.properties.get("s2:processing_baseline", 0))
        )
    ds = odc.stac.load(
        items,
        bands=["B04", "B08", "SCL"],
        bbox=city.bbox,
        crs="EPSG:4326",
        resolution=resolution_deg,
        chunks={},
        groupby="solar_day",
        resampling={"SCL": "nearest", "*": "average"},
    ).compute()
    layers, dates = [], []
    for t in range(ds.sizes["time"]):
        day = str(ds["time"].values[t])[:10]
        baseline = baseline_by_day.get(day, max(baseline_by_day.values()))
        v = ndvi(
            reflectance(ds["B04"].isel(time=t).values, baseline),
            reflectance(ds["B08"].isel(time=t).values, baseline),
        )
        v = np.where(scl_valid(ds["SCL"].isel(time=t).values), v, np.nan)
        if np.isfinite(v).mean() < 0.3:
            continue
        layers.append(v)
        dates.append(day)
    if not layers:
        raise RuntimeError("nenhuma cena Sentinel-2 válida")
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        med = np.nanmedian(np.stack(layers), axis=0)
    return med, ds.odc.geobox.affine, dates
