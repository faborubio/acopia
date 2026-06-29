"""Función objetivo: ingreso esperado de un plan, calculado de forma pura y auditable.

Convención de inyección a la red por intervalo (Wh, con signo):
    inyectado = generacion_PV + descarga_AC - carga_AC
El ingreso usa el CMg del escenario; la energía retirada de la red (inyección
negativa, p. ej. cargar desde la red) se valoriza al mismo CMg, así que resta.
Opcionalmente descuenta el costo de ciclado (degradación) sobre la energía de celdas.
"""

from __future__ import annotations

from acopia.domain.entities.accion_despacho import TipoAccion
from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.politica_despacho import PoliticaDespacho
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.intervalo import Intervalo

_WH_POR_MWH = 1_000_000


class FuncionObjetivo:
    """Valoriza un plan contra un escenario. Pura y determinista."""

    def ingreso_bruto(
        self,
        plan: PlanDespacho,
        escenario: Escenario,
        resolucion: Intervalo,
    ) -> int:
        """Ingreso en mills por la energía neta inyectada (sin costo de ciclado)."""
        total = 0
        for accion, punto in zip(plan.acciones, escenario.puntos, strict=True):
            generacion = punto.generacion.energia_en(resolucion).wh
            carga = descarga = 0
            if accion.tipo is TipoAccion.CARGAR:
                carga = accion.potencia.energia_en(resolucion).wh
            elif accion.tipo is TipoAccion.DESCARGAR:
                descarga = accion.potencia.energia_en(resolucion).wh
            inyectado = generacion + descarga - carga
            total += punto.cmg.ingreso_por_wh(inyectado)
        return total

    def costo_ciclado(
        self,
        plan: PlanDespacho,
        politica: PoliticaDespacho,
        carga_eff: Eficiencia,
        descarga_eff: Eficiencia,
    ) -> int:
        """Costo de degradación (mills) por la energía que pasa por las celdas."""
        if politica.costo_ciclado_mills_por_mwh == 0:
            return 0
        celdas = 0
        for accion in plan.acciones:
            energia_ac = accion.potencia.energia_en(politica.resolucion)
            if accion.tipo is TipoAccion.CARGAR:
                celdas += carga_eff.aplicar(energia_ac).wh
            elif accion.tipo is TipoAccion.DESCARGAR:
                celdas += descarga_eff.revertir(energia_ac).wh
        return (politica.costo_ciclado_mills_por_mwh * celdas) // _WH_POR_MWH
