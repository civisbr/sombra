import json

import pytest

from sombra.cli import main
from sombra.config import load_city, validate_ibge
from sombra.ingest.landsat import summer_windows


def test_validate_ibge():
    assert validate_ibge("3552205") == "3552205"
    for bad in ("355220", "abcdefg", "35522050"):
        with pytest.raises(ValueError):
            validate_ibge(bad)


def test_load_pilot_city():
    city = load_city("3552205")
    assert city.name == "Sorocaba" and city.season_months == (12, 1, 2, 3)
    assert city.bbox[0] < city.bbox[2] and city.bbox[1] < city.bbox[3]


def test_summer_windows_span_year_boundary():
    city = load_city("3552205")
    w = summer_windows(city, recent_only=True)
    assert len(w) == city.recent_summers
    assert w[-1] == f"{city.last_year - 1}-12-01/{city.last_year}-03-31"


def test_end_to_end_demo(tmp_path, monkeypatch):
    import sombra.publish.export_web as ew

    monkeypatch.setattr(ew, "WEB_DATA", tmp_path)
    monkeypatch.setattr(ew, "_write_geoparquet", lambda out: None)
    assert main(["run", "--city", "3552205", "--demo"]) == 0
    out = tmp_path / "3552205"
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["demo"] is True and meta["reference_date"] == "ilustrativo"
    gj = json.loads((out / "sectors.geojson").read_text(encoding="utf-8"))
    assert len(gj["features"]) == meta["n_sectors"]
    assert all("priority" in f["properties"] for f in gj["features"])


def test_end_to_end_is_deterministic(tmp_path, monkeypatch):
    import sombra.publish.export_web as ew

    monkeypatch.setattr(ew, "_write_geoparquet", lambda out: None)
    outs = []
    for name in ("a", "b"):
        monkeypatch.setattr(ew, "WEB_DATA", tmp_path / name)
        main(["run", "--city", "3552205", "--demo"])
        outs.append((tmp_path / name / "3552205" / "sectors.csv").read_bytes())
    assert outs[0] == outs[1]


def test_real_run_fails_clearly_when_not_implemented(capsys):
    assert main(["run", "--city", "3552205"]) == 1
    assert "ibge" in capsys.readouterr().err


def test_validate_ibge_rejects_unicode_digits():
    with pytest.raises(ValueError):
        validate_ibge("١٢٣٤٥٦٧")
