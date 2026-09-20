"""Olhar automatico: mostre um objeto na regiao definida e o Jarvis diz o que e.

Como no video de referencia ("limitado a regiao que eu defini que ele poderia
enxergar"): so a REGIAO escolhida conta; o resto do quadro e ignorado.

Por quadro so ha contas baratas (sem modelo): a regiao reduzida, em cores, e
comparada com o "fundo" aprendido. Quando algo novo ocupa parte da regiao
(descontados os rostos) e fica parado ~1 s, UMA foto recortada da regiao vai
ao modelo de visao local. Depois ele espera o objeto sair antes de olhar de
novo, com intervalo minimo entre analises. Nada e gravado.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import numpy as np

REGIOES = {
    "centro": (0.22, 0.15, 0.56, 0.70),
    "mesa": (0.12, 0.52, 0.76, 0.46),              # metade de baixo: camera apontada para a mesa
    "inteira": (0.0, 0.0, 1.0, 1.0),
}
TAM = (96, 72)                                     # regiao reduzida para as contas por quadro


class ObservadorObjeto:
    MUDOU = 26                  # diferenca num canal de cor (0-255) que conta como "mudou"
    OCUPA = 0.12                # fracao da regiao mudada para achar que ha um objeto
    VAZIO = 0.05                # abaixo disso a regiao voltou ao fundo
    PARADO = 3.5                # movimento medio maximo entre quadros para "esta parado"
    ESTAVEL_S = 1.0
    INTERVALO_S = 25.0          # minimo entre duas analises
    APRENDER_Q = 20             # quadros parados para aprender o fundo

    def __init__(self, ao_objeto: Callable[[np.ndarray], None], regiao: str = "centro") -> None:
        self._ao_objeto = ao_objeto
        self.regiao = regiao
        self._fundo: np.ndarray | None = None
        self._anterior: np.ndarray | None = None
        self._parados = 0
        self.fase = "aprendendo"
        self._desde = 0.0
        self._ultima = -1e9
        self._vazio_desde: float | None = None

    def definir_regiao(self, regiao: str) -> None:
        if regiao in REGIOES and regiao != self.regiao:
            self.regiao = regiao
            self.reiniciar()

    def reiniciar(self) -> None:
        self._fundo = self._anterior = None
        self._parados = 0
        self.fase = "aprendendo"

    def caixa(self, larg: int, alt: int) -> tuple[int, int, int, int]:
        x, y, w, h = REGIOES[self.regiao]
        return round(x * larg), round(y * alt), round(w * larg), round(h * alt)

    def _mascara_rostos(self, rostos: list[dict[str, Any]]) -> np.ndarray:
        """True onde NAO ha rosto (rostos em fracao do quadro, com folga)."""
        m = np.ones(TAM[::-1], bool)
        rx, ry, rw, rh = REGIOES[self.regiao]
        for f in rostos:
            fx, fy = f["x"] - f["w"] * 0.35, f["y"] - f["h"] * 0.35
            fw, fh = f["w"] * 1.7, f["h"] * 2.2                  # rosto + cabelo/pescoco
            x0 = int(max(0, (fx - rx) / rw) * TAM[0])
            y0 = int(max(0, (fy - ry) / rh) * TAM[1])
            x1 = int(min(1, (fx + fw - rx) / rw) * TAM[0])
            y1 = int(min(1, (fy + fh - ry) / rh) * TAM[1])
            if x1 > x0 and y1 > y0:
                m[y0:y1, x0:x1] = False
        return m

    def processar(self, img: np.ndarray, rostos: list[dict[str, Any]], agora: float | None = None) -> str:
        """Um quadro BGR (qualquer tamanho). Devolve a fase atual."""
        import cv2
        agora = time.monotonic() if agora is None else agora
        h, w = img.shape[:2]
        x, y, cw, ch = self.caixa(w, h)
        # em cores: um objeto azul sobre fundo cinza tem quase o mesmo brilho, mas outra cor
        cinza = cv2.GaussianBlur(cv2.resize(img[y:y + ch, x:x + cw], TAM, interpolation=cv2.INTER_AREA),
                                 (5, 5), 0).astype(np.int16)
        mov = float(np.abs(cinza - self._anterior).mean()) if self._anterior is not None else 99.0
        self._anterior = cinza
        livre = self._mascara_rostos(rostos)

        if self._fundo is None:                              # aprende o fundo com a regiao parada
            self._parados = self._parados + 1 if mov < self.PARADO else 0
            if self._parados >= self.APRENDER_Q:
                self._fundo = cinza.astype(np.float32)
                self.fase = "vazio"
            return self.fase

        mudou = (np.abs(cinza - self._fundo).max(axis=2) > self.MUDOU) & livre
        ocupa = float(mudou.sum()) / max(1, int(livre.sum()))
        if self.fase == "vazio":
            if ocupa > self.OCUPA:
                self.fase, self._desde = "candidato", agora
            elif mov < self.PARADO:                          # luz mudando devagar: fundo acompanha
                self._fundo += (cinza - self._fundo) * 0.03
        elif self.fase == "candidato":
            if ocupa < self.VAZIO:
                self.fase = "vazio"
            elif mov > self.PARADO:
                self._desde = agora                          # ainda mexendo: recomeca a contar
            elif agora - self._desde >= self.ESTAVEL_S and agora - self._ultima >= self.INTERVALO_S:
                self._ultima = agora
                self.fase = "aguardando_sair"
                self._vazio_desde = None
                self._ao_objeto(img[y:y + ch, x:x + cw].copy())
        elif self.fase == "aguardando_sair":
            if ocupa < self.VAZIO:
                self._vazio_desde = self._vazio_desde or agora
                if agora - self._vazio_desde > 1.5:
                    self.fase = "vazio"
            else:
                self._vazio_desde = None
        return self.fase
