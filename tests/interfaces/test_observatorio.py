"""Tests de los agregados del Observatorio (ADR-012)."""

from __future__ import annotations

import pytest

from acopia.infrastructure.ingesta.reducciones_erv import ReduccionDiaria
from acopia.interfaces.observatorio.agregados import (
    duck_curve_usd_mwh,
    perfil_horario_mwh,
    top_centrales,
    total_mensual_gwh,
    valor_desplazamiento_usd,
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


def _dia_cmg(fecha: str, mills_por_hora: list[int]) -> list[tuple[str, int]]:
    return [(f"{fecha}T{h:02d}:00", mills_por_hora[h]) for h in range(24)]


def test_duck_curve_promedia_por_hora_en_usd() -> None:
    dia_barato = _dia_cmg("2025-01-01", [10_000] * 24)
    dia_caro = _dia_cmg("2025-01-02", [30_000] * 24)
    curva = duck_curve_usd_mwh(dia_barato + dia_caro)
    assert curva == (20.0,) * 24  # (10k + 30k) / 2 mills = 20 USD/MWh


def test_duck_curve_exige_cobertura_de_24_horas() -> None:
    with pytest.raises(ValueError, match="no cubre"):
        duck_curve_usd_mwh([("2025-01-01T05:00", 1_000)])


def test_valor_desplazamiento_es_el_diferencial_contra_la_punta() -> None:
    # CMg 0 a mediodía y punta de 100 USD/MWh; 10 MWh vertidos a mediodía.
    cmg = [50.0] * 24
    cmg[12], cmg[20] = 0.0, 100.0
    vertido = [0.0] * 24
    vertido[12] = 10.0
    # 10 MWh * (0.85 * 100 - 0) = 850 USD
    assert valor_desplazamiento_usd(vertido, cmg, eficiencia=0.85) == pytest.approx(850.0)


def test_valor_desplazamiento_no_premia_vertido_en_horas_caras() -> None:
    # Con CMg plano, desplazar pierde la eficiencia: max(0, eta*p - p) = 0.
    assert valor_desplazamiento_usd([1.0] * 24, [100.0] * 24) == 0.0


def test_valor_desplazamiento_valida_la_eficiencia() -> None:
    with pytest.raises(ValueError, match="Eficiencia"):
        valor_desplazamiento_usd([0.0] * 24, [1.0] * 24, eficiencia=0.0)
    with pytest.raises(ValueError, match="Eficiencia"):
        valor_desplazamiento_usd([0.0] * 24, [1.0] * 24, eficiencia=1.2)


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
