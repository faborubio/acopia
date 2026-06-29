"""Métricas de calidad de pronóstico (auditoría de forecast, §12 del SAD).

Puras y deterministas. Permiten comparar implementaciones del `PuertoForecaster`
(baseline estacional vs SARIMAX vs LSTM) sobre los mismos datos.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


class MetricasForecast:
    """RMSE y MAPE entre un pronóstico puntual y la serie real."""

    def rmse(self, pronostico: Sequence[float], real: Sequence[float]) -> float:
        """Raíz del error cuadrático medio."""
        self._validar(pronostico, real)
        n = len(real)
        suma = sum((p - r) ** 2 for p, r in zip(pronostico, real, strict=True))
        return math.sqrt(suma / n)

    def mape(self, pronostico: Sequence[float], real: Sequence[float]) -> float:
        """Error porcentual absoluto medio (%), omitiendo los reales nulos.

        La generación PV es 0 de noche; MAPE no está definido ahí, así que esos
        puntos se omiten. Si todos los reales son 0, devuelve 0.
        """
        self._validar(pronostico, real)
        errores = [
            abs((r - p) / r) for p, r in zip(pronostico, real, strict=True) if r != 0
        ]
        if not errores:
            return 0.0
        return 100.0 * sum(errores) / len(errores)

    @staticmethod
    def _validar(pronostico: Sequence[float], real: Sequence[float]) -> None:
        if len(pronostico) != len(real):
            raise ValueError("pronóstico y real deben tener el mismo largo")
        if not real:
            raise ValueError("las series no pueden estar vacías")
