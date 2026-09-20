"""Falar enquanto o modelo escreve (como o Copilot do video de referencia).

Antes a voz esperava a resposta inteira (20-60 s nesta CPU) para comecar a
falar. Agora cada frase pronta vai para a sintese e toca em seguida, enquanto o
modelo continua escrevendo a proxima: a primeira frase sai em poucos segundos.

Dois fios: um sintetiza as frases na ordem, o outro toca os audios na ordem.
"Pare" (evento cancelado) descarta o que falta.
"""

from __future__ import annotations

import json
import queue
import re
import threading
from typing import Any, Callable, Iterable, Iterator

_FIM = re.compile(r"[.!?…]+[\"')\]]*(?=\s)")
_PENSANDO = re.compile(r"<think>.*?</think>", re.S)


def cortar_frases(buf: str, minimo: int = 18) -> tuple[list[str], str]:
    """Frases completas do texto acumulado -> (frases, resto que ainda nao terminou).
    "R$ 5.50" nao corta (o ponto precisa de espaco depois); trechos curtos ("Sr.")
    esperam juntar mais texto."""
    frases, inicio = [], 0
    for m in _FIM.finditer(buf):
        trecho = buf[inicio:m.end()].strip()
        if len(trecho) >= minimo:
            frases.append(trecho)
            inicio = m.end()
    return frases, buf[inicio:]


def ler_sse_openai(linhas: Iterable[bytes]) -> Iterator[str]:
    """Stream do servidor do OpenJarvis (formato OpenAI: data: {...choices[0].delta.content})."""
    for bruta in linhas:
        linha = bruta.decode("utf-8", "replace").strip()
        if not linha.startswith("data:"):
            continue
        dado = linha[5:].strip()
        if dado == "[DONE]":
            return
        try:
            j = json.loads(dado)
        except ValueError:
            continue
        pedaco = ((j.get("choices") or [{}])[0].get("delta") or {}).get("content")
        if pedaco:
            yield pedaco


def ler_ndjson_ollama(linhas: Iterable[bytes]) -> Iterator[str]:
    """Stream do Ollama (/api/chat): uma linha JSON por pedaco."""
    for bruta in linhas:
        try:
            j = json.loads(bruta)
        except ValueError:
            continue
        pedaco = (j.get("message") or {}).get("content")
        if pedaco:
            yield pedaco
        if j.get("done"):
            return


class FalaEmFluxo:
    def __init__(self, sintetizar: Callable[[str], tuple[Any, int]], tocar: Callable[[Any, int], str],
                 cancelado: threading.Event, limpar: Callable[[str], str] = lambda s: s.strip()) -> None:
        self._sintetizar, self._tocar, self._cancelado, self._limpar = sintetizar, tocar, cancelado, limpar
        self._frases: queue.Queue[str | None] = queue.Queue()
        self._audios: queue.Queue[tuple[Any, int] | None] = queue.Queue()
        self._buf = ""
        self.frases: list[str] = []
        self.falou = False
        self._fios = [threading.Thread(target=self._laco_sintese, name="fluxo-sintese", daemon=True),
                      threading.Thread(target=self._laco_toque, name="fluxo-toque", daemon=True)]
        for f in self._fios:
            f.start()

    def receber(self, pedaco: str) -> None:
        self._buf += pedaco
        if "<think>" in self._buf:                     # raciocinio do modelo: nunca e falado
            if "</think>" not in self._buf:
                return
            self._buf = _PENSANDO.sub("", self._buf)
        frases, self._buf = cortar_frases(self._buf)
        for f in frases:
            self._enviar(f)

    def _enviar(self, frase: str) -> None:
        frase = self._limpar(frase)
        if frase:
            self.frases.append(frase)
            self._frases.put(frase)

    def terminar(self, esperar: bool = True) -> str:
        """Fala o que sobrou e (por padrao) espera terminar. Devolve o texto inteiro."""
        resto = _PENSANDO.sub("", self._buf).split("<think>")[0]
        self._buf = ""
        if resto.strip():
            self._enviar(resto)
        self._frases.put(None)
        if esperar:
            self._fios[1].join()
        return " ".join(self.frases)

    def _laco_sintese(self) -> None:
        while True:
            frase = self._frases.get()
            if frase is None or self._cancelado.is_set():
                self._audios.put(None)
                return
            try:
                self._audios.put(self._sintetizar(frase))
            except Exception:  # noqa: BLE001 - uma frase que falha nao cala o resto
                continue

    def _laco_toque(self) -> None:
        while True:
            item = self._audios.get()
            if item is None:
                return
            if self._cancelado.is_set():
                continue                                   # "pare": descarta o que falta
            if self._tocar(*item) == "interrompido":
                self._cancelado.set()
            self.falou = True
