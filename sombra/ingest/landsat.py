"""Cenas Landsat 8/9 Collection 2 Level-2 de verão via STAC do Planetary Computer.

Requer o extra ``ingest`` (``uv sync --extra ingest``). Acesso à rede.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
from rasterio import features
from rasterio.transform import Affine

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


@dataclass
class LstComposite:
    anomaly: np.ndarray
    transform: Affine
    scenes: list[str]
    reference: str


def urban_mask_from(geoms: list):
    """Máscara urbana (pixels cobertos pelos setores urbanos) para referência da mediana da cena."""

    def make(shape, transform):
        return features.geometry_mask(geoms, out_shape=shape, transform=transform, invert=True)

    return make


def composite_anomaly(
    city: City,
    recent_only: bool = False,
    resolution_deg: float = 0.0003,
    urban_mask_fn=None,
    max_scenes: int | None = None,
    min_valid_fraction: float = 0.5,
    min_obs: int = 3,
) -> LstComposite:
    """Mediana das anomalias de LST (°C) por pixel (PROJECT.md 4.1).

    ``urban_mask_fn(shape, transform) -> bool[H, W]`` define a área urbana usada como referência
    da mediana de cada cena. Sem ela, a referência é o bbox inteiro.
    """
    import odc.stac

    items = search_items(city, recent_only)
    if not items:
        raise RuntimeError("nenhuma cena Landsat encontrada para o período e a área")
    items.sort(key=lambda i: i.datetime)
    if max_scenes:
        items = items[:max_scenes]
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
    anomalies, used = [], []
    for t in range(ds.sizes["time"]):
        dn = ds["lwir11"].isel(time=t).values
        qa = ds["qa_pixel"].isel(time=t).values
        masked = mask_scene(kelvin_to_celsius(dn_to_kelvin(dn)), qa_pixel_valid(qa))
        ref = masked if urban is None else np.where(urban, masked, np.nan)
        n_ref = urban.sum() if urban is not None else masked.size
        if np.isfinite(ref).sum() / max(n_ref, 1) < min_valid_fraction:
            continue
        anomalies.append(scene_anomaly(masked, urban))
        used.append(str(ds["time"].values[t])[:10])
    if not anomalies:
        raise RuntimeError("nenhuma cena com cobertura válida suficiente")
    comp = compose_median(anomalies, min_obs=min(min_obs, len(anomalies)))
    return LstComposite(comp, transform, used, "Landsat 8/9 C2 L2 ST_B10 (NASA/USGS)")


def cache_params(city: City, kind: str, period: str = "recent") -> str:
    """Identifica os parâmetros que definem um cache; mudou algum, o cache é recusado."""
    return json.dumps(
        {
            "kind": kind,
            "v": 2,
            "bbox": list(city.bbox),
            "years": [city.first_year, city.last_year, city.recent_summers],
            "cloud": city.max_cloud_cover,
            "period": period,
        },
        sort_keys=True,
    )


def check_params(stored: str, expected: str, path) -> None:
    if stored != expected:
        raise RuntimeError(f"cache {path} foi gerado com outros parâmetros; recalcule")


def save_composite(comp: LstComposite, path, params: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        params=np.array(params),
        anomaly=comp.anomaly.astype("float32"),
        transform=np.array(comp.transform)[:6],
        scenes=np.array(comp.scenes),
    )


def load_composite(path, expected_params: str | None = None) -> LstComposite:
    z = np.load(path, allow_pickle=False)
    if expected_params is not None:
        check_params(str(z["params"]) if "params" in z else "", expected_params, path)
    return LstComposite(
        z["anomaly"].astype("float64"),
        Affine(*[float(x) for x in z["transform"]]),
        [str(x) for x in z["scenes"]],
        "Landsat 8/9 C2 L2 ST_B10 (NASA/USGS)",
    )
