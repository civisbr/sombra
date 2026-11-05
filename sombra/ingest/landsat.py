"""Cenas Landsat 8/9 Collection 2 Level-2 de verão via STAC do Planetary Computer.

Requer o extra ``ingest`` (``uv sync --extra ingest``). Acesso à rede.
"""

from __future__ import annotations

import numpy as np

from sombra.config import City
from sombra.heat.lst import (
    compose_median,
    dn_to_kelvin,
    kelvin_to_celsius,
    mask_scene,
    qa_pixel_valid,
    scene_anomaly,
)

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "landsat-c2-l2"


def summer_windows(city: City, recent_only: bool = False) -> list[str]:
    """Intervalos de data (dez–mar) que cobrem os verões do período configurado."""
    first = city.last_year - city.recent_summers + 1 if recent_only else city.first_year
    windows = []
    for year in range(first, city.last_year + 1):
        windows.append(f"{year - 1}-12-01/{year}-03-31")
    return windows


def search_items(city: City, recent_only: bool = False):
    import planetary_computer
    from pystac_client import Client

    catalog = Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
    items = []
    for window in summer_windows(city, recent_only):
        search = catalog.search(
            collections=[COLLECTION],
            bbox=city.bbox,
            datetime=window,
            query={
                "eo:cloud_cover": {"lt": city.max_cloud_cover},
                "platform": {"in": ["landsat-8", "landsat-9"]},
            },
        )
        items.extend(search.items())
    return items


def composite_anomaly(
    city: City,
    recent_only: bool = False,
    resolution_deg: float = 0.0003,
    urban_mask_fn=None,
):
    """Mediana das anomalias de LST (°C) por pixel. Retorna (array 2D, transform affine).

    ``urban_mask_fn(shape, transform) -> bool[H, W]`` define a área urbana usada como referência
    da mediana de cada cena (PROJECT.md 4.1.3). Sem ela, a referência é o bbox inteiro.
    """
    import odc.stac

    items = search_items(city, recent_only)
    if not items:
        raise RuntimeError("nenhuma cena Landsat encontrada para o período e a área")
    ds = odc.stac.load(
        items,
        bands=["lwir11", "qa_pixel"],
        bbox=city.bbox,
        crs="EPSG:4326",
        resolution=resolution_deg,
        chunks={},
        groupby="solar_day",
    ).compute()
    transform = ds.odc.geobox.affine
    urban = urban_mask_fn(ds["lwir11"].shape[1:], transform) if urban_mask_fn else None
    anomalies = []
    for t in range(ds.sizes["time"]):
        dn = ds["lwir11"].isel(time=t).values
        qa = ds["qa_pixel"].isel(time=t).values
        celsius = kelvin_to_celsius(dn_to_kelvin(dn))
        masked = mask_scene(celsius, qa_pixel_valid(qa))
        probe = masked if urban is None else np.where(urban, masked, np.nan)
        n_ref = urban.sum() if urban is not None else masked.size
        if np.isfinite(probe).sum() / max(n_ref, 1) < 0.5:
            continue
        anomalies.append(scene_anomaly(masked, urban))
    return compose_median(anomalies, min_obs=3), transform
