"""Confere o que está versionado em web/data (e que o deploy publica)."""

import csv
import json
from pathlib import Path

import pytest

from sombra.publish.export_web import MIN_COUNT

DATA = Path(__file__).resolve().parent.parent / "web" / "data"
ALLOWED = {
    "id", "lst_anomaly_mean", "lst_anomaly_p90", "lst_pixels", "population", "pop_60plus",
    "pct_60plus", "pct_0_4", "income", "pct_black_brown", "persons_per_household", "ndvi",
    "dist_ubs_m", "exposure", "sensitivity", "low_adaptation", "priority", "priority_class",
    "priority_label",
}  # fmt: skip
CITIES = sorted(p.parent for p in DATA.glob("*/meta.json"))


@pytest.mark.skipif(not CITIES, reason="sem dados publicados em web/data")
@pytest.mark.parametrize("city", CITIES, ids=lambda p: p.name)
def test_published_city(city):
    meta = json.loads((city / "meta.json").read_text(encoding="utf-8"))
    assert meta["demo"] is False and meta["code_version"] != ""
    with (city / "sectors.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and set(rows[0]) == ALLOWED
    for r in rows:
        for col in ("population", "pop_60plus"):
            if r[col] != "":
                assert float(r[col]) >= MIN_COUNT, f"{r['id']} {col} abaixo do mínimo"
        pop = float(r["population"]) if r["population"] != "" else 0.0
        for col in ("pct_60plus", "pct_0_4", "pct_black_brown"):
            if r[col] != "":
                assert pop * float(r[col]) / 100.0 >= MIN_COUNT, (
                    f"{r['id']}: {col} recalcula contagem <5"
                )
    gj = json.loads((city / "sectors.geojson").read_text(encoding="utf-8"))
    assert len(gj["features"]) == len(rows) == meta["n_sectors"]
