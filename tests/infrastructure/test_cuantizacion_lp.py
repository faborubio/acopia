"""Regresión del hallazgo del experimento ADR-005 (2026-07-09): el repair a RETENER.

Los floors de la eficiencia entera acumulan una deriva: tras N cargas, la batería
entera tiene menos energía que la trayectoria continua del LP. La descarga final
planificada queda infactible por unos Wh y el repair antiguo la **anulaba entera**
— en datos reales, la hora más cara del día (~15% del ingreso). El repair nuevo
recorta al máximo factible: se pierde la deriva, no el intervalo.
"""

from __future__ import annotations

from acopia.domain.entities.accion_despacho import TipoAccion
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.services.modelo_bateria import ModeloBateria
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.domain.value_objects.soc import Soc
from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP

UNA_HORA = Intervalo.de_minutos(60)


def test_la_deriva_de_floors_recorta_la_descarga_en_vez_de_anularla() -> None:
    """10 cargas de 3 Wh a ef 95% (floor: 2 celdas/h vs 2.85 continuo) + hora cara.

    El LP continuo acumula 28.5 Wh y planifica descargar ~27; la batería entera
    tiene 20 → la descarga factible es 19. Antes: RETENER (ingreso 0 en la punta).
    Ahora: DESCARGAR 19 W.
    """
    bateria = Bateria(
        capacidad=Energia(1_000),
        potencia_max_carga=Potencia(3),
        potencia_max_descarga=Potencia(500),
        eficiencia_carga=Eficiencia.de_porcentaje(95),
        eficiencia_descarga=Eficiencia.de_porcentaje(100),
        soc_min=Soc.de_porcentaje(0),
        soc_max=Soc.de_porcentaje(100),
        throughput_garantia=Energia(1_000_000),
    )
    planta = Planta("planta-deriva", bateria, Potencia(1_000_000), Potencia(0))
    politica = PoliticaDespacho(
        id="deriva",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=11,
        resolucion=UNA_HORA,
        semilla=0,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
    )
    puntos = [PuntoPronostico(Potencia(3), Precio(0)) for _ in range(10)]
    puntos.append(PuntoPronostico(Potencia(0), Precio(90_000_000)))  # la punta cara
    plan = OptimizadorLP().optimizar(
        planta, EstadoBateria(Energia(0)), Escenario(tuple(puntos)), politica
    )

    ultima = plan.acciones[-1]
    assert ultima.tipo is TipoAccion.DESCARGAR  # recortada, no anulada
    assert 0 < ultima.potencia.w < 27  # menos que el plan continuo, pero no cero

    # y el plan sigue siendo factible de punta a punta
    modelo = ModeloBateria()
    estado = EstadoBateria(Energia(0))
    for accion in plan.acciones:
        estado = modelo.aplicar(bateria, estado, accion, UNA_HORA)
