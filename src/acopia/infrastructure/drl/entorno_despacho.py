"""EntornoDespacho: el problema de despacho como entorno gymnasium para DRL (ADR-005).

Un episodio recorre el horizonte de la política sobre un escenario (muestreado por
``probabilidad_bp`` en cada reset; ``options={"escenario": i}`` lo fuerza). La acción
es continua en [-1, 1]: negativa = cargar, positiva = descargar, escalada a la
potencia máxima. El entorno **recorta la acción a lo físicamente factible** (SoC,
potencia, throughput, nodo) y la valida con el ``ModeloBateria`` del dominio: el
agente no puede violar restricciones duras, solo perder ingreso.

La recompensa es el ingreso del intervalo (mills, escalado) menos el costo de
ciclado; el vertido es el **recurso analítico óptimo** dado el signo del CMg — el
mismo recurso que el LP resuelve como variable — para que la comparación entre
modos mida la calidad del *programa de batería*, no una asimetría de reglas.
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np

from acopia.domain.entities.accion_despacho import AccionDespacho, TipoAccion
from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import PoliticaDespacho
from acopia.domain.services.modelo_bateria import ModeloBateria
from acopia.domain.value_objects.potencia import Potencia

_BASE = 10_000
_WH_POR_MWH = 1_000_000


def vertido_recurso(
    generacion_wh: int,
    carga_wh: int,
    descarga_wh: int,
    iny_max_wh: int,
    retiro_max_wh: int,
    cmg_mills_por_mwh: int,
) -> int:
    """Vertimiento óptimo por intervalo dadas las acciones de batería ya fijadas.

    Con CMg >= 0 se vierte solo el excedente obligatorio sobre el techo del nodo;
    con CMg < 0 conviene verter lo máximo admisible (inyectar pagaría por generar),
    acotado para no exceder el límite de retiro. Es el recurso de segunda etapa que
    el LP obtiene como variable, resuelto en forma cerrada.
    """
    obligatorio = max(0, (generacion_wh - carga_wh + descarga_wh) - iny_max_wh)
    if cmg_mills_por_mwh >= 0:
        return min(obligatorio, generacion_wh)
    maximo = min(generacion_wh, generacion_wh + descarga_wh - carga_wh + retiro_max_wh)
    return max(obligatorio, min(maximo, generacion_wh))


class EntornoDespacho(gym.Env):  # type: ignore[misc]
    """Episodio = un horizonte de despacho; el agente decide cargar/descargar/retener."""

    def __init__(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenarios: tuple[Escenario, ...],
        politica: PoliticaDespacho,
    ) -> None:
        self._planta = planta
        self._estado_inicial = estado_inicial
        self._escenarios = escenarios
        self._politica = politica
        self._modelo = ModeloBateria()
        self._horizonte = politica.horizonte_intervalos
        resolucion = politica.resolucion
        bateria = planta.bateria
        self._cmax_wh = bateria.potencia_max_carga.energia_en(resolucion).wh
        self._dmax_wh = bateria.potencia_max_descarga.energia_en(resolucion).wh
        self._iny_max_wh = planta.potencia_max_inyeccion.energia_en(resolucion).wh
        self._retiro_max_wh = planta.potencia_max_retiro.energia_en(resolucion).wh
        self._e_min = bateria.energia_min.wh
        self._e_max = bateria.energia_max.wh

        # Series por escenario (Wh y mills/MWh) + constantes de normalización.
        self._gen_wh = [
            [p.generacion.energia_en(resolucion).wh for p in e.puntos] for e in escenarios
        ]
        self._cmg = [[p.cmg.mills_por_mwh for p in e.puntos] for e in escenarios]
        self._gen_norm = float(max(1, max(max(fila) for fila in self._gen_wh)))
        self._cmg_norm = float(max(1, max(max(abs(c) for c in fila) for fila in self._cmg)))
        pesos = np.array([e.probabilidad_bp for e in escenarios], dtype=float)
        self._pesos = pesos / pesos.sum()
        paso_max = max(self._cmax_wh, self._dmax_wh, int(self._gen_norm))
        self._escala_reward = max(1.0, self._cmg_norm * paso_max / _WH_POR_MWH)

        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(5,), dtype=np.float32
        )
        self.action_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)
        self._escenario_actual = 0
        self._k = 0
        self._estado = estado_inicial

    # ------------------------------------------------------------------ #
    # API gymnasium
    # ------------------------------------------------------------------ #

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        if options is not None and "escenario" in options:
            self._escenario_actual = int(options["escenario"])
        else:
            self._escenario_actual = int(
                self.np_random.choice(len(self._escenarios), p=self._pesos)
            )
        self._k = 0
        self._estado = self._estado_inicial
        return self._observacion(), {}

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        a = float(np.clip(np.asarray(action).reshape(-1)[0], -1.0, 1.0))
        k = self._k
        gen_wh = self._gen_wh[self._escenario_actual][k]
        cmg = self._cmg[self._escenario_actual][k]

        accion = self._accion_factible(a, gen_wh)
        if not self._modelo.es_factible(
            self._planta.bateria, self._estado, accion, self._politica.resolucion
        ):
            accion = AccionDespacho.retener()  # borde de redondeo: repair conservador
        self._estado = self._modelo.aplicar(
            self._planta.bateria, self._estado, accion, self._politica.resolucion
        )

        carga_wh = descarga_wh = celdas_wh = 0
        bateria = self._planta.bateria
        if accion.tipo is TipoAccion.CARGAR:
            carga_wh = accion.potencia.energia_en(self._politica.resolucion).wh
            celdas_wh = bateria.eficiencia_carga.aplicar(
                accion.potencia.energia_en(self._politica.resolucion)
            ).wh
        elif accion.tipo is TipoAccion.DESCARGAR:
            descarga_wh = accion.potencia.energia_en(self._politica.resolucion).wh
            celdas_wh = bateria.eficiencia_descarga.revertir(
                accion.potencia.energia_en(self._politica.resolucion)
            ).wh

        vertido = vertido_recurso(
            gen_wh, carga_wh, descarga_wh, self._iny_max_wh, self._retiro_max_wh, cmg
        )
        inyectado = gen_wh - vertido + descarga_wh - carga_wh
        ingreso = (cmg * inyectado) // _WH_POR_MWH
        ciclado = (self._politica.costo_ciclado_mills_por_mwh * celdas_wh) // _WH_POR_MWH
        recompensa = float(ingreso - ciclado)

        self._k += 1
        terminado = self._k == self._horizonte
        if terminado and self._politica.precio_energia_final_mills_por_mwh is not None:
            energia_util = self._estado.energia_almacenada.wh - self._e_min
            recompensa += float(
                (self._politica.precio_energia_final_mills_por_mwh * energia_util)
                // _WH_POR_MWH
            )
        info = {"accion": accion, "vertido_wh": vertido}
        return self._observacion(), recompensa / self._escala_reward, terminado, False, info

    # ------------------------------------------------------------------ #
    # Física: recorte de la acción a lo factible
    # ------------------------------------------------------------------ #

    def _accion_factible(self, a: float, gen_wh: int) -> AccionDespacho:
        """Convierte la acción [-1, 1] en una AccionDespacho dentro de los límites duros."""
        bateria = self._planta.bateria
        e = self._estado.energia_almacenada.wh
        budget = bateria.throughput_garantia.wh - self._estado.throughput_acumulado.wh
        segundos = self._politica.resolucion.segundos

        if a < 0:  # cargar
            ef_c = bateria.eficiencia_carga.puntos_base
            if ef_c == 0:
                return AccionDespacho.retener()
            deseo = round(-a * self._cmax_wh)
            tope = min(
                self._cmax_wh,
                ((self._e_max - e) * _BASE) // ef_c,  # espacio de SoC
                (budget * _BASE) // ef_c,  # throughput de garantía restante
                gen_wh + self._retiro_max_wh,  # límite de retiro del nodo
            )
            e_red = max(0, min(deseo, tope))
            potencia_w = min((e_red * 3600) // segundos, bateria.potencia_max_carga.w)
            if potencia_w == 0:
                return AccionDespacho.retener()
            return AccionDespacho.cargar(Potencia(potencia_w))

        if a > 0:  # descargar
            ef_d = bateria.eficiencia_descarga.puntos_base
            deseo = round(a * self._dmax_wh)
            tope = min(
                self._dmax_wh,
                ((e - self._e_min) * ef_d) // _BASE,  # energía disponible sobre el mínimo
                (budget * ef_d) // _BASE,  # throughput de garantía restante
                self._iny_max_wh,  # la descarga debe caber en el nodo
            )
            e_red = max(0, min(deseo, tope))
            potencia_w = min((e_red * 3600) // segundos, bateria.potencia_max_descarga.w)
            if potencia_w == 0:
                return AccionDespacho.retener()
            return AccionDespacho.descargar(Potencia(potencia_w))

        return AccionDespacho.retener()

    def _observacion(self) -> np.ndarray:
        k = min(self._k, self._horizonte - 1)
        banda = self._e_max - self._e_min
        soc = (self._estado.energia_almacenada.wh - self._e_min) / banda if banda else 0.0
        cmg = self._cmg[self._escenario_actual]
        futuros = cmg[k + 1 :]
        cmg_futuro = (sum(futuros) / len(futuros)) if futuros else 0.0
        return np.array(
            [
                soc,
                self._k / self._horizonte,
                self._gen_wh[self._escenario_actual][k] / self._gen_norm,
                cmg[k] / self._cmg_norm,
                cmg_futuro / self._cmg_norm,
            ],
            dtype=np.float32,
        )
