"""Deteccao de duas palmas, isolada do microfone para poder ser testada.

Uma palma e um impulso: sobe seco a partir do silencio e decai rapido.
Fala e musica tem energia sustentada. O detector exige as tres coisas:

  1. pico acima de max(limiar_fixo, ruido * FATOR)  -- o ruido e medido
  2. o bloco anterior estava baixo                   -- ataque seco
  3. em ate DECAIMENTO_S o nivel cai a < 40% do pico  -- decai rapido

e duas palmas validas separadas por 0.12 s a 1.2 s.
"""

from __future__ import annotations

from collections import deque

import numpy as np

TAXA = 16000
BLOCO = 256                       # 16 ms
BLOCO_S = BLOCO / TAXA


class DetectorPalmas:
    FATOR_RUIDO = 5.0
    DECAIMENTO_S = 0.15
    INTERVALO_MIN = 0.12
    INTERVALO_MAX = 1.2

    def __init__(self, limiar: float = 0.25) -> None:
        self.limiar_fixo = limiar
        self._ruido = deque(maxlen=int(3.0 / BLOCO_S))   # ~3 s de historico
        self._t = 0.0
        self._anterior = 0.0
        self._candidato: tuple[float, float] | None = None   # (instante, pico)
        self._ultima_palma: float | None = None

    @property
    def ruido(self) -> float:
        return float(np.median(self._ruido)) if self._ruido else 0.0

    @property
    def limiar(self) -> float:
        return max(self.limiar_fixo, self.ruido * self.FATOR_RUIDO)

    def processar(self, bloco: np.ndarray) -> bool:
        """Recebe um bloco float32 (-1..1). True quando fecham duas palmas."""
        pico = float(np.abs(bloco).max()) if bloco.size else 0.0
        self._t += BLOCO_S
        disparou = False
        limiar = self.limiar

        # confirma (ou descarta) o candidato pelo decaimento
        if self._candidato is not None:
            t0, pico0 = self._candidato
            if pico < pico0 * 0.4:
                self._candidato = None
                disparou = self._palma(t0)
            elif self._t - t0 > self.DECAIMENTO_S:
                self._candidato = None       # energia sustentada: nao e palma

        if (self._candidato is None and pico >= limiar
                and self._anterior < limiar * 0.5):
            self._candidato = (self._t, pico)

        # o historico de ruido ignora os proprios impulsos
        if self._candidato is None and pico < limiar:
            self._ruido.append(pico)
        self._anterior = pico
        return disparou

    def _palma(self, t: float) -> bool:
        anterior = self._ultima_palma
        if anterior is not None and self.INTERVALO_MIN <= t - anterior <= self.INTERVALO_MAX:
            self._ultima_palma = None
            return True
        self._ultima_palma = t
        return False
