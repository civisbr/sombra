import numpy as np
import pytest
from rasterio.transform import from_origin
from shapely.geometry import box

from sombra.heat.zonal import zonal_stats


def test_zonal_known_result():
    # raster 4x4, pixel 1x1, origem em (0, 4); valores 0..15 por linha
    arr = np.arange(16, dtype="float64").reshape(4, 4)
    transform = from_origin(0, 4, 1, 1)
    # cobre colunas 0-1 e linhas 0-1 (de cima): valores 0,1,4,5
    out = zonal_stats(arr, transform, [box(0, 2, 2, 4)])[0]
    assert out["n"] == 4
    assert out["mean"] == pytest.approx(2.5)
    assert out["p"] == pytest.approx(np.percentile([0, 1, 4, 5], 90))


def test_zonal_ignores_nan_and_empty():
    arr = np.ones((4, 4))
    arr[0, 0] = np.nan
    transform = from_origin(0, 4, 1, 1)
    full, outside = zonal_stats(arr, transform, [box(0, 2, 2, 4), box(10, 10, 12, 12)])
    assert full["n"] == 3 and full["mean"] == pytest.approx(1.0)
    assert outside["n"] == 0 and np.isnan(outside["mean"])
