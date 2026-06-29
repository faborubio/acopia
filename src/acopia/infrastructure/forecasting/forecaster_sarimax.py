"""Forecaster SARIMAX (statsmodels) detrás del mismo PuertoForecaster.

Ajusta un modelo SARIMAX por serie (generación PV y CMg) y proyecta el horizonte.
La incertidumbre sale de la distribución del pronóstico: el escenario 0 es la media
y los demás muestrean ``media + N(0, se)`` con una semilla fija (determinista).

Es el baseline estadístico de ADR-002: debe batir al estacional-naïve en RMSE/MAPE,
y a su vez el Seq2Seq-LSTM debe batirlo a él.
"""

from __future__ import annotations

import warnings

import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX

from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.observacion import Observacion
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio

_BASE = 10_000

Orden = tuple[int, int, int]
OrdenEstacional = tuple[int, int, int, int]


class ForecasterSARIMAX:
    """Implementa `PuertoForecaster` con un SARIMAX por serie."""

    def __init__(
        self,
        estacionalidad: int,
        orden: Orden = (1, 0, 0),
        orden_estacional: OrdenEstacional | None = None,
    ) -> None:
        if estacionalidad < 1:
            raise ValueError(f"La estacionalidad debe ser >= 1: {estacionalidad}")
        self._orden = orden
        self._orden_estacional = orden_estacional or (1, 0, 0, estacionalidad)

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
        if not historia:
            raise ValueError("La historia no puede estar vacía")

        generacion = np.array([o.generacion.w for o in historia], dtype=float)
        cmg = np.array([o.cmg.mills_por_mwh for o in historia], dtype=float)
        gen_media, gen_se = self._pronosticar_serie(generacion, horizonte)
        cmg_media, cmg_se = self._pronosticar_serie(cmg, horizonte)

        rng = np.random.default_rng(semilla)
        probabilidad = max(1, _BASE // n_escenarios)
        escenarios: list[Escenario] = []
        for indice in range(n_escenarios):
            if indice == 0:
                gen = gen_media
                precio = cmg_media
            else:
                gen = gen_media + rng.normal(0.0, gen_se)
                precio = cmg_media + rng.normal(0.0, cmg_se)
            puntos = tuple(
                PuntoPronostico(
                    Potencia(max(0, round(float(gen[h])))),
                    Precio(round(float(precio[h]))),
                )
                for h in range(horizonte)
            )
            escenarios.append(Escenario(puntos, probabilidad))
        return tuple(escenarios)

    def _pronosticar_serie(
        self, serie: np.ndarray, horizonte: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Ajusta SARIMAX y devuelve (media, error estándar) del pronóstico."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            modelo = SARIMAX(
                serie,
                order=self._orden,
                seasonal_order=self._orden_estacional,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            resultado = modelo.fit(disp=False)
            pronostico = resultado.get_forecast(steps=horizonte)
            media = np.nan_to_num(np.asarray(pronostico.predicted_mean, dtype=float))
            error = np.nan_to_num(np.asarray(pronostico.se_mean, dtype=float))
        return media, error
