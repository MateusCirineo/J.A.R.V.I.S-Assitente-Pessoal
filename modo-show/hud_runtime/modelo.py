"""Chamada simples ao modelo pelo servidor do OpenJarvis (fluxo oficial).

Para tarefas do HUD que precisam de texto gerado (rascunhos, programas,
resumos): mesmo servidor, mesma politica, cabecalho de caminho direto (sem o
laco do agente, que custa 30-110 s nesta CPU). Sem ferramentas: o modelo so
escreve; quem decide o que fazer com o texto e o codigo do HUD.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from . import SERVIDOR_OPENJARVIS


class ErroModelo(RuntimeError):
    pass


def limpar(texto: str) -> str:
    """Tira raciocinio (<think>) e cercas de codigo soltas no comeco/fim."""
    texto = re.sub(r"<think>.*?</think>", "", texto or "", flags=re.S)
    return texto.strip()


def gerar(mensagens: list[dict[str, Any]], modelo: str, max_tokens: int = 400,
          timeout: float = 600, temperatura: float | None = 0.3) -> str:
    pedido: dict[str, Any] = {"model": modelo, "messages": mensagens, "stream": False, "max_tokens": max_tokens}
    if temperatura is not None:
        pedido["temperature"] = temperatura
    req = urllib.request.Request(f"{SERVIDOR_OPENJARVIS}/v1/chat/completions", data=json.dumps(pedido).encode(),
                                 headers={"Content-Type": "application/json", "X-OpenJarvis-Direct": "1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dados = json.load(r)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ErroModelo(f"o servidor do OpenJarvis não respondeu ({type(e).__name__})") from e
    msg = (dados.get("choices") or [{}])[0].get("message") or {}
    texto = limpar(msg.get("content") or "")
    if not texto:
        raise ErroModelo("o modelo devolveu uma resposta vazia")
    return texto
