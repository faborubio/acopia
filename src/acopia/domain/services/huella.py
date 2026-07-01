"""Huella determinista de la historia observada (para el snapshot as-seen, ADR-007).

Permite atar un forecast a los datos *tal como se vieron* sin duplicar la serie:
el rastro guarda el hash, y un auditor verifica que reconstruye con la misma historia.
Puro y stdlib-only (frontera del dominio).
"""

from __future__ import annotations

import hashlib

from acopia.domain.entities.observacion import Observacion


def huella_historia(historia: tuple[Observacion, ...]) -> str:
    """SHA-256 de la serie observada (generación PV + CMg), en orden."""
    digest = hashlib.sha256()
    for observacion in historia:
        digest.update(
            f"{observacion.generacion.w},{observacion.cmg.mills_por_mwh};".encode()
        )
    return digest.hexdigest()
