"""Análise de sensibilidade: o ranking dos setores prioritários resiste a pesos alternativos?"""

import numpy as np

from sombra.index.priority import COMPONENT_WEIGHTS_EQUAL, COMPONENTS, compute_priority


def top_fraction(values: np.ndarray, fraction: float = 0.10) -> np.ndarray:
    """Máscara booleana dos ``fraction`` maiores valores (ignora NaN)."""
    ok = np.isfinite(values)
    mask = np.zeros(values.shape, dtype=bool)
    k = max(1, int(round(ok.sum() * fraction)))
    idx = np.where(ok)[0]
    order = idx[np.argsort(-values[idx], kind="stable")][:k]
    mask[order] = True
    return mask


def overlap(a: np.ndarray, b: np.ndarray) -> float:
    """Fração de a que também está em b."""
    n = a.sum()
    return float((a & b).sum() / n) if n else float("nan")


def alternative_schemes() -> dict[str, dict]:
    """Esquemas de pesos alternativos, todos publicados no site."""
    schemes: dict[str, dict] = {}
    for comp in COMPONENTS:
        w = {"exposure": 1.0, "sensitivity": 1.0, "low_adaptation": 1.0}
        w[comp] = 2.0
        schemes[f"componente {comp} ×2"] = {"component_weights": w}
    for comp, inds in COMPONENTS.items():
        for ind in inds:
            if len(inds) == 1:
                continue
            weights = {c: dict(v) for c, v in COMPONENT_WEIGHTS_EQUAL.items()}
            weights[comp][ind] = 0.0
            schemes[f"sem {ind}"] = {"weights": weights}
    return schemes


def robustness(table: dict[str, np.ndarray], fraction: float = 0.10) -> dict:
    base = compute_priority(table).priority
    base_top = top_fraction(base, fraction)
    rows = {}
    for name, kwargs in alternative_schemes().items():
        alt = compute_priority(table, **kwargs).priority
        rows[name] = overlap(base_top, top_fraction(alt, fraction))
    return {
        "fraction": fraction,
        "overlaps": rows,
        "min_overlap": min(rows.values()) if rows else float("nan"),
        "mean_overlap": float(np.mean(list(rows.values()))) if rows else float("nan"),
    }
