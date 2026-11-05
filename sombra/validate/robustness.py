from sombra.index.sensitivity import robustness

__all__ = ["robustness", "MIN_OVERLAP"]

# Critério de aceite da Fase 3: sobreposição do top 10% ≥ 70% sob pesos alternativos.
MIN_OVERLAP = 0.70
