"""Esquemas Pydantic v2 de entrada/salida y su mapeo al dominio.

La traducción DTO <-> dominio vive en `interfaces/`; el dominio nunca importa
Pydantic. Las unidades son explícitas en el nombre del campo (wh, w, pct, mills).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from acopia.domain.entities.accion_despacho import AccionDespacho
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import Modo, Objetivo, PoliticaDespacho
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.domain.value_objects.soc import Soc


class BateriaDTO(BaseModel):
    capacidad_wh: int
    potencia_max_carga_w: int
    potencia_max_descarga_w: int
    eficiencia_carga_pct: int = Field(ge=0, le=100)
    eficiencia_descarga_pct: int = Field(gt=0, le=100)
    soc_min_pct: int = Field(ge=0, le=100)
    soc_max_pct: int = Field(ge=0, le=100)
    throughput_garantia_wh: int

    def a_dominio(self) -> Bateria:
        return Bateria(
            capacidad=Energia(self.capacidad_wh),
            potencia_max_carga=Potencia(self.potencia_max_carga_w),
            potencia_max_descarga=Potencia(self.potencia_max_descarga_w),
            eficiencia_carga=Eficiencia.de_porcentaje(self.eficiencia_carga_pct),
            eficiencia_descarga=Eficiencia.de_porcentaje(self.eficiencia_descarga_pct),
            soc_min=Soc.de_porcentaje(self.soc_min_pct),
            soc_max=Soc.de_porcentaje(self.soc_max_pct),
            throughput_garantia=Energia(self.throughput_garantia_wh),
        )


class PlantaDTO(BaseModel):
    bateria: BateriaDTO
    potencia_max_inyeccion_w: int
    potencia_max_retiro_w: int | None = None
    id: str = "planta"

    def a_dominio(self) -> Planta:
        retiro = (
            self.potencia_max_retiro_w
            if self.potencia_max_retiro_w is not None
            else self.potencia_max_inyeccion_w
        )
        return Planta(
            id=self.id,
            bateria=self.bateria.a_dominio(),
            potencia_max_inyeccion=Potencia(self.potencia_max_inyeccion_w),
            potencia_max_retiro=Potencia(retiro),
        )


class EstadoDTO(BaseModel):
    energia_almacenada_wh: int
    throughput_acumulado_wh: int = 0

    def a_dominio(self) -> EstadoBateria:
        return EstadoBateria(
            energia_almacenada=Energia(self.energia_almacenada_wh),
            throughput_acumulado=Energia(self.throughput_acumulado_wh),
        )


class PuntoDTO(BaseModel):
    generacion_w: int
    cmg_mills_por_mwh: int

    def a_dominio(self) -> PuntoPronostico:
        return PuntoPronostico(Potencia(self.generacion_w), Precio(self.cmg_mills_por_mwh))


class EscenarioDTO(BaseModel):
    puntos: list[PuntoDTO]
    probabilidad_bp: int = 10_000

    def a_dominio(self) -> Escenario:
        return Escenario(tuple(p.a_dominio() for p in self.puntos), self.probabilidad_bp)


class PoliticaDTO(BaseModel):
    id: str
    version: int
    horizonte_intervalos: int
    resolucion_min: int
    semilla: int
    objetivo: Objetivo = Objetivo.MAX_INGRESO
    modo: Modo = Modo.PREDICT_THEN_OPTIMIZE
    costo_ciclado_mills_por_mwh: int = 0

    def a_dominio(self) -> PoliticaDespacho:
        return PoliticaDespacho(
            id=self.id,
            version=self.version,
            objetivo=self.objetivo,
            horizonte_intervalos=self.horizonte_intervalos,
            resolucion=Intervalo.de_minutos(self.resolucion_min),
            semilla=self.semilla,
            modo=self.modo,
            costo_ciclado_mills_por_mwh=self.costo_ciclado_mills_por_mwh,
        )


class PlanificarRequest(BaseModel):
    planta: PlantaDTO
    estado_inicial: EstadoDTO
    escenario: EscenarioDTO
    politica: PoliticaDTO


class AccionDTO(BaseModel):
    tipo: str
    potencia_w: int

    @classmethod
    def desde_dominio(cls, accion: AccionDespacho) -> AccionDTO:
        return cls(tipo=accion.tipo.value, potencia_w=accion.potencia.w)


class PlanDTO(BaseModel):
    plan_id: str | None
    politica_id: str
    politica_version: int
    semilla: int
    ingreso_esperado_mills: int
    acciones: list[AccionDTO]
    energia_vertida_wh: list[int]

    @classmethod
    def desde_dominio(cls, plan: PlanDespacho, plan_id: str | None) -> PlanDTO:
        return cls(
            plan_id=plan_id,
            politica_id=plan.politica_id,
            politica_version=plan.politica_version,
            semilla=plan.semilla,
            ingreso_esperado_mills=plan.ingreso_esperado_mills,
            acciones=[AccionDTO.desde_dominio(a) for a in plan.acciones],
            energia_vertida_wh=list(plan.energia_vertida_wh),
        )
