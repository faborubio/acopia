"""Optimizador de despacho predict-then-optimize determinista (LP, cvxpy + HIGHS).

Resuelve el arbitraje de CMg de una planta PV-BESS, respetando el **límite de
inyección del punto de conexión** y modelando el **vertimiento** (curtailment):
cuando la generación más la descarga superan el techo del nodo, el excedente se
almacena o se vierte.

Soporta dos modos detrás del mismo puerto:
- ``optimizar``: un único escenario (caso medio), el modo Fase 1.
- ``optimizar_escenarios``: **estocástico de dos etapas** (ADR-004). El programa de
  la batería (carga/descarga) es la decisión here-and-now común; el vertido es el
  recurso por escenario. Factible en todos los escenarios; maximiza el ingreso
  esperado ponderado por ``probabilidad_bp``.

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
        return self.optimizar_escenarios(planta, estado_inicial, (escenario,), politica)

    def optimizar_escenarios(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenarios: tuple[Escenario, ...],
        politica: PoliticaDespacho,
    ) -> PlanDespacho:
        if not escenarios:
            raise ValueError("Se requiere al menos un escenario")
        horizonte = politica.horizonte_intervalos
        for indice, escenario in enumerate(escenarios):
            if len(escenario) != horizonte:
                raise ValueError(
                    f"El escenario {indice} tiene {len(escenario)} puntos; "
                    f"la política espera {horizonte}"
                )
        e0 = estado_inicial.energia_almacenada.wh
        if not planta.bateria.energia_min.wh <= e0 <= planta.bateria.energia_max.wh:
            raise ValueError(
                f"El estado inicial ({e0} Wh) está fuera de la banda operativa "
                f"[{planta.bateria.energia_min.wh}, {planta.bateria.energia_max.wh}] Wh"
            )

        carga_ac, descarga_ac, vertidos_ac, reserva_ac = self._resolver(
            planta, estado_inicial, escenarios, politica
        )
        # La referencia del plan (acciones y vertido reportado) es el escenario 0
        # (pronóstico puntual); el recurso de los demás escenarios entra al ingreso.
        acciones, vertidos_por_escenario, reserva_w = self._a_plan_factible(
            planta, estado_inicial, escenarios, politica,
            carga_ac, descarga_ac, vertidos_ac, reserva_ac,
        )

        ingreso = self._ingreso_esperado(
            planta, escenarios, politica, acciones, vertidos_por_escenario, reserva_w
        )
        return PlanDespacho(
            politica_id=politica.id,
            politica_version=politica.version,
            semilla=politica.semilla,
            acciones=acciones,
            energia_vertida_wh=vertidos_por_escenario[0],
            ingreso_esperado_mills=ingreso,
            reserva_w=reserva_w,
        )

    def _ingreso_esperado(
        self,
        planta: Planta,
        escenarios: tuple[Escenario, ...],
        politica: PoliticaDespacho,
        acciones: tuple[AccionDespacho, ...],
        vertidos_por_escenario: tuple[tuple[int, ...], ...],
        reserva_w: tuple[int, ...],
    ) -> int:
        """Ingreso esperado (mills): energía ponderada por probabilidad_bp + reserva - ciclado.

        Cada escenario se valoriza con **su propio** vertido de recurso (mismas
        acciones de batería); la disponibilidad SSCC es determinista (no depende del
        escenario). Aritmética entera para el determinismo.
        """
        plan_base = PlanDespacho(
            politica_id=politica.id,
            politica_version=politica.version,
            semilla=politica.semilla,
            acciones=acciones,
            energia_vertida_wh=vertidos_por_escenario[0],
            ingreso_esperado_mills=0,
            reserva_w=reserva_w,
        )
        suma_ponderada = 0
        suma_pesos = 0
        for escenario, vertidos in zip(escenarios, vertidos_por_escenario, strict=True):
            plan_escenario = PlanDespacho(
                politica_id=politica.id,
                politica_version=politica.version,
                semilla=politica.semilla,
                acciones=acciones,
                energia_vertida_wh=vertidos,
                ingreso_esperado_mills=0,
            )
            bruto = self._objetivo.ingreso_bruto(plan_escenario, escenario, politica.resolucion)
            suma_ponderada += escenario.probabilidad_bp * bruto
            suma_pesos += escenario.probabilidad_bp
        esperado_bruto = suma_ponderada // suma_pesos
        return (
            esperado_bruto
            + self._objetivo.ingreso_reserva(plan_base, politica)
            - self._objetivo.costo_ciclado(
                plan_base,
                politica,
                planta.bateria.eficiencia_carga,
                planta.bateria.eficiencia_descarga,
            )
        )

    # ------------------------------------------------------------------ #
    # LP continuo (cvxpy)
    # ------------------------------------------------------------------ #

    def _resolver(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenarios: tuple[Escenario, ...],
        politica: PoliticaDespacho,
    ) -> tuple[np.ndarray, np.ndarray, list[np.ndarray], np.ndarray | None]:
        """LP de dos etapas: batería here-and-now, vertido de recurso por escenario.

        Con SSCC (``politica.reserva``) añade la banda simétrica R por intervalo:
        headroom de potencia (±R sobre el setpoint), de energía (activación sostenida
        el intervalo completo) y de inyección/retiro en **todos** los escenarios. La
        disponibilidad se remunera en el objetivo: arbitraje y reserva compiten por
        la misma batería en una sola función objetivo (§3.0).
        """
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

        # Primera etapa: el programa de la batería, común a todos los escenarios.
        carga = cp.Variable(t, nonneg=True)
        descarga = cp.Variable(t, nonneg=True)
        energia = cp.Variable(t)
        celdas = ef_c * carga + descarga / ef_d  # energía a través de las celdas

        restricciones = [
            carga <= cmax,
            descarga <= dmax,
            energia >= e_min,
            energia <= e_max,
            cp.sum(celdas) <= throughput_budget,
        ]
        restricciones.append(energia[0] == e0 + ef_c * carga[0] - descarga[0] / ef_d)
        for k in range(1, t):
            restricciones.append(
                energia[k] == energia[k - 1] + ef_c * carga[k] - descarga[k] / ef_d
            )

        # SSCC: banda simétrica de reserva de frecuencia (co-optimizada, §3.0).
        reserva: cp.Variable | None = None
        if politica.reserva is not None:
            banda_max_wh = politica.reserva.banda_max_w * resolucion.segundos / 3600
            reserva = cp.Variable(t, nonneg=True)
            restricciones += [
                reserva <= banda_max_wh,
                (descarga - carga) + reserva <= dmax,  # headroom para activar a subir
                (carga - descarga) + reserva <= cmax,  # headroom para activar a bajar
                energia - reserva / ef_d >= e_min,  # energía para sostener la activación
                energia + ef_c * reserva <= e_max,
            ]

        # Segunda etapa (recurso): vertido por escenario; factibilidad en todos.
        pesos = np.array([e.probabilidad_bp for e in escenarios], dtype=float)
        pesos = pesos / pesos.sum()
        vertidos: list[cp.Variable] = []
        ingreso_esperado: cp.Expression = cp.Constant(0)
        for escenario, peso in zip(escenarios, pesos, strict=True):
            generacion = np.array(
                [p.generacion.energia_en(resolucion).wh for p in escenario.puntos], dtype=float
            )
            precio = (
                np.array([p.cmg.mills_por_mwh for p in escenario.puntos], dtype=float) / 1e6
            )
            vertido = cp.Variable(t, nonneg=True)
            inyectado = generacion - vertido + descarga - carga
            restricciones += [
                vertido <= generacion,  # solo se puede verter PV existente
                inyectado <= iny_max,  # límite de transmisión del punto de conexión
                inyectado >= -retiro_max,
            ]
            if reserva is not None:
                # La activación (±R) también debe caber en el punto de conexión.
                restricciones += [
                    inyectado + reserva <= iny_max,
                    inyectado - reserva >= -retiro_max,
                ]
            ingreso_esperado = ingreso_esperado + peso * (precio @ inyectado)
            vertidos.append(vertido)

        costo = (politica.costo_ciclado_mills_por_mwh / 1e6) * cp.sum(celdas)
        objetivo = ingreso_esperado - costo
        if politica.reserva is not None and reserva is not None:
            precio_reserva = politica.reserva.precio_disponibilidad_mills_por_mwh / 1e6
            objetivo = objetivo + precio_reserva * cp.sum(reserva)
        if politica.precio_energia_final_mills_por_mwh is not None:
            # Valoriza la energía disponible que queda al final (evita liquidarla por
            # el solo hecho de que el horizonte termina).
            precio_final = politica.precio_energia_final_mills_por_mwh / 1e6
            objetivo = objetivo + precio_final * (energia[t - 1] - e_min)
        problema = cp.Problem(cp.Maximize(objetivo), restricciones)
        problema.solve(solver=cp.HIGHS)

        if problema.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            raise RuntimeError(f"El optimizador no encontró solución: status={problema.status}")

        return (
            np.asarray(carga.value),
            np.asarray(descarga.value),
            [np.asarray(v.value) for v in vertidos],
            np.asarray(reserva.value) if reserva is not None else None,
        )

    # ------------------------------------------------------------------ #
    # Cuantización entera + factibilidad garantizada por el dominio
    # ------------------------------------------------------------------ #

    def _a_plan_factible(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenarios: tuple[Escenario, ...],
        politica: PoliticaDespacho,
        carga_ac: np.ndarray,
        descarga_ac: np.ndarray,
        vertidos_ac: list[np.ndarray],
        reserva_ac: np.ndarray | None,
    ) -> tuple[tuple[AccionDespacho, ...], tuple[tuple[int, ...], ...], tuple[int, ...]]:
        """Cuantiza acciones (comunes), vertido de recurso por escenario y banda SSCC."""
        bateria = planta.bateria
        resolucion = politica.resolucion
        iny_max_wh = planta.potencia_max_inyeccion.energia_en(resolucion).wh
        acciones: list[AccionDespacho] = []
        vertidos: list[list[int]] = [[] for _ in escenarios]
        reservas: list[int] = []
        estado = estado_inicial

        for k in range(politica.horizonte_intervalos):
            neto_ac = round(float(carga_ac[k])) - round(float(descarga_ac[k]))
            accion = self._accion_recortada(planta, estado, escenarios, politica, k, neto_ac)
            if not self._modelo.es_factible(bateria, estado, accion, resolucion):
                accion = AccionDespacho.retener()  # última red ante bordes de redondeo

            estado = self._modelo.aplicar(bateria, estado, accion, resolucion)
            acciones.append(accion)
            vertidos_k: list[int] = []
            for s, escenario in enumerate(escenarios):
                vertido = self._vertido_factible(
                    escenario.puntos[k].generacion.energia_en(resolucion).wh,
                    accion,
                    resolucion,
                    iny_max_wh,
                    round(float(vertidos_ac[s][k])),
                )
                vertidos[s].append(vertido)
                vertidos_k.append(vertido)
            if reserva_ac is not None and politica.reserva is not None:
                reservas.append(
                    self._reserva_factible(
                        planta, politica, estado, accion, escenarios, vertidos_k, k,
                        round(float(reserva_ac[k])),
                    )
                )

        return tuple(acciones), tuple(tuple(v) for v in vertidos), tuple(reservas)

    def _accion_recortada(
        self,
        planta: Planta,
        estado: EstadoBateria,
        escenarios: tuple[Escenario, ...],
        politica: PoliticaDespacho,
        k: int,
        neto_ac_wh: int,
    ) -> AccionDespacho:
        """Acción entera recortada al máximo factible (SoC, potencia, throughput, nodo).

        Antes el repair ante un redondeo infactible era RETENER, lo que **anulaba el
        intervalo completo** — el caso real: la descarga de la hora más cara del día
        se perdía porque los floors de eficiencia acumulados dejaban 1 Wh menos que
        la trayectoria continua (hallazgo del experimento ADR-005, 2026-07-09).
        Recortar conserva el ingreso del tramo factible y de paso re-verifica el
        límite de retiro/inyección del nodo tras la cuantización (paga AUD-003).
        """
        bateria = planta.bateria
        resolucion = politica.resolucion
        segundos = resolucion.segundos
        e = estado.energia_almacenada.wh
        budget = bateria.throughput_garantia.wh - estado.throughput_acumulado.wh

        if neto_ac_wh > 0:  # cargar
            ef_c = bateria.eficiencia_carga.puntos_base
            if ef_c == 0:
                return AccionDespacho.retener()
            # El retiro del nodo debe respetarse en todos los escenarios (peor caso).
            gen_min_wh = min(
                esc.puntos[k].generacion.energia_en(resolucion).wh for esc in escenarios
            )
            retiro_max_wh = planta.potencia_max_retiro.energia_en(resolucion).wh
            tope = min(
                bateria.potencia_max_carga.energia_en(resolucion).wh,
                ((bateria.energia_max.wh - e) * _BASE) // ef_c,
                (budget * _BASE) // ef_c,
                gen_min_wh + retiro_max_wh,
            )
            e_red = min(neto_ac_wh, max(0, tope))
            potencia_w = min((e_red * 3600) // segundos, bateria.potencia_max_carga.w)
            return AccionDespacho.cargar(Potencia(potencia_w)) if potencia_w else (
                AccionDespacho.retener()
            )

        if neto_ac_wh < 0:  # descargar
            ef_d = bateria.eficiencia_descarga.puntos_base
            tope = min(
                bateria.potencia_max_descarga.energia_en(resolucion).wh,
                ((e - bateria.energia_min.wh) * ef_d) // _BASE,
                (budget * ef_d) // _BASE,
                planta.potencia_max_inyeccion.energia_en(resolucion).wh,
            )
            e_red = min(-neto_ac_wh, max(0, tope))
            potencia_w = min((e_red * 3600) // segundos, bateria.potencia_max_descarga.w)
            return AccionDespacho.descargar(Potencia(potencia_w)) if potencia_w else (
                AccionDespacho.retener()
            )

        return AccionDespacho.retener()

    def _reserva_factible(
        self,
        planta: Planta,
        politica: PoliticaDespacho,
        estado_despues: EstadoBateria,
        accion: AccionDespacho,
        escenarios: tuple[Escenario, ...],
        vertidos_k: list[int],
        k: int,
        reserva_lp_wh: int,
    ) -> int:
        """Banda entera (W) que respeta todos los headrooms tras la cuantización.

        Clamp conservador: potencia (±R sobre el setpoint), energía (activación
        sostenida el intervalo), e inyección/retiro en todos los escenarios con los
        vertidos ya cuantizados. Nunca aumenta la banda del LP, solo la recorta.
        """
        bateria = planta.bateria
        resolucion = politica.resolucion
        assert politica.reserva is not None  # invariante garantizada por el llamador
        banda_max_wh = (politica.reserva.banda_max_w * resolucion.segundos) // 3600

        carga_wh = descarga_wh = 0
        if accion.tipo is TipoAccion.CARGAR:
            carga_wh = accion.potencia.energia_en(resolucion).wh
        elif accion.tipo is TipoAccion.DESCARGAR:
            descarga_wh = accion.potencia.energia_en(resolucion).wh

        dmax_wh = bateria.potencia_max_descarga.energia_en(resolucion).wh
        cmax_wh = bateria.potencia_max_carga.energia_en(resolucion).wh
        r_wh = min(
            reserva_lp_wh,
            banda_max_wh,
            dmax_wh - (descarga_wh - carga_wh),  # headroom de potencia a subir
            cmax_wh - (carga_wh - descarga_wh),  # headroom de potencia a bajar
        )

        # Headroom de energía tras la acción (activación sostenida el intervalo).
        e_despues = estado_despues.energia_almacenada.wh
        ef_c_bp = bateria.eficiencia_carga.puntos_base
        ef_d_bp = bateria.eficiencia_descarga.puntos_base
        r_wh = min(
            r_wh,
            ((e_despues - bateria.energia_min.wh) * ef_d_bp) // _BASE,
            ((bateria.energia_max.wh - e_despues) * _BASE) // ef_c_bp,
        )

        # Headroom de inyección/retiro en todos los escenarios (vertidos cuantizados).
        iny_max_wh = planta.potencia_max_inyeccion.energia_en(resolucion).wh
        retiro_max_wh = planta.potencia_max_retiro.energia_en(resolucion).wh
        for escenario, vertido in zip(escenarios, vertidos_k, strict=True):
            generacion_wh = escenario.puntos[k].generacion.energia_en(resolucion).wh
            inyectado = generacion_wh - vertido + descarga_wh - carga_wh
            r_wh = min(r_wh, iny_max_wh - inyectado, inyectado + retiro_max_wh)

        r_wh = max(0, r_wh)
        return (r_wh * 3600) // politica.resolucion.segundos

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
