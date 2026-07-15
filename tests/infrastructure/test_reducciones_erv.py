"""Tests del lector del XLSX "Reducciones ERV" del Coordinador (ADR-012)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from acopia.infrastructure.ingesta.reducciones_erv import (
    ReduccionDiaria,
    leer_reducciones_erv,
)


def _escribir_erv(
    ruta: Path,
    hojas: dict[str, list[tuple[str, list[tuple[str, list[float]]]]]],
) -> None:
    """Emula el XLSX real: por hoja, bloques por día con título, header 1..24 y Total.

    ``hojas`` = {nombre_hoja: [(fecha, [(central, [24 MWh]), ...]), ...]}.
    """
    openpyxl = pytest.importorskip("openpyxl")
    libro = openpyxl.Workbook()
    libro.remove(libro.active)
    for nombre, dias in hojas.items():
        ws = libro.create_sheet(nombre)
        ws.append([])  # el archivo real trae filas de adorno sobre cada bloque
        ws.append([None, "CURTAILMENTS POR CENTRALES EN FORMA DIARIA/HORARIA"])
        for fecha, centrales in dias:
            ws.append([])
            # en el archivo real la fecha es una fórmula; el lector ve el valor cacheado
            ws.append([None, datetime.fromisoformat(f"{fecha}T00:00:00")])
            ws.append([])
            ws.append([None, "Central/Hora", None, None, *range(1, 25), "Total"])
            for central, valores in centrales:
                ws.append([None, central, None, None, *valores, sum(valores)])
            ws.append([None, "Total", None, None, *([0.0] * 24), 0.0])
    libro.save(ruta)


def _dia_soleado(mwh_hora_13: float) -> list[float]:
    valores = [0.0] * 24
    valores[12] = mwh_hora_13  # hora 13 del Coordinador = índice 12
    return valores


def test_aplana_bloques_por_dia_y_omite_totales(tmp_path: Path) -> None:
    ruta = tmp_path / "erv.xlsx"
    _escribir_erv(
        ruta,
        {
            "Resumen-DiarioHorario-Solar": [
                ("2026-05-01", [("PFV-UNO", _dia_soleado(4.5)), ("PFV-DOS", [1.0] * 24)]),
                ("2026-05-02", [("PFV-UNO", _dia_soleado(2.25))]),
            ],
            "Resumen-DiarioHorario-Eólico": [
                ("2026-05-01", [("PE-TCHAMMA", [0.5] * 24)]),
            ],
        },
    )
    registros = leer_reducciones_erv(ruta)

    assert len(registros) == 4  # 3 solares + 1 eólico; ninguna fila Total
    assert {r.central for r in registros} == {"PFV-UNO", "PFV-DOS", "PE-TCHAMMA"}
    primero = registros[0]
    assert primero == ReduccionDiaria(
        "solar", "PFV-UNO", "2026-05-01", tuple(_dia_soleado(4.5))
    )
    assert primero.total_mwh == pytest.approx(4.5)
    eolico = [r for r in registros if r.tecnologia == "eolica"]
    assert len(eolico) == 1 and eolico[0].total_mwh == pytest.approx(12.0)


def test_mapea_las_cuatro_tecnologias_e_ignora_hojas_resumen(tmp_path: Path) -> None:
    ruta = tmp_path / "erv.xlsx"
    dia = [("2026-05-01", [("CENTRAL-X", [1.0] * 24)])]
    _escribir_erv(
        ruta,
        {
            "Resumen-Mensual": [],  # se ignora aunque exista
            "Resumen-DiarioHorario-Eólico": dia,
            "Resumen-DiarioHorario-Solar": dia,
            "Resumen-DiarioHorario-HP": dia,
            "Resumen-DiarioHorario-HE": dia,
            "Acumulado-Anual-Solar": [],  # se ignora
        },
    )
    tecnologias = {r.tecnologia for r in leer_reducciones_erv(ruta)}
    assert tecnologias == {"eolica", "solar", "hidro_pasada", "hidro_embalse"}


def test_celda_vacia_cuenta_como_cero(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    ruta = tmp_path / "erv.xlsx"
    _escribir_erv(
        ruta,
        {"Resumen-DiarioHorario-Solar": [("2026-05-01", [("PFV-UNO", [1.0] * 24)])]},
    )
    libro = openpyxl.load_workbook(ruta)
    hoja = libro["Resumen-DiarioHorario-Solar"]
    fila_central = next(
        celda.row for fila in hoja.iter_rows() for celda in fila if celda.value == "PFV-UNO"
    )
    # openpyxl ignora value=None en cell(); hay que asignar la propiedad
    hoja.cell(row=fila_central, column=10).value = None  # borra la hora 6 de PFV-UNO
    libro.save(ruta)

    (registro,) = leer_reducciones_erv(ruta)
    assert registro.energia_mwh[5] == 0.0
    assert registro.total_mwh == pytest.approx(23.0)


def test_guion_contable_cuenta_como_cero(tmp_path: Path) -> None:
    """El archivo real de mayo 2026 trae '-' por 'sin reducción' (hoja eólica)."""
    openpyxl = pytest.importorskip("openpyxl")
    ruta = tmp_path / "erv.xlsx"
    _escribir_erv(
        ruta,
        {"Resumen-DiarioHorario-Solar": [("2026-05-01", [("PFV-UNO", [1.0] * 24)])]},
    )
    libro = openpyxl.load_workbook(ruta)
    hoja = libro["Resumen-DiarioHorario-Solar"]
    fila_central = next(
        celda.row for fila in hoja.iter_rows() for celda in fila if celda.value == "PFV-UNO"
    )
    hoja.cell(row=fila_central, column=5, value="-")  # hora 1
    libro.save(ruta)

    (registro,) = leer_reducciones_erv(ruta)
    assert registro.energia_mwh[0] == 0.0
    assert registro.total_mwh == pytest.approx(23.0)


def test_vertimiento_negativo_es_error_con_ubicacion(tmp_path: Path) -> None:
    ruta = tmp_path / "erv.xlsx"
    valores = [0.0] * 24
    valores[7] = -1.0
    _escribir_erv(
        ruta,
        {"Resumen-DiarioHorario-Solar": [("2026-05-01", [("PFV-UNO", valores)])]},
    )
    with pytest.raises(ValueError, match=r"hora 8.*negativo"):
        leer_reducciones_erv(ruta)


def test_typo_en_el_header_se_repara_por_posicion(tmp_path: Path) -> None:
    """Mayo 2026 real: la hora 2 del header venía como '|'; las columnas son contiguas."""
    openpyxl = pytest.importorskip("openpyxl")
    ruta = tmp_path / "erv.xlsx"
    valores = [float(h) for h in range(1, 25)]  # hora h vale h MWh: detecta desfases
    _escribir_erv(
        ruta,
        {"Resumen-DiarioHorario-Solar": [("2026-05-01", [("PFV-UNO", valores)])]},
    )
    libro = openpyxl.load_workbook(ruta)
    hoja = libro["Resumen-DiarioHorario-Solar"]
    fila_header = next(
        celda.row for fila in hoja.iter_rows() for celda in fila if celda.value == "Central/Hora"
    )
    hoja.cell(row=fila_header, column=6, value="|")  # el typo real: hora 2 -> '|'
    libro.save(ruta)

    (registro,) = leer_reducciones_erv(ruta)
    assert registro.energia_mwh == tuple(valores)  # sin desfase: hora 2 sigue siendo 2.0


def test_header_incompleto_es_error(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    ruta = tmp_path / "erv.xlsx"
    libro = openpyxl.Workbook()
    ws = libro.active
    ws.title = "Resumen-DiarioHorario-Solar"
    ws.append([None, datetime.fromisoformat("2026-05-01T00:00:00")])
    ws.append([None, "Central/Hora", None, None, *range(1, 12)])  # solo 11 horas
    libro.save(ruta)
    with pytest.raises(ValueError, match="24 horas"):
        leer_reducciones_erv(ruta)


def test_sin_hojas_erv_es_error_claro(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    ruta = tmp_path / "otro.xlsx"
    libro = openpyxl.Workbook()
    libro.active.title = "Hoja1"
    libro.save(ruta)
    with pytest.raises(ValueError, match="Reducciones ERV"):
        leer_reducciones_erv(ruta)
