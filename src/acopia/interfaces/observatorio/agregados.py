"""Agregados del vertimiento para las páginas del Observatorio (ADR-012).

Funciones puras sobre los registros de `leer_reducciones_erv`. Todo se recalcula
desde los valores horarios por central — nunca desde los totales del libro.
"""

from __future__ import annotations

from collections.abc import Iterable

from acopia.infrastructure.ingesta.reducciones_erv import ReduccionDiaria

_HORAS = 24


def total_mensual_gwh(registros: Iterable[ReduccionDiaria]) -> dict[tuple[str, str], float]:
    """Vertimiento total por (mes ``YYYY-MM``, tecnología), en GWh."""
    totales: dict[tuple[str, str], float] = {}
    for registro in registros:
        clave = (registro.fecha[:7], registro.tecnologia)
        totales[clave] = totales.get(clave, 0.0) + registro.total_mwh / 1000.0
    return totales


def perfil_horario_mwh(registros: Iterable[ReduccionDiaria]) -> dict[str, tuple[float, ...]]:
    """Suma por hora del día (1..24) por tecnología, en MWh.

    Es la foto de la tesis: el vertimiento solar se concentra en las horas de
    mediodía, exactamente cuando el CMg colapsa.
    """
    perfiles: dict[str, list[float]] = {}
    for registro in registros:
        acumulado = perfiles.setdefault(registro.tecnologia, [0.0] * _HORAS)
        for i, mwh in enumerate(registro.energia_mwh):
            acumulado[i] += mwh
    return {tecnologia: tuple(valores) for tecnologia, valores in perfiles.items()}


def top_centrales(
    registros: Iterable[ReduccionDiaria], n: int = 10
) -> list[tuple[str, str, float]]:
    """Las ``n`` centrales con más vertimiento: ``(central, tecnología, total MWh)``.

    Orden descendente por energía; a igual energía, alfabético (determinista).
    """
    totales: dict[tuple[str, str], float] = {}
    for registro in registros:
        clave = (registro.central, registro.tecnologia)
        totales[clave] = totales.get(clave, 0.0) + registro.total_mwh
    ordenadas = sorted(totales.items(), key=lambda par: (-par[1], par[0]))
    return [(central, tecnologia, total) for (central, tecnologia), total in ordenadas[:n]]
