"""Validação física: LST média vs. temperatura do ar nas estações INMET."""

import numpy as np
from scipy import stats


def correlate(lst_c: np.ndarray, air_c: np.ndarray) -> dict[str, float]:
    lst_c, air_c = np.asarray(lst_c, float), np.asarray(air_c, float)
    ok = np.isfinite(lst_c) & np.isfinite(air_c)
    n = int(ok.sum())
    if n < 3:
        return {"n": n, "pearson": float("nan"), "spearman": float("nan")}
    return {
        "n": n,
        "pearson": float(stats.pearsonr(lst_c[ok], air_c[ok]).statistic),
        "spearman": float(stats.spearmanr(lst_c[ok], air_c[ok]).statistic),
    }
