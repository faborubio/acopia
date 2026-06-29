"""App FastAPI: expone PlanificarDespacho y la consulta de planes.

`crear_app` es la raíz de composición (wiring): construye los adaptadores de
infraestructura y el caso de uso. Permite inyectar dobles en tests.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from acopia.application.planificar_despacho import PlanificarDespacho
from acopia.domain.ports.puerto_optimizador import PuertoOptimizador
from acopia.domain.ports.repositorio_planes import RepositorioPlanes
from acopia.infrastructure.optimizacion.optimizador_lp import OptimizadorLP
from acopia.infrastructure.persistencia.repositorio_planes_memoria import (
    RepositorioPlanesEnMemoria,
)
from acopia.interfaces.rest.esquemas import PlanDTO, PlanificarRequest


def crear_app(
    optimizador: PuertoOptimizador | None = None,
    repositorio: RepositorioPlanes | None = None,
) -> FastAPI:
    optimizador = optimizador or OptimizadorLP()
    repositorio = repositorio or RepositorioPlanesEnMemoria()
    caso = PlanificarDespacho(optimizador, repositorio)

    app = FastAPI(title="Acopia", version="0.1.0", description="Motor de despacho PV-BESS")

    @app.get("/salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    @app.post("/planes", response_model=PlanDTO)
    def planificar(peticion: PlanificarRequest) -> PlanDTO:
        try:
            resultado = caso.ejecutar(
                peticion.planta.a_dominio(),
                peticion.estado_inicial.a_dominio(),
                peticion.escenario.a_dominio(),
                peticion.politica.a_dominio(),
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return PlanDTO.desde_dominio(resultado.plan, resultado.plan_id)

    @app.get("/planes/{plan_id}", response_model=PlanDTO)
    def obtener(plan_id: str) -> PlanDTO:
        try:
            plan, _ = repositorio.obtener(plan_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=f"No existe el plan {plan_id}") from error
        return PlanDTO.desde_dominio(plan, plan_id)

    return app


app = crear_app()
