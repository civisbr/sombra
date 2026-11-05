"""Busca ativa: setores com mais idosos em calor alto, para a atenção primária."""

import numpy as np


def active_search_sectors(
    pop_65plus: np.ndarray, exposure: np.ndarray, min_exposure_quantile: float = 0.5
) -> list[int]:
    ok = np.isfinite(pop_65plus) & np.isfinite(exposure)
    if not ok.any():
        return []
    cut = np.quantile(exposure[ok], min_exposure_quantile)
    idx = np.where(ok & (exposure >= cut) & (pop_65plus > 0))[0]
    return [int(i) for i in idx[np.argsort(-pop_65plus[idx], kind="stable")]]
