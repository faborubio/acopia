"""Adaptadores de persistencia (implementan los repositorios del dominio)."""

from acopia.infrastructure.persistencia.repositorio_planes_memoria import (
    RepositorioPlanesEnMemoria,
)

__all__ = ["RepositorioPlanesEnMemoria"]
