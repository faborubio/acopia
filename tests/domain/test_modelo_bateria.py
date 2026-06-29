"""Tests del ModeloBateria: ejemplos concretos + property-tests de determinismo y factibilidad.

Cubren los dos requisitos de calidad clave de la Fase 1 (anticipados en Fase 0):
- **Reproducibilidad/determinismo:** misma entrada -> mismo estado (property-test).
- **Factibilidad:** toda acción aceptada deja el SoC dentro de [min, max] y el
  throughput bajo la garantía — 0 violaciones.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given

from acopia.domain.entities.accion_despacho import AccionDespacho, TipoAccion
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.services.modelo_bateria import AccionInfactible, ModeloBateria
from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.soc import Soc

UNA_HORA = Intervalo.de_minutos(60)


def _bateria_ejemplo(throughput_garantia: int = 10_000_000) -> Bateria:
    """Batería de 100 kWh, 50 kW, 95 % ida y vuelta, SoC operativo 10 %-90 %."""
    return Bateria(
        capacidad=Energia(100_000),
        potencia_max_carga=Potencia(50_000),
        potencia_max_descarga=Potencia(50_000),
        eficiencia_carga=Eficiencia.de_porcentaje(95),
        eficiencia_descarga=Eficiencia.de_porcentaje(95),
        soc_min=Soc.de_porcentaje(10),
        soc_max=Soc.de_porcentaje(90),
        throughput_garantia=Energia(throughput_garantia),
    )


# --------------------------------------------------------------------------- #
# Ejemplos concretos (anclan los números)
# --------------------------------------------------------------------------- #


class TestEjemplos:
    def setup_method(self) -> None:
        self.modelo = ModeloBateria()
        self.bateria = _bateria_ejemplo()

    def test_cargar_actualiza_energia_y_throughput(self) -> None:
        estado = EstadoBateria(Energia(50_000))
        accion = AccionDespacho.cargar(Potencia(40_000))  # 40 kWh desde la red
        nuevo = self.modelo.aplicar(self.bateria, estado, accion, UNA_HORA)
        # 95 % de 40 000 = 38 000 Wh a celdas
        assert nuevo.energia_almacenada == Energia(88_000)
        assert nuevo.throughput_acumulado == Energia(38_000)

    def test_retener_no_cambia_el_estado(self) -> None:
        estado = EstadoBateria(Energia(50_000), Energia(123))
        nuevo = self.modelo.aplicar(self.bateria, estado, AccionDespacho.retener(), UNA_HORA)
        assert nuevo == estado

    def test_cargar_sobre_el_maximo_es_infactible(self) -> None:
        estado = EstadoBateria(Energia(89_000))  # tope operativo 90 000
        accion = AccionDespacho.cargar(Potencia(50_000))
        with pytest.raises(AccionInfactible):
            self.modelo.aplicar(self.bateria, estado, accion, UNA_HORA)

    def test_descargar_bajo_el_minimo_es_infactible(self) -> None:
        estado = EstadoBateria(Energia(11_000))  # piso operativo 10 000
        accion = AccionDespacho.descargar(Potencia(50_000))
        with pytest.raises(AccionInfactible):
            self.modelo.aplicar(self.bateria, estado, accion, UNA_HORA)

    def test_potencia_sobre_el_maximo_es_infactible(self) -> None:
        estado = EstadoBateria(Energia(50_000))
        accion = AccionDespacho.cargar(Potencia(50_001))
        with pytest.raises(AccionInfactible):
            self.modelo.aplicar(self.bateria, estado, accion, UNA_HORA)

    def test_throughput_garantia_agotado_es_infactible(self) -> None:
        bateria = _bateria_ejemplo(throughput_garantia=1_000)
        estado = EstadoBateria(Energia(50_000))
        accion = AccionDespacho.cargar(Potencia(40_000))  # 38 000 Wh > 1 000 de garantía
        with pytest.raises(AccionInfactible):
            self.modelo.aplicar(bateria, estado, accion, UNA_HORA)


# --------------------------------------------------------------------------- #
# Estrategias para property-tests
# --------------------------------------------------------------------------- #


@st.composite
def baterias(draw: st.DrawFn) -> Bateria:
    capacidad = draw(st.integers(min_value=1_000, max_value=5_000_000))
    soc_min = draw(st.integers(min_value=0, max_value=10_000))
    soc_max = draw(st.integers(min_value=soc_min, max_value=10_000))
    return Bateria(
        capacidad=Energia(capacidad),
        potencia_max_carga=Potencia(draw(st.integers(1, 5_000_000))),
        potencia_max_descarga=Potencia(draw(st.integers(1, 5_000_000))),
        eficiencia_carga=Eficiencia(draw(st.integers(5_000, 10_000))),
        eficiencia_descarga=Eficiencia(draw(st.integers(5_000, 10_000))),
        soc_min=Soc(soc_min),
        soc_max=Soc(soc_max),
        throughput_garantia=Energia(draw(st.integers(0, 50_000_000))),
    )


@st.composite
def estados_de(draw: st.DrawFn, bateria: Bateria) -> EstadoBateria:
    energia = draw(st.integers(bateria.energia_min.wh, bateria.energia_max.wh))
    throughput = draw(st.integers(0, bateria.throughput_garantia.wh))
    return EstadoBateria(Energia(energia), Energia(throughput))


@st.composite
def acciones(draw: st.DrawFn) -> AccionDespacho:
    tipo = draw(st.sampled_from(list(TipoAccion)))
    if tipo is TipoAccion.RETENER:
        return AccionDespacho.retener()
    return AccionDespacho(tipo, Potencia(draw(st.integers(1, 10_000_000))))


@st.composite
def escenarios(draw: st.DrawFn) -> tuple[Bateria, EstadoBateria, AccionDespacho, Intervalo]:
    bateria = draw(baterias())
    estado = draw(estados_de(bateria))
    accion = draw(acciones())
    intervalo = Intervalo.de_minutos(draw(st.sampled_from([5, 15, 30, 60])))
    return bateria, estado, accion, intervalo


# --------------------------------------------------------------------------- #
# Property-tests
# --------------------------------------------------------------------------- #


@given(escenarios())
def test_determinismo(esc: tuple[Bateria, EstadoBateria, AccionDespacho, Intervalo]) -> None:
    bateria, estado, accion, intervalo = esc
    modelo = ModeloBateria()
    if modelo.es_factible(bateria, estado, accion, intervalo):
        assert modelo.aplicar(bateria, estado, accion, intervalo) == modelo.aplicar(
            bateria, estado, accion, intervalo
        )


@given(escenarios())
def test_factible_respeta_limites(
    esc: tuple[Bateria, EstadoBateria, AccionDespacho, Intervalo],
) -> None:
    bateria, estado, accion, intervalo = esc
    modelo = ModeloBateria()
    if not modelo.es_factible(bateria, estado, accion, intervalo):
        return
    nuevo = modelo.aplicar(bateria, estado, accion, intervalo)
    assert bateria.energia_min.wh <= nuevo.energia_almacenada.wh <= bateria.energia_max.wh
    assert nuevo.throughput_acumulado.wh <= bateria.throughput_garantia.wh


@given(escenarios())
def test_es_factible_coherente_con_aplicar(
    esc: tuple[Bateria, EstadoBateria, AccionDespacho, Intervalo],
) -> None:
    bateria, estado, accion, intervalo = esc
    modelo = ModeloBateria()
    if modelo.es_factible(bateria, estado, accion, intervalo):
        modelo.aplicar(bateria, estado, accion, intervalo)  # no debe lanzar
    else:
        with pytest.raises(AccionInfactible):
            modelo.aplicar(bateria, estado, accion, intervalo)


@st.composite
def secuencias(
    draw: st.DrawFn,
) -> tuple[Bateria, EstadoBateria, list[AccionDespacho], Intervalo]:
    bateria = draw(baterias())
    estado = draw(estados_de(bateria))
    lista = draw(st.lists(acciones(), min_size=1, max_size=20))
    intervalo = Intervalo.de_minutos(draw(st.sampled_from([5, 15, 30, 60])))
    return bateria, estado, lista, intervalo


def _reproducir(
    modelo: ModeloBateria,
    bateria: Bateria,
    estado: EstadoBateria,
    acciones_: list[AccionDespacho],
    intervalo: Intervalo,
) -> EstadoBateria:
    actual = estado
    for accion in acciones_:
        if modelo.es_factible(bateria, actual, accion, intervalo):
            actual = modelo.aplicar(bateria, actual, accion, intervalo)
    return actual


@given(secuencias())
def test_secuencia_reproducible(
    seq: tuple[Bateria, EstadoBateria, list[AccionDespacho], Intervalo],
) -> None:
    bateria, estado, lista, intervalo = seq
    modelo = ModeloBateria()
    assert _reproducir(modelo, bateria, estado, lista, intervalo) == _reproducir(
        modelo, bateria, estado, lista, intervalo
    )
