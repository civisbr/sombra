import numpy as np
import pytest

from sombra.actions.active_search import active_search_sectors
from sombra.actions.cooling_points import rank_cooling_points
from sombra.actions.trees import tree_candidates
from sombra.index.priority import compute_priority, priority_class
from sombra.index.sensitivity import overlap, robustness, top_fraction
from sombra.validate.air_vs_lst import correlate
from sombra.vulnerability.indicators import percentile_rank, safe_pct


def make_table(n=100, seed=0):
    rng = np.random.default_rng(seed)
    return {
        "lst_anomaly": rng.normal(size=n),
        "pct_65plus": rng.random(n),
        "pct_0_4": rng.random(n),
        "persons_per_household": rng.random(n),
        "income": rng.random(n),
        "pct_black_brown": rng.random(n),
        "ndvi": rng.random(n),
        "dist_ubs_m": rng.random(n),
    }


def test_percentile_rank_ties_and_nan():
    r = percentile_rank(np.array([1.0, 2.0, 2.0, 3.0, np.nan]))
    assert r[0] == 0.0 and r[3] == 1.0 and r[1] == r[2] == pytest.approx(0.5)
    assert np.isnan(r[4])


def test_safe_pct():
    out = safe_pct(np.array([1, 2]), np.array([4, 0]))
    assert out[0] == 25.0 and np.isnan(out[1])


def test_priority_direction():
    t = make_table()
    base = compute_priority(t).priority
    t2 = dict(t)
    t2["ndvi"] = t["ndvi"].copy()
    # setor 0 com vegetação mínima: prioridade não pode cair
    t2["ndvi"][0] = -1.0
    assert compute_priority(t2).priority[0] >= base[0]


def test_priority_missing_is_reported_not_silent():
    t = make_table(20)
    t["ndvi"][3] = np.nan
    res = compute_priority(t)
    assert "ndvi" in res.missing[3]
    assert np.isfinite(res.priority[3])  # componente segue com os demais indicadores


def test_priority_class_quartiles():
    cls = priority_class(np.arange(100, dtype=float))
    assert set(cls) == {0, 1, 2, 3}
    assert priority_class(np.array([np.nan]))[0] == -1


def test_top_fraction_and_overlap():
    v = np.arange(100, dtype=float)
    top = top_fraction(v, 0.1)
    assert top.sum() == 10 and top[90:].all()
    assert overlap(top, top) == 1.0


def test_robustness_reports_all_schemes():
    out = robustness(make_table(200))
    assert len(out["overlaps"]) >= 6
    assert 0.0 <= out["min_overlap"] <= out["mean_overlap"] <= 1.0


def test_tree_candidates_filters():
    prio = np.array([90.0, 80.0, 70.0, 10.0])
    expo = np.array([2.0, 2.0, -1.0, 0.0])
    ndvi = np.array([0.1, 0.9, 0.1, 0.1])
    assert tree_candidates(prio, expo, ndvi, top_fraction=0.75) == [0]


def test_cooling_points_radius():
    prio = np.array([100.0, 100.0, 1.0, 1.0])
    pop = np.array([1000.0, 500.0, 300.0, 300.0])
    cents = [(-47.46, -23.50), (-47.461, -23.50), (-47.40, -23.50), (-47.41, -23.50)]
    eq = [
        {"name": "perto", "kind": "ubs", "lon": -47.4605, "lat": -23.50},
        {"name": "longe", "kind": "escola", "lon": -47.30, "lat": -23.50},
    ]
    out = rank_cooling_points(eq, cents, prio, pop, radius_m=500, top_fraction=0.5)
    assert [e["name"] for e in out] == ["perto"]
    assert out[0]["population"] == 1500


def test_active_search_orders_by_elderly():
    pop65 = np.array([10.0, 50.0, 30.0, 99.0])
    expo = np.array([3.0, 3.0, 3.0, 0.0])
    assert active_search_sectors(pop65, expo) == [1, 2, 0]


def test_correlate():
    x = np.arange(10.0)
    out = correlate(x, 2 * x + 1)
    assert out["pearson"] == pytest.approx(1.0) and out["n"] == 10
    assert np.isnan(correlate([1.0], [1.0])["pearson"])
