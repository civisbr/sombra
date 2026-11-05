"""Razão observado/esperado de óbitos em ondas de calor (validação entre municípios)."""


def observed_expected_ratio(observed: float, expected: float) -> float:
    if expected <= 0:
        raise ValueError("óbitos esperados devem ser positivos")
    return observed / expected
