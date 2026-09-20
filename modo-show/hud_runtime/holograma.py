"""Apoio da mesa holografica: monitores (o projetor e o segundo monitor), achar
modelos 3D do Senhor pelo nome e montar graficos (cotacoes, clima) para a mesa.

Modelos: .stl e .obj em Documentos\\Jarvis\\Projetos, Area de Trabalho, Downloads,
Documentos e Objetos 3D (ate 3 pastas de profundidade). Nada e enviado para fora:
a pagina pede o arquivo escolhido ao runtime, com o token da sessao.
"""

from __future__ import annotations

import ctypes
import os
import time
import unicodedata
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Any

EXTENSOES = (".stl", ".obj")


def monitores() -> list[dict[str, Any]]:
    """[{x, y, w, h, principal}] de cada monitor (o projetor aparece como um deles)."""
    saida: list[dict[str, Any]] = []

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                              wintypes.LPARAM)

    def cada(hmon, _hdc, _rect, _l):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcMonitor
            saida.append({"x": r.left, "y": r.top, "w": r.right - r.left, "h": r.bottom - r.top,
                          "principal": bool(mi.dwFlags & 1)})
        return True
    try:
        ctypes.windll.user32.EnumDisplayMonitors(None, None, PROC(cada), 0)
    except (OSError, AttributeError):
        pass
    return saida


def projetor() -> dict[str, Any] | None:
    """O monitor que nao e o principal (projetor/TV), se houver."""
    return next((m for m in monitores() if not m["principal"]), None)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.replace("_", " ").replace("-", " ").replace(".", " ").split())


def pastas_de_modelos() -> list[Path]:
    casa = Path.home()
    docs = casa / "Documents"
    candidatas = [docs / "Jarvis" / "Projetos", casa / "OneDrive" / "Área de Trabalho", casa / "Desktop",
                  casa / "Downloads", docs, casa / "OneDrive" / "Documentos", casa / "3D Objects"]
    return [p for p in candidatas if p.is_dir()]


def achar_modelo(pedido: str, pastas: list[Path] | None = None, profundidade: int = 3) -> Path | None:
    """O arquivo .stl/.obj cujo nome mais combina com o pedido (o mais recente no empate)."""
    alvo = set(_norm(pedido).split()) - {"o", "a", "de", "do", "da", "modelo", "arquivo", "projeto", "3d", "peca"}
    melhor: tuple[float, float, Path] | None = None
    for base in pastas if pastas is not None else pastas_de_modelos():
        for raiz, dirs, arquivos in os.walk(base):
            if Path(raiz).relative_to(base).parts.__len__() >= profundidade:
                dirs[:] = []
            dirs[:] = [d for d in dirs if not d.startswith((".", "$")) and d.lower() not in ("node_modules", "appdata")]
            for a in arquivos:
                if not a.lower().endswith(EXTENSOES):
                    continue
                palavras = set(_norm(Path(a).stem).split())
                if not alvo:
                    nota = 0.1
                else:
                    iguais = len(alvo & palavras)
                    parciais = sum(1 for w in alvo for p in palavras if w != p and (w in p or p in w) and len(w) >= 3)
                    nota = (iguais + 0.5 * parciais) / len(alvo)
                if nota <= 0:
                    continue
                caminho = Path(raiz) / a
                try:
                    quando = caminho.stat().st_mtime
                except OSError:
                    continue
                if melhor is None or (nota, quando) > melhor[:2]:
                    melhor = (nota, quando, caminho)
    return melhor[2] if melhor else None


# ---- graficos -------------------------------------------------------------------------
MOEDAS = {"dolar": ("USD-BRL", "Dólar"), "euro": ("EUR-BRL", "Euro"), "libra": ("GBP-BRL", "Libra"),
          "peso": ("ARS-BRL", "Peso argentino")}
CRIPTOS = {"bitcoin": ("bitcoin", "Bitcoin"), "ethereum": ("ethereum", "Ethereum"), "solana": ("solana", "Solana")}


def _variacao(pontos: list[list[float]]) -> float:
    return (pontos[-1][1] / pontos[0][1] - 1) * 100 if pontos and pontos[0][1] else 0.0


def grafico_moeda(chave: str, dias: int = 30) -> dict[str, Any]:
    from .rede import baixar_json
    par, nome = MOEDAS[chave]
    dados = baixar_json(f"https://economia.awesomeapi.com.br/json/daily/{par}/{dias}")
    pontos = sorted([[float(d["timestamp"]), float(d["bid"])] for d in dados if d.get("bid")])
    return {"titulo": f"{nome} · {dias} dias (AwesomeAPI)", "unidade": "R$", "series": [{"nome": nome, "pontos": pontos}],
            "variacao": _variacao(pontos), "nome": nome}


def grafico_cripto(chave: str, dias: int = 30) -> dict[str, Any]:
    from .rede import baixar_json
    ident, nome = CRIPTOS[chave]
    dados = baixar_json(f"https://api.coingecko.com/api/v3/coins/{ident}/market_chart?vs_currency=brl&days={dias}&interval=daily")
    pontos = [[p[0] / 1000, float(p[1])] for p in dados.get("prices", [])]
    return {"titulo": f"{nome} · {dias} dias (CoinGecko)", "unidade": "R$", "series": [{"nome": nome, "pontos": pontos}],
            "variacao": _variacao(pontos), "nome": nome}


def grafico_clima(local: dict[str, Any]) -> dict[str, Any]:
    from .rede import baixar_json
    d = baixar_json(f"https://api.open-meteo.com/v1/forecast?latitude={local['lat']}&longitude={local['lon']}"
                    "&hourly=temperature_2m&forecast_days=2&timezone=auto")
    horas, temps = d["hourly"]["time"], d["hourly"]["temperature_2m"]
    agora = time.time()
    pontos = [[datetime.fromisoformat(h).timestamp(), float(t)] for h, t in zip(horas, temps) if t is not None]
    pontos = [p for p in pontos if agora - 3600 <= p[0] <= agora + 24 * 3600]
    return {"titulo": f"Temperatura · próximas 24 h · {local['nome']} (Open-Meteo)", "unidade": "°C",
            "series": [{"nome": local["nome"], "pontos": pontos}], "nome": local["nome"],
            "minimo": min(p[1] for p in pontos) if pontos else None, "maximo": max(p[1] for p in pontos) if pontos else None}
