"""Helpers puros para preparar datos reales al formato de la planta modelo.

Convierten/alinean dos series horarias —CMg del Coordinador y generación PV del
Explorador Solar— en el CSV `timestamp,generacion_w,cmg_mills_por_mwh` que consume
`GatewayCSV`. Todo es función pura y testeable; el HTTP vive en la CLI.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

Serie = list[tuple[str, int]]


def parsear_decimal(texto: str) -> float:
    """Convierte un número en texto a float, tolerando la coma decimal chilena.

    - ``"57,79415"`` -> 57.79415  (coma decimal)
    - ``"1.234,56"`` -> 1234.56   (punto de miles + coma decimal)
    - ``"78500.4"`` -> 78500.4    (punto decimal estándar)
    - ``"80000"`` -> 80000.0

    Regla: si hay coma, la coma es el separador decimal y los puntos son de miles;
    si no hay coma, el punto es decimal. (Exporta sin separador de miles para evitar
    ambigüedad en valores como ``"80.000"``.)
    """
    valor = (texto or "").strip()
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    return float(valor)


def leer_serie_csv(
    ruta: Path | str,
    columna_ts: str,
    columna_valor: str,
    escala: float = 1.0,
) -> Serie:
    """Lee un CSV como serie ``(timestamp, valor_entero)``, escalando el valor.

    ``escala`` convierte unidades (p. ej. 1000 si la generación viene en kW y se
    quiere en W). El valor se redondea a entero.
    """
    ruta = Path(ruta)
    with ruta.open(newline="", encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
        faltantes = {columna_ts, columna_valor} - set(lector.fieldnames or [])
        if faltantes:
            raise ValueError(f"Faltan columnas en {ruta.name}: {sorted(faltantes)}")
        serie: Serie = []
        for numero_fila, fila in enumerate(lector, 2):
            timestamp = (fila[columna_ts] or "").strip()
            if not timestamp:
                raise ValueError(f"Fila {numero_fila}: timestamp vacío")
            try:
                valor = round(parsear_decimal(fila[columna_valor] or "") * escala)
            except ValueError as error:
                raise ValueError(f"Fila {numero_fila}: valor inválido ({error})") from error
            serie.append((timestamp, valor))
    return serie


def extraer_cmg(
    resultados: Iterable[dict[str, Any]],
    campo_ts: str,
    campo_valor: str,
    escala: float = 1.0,
) -> Serie:
    """Extrae ``(timestamp, cmg)`` de los registros JSON de la API del Coordinador."""
    serie: Serie = []
    for registro in resultados:
        timestamp = str(registro[campo_ts])
        valor = round(parsear_decimal(str(registro[campo_valor])) * escala)
        serie.append((timestamp, valor))
    return serie


def alinear_series(generacion: Serie, cmg: Serie) -> list[tuple[str, int, int]]:
    """Cruza generación y CMg por timestamp (inner join), ordenado cronológicamente.

    Solo conserva los timestamps presentes en ambas series.
    """
    cmg_por_ts = dict(cmg)
    filas = [
        (timestamp, valor_gen, cmg_por_ts[timestamp])
        for timestamp, valor_gen in generacion
        if timestamp in cmg_por_ts
    ]
    return sorted(filas)


def alinear_por_posicion(generacion: Serie, cmg: Serie) -> list[tuple[str, int, int]]:
    """Cruza generación y CMg por **posición** (hora a hora), usando el timestamp del CMg.

    Útil cuando las series son de años distintos (p. ej. CMg real reciente + generación
    de un "año típico" del Explorador Solar): no comparten calendario, pero ambas son
    horarias y se aparean por índice. Exige el mismo largo para evitar desfases silenciosos.
    """
    if len(generacion) != len(cmg):
        raise ValueError(
            f"Las series deben tener el mismo largo para alinear por posición: "
            f"generación={len(generacion)}, cmg={len(cmg)}"
        )
    return [
        (cmg_ts, valor_gen, valor_cmg)
        for (_, valor_gen), (cmg_ts, valor_cmg) in zip(generacion, cmg, strict=True)
    ]


def escribir_csv_planta(ruta: Path | str, filas: Sequence[tuple[str, int, int]]) -> None:
    """Escribe el CSV de planta que consume `GatewayCSV`."""
    with Path(ruta).open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["timestamp", "generacion_w", "cmg_mills_por_mwh"])
        escritor.writerows(filas)


def escribir_serie_csv(ruta: Path | str, serie: Serie, nombre_valor: str) -> None:
    """Escribe una serie ``(timestamp, valor)`` como CSV de dos columnas."""
    with Path(ruta).open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["timestamp", nombre_valor])
        escritor.writerows(serie)
