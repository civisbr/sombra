"""Conversão, máscara, anomalia e composição de temperatura de superfície (Landsat C2 L2)."""

import numpy as np

# Landsat Collection 2 Level-2, ST_B10: K = DN * 0.00341802 + 149.0
ST_SCALE = 0.00341802
ST_OFFSET = 149.0

# Bits de QA_PIXEL: 1 dilated cloud, 2 cirrus, 3 cloud, 4 cloud shadow, 5 snow
_QA_BITS_BAD = (1, 2, 3, 4, 5)
_QA_FILL_BIT = 0


def dn_to_kelvin(dn: np.ndarray) -> np.ndarray:
    out = dn.astype("float64") * ST_SCALE + ST_OFFSET
    return np.where(dn == 0, np.nan, out)


def kelvin_to_celsius(kelvin: np.ndarray) -> np.ndarray:
    return kelvin - 273.15


def qa_pixel_valid(qa: np.ndarray) -> np.ndarray:
    """True onde o pixel não é fill, nuvem, cirrus, sombra de nuvem, nuvem dilatada ou neve."""
    qa = qa.astype("uint16")
    bad = (qa >> _QA_FILL_BIT) & 1 == 1
    for bit in _QA_BITS_BAD:
        bad |= (qa >> bit) & 1 == 1
    return ~bad


def mask_scene(celsius: np.ndarray, valid: np.ndarray) -> np.ndarray:
    return np.where(valid, celsius, np.nan)


def scene_anomaly(celsius: np.ndarray, urban_mask: np.ndarray | None = None) -> np.ndarray:
    """Anomalia de cada pixel em relação à mediana urbana da própria cena.

    Remove a diferença entre dias mais quentes e mais frios, deixando só o padrão espacial.
    """
    ref = celsius if urban_mask is None else np.where(urban_mask, celsius, np.nan)
    if not np.isfinite(ref).any():
        return np.full_like(celsius, np.nan, dtype="float64")
    return celsius - np.nanmedian(ref)


def compose_median(anomalies: list[np.ndarray], min_obs: int = 1) -> np.ndarray:
    """Mediana por pixel das anomalias; pixels com menos de ``min_obs`` observações viram NaN."""
    if not anomalies:
        raise ValueError("nenhuma cena para compor")
    stack = np.stack(anomalies)
    count = np.isfinite(stack).sum(axis=0)
    with np.errstate(all="ignore"):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            med = np.nanmedian(stack, axis=0)
    return np.where(count >= min_obs, med, np.nan)
