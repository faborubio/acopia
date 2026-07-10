"""Optimizador DRL (PPO) detrás de `PuertoOptimizador` — el modo experimental de ADR-005.

Entrena una política PPO **por llamada** sobre el/los escenarios recibidos (mismo
patrón entrena-por-llamada que el LSTM, deuda AUD-009) y la despliega en un rollout
determinista para producir un ``PlanDespacho``. La salida pasa por el mismo contrato
que el LP: acciones enteras validadas contra el ``ModeloBateria`` (factibilidad
garantizada) e ingreso esperado calculado con la ``FuncionObjetivo`` del dominio,
ponderado por ``probabilidad_bp`` — cifras comparables una a una con el baseline.

Postura de ADR-005: para una planta con buen forecast, el LP es casi óptimo; este
modo existe para **medir** esa afirmación, no para reemplazar al núcleo auditable.
Determinismo: misma (política, escenarios, semilla) → mismo plan (semillas fijadas
en numpy/torch/PPO, entrenamiento y rollout en CPU).

Límites explícitos:
- No co-optimiza SSCC (``politica.reserva``): usa el baseline determinista para eso.
- El costo del entrenamiento por llamada es real (segundos a minutos según
  ``total_timesteps``).
"""

from __future__ import annotations

from stable_baselines3 import PPO
from stable_baselines3.common.utils import set_random_seed

from acopia.domain.entities.accion_despacho import AccionDespacho, TipoAccion
from acopia.domain.entities.escenario import Escenario
from acopia.domain.entities.estado_bateria import EstadoBateria
from acopia.domain.entities.plan_despacho import PlanDespacho
from acopia.domain.entities.planta import Planta
from acopia.domain.entities.politica_despacho import PoliticaDespacho
from acopia.domain.services.funcion_objetivo import FuncionObjetivo
from acopia.infrastructure.drl.entorno_despacho import EntornoDespacho, vertido_recurso


