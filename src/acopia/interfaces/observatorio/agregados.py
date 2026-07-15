"""Agregados del vertimiento para las páginas del Observatorio (ADR-012).

Funciones puras sobre los registros de `leer_reducciones_erv`. Todo se recalcula
desde los valores horarios por central — nunca desde los totales del libro.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

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


def duck_curve_usd_mwh(serie_cmg: Sequence[tuple[str, int]]) -> tuple[float, ...]:
    """Promedio del CMg por hora del día (0..23), en USD/MWh.

    ``serie_cmg`` es la serie ``(timestamp ISO, mills/MWh entero)`` que entrega la
    ingesta (`leer_serie`); la hora se toma del timestamp. Exige cobertura de las
    24 horas: una hora sin observaciones es señal de serie mal leída, no un cero.
    """
    sumas = [0.0] * _HORAS
    cuentas = [0] * _HORAS
    for timestamp, mills in serie_cmg:
        hora = int(timestamp[11:13])
        sumas[hora] += mills
        cuentas[hora] += 1
    sin_datos = [h for h in range(_HORAS) if cuentas[h] == 0]
    if sin_datos:
        raise ValueError(f"La serie de CMg no cubre las horas {sin_datos}; ¿serie truncada?")
    return tuple(sumas[h] / cuentas[h] / 1000.0 for h in range(_HORAS))


def valor_desplazamiento_usd(
    perfil_vertido_mwh: Sequence[float],
    cmg_usd_mwh: Sequence[float],
    eficiencia: float = 0.85,
) -> float:
    """Valor del desplazamiento a la punta (ADR-012.2), en USD.

    ``Σ_h E_h · max(0, η·CMg_punta - CMg_h)``: qué valdría la energía vertida si se
    almacenara (con eficiencia de ida y vuelta ``η``) y se vendiera en la hora punta,
    neto de lo que valía en su hora (≈0 cuando se vierte — la regla de honestidad del
    ADR-012 exige el diferencial, no el spot ni la punta a secas).

    Alineación de índices: el perfil ERV usa hora oficial 1..24 (índice 0 = 00-01 h)
    y la duck curve hora 0..23 del timestamp — el índice ``h`` coincide.
    """
    if not 0.0 < eficiencia <= 1.0:
        raise ValueError(f"Eficiencia de ida y vuelta fuera de (0, 1]: {eficiencia}")
    punta = max(cmg_usd_mwh)
    return sum(
        vertido * max(0.0, eficiencia * punta - cmg)
        for vertido, cmg in zip(perfil_vertido_mwh, cmg_usd_mwh, strict=True)
    )


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
