"""Tests de los agregados del Observatorio (ADR-012)."""

from __future__ import annotations

import pytest

from acopia.infrastructure.ingesta.reducciones_erv import ReduccionDiaria
from acopia.interfaces.observatorio.agregados import (
    perfil_horario_mwh,
    top_centrales,
    total_mensual_gwh,
)


def _registro(
    tecnologia: str, central: str, fecha: str, mwh_por_hora: float
) -> ReduccionDiaria:
    return ReduccionDiaria(tecnologia, central, fecha, (mwh_por_hora,) * 24)


def test_total_mensual_agrupa_por_mes_y_tecnologia() -> None:
    registros = (
        _registro("solar", "PFV-UNO", "2026-05-01", 10.0),  # 240 MWh
        _registro("solar", "PFV-DOS", "2026-05-15", 5.0),  # 120 MWh
        _registro("solar", "PFV-UNO", "2026-06-01", 1.0),  # otro mes
        _registro("eolica", "PE-UNO", "2026-05-01", 2.0),  # otra tecnología
    )
    totales = total_mensual_gwh(registros)
    assert totales[("2026-05", "solar")] == pytest.approx(0.360)
    assert totales[("2026-06", "solar")] == pytest.approx(0.024)
    assert totales[("2026-05", "eolica")] == pytest.approx(0.048)


def test_perfil_horario_suma_cada_hora_por_tecnologia() -> None:
    mediodia = [0.0] * 24
    mediodia[12] = 100.0  # hora 13
    registros = (
        ReduccionDiaria("solar", "PFV-UNO", "2026-05-01", tuple(mediodia)),
        ReduccionDiaria("solar", "PFV-DOS", "2026-05-02", tuple(mediodia)),
        _registro("eolica", "PE-UNO", "2026-05-01", 1.0),
    )
    perfiles = perfil_horario_mwh(registros)
    assert perfiles["solar"][12] == pytest.approx(200.0)
    assert sum(perfiles["solar"]) == pytest.approx(200.0)  # el resto del día en cero
    assert perfiles["eolica"] == (1.0,) * 24


def test_top_centrales_ordena_desc_y_corta_en_n() -> None:
    registros = (
        _registro("solar", "PFV-CHICA", "2026-05-01", 1.0),
        _registro("solar", "PFV-GRANDE", "2026-05-01", 10.0),
        _registro("solar", "PFV-GRANDE", "2026-05-02", 10.0),
        _registro("eolica", "PE-MEDIANA", "2026-05-01", 5.0),
    )
    top = top_centrales(registros, n=2)
    assert [(central, tec) for central, tec, _ in top] == [
        ("PFV-GRANDE", "solar"),
        ("PE-MEDIANA", "eolica"),
    ]
    assert [total for _, _, total in top] == pytest.approx([480.0, 120.0])


def test_top_centrales_desempata_alfabetico_determinista() -> None:
    registros = (
        _registro("solar", "PFV-ZETA", "2026-05-01", 1.0),
        _registro("solar", "PFV-ALFA", "2026-05-01", 1.0),
    )
    top = top_centrales(registros, n=2)
    assert [central for central, _, _ in top] == ["PFV-ALFA", "PFV-ZETA"]