class OptimizadorDRL:
    """Implementa `PuertoOptimizador` con PPO (stable-baselines3) sobre EntornoDespacho."""

    def __init__(
        self,
        total_timesteps: int = 16_384,
        n_steps: int = 256,
        batch_size: int = 64,
        tasa_aprendizaje: float = 3e-4,
    ) -> None:
        self._total_timesteps = total_timesteps
        self._n_steps = n_steps
        self._batch_size = batch_size
        self._tasa_aprendizaje = tasa_aprendizaje
        self._objetivo = FuncionObjetivo()

    def optimizar(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenario: Escenario,
        politica: PoliticaDespacho,
    ) -> PlanDespacho:
        return self.optimizar_escenarios(planta, estado_inicial, (escenario,), politica)

    def optimizar_escenarios(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenarios: tuple[Escenario, ...],
        politica: PoliticaDespacho,
    ) -> PlanDespacho:
        if not escenarios:
            raise ValueError("Se requiere al menos un escenario")
        horizonte = politica.horizonte_intervalos
        for indice, escenario in enumerate(escenarios):
            if len(escenario) != horizonte:
                raise ValueError(
                    f"El escenario {indice} tiene {len(escenario)} puntos; "
                    f"la política espera {horizonte}"
                )
        e0 = estado_inicial.energia_almacenada.wh
        if not planta.bateria.energia_min.wh <= e0 <= planta.bateria.energia_max.wh:
            raise ValueError(
                f"El estado inicial ({e0} Wh) está fuera de la banda operativa "
                f"[{planta.bateria.energia_min.wh}, {planta.bateria.energia_max.wh}] Wh"
            )
        if politica.reserva is not None:
            raise ValueError(
                "El modo DRL no co-optimiza SSCC (ADR-005/ADR-010): "
                "usa el baseline determinista para políticas con reserva"
            )

        acciones = self._entrenar_y_desplegar(planta, estado_inicial, escenarios, politica)
        vertidos = self._vertidos_por_escenario(planta, escenarios, politica, acciones)
        ingreso = self._ingreso_esperado(planta, escenarios, politica, acciones, vertidos)
        return PlanDespacho(
            politica_id=politica.id,
            politica_version=politica.version,
            semilla=politica.semilla,
            acciones=acciones,
            energia_vertida_wh=vertidos[0],
            ingreso_esperado_mills=ingreso,
        )

    # ------------------------------------------------------------------ #
    # PPO: entrenamiento por llamada + rollout determinista
    # ------------------------------------------------------------------ #

    def _entrenar_y_desplegar(
        self,
        planta: Planta,
        estado_inicial: EstadoBateria,
        escenarios: tuple[Escenario, ...],
        politica: PoliticaDespacho,
    ) -> tuple[AccionDespacho, ...]:
        set_random_seed(politica.semilla)
        entorno = EntornoDespacho(planta, estado_inicial, escenarios, politica)
        modelo = PPO(
            "MlpPolicy",
            entorno,
            learning_rate=self._tasa_aprendizaje,
            n_steps=self._n_steps,
            batch_size=self._batch_size,
            gamma=1.0,  # horizonte finito episódico: el ingreso de la tarde vale entero
            seed=politica.semilla,
            device="cpu",
            verbose=0,
        )
        modelo.learn(total_timesteps=self._total_timesteps, progress_bar=False)

        # Rollout determinista sobre el escenario 0 (la referencia del plan, como el LP).
        acciones: list[AccionDespacho] = []
        obs, _ = entorno.reset(seed=politica.semilla, options={"escenario": 0})
        for _ in range(politica.horizonte_intervalos):
            accion_cruda, _ = modelo.predict(obs, deterministic=True)
            obs, _, _, _, info = entorno.step(accion_cruda)
            acciones.append(info["accion"])
        return tuple(acciones)

    # ------------------------------------------------------------------ #
    # Valorización comparable con el baseline (FuncionObjetivo del dominio)
    # ------------------------------------------------------------------ #

    def _vertidos_por_escenario(
        self,
        planta: Planta,
        escenarios: tuple[Escenario, ...],
        politica: PoliticaDespacho,
        acciones: tuple[AccionDespacho, ...],
    ) -> tuple[tuple[int, ...], ...]:
        """Recurso de vertido por escenario dadas las acciones (misma regla que el entorno)."""
        resolucion = politica.resolucion
        iny_max_wh = planta.potencia_max_inyeccion.energia_en(resolucion).wh
        retiro_max_wh = planta.potencia_max_retiro.energia_en(resolucion).wh
        vertidos: list[tuple[int, ...]] = []
        for escenario in escenarios:
            fila: list[int] = []
            for accion, punto in zip(acciones, escenario.puntos, strict=True):
                carga_wh = descarga_wh = 0
                if accion.tipo is TipoAccion.CARGAR:
                    carga_wh = accion.potencia.energia_en(resolucion).wh
                elif accion.tipo is TipoAccion.DESCARGAR:
                    descarga_wh = accion.potencia.energia_en(resolucion).wh
                fila.append(
                    vertido_recurso(
                        punto.generacion.energia_en(resolucion).wh,
                        carga_wh,
                        descarga_wh,
                        iny_max_wh,
                        retiro_max_wh,
                        punto.cmg.mills_por_mwh,
                    )
                )
            vertidos.append(tuple(fila))
        return tuple(vertidos)

    def _ingreso_esperado(
        self,
        planta: Planta,
        escenarios: tuple[Escenario, ...],
        politica: PoliticaDespacho,
        acciones: tuple[AccionDespacho, ...],
        vertidos_por_escenario: tuple[tuple[int, ...], ...],
    ) -> int:
        """Ingreso esperado ponderado por probabilidad_bp menos ciclado (idéntico al LP)."""
        suma_ponderada = 0
        suma_pesos = 0
        for escenario, vertidos in zip(escenarios, vertidos_por_escenario, strict=True):
            plan_escenario = PlanDespacho(
                politica_id=politica.id,
                politica_version=politica.version,
                semilla=politica.semilla,
                acciones=acciones,
                energia_vertida_wh=vertidos,
                ingreso_esperado_mills=0,
            )
            bruto = self._objetivo.ingreso_bruto(plan_escenario, escenario, politica.resolucion)
            suma_ponderada += escenario.probabilidad_bp * bruto
            suma_pesos += escenario.probabilidad_bp
        plan_base = PlanDespacho(
            politica_id=politica.id,
            politica_version=politica.version,
            semilla=politica.semilla,
            acciones=acciones,
            energia_vertida_wh=vertidos_por_escenario[0],
            ingreso_esperado_mills=0,
        )
        return suma_ponderada // suma_pesos - self._objetivo.costo_ciclado(
            plan_base,
            politica,
            planta.bateria.eficiencia_carga,
            planta.bateria.eficiencia_descarga,
        )
