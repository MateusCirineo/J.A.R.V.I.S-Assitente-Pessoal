"""Leitura explícita por trechos, usando a mesma síntese, player e trava da conversa.

Não abre arquivos, observa pastas ou envia texto a modelos. Recebe só o texto
selecionado pelo chamador. O índice só avança quando o player confirma conclusão.
"""
from __future__ import annotations

import copy
import threading
import time
import uuid
from typing import Callable


def dividir(texto: str, limite: int = 450) -> list[str]:
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("não há texto selecionado para ler")
    if len(texto) > 100_000:
        raise ValueError("selecione até cem mil caracteres; a leitura não corta o restante silenciosamente")
    if type(limite) is not int or not 80 <= limite <= 1500:
        raise ValueError("tamanho do trecho deve estar entre 80 e 1500 caracteres")
    texto = texto.strip()
    trechos = []
    while texto:
        fim = min(len(texto), limite)
        if fim < len(texto):
            pontuacao = max(texto.rfind(marca, limite // 2, fim) for marca in (". ", "! ", "? ", "\n"))
            espaco = texto.rfind(" ", 0, fim)
            if pontuacao >= 0:
                fim = pontuacao + 1
            elif espaco > 0:
                fim = espaco
        trechos.append(texto[:fim].strip())
        texto = texto[fim:].lstrip()
    return trechos


class Leitura:
    def __init__(self, sintetizar: Callable, tocar: Callable, parar_audio: Callable,
                 lock_audio, publicar: Callable, *, validar_fonte: Callable | None = None,
                 tamanho_trecho: int = 450):
        if any(not callable(c) for c in (sintetizar, tocar, parar_audio, publicar)) or lock_audio is None:
            raise ValueError("leitura exige callbacks e a trava compartilhada da conversa")
        self._sintetizar, self._tocar, self._parar_audio = sintetizar, tocar, parar_audio
        self._audio_lock, self._publicar = lock_audio, publicar
        self._validar_fonte, self._tamanho = validar_fonte, tamanho_trecho
        self._cond = threading.Condition(threading.RLock())
        self._geracao = 0
        self._cancelado = threading.Event()
        self._tocando = False
        self._trechos = []
        self._thread = None
        self._dados = {"estado": "inativo", "titulo": "", "trecho_atual": "", "indice": 0,
                       "total": 0, "erro": None, "fonte": None, "id": None, "em": time.time()}

    def estado(self) -> dict:
        with self._cond:
            return copy.deepcopy(self._dados)

    def _notificar(self) -> bool:
        try:
            self._publicar(self.estado())
            return True
        except Exception as exc:
            with self._cond:
                self._dados.update(estado="erro", erro=f"Não consegui atualizar o painel ({type(exc).__name__}).", em=time.time())
                self._cancelado.set()
            return False

    def iniciar(self, texto: str, titulo: str = "Documento", fonte=None) -> dict:
        trechos = dividir(texto, self._tamanho)
        if not isinstance(titulo, str) or not titulo.strip() or len(titulo) > 300:
            raise ValueError("título inválido")
        self.parar(notificar=False)
        with self._cond:
            self._geracao += 1
            geracao = self._geracao
            self._cancelado = threading.Event()
            self._trechos = trechos
            self._dados = {"estado": "aguardando_audio", "titulo": titulo.strip(),
                           "trecho_atual": trechos[0], "indice": 0, "total": len(trechos),
                           "erro": None, "fonte": copy.deepcopy(fonte),
                           "id": "l" + uuid.uuid4().hex[:16], "em": time.time()}
            self._thread = threading.Thread(target=self._rodar, args=(geracao,), daemon=True, name="jarvis-leitura")
            worker = self._thread
        if self._notificar():
            worker.start()
        return self.estado()

    def pausar(self) -> dict:
        with self._cond:
            if self._dados["estado"] not in {"aguardando_audio", "lendo"}:
                return self.estado()
            self._cancelado.set()
            parar = self._tocando
            self._dados.update(estado="pausado", em=time.time())
            self._cond.notify_all()
        if parar:
            self._parar_audio()
        self._notificar()
        return self.estado()

    def retomar(self) -> dict:
        with self._cond:
            if self._dados["estado"] not in {"pausado", "erro"} or not self._trechos:
                raise ValueError("não há leitura pausada para retomar")
            self._cancelado = threading.Event()
            self._dados.update(estado="aguardando_audio", erro=None, em=time.time())
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._rodar, args=(self._geracao,), daemon=True, name="jarvis-leitura")
                self._thread.start()
            self._cond.notify_all()
        self._notificar()
        return self.estado()

    def parar(self, *, notificar=True) -> dict:
        with self._cond:
            self._cancelado.set()
            self._geracao += 1
            parar = self._tocando
            self._dados.update(estado="parado", em=time.time())
            self._cond.notify_all()
        if parar:
            self._parar_audio()
        if notificar:
            self._notificar()
        return self.estado()

    def _vigente(self, geracao, cancelado) -> bool:
        return (geracao == self._geracao and cancelado is self._cancelado
                and not cancelado.is_set() and self._dados["estado"] in {"aguardando_audio", "lendo"})

    def _rodar(self, geracao):
        while True:
            with self._cond:
                self._cond.wait_for(lambda: geracao != self._geracao or self._dados["estado"] not in {"pausado", "erro"})
                if geracao != self._geracao or self._dados["estado"] in {"parado", "concluido"}:
                    return
                cancelado = self._cancelado
                indice = self._dados["indice"]
                trecho, fonte = self._trechos[indice], copy.deepcopy(self._dados["fonte"])
            if not self._audio_lock.acquire(timeout=0.1):
                continue
            try:
                with self._cond:
                    if not self._vigente(geracao, cancelado):
                        continue
                if self._validar_fonte is not None and self._validar_fonte(fonte) is not True:
                    raise ValueError("a fonte mudou ou não está disponível; selecione novamente o documento")
                with self._cond:
                    if not self._vigente(geracao, cancelado):
                        continue
                    self._dados.update(estado="lendo", em=time.time())
                if not self._notificar():
                    continue
                audio, taxa = self._sintetizar(trecho)
                with self._cond:
                    if not self._vigente(geracao, cancelado):
                        continue
                    self._tocando = True
                # O evento também é verificado dentro do player: pausa entre a
                # verificação acima e o começo da reprodução não reinicia áudio.
                resultado = self._tocar(audio, taxa, cancelado=cancelado)
                with self._cond:
                    if not self._vigente(geracao, cancelado):
                        continue
                    if resultado == "concluido":
                        self._dados["indice"] = indice + 1
                        concluiu = indice + 1 == len(self._trechos)
                        self._dados.update(estado="concluido" if concluiu else "aguardando_audio",
                                           trecho_atual="" if concluiu else self._trechos[indice + 1], em=time.time())
                    elif resultado == "interrompido":
                        cancelado.set()
                        self._dados.update(estado="pausado", em=time.time())
                    else:
                        raise ValueError("o reprodutor não confirmou a conclusão do trecho")
            except Exception as exc:
                with self._cond:
                    if self._vigente(geracao, cancelado):
                        cancelado.set()
                        detalhe = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                        self._dados.update(estado="erro", erro=f"Leitura interrompida: {detalhe}", em=time.time())
            finally:
                with self._cond:
                    self._tocando = False
                self._audio_lock.release()
            with self._cond:
                if geracao != self._geracao:
                    return
            self._notificar()
