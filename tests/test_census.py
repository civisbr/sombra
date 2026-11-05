import zipfile

import numpy as np
import pytest

from sombra.ingest.ibge import parse_num, read_census_zip
from sombra.vulnerability.census import census_indicators


def test_parse_num_handles_ibge_formats():
    assert parse_num("2,8") == 2.8
    assert parse_num("2453.03") == 2453.03
    assert parse_num('"336"') == 336.0
    for bad in (".", "X", "", "-", "abc"):
        assert np.isnan(parse_num(bad))


def _zip(tmp_path, text):
    p = tmp_path / "t.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("t.csv", text.encode("latin-1"))
    return p


def test_read_census_zip_filters_municipality_and_columns(tmp_path):
    csv = (
        '"CD_setor";"V01006";"V01040"\n'
        '"355220505000001";"100";"10"\n'
        '"355220505000002";".";"3"\n'
        '"111111111000001";"9";"9"\n'
    )
    out = read_census_zip(_zip(tmp_path, csv), "3552205", ["V01006", "V01040"])
    assert set(out) == {"355220505000001", "355220505000002"}
    assert out["355220505000001"]["V01006"] == 100.0
    assert np.isnan(out["355220505000002"]["V01006"])


def test_read_census_zip_fails_on_missing_column(tmp_path):
    with pytest.raises(RuntimeError):
        read_census_zip(_zip(tmp_path, '"CD_SETOR";"A"\n"3552205"\n'), "3552205", ["V01006"])


def test_census_indicators_known_values_and_suppression():
    ids = ["a", "b"]
    dem = {
        "a": {"V01006": 200.0, "V01031": 10.0, "V01040": 20.0, "V01041": 10.0},
        "b": {"V01006": float("nan"), "V01031": 5.0, "V01040": 5.0, "V01041": 5.0},
    }
    cor = {"a": {"V01318": 40.0, "V01320": 60.0}}
    renda = {"a": {"V06006": 2500.0}}
    out = census_indicators(ids, dem, cor, renda)
    assert out["pct_60plus"][0] == pytest.approx(15.0)
    assert out["pct_0_4"][0] == pytest.approx(5.0)
    assert out["pct_black_brown"][0] == pytest.approx(50.0)
    assert out["income"][0] == 2500.0
    assert np.isnan(out["pct_60plus"][1]) and np.isnan(out["income"][1])


def test_sector_status_keeps_favelas_and_flags_exclusions():
    from sombra.ingest.ibge import sector_status

    assert sector_status("Urbana", "0") == "incluido"
    assert sector_status("Urbana", "1") == "incluido"  # favela e comunidade urbana
    assert sector_status("Urbana", "6") == "tipo 6"
    assert sector_status("Rural", "0") == "rural"
