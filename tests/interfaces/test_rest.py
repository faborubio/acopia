"""Tests del adaptador REST: planificar, consultar y manejo de errores."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from acopia.interfaces.rest.app import crear_app

client = TestClient(crear_app())


def _peticion_arbitraje() -> dict[str, Any]:
    return {
        "planta": {
            "bateria": {
                "capacidad_wh": 100_000,
                "potencia_max_carga_w": 50_000,
                "potencia_max_descarga_w": 50_000,
                "eficiencia_carga_pct": 100,
                "eficiencia_descarga_pct": 100,
                "soc_min_pct": 0,
                "soc_max_pct": 100,
                "throughput_garantia_wh": 10_000_000,
            },
            "potencia_max_inyeccion_w": 10_000_000,
        },
        "estado_inicial": {"energia_almacenada_wh": 0, "throughput_acumulado_wh": 0},
        "escenario": {
            "puntos": [
                {"generacion_w": 0, "cmg_mills_por_mwh": 10_000},
                {"generacion_w": 0, "cmg_mills_por_mwh": 10_000},
                {"generacion_w": 0, "cmg_mills_por_mwh": 500_000},
                {"generacion_w": 0, "cmg_mills_por_mwh": 500_000},
            ]
        },
        "politica": {
            "id": "arbitraje",
            "version": 1,
            "horizonte_intervalos": 4,
            "resolucion_min": 60,
            "semilla": 42,
        },
    }


def test_salud() -> None:
    assert client.get("/salud").json() == {"estado": "ok"}


def test_planificar_y_consultar() -> None:
    respuesta = client.post("/planes", json=_peticion_arbitraje())
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["ingreso_esperado_mills"] == 49_000
    tipos = [a["tipo"] for a in cuerpo["acciones"]]
    assert tipos == ["CARGAR", "CARGAR", "DESCARGAR", "DESCARGAR"]
    assert cuerpo["energia_vertida_wh"] == [0, 0, 0, 0]

    plan_id = cuerpo["plan_id"]
    consulta = client.get(f"/planes/{plan_id}")
    assert consulta.status_code == 200
    assert consulta.json()["acciones"] == cuerpo["acciones"]


def test_horizonte_incoherente_devuelve_422() -> None:
    peticion = _peticion_arbitraje()
    peticion["politica"]["horizonte_intervalos"] = 3  # el escenario tiene 4 puntos
    respuesta = client.post("/planes", json=peticion)
    assert respuesta.status_code == 422


def test_plan_inexistente_devuelve_404() -> None:
    assert client.get("/planes/no-existe").status_code == 404
