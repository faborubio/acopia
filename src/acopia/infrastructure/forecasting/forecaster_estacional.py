"""Forecaster baseline: estacional-naïve + bootstrap de residuos para la incertidumbre.

Es el **piso de comparación** (ADR-002): el pronóstico puntual repite el patrón de
la última estación; los escenarios añaden ruido muestreado de los residuos
estacionales históricos. SARIMAX y el Seq2Seq-LSTM, detrás del mismo puerto, deben
batir este baseline en RMSE/MAPE.

Determinista: misma ``semilla`` -> mismos escenarios.
"""

from __future__ import annotations

import numpy as np

from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.observacion import Observacion
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio

_BASE = 10_000


class ForecasterEstacionalNaive:
    """Implementa `PuertoForecaster` con estacional-naïve + bootstrap de residuos."""

    def __init__(self, estacionalidad: int) -> None:
        if estacionalidad < 1:
            raise ValueError(f"La estacionalidad debe ser >= 1: {estacionalidad}")
        self._estacionalidad = estacionalidad

    def pronosticar(
        self,
        historia: tuple[Observacion, ...],
        horizonte: int,
        n_escenarios: int,
        semilla: int,
    ) -> tuple[Escenario, ...]:
        if horizonte < 1:
            raise ValueError("El horizonte debe ser >= 1")
        if n_escenarios < 1:
            raise ValueError("n_escenarios debe ser >= 1")
        if len(historia) < self._estacionalidad:
            raise ValueError(
                f"La historia ({len(historia)}) es más corta que la estacionalidad "
                f"({self._estacionalidad})"
            )

        generacion = np.array([o.generacion.w for o in historia], dtype=float)
        cmg = np.array([o.cmg.mills_por_mwh for o in historia], dtype=float)

        gen_base = self._punto(generacion, horizonte)
        cmg_base = self._punto(cmg, horizonte)
        gen_residuos = self._residuos(generacion)
        cmg_residuos = self._residuos(cmg)

        rng = np.random.default_rng(semilla)
        probabilidad = max(1, _BASE // n_escenarios)
        escenarios: list[Escenario] = []
        for indice in range(n_escenarios):
            if indice == 0:
                gen = gen_base
                precio = cmg_base
            else:
                gen = gen_base + rng.choice(gen_residuos, size=horizonte)
                precio = cmg_base + rng.choice(cmg_residuos, size=horizonte)
            puntos = tuple(
                PuntoPronostico(
                    Potencia(max(0, round(float(gen[h])))),
                    Precio(round(float(precio[h]))),
                )
                for h in range(horizonte)
            )
            escenarios.append(Escenario(puntos, probabilidad))
        return tuple(escenarios)

    def _punto(self, serie: np.ndarray, horizonte: int) -> np.ndarray:
        """Pronóstico puntual estacional-naïve: repite la última estación observada."""
        e = self._estacionalidad
        base = serie[len(serie) - e :]
        return np.array([base[h % e] for h in range(horizonte)], dtype=float)

    def _residuos(self, serie: np.ndarray) -> np.ndarray:
        """Residuos estacionales en muestra: serie[t] - serie[t - estacionalidad]."""
        e = self._estacionalidad
        if len(serie) <= e:
            return np.array([0.0])
        return np.asarray(serie[e:] - serie[:-e], dtype=float)
