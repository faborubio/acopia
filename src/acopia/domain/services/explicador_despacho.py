"""ExplicadorDespacho: por qué el plan cargó/descargó/retuvo en cada intervalo (§5).

Es la explicabilidad que la capa MCP expone al operador ("¿por qué cargaste a
mediodía?"). Puro y determinista: todo sale del plan + el rastro as-seen (ADR-007),
sin heurísticas externas — la explicación es reconstruible igual que el plan.
"""

from __future__ import annotations

from dataclasses import dataclass

from acopia.domain.entities.accion_despacho import TipoAccion
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.rastro import RastroDespacho
from acopia.domain.services.modelo_bateria import ModeloBateria
from acopia.domain.value_objects.intervalo import Intervalo

_BASE = 10_000


@dataclass(frozen=True, slots=True)
class ExplicacionIntervalo:
    """Explicación estructurada de la decisión de un intervalo."""

    intervalo: int
    accion: str  # CARGAR | DESCARGAR | RETENER
    potencia_w: int
    cmg_mills_por_mwh: int
    percentil_cmg_bp: int  # posición del CMg dentro del horizonte (0 = el más barato)
    energia_antes_wh: int
    energia_despues_wh: int
    energia_vertida_wh: int
    reserva_w: int
    motivo: str


class ExplicadorDespacho:
    """Reconstruye la lógica económica de cada decisión del plan. Puro."""

    def __init__(self) -> None:
        self._modelo = ModeloBateria()

    def explicar(
        self,
        bateria: Bateria,
        plan: PlanDespacho,
        rastro: RastroDespacho,
        resolucion: Intervalo,
    ) -> tuple[ExplicacionIntervalo, ...]:
        """Explica todos los intervalos, reproduciendo la trayectoria de SoC."""
        escenario = rastro.escenarios[0]  # el escenario de referencia (puntual)
        if len(escenario) != len(plan):
            raise ValueError(
                f"El rastro tiene {len(escenario)} puntos; el plan {len(plan)} acciones"
            )
        precios = [p.cmg.mills_por_mwh for p in escenario.puntos]
        orden = sorted(precios)

        explicaciones: list[ExplicacionIntervalo] = []
        estado = rastro.estado_inicial
        for k, accion in enumerate(plan.acciones):
            antes = estado.energia_almacenada.wh
            estado = self._modelo.aplicar(bateria, estado, accion, resolucion)
            cmg = precios[k]
            percentil = (orden.index(cmg) * _BASE) // max(1, len(precios) - 1)
            reserva = plan.reserva_w[k] if plan.reserva_w else 0
            explicaciones.append(
                ExplicacionIntervalo(
                    intervalo=k,
                    accion=accion.tipo.value,
                    potencia_w=accion.potencia.w,
                    cmg_mills_por_mwh=cmg,
                    percentil_cmg_bp=percentil,
                    energia_antes_wh=antes,
                    energia_despues_wh=estado.energia_almacenada.wh,
                    energia_vertida_wh=plan.energia_vertida_wh[k],
                    reserva_w=reserva,
                    motivo=self._motivo(
                        accion.tipo, percentil, plan.energia_vertida_wh[k], reserva, cmg
                    ),
                )
            )
        return tuple(explicaciones)

    @staticmethod
    def _motivo(
        tipo: TipoAccion,
        percentil_bp: int,
        vertido_wh: int,
        reserva_w: int,
        cmg: int,
    ) -> str:
        """Relato determinista de la decisión, en términos del dominio."""
        posicion = (
            "de los más baratos del horizonte"
            if percentil_bp <= 3_333
            else "de los más caros del horizonte"
            if percentil_bp >= 6_667
            else "intermedio en el horizonte"
        )
        if tipo is TipoAccion.CARGAR:
            motivo = (
                f"Carga: el CMg ({cmg} mills/MWh) es {posicion}; "
                "almacena para vender más caro."
            )
            if cmg <= 0:
                motivo += " Con CMg <= 0, inyectar pagaría por generar: absorber es lo óptimo."
        elif tipo is TipoAccion.DESCARGAR:
            motivo = f"Descarga: el CMg ({cmg} mills/MWh) es {posicion}; vende lo almacenado."
        else:
            motivo = (
                f"Retiene: el CMg ({cmg} mills/MWh) es {posicion}; "
                "no hay diferencial que capturar."
            )
            if reserva_w > 0:
                motivo += " Mantiene headroom para la banda SSCC comprometida."
        if vertido_wh > 0:
            motivo += f" Vierte {vertido_wh} Wh (excedente sobre el nodo o CMg sin valor)."
        return motivo
