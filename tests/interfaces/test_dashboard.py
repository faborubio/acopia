"""Tests del dashboard demo (`GET /demo`): HTML autocontenido, datos y determinismo."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from acopia.interfaces.demo_dia import CMG_USD_MWH, sembrar_dia_demo
from acopia.interfaces.rest.app import crear_app

client = TestClient(crear_app())


def test_demo_responde_html() -> None:
    respuesta = client.get("/demo")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    assert "Acopia" in respuesta.text


def test_demo_es_autocontenido() -> None:
    """Sin recursos externos: el reporte debe abrir offline (portafolio/demo)."""
    texto = client.get("/demo").text
    assert "<script src" not in texto
    assert "<link" not in texto
    assert "url(" not in texto
    assert texto.count("https://") == 1  # solo el enlace al repo en el footer


def test_demo_lleva_el_dia_completo() -> None:
    """La tabla server-side trae las 24 horas (legible sin JavaScript)."""
    texto = client.get("/demo").text
    for hora in ("00:00", "12:00", "23:00"):
        assert hora in texto
    assert texto.count('class="motivo"') == 24  # una celda de motivo por hora


def test_demo_embebe_los_datos_del_plan() -> None:
    """El data island coincide con el escenario sembrado (misma fuente que el MCP)."""
    texto = client.get("/demo").text
    crudo = texto.split("const D = ", 1)[1].split(";\n", 1)[0]
    datos = json.loads(crudo)
    assert datos["cmg_mills"] == [c * 1_000 for c in CMG_USD_MWH]
    assert len(datos["accion"]) == 24
    assert len(datos["motivo"]) == 24
    assert "DESCARGAR" in datos["accion"]  # el arbitraje descarga en la punta


def test_demo_es_determinista() -> None:
    assert client.get("/demo").text == client.get("/demo").text


def test_dia_demo_compartido_reproducible() -> None:
    """MCP y dashboard cuentan el mismo día: mismo plan con la misma semilla."""
    a, b = sembrar_dia_demo(), sembrar_dia_demo()
    assert a.plan.acciones == b.plan.acciones
    assert a.plan.ingreso_esperado_mills == b.plan.ingreso_esperado_mills
