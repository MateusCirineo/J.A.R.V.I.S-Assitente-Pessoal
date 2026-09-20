"""Atalhos globais de teclado (funcionam com qualquer janela em foco).

- Ctrl+Alt+J: falar com o Jarvis (abre a janela de conversa: a proxima frase
  vale sem dizer "Jarvis"; liga o microfone se estiver desligado)
- Ctrl+Alt+P: parar a fala agora (e descartar a resposta que ainda vem)

Usa RegisterHotKey do Windows num fio proprio com fila de mensagens. Se outro
programa ja usa a combinacao, o registro falha e isso aparece no log; nada e
capturado alem dessas duas combinacoes (nao ha registro de teclas).
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
ATALHOS = {1: ("Ctrl+Alt+J", ord("J"), "falar"), 2: ("Ctrl+Alt+P", ord("P"), "parar")}


class Atalhos(threading.Thread):
    def __init__(self, acoes: dict[str, Callable[[], None]], registrar: Callable[[str, str], None]) -> None:
        super().__init__(name="atalhos", daemon=True)
        self._acoes = acoes
        self._registrar = registrar
        self._fio_id: int | None = None
        self.ativos: list[str] = []

    def run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._fio_id = kernel32.GetCurrentThreadId()
        for ident, (rotulo, tecla, _acao) in ATALHOS.items():
            if user32.RegisterHotKey(None, ident, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, tecla):
                self.ativos.append(rotulo)
            else:
                self._registrar(f"atalho {rotulo} indisponível (outro programa já usa)", "aviso")
        if self.ativos:
            self._registrar("atalhos: " + ", ".join(self.ativos), "info")
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in ATALHOS:
                acao = self._acoes.get(ATALHOS[msg.wParam][2])
                if acao:
                    try:
                        acao()
                    except Exception as e:  # noqa: BLE001
                        self._registrar(f"atalho falhou: {e}", "erro")
        for ident in ATALHOS:
            user32.UnregisterHotKey(None, ident)

    def encerrar(self) -> None:
        if self._fio_id:
            ctypes.windll.user32.PostThreadMessageW(self._fio_id, WM_QUIT, 0, 0)
