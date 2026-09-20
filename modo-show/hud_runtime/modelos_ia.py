"""Qual modelo usar AGORA (principal ou reserva).

O modelo principal do Senhor (gemma4:e4b, 9,6 GB) nem sempre cabe na memoria desta
maquina (11,7 GB, quase sempre acima de 90% de uso). Quando nao cabe, o Ollama
devolve "timed out waiting for llama-server to start" depois de MINUTOS -- foi o
que derrubou a conversa em 19/09.

Regra (autorizada pelo Senhor em 19/09): tenta o principal; usa o reserva
(qwen3.5:4b, 3,4 GB) quando ele nao esta carregado E nao cabe na memoria livre, ou
quando acabou de falhar. A troca nunca e silenciosa: fica no registro e o Jarvis
avisa na fala (no maximo uma vez a cada 30 min).
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from . import OLLAMA

FOLGA_GB = 0.8                     # o modelo precisa caber com uma folga
VALIDADE_S = 20.0                  # cache das consultas ao Ollama
FALHA_VALE_S = 600.0               # depois de falhar, o principal fica de molho 10 min
AVISO_S = 1800.0                   # avisa a troca no maximo a cada 30 min

_trava = threading.Lock()
_cache: dict[str, tuple[float, Any]] = {}
_falhas: dict[str, float] = {}
_ultimo_aviso = 0.0


def _consultar(caminho: str, dados: dict | None = None) -> Any:
    agora = time.time()
    with _trava:
        quando, valor = _cache.get(caminho, (0.0, None))
        if agora - quando < VALIDADE_S:
            return valor
    try:
        corpo = json.dumps(dados).encode() if dados is not None else None
        req = urllib.request.Request(f"{OLLAMA}{caminho}", data=corpo, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            valor = json.load(r)
    except (urllib.error.URLError, OSError, ValueError):
        valor = None
    with _trava:
        _cache[caminho] = (time.time(), valor)
    return valor


def tamanho_gb(modelo: str) -> float | None:
    d = _consultar("/api/tags")
    for m in (d or {}).get("models", []):
        if m.get("name") == modelo or m.get("model") == modelo:
            return float(m.get("size", 0)) / 1e9
    return None


def carregado(modelo: str) -> bool:
    d = _consultar("/api/ps")
    return any(m.get("name") == modelo or m.get("model") == modelo for m in (d or {}).get("models", []))


def memoria_livre_gb() -> float | None:
    try:
        import psutil
        return psutil.virtual_memory().available / 1e9
    except Exception:  # noqa: BLE001 - sem psutil: decide so pelas falhas
        return None


def marcar_falha(modelo: str) -> None:
    _falhas[modelo] = time.time()


def falhou_ha_pouco(modelo: str) -> bool:
    return time.time() - _falhas.get(modelo, 0.0) < FALHA_VALE_S


def escolher(prefs: dict[str, Any]) -> tuple[str, str | None]:
    """(modelo a usar, motivo da reserva ou None). Nao chama o Ollama se nao houver reserva."""
    principal = prefs.get("modelo_voz") or "qwen3.5:4b"
    reserva = (prefs.get("modelo_reserva") or "").strip()
    if not reserva or reserva == principal:
        return principal, None
    if falhou_ha_pouco(principal):
        return reserva, "o modelo principal acabou de falhar"
    if carregado(principal):
        return principal, None
    tamanho, livre = tamanho_gb(principal), memoria_livre_gb()
    if tamanho and livre is not None and livre < tamanho + FOLGA_GB:
        return reserva, f"o modelo principal ({tamanho:.1f} GB) não cabe na memória livre ({livre:.1f} GB)"
    return principal, None


def aviso_de_reserva(motivo: str | None, tratamento: str = "Senhor") -> str:
    """Frase curta para a fala, no maximo uma vez a cada 30 min (vazia nas outras)."""
    global _ultimo_aviso
    if not motivo:
        return ""
    agora = time.time()
    if agora - _ultimo_aviso < AVISO_S:
        return ""
    _ultimo_aviso = agora
    return f"Usando o modelo reserva, {tratamento}: {motivo}. "
