"""Value objects del dominio: cantidades físicas en unidades enteras.

El determinismo exige aritmética entera (sin float) en energía, potencia,
eficiencia y SoC. Las conversiones usan división entera (floor), explícita y
reproducible.
"""

from acopia.domain.value_objects.eficiencia import Eficiencia
from acopia.domain.value_objects.energia import Energia
from acopia.domain.value_objects.intervalo import Intervalo
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio
from acopia.domain.value_objects.soc import Soc

__all__ = ["Eficiencia", "Energia", "Intervalo", "Potencia", "Precio", "Soc"]
