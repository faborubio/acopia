"""Tests del GatewayCSV: carga, validaciones y la ruta dato real -> forecaster."""

from __future__ import annotations

from pathlib import Path

import pytest

from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.infrastructure.forecasting.forecaster_estacional import ForecasterEstacionalNaive
from acopia.infrastructure.ingesta.gateway_csv import GatewayCSV

FIXTURE = Path(__file__).parent / "datos" / "muestra_planta.csv"


def test_carga_la_serie_completa() -> None:
    observaciones = GatewayCSV(FIXTURE).cargar()
    assert len(observaciones) == 8
    assert observaciones[0].generacion == Potencia(0)
    assert observaciones[0].cmg == Precio(90_000)
    # mediodía del día 2 con generación 78500.4 -> redondea a 78500
    assert observaciones[6].generacion == Potencia(78_500)
    assert observaciones[2].cmg == Precio(5_000)  # CMg bajo de mediodía


def test_archivo_inexistente() -> None:
    with pytest.raises(FileNotFoundError):
        GatewayCSV(Path("no") / "existe.csv").cargar()


def test_columna_faltante(tmp_path: Path) -> None:
    ruta = tmp_path / "incompleto.csv"
    ruta.write_text("timestamp,generacion_w\n2025-01-01T00:00,0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Faltan columnas"):
        GatewayCSV(ruta).cargar()


def test_csv_sin_filas(tmp_path: Path) -> None:
    ruta = tmp_path / "vacio.csv"
    ruta.write_text("timestamp,generacion_w,cmg_mills_por_mwh\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no contiene filas"):
        GatewayCSV(ruta).cargar()


def test_valor_no_numerico_reporta_la_fila(tmp_path: Path) -> None:
    ruta = tmp_path / "malo.csv"
    ruta.write_text(
        "generacion_w,cmg_mills_por_mwh\n100,5000\nABC,6000\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Fila 3"):
        GatewayCSV(ruta).cargar()


def test_lee_coma_decimal_chilena(tmp_path: Path) -> None:
    ruta = tmp_path / "chileno.csv"
    ruta.write_text(
        "timestamp,generacion_w,cmg_mills_por_mwh\n2025-06-01 00:00,80000,\"57,79415\"\n",
        encoding="utf-8",
    )
    observaciones = GatewayCSV(ruta).cargar()
    assert observaciones[0].cmg == Precio(58)  # 57,79415 -> 58


def test_generacion_negativa_reporta_la_fila(tmp_path: Path) -> None:
    ruta = tmp_path / "negativo.csv"
    ruta.write_text(
        "generacion_w,cmg_mills_por_mwh\n-100,5000\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Fila 2"):
        GatewayCSV(ruta).cargar()


def test_la_serie_real_alimenta_al_forecaster() -> None:
    # Ruta completa: CSV (datos) -> Observaciones -> escenarios pronosticados.
    historia = GatewayCSV(FIXTURE).cargar()
    forecaster = ForecasterEstacionalNaive(estacionalidad=4)
    escenarios = forecaster.pronosticar(historia, horizonte=4, n_escenarios=3, semilla=0)
    assert len(escenarios) == 3
    assert all(len(e.puntos) == 4 for e in escenarios)
    # el pronóstico puntual repite el patrón diario observado (mediodía soleado)
    assert escenarios[0].puntos[2].generacion == Potencia(78_500)
