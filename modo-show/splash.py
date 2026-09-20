"""Tela de "Inicializando" no estilo HUD circular do J.A.R.V.I.S. (referencias
enviadas pelo Senhor): aneis concentricos girando, marcas, faixa translucida,
pontos amarelos, arco laranja e fundo de planta tecnica. O desenho e original,
feito aqui em codigo: nenhuma arte, logo ou marca de terceiros e copiada.

A faixa larga e o progresso REAL do boot (lido do runtime em /api/estado) e os
pontos no alto sao as etapas: amarelo = passou, laranja = aviso, vermelho =
falha, branco pulsando = verificando. Fecha sozinha quando a janela do Jarvis
aparece (ou o boot termina), com clique ou Esc, ou depois de 3 min avisando
que esta demorando. Nao inicia nada: so observa.

Desenho com OpenCV (antisserrilhado, brilho por desfoque) e texto pela fonte do
Windows (Bahnschrift, via GDI); cada anel e uma camada pronta que so gira.

    pythonw modo-show\\splash.py            (chamado pelo jarvis-tudo.cmd)
    pythonw modo-show\\splash.py --show     (Modo Show, depois das palmas)
"""

from __future__ import annotations

import ctypes
import json
import math
import os
import sys
import threading
import time
import tkinter as tk
import urllib.request
from ctypes import wintypes
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "_libs"))      # opencv fica em _libs
try:
    import cv2
    import numpy as np
except ImportError:                                                   # sem opencv: tela simples
    cv2 = np = None

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
TRAVA = HOME / "splash.pid"
LIMITE_S = 180
TITULOS_JARVIS = ("J.A.R.V.I.S.", "JARVIS · Central de Comando")
# as 10 etapas do runtime (hud_runtime/estado.py)
ETAPAS_PADRAO = [("servidor", "Servidor"), ("ollama", "Ollama"), ("modelo_chat", "Modelo do chat"),
                 ("modelo_voz", "Modelo da voz"), ("microfone", "Microfone"), ("saida_audio", "Saída de áudio"),
                 ("sintese", "Síntese de voz"), ("transcricao", "Transcrição"), ("eventos", "Eventos"),
                 ("memoria", "Memória")]

CIANO, CIANO_CLARO, AZUL = "#5fd3ff", "#a6ecff", "#4fb4e0"
AMARELO, LARANJA, VERMELHO, BRANCO = "#ffe14d", "#ff8418", "#ff5964", "#eef8ff"
FPS_MS = 33


def bgr(cor: str, k: float = 1.0) -> tuple[float, float, float]:
    r, g, b = (int(cor[i:i + 2], 16) for i in (1, 3, 5))
    return (b * k, g * k, r * k)


# ---- texto pela fonte do Windows (GDI) ----------------------------------------------
class _BMI(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def _gdi():
    g = ctypes.windll.gdi32
    vp = ctypes.c_void_p                       # handles de 64 bits: sem isso o ctypes os corta
    g.CreateCompatibleDC.restype, g.CreateCompatibleDC.argtypes = vp, [vp]
    g.CreateFontW.restype = vp
    g.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
    g.SelectObject.restype, g.SelectObject.argtypes = vp, [vp, vp]
    g.CreateDIBSection.restype = vp
    g.CreateDIBSection.argtypes = [vp, vp, wintypes.UINT, ctypes.POINTER(vp), vp, wintypes.DWORD]
    g.DeleteObject.argtypes = [vp]
    g.DeleteDC.argtypes = [vp]
    g.SetTextCharacterExtra.argtypes = [vp, ctypes.c_int]
    g.SetBkMode.argtypes = [vp, ctypes.c_int]
    g.SetTextColor.argtypes = [vp, wintypes.DWORD]
    g.TextOutW.argtypes = [vp, ctypes.c_int, ctypes.c_int, wintypes.LPCWSTR, ctypes.c_int]
    g.GetTextExtentPoint32W.argtypes = [vp, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.SIZE)]
    return g


