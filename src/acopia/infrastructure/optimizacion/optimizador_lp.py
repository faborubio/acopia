"""Optimizador de despacho predict-then-optimize determinista (LP, cvxpy + HIGHS).

Resuelve el arbitraje de CMg de una planta PV-BESS sobre un único escenario
(caso medio). El problema es lineal: con eficiencia < 1 y costo de ciclado >= 0,
el óptimo nunca carga y descarga a la vez, así que un LP basta (sin binarias).

Frontera: este adaptador vive en `infrastructure/` (usa cvxpy/numpy). El plan que
devuelve se **cuantiza a unidades enteras** y se valida contra el `ModeloBateria`
del dominio, de modo que la salida es siempre factible y auditable.
"""

from __future__ import annotations

import cvxpy as cp
import numpy as np

from acopia.domain.entities.accion_despacho import AccionDespacho
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.politica_despacho import PoliticaDespacho
from acopia.domain.services.funcion_objetivo import FuncionObjetivo
from acopia.domain.services.modelo_bateria import ModeloBateria
from acopia.domain.value_objects.potencia import Potencia

_BASE = 10_000


class OptimizadorLP:
    """Implementa `PuertoOptimizador` con un LP determinista resuelto por HIGHS."""

    def __init__(self) -> None:
        self._modelo = ModeloBateria()
        self._objetivo = FuncionObjetivo()

    def optimizar(
        self,
        bateria: Bateria,
        estado_inicial: EstadoBateria,
        escenario: Escenario,
        politica: PoliticaDespacho,
    ) -> PlanDespacho:
        horizonte = politica.horizonte_intervalos
        if len(escenario) != horizonte:
            raise ValueError(
                f"El escenario tiene {len(escenario)} puntos; la política espera {horizonte}"
            )

        carga_ac, descarga_ac = self._resolver(bateria, estado_inicial, escenario, politica)
        acciones = self._a_plan_factible(bateria, estado_inicial, politica, carga_ac, descarga_ac)

        plan_provisional = PlanDespacho(
            politica_id=politica.id,
            politica_version=politica.version,
            semilla=politica.semilla,
            acciones=acciones,
            ingreso_esperado_mills=0,
        )
        ingreso = self._objetivo.ingreso_bruto(
            plan_provisional, escenario, politica.resolucion
        ) - self._objetivo.costo_ciclado(
            plan_provisional, politica, bateria.eficiencia_carga, bateria.eficiencia_descarga
        )
        return PlanDespacho(
            politica_id=politica.id,
            politica_version=politica.version,
            semilla=politica.semilla,
            acciones=acciones,
            ingreso_esperado_mills=ingreso,
        )

    # ------------------------------------------------------------------ #
    # LP continuo (cvxpy)
    # ------------------------------------------------------------------ #

    def _resolver(
        self,
        bateria: Bateria,
        estado_inicial: EstadoBateria,
        escenario: Escenario,
        politica: PoliticaDespacho,
    ) -> tuple[np.ndarray, np.ndarray]:
        t = politica.horizonte_intervalos
        resolucion = politica.resolucion
        ef_c = bateria.eficiencia_carga.puntos_base / _BASE
        ef_d = bateria.eficiencia_descarga.puntos_base / _BASE

        cmax = float(bateria.potencia_max_carga.energia_en(resolucion).wh)
        dmax = float(bateria.potencia_max_descarga.energia_en(resolucion).wh)
        e_min = float(bateria.energia_min.wh)
        e_max = float(bateria.energia_max.wh)
        e0 = float(estado_inicial.energia_almacenada.wh)
        throughput_budget = float(
            bateria.throughput_garantia.wh - estado_inicial.throughput_acumulado.wh
        )

        generacion = np.array(
            [p.generacion.energia_en(resolucion).wh for p in escenario.puntos], dtype=float
        )
        # Precio por Wh (mills/Wh) = CMg[mills/MWh] / 1e6
        precio = np.array([p.cmg.mills_por_mwh for p in escenario.puntos], dtype=float) / 1e6

        carga = cp.Variable(t, nonneg=True)
        descarga = cp.Variable(t, nonneg=True)
        energia = cp.Variable(t)
        celdas = ef_c * carga + descarga / ef_d  # energía a través de las celdas

        restricciones = [carga <= cmax, descarga <= dmax, energia >= e_min, energia <= e_max]
        restricciones.append(energia[0] == e0 + ef_c * carga[0] - descarga[0] / ef_d)
        for k in range(1, t):
            restricciones.append(
                energia[k] == energia[k - 1] + ef_c * carga[k] - descarga[k] / ef_d
            )
        restricciones.append(cp.sum(celdas) <= throughput_budget)

        inyectado = generacion + descarga - carga
        ingreso = precio @ inyectado
        costo = (politica.costo_ciclado_mills_por_mwh / 1e6) * cp.sum(celdas)
        problema = cp.Problem(cp.Maximize(ingreso - costo), restricciones)
        problema.solve(solver=cp.HIGHS)

        if problema.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            raise RuntimeError(f"El optimizador no encontró solución: status={problema.status}")

        return np.asarray(carga.value), np.asarray(descarga.value)

    # ------------------------------------------------------------------ #
    # Cuantización entera + factibilidad garantizada por el dominio
    # ------------------------------------------------------------------ #

    def _a_plan_factible(
        self,
        bateria: Bateria,
        estado_inicial: EstadoBateria,
        politica: PoliticaDespacho,
        carga_ac: np.ndarray,
        descarga_ac: np.ndarray,
    ) -> tuple[AccionDespacho, ...]:
        resolucion = politica.resolucion
        segundos = resolucion.segundos
        acciones: list[AccionDespacho] = []
        estado = estado_inicial

        for k in range(politica.horizonte_intervalos):
            neto_ac = round(float(carga_ac[k])) - round(float(descarga_ac[k]))
            potencia_w = (abs(neto_ac) * 3600) // segundos
            if neto_ac > 0:
                pmax = bateria.potencia_max_carga.w
                accion = AccionDespacho.cargar(Potencia(min(potencia_w, pmax)))
            elif neto_ac < 0:
                pmax = bateria.potencia_max_descarga.w
                accion = AccionDespacho.descargar(Potencia(min(potencia_w, pmax)))
            else:
                accion = AccionDespacho.retener()

            if not self._modelo.es_factible(bateria, estado, accion, resolucion):
                accion = AccionDespacho.retener()  # repair conservador ante redondeo

            estado = self._modelo.aplicar(bateria, estado, accion, resolucion)
            acciones.append(accion)

        return tuple(acciones)
