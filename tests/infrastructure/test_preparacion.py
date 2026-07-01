"""Tests de los helpers de preparación de datos y la CLI de alineación."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from acopia.infrastructure.ingesta.gateway_csv import GatewayCSV
from acopia.infrastructure.ingesta.preparacion import (
    alinear_por_posicion,
    alinear_series,
    escribir_csv_planta,
    extraer_cmg,
    leer_serie,
    leer_serie_csv,
    leer_serie_xlsx,
    parsear_decimal,
)
from acopia.interfaces.cli.preparar_datos import main


def _escribir_xlsx(ruta: Path, filas: list[list[Any]], hoja: str = "Hoja1") -> None:
    """Crea un .xlsx con las filas dadas (la primera suele ser el encabezado)."""
    openpyxl = pytest.importorskip("openpyxl")
    libro = openpyxl.Workbook()
    ws = libro.active
    ws.title = hoja
    for fila in filas:
        ws.append(fila)
    libro.save(ruta)


def _escribir_cmg_coordinador(
    ruta: Path, dias: list[tuple[str, list[str]]], barra: str = "S.GREGORIO____013"
) -> None:
    """Emula el .xlsx real del Coordinador: Fecha combinada + Hora + columna de la barra."""
    openpyxl = pytest.importorskip("openpyxl")
    libro = openpyxl.Workbook()
    ws = libro.active
    ws.append(["Fecha", "Dia", "Hora", "Barra", barra])
    fila = 2
    for numero_dia, (fecha, valores) in enumerate(dias, 1):
        inicio = fila
        for hora, valor in enumerate(valores):
            ws.cell(row=fila, column=3, value=hora)
            ws.cell(row=fila, column=5, value=valor)  # texto con coma chilena
            fila += 1
        ws.cell(row=inicio, column=1, value=fecha)  # fecha en el anchor (fila superior)
        ws.cell(row=inicio, column=2, value=numero_dia)
        if len(valores) > 1:  # celda combinada por día, como el archivo real
            ws.merge_cells(start_row=inicio, start_column=1, end_row=fila - 1, end_column=1)
    libro.save(ruta)


def test_alinear_series_hace_inner_join_ordenado() -> None:
    generacion = [("2025-01-01T12:00", 80_000), ("2025-01-01T18:00", 10_000)]
    cmg = [("2025-01-01T18:00", 250_000), ("2025-01-01T12:00", 5_000), ("2025-01-02T00:00", 9)]
    filas = alinear_series(generacion, cmg)
    # solo los timestamps comunes, ordenados
    assert filas == [
        ("2025-01-01T12:00", 80_000, 5_000),
        ("2025-01-01T18:00", 10_000, 250_000),
    ]


def test_extraer_cmg_escala_a_mills() -> None:
    resultados = [{"fecha": "2025-01-01T12:00", "cmg": 5.0}]
    # CMg viene en CLP/kWh y se quiere en mills/MWh: factor 1000
    assert extraer_cmg(resultados, "fecha", "cmg", escala=1000) == [("2025-01-01T12:00", 5_000)]


def test_parsear_decimal_tolera_coma_chilena() -> None:
    assert parsear_decimal("57,79415") == 57.79415   # coma decimal
    assert parsear_decimal("1.234,56") == 1234.56     # punto miles + coma decimal
    assert parsear_decimal("78500.4") == 78500.4      # punto decimal estándar
    assert parsear_decimal("80000") == 80000.0


def test_extraer_cmg_con_coma_decimal() -> None:
    # como llega de la API del Coordinador: cmg_clp_kwh_ con coma decimal
    resultados = [{"fecha_hora": "2025-06-01 00:00", "cmg_clp_kwh_": "57,79415"}]
    serie = extraer_cmg(resultados, "fecha_hora", "cmg_clp_kwh_", escala=1000)
    # 57,79415 CLP/kWh * 1000 = 57794.15 -> 57794
    assert serie == [("2025-06-01 00:00", 57_794)]


def test_alinear_por_posicion_usa_ts_del_cmg() -> None:
    # series de años distintos: se aparean por índice, con el timestamp del CMg
    generacion = [("2015-01-01T00:00", 0), ("2015-01-01T12:00", 80_000)]
    cmg = [("2024-06-01T00:00", 90_000), ("2024-06-01T12:00", 5_000)]
    assert alinear_por_posicion(generacion, cmg) == [
        ("2024-06-01T00:00", 0, 90_000),
        ("2024-06-01T12:00", 80_000, 5_000),
    ]


def test_alinear_por_posicion_exige_mismo_largo() -> None:
    with pytest.raises(ValueError, match="mismo largo"):
        alinear_por_posicion([("a", 1)], [("b", 2), ("c", 3)])


def test_leer_serie_csv_escala_y_redondea(tmp_path: Path) -> None:
    ruta = tmp_path / "gen.csv"
    ruta.write_text("timestamp,gen_kw\n2025-01-01T12:00,80.4\n", encoding="utf-8")
    # kW -> W con factor 1000; 80.4 kW -> 80400 W
    serie = leer_serie_csv(ruta, "timestamp", "gen_kw", escala=1000)
    assert serie == [("2025-01-01T12:00", 80_400)]


def test_leer_serie_csv_salta_filas_de_metadatos(tmp_path: Path) -> None:
    # Como el export TMY del Explorador Solar: metadatos y luego la tabla.
    ruta = tmp_path / "gen.csv"
    ruta.write_text(
        "TITULO\nDESCRIPCION,algo\nFecha/Hora,pv\n2005-01-01 00:00:00,0.4645\n",
        encoding="utf-8",
    )
    serie = leer_serie_csv(ruta, "Fecha/Hora", "pv", escala=1000, fila_encabezado=3)
    # 0.4645 kWh -> 464.5 W -> 464 (redondeo bancario)
    assert serie == [("2005-01-01 00:00:00", 464)]


def test_leer_serie_csv_omite_fila_en_blanco_final(tmp_path: Path) -> None:
    ruta = tmp_path / "gen.csv"
    ruta.write_text("ts,v\n2025-01-01T00:00,5\n,\n", encoding="utf-8")
    assert leer_serie_csv(ruta, "ts", "v") == [("2025-01-01T00:00", 5)]


def test_cli_alinear_recortar_al_largo_menor(tmp_path: Path) -> None:
    # CMg de 2 horas vs generación de 4: --recortar iguala al mínimo (2).
    (tmp_path / "cmg.csv").write_text(
        "timestamp,cmg_mills_por_mwh\n2025-01-01T00:00,90000\n2025-01-01T01:00,5000\n",
        encoding="utf-8",
    )
    (tmp_path / "gen.csv").write_text(
        "timestamp,generacion_w\n2015-01-01T00:00,0\n2015-01-01T01:00,10\n"
        "2015-01-01T02:00,20\n2015-01-01T03:00,30\n",
        encoding="utf-8",
    )
    salida = tmp_path / "planta.csv"
    codigo = main(
        [
            "alinear", "--por-posicion", "--recortar",
            "--cmg", str(tmp_path / "cmg.csv"),
            "--generacion", str(tmp_path / "gen.csv"),
            "--salida", str(salida),
        ]
    )
    assert codigo == 0
    observaciones = GatewayCSV(salida).cargar()
    assert len(observaciones) == 2  # recortado al largo del CMg


def test_leer_serie_csv_columna_faltante(tmp_path: Path) -> None:
    ruta = tmp_path / "x.csv"
    ruta.write_text("timestamp\n2025-01-01T12:00\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Faltan columnas"):
        leer_serie_csv(ruta, "timestamp", "cmg")


def test_leer_serie_csv_valor_invalido_reporta_fila(tmp_path: Path) -> None:
    ruta = tmp_path / "x.csv"
    ruta.write_text("timestamp,cmg\n2025-01-01T12:00,ABC\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Fila 2"):
        leer_serie_csv(ruta, "timestamp", "cmg")


def test_salida_alineada_la_lee_gateway(tmp_path: Path) -> None:
    ruta = tmp_path / "planta.csv"
    escribir_csv_planta(ruta, [("2025-01-01T12:00", 80_000, 5_000)])
    observaciones = GatewayCSV(ruta).cargar()
    assert len(observaciones) == 1
    assert observaciones[0].generacion.w == 80_000
    assert observaciones[0].cmg.mills_por_mwh == 5_000


def test_cli_alinear_de_punta_a_punta(tmp_path: Path) -> None:
    (tmp_path / "cmg.csv").write_text(
        "timestamp,cmg_mills_por_mwh\n2025-01-01T12:00,5000\n2025-01-01T18:00,250000\n",
        encoding="utf-8",
    )
    (tmp_path / "gen.csv").write_text(
        "timestamp,generacion_w\n2025-01-01T12:00,80000\n2025-01-01T18:00,10000\n",
        encoding="utf-8",
    )
    salida = tmp_path / "planta.csv"
    codigo = main(
        [
            "alinear",
            "--cmg", str(tmp_path / "cmg.csv"),
            "--generacion", str(tmp_path / "gen.csv"),
            "--salida", str(salida),
        ]
    )
    assert codigo == 0
    observaciones = GatewayCSV(salida).cargar()
    assert len(observaciones) == 2
    assert observaciones[0].cmg.mills_por_mwh == 5_000


def test_leer_serie_xlsx_celdas_nativas(tmp_path: Path) -> None:
    # Como exporta el Coordinador: fecha_hora datetime + cmg float nativo.
    ruta = tmp_path / "cmg.xlsx"
    _escribir_xlsx(
        ruta,
        [
            ["fecha_hora", "cmg_clp_kwh_"],
            [datetime(2025, 6, 1, 0, 0), 57.79415],
            [datetime(2025, 6, 1, 1, 0), 60.0],
        ],
    )
    serie = leer_serie_xlsx(ruta, "fecha_hora", "cmg_clp_kwh_", escala=1000)
    assert serie == [("2025-06-01T00:00", 57_794), ("2025-06-01T01:00", 60_000)]


def test_leer_serie_xlsx_texto_con_coma_chilena(tmp_path: Path) -> None:
    # Cuando Excel guarda los números como texto con coma decimal.
    ruta = tmp_path / "cmg.xlsx"
    _escribir_xlsx(ruta, [["ts", "cmg"], ["2025-06-01 00:00", "57,79415"]])
    assert leer_serie_xlsx(ruta, "ts", "cmg", escala=1000) == [("2025-06-01 00:00", 57_794)]


def test_leer_serie_xlsx_salta_filas_de_metadatos(tmp_path: Path) -> None:
    # El encabezado real está en la fila 3 (dos filas de metadatos arriba).
    ruta = tmp_path / "cmg.xlsx"
    _escribir_xlsx(
        ruta,
        [
            ["Reporte CMg - Coordinador", None],
            ["Barra: S.GREGORIO____013", None],
            ["ts", "cmg"],
            ["2025-06-01 12:00", "5,0"],
        ],
    )
    serie = leer_serie_xlsx(ruta, "ts", "cmg", escala=1000, fila_encabezado=3)
    assert serie == [("2025-06-01 12:00", 5_000)]


def test_leer_serie_xlsx_columna_faltante(tmp_path: Path) -> None:
    ruta = tmp_path / "x.xlsx"
    _escribir_xlsx(ruta, [["ts"], ["2025-06-01 12:00"]])
    with pytest.raises(ValueError, match="no encontrada"):
        leer_serie_xlsx(ruta, "ts", "cmg")


def test_leer_serie_despacha_por_extension(tmp_path: Path) -> None:
    csv_ruta = tmp_path / "g.csv"
    csv_ruta.write_text("ts,g\n2025-01-01T12:00,80\n", encoding="utf-8")
    xlsx_ruta = tmp_path / "g.xlsx"
    _escribir_xlsx(xlsx_ruta, [["ts", "g"], ["2025-01-01T12:00", 80]])
    assert leer_serie(csv_ruta, "ts", "g") == leer_serie(xlsx_ruta, "ts", "g")


def test_leer_cmg_formato_ancho_coordinador(tmp_path: Path) -> None:
    # Fecha combinada por día + Hora 0..23 + columna titulada con la barra.
    ruta = tmp_path / "cmg.xlsx"
    _escribir_cmg_coordinador(
        ruta,
        [
            ("2025-01-01", ["58,62", "64,86", "0,00"]),
            ("2025-01-02", ["74,27", "70,97", "0,00"]),
        ],
    )
    # --col-cmg "S.GREGORIO" calza con "S.GREGORIO____013" (matching tolerante).
    serie = leer_serie_xlsx(ruta, "Fecha", "S.GREGORIO", escala=1000, columna_hora="Hora")
    assert serie[:4] == [
        ("2025-01-01T00:00", 58_620),
        ("2025-01-01T01:00", 64_860),
        ("2025-01-01T02:00", 0),
        ("2025-01-02T00:00", 74_270),  # fecha del 2º día arrastrada (forward-fill)
    ]


def test_leer_serie_csv_rechaza_columna_hora(tmp_path: Path) -> None:
    ruta = tmp_path / "x.csv"
    ruta.write_text("Fecha,Hora,cmg\n2025-01-01,0,5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="solo se soporta en"):
        leer_serie(ruta, "Fecha", "cmg", columna_hora="Hora")


def test_cli_alinear_cmg_ancho_del_coordinador(tmp_path: Path) -> None:
    # De punta a punta con el formato real del Coordinador para el CMg.
    _escribir_cmg_coordinador(
        tmp_path / "cmg.xlsx", [("2025-01-01", ["58,62", "64,86"])]
    )
    (tmp_path / "gen.csv").write_text(
        "timestamp,generacion_w\n2015-01-01T00:00,0\n2015-01-01T01:00,5000\n", encoding="utf-8"
    )
    salida = tmp_path / "planta.csv"
    codigo = main(
        [
            "alinear", "--por-posicion",
            "--cmg", str(tmp_path / "cmg.xlsx"),
            "--col-ts-cmg", "Fecha", "--col-hora-cmg", "Hora",
            "--col-cmg", "S.GREGORIO", "--escala-cmg", "1000",
            "--generacion", str(tmp_path / "gen.csv"),
            "--salida", str(salida),
        ]
    )
    assert codigo == 0
    observaciones = GatewayCSV(salida).cargar()
    assert len(observaciones) == 2
    assert observaciones[0].cmg.mills_por_mwh == 58_620


def test_cli_alinear_acepta_xlsx(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    _escribir_xlsx(
        tmp_path / "cmg.xlsx",
        [
            ["fecha_hora", "cmg_clp_kwh_"],
            [datetime(2025, 6, 1, 0, 0), "57,79415"],
            [datetime(2025, 6, 1, 1, 0), "60,0"],
        ],
    )
    _escribir_xlsx(
        tmp_path / "gen.xlsx",
        [["t", "kw"], ["2015-01-01T00:00", 0], ["2015-01-01T01:00", 12.5]],
    )
    salida = tmp_path / "planta.csv"
    codigo = main(
        [
            "alinear", "--por-posicion",
            "--cmg", str(tmp_path / "cmg.xlsx"),
            "--col-ts-cmg", "fecha_hora", "--col-cmg", "cmg_clp_kwh_", "--escala-cmg", "1000",
            "--generacion", str(tmp_path / "gen.xlsx"),
            "--col-ts-gen", "t", "--col-gen", "kw", "--escala-gen", "1000",
            "--salida", str(salida),
        ]
    )
    assert codigo == 0
    observaciones = GatewayCSV(salida).cargar()
    assert len(observaciones) == 2
    assert observaciones[1].generacion.w == 12_500  # 12.5 kW -> 12500 W
    assert observaciones[0].cmg.mills_por_mwh == 57_794  # 57,79415 CLP/kWh * 1000


def test_cli_backtest_naive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Señal periódica (período 2); el naive la reproduce -> corre sin error.
    lineas = ["timestamp,generacion_w,cmg_mills_por_mwh"]
    for i in range(8):
        lineas.append(f"2025-01-01T{i:02d}:00,{10 if i % 2 else 20},{100 if i % 2 else 200}")
    (tmp_path / "planta.csv").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    codigo = main(
        [
            "backtest", "--planta", str(tmp_path / "planta.csv"),
            "--horizonte", "2", "--folds", "2", "--estacionalidad", "2",
            "--modelos", "naive",
        ]
    )
    assert codigo == 0
    assert "naive" in capsys.readouterr().out


def test_cli_alinear_por_posicion(tmp_path: Path) -> None:
    # CMg de 2024 y generación de 2015 (años distintos): se unen por posición
    (tmp_path / "cmg.csv").write_text(
        "timestamp,cmg_mills_por_mwh\n2024-06-01T00:00,90000\n2024-06-01T12:00,5000\n",
        encoding="utf-8",
    )
    (tmp_path / "gen.csv").write_text(
        "timestamp,generacion_w\n2015-01-01T00:00,0\n2015-01-01T12:00,80000\n",
        encoding="utf-8",
    )
    salida = tmp_path / "planta.csv"
    codigo = main(
        [
            "alinear", "--por-posicion",
            "--cmg", str(tmp_path / "cmg.csv"),
            "--generacion", str(tmp_path / "gen.csv"),
            "--salida", str(salida),
        ]
    )
    assert codigo == 0
    observaciones = GatewayCSV(salida).cargar()
    assert len(observaciones) == 2
    assert observaciones[1].generacion.w == 80_000
    assert observaciones[1].cmg.mills_por_mwh == 5_000
