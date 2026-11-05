import numpy as np
import pytest

from sombra.ingest.landsat import LstComposite, load_composite, save_composite
from sombra.ingest.osm import classify, in_bbox, nearest_distance_m, parse_elements
from sombra.ingest.sentinel2 import ndvi, pick_scenes, reflectance, scl_valid


def test_ndvi_known_values():
    out = ndvi(np.array([0.01, 0.0]), np.array([0.03, 0.0]))
    assert out[0] == pytest.approx(0.5)
    assert np.isnan(out[1])


def test_reflectance_applies_boa_offset_from_baseline_04():
    dn = np.array([1000.0, 2000.0, 500.0])
    new = reflectance(dn, 5.10)
    assert new.tolist() == pytest.approx([0.0, 0.1, 0.0])  # -1000 e piso em zero
    assert reflectance(dn, 3.0).tolist() == pytest.approx([0.1, 0.2, 0.05])


def test_ndvi_from_dn_matches_real_value_with_offset():
    # vegetação: red DN 1500 (ρ=0,05), nir DN 5000 (ρ=0,40) na baseline 05.10 -> NDVI 0,778
    out = ndvi(reflectance(np.array([1500.0]), 5.10), reflectance(np.array([5000.0]), 5.10))
    assert out[0] == pytest.approx(0.7778, abs=1e-3)
    # sem aplicar o offset o NDVI sai comprimido (0,538): é o erro que isto evita
    assert (5000 - 1500) / (5000 + 1500) == pytest.approx(0.538, abs=1e-3)


def test_pick_scenes_covers_every_summer():
    import datetime

    class It:
        def __init__(self, i, d, cloud):
            self.id, self.datetime = i, d
            self.properties = {"eo:cloud_cover": cloud}

    items = [
        It("a", datetime.datetime(2023, 12, 5), 10),
        It("b", datetime.datetime(2024, 1, 5), 5),
        It("c", datetime.datetime(2025, 1, 5), 20),
        It("d", datetime.datetime(2025, 2, 5), 1),
    ]
    got = [i.id for i in pick_scenes(items, per_summer=1)]
    assert got == ["b", "d"]  # um por verão, o menos nublado de cada


def test_scl_valid_masks_clouds_shadow_and_nodata():
    scl = np.array([0, 1, 3, 4, 5, 6, 8, 9, 10, 11])
    assert scl_valid(scl).tolist() == [
        False,
        False,
        False,
        True,
        True,
        True,
        False,
        False,
        False,
        False,
    ]


def test_osm_classify():
    assert classify({"amenity": "school"}) == "escola"
    assert classify({"amenity": "library"}) == "biblioteca"
    assert classify({"amenity": "clinic", "name": "Unidade Básica de Saúde Vila X"}) == "ubs"
    assert classify({"amenity": "clinic", "name": "UBS Centro"}) == "ubs"
    assert classify({"amenity": "hospital", "name": "Hospital UBS Regional"}) is None
    assert classify({"amenity": "clinic", "name": "Clínica Dr. Fulano"}) is None


def test_parse_elements_dedup_and_center():
    els = [
        {"type": "node", "id": 1, "lat": -23.5, "lon": -47.4, "tags": {"amenity": "school"}},
        {"type": "node", "id": 1, "lat": -23.5, "lon": -47.4, "tags": {"amenity": "school"}},
        {
            "type": "way",
            "id": 2,
            "center": {"lat": -23.4, "lon": -47.3},
            "tags": {"amenity": "library"},
        },
        {"type": "node", "id": 3, "tags": {"amenity": "school"}},
    ]
    out = parse_elements(els)
    assert [e["kind"] for e in out] == ["escola", "biblioteca"]


def test_in_bbox_rejects_outside_and_bad_types():
    bbox = (-47.6, -23.6, -47.3, -23.3)
    assert in_bbox({"lat": -23.5, "lon": -47.4}, bbox)
    assert not in_bbox({"lat": 0.0, "lon": 0.0}, bbox)
    assert not in_bbox({"lat": "x", "lon": -47.4}, bbox)


def test_nearest_distance_without_points_is_nan():
    assert np.isnan(nearest_distance_m([(-47.4, -23.5)], [])).all()
    d = nearest_distance_m([(-47.4, -23.5)], [{"lon": -47.4, "lat": -23.5}])
    assert d[0] == pytest.approx(0.0)


def test_composite_roundtrip(tmp_path):
    from rasterio.transform import from_origin

    comp = LstComposite(
        np.array([[1.5, np.nan]]), from_origin(-47.6, -23.3, 0.0003, 0.0003), ["2024-01-01"], "x"
    )
    save_composite(comp, tmp_path / "c.npz")
    back = load_composite(tmp_path / "c.npz")
    assert back.scenes == ["2024-01-01"] and back.transform == comp.transform
    assert back.anomaly[0, 0] == pytest.approx(1.5) and np.isnan(back.anomaly[0, 1])
