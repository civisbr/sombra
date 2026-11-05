import numpy as np
import pytest

from sombra.heat.lst import (
    compose_median,
    dn_to_kelvin,
    kelvin_to_celsius,
    qa_pixel_valid,
    scene_anomaly,
)


def test_dn_to_kelvin_known_values():
    # DN 44000 -> 44000*0.00341802 + 149.0 = 299.3929 K
    k = dn_to_kelvin(np.array([44000, 0], dtype="uint16"))
    assert k[0] == pytest.approx(299.39288, abs=1e-4)
    assert np.isnan(k[1])  # DN 0 é fill


def test_kelvin_to_celsius():
    assert kelvin_to_celsius(np.array([273.15]))[0] == pytest.approx(0.0)
    assert kelvin_to_celsius(dn_to_kelvin(np.array([44000], dtype="uint16")))[0] == pytest.approx(
        26.24288, abs=1e-4
    )


def test_qa_pixel_flags():
    clear = 1 << 6
    qa = np.array(
        [clear, clear | (1 << 3), clear | (1 << 4), clear | (1 << 1), 1, clear | (1 << 2)]
    )
    assert qa_pixel_valid(qa).tolist() == [True, False, False, False, False, False]


def test_scene_anomaly_removes_scene_level():
    base = np.array([[30.0, 32.0], [34.0, 36.0]])
    hot_day = base + 5
    assert np.allclose(scene_anomaly(base), scene_anomaly(hot_day))
    assert np.nanmedian(scene_anomaly(base)) == pytest.approx(0.0)


def test_scene_anomaly_ignores_nan_and_all_nan():
    a = np.array([[np.nan, 30.0], [32.0, 34.0]])
    out = scene_anomaly(a)
    assert np.isnan(out[0, 0]) and out[1, 0] == pytest.approx(0.0)
    assert np.isnan(scene_anomaly(np.full((2, 2), np.nan))).all()


def test_compose_median_min_obs():
    a = np.array([[1.0, np.nan]])
    b = np.array([[3.0, np.nan]])
    c = np.array([[2.0, 5.0]])
    out = compose_median([a, b, c], min_obs=2)
    assert out[0, 0] == pytest.approx(2.0)
    assert np.isnan(out[0, 1])
