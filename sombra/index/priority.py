"""Índice de prioridade = exposição × sensibilidade × baixa capacidade de adaptação.

Cada componente é a média ponderada (pesos explícitos) de indicadores em percentil (0–1).
O índice é a média geométrica dos três componentes, reescalada para 0–100.
"""

from dataclasses import dataclass, field

import numpy as np

from sombra.vulnerability.indicators import percentile_rank

# direção: +1 aumenta a prioridade; -1 reduz (valor alto = mais capacidade de adaptação)
COMPONENTS: dict[str, dict[str, int]] = {
    "exposure": {"lst_anomaly": +1},
    "sensitivity": {"pct_60plus": +1, "pct_0_4": +1, "persons_per_household": +1},
    "low_adaptation": {"income": -1, "pct_black_brown": +1, "ndvi": -1, "dist_ubs_m": +1},
}

COMPONENT_WEIGHTS_EQUAL: dict[str, dict[str, float]] = {
    comp: {ind: 1.0 for ind in inds} for comp, inds in COMPONENTS.items()
}


@dataclass(frozen=True)
class IndexResult:
    exposure: np.ndarray
    sensitivity: np.ndarray
    low_adaptation: np.ndarray
    priority: np.ndarray
    missing: list[list[str]] = field(default_factory=list)


def _component(
    table: dict[str, np.ndarray], spec: dict[str, int], weights: dict[str, float], n: int
) -> tuple[np.ndarray, list[list[str]]]:
    num = np.zeros(n)
    den = np.zeros(n)
    missing: list[list[str]] = [[] for _ in range(n)]
    for ind, direction in spec.items():
        w = weights.get(ind, 0.0)
        if w == 0:
            continue
        pr = percentile_rank(table[ind])
        if direction < 0:
            pr = 1.0 - pr
        ok = np.isfinite(pr)
        num += np.where(ok, w * pr, 0.0)
        den += np.where(ok, w, 0.0)
        for i in np.where(~ok)[0]:
            missing[i].append(ind)
    with np.errstate(invalid="ignore", divide="ignore"):
        comp = np.where(den > 0, num / den, np.nan)
    return comp, missing


def compute_priority(
    table: dict[str, np.ndarray],
    weights: dict[str, dict[str, float]] | None = None,
    component_weights: dict[str, float] | None = None,
) -> IndexResult:
    """Calcula o índice. ``table`` mapeia indicador → vetor por setor (mesma ordem)."""
    weights = weights or COMPONENT_WEIGHTS_EQUAL
    component_weights = component_weights or {c: 1.0 for c in COMPONENTS}
    n = len(next(iter(table.values())))
    comps: dict[str, np.ndarray] = {}
    missing: list[list[str]] = [[] for _ in range(n)]
    for name, spec in COMPONENTS.items():
        comps[name], miss = _component(table, spec, weights.get(name, {}), n)
        for i, m in enumerate(miss):
            missing[i].extend(m)

    # Média geométrica ponderada; epsilon evita zerar o índice por um único componente mínimo.
    eps = 1e-3
    total_w = sum(component_weights.values())
    log_sum = np.zeros(n)
    for name, c in comps.items():
        log_sum += component_weights[name] * np.log(np.clip(c, eps, 1.0))
    priority = np.exp(log_sum / total_w) * 100.0
    any_nan = np.zeros(n, dtype=bool)
    for c in comps.values():
        any_nan |= ~np.isfinite(c)
    priority = np.where(any_nan, np.nan, priority)
    return IndexResult(
        exposure=comps["exposure"],
        sensitivity=comps["sensitivity"],
        low_adaptation=comps["low_adaptation"],
        priority=priority,
        missing=missing,
    )


def priority_class(priority: np.ndarray) -> np.ndarray:
    """Classes por quartil da cidade: 0 menor, 1 moderada, 2 alta, 3 muito alta; -1 sem dado."""
    out = np.full(priority.shape, -1, dtype=int)
    ok = np.isfinite(priority)
    if ok.sum() == 0:
        return out
    q = np.percentile(priority[ok], [25, 50, 75])
    out[ok] = np.searchsorted(q, priority[ok], side="right")
    return out
