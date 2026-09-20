"""Abre as janelas como aplicativos do Edge (--app) sem duplicar.

Antes de abrir, procura uma janela do msedge.exe com o mesmo titulo; se
achar, so traz para frente. Reabrir nunca acumula janelas.
"""

from __future__ import annotations

import ctypes
import shutil
import subprocess
import threading
import time
from ctypes import wintypes
from pathlib import Path

from . import SERVIDOR_OPENJARVIS

TITULOS = {
    "jarvis": "J.A.R.V.I.S.",
    "painel": "JARVIS · Central de Comando",
    "chat": "OpenJarvis",
    "holograma": "J.A.R.V.I.S. · Mesa holográfica",
}

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32


def navegador() -> str | None:
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if Path(p).exists():
            return p
    return shutil.which("msedge") or shutil.which("chrome")


def _processo(hwnd: int) -> str:
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = _kernel32.OpenProcess(0x1000, False, pid.value)   # QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        n = wintypes.DWORD(512)
        if _kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return Path(buf.value).name.lower()
        return ""
    finally:
        _kernel32.CloseHandle(h)


def achar(titulo: str) -> int | None:
    achado: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cada(hwnd, _):
        if not _user32.IsWindowVisible(hwnd):
            return True
        n = _user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            _user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value == titulo and _processo(hwnd) in ("msedge.exe", "chrome.exe"):
                achado.append(hwnd)
                return False
        return True

    _user32.EnumWindows(cada, 0)
    return achado[0] if achado else None


def _area_trabalho() -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    _user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)   # SPI_GETWORKAREA
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def geometria(nome: str) -> tuple[int, int, int, int]:
    """Posicao no monitor principal. Sempre dentro da area visivel."""
    x0, y0, w, h = _area_trabalho()
    # o nucleo precisa de largura; o painel se reorganiza bem em uma coluna
    corte = int(w * 0.6)
    if nome == "jarvis":
        return x0, y0, corte, h
    if nome == "painel":
        return x0 + corte, y0, w - corte, h
    if nome == "holograma":                                    # no projetor (2o monitor), se houver
        from .holograma import projetor
        p = projetor()
        if p:
            return p["x"], p["y"], p["w"], p["h"]
        return x0, y0, w, h
    lw, lh = int(w * 0.72), int(h * 0.86)
    return x0 + (w - lw) // 2, y0 + (h - lh) // 2, lw, lh


def _posicionar(titulo: str, geo: tuple[int, int, int, int], prazo_s: float = 15.0) -> None:
    """Com o Edge ja aberto, --window-position/--window-size sao ignorados (as
    janelas saiam empilhadas). Espera a janela ganhar o titulo e a move."""
    fim = time.monotonic() + prazo_s
    while time.monotonic() < fim:
        hwnd = achar(titulo)
        if hwnd:
            x, y, w, h = geo
            _user32.ShowWindow(hwnd, 9)                          # SW_RESTORE
            _user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0004)    # SWP_NOZORDER
            return
        time.sleep(0.4)


def abrir(nome: str, porta: int) -> str:
    titulo = TITULOS[nome]
    hwnd = achar(titulo)
    if hwnd:
        _user32.ShowWindow(hwnd, 9)              # SW_RESTORE
        _user32.SetForegroundWindow(hwnd)
        return "focada"
    nav = navegador()
    if not nav:
        return "sem navegador"
    # ?tema=hud: o chat grava o tema HUD uma vez nas proprias configuracoes
    url = (f"{SERVIDOR_OPENJARVIS}/?tema=hud" if nome == "chat"
           else f"http://127.0.0.1:{porta}/{nome}")
    geo = geometria(nome)
    x, y, w, h = geo
    subprocess.Popen([nav, f"--app={url}", f"--window-position={x},{y}",
                      f"--window-size={w},{h}", "--new-window"])
    threading.Thread(target=_posicionar, args=(titulo, geo), daemon=True).start()
    return "aberta"


def tela_cheia(nome: str) -> bool:
    """Alterna a tela cheia da janela (F11 do navegador). A pagina so pode pedir
    tela cheia com um clique; por voz, quem aperta F11 e o runtime."""
    hwnd = achar(TITULOS[nome])
    if not hwnd:
        return False
    _user32.ShowWindow(hwnd, 9)                                   # SW_RESTORE
    _user32.SetForegroundWindow(hwnd)
    import time
    time.sleep(0.25)
    vk_f11 = 0x7A
    _user32.keybd_event(vk_f11, 0, 0, 0)
    _user32.keybd_event(vk_f11, 0, 0x0002, 0)                     # KEYEVENTF_KEYUP
    return True
