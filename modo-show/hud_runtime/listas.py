"""Listas por voz, como na Alexa: "adicione leite e pão à lista de compras",
"o que tem na lista de compras?", "tire o leite da lista", "limpe a lista de compras".

Guardadas em ~/.openjarvis/hud-listas.json ({nome da lista: [itens]}). Sem nome,
a lista e "compras". Itens repetidos nao entram duas vezes.
"""

from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
from pathlib import Path

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def separar_itens(texto: str) -> list[str]:
    """ "leite, pão e 2 ovos" -> ["leite", "pão", "2 ovos"]."""
    partes = re.split(r",|\s+e\s+", texto)
    itens = []
    for p in partes:
        p = re.sub(r"^(?:o|a|os|as|um|uma|uns|umas)\s+", "", p.strip(" .!?"), flags=re.I)
        if p:
            itens.append(p[:60])
    return itens


def juntar(itens: list[str]) -> str:
    """["leite", "pão", "ovos"] -> "leite, pão e ovos"."""
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1] if itens else ""


def nome_lista(texto: str | None) -> str:
    n = _norm(texto or "").strip(" .!?")
    n = re.sub(r"^(?:de|do|da|dos|das)\s+", "", n)
    return {"mercado": "compras", "supermercado": "compras", "feira": "compras"}.get(n, n or "compras")


class Listas:
    def __init__(self, arquivo: Path = HOME / "hud-listas.json") -> None:
        self._arquivo = arquivo
        self._trava = threading.Lock()

    def _ler(self) -> dict[str, list[str]]:
        try:
            d = json.loads(self._arquivo.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _gravar(self, d: dict[str, list[str]]) -> None:
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._arquivo)

    def ler(self, lista: str) -> list[str]:
        return list(self._ler().get(lista, []))

    def adicionar(self, lista: str, itens: list[str]) -> list[str]:
        with self._trava:
            d = self._ler()
            atual = d.setdefault(lista, [])
            vistos = {_norm(i) for i in atual}
            novos = [i for i in itens if _norm(i) not in vistos]
            atual.extend(novos)
            self._gravar(d)
        return novos

    def remover(self, lista: str, item: str) -> str | None:
        alvo = _norm(re.sub(r"^(?:o|a|os|as)\s+", "", item.strip(), flags=re.I))
        with self._trava:
            d = self._ler()
            for i in d.get(lista, []):
                if _norm(i) == alvo or alvo in _norm(i):
                    d[lista].remove(i)
                    self._gravar(d)
                    return i
        return None

    def limpar(self, lista: str) -> int:
        with self._trava:
            d = self._ler()
            n = len(d.get(lista, []))
            d[lista] = []
            self._gravar(d)
        return n

    def nomes(self) -> list[str]:
        return [k for k, v in self._ler().items() if v]
