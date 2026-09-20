"""O que o OpenJarvis tem instalado: agentes, canais, skills e persona (A7-A9).

So LEITURA e descoberta: nada e ativado daqui. Canal registrado nao e canal
conectado; conectar e escolha do usuario, na configuracao do OpenJarvis.
A lista de adaptadores de canal e descoberta num processo separado (importa
~30 modulos) e guardada em cache, para nao pesar o runtime do HUD.

Persona do Chat: o servidor ja injeta SOUL.md / USER.md / MEMORY.md em
/v1/chat/completions. Se os arquivos nao existem, o Chat usa o prompt padrao;
`criar_persona` cria SOUL.md e USER.md SO quando o usuario pede (botao), sem
sobrescrever, e o USER.md so leva o que ja esta nas preferencias.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import SERVIDOR_OPENJARVIS

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
_CANAIS: dict[str, Any] = {"lista": None, "em": 0.0}

SOUL = """# J.A.R.V.I.S.

Você é o J.A.R.V.I.S., assistente pessoal do usuário, rodando no computador dele.
- Fale em português do Brasil, com tom sóbrio, prestativo e breve; humor discreto só de vez em quando.
- Chame o usuário como ele preferir (veja USER.md).
- Não invente fatos, fontes, datas ou números. Quando citar notícia ou dado, diga de onde veio.
- Diga claramente o que fez, o que só preparou e o que falhou. Nunca diga que enviou ou executou algo sem confirmação.
- Antes de ações com efeito externo (enviar, apagar, comprar, compartilhar), peça confirmação.
- Se não souber, diga que não sabe.
"""


def _get(caminho: str, timeout: float = 5) -> Any:
    with urllib.request.urlopen(f"{SERVIDOR_OPENJARVIS}{caminho}", timeout=timeout) as r:
        return json.load(r)


def canais_registrados(atualizar: bool = False) -> list[str] | None:
    if _CANAIS["lista"] is not None and not atualizar:
        return _CANAIS["lista"]
    codigo = ("import importlib, json, pkgutil, openjarvis.channels as c\n"
              "from openjarvis.core.registry import ChannelRegistry\n"
              "for m in pkgutil.iter_modules(c.__path__):\n"
              "    try: importlib.import_module('openjarvis.channels.' + m.name)\n"
              "    except Exception: pass\n"
              "print(json.dumps(sorted(ChannelRegistry.keys())))\n")
    try:
        saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=120,
                               creationflags=0x08000000).stdout.strip().splitlines()
        _CANAIS.update(lista=json.loads(saida[-1]) if saida else [], em=time.time())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return _CANAIS["lista"]


def persona() -> dict[str, bool]:
    return {nome: (HOME / nome).is_file() for nome in ("SOUL.md", "USER.md", "MEMORY.md")}


def resumo() -> dict[str, Any]:
    saida: dict[str, Any] = {"status": "medido", "em": time.time(), "persona": persona()}
    try:
        ag = _get("/v1/agents")
        saida["agentes"] = [{"chave": a["key"], "ferramentas": bool(a.get("accepts_tools"))} for a in ag.get("registered", [])]
        saida["agentes_rodando"] = len(ag.get("running") or [])
        saida["ponte_canais"] = _get("/v1/channels/status").get("status")
        saida["skills"] = len(_get("/v1/skills").get("skills") or [])
    except (urllib.error.URLError, OSError, ValueError) as e:
        saida.update(status="erro", detalhe=f"servidor do OpenJarvis não respondeu ({type(e).__name__})")
    saida["canais"] = canais_registrados()
    return saida


def criar_persona(prefs: dict[str, Any]) -> dict[str, Any]:
    """Cria SOUL.md e USER.md que faltarem. Nunca sobrescreve."""
    criados = []
    soul = HOME / "SOUL.md"
    if not soul.exists():
        soul.write_text(SOUL, encoding="utf-8")
        criados.append("SOUL.md")
    user = HOME / "USER.md"
    if not user.exists():
        linhas = ["# Usuário", ""]
        if prefs.get("nome_usuario"):
            linhas.append(f"- Como chamar: {prefs['nome_usuario']}")
        linhas.append("- Idioma: português do Brasil")
        cidades = [c["nome"] for c in [prefs.get("local_clima")] + (prefs.get("climas_extras") or []) if c]
        if cidades:
            linhas.append(f"- Cidades do clima: {', '.join(cidades)}")
        user.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        criados.append("USER.md")
    return {"criados": criados, "persona": persona()}
