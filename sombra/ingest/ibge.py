"""Dados do IBGE: contorno municipal (API de malhas); setores e Censo 2022 em seguida."""

import json
import os
import urllib.request
from pathlib import Path

from sombra.config import CITIES_DIR, validate_ibge

BOUNDARY_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{code}"
    "?formato=application/vnd.geo+json&qualidade=maxima"
)
MAX_BYTES = 20 * 1024 * 1024


def boundary_path(ibge: str, cities_dir: Path = CITIES_DIR) -> Path:
    return cities_dir / f"{validate_ibge(ibge)}.boundary.geojson"


def validate_boundary(data, ibge: str) -> None:
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise RuntimeError("resposta inesperada da API de malhas do IBGE")
    features = data.get("features")
    if not isinstance(features, list) or len(features) != 1:
        raise RuntimeError("esperada exatamente uma feição de contorno")
    feat = features[0]
    if (feat.get("properties") or {}).get("codarea") != ibge:
        raise RuntimeError("codarea do contorno difere do município pedido")
    if (feat.get("geometry") or {}).get("type") not in ("Polygon", "MultiPolygon"):
        raise RuntimeError("geometria do contorno não é Polygon/MultiPolygon")


def fetch_boundary(ibge: str, cities_dir: Path = CITIES_DIR, force: bool = False) -> Path:
    """Baixa o contorno oficial (IBGE) e grava em ``cities/<ibge>.boundary.geojson``.

    É dado-fonte versionado no repositório, não cache: ``force`` só serve para atualizá-lo.
    """
    path = boundary_path(ibge, cities_dir)
    if path.exists() and not force:
        return path
    with urllib.request.urlopen(BOUNDARY_URL.format(code=validate_ibge(ibge)), timeout=60) as r:
        raw = r.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise RuntimeError("resposta do IBGE maior que o limite")
    data = json.loads(raw)
    validate_boundary(data, ibge)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def fetch_sectors(city_ibge: str):
    raise NotImplementedError("ibge: setores e Censo 2022 ainda não implementados")
