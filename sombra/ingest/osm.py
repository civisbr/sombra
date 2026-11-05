"""Equipamentos públicos do OpenStreetMap (Overpass): UBS, escolas e bibliotecas."""

import json
import re
import time
import urllib.parse
import urllib.request

import numpy as np

from sombra.config import City
from sombra.geo import haversine_m

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
USER_AGENT = "sombra-civisbr/0.1 (https://github.com/civisbr/sombra)"
UBS_NAME = re.compile(
    r"\b(ubs|usf|unidade b[aá]sica|posto de sa[uú]de|unidade de sa[uú]de)\b", re.I
)


def build_query(bbox: tuple[float, float, float, float]) -> str:
    w, s, e, n = bbox
    box = f"{s},{w},{n},{e}"
    return (
        "[out:json][timeout:120];("
        f'nwr["amenity"~"^(school|library)$"]({box});'
        f'nwr["amenity"~"^(clinic|doctors|hospital)$"]({box});'
        f'nwr["healthcare"]({box});'
        ");out center tags;"
    )


def classify(tags: dict) -> str | None:
    amenity = tags.get("amenity")
    if amenity == "school":
        return "escola"
    if amenity == "library":
        return "biblioteca"
    name = tags.get("name", "")
    if UBS_NAME.search(name) and amenity != "hospital":
        return "ubs"
    return None


def parse_elements(elements: list[dict]) -> list[dict]:
    out, seen = [], set()
    for el in elements:
        kind = classify(el.get("tags", {}))
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not kind or lat is None or lon is None:
            continue
        key = (el.get("type"), el.get("id"))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "name": el["tags"].get("name")
                or {"escola": "Escola", "biblioteca": "Biblioteca", "ubs": "UBS"}[kind],
                "kind": kind,
                "lon": float(lon),
                "lat": float(lat),
                "osm": f"{el.get('type')}/{el.get('id')}",
            }
        )
    return out


MAX_RESPONSE = 64 * 1024 * 1024


def in_bbox(el: dict, bbox) -> bool:
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    return (
        isinstance(lat, (int, float))
        and isinstance(lon, (int, float))
        and bbox[0] <= lon <= bbox[2]
        and bbox[1] <= lat <= bbox[3]
    )


def fetch_equipment(city: City) -> dict:
    """Equipamentos do bbox da cidade, com a origem (endpoint e data da base OSM) para auditoria."""
    data = urllib.parse.urlencode({"data": build_query(city.bbox)}).encode()
    last: Exception | None = None
    for attempt in range(3):
        for url in OVERPASS_ENDPOINTS:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    raw = r.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise ValueError("resposta do Overpass maior que o limite")
                payload = json.loads(raw)
                elements = [e for e in payload.get("elements", []) if in_bbox(e, city.bbox)]
                return {
                    "endpoint": url,
                    "osm_base": (payload.get("osm3s") or {}).get("timestamp_osm_base"),
                    "equipment": parse_elements(elements),
                }
            except (OSError, ValueError, KeyError) as exc:
                last = exc
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Overpass indisponível: {last}")


def nearest_distance_m(centroids: list[tuple[float, float]], points: list[dict]) -> np.ndarray:
    if not points:
        return np.full(len(centroids), np.nan)
    return np.array(
        [min(haversine_m(lon, lat, p["lon"], p["lat"]) for p in points) for lon, lat in centroids]
    )
