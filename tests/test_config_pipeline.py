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


def test_real_run_fails_clearly_without_lst_cache(capsys, monkeypatch, tmp_path):
    import sombra.config as cfg

    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    monkeypatch.setattr("sombra.cli.lst_path", lambda city, period: tmp_path / "x.npz")
    assert main(["run", "--city", "3552205"]) == 1
    assert "sombra lst" in capsys.readouterr().err


def test_validate_ibge_rejects_unicode_digits():
    with pytest.raises(ValueError):
        validate_ibge("١٢٣٤٥٦٧")


def _fake_boundary(code="3552205", geom_type="Polygon"):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"codarea": code},
                "geometry": {"type": geom_type, "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            }
        ],
    }


def test_boundary_in_repo_is_valid():
    from sombra.ingest.ibge import boundary_path, validate_boundary

    data = json.loads(boundary_path("3552205").read_text(encoding="utf-8"))
    validate_boundary(data, "3552205")


def test_fetch_boundary_validates_and_writes_atomically(tmp_path, monkeypatch):
    import io

    from sombra.ingest import ibge

    payload = json.dumps(_fake_boundary()).encode()
    monkeypatch.setattr(ibge.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(payload))
    path = ibge.fetch_boundary("3552205", cities_dir=tmp_path, force=True)
    assert json.loads(path.read_text())["features"][0]["properties"]["codarea"] == "3552205"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        json.dumps(_fake_boundary("9999999")).encode(),
        json.dumps(_fake_boundary(geom_type="Point")).encode(),
    ],
)
def test_fetch_boundary_rejects_bad_payload(tmp_path, monkeypatch, payload):
    import io

    from sombra.ingest import ibge

    monkeypatch.setattr(ibge.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(payload))
    with pytest.raises(RuntimeError):
        ibge.fetch_boundary("3552205", cities_dir=tmp_path, force=True)
    assert not list(tmp_path.iterdir())


def test_missing_boundary_removes_stale_copy(tmp_path, monkeypatch):
    import sombra.publish.export_web as ew

    out = tmp_path / "x"
    out.mkdir()
    (out / "boundary.geojson").write_text("{}")
    monkeypatch.setattr(ew, "boundary_path", lambda ibge: tmp_path / "nao-existe.geojson")
    ew._copy_boundary("3552205", out)
    assert not (out / "boundary.geojson").exists()


def test_demo_does_not_overwrite_real_data(tmp_path):
    from sombra.cli import main as cli_main

    out = tmp_path / "real"
    out.mkdir()
    (out / "meta.json").write_text('{"demo": false}', encoding="utf-8")
    assert cli_main(["run", "--city", "3552205", "--demo", "--out", str(out)]) == 1
    assert json.loads((out / "meta.json").read_text())["demo"] is False
