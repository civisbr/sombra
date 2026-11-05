"""Dados do IBGE: contorno municipal (API de malhas); setores e Censo 2022 em seguida."""

import csv
import io
import json
import os
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from sombra.config import CITIES_DIR, DATA_DIR, validate_ibge

BOUNDARY_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{code}"
    "?formato=application/vnd.geo+json&qualidade=maxima"
)
MAX_BYTES = 20 * 1024 * 1024

CENSO = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022"
AGREGADOS = f"{CENSO}/Agregados_por_Setores_Censitarios"
RENDA = f"{CENSO}/Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel"
CENSUS_ZIPS = {
    "demografia": f"{AGREGADOS}/Agregados_por_Setor_csv/Agregados_por_setores_demografia_BR.zip",
    "cor_raca": f"{AGREGADOS}/Agregados_por_Setor_csv/Agregados_por_setores_cor_ou_raca_BR.zip",
    "renda": f"{RENDA}/Agregados_por_setores_renda_responsavel_BR_20260508_csv.zip",
}
RAW_IBGE = DATA_DIR / "raw" / "ibge"
CENSUS_REFERENCE = "Censo Demográfico 2022 (IBGE)"


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


def sectors_gpkg_url(uf: str) -> str:
    return f"{AGREGADOS}/malha_com_atributos/setores/gpkg/UF/{uf}/{uf}_setores_CD2022.gpkg"


MAX_DOWNLOAD = 1 << 30  # 1 GiB
MAX_CSV_BYTES = 2 << 30


def _download(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    size = 0
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            if not r.geturl().startswith("https://ftp.ibge.gov.br/"):
                raise RuntimeError(f"redirecionamento para fora do IBGE: {r.geturl()}")
            if int(r.headers.get("Content-Length") or 0) > MAX_DOWNLOAD:
                raise RuntimeError(f"download maior que o limite: {url}")
            with tmp.open("wb") as f:
                while chunk := r.read(1 << 20):
                    size += len(chunk)
                    if size > MAX_DOWNLOAD:
                        raise RuntimeError(f"download maior que o limite: {url}")
                    f.write(chunk)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def input_record(path: Path, url: str | None = None) -> dict:
    """Registro de proveniência de um insumo: nome, URL, tamanho, sha256 e data do arquivo."""
    import datetime
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    day = datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.UTC).date().isoformat()
    return {
        "file": path.name,
        "url": url,
        "bytes": path.stat().st_size,
        "sha256": h.hexdigest(),
        "date": day,
    }


def ensure_raw(uf: str, raw_dir: Path = RAW_IBGE) -> dict[str, Path]:
    """Baixa (uma vez) a malha de setores da UF e os agregados do Censo 2022."""
    files = {"gpkg": _download(sectors_gpkg_url(uf), raw_dir / f"{uf}_setores_CD2022.gpkg")}
    for name, url in CENSUS_ZIPS.items():
        files[name] = _download(url, raw_dir / url.rsplit("/", 1)[1])
    return files


def parse_num(value: str) -> float:
    """Número do IBGE: vírgula ou ponto decimal; '.', 'X' e vazio (sigilo/ausente) viram NaN."""
    v = (value or "").strip().strip('"')
    if v in ("", ".", "X", "-"):
        return float("nan")
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return float("nan")


def read_census_zip(zip_path: Path, ibge: str, wanted: list[str]) -> dict[str, dict[str, float]]:
    """Lê do CSV (dentro do zip) só as linhas do município e as colunas pedidas."""
    out: dict[str, dict[str, float]] = {}
    with zipfile.ZipFile(zip_path) as zf:
        name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
        if name is None:
            raise RuntimeError(f"{zip_path.name} não contém CSV")
        if zf.getinfo(name).file_size > MAX_CSV_BYTES:
            raise RuntimeError(f"{name} descomprimido excede o limite")
        with zf.open(name) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="latin-1"), delimiter=";")
            header = [h.strip().upper() for h in next(reader)]
            idx = {h: i for i, h in enumerate(header)}
            missing = [w for w in wanted if w.upper() not in idx]
            if missing:
                raise RuntimeError(f"colunas ausentes em {zip_path.name}: {missing}")
            for row in reader:
                if row and row[0].startswith(ibge):
                    out[row[0]] = {w: parse_num(row[idx[w.upper()]]) for w in wanted}
    return out


# CD_TIPO do IBGE: 0 = setor comum; 1 = favela e comunidade urbana (os 40 setores de Sorocaba têm
# NM_FCU preenchido). Os tipos 4, 6 e 7 em Sorocaba têm de 0 a 2.067 moradores.
INCLUDED_TYPES = {"0": "comum", "1": "favela e comunidade urbana"}


def sector_status(situacao: str, tipo: str) -> str:
    """'incluido' ou o motivo da exclusão: 'rural' ou 'tipo <n>' (setor especial)."""
    if situacao != "Urbana":
        return "rural"
    return "incluido" if tipo in INCLUDED_TYPES else f"tipo {tipo}"


@dataclass
class Sectors:
    ids: list[str]
    geoms: list
    population: np.ndarray
    persons_per_household: np.ndarray
    excluded: dict[str, int]
    types: list[str]


def load_sectors(gpkg: Path, ibge: str) -> Sectors:
    """Setores urbanos comuns e de favelas (CD_TIPO 0 e 1); os demais só são contados."""
    import duckdb
    from shapely import wkb

    validate_ibge(ibge)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    rows = con.execute(
        "SELECT CD_SETOR, SITUACAO, CD_TIPO, v0001, v0005, ST_AsWKB(geom) "
        "FROM ST_Read(?) WHERE CD_MUN = ? ORDER BY CD_SETOR",
        [str(gpkg), ibge],
    ).fetchall()
    ids, geoms, pop, pph, types = [], [], [], [], []
    excluded: dict[str, int] = {}
    for cd, situacao, tipo, v1, v5, geom in rows:
        status = sector_status(situacao, tipo)
        if status != "incluido":
            excluded[status] = excluded.get(status, 0) + 1
        else:
            types.append(tipo)
            ids.append(cd)
            geoms.append(wkb.loads(bytes(geom)))
            pop.append(float(v1) if v1 is not None else np.nan)
            pph.append(float(v5) if v5 is not None else np.nan)
    return Sectors(ids, geoms, np.array(pop), np.array(pph), dict(sorted(excluded.items())), types)


def load_boundary_geom(ibge: str, cities_dir: Path = CITIES_DIR):
    """Polígono do município (união das feições do contorno oficial)."""
    from shapely.geometry import shape
    from shapely.ops import unary_union

    data = json.loads(boundary_path(ibge, cities_dir).read_text(encoding="utf-8"))
    return unary_union([shape(f["geometry"]) for f in data["features"]])
