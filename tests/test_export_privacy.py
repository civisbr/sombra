import json

import numpy as np
from shapely.geometry import box

from sombra.config import load_city
from sombra.pipeline import Result
from sombra.publish import export_web as ew

ALLOWED = {
    "id", "lst_anomaly_mean", "lst_anomaly_p90", "lst_pixels", "population", "pop_60plus",
    "pct_60plus", "pct_0_4", "income", "pct_black_brown", "persons_per_household", "ndvi",
    "dist_ubs_m", "exposure", "sensitivity", "low_adaptation", "priority", "priority_class",
    "priority_label",
}  # fmt: skip


def test_small_counts_suppressed_and_columns_allowlisted(tmp_path, monkeypatch):
    monkeypatch.setattr(ew, "_write_geoparquet", lambda out: None)
    cols = {k: np.array([1.0, 50.0]) for k in ALLOWED - {"id", "priority_label"}}
    cols["population"] = np.array([3.0, 500.0])
    cols["pop_60plus"] = np.array([2.0, 60.0])
    cols["priority_class"] = np.array([1, 2])
    res = Result(
        city=load_city("3552205"),
        sector_ids=["A", "B"],
        geoms=[box(0, 0, 1, 1), box(1, 0, 2, 1)],
        columns=cols,
        trees=[],
        cooling=[],
        active_search=[],
        robustness={"fraction": 0.1, "overlaps": {}, "min_overlap": 1.0, "mean_overlap": 1.0},
    )
    out = ew.export(res, demo=True, reference_date="ilustrativo", out_dir=tmp_path / "x")
    props = [f["properties"] for f in json.loads((out / "sectors.geojson").read_text())["features"]]
    assert props[0]["population"] is None and props[0]["pop_60plus"] is None
    assert props[1]["population"] == 500
    for p in props:
        assert set(p) == ALLOWED
