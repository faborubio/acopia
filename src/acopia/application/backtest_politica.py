"""BacktestPolitica: valida una política de despacho sobre el histórico real (§6.3).

Por cada fold (día): pronostica con la historia as-seen → optimiza (estocástico
sobre escenarios) → **ejecuta el plan contra lo que realmente pasó** → compara:

- ``ingreso_esperado``: lo que el plan prometía (sobre el forecast).
- ``ingreso_realizado``: lo que la ejecución logró contra generación/CMg reales.
- ``ingreso_foresight``: techo con previsión perfecta (optimizar el día real).

El estado de la batería **se arrastra entre folds** (la ejecución de un día define
el punto de partida del siguiente). Todo entra por puertos: sin infraestructura.
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.observacion import Observacion
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import PoliticaDespacho
from acopia.domain.ports.puerto_forecaster import PuertoForecaster
from acopia.domain.ports.puerto_optimizador import PuertoOptimizador
from acopia.domain.services.simulador_ejecucion import SimuladorEjecucion


@dataclass(frozen=True, slots=True)
class FoldPolitica:
    """Resultado de un día del backtest."""

    ingreso_esperado_mills: int
    ingreso_realizado_mills: int
    ingreso_foresight_mills: int
    energia_vertida_wh: int
    acciones_reparadas: int


@dataclass(frozen=True, slots=True)
class ResultadoBacktestPolitica:
    """Agregado del backtest de una política sobre el histórico."""

    folds: tuple[FoldPolitica, ...]

    @property
    def ingreso_esperado_mills(self) -> int:
        return sum(f.ingreso_esperado_mills for f in self.folds)

    @property
    def ingreso_realizado_mills(self) -> int:
        return sum(f.ingreso_realizado_mills for f in self.folds)

    @property
    def ingreso_foresight_mills(self) -> int:
        return sum(f.ingreso_foresight_mills for f in self.folds)

    @property
    def captura_vs_foresight_bp(self) -> int:
        """Cuánto del techo de previsión perfecta capturó la política (puntos base)."""
        if self.ingreso_foresight_mills <= 0:
            return 0
        return (self.ingreso_realizado_mills * 10_000) // self.ingreso_foresight_mills


def _escenario_real(tramo: tuple[Observacion, ...]) -> Escenario:
    return Escenario(tuple(PuntoPronostico(o.generacion, o.cmg) for o in tramo))


def backtest_politica(
    forecaster: PuertoForecaster,
    optimizador: PuertoOptimizador,
    planta: Planta,
    estado_inicial: EstadoBateria,
    historia: tuple[Observacion, ...],
    politica: PoliticaDespacho,
    folds: int,
    n_escenarios: int = 1,
    semilla: int = 0,
) -> ResultadoBacktestPolitica:
    """Evalúa la política en los últimos ``folds`` tramos del histórico."""
    if folds < 1:
        raise ValueError("folds debe ser >= 1")
    horizonte = politica.horizonte_intervalos
    if len(historia) <= folds * horizonte:
        raise ValueError(
            f"Historia insuficiente ({len(historia)}) para {folds} folds de {horizonte} "
            f"pasos: se requieren más de {folds * horizonte} observaciones"
        )

    simulador = SimuladorEjecucion()
    estado = estado_inicial
    resultados: list[FoldPolitica] = []
    for k in range(folds):
        inicio = len(historia) - (folds - k) * horizonte
        entrenamiento = historia[:inicio]
        tramo_real = historia[inicio : inicio + horizonte]

        escenarios = forecaster.pronosticar(entrenamiento, horizonte, n_escenarios, semilla)
        plan = optimizador.optimizar_escenarios(planta, estado, escenarios, politica)

        escenario_real = _escenario_real(tramo_real)
        ejecucion = simulador.ejecutar(planta, estado, plan, escenario_real, politica)
        foresight = optimizador.optimizar(planta, estado, escenario_real, politica)

        resultados.append(
            FoldPolitica(
                ingreso_esperado_mills=plan.ingreso_esperado_mills,
                ingreso_realizado_mills=ejecucion.ingreso_realizado_mills,
                ingreso_foresight_mills=foresight.ingreso_esperado_mills,
                energia_vertida_wh=sum(ejecucion.energia_vertida_wh),
                acciones_reparadas=ejecucion.acciones_reparadas,
            )
        )
        estado = ejecucion.estado_final  # el día siguiente parte donde quedó la batería

    return ResultadoBacktestPolitica(folds=tuple(resultados))
