"""Lista de arborização: calor alto + pouca vegetação + vulnerabilidade alta."""

import numpy as np


def tree_candidates(
    priority: np.ndarray,
    exposure: np.ndarray,
    ndvi: np.ndarray,
    available_area_m2: np.ndarray | None = None,
    top_fraction: float = 0.25,
) -> list[int]:
    """Índices dos setores prioritários, do mais ao menos prioritário.

    Critérios: prioridade no quartil superior, exposição acima da mediana e NDVI abaixo da mediana.
    Se ``available_area_m2`` (calçada/praça livre, OSM) for dado, exige área > 0.
    """
    ok = np.isfinite(priority) & np.isfinite(exposure) & np.isfinite(ndvi)
    if not ok.any():
        return []
    cut = np.quantile(priority[ok], 1 - top_fraction)
    sel = (
        ok & (priority >= cut) & (exposure >= np.nanmedian(exposure)) & (ndvi <= np.nanmedian(ndvi))
    )
    if available_area_m2 is not None:
        sel &= np.nan_to_num(available_area_m2, nan=0.0) > 0
    idx = np.where(sel)[0]
    return [int(i) for i in idx[np.argsort(-priority[idx], kind="stable")]]
