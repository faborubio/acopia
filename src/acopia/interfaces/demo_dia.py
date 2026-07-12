"""Día demo compartido: la duck curve chilena sembrada, lista para interrogar.

Composición (wiring) de un día típico del SEN — PV de campana, CMg colapsado a
mediodía por sobreoferta solar y punta vespertina — con una planta modelo y un plan
de arbitraje ya optimizado. La usan la demo stdio del servidor MCP y el dashboard
REST (`GET /demo`): una sola fuente para que ambos cuenten exactamente el mismo día.
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.application.planificar_despacho import PlanificarDespacho
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.entities.rastro import RastroDespacho
from acopia.domain.ports.puerto_optimizador import PuertoOptimizador
from acopia.domain.ports.repositorio_planes import RepositorioPlanes
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.domain.value_objects.soc import Soc
from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP
from acopia.infrastructure.persistencia.repositorio_planes_memoria import (
    RepositorioPlanesEnMemoria,
)

# Día chileno típico: PV de campana (kW) con CMg (USD/MWh) colapsado a mediodía
# y punta vespertina. Mismos valores que la demo MCP original.
GENERACION_KW = (
    0, 0, 0, 0, 0, 0, 5, 20, 45, 65, 80, 90, 95, 90, 80, 65, 45, 20, 5, 0, 0, 0, 0, 0,
)
CMG_USD_MWH = (
    75, 74, 73, 72, 73, 75, 70, 40, 5, 0, 0, 0, 0, 0, 3, 10, 25, 60, 95, 110, 105, 95, 85, 80,
)


@dataclass(frozen=True, slots=True)
class DemoSembrado:
    """El día demo ya optimizado: planta, política, plan y su rastro as-seen."""

    planta: Planta
    politica: PoliticaDespacho
    escenario: Escenario
    repositorio: RepositorioPlanes
    optimizador: PuertoOptimizador
    plan_id: str
    plan: PlanDespacho
    rastro: RastroDespacho


def sembrar_dia_demo() -> DemoSembrado:
    """Construye la planta modelo, optimiza el día típico y persiste plan + rastro."""
    bateria = Bateria(
        capacidad=Energia(100_000),
        potencia_max_carga=Potencia(50_000),
        potencia_max_descarga=Potencia(50_000),
        eficiencia_carga=Eficiencia.de_porcentaje(95),
        eficiencia_descarga=Eficiencia.de_porcentaje(95),
        soc_min=Soc.de_porcentaje(0),
        soc_max=Soc.de_porcentaje(100),
        throughput_garantia=Energia(1_000_000_000),
    )
    planta = Planta("planta-demo", bateria, Potencia(80_000), Potencia(0))
    politica = PoliticaDespacho(
        id="arbitraje-demo",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=24,
        resolucion=Intervalo.de_minutos(60),
        semilla=42,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
    )
    escenario = Escenario(
        tuple(
            PuntoPronostico(Potencia(g * 1_000), Precio(c * 1_000))
            for g, c in zip(GENERACION_KW, CMG_USD_MWH, strict=True)
        )
    )
    repositorio = RepositorioPlanesEnMemoria()
    optimizador = OptimizadorLP()
    resultado = PlanificarDespacho(optimizador, repositorio).ejecutar(
        planta, EstadoBateria(Energia(20_000)), escenario, politica
    )
    _, rastro = repositorio.obtener(resultado.plan_id)
    return DemoSembrado(
        planta=planta,
        politica=politica,
        escenario=escenario,
        repositorio=repositorio,
        optimizador=optimizador,
        plan_id=resultado.plan_id,
        plan=resultado.plan,
        rastro=rastro,
    )
