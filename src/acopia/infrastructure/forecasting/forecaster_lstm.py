"""Forecaster Seq2Seq-LSTM (PyTorch) detrás del mismo PuertoForecaster.

Arquitectura encoder-decoder: un LSTM codifica la ventana histórica (generación PV
y CMg como dos features estandarizadas) y otro LSTM decodifica el horizonte paso a
paso. El escenario 0 es el pronóstico puntual (forward sin ruido); los demás suman
``N(0, sigma)`` con ``sigma`` estimado de los residuos de entrenamiento (determinista
con la semilla), igual que SARIMAX y el baseline.

Es el tope de ADR-002: debe batir al baseline (y ser competitivo con SARIMAX) en
nuestro set. Entrena por llamada sobre la ``historia`` recibida, como SARIMAX; sin
datos chilenos reales se entrena sobre sintéticos, así que esta rebanada entrega la
**arquitectura + el pipeline determinista**, no la cifra del paper (~34% menos RMSE).

Determinismo: se fijan las semillas de PyTorch y numpy, sin shuffle (full-batch), en
CPU. Misma ``(historia, semilla)`` -> mismos escenarios.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

from acopia.domain.entities.escenario import Escenario, PuntoPronostico
from acopia.domain.entities.observacion import Observacion
from acopia.domain.value_objects.potencia import Potencia
from acopia.domain.value_objects.precio import Precio

_BASE = 10_000
_N_FEATURES = 2  # (generación PV, CMg)
_EPS = 1e-8


class _Seq2Seq(nn.Module):  # type: ignore[misc]
    """Encoder-decoder LSTM que proyecta ``n_features`` series a ``horizonte`` pasos."""

    def __init__(self, n_features: int, hidden: int, capas: int) -> None:
        super().__init__()
        self.encoder = nn.LSTM(n_features, hidden, capas, batch_first=True)
        self.decoder = nn.LSTM(n_features, hidden, capas, batch_first=True)
        self.proyeccion = nn.Linear(hidden, n_features)

    def forward(
        self,
        ventana: torch.Tensor,
        horizonte: int,
        objetivo: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Decodifica ``horizonte`` pasos; con ``objetivo`` aplica teacher forcing."""
        _, estado = self.encoder(ventana)
        entrada = ventana[:, -1:, :]
        salidas = []
        for t in range(horizonte):
            paso, estado = self.decoder(entrada, estado)
            paso = self.proyeccion(paso)
            salidas.append(paso)
            entrada = objetivo[:, t : t + 1, :] if objetivo is not None else paso
        return torch.cat(salidas, dim=1)


class ForecasterSeq2SeqLSTM:
    """Implementa `PuertoForecaster` con un Seq2Seq-LSTM entrenado por llamada."""

    def __init__(
        self,
        ventana: int,
        hidden: int = 32,
        capas: int = 1,
        epocas: int = 200,
        tasa_aprendizaje: float = 0.01,
    ) -> None:
        if ventana < 1:
            raise ValueError(f"La ventana debe ser >= 1: {ventana}")
        self._ventana = ventana
        self._hidden = hidden
        self._capas = capas
        self._epocas = epocas
        self._lr = tasa_aprendizaje

    def pronosticar(
        self,
        historia: tuple[Observacion, ...],
        horizonte: int,
        n_escenarios: int,
        semilla: int,
    ) -> tuple[Escenario, ...]:
        if horizonte < 1:
            raise ValueError("El horizonte debe ser >= 1")
        if n_escenarios < 1:
            raise ValueError("n_escenarios debe ser >= 1")
        if len(historia) < self._ventana + horizonte:
            raise ValueError(
                f"La historia ({len(historia)}) es más corta que la ventana + horizonte "
                f"({self._ventana} + {horizonte})"
            )

        serie = np.array(
            [[float(o.generacion.w), float(o.cmg.mills_por_mwh)] for o in historia],
            dtype=np.float32,
        )
        media = serie.mean(axis=0)
        desviacion = serie.std(axis=0) + _EPS
        normal = (serie - media) / desviacion

        torch.manual_seed(semilla)
        modelo = _Seq2Seq(_N_FEATURES, self._hidden, self._capas)
        entradas, objetivos = self._ventanas(normal, horizonte)
        residuo_se = self._entrenar(modelo, entradas, objetivos, horizonte, desviacion)

        # Pronóstico puntual: última ventana observada -> horizonte (sin teacher forcing).
        ultima = torch.from_numpy(normal[-self._ventana :]).unsqueeze(0)
        modelo.eval()
        with torch.no_grad():
            prediccion = modelo(ultima, horizonte).squeeze(0).numpy()
        punto = prediccion * desviacion + media  # (horizonte, 2) en unidades reales

        rng = np.random.default_rng(semilla)
        probabilidad = max(1, _BASE // n_escenarios)
        escenarios: list[Escenario] = []
        for indice in range(n_escenarios):
            trayectoria = punto if indice == 0 else punto + rng.normal(0.0, residuo_se)
            puntos = tuple(
                PuntoPronostico(
                    Potencia(max(0, round(float(trayectoria[h, 0])))),
                    Precio(round(float(trayectoria[h, 1]))),
                )
                for h in range(horizonte)
            )
            escenarios.append(Escenario(puntos, probabilidad))
        return tuple(escenarios)

    def _ventanas(
        self, normal: np.ndarray, horizonte: int
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Corta (ventana -> horizonte) deslizando sobre la serie estandarizada."""
        entradas, objetivos = [], []
        ultimo_inicio = len(normal) - self._ventana - horizonte
        for inicio in range(ultimo_inicio + 1):
            corte = inicio + self._ventana
            entradas.append(normal[inicio:corte])
            objetivos.append(normal[corte : corte + horizonte])
        return (
            torch.from_numpy(np.stack(entradas)),
            torch.from_numpy(np.stack(objetivos)),
        )

    def _entrenar(
        self,
        modelo: _Seq2Seq,
        entradas: torch.Tensor,
        objetivos: torch.Tensor,
        horizonte: int,
        desviacion: np.ndarray,
    ) -> np.ndarray:
        """Entrena full-batch (Adam, MSE) y devuelve el error estándar de residuos."""
        optimizador = torch.optim.Adam(modelo.parameters(), lr=self._lr)
        perdida = nn.MSELoss()
        modelo.train()
        for _ in range(self._epocas):
            optimizador.zero_grad()
            salida = modelo(entradas, horizonte, objetivo=objetivos)
            error = perdida(salida, objetivos)
            error.backward()
            optimizador.step()

        modelo.eval()
        with torch.no_grad():
            ajuste = modelo(entradas, horizonte).numpy()
        objetivo_np = objetivos.numpy()
        # Residuos en unidades reales, error estándar por feature.
        residuos = (ajuste - objetivo_np) * desviacion
        se = residuos.reshape(-1, _N_FEATURES).std(axis=0)
        return np.asarray(se, dtype=float)
