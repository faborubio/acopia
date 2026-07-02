"""Tests del BacktestPolitica: validar la política sobre el histórico (§6.3, Fase 3)."""

from __future__ import annotations

import pytest

from acopia.application.backtest_politica import backtest_politica
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.observacion import Observacion
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.domain.value_objects.soc import Soc
from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP

UNA_HORA = Intervalo.de_minutos(60)


class _ForecasterPerfecto:
    """Stub con previsión perfecta: devuelve el tramo real que sigue a la historia."""

    def __init__(self, historia_completa: tuple[Observacion, ...]) -> None:
        self._completa = historia_completa

    def pronosticar(
        self,
        historia: tuple[Observacion, ...],
        horizonte: int,
        n_escenarios: int,
        semilla: int,
    ) -> tuple[Escenario, ...]:
        inicio = len(historia)
        tramo = self._completa[inicio : inicio + horizonte]
        puntos = tuple(PuntoPronostico(o.generacion, o.cmg) for o in tramo)
        return (Escenario(puntos),) * n_escenarios


class _ForecasterOptimista:
    """Stub que promete un PV enorme y barato que no existirá."""

    def pronosticar(
        self,
        historia: tuple[Observacion, ...],
        horizonte: int,
        n_escenarios: int,
        semilla: int,
    ) -> tuple[Escenario, ...]:
        puntos = tuple(
            PuntoPronostico(Potencia(50_000), Precio(10_000 if h == 0 else 500_000))
            for h in range(horizonte)
        )
        return (Escenario(puntos),) * n_escenarios


def _bateria() -> Bateria:
    return Bateria(
        capacidad=Energia(100_000),
        potencia_max_carga=Potencia(50_000),
        potencia_max_descarga=Potencia(50_000),
        eficiencia_carga=Eficiencia.de_porcentaje(100),
        eficiencia_descarga=Eficiencia.de_porcentaje(100),
        soc_min=Soc.de_porcentaje(0),
        soc_max=Soc.de_porcentaje(100),
        throughput_garantia=Energia(10_000_000),
    )


def _planta(retiro_w: int = 10_000_000) -> Planta:
    return Planta("planta-test", _bateria(), Potencia(10_000_000), Potencia(retiro_w))


def _politica(horizonte: int) -> PoliticaDespacho:
    return PoliticaDespacho(
        id="arbitraje",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=horizonte,
        resolucion=UNA_HORA,
        semilla=42,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
        costo_ciclado_mills_por_mwh=0,
    )


def _historia_diaria(dias: int) -> tuple[Observacion, ...]:
    """Días de 4 pasos: PV al mediodía barato, tarde cara sin PV (arbitraje claro)."""
    patron = [(0, 80_000), (30_000, 10_000), (20_000, 20_000), (0, 400_000)]
    return tuple(
        Observacion(Potencia(g), Precio(c)) for _ in range(dias) for g, c in patron
    )


def test_forecast_perfecto_captura_el_foresight() -> None:
    historia = _historia_diaria(4)
    resultado = backtest_politica(
        _ForecasterPerfecto(historia),
        OptimizadorLP(),
        _planta(),
        EstadoBateria(Energia(0)),
        historia,
        _politica(4),
        folds=2,
    )
    # Con previsión perfecta, lo realizado == lo esperado == el techo.
    assert resultado.ingreso_realizado_mills == resultado.ingreso_esperado_mills
    assert resultado.ingreso_realizado_mills == resultado.ingreso_foresight_mills
    assert resultado.captura_vs_foresight_bp == 10_000
    assert all(f.acciones_reparadas == 0 for f in resultado.folds)


def test_forecast_enganoso_pierde_contra_el_foresight() -> None:
    # El forecaster promete PV barato que no existe; la planta no puede retirar de
    # la red: las cargas planificadas se reparan y el ingreso queda bajo el techo.
    historia = _historia_diaria(4)
    resultado = backtest_politica(
        _ForecasterOptimista(),
        OptimizadorLP(),
        _planta(retiro_w=0),
        EstadoBateria(Energia(0)),
        historia,
        _politica(4),
        folds=2,
    )
    assert resultado.ingreso_realizado_mills < resultado.ingreso_foresight_mills
    assert resultado.captura_vs_foresight_bp < 10_000
    assert any(f.acciones_reparadas > 0 for f in resultado.folds)


def test_el_estado_se_arrastra_entre_folds() -> None:
    # Si el día 1 deja energía en la batería, el día 2 parte con ella (no se resetea).
    historia = _historia_diaria(4)
    resultado = backtest_politica(
        _ForecasterPerfecto(historia),
        OptimizadorLP(),
        _planta(),
        EstadoBateria(Energia(0)),
        historia,
        _politica(4),
        folds=3,
    )
    assert len(resultado.folds) == 3  # corre completo con estado encadenado


def test_historia_insuficiente_es_error() -> None:
    historia = _historia_diaria(1)
    with pytest.raises(ValueError, match="insuficiente"):
        backtest_politica(
            _ForecasterPerfecto(historia),
            OptimizadorLP(),
            _planta(),
            EstadoBateria(Energia(0)),
            historia,
            _politica(4),
            folds=1,
        )
