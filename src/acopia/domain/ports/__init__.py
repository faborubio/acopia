"""Puertos (interfaces) que el dominio define y la infraestructura implementa.

El forecast entra al optimizador como **dato** (escenarios), no como una llamada:
``PuertoForecaster`` se introduce en la Fase 2 junto con el Seq2Seq-LSTM.
"""

from acopia.domain.ports.puerto_forecaster import PuertoForecaster
from acopia.domain.ports.puerto_historia import PuertoHistoria
from acopia.domain.ports.puerto_optimizador import PuertoOptimizador
from acopia.domain.ports.repositorio_planes import RepositorioPlanes

__all__ = ["PuertoForecaster", "PuertoHistoria", "PuertoOptimizador", "RepositorioPlanes"]
