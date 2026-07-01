"""Caso de uso PronosticarConRastro: forecast + snapshot as-seen atómicos (ADR-007).

Envuelve cualquier `PuertoForecaster` para que ningún pronóstico salga sin su rastro
(procedencia reconstruible). `reproduce_el_rastro` deja a un auditor verificar que el
snapshot se regenera bit a bit con la misma historia y semilla (determinismo, ADR-001).
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.observacion import Observacion
from acopia.domain.entities.rastro_forecast import RastroForecast
from acopia.domain.ports.puerto_forecaster import PuertoForecaster
from acopia.domain.services.huella import huella_historia


@dataclass(frozen=True, slots=True)
class ResultadoForecast:
    """Salida del caso de uso: los escenarios y su snapshot as-seen."""

    escenarios: tuple[Escenario, ...]
    rastro: RastroForecast


def pronosticar_con_rastro(
    forecaster: PuertoForecaster,
    forecaster_id: str,
    historia: tuple[Observacion, ...],
    horizonte: int,
    n_escenarios: int,
    semilla: int,
) -> ResultadoForecast:
    """Pronostica y arma el `RastroForecast` con la procedencia as-seen."""
    if not historia:
        raise ValueError("La historia no puede estar vacía")
    escenarios = forecaster.pronosticar(historia, horizonte, n_escenarios, semilla)
    rastro = RastroForecast(
        forecaster=forecaster_id,
        horizonte=horizonte,
        n_escenarios=n_escenarios,
        semilla=semilla,
        n_observaciones=len(historia),
        huella_historia=huella_historia(historia),
        escenarios=escenarios,
    )
    return ResultadoForecast(escenarios=escenarios, rastro=rastro)


def reproduce_el_rastro(
    forecaster: PuertoForecaster,
    historia: tuple[Observacion, ...],
    rastro: RastroForecast,
) -> bool:
    """Verifica que ``forecaster`` + ``historia`` regeneran el forecast del snapshot.

    Comprueba primero que la historia coincide con la huella guardada y luego que los
    escenarios se reproducen de forma idéntica (auditoría de ADR-007).
    """
    if huella_historia(historia) != rastro.huella_historia:
        return False
    escenarios = forecaster.pronosticar(
        historia, rastro.horizonte, rastro.n_escenarios, rastro.semilla
    )
    return escenarios == rastro.escenarios
