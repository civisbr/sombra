"""Orquestra: LST por setor + indicadores → índice → ações → validação."""

from dataclasses import dataclass, field

import numpy as np

from sombra.actions.active_search import active_search_sectors
from sombra.actions.cooling_points import rank_cooling_points
from sombra.actions.trees import tree_candidates
from sombra.config import City
from sombra.heat.zonal import zonal_stats
from sombra.index.priority import compute_priority, priority_class
from sombra.index.sensitivity import robustness


@dataclass
class Result:
    city: City
    sector_ids: list[str]
    geoms: list
    columns: dict[str, np.ndarray]
    trees: list[int]
    cooling: list[dict]
    active_search: list[int]
    robustness: dict
    notes: dict = field(default_factory=dict)


def run(
    city: City,
    sector_ids: list[str],
    geoms: list,
    lst_anomaly: np.ndarray,
    transform,
    census: dict[str, np.ndarray],
    population: np.ndarray,
    equipment: list[dict],
) -> Result:
    zs = zonal_stats(lst_anomaly, transform, geoms)
    lst_mean = np.array([z["mean"] for z in zs])
    lst_p90 = np.array([z["p"] for z in zs])
    lst_n = np.array([z["n"] for z in zs])

    table = {"lst_anomaly": lst_mean, **census}
    res = compute_priority(table)
    cls = priority_class(res.priority)

    pct60 = census["pct_60plus"]
    pop60 = census.get("pop_60plus", np.round(population * pct60 / 100.0))

    centroids = [(g.centroid.x, g.centroid.y) for g in geoms]
    trees = tree_candidates(res.priority, res.exposure, census["ndvi"])
    cooling = rank_cooling_points(
        equipment, centroids, res.priority, population, radius_m=city.cooling_radius_m
    )
    active = active_search_sectors(pop60, res.exposure)

    columns = {
        "lst_anomaly_mean": lst_mean,
        "lst_anomaly_p90": lst_p90,
        "lst_pixels": lst_n,
        "population": population,
        "pop_60plus": pop60,
        **census,
        "exposure": res.exposure,
        "sensitivity": res.sensitivity,
        "low_adaptation": res.low_adaptation,
        "priority": res.priority,
        "priority_class": cls,
    }
    return Result(
        city=city,
        sector_ids=sector_ids,
        geoms=geoms,
        columns=columns,
        trees=trees,
        cooling=cooling,
        active_search=active,
        robustness=robustness(table),
    )
