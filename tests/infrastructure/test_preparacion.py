"""Tests de los helpers de preparación de datos y la CLI de alineación."""

from __future__ import annotations

from pathlib import Path

import pytest

from acopia.infrastructure.ingesta.gateway_csv import GatewayCSV
from acopia.infrastructure.ingesta.preparacion import (
    alinear_series,
    escribir_csv_planta,
    extraer_cmg,
    leer_serie_csv,
)
from acopia.interfaces.cli.preparar_datos import main


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


def test_leer_serie_csv_escala_y_redondea(tmp_path: Path) -> None:
    ruta = tmp_path / "gen.csv"
    ruta.write_text("timestamp,gen_kw\n2025-01-01T12:00,80.4\n", encoding="utf-8")
    # kW -> W con factor 1000; 80.4 kW -> 80400 W
    serie = leer_serie_csv(ruta, "timestamp", "gen_kw", escala=1000)
    assert serie == [("2025-01-01T12:00", 80_400)]


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
