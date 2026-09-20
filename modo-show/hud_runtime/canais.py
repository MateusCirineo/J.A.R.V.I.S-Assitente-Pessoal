"""Cada canal declara o que sabe fazer -- e o Jarvis não promete o resto.

F37 do prompt mestre: "Cada cliente ou integração deve declarar capacidades:
texto, áudio, arquivos, apresentação ou controle permitido. Não prometer
chamadas telefônicas ou acesso a aplicativos que o conector não oferece."

O problema concreto desta casa: pelo Telegram o Senhor recebe TEXTO. Se ele
pedir "leia isso em voz alta" por lá, a fala sai no computador, não no celular
-- e o Jarvis precisa dizer isso, em vez de responder "pronto, estou lendo".

Duas regras:

1. **Capacidade não declarada é capacidade ausente.** Na dúvida, o canal não faz.
2. **Autenticado é diferente de capaz.** Um canal pareado pode receber texto e
   ainda assim não tocar áudio; e um canal capaz sem autenticação não recupera
   contexto privado nem executa ação (§14).
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

# o que um canal pode oferecer
TEXTO = "texto"                  # recebe e devolve texto
AUDIO = "audio"                  # reproduz fala NAQUELE canal
ARQUIVO = "arquivo"              # entrega arquivo (STL, planilha, transcrição)
APRESENTACAO = "apresentacao"    # mostra modelo 3D, gráfico, cartão
CONTROLE = "controle"            # dispara ações no computador
CAPACIDADES = (TEXTO, AUDIO, ARQUIVO, APRESENTACAO, CONTROLE)

_FALADO = {
    TEXTO: "texto",
    AUDIO: "áudio falado",
    ARQUIVO: "arquivos",
    APRESENTACAO: "apresentação na tela",
    CONTROLE: "controle do computador",
}

# o que existe DE FATO nesta instalação (20/09/2026)
PADRAO: dict[str, dict[str, Any]] = {
    "voz": {"nome": "Voz no computador", "capacidades": (TEXTO, AUDIO, ARQUIVO, APRESENTACAO, CONTROLE),
            "autenticado": True, "detalhe": "microfone e alto-falante desta máquina"},
    "tela": {"nome": "Telas do HUD", "capacidades": (TEXTO, AUDIO, ARQUIVO, APRESENTACAO, CONTROLE),
             "autenticado": True, "detalhe": "autenticada por token da instância"},
    "chat": {"nome": "Chat do OpenJarvis", "capacidades": (TEXTO, ARQUIVO),
             "autenticado": True, "detalhe": "texto e arquivos; a fala sai no computador"},
    "telegram": {"nome": "Telegram", "capacidades": (TEXTO,),
                 "autenticado": False, "detalhe": "só texto, e só depois do pareamento"},
}


@dataclass
class Canal:
    id: str
    nome: str
    capacidades: tuple[str, ...] = ()
    autenticado: bool = False
    detalhe: str = ""
    visto_em: float = field(default_factory=time.time)

    def pode(self, capacidade: str) -> bool:
        return capacidade in self.capacidades

    def falado(self) -> str:
        lista = [_FALADO.get(c, c) for c in self.capacidades] or ["nada declarado"]
        junto = lista[0] if len(lista) == 1 else ", ".join(lista[:-1]) + " e " + lista[-1]
        estado = "autenticado" if self.autenticado else "sem autenticação"
        return f"{self.nome} ({estado}): {junto}"


class Canais:
    """Registro dos canais. Quem não está aqui não tem capacidade nenhuma."""

    def __init__(self, padrao: dict[str, dict[str, Any]] | None = None) -> None:
        self._trava = threading.RLock()
        self._canais: dict[str, Canal] = {}
        for cid, d in (padrao if padrao is not None else PADRAO).items():
            self.registrar(cid, d["nome"], d["capacidades"], autenticado=d.get("autenticado", False),
                           detalhe=d.get("detalhe", ""))

    def registrar(self, cid: str, nome: str, capacidades: Iterable[str], *,
                  autenticado: bool = False, detalhe: str = "") -> Canal:
        caps = tuple(c for c in capacidades if c in CAPACIDADES)
        with self._trava:
            c = Canal(id=cid, nome=nome, capacidades=caps, autenticado=autenticado, detalhe=detalhe)
            self._canais[cid] = c
        return c

    def autenticar(self, cid: str, autenticado: bool = True) -> Canal | None:
        with self._trava:
            c = self._canais.get(cid)
            if c is not None:
                c.autenticado = autenticado
                c.visto_em = time.time()
            return c

    def obter(self, cid: str) -> Canal | None:
        return self._canais.get(cid)

    def listar(self) -> list[Canal]:
        return sorted(self._canais.values(), key=lambda c: c.id)

    def pode(self, cid: str, capacidade: str) -> bool:
        """Canal desconhecido não pode nada -- é o padrão seguro."""
        c = self._canais.get(cid)
        return bool(c and c.pode(capacidade))

    def porque_nao(self, cid: str, capacidade: str, tratamento: str = "Senhor") -> str:
        """A frase honesta para quando o canal não faz aquilo."""
        c = self._canais.get(cid)
        nome_cap = _FALADO.get(capacidade, capacidade)
        if c is None:
            return f"Não conheço esse canal, {tratamento}, então não prometo {nome_cap} por ele."
        partes = []
        if not c.pode(capacidade):
            onde = "no computador" if capacidade == AUDIO else "aqui"
            partes.append(f"{c.nome} não faz {nome_cap} — {c.detalhe}; o que dá sai {onde}")
        if not c.autenticado:
            partes.append("e ainda não está autenticado: por ele eu não recupero contexto "
                          "privado nem executo ações")
        if not partes:                                   # faz e está autenticado
            return f"{c.nome} faz {nome_cap}, {tratamento}."
        return partes[0][0].upper() + partes[0][1:] + (f", {tratamento}" if len(partes) == 1
                                                       else f" {partes[1]}, {tratamento}") + "."

    def cartao(self) -> dict[str, Any]:
        return {"canais": [asdict(c) for c in self.listar()], "em": time.time()}


def falar_lista(canais: list[Canal], tratamento: str = "Senhor") -> str:
    if not canais:
        return f"Não há canal declarado, {tratamento}."
    return f"Canais, {tratamento}: " + "; ".join(c.falado() for c in canais) + "."
