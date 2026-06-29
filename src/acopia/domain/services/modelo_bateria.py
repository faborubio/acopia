"""Modelo físico de la batería: dinámica de SoC, eficiencia y throughput.

PURO: sin solver, sin IO, sin azar. Determinista — la misma entrada produce
siempre el mismo estado. Es el núcleo auditable que el optimizador respeta como
restricción dura.

Convención de signos: ``Potencia`` es el intercambio con la red (lado AC).
- CARGAR: la red entrega ``E_red``; a las celdas llega ``ef_carga · E_red``.
- DESCARGAR: la red recibe ``E_red``; las celdas entregan ``E_red / ef_descarga``.
La autodescarga se ignora a esta fidelidad (documentado como deuda de §11).
"""

from __future__ import annotations

from acopia.domain.entities.accion_despacho import AccionDespacho, TipoAccion
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo


class AccionInfactible(Exception):
    """La acción viola una restricción física de la batería (potencia, SoC o throughput)."""


class ModeloBateria:
    """Aplica acciones de despacho a la batería respetando sus restricciones duras."""

    def aplicar(
        self,
        bateria: Bateria,
        estado: EstadoBateria,
        accion: AccionDespacho,
        intervalo: Intervalo,
    ) -> EstadoBateria:
        """Devuelve el estado tras la acción, o lanza ``AccionInfactible``."""
        if accion.tipo is TipoAccion.RETENER:
            return estado
        if accion.tipo is TipoAccion.CARGAR:
            return self._cargar(bateria, estado, accion, intervalo)
        return self._descargar(bateria, estado, accion, intervalo)

    def es_factible(
        self,
        bateria: Bateria,
        estado: EstadoBateria,
        accion: AccionDespacho,
        intervalo: Intervalo,
    ) -> bool:
        """True si la acción es aplicable sin violar restricciones."""
        try:
            self.aplicar(bateria, estado, accion, intervalo)
        except AccionInfactible:
            return False
        return True

    def _cargar(
        self,
        bateria: Bateria,
        estado: EstadoBateria,
        accion: AccionDespacho,
        intervalo: Intervalo,
    ) -> EstadoBateria:
        if accion.potencia > bateria.potencia_max_carga:
            raise AccionInfactible(
                f"Potencia de carga {accion.potencia} excede el máximo "
                f"{bateria.potencia_max_carga}"
            )
        energia_red = accion.potencia.energia_en(intervalo)
        energia_celdas = bateria.eficiencia_carga.aplicar(energia_red)
        nueva = estado.energia_almacenada.wh + energia_celdas.wh
        if nueva > bateria.energia_max.wh:
            raise AccionInfactible(
                f"Cargar dejaría {nueva} Wh, sobre el máximo {bateria.energia_max.wh} Wh"
            )
        return self._con_throughput(bateria, estado, Energia(nueva), energia_celdas)

    def _descargar(
        self,
        bateria: Bateria,
        estado: EstadoBateria,
        accion: AccionDespacho,
        intervalo: Intervalo,
    ) -> EstadoBateria:
        if accion.potencia > bateria.potencia_max_descarga:
            raise AccionInfactible(
                f"Potencia de descarga {accion.potencia} excede el máximo "
                f"{bateria.potencia_max_descarga}"
            )
        energia_red = accion.potencia.energia_en(intervalo)
        energia_celdas = bateria.eficiencia_descarga.revertir(energia_red)
        nueva = estado.energia_almacenada.wh - energia_celdas.wh
        if nueva < bateria.energia_min.wh:
            raise AccionInfactible(
                f"Descargar dejaría {nueva} Wh, bajo el mínimo {bateria.energia_min.wh} Wh"
            )
        return self._con_throughput(bateria, estado, Energia(nueva), energia_celdas)

    def _con_throughput(
        self,
        bateria: Bateria,
        estado: EstadoBateria,
        nueva_almacenada: Energia,
        delta_celdas: Energia,
    ) -> EstadoBateria:
        nuevo_throughput = estado.throughput_acumulado.wh + delta_celdas.wh
        if nuevo_throughput > bateria.throughput_garantia.wh:
            raise AccionInfactible(
                f"El throughput acumulado {nuevo_throughput} Wh superaría la "
                f"garantía {bateria.throughput_garantia.wh} Wh"
            )
        return EstadoBateria(
            energia_almacenada=nueva_almacenada,
            throughput_acumulado=Energia(nuevo_throughput),
        )
