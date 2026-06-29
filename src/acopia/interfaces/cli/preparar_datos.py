"""CLI `acopia-datos`: prepara datos reales chilenos al formato de la planta modelo.

Subcomandos:
- ``cmg``: descarga el costo marginal del Coordinador (API SIP v2, requiere un
  ``user_key`` gratuito de portal.api.coordinador.cl incluido en la URL) y lo
  guarda como CSV ``timestamp,cmg_mills_por_mwh``. Sigue la paginación (``next``).
- ``alinear``: cruza ese CMg con la generación PV exportada del Explorador Solar
  y escribe el CSV ``timestamp,generacion_w,cmg_mills_por_mwh`` para `GatewayCSV`.

La generación PV no tiene API horaria pública: se exporta desde solar.minenergia.cl
y se pasa a ``alinear`` (con --col-gen/--escala-gen según el formato exportado).
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any

from acopia.infrastructure.ingesta.preparacion import (
    Serie,
    alinear_series,
    escribir_csv_planta,
    escribir_serie_csv,
    extraer_cmg,
    leer_serie_csv,
)


def _descargar_cmg(url: str, campo_ts: str, campo_valor: str, escala: float) -> Serie:
    """Descarga el CMg siguiendo la paginación de la API SIP del Coordinador."""
    serie: Serie = []
    siguiente: str | None = url
    while siguiente:
        with urllib.request.urlopen(siguiente) as respuesta:
            datos: dict[str, Any] = json.load(respuesta)
        serie.extend(extraer_cmg(datos.get("results", []), campo_ts, campo_valor, escala))
        siguiente = datos.get("next")
    return serie


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acopia-datos", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    cmg = sub.add_parser("cmg", help="Descarga CMg del Coordinador (SIP API) a CSV")
    cmg.add_argument("--url", required=True, help="URL del recurso SIP con user_key y filtros")
    cmg.add_argument("--campo-ts", default="fecha", help="Campo de timestamp en el JSON")
    cmg.add_argument("--campo-cmg", default="cmg", help="Campo de CMg en el JSON")
    cmg.add_argument("--escala", type=float, default=1.0, help="Factor a mills/MWh")
    cmg.add_argument("--salida", required=True, help="CSV de salida (timestamp,cmg_mills_por_mwh)")

    alinear = sub.add_parser("alinear", help="Alinea CMg + generación al CSV de planta")
    alinear.add_argument("--cmg", required=True, help="CSV de CMg")
    alinear.add_argument("--col-ts-cmg", default="timestamp")
    alinear.add_argument("--col-cmg", default="cmg_mills_por_mwh")
    alinear.add_argument("--generacion", required=True, help="CSV de generación PV exportado")
    alinear.add_argument("--col-ts-gen", default="timestamp")
    alinear.add_argument("--col-gen", default="generacion_w")
    alinear.add_argument("--escala-gen", type=float, default=1.0, help="Factor a W (1000 si es kW)")
    alinear.add_argument("--salida", required=True, help="CSV de planta (lo consume GatewayCSV)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _construir_parser().parse_args(argv)

    if args.comando == "cmg":
        serie = _descargar_cmg(args.url, args.campo_ts, args.campo_cmg, args.escala)
        escribir_serie_csv(args.salida, serie, "cmg_mills_por_mwh")
        print(f"CMg: {len(serie)} filas escritas en {args.salida}")
    elif args.comando == "alinear":
        cmg = leer_serie_csv(args.cmg, args.col_ts_cmg, args.col_cmg)
        generacion = leer_serie_csv(args.generacion, args.col_ts_gen, args.col_gen, args.escala_gen)
        filas = alinear_series(generacion, cmg)
        escribir_csv_planta(args.salida, filas)
        print(f"Alineadas {len(filas)} filas en {args.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
