"""Puerto del forecaster: el dominio lo define, la infraestructura lo implementa.

El forecast entra al optimizador como **dato** (escenarios), no como una llamada.
Distintas implementaciones (baseline estacional, SARIMAX, Seq2Seq-LSTM) viven en
`infrastructure/` detrás de este mismo puerto y se comparan entre sí (ADR-002).
"""

from __future__ import annotations

from typing import Protocol

from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.observacion import Observacion


class PuertoForecaster(Protocol):
    """Proyecta generación PV y CMg a futuro como escenarios probabilísticos."""

    def pronosticar(
        self,
        historia: tuple[Observacion, ...],
        horizonte: int,
        n_escenarios: int,
        semilla: int,
    ) -> tuple[Escenario, ...]:
        """Devuelve ``n_escenarios`` trayectorias de largo ``horizonte``.

        El primer escenario es el pronóstico puntual (sin ruido); los demás
        incorporan la incertidumbre. Determinista para una misma ``semilla``.
        """
        ...
