"""Tests de MetricasForecast: RMSE y MAPE."""

from __future__ import annotations

import math

import pytest

from acopia.domain.services.metricas_forecast import MetricasForecast


def test_rmse() -> None:
    metricas = MetricasForecast()
    # errores [0, 10] -> sqrt((0 + 100) / 2) = sqrt(50)
    assert metricas.rmse([10.0, 20.0], [10.0, 30.0]) == pytest.approx(math.sqrt(50))


def test_rmse_perfecto_es_cero() -> None:
    metricas = MetricasForecast()
    assert metricas.rmse([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0


def test_mape_omite_reales_nulos() -> None:
    metricas = MetricasForecast()
    # solo cuenta el primer punto: |(100-90)/100| = 10 %
    assert metricas.mape([90.0, 5.0], [100.0, 0.0]) == pytest.approx(10.0)


def test_mape_todo_cero_es_cero() -> None:
    metricas = MetricasForecast()
    assert metricas.mape([1.0, 2.0], [0.0, 0.0]) == 0.0


def test_largos_distintos_es_error() -> None:
    metricas = MetricasForecast()
    with pytest.raises(ValueError):
        metricas.rmse([1.0], [1.0, 2.0])
