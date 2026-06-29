"""Entidades del dominio."""

from acopia.domain.entities.accion_despacho import AccionDespacho, TipoAccion
from acopia.domain.entities.bateria import Bateria
from acopia.domain.entities.estado_bateria import EstadoBateria

__all__ = ["AccionDespacho", "Bateria", "EstadoBateria", "TipoAccion"]
