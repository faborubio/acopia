"""Tests del render de la página de vertimiento del Observatorio (ADR-012)."""

from __future__ import annotations

from pathlib import Path

import pytest

from acopia.infrastructure.ingesta.reducciones_erv import ReduccionDiaria
from acopia.interfaces.observatorio.sitio import render_vertimiento


def _registro(
    tecnologia: str, central: str, fecha: str, mwh_hora_13: float
) -> ReduccionDiaria:
    energia = [0.0] * 24
    energia[12] = mwh_hora_13
    return ReduccionDiaria(tecnologia, central, fecha, tuple(energia))


def _registros_demo() -> tuple[ReduccionDiaria, ...]:
    return (
        _registro("solar", "PFV-UNO", "2026-01-01", 3000.0),  # 3 GWh
        _registro("solar", "PFV-DOS", "2026-01-02", 1000.0),
        _registro("eolica", "PE-UNO", "2026-02-01", 1000.0),
    )


def test_render_es_html_autocontenido_con_kpis() -> None:
    pagina = render_vertimiento(_registros_demo(), generado_el="2026-07-15")
    assert pagina.startswith("<!DOCTYPE html>")
    assert "enero \u2013 febrero 2026" in pagina  # período (guión largo) derivado de los datos
    assert "2026-07-15" in pagina
    assert ">5 GWh<" in pagina  # KPI total: 3 + 1 + 1
    assert ">80%<" in pagina  # KPI solar: 4 de 5
    assert ">13:00<" in pagina  # hora pico (todo cae en la hora 13)
    # autocontenido: JS inline, sin hojas/imágenes/fuentes externas (los <a> sí se permiten)
    assert "<script" in pagina
    assert "<link" not in pagina and "src=" not in pagina


def test_tabla_mensual_trae_fila_por_mes_y_total() -> None:
    pagina = render_vertimiento(_registros_demo(), generado_el="2026-07-15")
    assert "Enero 2026" in pagina and "Febrero 2026" in pagina
    assert pagina.count("<tr>") == 3  # encabezado + una fila por mes (el total usa tr.total)
    assert '<tr class="total">' in pagina


def test_hit_targets_por_columna_y_por_central() -> None:
    pagina = render_vertimiento(_registros_demo(), generado_el="2026-07-15")
    # 2 meses + 24 horas + 3 centrales en el top
    assert pagina.count('class="hit"') == 2 + 24 + 3
    assert pagina.count("data-tooltip=") == 2 + 24 + 3


def test_escapa_nombres_de_central() -> None:
    registros = (_registro("solar", "PFV-<X>&", "2026-01-01", 10.0),)
    pagina = render_vertimiento(registros, generado_el="2026-07-15")
    assert "PFV-<X>" not in pagina
    assert "PFV-&lt;X&gt;&amp;" in pagina


def test_periodo_de_un_solo_mes_y_cruce_de_ano() -> None:
    un_mes = render_vertimiento(
        (_registro("solar", "PFV-UNO", "2026-05-01", 1.0),), generado_el="x"
    )
    assert "mayo 2026" in un_mes and "\u2013" not in un_mes.split("<h1")[1].split("</h1>")[0]
    cruce = render_vertimiento(
        (
            _registro("solar", "PFV-UNO", "2025-12-01", 1.0),
            _registro("solar", "PFV-UNO", "2026-01-01", 1.0),
        ),
        generado_el="x",
    )
    assert "diciembre 2025 \u2013 enero 2026" in cruce


def test_sin_registros_es_error() -> None:
    with pytest.raises(ValueError, match="Sin registros"):
        render_vertimiento((), generado_el="2026-07-15")


def test_enlace_a_la_demo_solo_si_el_sitio_la_incluye() -> None:
    con = render_vertimiento(_registros_demo(), generado_el="x", enlace_demo=True)
    sin = render_vertimiento(_registros_demo(), generado_el="x", enlace_demo=False)
    assert 'href="demo.html"' in con
    assert 'href="demo.html"' not in sin


def test_cli_observatorio_escribe_el_sitio(tmp_path: Path) -> None:
    """End-to-end: XLSX del formato del Coordinador -> sitio estático completo."""
    openpyxl = pytest.importorskip("openpyxl")
    from datetime import datetime

    from acopia.interfaces.cli.preparar_datos import main

    libro = openpyxl.Workbook()
    ws = libro.active
    ws.title = "Resumen-DiarioHorario-Solar"
    ws.append([None, datetime.fromisoformat("2026-05-01T00:00:00")])
    ws.append([None, "Central/Hora", None, None, *range(1, 25)])
    ws.append([None, "PFV-UNO", None, None, *([2.0] * 24)])
    ruta = tmp_path / "erv.xlsx"
    libro.save(ruta)

    salida = tmp_path / "sitio"
    codigo = main(
        ["observatorio", "--reducciones", str(ruta), "--salida", str(salida),
         "--sin-demo", "--fecha", "2026-07-15"]
    )
    assert codigo == 0
    pagina = (salida / "index.html").read_text(encoding="utf-8")
    assert "mayo 2026" in pagina and "PFV-UNO" in pagina
    assert not (salida / "demo.html").exists()  # --sin-demo
