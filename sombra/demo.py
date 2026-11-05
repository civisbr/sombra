"""Cidade sintética para rodar o pipeline ponta a ponta sem rede.

Todos os valores são ILUSTRATIVOS e não representam nenhum bairro real. A geometria dos setores
é um diagrama de Voronoi aleatório (semente fixa) ao redor do centro de ``City.bbox``.
"""

from dataclasses import dataclass

import numpy as np
from rasterio.transform import from_origin
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, box

from sombra.config import City

SEED = 20260101
PIXEL_DEG = 0.0003


@dataclass
class DemoCity:
    sector_ids: list[str]
    geoms: list[Polygon]
    census: dict[str, np.ndarray]
    population: np.ndarray
    lst_anomaly: np.ndarray
    transform: object
    equipment: list[dict]


def _voronoi_cells(points: np.ndarray, bounds: Polygon) -> list[Polygon]:
    far = np.array([[-1e3, -1e3], [-1e3, 1e3], [1e3, -1e3], [1e3, 1e3]])
    vor = Voronoi(np.vstack([points, far]))
    cells = []
    for i in range(len(points)):
        region = vor.regions[vor.point_region[i]]
        poly = Polygon(vor.vertices[region]).intersection(bounds)
        cells.append(poly)
    return cells


def build_demo(city: City, n_sectors: int = 220) -> DemoCity:
    rng = np.random.default_rng(SEED)
    west, south, east, north = city.bbox
    cx, cy = (west + east) / 2, (south + north) / 2
    half_w, half_h = 0.07, 0.06
    area = box(cx - half_w, cy - half_h, cx + half_w, cy + half_h)

    pts = np.column_stack(
        [
            rng.uniform(cx - half_w, cx + half_w, n_sectors),
            rng.uniform(cy - half_h, cy + half_h, n_sectors),
        ]
    )
    cells = _voronoi_cells(pts, area)
    geoms = [c for c in cells if c.geom_type == "Polygon" and c.area > 0]

    w = int(2 * half_w / PIXEL_DEG)
    h = int(2 * half_h / PIXEL_DEG)
    transform = from_origin(cx - half_w, cy + half_h, PIXEL_DEG, PIXEL_DEG)
    xs = cx - half_w + (np.arange(w) + 0.5) * PIXEL_DEG
    ys = cy + half_h - (np.arange(h) + 0.5) * PIXEL_DEG
    gx, gy = np.meshgrid(xs, ys)

    def field(x, y):
        core = np.exp(-(((x - cx + 0.01) / 0.035) ** 2 + ((y - cy) / 0.03) ** 2))
        industrial = np.exp(-(((x - cx - 0.04) / 0.02) ** 2 + ((y - cy + 0.035) / 0.015) ** 2))
        park = np.exp(-(((x - cx + 0.045) / 0.015) ** 2 + ((y - cy - 0.03) / 0.015) ** 2))
        river = np.exp(-((((y - cy + 0.012 * np.sin((x - cx) * 60)) - 0.005) / 0.003) ** 2))
        return core, industrial, park, river

    core, industrial, park, river = field(gx, gy)
    lst = 3.5 * core + 4.0 * industrial - 4.5 * park - 3.0 * river
    lst += rng.normal(0, 0.5, lst.shape)

    cx_s = np.array([g.centroid.x for g in geoms])
    cy_s = np.array([g.centroid.y for g in geoms])
    s_core, s_ind, s_park, s_river = field(cx_s, cy_s)
    n = len(geoms)
    density = np.clip(
        0.2 + 0.8 * s_core + 0.3 * s_ind - 0.4 * s_park + rng.normal(0, 0.12, n), 0, 1
    )
    poverty = np.clip(0.35 * (1 - s_core) + 0.4 * s_ind + rng.normal(0, 0.2, n) + 0.1, 0, 1)
    # Exceções reais: alguns setores pobres e verdes
    green_poor = rng.random(n) < 0.06
    ndvi = np.clip(0.75 - 0.6 * density + 0.5 * s_park + rng.normal(0, 0.06, n), 0.05, 0.9)
    ndvi = np.where(green_poor, np.clip(ndvi + 0.3, 0, 0.9), ndvi)

    areas_km2 = np.array([g.area * (111.0 * 102.0) for g in geoms])
    population = np.round(areas_km2 * (1500 + 9000 * density) + 30).astype(float)
    pct65 = np.clip(6 + 10 * (1 - poverty) * (1 - 0.5 * density) + rng.normal(0, 2, n), 2, 30)
    pct04 = np.clip(4 + 5 * poverty + rng.normal(0, 1, n), 1, 14)
    income = np.clip(900 + 4200 * (1 - poverty) + rng.normal(0, 350, n), 600, None)
    black_brown = np.clip(25 + 45 * poverty + rng.normal(0, 8, n), 5, 95)
    persons = np.clip(2.4 + 1.1 * poverty + rng.normal(0, 0.2, n), 1.8, 4.5)
    dist_ubs = np.clip(250 + 1500 * (1 - density) + 600 * poverty + rng.normal(0, 150, n), 80, None)

    census = {
        "pct_65plus": pct65,
        "pct_0_4": pct04,
        "income": income,
        "pct_black_brown": black_brown,
        "persons_per_household": persons,
        "ndvi": ndvi,
        "dist_ubs_m": dist_ubs,
    }

    kinds = [("ubs", "UBS", 14), ("escola", "Escola", 40), ("biblioteca", "Biblioteca", 4)]
    equipment = []
    for kind, label, count in kinds:
        for k in range(count):
            equipment.append(
                {
                    "name": f"{label} demonstrativa {k + 1}",
                    "kind": kind,
                    "lon": float(rng.uniform(cx - half_w, cx + half_w)),
                    "lat": float(rng.uniform(cy - half_h, cy + half_h)),
                }
            )
    return DemoCity(
        sector_ids=[f"DEMO{i + 1:04d}" for i in range(n)],
        geoms=geoms,
        census=census,
        population=population,
        lst_anomaly=lst,
        transform=transform,
        equipment=equipment,
    )
