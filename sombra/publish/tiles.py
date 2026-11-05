"""PMTiles via tippecanoe (opcional; o site também lê o GeoJSON direto)."""

import shutil
import subprocess
from pathlib import Path


def build_pmtiles(geojson: Path, out: Path, layer: str = "sectors") -> bool:
    if shutil.which("tippecanoe") is None:
        print("aviso: tippecanoe não encontrado; site usa o GeoJSON")
        return False
    subprocess.run(
        ["tippecanoe", "-o", str(out), "-l", layer, "-zg", "--force", str(geojson)], check=True
    )
    return True
