"""RastroForecast: snapshot as-seen de un pronóstico, reconstruible y auditable (ADR-007).

Guarda la **procedencia** del forecast (qué modelo, qué historia as-seen vía huella,
horizonte, nº de escenarios y semilla) junto con lo **producido** (los escenarios). Con
esto, `(forecaster, historia, semilla)` reproduce el mismo forecast de forma verificable.
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.entities.escenario import Escenario


@dataclass(frozen=True, slots=True)
class RastroForecast:
    """Snapshot de un pronóstico: su procedencia as-seen y los escenarios generados."""

    forecaster: str  # identidad/versión del modelo, p. ej. "lstm@ventana48,hidden32"
    horizonte: int
    n_escenarios: int
    semilla: int
    n_observaciones: int  # largo de la historia as-seen
    huella_historia: str  # hash de la historia (ver domain/services/huella.py)
    escenarios: tuple[Escenario, ...]

    def __post_init__(self) -> None:
        if not self.escenarios:
            raise ValueError("El rastro debe guardar al menos un escenario")
        if self.n_observaciones < 1:
            raise ValueError("n_observaciones debe ser >= 1")
        if len(self.escenarios) != self.n_escenarios:
            raise ValueError(
                f"n_escenarios ({self.n_escenarios}) no coincide con los escenarios "
                f"guardados ({len(self.escenarios)})"
            )
