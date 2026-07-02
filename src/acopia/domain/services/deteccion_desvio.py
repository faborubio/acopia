"""Detección de desvío forecast-vs-real: el gatillo de la reoptimización intradía (§6.2).

Puro y determinista. Compara la generación PV acumulada que el plan asumió con la
observada por telemetría; si el desvío relativo supera el umbral, corresponde
reoptimizar el resto del día desde el estado real de la batería.
"""

from __future__ import annotations

from collections.abc import Sequence

from acopia.domain.entities.escenario import PuntoPronostico
from acopia.domain.entities.observacion import Observacion

_BASE = 10_000


def desvio_generacion_bp(
    previsto: Sequence[PuntoPronostico],
    observado: Sequence[Observacion],
) -> int:
    """Desvío relativo de la generación acumulada, en puntos base.

    Compara los intervalos ya transcurridos (mismo largo). Si lo previsto acumulado
    es 0 (noche), cualquier generación observada cuenta como desvío total (10000 bp).
    """
    if len(previsto) != len(observado):
        raise ValueError(
            f"previsto ({len(previsto)}) y observado ({len(observado)}) deben tener el mismo largo"
        )
    if not previsto:
        return 0
    acumulado_previsto = sum(p.generacion.w for p in previsto)
    acumulado_real = sum(o.generacion.w for o in observado)
    if acumulado_previsto == 0:
        return 0 if acumulado_real == 0 else _BASE
    return abs(acumulado_real - acumulado_previsto) * _BASE // acumulado_previsto


def hay_desvio(
    previsto: Sequence[PuntoPronostico],
    observado: Sequence[Observacion],
    umbral_bp: int,
) -> bool:
    """True si el desvío de generación supera el umbral (gatillo de reoptimización)."""
    if umbral_bp < 0:
        raise ValueError(f"El umbral no puede ser negativo: {umbral_bp}")
    return desvio_generacion_bp(previsto, observado) > umbral_bp
