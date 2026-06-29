"""Tests de los value objects: invariantes y aritmética entera determinista."""

from __future__ import annotations

import pytest

from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.soc import Soc


class TestEnergia:
    def test_no_admite_negativos(self) -> None:
        with pytest.raises(ValueError):
            Energia(-1)

    def test_suma_y_resta(self) -> None:
        assert Energia(100) + Energia(50) == Energia(150)
        assert Energia(100) - Energia(40) == Energia(60)

    def test_resta_negativa_es_error(self) -> None:
        with pytest.raises(ValueError):
            Energia(10) - Energia(20)


class TestPotencia:
    def test_energia_en_intervalo_es_floor(self) -> None:
        # 1000 W durante 90 s = 25 Wh (90000/3600 = 25.0)
        assert Potencia(1000).energia_en(Intervalo(90)) == Energia(25)
        # 1000 W durante 100 s = 27.77... -> floor 27 Wh
        assert Potencia(1000).energia_en(Intervalo(100)) == Energia(27)

    def test_no_admite_negativos(self) -> None:
        with pytest.raises(ValueError):
            Potencia(-5)


class TestEficiencia:
    def test_aplicar_y_revertir(self) -> None:
        ef = Eficiencia.de_porcentaje(95)  # 9500 pb
        assert ef.aplicar(Energia(40_000)) == Energia(38_000)
        assert ef.revertir(Energia(38_000)) == Energia(40_000)

    def test_fuera_de_rango_es_error(self) -> None:
        with pytest.raises(ValueError):
            Eficiencia(10_001)

    def test_revertir_con_eficiencia_nula_es_error(self) -> None:
        with pytest.raises(ValueError):
            Eficiencia(0).revertir(Energia(100))


class TestSoc:
    def test_desde_energia(self) -> None:
        assert Soc.desde_energia(Energia(50), Energia(100)) == Soc.de_porcentaje(50)

    def test_energia_en_capacidad(self) -> None:
        assert Soc.de_porcentaje(90).energia_en(Energia(100_000)) == Energia(90_000)

    def test_capacidad_nula_es_error(self) -> None:
        with pytest.raises(ValueError):
            Soc.desde_energia(Energia(0), Energia(0))


class TestIntervalo:
    def test_de_minutos(self) -> None:
        assert Intervalo.de_minutos(15) == Intervalo(900)

    def test_no_positivo_es_error(self) -> None:
        with pytest.raises(ValueError):
            Intervalo(0)
