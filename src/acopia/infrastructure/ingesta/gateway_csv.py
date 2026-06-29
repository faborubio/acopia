"""Gateway de ingesta CSV -> serie histórica de observaciones.

Lee un CSV con la serie horaria alineada de generación PV (W) y CMg (mills/MWh)
de la planta modelo. Pensado para volcar datos reales del Coordinador Eléctrico
(CMg por barra) cruzados con el Explorador Solar (generación PV simulada).

Formato esperado (cabecera, columnas en cualquier orden):

    timestamp,generacion_w,cmg_mills_por_mwh
    2025-01-01T12:00,80000,5000
    ...

``timestamp`` es opcional (solo trazabilidad); las filas se toman en el orden del
archivo. Solo usa la librería estándar: sin dependencias.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import ClassVar

from acopia.domain.entities.observacion import Observacion
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio


class GatewayCSV:
    """Implementa `PuertoHistoria` leyendo un CSV de la planta modelo."""

    COL_GENERACION: ClassVar[str] = "generacion_w"
    COL_CMG: ClassVar[str] = "cmg_mills_por_mwh"

    def __init__(self, ruta: Path | str) -> None:
        self._ruta = Path(ruta)

    def cargar(self) -> tuple[Observacion, ...]:
        if not self._ruta.exists():
            raise FileNotFoundError(f"No existe el archivo de datos: {self._ruta}")

        with self._ruta.open(newline="", encoding="utf-8") as archivo:
            lector = csv.DictReader(archivo)
            faltantes = {self.COL_GENERACION, self.COL_CMG} - set(lector.fieldnames or [])
            if faltantes:
                raise ValueError(f"Faltan columnas requeridas en el CSV: {sorted(faltantes)}")
            # La fila 1 es la cabecera; los datos empiezan en la fila 2.
            observaciones = [self._fila_a_observacion(fila, i) for i, fila in enumerate(lector, 2)]

        if not observaciones:
            raise ValueError(f"El CSV no contiene filas de datos: {self._ruta}")
        return tuple(observaciones)

    def _fila_a_observacion(self, fila: dict[str, str | None], numero_fila: int) -> Observacion:
        try:
            generacion = round(float(fila[self.COL_GENERACION] or ""))
            cmg = round(float(fila[self.COL_CMG] or ""))
            return Observacion(Potencia(generacion), Precio(cmg))
        except ValueError as error:
            raise ValueError(f"Fila {numero_fila}: dato inválido ({error})") from error
