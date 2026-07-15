"""CLI `acopia-datos`: prepara datos reales chilenos al formato de la planta modelo.

Subcomandos:
- ``cmg``: descarga CMg de una API JSON paginada por ``next`` (formato SIP v2).
  OJO: la API actual del Coordinador es **v4** (page/limit, ver ``MEMORY.md``) y no
  filtra por barra; para un set real conviene la **descarga manual del XLS**. Este
  subcomando se mantiene para APIs con paginación ``next`` pero quedó desalineado
  del Coordinador v4 (reescribir si se quiere la vía API).
- ``alinear``: cruza el CMg con la generación PV exportada del Explorador Solar y
  escribe el CSV ``timestamp,generacion_w,cmg_mills_por_mwh`` para `GatewayCSV`.
  Acepta entradas **.csv o .xlsx** (despacha por extensión); para Excel usa
  ``--hoja-*``/``--fila-encabezado-*`` si hay metadatos sobre la tabla.
  Usa ``--por-posicion`` (con ``--recortar`` si difieren en largo) para series de años distintos.
- ``backtest``: compara forecasters (naive, SARIMAX, LSTM) sobre un CSV de planta con
  un backtest rodante y reporta RMSE/MAPE por serie (comparación honesta de ADR-002).
- ``comparar-modos``: el experimento de ADR-005 — DRL (PPO) vs baseline determinista
  (LP) sobre días reales con **forecast perfecto** (mide la calidad del optimizador,
  no la del forecaster). Requiere el extra ``acopia[drl]``.

La generación PV no tiene API horaria pública: se exporta desde solar.minenergia.cl
y se pasa a ``alinear`` (con --col-gen/--escala-gen según el formato exportado).
Las descargas del Coordinador vienen en .xlsx; leerlas requiere el extra
``acopia[ingesta]`` (openpyxl).
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any

from acopia.application.backtest import backtest_rodante
from acopia.domain.ports.puerto_forecaster import PuertoForecaster
from acopia.infrastructure.forecasting.forecaster_estacional import ForecasterEstacionalNaive
from acopia.infrastructure.forecasting.forecaster_sarimax import ForecasterSARIMAX
from acopia.infrastructure.ingesta.gateway_csv import GatewayCSV
from acopia.infrastructure.ingesta.preparacion import (
    Serie,
    alinear_por_posicion,
    alinear_series,
    escribir_csv_planta,
    escribir_serie_csv,
    extraer_cmg,
    leer_serie,
)


def _construir_forecasters(
    nombres: list[str], estacionalidad: int
) -> list[tuple[str, PuertoForecaster]]:
    """Instancia los forecasters pedidos; omite el LSTM si torch no está instalado."""
    forecasters: list[tuple[str, PuertoForecaster]] = []
    for crudo in nombres:
        nombre = crudo.strip().lower()
        if nombre == "naive":
            forecasters.append((nombre, ForecasterEstacionalNaive(estacionalidad)))
        elif nombre == "sarimax":
            forecasters.append(
                (
                    nombre,
                    ForecasterSARIMAX(
                        estacionalidad,
                        orden=(2, 0, 1),
                        orden_estacional=(1, 0, 0, estacionalidad),
                    ),
                )
            )
        elif nombre == "lstm":
            try:
                from acopia.infrastructure.forecasting.forecaster_lstm import (
                    ForecasterSeq2SeqLSTM,
                )
            except ImportError:
                print("(LSTM omitido: torch no instalado; usa el extra acopia[forecasting])")
                continue
            forecasters.append(
                (nombre, ForecasterSeq2SeqLSTM(ventana=2 * estacionalidad, hidden=32, epocas=250))
            )
        else:
            raise ValueError(f"Modelo desconocido: {nombre!r} (usa naive, sarimax, lstm)")
    return forecasters


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
    alinear.add_argument(
        "--cmg", required=True, nargs="+",
        help="Uno o más CSV/XLSX de CMg (se concatenan y ordenan cronológicamente)",
    )
    alinear.add_argument(
        "--col-ts-cmg", default="timestamp",
        help="Columna de timestamp; con --col-hora-cmg se trata como columna de fecha",
    )
    alinear.add_argument(
        "--col-hora-cmg", default=None,
        help="Columna de hora (0..23) del formato ancho del Coordinador; combina Fecha+Hora",
    )
    alinear.add_argument(
        "--col-cmg", default="cmg_mills_por_mwh",
        help="Columna de CMg (en el formato ancho, el nombre de la barra, ej. 'S.GREGORIO')",
    )
    alinear.add_argument(
        "--escala-cmg", type=float, default=1.0,
        help="Factor a mills/MWh (1000 si el CMg viene en CLP/kWh, como el Coordinador)",
    )
    alinear.add_argument("--hoja-cmg", default=None, help="Pestaña del XLSX de CMg")
    alinear.add_argument(
        "--fila-encabezado-cmg", type=int, default=1, help="Fila del encabezado en el XLSX de CMg"
    )
    alinear.add_argument("--generacion", required=True, help="CSV o XLSX de generación PV")
    alinear.add_argument("--col-ts-gen", default="timestamp")
    alinear.add_argument(
        "--col-hora-gen", default=None, help="Columna de hora (0..23) si la generación es ancha"
    )
    alinear.add_argument("--col-gen", default="generacion_w")
    alinear.add_argument("--escala-gen", type=float, default=1.0, help="Factor a W (1000 si es kW)")
    alinear.add_argument("--hoja-gen", default=None, help="Pestaña del XLSX de generación")
    alinear.add_argument(
        "--fila-encabezado-gen", type=int, default=1,
        help="Fila del encabezado de la generación (54 filas de metadatos en el TMY -> 55)",
    )
    alinear.add_argument(
        "--por-posicion",
        action="store_true",
        help="Une por posición (hora a hora) en vez de por timestamp; usa el ts del CMg. "
        "Necesario si las series son de años distintos (CMg real + Explorador Solar).",
    )
    alinear.add_argument(
        "--recortar",
        action="store_true",
        help="Con --por-posicion, recorta ambas series al largo menor (p. ej. CMg de 1 mes "
        "vs generación de 1 año). Opt-in para no ocultar desfases silenciosos.",
    )
    alinear.add_argument("--salida", required=True, help="CSV de planta (lo consume GatewayCSV)")

    backtest = sub.add_parser(
        "backtest", help="Compara forecasters (RMSE/MAPE) sobre un CSV de planta"
    )
    backtest.add_argument("--planta", required=True, help="CSV de planta (timestamp,gen,cmg)")
    backtest.add_argument("--horizonte", type=int, default=24, help="Pasos a pronosticar por fold")
    backtest.add_argument("--folds", type=int, default=5, help="Nº de tramos out-of-sample")
    backtest.add_argument(
        "--estacionalidad", type=int, default=24, help="Período estacional (24 = diario horario)"
    )
    backtest.add_argument(
        "--modelos", default="naive,sarimax,lstm", help="Lista separada por comas"
    )
    backtest.add_argument(
        "--ventana-entrenamiento", type=int, default=None,
        help="Entrenar solo con las últimas N observaciones (régimen-local); "
        "por defecto usa todo el histórico (ventana expansiva)",
    )

    politica = sub.add_parser(
        "backtest-politica",
        help="Backtest de la política de despacho: forecast -> plan -> ejecución real",
    )
    politica.add_argument("--planta", required=True, help="CSV de planta (timestamp,gen,cmg)")
    politica.add_argument("--folds", type=int, default=5, help="Días out-of-sample")
    politica.add_argument("--horizonte", type=int, default=24)
    politica.add_argument("--estacionalidad", type=int, default=24)
    politica.add_argument("--modelo", default="naive", help="naive | sarimax | lstm")
    politica.add_argument("--escenarios", type=int, default=1, help="N para el estocástico")
    politica.add_argument("--semilla", type=int, default=0)
    politica.add_argument("--capacidad-wh", type=int, default=2_000, help="Batería (Wh)")
    politica.add_argument("--potencia-w", type=int, default=500, help="Carga/descarga (W)")
    politica.add_argument("--iny-w", type=int, default=1_000_000, help="Techo de inyección (W)")
    politica.add_argument(
        "--retiro-w", type=int, default=0,
        help="Retiro máx. de red (W); 0 = solo PV+BESS (default, típico solar)",
    )

    comparar = sub.add_parser(
        "comparar-modos",
        help="ADR-005: modo DRL (PPO) vs baseline determinista (LP) sobre días reales",
    )
    comparar.add_argument("--planta", required=True, help="CSV de planta (timestamp,gen,cmg)")
    comparar.add_argument("--dias", type=int, default=3, help="Últimos N días completos")
    comparar.add_argument("--horizonte", type=int, default=24)
    comparar.add_argument(
        "--timesteps", type=int, default=30_000,
        help="Presupuesto de entrenamiento PPO por día (más = mejor y más lento)",
    )
    comparar.add_argument("--semilla", type=int, default=0)
    comparar.add_argument("--capacidad-wh", type=int, default=2_000, help="Batería (Wh)")
    comparar.add_argument("--potencia-w", type=int, default=500, help="Carga/descarga (W)")
    comparar.add_argument("--iny-w", type=int, default=1_000_000, help="Techo de inyección (W)")
    comparar.add_argument("--retiro-w", type=int, default=0, help="Retiro máx. de red (W)")

    observatorio = sub.add_parser(
        "observatorio",
        help="Genera el sitio estático del Observatorio (ADR-012): vertimiento + demo",
    )
    observatorio.add_argument(
        "--reducciones", required=True, nargs="+",
        help="Uno o más XLSX 'Reducciones ERV' del Coordinador (un mes cada uno)",
    )
    observatorio.add_argument(
        "--salida", required=True,
        help="Directorio del sitio: escribe index.html (y demo.html salvo --sin-demo)",
    )
    observatorio.add_argument(
        "--sin-demo", action="store_true",
        help="No incluir el snapshot del dashboard demo (ADR-011)",
    )
    observatorio.add_argument(
        "--fecha", default=None, help="Fecha 'generado el' (YYYY-MM-DD; default: hoy)",
    )
    observatorio.add_argument(
        "--cmg", action="append", default=None, metavar="ETIQUETA=COLUMNA=RUTA",
        help="Serie de CMg para la duck curve (ADR-012.2; repetible, máx. 3 barras): "
             "etiqueta visible, columna de la barra (matching tolerante) y XLSX del "
             "Coordinador en formato ancho Fecha/Hora (USD/MWh). Misma etiqueta en "
             "varios --cmg concatena archivos. Ej: "
             '"Norte - S. Gregorio=S.GREGORIO=datos/cmg/sgregorio_2025.xlsx"',
    )
    observatorio.add_argument(
        "--eficiencia", type=float, default=0.85,
        help="Eficiencia de ida y vuelta para la valorización a la punta (default 0.85)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _construir_parser().parse_args(argv)

    if args.comando == "cmg":
        serie = _descargar_cmg(args.url, args.campo_ts, args.campo_cmg, args.escala)
        escribir_serie_csv(args.salida, serie, "cmg_mills_por_mwh")
        print(f"CMg: {len(serie)} filas escritas en {args.salida}")
    elif args.comando == "alinear":
        cmg = []
        for ruta_cmg in args.cmg:
            cmg.extend(
                leer_serie(
                    ruta_cmg, args.col_ts_cmg, args.col_cmg, args.escala_cmg,
                    hoja=args.hoja_cmg, fila_encabezado=args.fila_encabezado_cmg,
                    columna_hora=args.col_hora_cmg,
                )
            )
        cmg.sort(key=lambda par: par[0])  # cronológico por timestamp ISO
        generacion = leer_serie(
            args.generacion, args.col_ts_gen, args.col_gen, args.escala_gen,
            hoja=args.hoja_gen, fila_encabezado=args.fila_encabezado_gen,
            columna_hora=args.col_hora_gen,
        )
        if args.recortar:
            n = min(len(generacion), len(cmg))
            generacion, cmg = generacion[:n], cmg[:n]
        if args.por_posicion:
            filas = alinear_por_posicion(generacion, cmg)
        else:
            filas = alinear_series(generacion, cmg)
        escribir_csv_planta(args.salida, filas)
        print(f"Alineadas {len(filas)} filas en {args.salida}")
    elif args.comando == "backtest":
        observaciones = GatewayCSV(args.planta).cargar()
        forecasters = _construir_forecasters(args.modelos.split(","), args.estacionalidad)
        print(
            f"Backtest rodante: {args.folds} folds x {args.horizonte}h "
            f"sobre {len(observaciones)} observaciones"
        )
        print(f"{'modelo':9s} | gen RMSE | gen MAPE | cmg RMSE | cmg MAPE")
        print("-" * 60)
        for nombre, forecaster in forecasters:
            r = backtest_rodante(
                forecaster, observaciones, args.horizonte, args.folds,
                ventana_entrenamiento=args.ventana_entrenamiento,
            )
            print(
                f"{nombre:9s} | {r.generacion.rmse:8.1f} | {r.generacion.mape:7.1f}% "
                f"| {r.cmg.rmse:8.0f} | {r.cmg.mape:7.1f}%"
            )
    elif args.comando == "backtest-politica":
        _ejecutar_backtest_politica(args)
    elif args.comando == "comparar-modos":
        _ejecutar_comparar_modos(args)
    elif args.comando == "observatorio":
        _ejecutar_observatorio(args)
    return 0


def _ejecutar_observatorio(args: argparse.Namespace) -> None:
    from datetime import date

    from acopia.infrastructure.ingesta.reducciones_erv import (
        ReduccionDiaria,
        leer_reducciones_erv,
    )
    from acopia.interfaces.observatorio.sitio import render_vertimiento

    registros: list[ReduccionDiaria] = []
    for ruta in args.reducciones:
        registros.extend(leer_reducciones_erv(ruta))
    generado_el = args.fecha or date.today().isoformat()

    # Duck curve (ADR-012.2): convenciones fijas del XLSX de CMg del Coordinador
    # (Fecha combinada + Hora 0..23, USD/MWh -> mills con escala 1000).
    cmg_por_barra: dict[str, list[tuple[str, int]]] | None = None
    if args.cmg:
        cmg_por_barra = {}
        for spec in args.cmg:
            try:
                etiqueta, columna, ruta_cmg = spec.split("=", 2)
            except ValueError:
                raise SystemExit(
                    f"--cmg espera ETIQUETA=COLUMNA=RUTA, no {spec!r}"
                ) from None
            serie = leer_serie(
                ruta_cmg, "Fecha", columna, escala=1000.0, columna_hora="Hora"
            )
            cmg_por_barra.setdefault(etiqueta, []).extend(serie)
        for serie in cmg_por_barra.values():
            serie.sort(key=lambda par: par[0])  # cronológico por timestamp ISO

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    pagina = render_vertimiento(
        tuple(registros), generado_el, enlace_demo=not args.sin_demo,
        cmg_por_barra=cmg_por_barra, eficiencia=args.eficiencia,
    )
    (salida / "index.html").write_text(pagina, encoding="utf-8")
    print(f"Observatorio: index.html ({len(registros)} registros) en {salida}")

    if not args.sin_demo:
        from acopia.interfaces.rest.dashboard import render_dashboard

        (salida / "demo.html").write_text(render_dashboard(), encoding="utf-8")
        print(f"Observatorio: demo.html (snapshot ADR-011) en {salida}")


def _ejecutar_backtest_politica(args: argparse.Namespace) -> None:
    from acopia.application.backtest_politica import backtest_politica
    from acopia.domain.entities.bateria import Bateria
    from acopia.domain.entities.estado_bateria import EstadoBateria
    from acopia.domain.entities.planta import Planta
    from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
    from acopia.domain.value_objects.eficiencia import Eficiencia
    from acopia.domain.value_objects.energia import Energia
    from acopia.domain.value_objects.intervalo import Intervalo
    from acopia.domain.value_objects.potencia import Potencia
    from acopia.domain.value_objects.soc import Soc
    from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP

    observaciones = GatewayCSV(args.planta).cargar()
    forecasters = _construir_forecasters([args.modelo], args.estacionalidad)
    if not forecasters:
        raise SystemExit(1)
    nombre, forecaster = forecasters[0]

    bateria = Bateria(
        capacidad=Energia(args.capacidad_wh),
        potencia_max_carga=Potencia(args.potencia_w),
        potencia_max_descarga=Potencia(args.potencia_w),
        eficiencia_carga=Eficiencia.de_porcentaje(95),
        eficiencia_descarga=Eficiencia.de_porcentaje(95),
        soc_min=Soc.de_porcentaje(0),
        soc_max=Soc.de_porcentaje(100),
        throughput_garantia=Energia(1_000_000_000),
    )
    planta = Planta("planta-modelo", bateria, Potencia(args.iny_w), Potencia(args.retiro_w))
    politica = PoliticaDespacho(
        id="arbitraje-backtest",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=args.horizonte,
        resolucion=Intervalo.de_minutos(60),
        semilla=args.semilla,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
        costo_ciclado_mills_por_mwh=0,
    )
    resultado = backtest_politica(
        forecaster,
        OptimizadorLP(),
        planta,
        EstadoBateria(Energia(0)),
        observaciones,
        politica,
        folds=args.folds,
        n_escenarios=args.escenarios,
        semilla=args.semilla,
    )
    reparadas = sum(f.acciones_reparadas for f in resultado.folds)
    vertida = sum(f.energia_vertida_wh for f in resultado.folds)
    print(
        f"Backtest de política: {args.folds} folds x {args.horizonte}h · "
        f"forecaster={nombre} · escenarios={args.escenarios} · retiro={args.retiro_w} W"
    )
    print(f"  ingreso esperado  : {resultado.ingreso_esperado_mills:>12,} mills")
    print(f"  ingreso realizado : {resultado.ingreso_realizado_mills:>12,} mills")
    print(f"  ingreso foresight : {resultado.ingreso_foresight_mills:>12,} mills")
    print(f"  captura vs techo  : {resultado.captura_vs_foresight_bp / 100:>11.1f} %")
    print(f"  vertido realizado : {vertida:>12,} Wh · acciones reparadas: {reparadas}")


def _ejecutar_comparar_modos(args: argparse.Namespace) -> None:
    """Experimento de ADR-005: LP vs PPO por día real, con forecast perfecto.

    Forecast perfecto = el escenario es el día observado. Así la brecha mide SOLO la
    calidad del optimizador (programa de batería), sin confundirla con el error de
    forecast. El baseline LP es el óptimo del problema: la pregunta honesta es
    cuánto se le acerca el DRL, no si lo supera.
    """
    from acopia.application.comparar_modos import comparar_modos
    from acopia.domain.entities.bateria import Bateria
    from acopia.domain.entities.escenario import Escenario, PuntoPronostico
    from acopia.domain.entities.estado_bateria import EstadoBateria
    from acopia.domain.entities.planta import Planta
    from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
    from acopia.domain.entities.rastro import RastroDespacho
    from acopia.domain.value_objects.eficiencia import Eficiencia
    from acopia.domain.value_objects.energia import Energia
    from acopia.domain.value_objects.intervalo import Intervalo
    from acopia.domain.value_objects.potencia import Potencia
    from acopia.domain.value_objects.soc import Soc
    from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP

    try:
        from acopia.infrastructure.drl.optimizador_drl import OptimizadorDRL
    except ImportError:
        print("comparar-modos requiere el extra acopia[drl] (stable-baselines3 + gymnasium)")
        raise SystemExit(1) from None

    observaciones = GatewayCSV(args.planta).cargar()
    horizonte = args.horizonte
    if len(observaciones) < horizonte * args.dias:
        raise SystemExit(
            f"Se necesitan {horizonte * args.dias} observaciones para "
            f"{args.dias} días; hay {len(observaciones)}"
        )

    bateria = Bateria(
        capacidad=Energia(args.capacidad_wh),
        potencia_max_carga=Potencia(args.potencia_w),
        potencia_max_descarga=Potencia(args.potencia_w),
        eficiencia_carga=Eficiencia.de_porcentaje(95),
        eficiencia_descarga=Eficiencia.de_porcentaje(95),
        soc_min=Soc.de_porcentaje(0),
        soc_max=Soc.de_porcentaje(100),
        throughput_garantia=Energia(1_000_000_000),
    )
    planta = Planta("planta-modelo", bateria, Potencia(args.iny_w), Potencia(args.retiro_w))
    politica = PoliticaDespacho(
        id="comparar-modos",
        version=1,
        objetivo=Objetivo.MAX_INGRESO,
        horizonte_intervalos=horizonte,
        resolucion=Intervalo.de_minutos(60),
        semilla=args.semilla,
        modo=Modo.PREDICT_THEN_OPTIMIZE,
    )
    optimizador_lp = OptimizadorLP()
    optimizador_drl = OptimizadorDRL(total_timesteps=args.timesteps)

    print(
        f"Comparación de modos (ADR-005): {args.dias} días x {horizonte}h · "
        f"forecast perfecto · PPO {args.timesteps} timesteps/día · semilla {args.semilla}"
    )
    print(
        f"{'día':>4s} | {'LP (mills)':>12s} | {'DRL (mills)':>12s} | {'delta':>10s} | captura DRL"
    )
    print("-" * 66)
    total_lp = total_drl = 0
    inicio = len(observaciones) - horizonte * args.dias
    for d in range(args.dias):
        tramo = observaciones[inicio + d * horizonte : inicio + (d + 1) * horizonte]
        escenario = Escenario(
            tuple(PuntoPronostico(o.generacion, o.cmg) for o in tramo)
        )
        rastro = RastroDespacho(
            politica_id=politica.id,
            politica_version=politica.version,
            semilla=politica.semilla,
            estado_inicial=EstadoBateria(Energia(0)),
            escenarios=(escenario,),
        )
        r = comparar_modos(optimizador_lp, optimizador_drl, planta, rastro, politica)
        captura = (
            r.ingreso_drl_mills / r.ingreso_deterministico_mills * 100
            if r.ingreso_deterministico_mills
            else float("nan")
        )
        print(
            f"{d:>4d} | {r.ingreso_deterministico_mills:>12,} | "
            f"{r.ingreso_drl_mills:>12,} | {r.delta_mills:>10,} | {captura:10.1f} %"
        )
        total_lp += r.ingreso_deterministico_mills
        total_drl += r.ingreso_drl_mills
    print("-" * 66)
    captura_total = total_drl / total_lp * 100 if total_lp else float("nan")
    print(
        f"{'TOT':>4s} | {total_lp:>12,} | {total_drl:>12,} | "
        f"{total_drl - total_lp:>10,} | {captura_total:10.1f} %"
    )


if __name__ == "__main__":
    raise SystemExit(main())
