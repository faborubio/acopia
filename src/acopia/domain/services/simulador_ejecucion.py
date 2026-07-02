"""SimuladorEjecucion: ejecuta un plan contra lo que realmente pasó (§6.3 del SAD).

Puro y determinista. El plan se planificó sobre un forecast; aquí se confronta con
la generación y el CMg **reales**. Reglas de ejecución (conservadoras y auditables):

- Una acción que la batería no puede ejecutar (redondeos, estado distinto al
  previsto) se **repara a RETENER**.
- Una carga que exigiría retirar de la red más allá del límite del nodo (el PV real
  no alcanza) también se repara a RETENER: el plan era inejecutable ese intervalo.
- El vertido realizado toma el planificado (decisión voluntaria, p. ej. CMg negativo)
  elevado al **excedente obligatorio** sobre el techo de inyección, acotado al PV real.

Límite honesto (SAD §6.3): asume que las órdenes ejecutables se ejecutan; los
desvíos de ejecución real se documentan, no se modelan.
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.entities.accion_despacho import AccionDespacho, TipoAccion
from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import PoliticaDespacho
from acopia.domain.services.funcion_objetivo import FuncionObjetivo
from acopia.domain.services.modelo_bateria import ModeloBateria
from acopia.domain.value_objects.intervalo import Intervalo


@dataclass(frozen=True, slots=True)
class ResultadoEjecucion:
    """Lo que de verdad pasó al ejecutar el plan contra el día real."""

    acciones_realizadas: tuple[AccionDespacho, ...]
    energia_vertida_wh: tuple[int, ...]
    ingreso_realizado_mills: int
    acciones_reparadas: int  # intervalos donde el plan fue inejecutable
    estado_final: EstadoBateria


class SimuladorEjecucion:
    """Confronta un plan con el escenario real. Puro (solo dominio)."""

    def __init__(self) -> None:
        self._modelo = ModeloBateria()
        self._objetivo = FuncionObjetivo()

    def ejecutar(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        plan: PlanDespacho,
        escenario_real: Escenario,
        politica: PoliticaDespacho,
    ) -> ResultadoEjecucion:
        if len(escenario_real) != len(plan):
            raise ValueError(
                f"El escenario real tiene {len(escenario_real)} puntos; "
                f"el plan tiene {len(plan)}"
            )
        resolucion = politica.resolucion
        iny_max_wh = planta.potencia_max_inyeccion.energia_en(resolucion).wh
        retiro_max_wh = planta.potencia_max_retiro.energia_en(resolucion).wh

        acciones: list[AccionDespacho] = []
        vertidos: list[int] = []
        reparadas = 0
        estado = estado_inicial
        for k, accion_plan in enumerate(plan.acciones):
            generacion_wh = escenario_real.puntos[k].generacion.energia_en(resolucion).wh
            accion = accion_plan
            if not self._es_ejecutable(
                planta, estado, accion, resolucion, generacion_wh, retiro_max_wh
            ):
                accion = AccionDespacho.retener()
                reparadas += 1
            estado = self._modelo.aplicar(planta.bateria, estado, accion, resolucion)
            acciones.append(accion)
            vertidos.append(
                self._vertido_realizado(
                    generacion_wh, accion, resolucion, iny_max_wh, plan.energia_vertida_wh[k]
                )
            )

        realizado = PlanDespacho(
            politica_id=plan.politica_id,
            politica_version=plan.politica_version,
            semilla=plan.semilla,
            acciones=tuple(acciones),
            energia_vertida_wh=tuple(vertidos),
            ingreso_esperado_mills=0,
        )
        ingreso = self._objetivo.ingreso_bruto(
            realizado, escenario_real, resolucion
        ) - self._objetivo.costo_ciclado(
            realizado,
            politica,
            planta.bateria.eficiencia_carga,
            planta.bateria.eficiencia_descarga,
        )
        return ResultadoEjecucion(
            acciones_realizadas=tuple(acciones),
            energia_vertida_wh=tuple(vertidos),
            ingreso_realizado_mills=ingreso,
            acciones_reparadas=reparadas,
            estado_final=estado,
        )

    def _es_ejecutable(
        self,
        planta: Planta,
        estado: EstadoBateria,
        accion: AccionDespacho,
        resolucion: Intervalo,
        generacion_wh: int,
        retiro_max_wh: int,
    ) -> bool:
        if not self._modelo.es_factible(planta.bateria, estado, accion, resolucion):
            return False
        if accion.tipo is TipoAccion.CARGAR:
            # La energía de carga sale del PV real o de la red (hasta el retiro máx.).
            carga_wh = accion.potencia.energia_en(resolucion).wh
            return carga_wh <= generacion_wh + retiro_max_wh
        return True

    @staticmethod
    def _vertido_realizado(
        generacion_wh: int,
        accion: AccionDespacho,
        resolucion: Intervalo,
        iny_max_wh: int,
        vertido_plan: int,
    ) -> int:
        """Vertido planificado elevado al excedente obligatorio, acotado al PV real."""
        carga = descarga = 0
        if accion.tipo is TipoAccion.CARGAR:
            carga = accion.potencia.energia_en(resolucion).wh
        elif accion.tipo is TipoAccion.DESCARGAR:
            descarga = accion.potencia.energia_en(resolucion).wh
        excedente = (generacion_wh - carga + descarga) - iny_max_wh
        return min(max(vertido_plan, excedente, 0), generacion_wh)
