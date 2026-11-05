import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CITIES_DIR = ROOT / "cities"
DATA_DIR = ROOT / "data"


@dataclass(frozen=True)
class City:
    ibge: str
    name: str
    uf: str
    bbox: tuple[float, float, float, float]
    season_months: tuple[int, ...]
    first_year: int
    last_year: int
    recent_summers: int
    max_cloud_cover: int
    inmet_stations: tuple[str, ...]
    cooling_radius_m: float

    @property
    def raw_dir(self) -> Path:
        return DATA_DIR / "raw" / self.ibge

    @property
    def processed_dir(self) -> Path:
        return DATA_DIR / "processed" / self.ibge


def validate_ibge(code: str) -> str:
    if not re.fullmatch(r"[0-9]{7}", code):
        raise ValueError(
            f"código IBGE inválido: {code!r} (esperado 7 dígitos; SIM/DATASUS usa 6, IBGE usa 7)"
        )
    return code


def load_city(code: str, cities_dir: Path = CITIES_DIR) -> City:
    code = validate_ibge(code)
    path = cities_dir / f"{code}.toml"
    if not path.exists():
        raise FileNotFoundError(f"configuração não encontrada: {path}")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    period = raw["period"]
    if validate_ibge(str(raw["ibge"])) != code:
        raise ValueError(f"ibge em {path.name} difere do nome do arquivo")
    return City(
        ibge=code,
        name=raw["name"],
        uf=raw["uf"],
        bbox=tuple(raw["bbox"]),
        season_months=tuple(period["season_months"]),
        first_year=period["first_year"],
        last_year=period["last_year"],
        recent_summers=period["recent_summers"],
        max_cloud_cover=period["max_cloud_cover"],
        inmet_stations=tuple(raw.get("inmet", {}).get("stations", ())),
        cooling_radius_m=float(raw.get("cooling", {}).get("radius_m", 500)),
    )
