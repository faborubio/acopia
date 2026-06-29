"""Optimizador de despacho predict-then-optimize determinista (LP, cvxpy + HIGHS).

Resuelve el arbitraje de CMg de una planta PV-BESS sobre un único escenario
(caso medio), respetando el **límite de inyección del punto de conexión** y
modelando el **vertimiento** (curtailment): cuando la generación más la descarga
superan el techo del nodo, el excedente se almacena o se vierte.

El problema es lineal: con eficiencia < 1 y costo de ciclado >= 0 el óptimo nunca
carga y descarga a la vez. El plan continuo se **cuantiza a unidades enteras** y
se valida contra el `ModeloBateria` del dominio: la salida es siempre factible.
"""

from __future__ import annotations

import cvxpy as cp
import numpy as np

from acopia.domain.entities.accion_despacho import AccionDespacho, TipoAccion
from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import PoliticaDespacho
from acopia.domain.services.funcion_objetivo import FuncionObjetivo
from acopia.domain.services.modelo_bateria import ModeloBateria
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia

_BASE = 10_000


class OptimizadorLP:
    """Implementa `PuertoOptimizador` con un LP determinista resuelto por HIGHS."""

    def __init__(self) -> None:
        self._modelo = ModeloBateria()
        self._objetivo = FuncionObjetivo()

    def optimizar(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenario: Escenario,
        politica: PoliticaDespacho,
    ) -> PlanDespacho:
        horizonte = politica.horizonte_intervalos
        if len(escenario) != horizonte:
            raise ValueError(
                f"El escenario tiene {len(escenario)} puntos; la política espera {horizonte}"
            )
        e0 = estado_inicial.energia_almacenada.wh
        if not planta.bateria.energia_min.wh <= e0 <= planta.bateria.energia_max.wh:
            raise ValueError(
                f"El estado inicial ({e0} Wh) está fuera de la banda operativa "
                f"[{planta.bateria.energia_min.wh}, {planta.bateria.energia_max.wh}] Wh"
            )

        carga_ac, descarga_ac, vertido_ac = self._resolver(
            planta, estado_inicial, escenario, politica
        )
        acciones, vertidos = self._a_plan_factible(
            planta, estado_inicial, escenario, politica, carga_ac, descarga_ac, vertido_ac
        )

        plan_provisional = PlanDespacho(
            politica_id=politica.id,
            politica_version=politica.version,
            semilla=politica.semilla,
            acciones=acciones,
            energia_vertida_wh=vertidos,
            ingreso_esperado_mills=0,
        )
        ingreso = self._objetivo.ingreso_bruto(
            plan_provisional, escenario, politica.resolucion
        ) - self._objetivo.costo_ciclado(
            plan_provisional,
            politica,
            planta.bateria.eficiencia_carga,
            planta.bateria.eficiencia_descarga,
        )
        return PlanDespacho(
            politica_id=politica.id,
            politica_version=politica.version,
            semilla=politica.semilla,
            acciones=acciones,
            energia_vertida_wh=vertidos,
            ingreso_esperado_mills=ingreso,
        )

    # ------------------------------------------------------------------ #
    # LP continuo (cvxpy)
    # ------------------------------------------------------------------ #

    def _resolver(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenario: Escenario,
        politica: PoliticaDespacho,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        bateria = planta.bateria
        t = politica.horizonte_intervalos
        resolucion = politica.resolucion
        ef_c = bateria.eficiencia_carga.puntos_base / _BASE
        ef_d = bateria.eficiencia_descarga.puntos_base / _BASE

        cmax = float(bateria.potencia_max_carga.energia_en(resolucion).wh)
        dmax = float(bateria.potencia_max_descarga.energia_en(resolucion).wh)
        iny_max = float(planta.potencia_max_inyeccion.energia_en(resolucion).wh)
        retiro_max = float(planta.potencia_max_retiro.energia_en(resolucion).wh)
        e_min = float(bateria.energia_min.wh)
        e_max = float(bateria.energia_max.wh)
        e0 = float(estado_inicial.energia_almacenada.wh)
        throughput_budget = float(
            bateria.throughput_garantia.wh - estado_inicial.throughput_acumulado.wh
        )

        generacion = np.array(
            [p.generacion.energia_en(resolucion).wh for p in escenario.puntos], dtype=float
        )
        precio = np.array([p.cmg.mills_por_mwh for p in escenario.puntos], dtype=float) / 1e6

        carga = cp.Variable(t, nonneg=True)
        descarga = cp.Variable(t, nonneg=True)
        vertido = cp.Variable(t, nonneg=True)
        energia = cp.Variable(t)
        celdas = ef_c * carga + descarga / ef_d  # energía a través de las celdas
        inyectado = generacion - vertido + descarga - carga

        restricciones = [
            carga <= cmax,
            descarga <= dmax,
            vertido <= generacion,  # solo se puede verter PV existente
            energia >= e_min,
            energia <= e_max,
            inyectado <= iny_max,  # límite de transmisión del punto de conexión
            inyectado >= -retiro_max,
            cp.sum(celdas) <= throughput_budget,
        ]
        restricciones.append(energia[0] == e0 + ef_c * carga[0] - descarga[0] / ef_d)
        for k in range(1, t):
            restricciones.append(
                energia[k] == energia[k - 1] + ef_c * carga[k] - descarga[k] / ef_d
            )

        costo = (politica.costo_ciclado_mills_por_mwh / 1e6) * cp.sum(celdas)
        objetivo = precio @ inyectado - costo
        if politica.precio_energia_final_mills_por_mwh is not None:
            # Valoriza la energía disponible que queda al final (evita liquidarla por
            # el solo hecho de que el horizonte termina).
            precio_final = politica.precio_energia_final_mills_por_mwh / 1e6
            objetivo = objetivo + precio_final * (energia[t - 1] - e_min)
        problema = cp.Problem(cp.Maximize(objetivo), restricciones)
        problema.solve(solver=cp.HIGHS)

        if problema.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            raise RuntimeError(f"El optimizador no encontró solución: status={problema.status}")

        return np.asarray(carga.value), np.asarray(descarga.value), np.asarray(vertido.value)

    # ------------------------------------------------------------------ #
    # Cuantización entera + factibilidad garantizada por el dominio
    # ------------------------------------------------------------------ #

    def _a_plan_factible(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenario: Escenario,
        politica: PoliticaDespacho,
        carga_ac: np.ndarray,
        descarga_ac: np.ndarray,
        vertido_ac: np.ndarray,
    ) -> tuple[tuple[AccionDespacho, ...], tuple[int, ...]]:
        bateria = planta.bateria
        resolucion = politica.resolucion
        segundos = resolucion.segundos
        iny_max_wh = planta.potencia_max_inyeccion.energia_en(resolucion).wh
        acciones: list[AccionDespacho] = []
        vertidos: list[int] = []
        estado = estado_inicial

        for k in range(politica.horizonte_intervalos):
            neto_ac = round(float(carga_ac[k])) - round(float(descarga_ac[k]))
            potencia_w = (abs(neto_ac) * 3600) // segundos
            if neto_ac > 0:
                accion = AccionDespacho.cargar(
                    Potencia(min(potencia_w, bateria.potencia_max_carga.w))
                )
            elif neto_ac < 0:
                accion = AccionDespacho.descargar(
                    Potencia(min(potencia_w, bateria.potencia_max_descarga.w))
                )
            else:
                accion = AccionDespacho.retener()

            if not self._modelo.es_factible(bateria, estado, accion, resolucion):
                accion = AccionDespacho.retener()  # repair conservador ante redondeo

            estado = self._modelo.aplicar(bateria, estado, accion, resolucion)
            acciones.append(accion)
            vertidos.append(
                self._vertido_factible(
                    escenario.puntos[k].generacion.energia_en(resolucion).wh,
                    accion,
                    resolucion,
                    iny_max_wh,
                    round(float(vertido_ac[k])),
                )
            )

        return tuple(acciones), tuple(vertidos)

    @staticmethod
    def _vertido_factible(
        generacion_wh: int,
        accion: AccionDespacho,
        resolucion: Intervalo,
        iny_max_wh: int,
        vertido_lp: int,
    ) -> int:
        """Vertimiento entero que mantiene la inyección dentro del techo del nodo.

        Toma el máximo entre el vertimiento del LP y el excedente obligatorio sobre
        el límite de inyección, acotado a la generación disponible.
        """
        carga = descarga = 0
        if accion.tipo is TipoAccion.CARGAR:
            carga = accion.potencia.energia_en(resolucion).wh
        elif accion.tipo is TipoAccion.DESCARGAR:
            descarga = accion.potencia.energia_en(resolucion).wh
        excedente = (generacion_wh - carga + descarga) - iny_max_wh
        vertido = max(vertido_lp, excedente, 0)
        return min(vertido, generacion_wh)
