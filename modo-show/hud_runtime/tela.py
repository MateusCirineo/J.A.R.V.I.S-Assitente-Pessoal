"""Olhar a janela em que o usuario esta trabalhando (sob pedido).

"Jarvis, olhe minha tela" / "explique esse erro" / "o que tem nessa janela?"
- Escolhe a janela de trabalho: a do primeiro plano, pulando as do proprio
  Jarvis (HUD, Painel, console) e janelas escondidas/minimizadas.
- Captura SO essa janela (PrintWindow), mesmo que o HUD esteja por cima: nada
  de outras janelas nem da area de trabalho inteira.
- Recusa janelas de senha e de banco.
- A imagem vai ao modelo de visao LOCAL (Ollama) e nao e gravada em disco.
"""

from __future__ import annotations

import ctypes
import re
from ctypes import wintypes

import numpy as np

JANELAS_DO_JARVIS = {"j.a.r.v.i.s.", "jarvis · central de comando", "jarvis", "painel", "jarvis runtime",
                     "openjarvis", "program manager"}
_SENSIVEL = re.compile(r"senha|password|bitwarden|1password|keepass|lastpass|dashlane|credenciais|nubank|ita[uú]"
                       r"|bradesco|santander|banco do brasil|caixa econ[oô]mica|banco inter|c6 bank|picpay"
                       r"|mercado pago|internet banking", re.I)


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def titulo(hwnd: int) -> str:
    u = ctypes.windll.user32
    n = u.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def e_do_jarvis(t: str) -> bool:
    return t.split(" - ")[0].strip().lower() in JANELAS_DO_JARVIS


def sensivel(t: str) -> bool:
    return bool(_SENSIVEL.search(t))


def _escondida(hwnd: int) -> bool:
    u = ctypes.windll.user32
    if not u.IsWindowVisible(hwnd) or u.IsIconic(hwnd):
        return True
    oculta = ctypes.c_int(0)                     # janelas "cloaked" (apps da Loja suspensos, outras areas)
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(oculta), ctypes.sizeof(oculta))
    if oculta.value:
        return True
    r = RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.right - r.left) < 200 or (r.bottom - r.top) < 120


def janela_de_trabalho() -> tuple[int, str] | None:
    """(hwnd, titulo) da janela em primeiro plano que nao e do Jarvis."""
    u = ctypes.windll.user32
    u.GetWindow.restype = wintypes.HWND
    hwnd = u.GetForegroundWindow()
    for _ in range(300):
        if not hwnd:
            return None
        t = titulo(hwnd)
        if t and not e_do_jarvis(t) and not _escondida(hwnd):
            return int(hwnd), t
        hwnd = u.GetWindow(hwnd, 2)              # GW_HWNDNEXT: a de baixo na ordem Z
    return None


def _assinaturas(u, g) -> None:
    """Handles sao ponteiros de 64 bits: sem argtypes o ctypes os trunca."""
    H = wintypes.HANDLE
    u.GetWindowDC.argtypes, u.GetWindowDC.restype = [wintypes.HWND], wintypes.HDC
    u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    u.PrintWindow.argtypes, u.PrintWindow.restype = [wintypes.HWND, wintypes.HDC, wintypes.UINT], wintypes.BOOL
    g.CreateCompatibleDC.argtypes, g.CreateCompatibleDC.restype = [wintypes.HDC], wintypes.HDC
    g.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    g.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    g.SelectObject.argtypes, g.SelectObject.restype = [wintypes.HDC, H], H
    g.DeleteObject.argtypes = [H]
    g.DeleteDC.argtypes = [wintypes.HDC]
    g.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                            ctypes.c_void_p, wintypes.UINT]


def capturar(hwnd: int) -> np.ndarray:
    """Imagem BGR so desta janela, em pixels reais (independe da escala do Windows)."""
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    u.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    u.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    antes = u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))      # per-monitor v2
    try:
        r = RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 0 or h <= 0:
            raise RuntimeError("janela sem tamanho")
        _assinaturas(u, g)
        dc_janela = u.GetWindowDC(hwnd)
        dc = g.CreateCompatibleDC(dc_janela)
        bmp = g.CreateCompatibleBitmap(dc_janela, w, h)
        velho = g.SelectObject(dc, bmp)
        try:
            if not u.PrintWindow(hwnd, dc, 2):                          # PW_RENDERFULLCONTENT
                raise RuntimeError("a janela não permitiu captura")
            bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
            buf = (ctypes.c_ubyte * (w * h * 4))()
            if not g.GetDIBits(dc, bmp, 0, h, buf, ctypes.byref(bmi), 0):
                raise RuntimeError("falha ao ler a imagem da janela")
        finally:
            g.SelectObject(dc, velho)
            g.DeleteObject(bmp)
            g.DeleteDC(dc)
            u.ReleaseDC(hwnd, dc_janela)
    finally:
        u.SetThreadDpiAwarenessContext(ctypes.c_void_p(antes))
    img = np.frombuffer(buf, np.uint8).reshape(h, w, 4)[:, :, :3].copy()
    if img.max() == 0:
        raise RuntimeError("a janela veio em branco (alguns programas bloqueiam captura)")
    return img


def jpeg(img: np.ndarray, largura: int = 1280, qualidade: int = 85) -> bytes:
    import cv2
    h, w = img.shape[:2]
    if w > largura:
        img = cv2.resize(img, (largura, round(h * largura / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, qualidade])
    if not ok:
        raise RuntimeError("falha ao comprimir a captura")
    return buf.tobytes()
