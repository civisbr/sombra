"""Pontos de resfriamento: equipamentos públicos que cobrem setores prioritários a pé."""

import numpy as np

from sombra.geo import haversine_m


def rank_cooling_points(
    equipment: list[dict],
    sector_centroids: list[tuple[float, float]],
    priority: np.ndarray,
    population: np.ndarray,
    radius_m: float = 500.0,
    top_fraction: float = 0.25,
) -> list[dict]:
    """Ordena equipamentos pela população prioritária alcançável em ``radius_m``.

    ``equipment``: dicts com ``name``, ``kind``, ``lon``, ``lat``.
    Um setor é prioritário se está no quartil superior do índice.
    """
    ok = np.isfinite(priority)
    if not ok.any():
        return []
    cut = np.quantile(priority[ok], 1 - top_fraction)
    prio_idx = [i for i in np.where(ok & (priority >= cut))[0]]
    out = []
    for eq in equipment:
        covered = [
            int(i)
            for i in prio_idx
            if haversine_m(eq["lon"], eq["lat"], *sector_centroids[i]) <= radius_m
        ]
        pop = float(np.nansum(population[covered])) if covered else 0.0
        out.append({**eq, "sectors": covered, "population": int(pop), "radius_m": radius_m})
    out = [e for e in out if e["sectors"]]
    out.sort(key=lambda e: (-e["population"], e["name"]))
    return out