def mascara_texto(texto: str, px: int, fonte: str = "Bahnschrift", espaco: int = 0):
    """Cobertura (0..1) do texto desenhado pelo Windows, antisserrilhado."""
    g = _gdi()
    dc = g.CreateCompatibleDC(None)
    f = g.CreateFontW(-px, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 4, 0, fonte)       # 4 = ANTIALIASED_QUALITY
    velha_f = g.SelectObject(dc, f)
    g.SetTextCharacterExtra(dc, espaco)
    tam = wintypes.SIZE()
    g.GetTextExtentPoint32W(dc, texto, len(texto), ctypes.byref(tam))
    w, h = tam.cx + 8, tam.cy + 8
    bmi = _BMI(ctypes.sizeof(_BMI), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    bits = ctypes.c_void_p()
    dib = g.CreateDIBSection(dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    velho_b = g.SelectObject(dc, dib)
    g.SetBkMode(dc, 1)
    g.SetTextColor(dc, 0x00FFFFFF)
    g.TextOutW(dc, 4, 4, texto, len(texto))
    ctypes.windll.gdi32.GdiFlush()
    buf = (ctypes.c_uint8 * (w * h * 4)).from_address(bits.value)
    m = np.frombuffer(buf, np.uint8).reshape(h, w, 4)[..., 1].astype(np.float32) / 255
    g.SelectObject(dc, velho_b)
    g.SelectObject(dc, velha_f)
    g.DeleteObject(dib)
    g.DeleteObject(f)
    g.DeleteDC(dc)
    return m


def texto_brilhante(texto: str, px: int, fonte: str, espaco: int, topo: str, base: str,
                    halo: str, forca: float = 0.8):
    """Texto com degrade vertical e halo (camada BGR para somar na imagem)."""
    m = mascara_texto(texto, px, fonte, espaco)
    pad = max(4, int(px * 0.45))
    m = cv2.copyMakeBorder(m, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    h = m.shape[0]
    t = np.clip((np.arange(h, dtype=np.float32) - pad) / max(1, h - 2 * pad), 0, 1)[:, None, None]
    cor = np.array(bgr(topo), np.float32) * (1 - t) + np.array(bgr(base), np.float32) * t
    brilho = cv2.GaussianBlur(m, (0, 0), max(1.0, px * 0.16))[..., None] * np.array(bgr(halo), np.float32) * forca
    return np.clip(m[..., None] * cor + brilho, 0, 255).astype(np.uint8)


# ---- desenho --------------------------------------------------------------------------
SS = 2          # desenha em 2x e reduz: bordas lisas


def polar(cx: float, cy: float, r: float, ang: float) -> tuple[float, float]:
    a = math.radians(ang)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def setor(cx, cy, r1, r2, a0, a1):
    """Pedaco de anel (poligono) entre os raios r1..r2 e os angulos a0..a1."""
    angs = np.linspace(a0, a1, max(2, int(abs(a1 - a0)) + 2))
    fora = [polar(cx, cy, r2, a) for a in angs]
    dentro = [polar(cx, cy, r1, a) for a in angs[::-1]]
    return np.array(fora + dentro, np.float32)


class Pincel:
    def __init__(self, w: int, h: int, k: int = SS) -> None:
        self.w, self.h, self.k = w, h, k
        self.img = np.zeros((h * k, w * k, 3), np.uint8)

    def _pt(self, x, y):
        return int(round(x * self.k * 16)), int(round(y * self.k * 16))

    def _esp(self, e):
        return max(1, int(round(e * self.k)))

    def arco(self, cx, cy, r, a0, a1, cor, esp=1.0):
        rr = int(round(r * self.k * 16))
        cv2.ellipse(self.img, self._pt(cx, cy), (rr, rr), 0, a0, a1, cor, self._esp(esp), cv2.LINE_AA, 4)

    def linha(self, x1, y1, x2, y2, cor, esp=1.0):
        cv2.line(self.img, self._pt(x1, y1), self._pt(x2, y2), cor, self._esp(esp), cv2.LINE_AA, 4)

    def disco(self, x, y, r, cor):
        cv2.circle(self.img, self._pt(x, y), int(round(r * self.k * 16)), cor, -1, cv2.LINE_AA, 4)

    def poli(self, pts, cor, esp=None):
        p = np.round(np.asarray(pts, np.float32) * self.k * 16).astype(np.int32).reshape(-1, 1, 2)
        if esp is None:
            cv2.fillPoly(self.img, [p], cor, cv2.LINE_AA, 4)
        else:
            cv2.polylines(self.img, [p], True, cor, self._esp(esp), cv2.LINE_AA, 4)

    def pronto(self, sigma: float = 0.0, ganho: float = 0.0):
        img = self.img if self.k == 1 else cv2.resize(self.img, (self.w, self.h), interpolation=cv2.INTER_AREA)
        if sigma:
            img = cv2.addWeighted(img, 1.0, cv2.GaussianBlur(img, (0, 0), sigma), ganho, 0)
        return img


class Arte:
    """Camadas do HUD. Estaticas prontas uma vez; aneis so giram; faixa refeita
    quando o progresso muda."""

    PAINEIS, FAIXA_A0, PASSO = 44, -90.0, 7.5          # faixa: 330 graus, abertura no alto a esquerda

    def __init__(self, lado: int, show: bool) -> None:
        self.W, self.H = lado, int(lado * 1.10)
        self.cx, self.cy, self.R = lado / 2, lado * 0.515, lado * 0.455
        self.show = show
        self.base = self._base()
        R = self.R
        self.giros = [(self._anel_externo(), 3.0), (self._marcas(), -5.0),
                      (self._anel_interno(), 14.0), (self._cometa(), -115.0)]
        self.laranja = self._laranja()
        self.r1, self.r2 = 0.665 * R, 0.815 * R
        self._paineis = [setor(self.cx, self.cy, self.r1, self.r2, a0 + 0.55, a0 + self.PASSO - 0.55)
                         for a0 in (self.FAIXA_A0 + i * self.PASSO for i in range(self.PAINEIS))]
        self._faixa_n: int | None = None
        self.faixa = None
        self._textos: dict[tuple, object] = {}

    def novo(self, k: int = SS) -> Pincel:
        return Pincel(self.W, self.H, k)

    # ---- fundo: planta tecnica, disco escuro, reator ao fundo, faixa do titulo ------
    def _base(self):
        W, H, cx, cy, R = self.W, self.H, self.cx, self.cy, self.R
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        t = np.clip(1 - dist / (R * 1.55), 0, 1)[..., None] ** 1.7
        fundo = np.array(bgr("#02070c"), np.float32) + (np.array(bgr("#0e3c52"), np.float32)
                                                          - np.array(bgr("#02070c"), np.float32)) * t

        p = self.novo()                                                         # planta tecnica (bem fraca)
        passo = R / 7
        for i in range(-12, 13):
            p.linha(cx + i * passo, 0, cx + i * passo, H, bgr("#08202a"), 0.8)
            p.linha(0, cy + i * passo, W, cy + i * passo, bgr("#08202a"), 0.8)
        for a0 in range(0, 360, 6):
            p.arco(cx, cy, 1.07 * R, a0, a0 + 3, bgr(CIANO, 0.16), 1)
        p.arco(cx, cy, 1.16 * R, 0, 360, bgr(CIANO, 0.10), 1)
        for lado in (-1, 1):                                                    # mira horizontal e vertical
            p.linha(cx + lado * 1.03 * R, cy, cx + lado * 1.2 * R, cy, bgr(CIANO, 0.35), 1)
            p.linha(cx, cy + lado * 1.03 * R, cx, cy + lado * 1.2 * R, bgr(CIANO, 0.35), 1)
            for j in range(1, 6):
                x = cx + lado * (1.03 + j * 0.03) * R
                p.linha(x, cy - 4, x, cy + 4, bgr(CIANO, 0.3), 1)
        for (x0, y0, x1, y1) in ((0.035, 0.80, 0.24, 0.95), (0.78, 0.07, 0.965, 0.2)):   # caixas de dados
            a, b, c, d = x0 * W, y0 * H, x1 * W, y1 * H
            p.poli([(a, b), (c, b), (c, d), (a, d)], bgr(CIANO, 0.22), 1)
            for k in range(1, 5):
                yk = b + (d - b) * k / 5
                p.linha(a + 6, yk, a + 6 + (c - a - 12) * (0.35 + 0.5 * ((k * 37) % 10) / 10), yk,
                        bgr(CIANO, 0.18), 1.5)
        deco = p.pronto()

        img = np.clip(fundo + deco.astype(np.float32), 0, 255)
        disco = np.clip((0.585 * R - dist) / 2.0, 0, 1)[..., None]              # centro escuro
        img *= 1 - 0.55 * disco

        p = self.novo()                                                         # reator ao fundo, fraco
        for r, k in ((0.52, 0.30), (0.49, 0.18), (0.26, 0.22), (0.18, 0.28)):
            p.arco(cx, cy, r * R, 0, 360, bgr(CIANO, k), 1.2)
        for i in range(10):
            a = i * 36 + 18
            p.poli(setor(cx, cy, 0.30 * R, 0.46 * R, a - 11, a + 11), bgr(AZUL, 0.22), 1.2)
        for i in range(36):
            p.linha(*polar(cx, cy, 0.195 * R, i * 10), *polar(cx, cy, 0.245 * R, i * 10), bgr(CIANO, 0.14), 1)
        img = np.clip(img + p.pronto(1.5, 0.6).astype(np.float32), 0, 255)

        mw, mh = 0.70 * R, 0.155 * R                                             # faixa do titulo
        ponta = 0.06 * R
        forma = [(cx - mw, cy - mh + ponta), (cx - mw + ponta, cy - mh), (cx + mw - ponta, cy - mh),
                 (cx + mw, cy - mh + ponta), (cx + mw, cy + mh - ponta), (cx + mw - ponta, cy + mh),
                 (cx - mw + ponta, cy + mh), (cx - mw, cy + mh - ponta)]
        m = self.novo()
        m.poli(forma, (255, 255, 255))
        mascara = m.pronto().astype(np.float32)[..., :1] / 255
        img *= 1 - 0.55 * mascara
        p = self.novo()
        p.poli(forma, bgr(CIANO, 0.35), 1)
        for lado in (-1, 1):
            for y in (cy - mh, cy + mh):
                p.linha(cx + lado * (mw - ponta), y, cx + lado * (mw - ponta - 0.22 * R), y, bgr(CIANO_CLARO, 0.8), 2)
        p.linha(cx - 0.42 * R, cy + mh - 0.035 * R, cx + 0.42 * R, cy + mh - 0.035 * R, bgr(CIANO, 0.18), 1)
        img = np.clip(img + p.pronto(2, 0.8).astype(np.float32), 0, 255)

        p = self.novo()                                                          # moldura e cantos
        e = 0.012 * W
        p.poli([(e, e), (W - e, e), (W - e, H - e), (e, H - e)], bgr(CIANO, 0.18), 1)
        c = 0.06 * W
        for (x, y, sx, sy) in ((e, e, 1, 1), (W - e, e, -1, 1), (e, H - e, 1, -1), (W - e, H - e, -1, -1)):
            p.linha(x, y, x + sx * c, y, bgr(CIANO, 0.9), 2)
            p.linha(x, y, x, y + sy * c, bgr(CIANO, 0.9), 2)
        img = np.clip(img + p.pronto(2, 0.7).astype(np.float32), 0, 255).astype(np.uint8)

        self._colar(img, texto_brilhante("J.A.R.V.I.S.  ·  SISTEMA PESSOAL", max(10, int(0.035 * R)),
                                         "Bahnschrift SemiLight", 2, CIANO_CLARO, CIANO, CIANO, 0.4),
                    0.035 * W, 0.042 * H, ancora="w")
        if self.show:
            self._colar(img, texto_brilhante("MODO SHOW", max(10, int(0.035 * R)), "Bahnschrift SemiLight", 3,
                                             CIANO_CLARO, CIANO, CIANO, 0.4), 0.965 * W, 0.042 * H, ancora="e")
        self._colar(img, texto_brilhante("46", max(9, int(0.03 * R)), "Bahnschrift", 1, CIANO, CIANO, CIANO, 0.2),
                    0.93 * W, 0.885 * H)
        self._colar(img, texto_brilhante("Pd", max(12, int(0.07 * R)), "Bahnschrift SemiBold", 1, CIANO_CLARO,
                                         CIANO, CIANO, 0.35), 0.93 * W, 0.925 * H)
        return img

    # ---- aneis que giram --------------------------------------------------------------
    def _anel_externo(self):
        cx, cy, R = self.cx, self.cy, self.R
        p = self.novo()
        for a0, a1 in ((-175, -95), (-85, 80), (95, 170)):
            p.arco(cx, cy, 1.0 * R, a0, a1, bgr(CIANO, 0.6), 1.3)
        for a0, a1 in ((-60, -18), (12, 58), (118, 152), (200, 252)):
            p.arco(cx, cy, 0.965 * R, a0, a1, bgr(CIANO_CLARO, 0.55), 0.02 * R)
        for a in (-90, 0, 90, 180):
            p.disco(*polar(cx, cy, 1.0 * R, a), 0.011 * R, bgr(CIANO_CLARO))
        for base in (30, 210):
            for a in range(base, base + 12, 2):
                p.linha(*polar(cx, cy, 0.985 * R, a), *polar(cx, cy, 1.02 * R, a), bgr(CIANO, 0.7), 1)
        return p.pronto(3, 0.7)

    def _marcas(self):
        cx, cy, R = self.cx, self.cy, self.R
        p = self.novo()
        for i in range(120):
            longa = i % 10 == 0
            r1, r2 = (0.868, 0.935) if longa else (0.886, 0.917)
            p.linha(*polar(cx, cy, r1 * R, i * 3), *polar(cx, cy, r2 * R, i * 3),
                    bgr(CIANO_CLARO if longa else CIANO, 0.95 if longa else 0.45), 2.0 if longa else 1.0)
        for a in range(0, 360, 4):
            p.disco(*polar(cx, cy, 0.85 * R, a), 0.0045 * R, bgr(CIANO, 0.55))
        for a0, a1 in ((100, 114), (280, 302)):
            p.arco(cx, cy, 0.945 * R, a0, a1, bgr(CIANO_CLARO, 0.9), 3)
        return p.pronto(2.5, 0.8)

    def _anel_interno(self):
        cx, cy, R = self.cx, self.cy, self.R
        p = self.novo()
        p.arco(cx, cy, 0.622 * R, 0, 360, bgr(CIANO, 0.4), 1)
        for a0 in (0, 120, 240):
            p.arco(cx, cy, 0.598 * R, a0, a0 + 78, bgr("#7fdcff", 0.8), 0.028 * R)
            p.arco(cx, cy, 0.598 * R, a0 + 84, a0 + 92, bgr("#7fdcff", 0.8), 0.028 * R)
        for a in range(0, 360, 6):
            p.linha(*polar(cx, cy, 0.563 * R, a), *polar(cx, cy, 0.578 * R, a), bgr(CIANO, 0.35), 1)
        return p.pronto(4, 0.8)

    def _cometa(self):
        cx, cy, R = self.cx, self.cy, self.R
        p = self.novo()
        n = 34
        for j in range(n):
            k = (1 - j / n) ** 2
            p.arco(cx, cy, 0.545 * R, -2 * (j + 1), -2 * j, bgr(CIANO_CLARO, k), 0.014 * R)
        p.disco(*polar(cx, cy, 0.545 * R, 0), 0.012 * R, bgr(BRANCO))
        return p.pronto(4, 1.1)

    def _laranja(self):
        cx, cy, R = self.cx, self.cy, self.R
        p = self.novo()
        r = 0.642 * R
        p.arco(cx, cy, r, 146, 212, bgr(LARANJA), 0.018 * R)
        p.arco(cx, cy, r + 0.018 * R, 150, 176, bgr(LARANJA, 0.6), 1)
        for a in (146, 212):
            p.linha(*polar(cx, cy, r, a), *polar(cx, cy, r - 0.035 * R, a), bgr(LARANJA), 0.011 * R)
        p.arco(cx, cy, r - 0.035 * R, 138, 146, bgr(LARANJA), 0.011 * R)
        p.arco(cx, cy, r - 0.035 * R, 212, 218, bgr(LARANJA), 0.011 * R)
        return p.pronto(4, 1.0)

    # ---- faixa de progresso ---------------------------------------------------------------
    def faixa_com(self, cheios: int):
        if cheios == self._faixa_n:
            return self.faixa
        cx, cy, R = self.cx, self.cy, self.R
        p = self.novo(1)
        for i, pol in enumerate(self._paineis):
            a0 = self.FAIXA_A0 + i * self.PASSO + 0.55
            if i < cheios:
                for fa, fb, k in ((0.0, 0.4, 0.32), (0.4, 0.75, 0.44), (0.75, 1.0, 0.58)):
                    ra, rb = self.r1 + (self.r2 - self.r1) * fa, self.r1 + (self.r2 - self.r1) * fb
                    p.poli(setor(cx, cy, ra, rb, a0, a0 + self.PASSO - 1.1), bgr(AZUL, k))
                p.arco(cx, cy, self.r2 - 0.018 * R, a0, a0 + self.PASSO - 1.1, bgr(CIANO_CLARO, 0.75), 2)
            else:
                p.poli(pol, bgr("#0f3a50", 0.55))
        fim = self.FAIXA_A0 + self.PAINEIS * self.PASSO
        for r in (self.r1, self.r2):
            p.arco(cx, cy, r, self.FAIXA_A0, fim, bgr(CIANO, 0.6), 1)
        self.faixa = p.pronto(5, 0.55)
        self._faixa_n = cheios
        return self.faixa

    # ---- texto -------------------------------------------------------------------------------
    def texto(self, chave: tuple, *args):
        if chave not in self._textos:
            if len(self._textos) > 40:
                self._textos.clear()
            self._textos[chave] = texto_brilhante(*args)
        return self._textos[chave]

    @staticmethod
    def _colar(img, patch, x: float, y: float, ancora: str = "c") -> None:
        """Soma (luz) o patch centrado em (x, y); ancora w/e = alinhado pela esquerda/direita."""
        h, w = patch.shape[:2]
        x0 = int(x) if ancora == "w" else int(x - w) if ancora == "e" else int(x - w / 2)
        y0 = int(y - h / 2)
        a0, b0 = max(0, x0), max(0, y0)
        a1, b1 = min(img.shape[1], x0 + w), min(img.shape[0], y0 + h)
        if a1 > a0 and b1 > b0:
            img[b0:b1, a0:a1] = cv2.add(img[b0:b1, a0:a1], patch[b0 - y0:b1 - y0, a0 - x0:a1 - x0])

    # ---- quadro ----------------------------------------------------------------------------------
    def quadro(self, t: float, etapas, progresso: float, subtitulo: str, status: str, contagem: str,
               estado_final: str | None, clarao: float = 0.0):
        cx, cy, R = self.cx, self.cy, self.R
        f = self.base.copy()
        for camada, vel in self.giros:
            M = cv2.getRotationMatrix2D((cx, cy), vel * t, 1.0)
            f = cv2.add(f, cv2.warpAffine(camada, M, (self.W, self.H), flags=cv2.INTER_LINEAR))
        cheios = int(progresso * self.PAINEIS + 1e-6)
        f = cv2.add(f, self.faixa_com(cheios))
        if clarao > 0:                                                   # terminou: a faixa acende
            f = cv2.add(f, cv2.convertScaleAbs(self.faixa, alpha=1.6 * clarao))
        if cheios < self.PAINEIS and not estado_final:                  # painel da vez pulsando
            k = 0.25 + 0.3 * (0.5 + 0.5 * math.sin(t * 5))
            pol = np.round(self._paineis[cheios] * 16).astype(np.int32).reshape(-1, 1, 2)
            cv2.fillPoly(f, [pol], bgr(CIANO, k), cv2.LINE_AA, 4)
        pulso = 0.75 + 0.25 * math.sin(t * 2.2)
        f = cv2.add(f, cv2.convertScaleAbs(self.laranja, alpha=pulso))

        n = len(etapas)                                                  # pontos das etapas, no alto
        for i, (_, _, estado) in enumerate(etapas):
            a = -86 + 60 * i / max(1, n - 1)
            x, y = polar(cx, cy, (self.r1 + self.r2) / 2, a)
            pt = (int(x * 16), int(y * 16))
            cor = {"ok": AMARELO, "aviso": LARANJA, "falha": VERMELHO}.get(estado)
            if estado == "verificando":
                k = 0.5 + 0.5 * math.sin(t * 7)
                cv2.circle(f, pt, int((0.018 + 0.012 * k) * R * 16), bgr(BRANCO, 0.5 + 0.5 * k), 1, cv2.LINE_AA, 4)
                cor = BRANCO
            if cor:
                cv2.circle(f, pt, int(0.02 * R * 16), bgr(cor, 0.35), -1, cv2.LINE_AA, 4)
                cv2.circle(f, pt, int(0.011 * R * 16), bgr(cor), -1, cv2.LINE_AA, 4)
            else:
                cv2.circle(f, pt, int(0.009 * R * 16), bgr("#2c5a70"), -1, cv2.LINE_AA, 4)

        titulo = self.texto(("titulo",), "J.A.R.V.I.S.", int(0.17 * R), "Bahnschrift SemiLight", int(0.026 * R),
                            "#ffffff", "#9fc6d8", CIANO, 0.9)
        self._colar(f, titulo, cx, cy - 0.035 * R)
        cor_sub = {"limitado": LARANJA}.get(estado_final, BRANCO)
        sub = self.texto(("sub", subtitulo, cor_sub), subtitulo, int(0.072 * R), "Bahnschrift", int(0.016 * R),
                         cor_sub, cor_sub, CIANO, 0.5)
        self._colar(f, sub, cx, cy + 0.09 * R)
        if status:
            st = self.texto(("st", status), status, int(0.058 * R), "Bahnschrift SemiLight", 1,
                            CIANO_CLARO, CIANO, CIANO, 0.35)
            self._colar(f, st, cx, self.H * 0.925)
        ct = self.texto(("ct", contagem), contagem, int(0.042 * R), "Bahnschrift", 2, "#7fb4c9", "#5d93aa",
                        CIANO, 0.15)
        self._colar(f, ct, cx, self.H * 0.965)
        return f


# ---- janela ------------------------------------------------------------------------------------
def janela_do_jarvis_aberta() -> bool:
    u = ctypes.windll.user32
    achou = []
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cada(h, _l):
        n = u.GetWindowTextLengthW(h)
        if n and u.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(h, b, n + 1)
            if b.value in TITULOS_JARVIS:
                achou.append(1)
                return False
        return True
    u.EnumWindows(PROC(cada), 0)
    return bool(achou)


def ler_boot() -> dict | None:
    try:
        inst = json.loads((HOME / "hud-runtime.json").read_text(encoding="utf-8"))
        with urllib.request.urlopen(f"http://127.0.0.1:{inst['porta']}/api/estado", timeout=2) as r:
            return json.load(r).get("boot")
    except (OSError, ValueError, KeyError):
        return None


class Splash:
    def __init__(self, show: bool) -> None:
        self.r = tk.Tk()
        self.r.overrideredirect(True)
        self.r.attributes("-topmost", True)
        self.r.configure(bg="#02070c")
        sw, sh = self.r.winfo_screenwidth(), self.r.winfo_screenheight()
        lado = max(440, min(760, int(sh * 0.70)))
        self.arte = Arte(lado, show) if cv2 is not None else None
        largura, altura = (self.arte.W, self.arte.H) if self.arte else (560, 300)
        self.r.geometry(f"{largura}x{altura}+{(sw - largura) // 2}+{(sh - altura) // 2}")
        self.c = tk.Canvas(self.r, width=largura, height=altura, bg="#02070c", highlightthickness=0)
        self.c.pack()
        self.r.bind("<Escape>", lambda e: self.fechar())
        self.c.bind("<Button-1>", lambda e: self.fechar())
        try:
            self.r.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        self.t0 = time.time()
        self.status = "Carregando o núcleo…"
        self.subtitulo = "INICIALIZANDO"
        self.estado_final: str | None = None
        self.final_em: float | None = None
        self.etapas: list[tuple[str, str, str | None]] = [(i, n, None) for i, n in ETAPAS_PADRAO]
        self.progresso = 0.0
        self.fim_em: float | None = None
        self.saindo: float | None = None
        self.vivo = True
        self.foto = None
        self.item = None
        if not self.arte:                                             # sem opencv: so texto
            self.c.create_text(largura / 2, 110, text="J.A.R.V.I.S.", fill=BRANCO, font=("Bahnschrift", 30))
            self.c.create_text(largura / 2, 150, text="INICIALIZANDO", fill=CIANO, font=("Bahnschrift", 12))
            self.item = self.c.create_text(largura / 2, 220, text=self.status, fill=CIANO, font=("Bahnschrift", 10))
        threading.Thread(target=self._observar, daemon=True).start()
        self._animar()

    def _animar(self) -> None:
        if not self.vivo:
            return
        agora = time.time()
        t = agora - self.t0
        prontas = sum(1 for _, _, e in self.etapas if e in ("ok", "aviso", "falha"))
        n = len(self.etapas)
        alvo = 1.0 if self.estado_final else prontas / max(1, n)
        self.progresso += (alvo - self.progresso) * 0.12                # a faixa enche suave
        if self.arte:
            contagem = f"{prontas} DE {n} VERIFICAÇÕES  ·  {round(100 * prontas / max(1, n))}%"
            if self.estado_final and self.final_em is None:
                self.final_em = agora
            clarao = max(0.0, 1 - (agora - self.final_em) / 0.9) if self.final_em else 0.0
            f = self.arte.quadro(t, self.etapas, self.progresso, self.subtitulo, self.status, contagem,
                                 self.estado_final, clarao)
            h, w = f.shape[:2]
            dados = f"P6 {w} {h} 255 ".encode() + f[..., ::-1].tobytes()
            if self.foto is None:
                self.foto = tk.PhotoImage(data=dados, format="PPM")
                self.item = self.c.create_image(0, 0, image=self.foto, anchor="nw")
            else:
                self.foto.configure(data=dados, format="PPM")
        else:
            self.c.itemconfigure(self.item, text=self.status)
        alfa = min(1.0, t / 0.35)                                       # entra e sai suave
        if self.fim_em and agora >= self.fim_em:
            self.saindo = self.saindo or agora
            alfa = 1 - (agora - self.saindo) / 0.45
            if alfa <= 0:
                self.fechar()
                return
        try:
            self.r.attributes("-alpha", max(0.0, alfa))
        except tk.TclError:
            pass
        gasto = int((time.time() - agora) * 1000)
        self.r.after(max(5, FPS_MS - gasto), self._animar)

    def _observar(self) -> None:
        ja_aberto = janela_do_jarvis_aberta()
        rotulos = dict(ETAPAS_PADRAO)
        while self.vivo:
            boot = ler_boot()
            if boot:
                etapas = boot.get("etapas") or []
                if etapas:
                    self.etapas = [(e.get("id", ""), rotulos.get(e.get("id"), e.get("rotulo", "")),
                                    e.get("estado") if e.get("estado") != "pendente" else None) for e in etapas]
                agora = next((e for e in etapas if e.get("estado") == "verificando"), None)
                if boot.get("concluido"):
                    online = boot.get("resultado") == "online"
                    self.estado_final = "online" if online else "limitado"
                    self.subtitulo = "SISTEMA ONLINE" if online else "ONLINE COM LIMITAÇÕES"
                    self.status = "Pronto para servi-lo, Senhor." if online else "Algumas partes com aviso: veja o painel."
                elif agora:
                    self.status = f"Verificando: {rotulos.get(agora.get('id'), agora.get('rotulo', ''))}…"
                if boot.get("concluido") and (ja_aberto or janela_do_jarvis_aberta()):
                    self.fim_em = self.fim_em or time.time() + (1.0 if ja_aberto else 1.6)
                elif boot.get("concluido"):
                    self.fim_em = self.fim_em or time.time() + 5          # sem janela (so servico): fecha
            elif time.time() - self.t0 > 8:
                self.status = "Carregando o núcleo: voz, câmera e modelos…"
            if time.time() - self.t0 > LIMITE_S and not self.fim_em:
                self.status = "O Jarvis está demorando. Veja a janela \"Jarvis runtime\"."
                self.fim_em = time.time() + 8
            time.sleep(0.5)

    def fechar(self) -> None:
        self.vivo = False
        try:
            self.r.destroy()
        except tk.TclError:
            pass


def unica() -> bool:
    try:
        pid = int(TRAVA.read_text())
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if pid != os.getpid() and h:
            codigo = wintypes.DWORD()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(codigo))
            ctypes.windll.kernel32.CloseHandle(h)
            if codigo.value == 259:                          # STILL_ACTIVE: ja ha uma tela aberta
                return False
    except (OSError, ValueError):
        pass
    try:
        TRAVA.write_text(str(os.getpid()))
    except OSError:
        pass
    return True


def main() -> int:
    if not unica():
        return 0
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (OSError, AttributeError):
        pass
    s = Splash("--show" in sys.argv)
    s.r.mainloop()
    try:
        if TRAVA.read_text() == str(os.getpid()):
            TRAVA.unlink()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
