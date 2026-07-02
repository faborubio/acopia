"""Producto de servicios complementarios (SSCC): reserva de frecuencia (§3.0 del SAD).

Decisión de alcance (Fase 4): **un solo producto**, una banda **simétrica** de
reserva de frecuencia remunerada por **disponibilidad** — la planta compromete ±R de
headroom de potencia por intervalo y cobra por tenerlo, se active o no. El settlement
de la energía activada queda fuera del MVP (documentado, no modelado).

El precio de disponibilidad es constante en la política: la remuneración chilena de
SSCC (subastas/regulada) se acerca más a un precio fijo que a un spot horario.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReservaFrecuencia:
    """Banda simétrica de reserva de frecuencia, remunerada por disponibilidad.

    ``banda_max_w`` es el techo de banda ofertable (por habilitación/producto), no
    la potencia de la batería: el optimizador decide cuánta banda comprometer en
    cada intervalo compitiendo con el arbitraje por la misma potencia y energía.
    """

    precio_disponibilidad_mills_por_mwh: int
    banda_max_w: int

    def __post_init__(self) -> None:
        if self.precio_disponibilidad_mills_por_mwh < 0:
            raise ValueError("El precio de disponibilidad no puede ser negativo")
        if self.banda_max_w < 1:
            raise ValueError(f"La banda máxima debe ser >= 1 W: {self.banda_max_w}")
