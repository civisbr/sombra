"""Exporta o resultado para o site estático e para download (GeoJSON, CSV, GeoParquet)."""

import csv
import json
import os
from pathlib import Path

import numpy as np
from shapely.geometry import mapping

from sombra.config import ROOT
from sombra.pipeline import Result

WEB_DATA = ROOT / "web" / "data"
MIN_COUNT = 5  # contagens menores são suprimidas para evitar reidentificação
SUPPRESSED = ("population", "pop_65plus")
CLASS_LABELS = ["Menor", "Moderada", "Alta", "Muito alta"]

SOURCES_REAL = [
    {"name": "Landsat 8/9 Collection 2 Level-2 (NASA/USGS)", "use": "calor de superfície"},
    {"name": "Censo 2022 (IBGE)", "use": "população, idade, cor/raça, domicílios"},
    {"name": "Sentinel-2 L2A (ESA/Copernicus)", "use": "vegetação (NDVI)"},
    {"name": "CNES (DATASUS), INEP e OpenStreetMap", "use": "equipamentos públicos"},
]
SOURCES_DEMO = [
    {
        "name": "Dados sintéticos gerados por sombra.demo",
        "use": "todos os números desta prévia são ilustrativos e não descrevem nenhum bairro real",
    }
]


def _clean(v):
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else round(float(v), 3)
    if isinstance(v, np.integer):
        return int(v)
    return v


def _rows(result: Result) -> list[dict]:
    rows = []
    for i, sid in enumerate(result.sector_ids):
        row = {"id": sid}
        for name, col in result.columns.items():
            row[name] = _clean(col[i])
            if name in SUPPRESSED and row[name] is not None and row[name] < MIN_COUNT:
                row[name] = None
        cls = row["priority_class"]
        row["priority_label"] = CLASS_LABELS[cls] if cls >= 0 else "Sem dado"
        rows.append(row)
    return rows


def export(result: Result, demo: bool, reference_date: str, out_dir: Path | None = None) -> Path:
    city = result.city
    out = out_dir or WEB_DATA / city.ibge
    out.mkdir(parents=True, exist_ok=True)
    rows = _rows(result)

    features = []
    for geom, row in zip(result.geoms, rows, strict=True):
        features.append({"type": "Feature", "geometry": mapping(geom), "properties": row})
    (out / "sectors.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )

    with (out / "sectors.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    def sector_ref(i: int) -> dict:
        r = rows[i]
        return {
            k: r[k]
            for k in ("id", "priority", "priority_label", "population", "pop_65plus", "ndvi")
        }

    actions = {
        "trees": [sector_ref(i) for i in result.trees],
        "cooling": [
            {k: e[k] for k in ("name", "kind", "lon", "lat", "population", "radius_m")}
            | {"sectors": [result.sector_ids[i] for i in e["sectors"]]}
            for e in result.cooling
        ],
        "active_search": [sector_ref(i) for i in result.active_search],
    }
    (out / "actions.json").write_text(json.dumps(actions, ensure_ascii=False), encoding="utf-8")

    centroids = np.array([[g.centroid.x, g.centroid.y] for g in result.geoms])
    meta = {
        "ibge": city.ibge,
        "name": city.name,
        "uf": city.uf,
        "demo": demo,
        "reference_date": reference_date,
        "n_sectors": len(rows),
        "center": [float(centroids[:, 0].mean()), float(centroids[:, 1].mean())],
        "bounds": [
            float(min(g.bounds[0] for g in result.geoms)),
            float(min(g.bounds[1] for g in result.geoms)),
            float(max(g.bounds[2] for g in result.geoms)),
            float(max(g.bounds[3] for g in result.geoms)),
        ],
        "sources": SOURCES_DEMO if demo else SOURCES_REAL,
        "robustness": {
            "fraction": result.robustness["fraction"],
            "min_overlap": _clean(result.robustness["min_overlap"]),
            "mean_overlap": _clean(result.robustness["mean_overlap"]),
            "overlaps": {k: _clean(v) for k, v in result.robustness["overlaps"].items()},
        },
        "code_version": os.environ.get("GITHUB_SHA", "local"),
        "min_count_suppressed": MIN_COUNT,
        "weights": "pesos iguais entre indicadores e entre componentes",
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    _write_geoparquet(out)
    _update_index(out.parent, meta)
    return out


def _write_geoparquet(out: Path) -> None:
    """GeoParquet via DuckDB spatial; segue sem o arquivo se a extensão não estiver disponível."""
    (out / "sectors.parquet").unlink(missing_ok=True)
    try:
        import duckdb

        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial;")
        src = str(out / "sectors.geojson").replace("'", "''")
        dst = str(out / "sectors.parquet").replace("'", "''")
        con.execute(f"COPY (SELECT * FROM ST_Read('{src}')) TO '{dst}' (FORMAT PARQUET)")
    except Exception as exc:  # noqa: BLE001 - extensão exige rede na primeira vez
        print(f"aviso: GeoParquet não gerado ({exc.__class__.__name__})")


def _update_index(web_data: Path, meta: dict) -> None:
    path = web_data / "cities.json"
    cities = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    cities = [c for c in cities if c["ibge"] != meta["ibge"]]
    cities.append(
        {"ibge": meta["ibge"], "name": meta["name"], "uf": meta["uf"], "demo": meta["demo"]}
    )
    cities.sort(key=lambda c: c["name"])
    path.write_text(json.dumps(cities, ensure_ascii=False), encoding="utf-8")
