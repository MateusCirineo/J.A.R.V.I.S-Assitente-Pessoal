"""Quando há duas leituras possíveis, perguntar -- em vez de escolher sozinho.

F04 do prompt mestre: "Fazer uma pergunta breve quando existirem interpretações
relevantes concorrentes." O caso que aparece de verdade aqui: "abra o manual"
com dois manuais indexados, "esqueça a impressora" com duas impressoras
cadastradas, "apague isso" sem alvo claro.

A regra é sempre a mesma: se um candidato está claramente na frente, sigo; se
dois empatam, eu pergunto **citando os dois** -- e não faço nada até a resposta.
Perguntar custa uma frase; escolher errado custa o trabalho do Senhor.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


@dataclass
class Candidato:
    """Uma leitura possível do pedido."""
    id: str
    rotulo: str                   # como o Senhor chamaria isso
    tipo: str = ""                # "documento", "objeto", "peça", "projeto"...
    nota: float = 0.0             # quanto essa leitura casa com o pedido
    extra: Any = None


def pontuar(pedido: str, candidatos: Iterable[Candidato]) -> list[Candidato]:
    """Nota por palavras do pedido que aparecem no rótulo. Simples e explicável."""
    palavras = [p for p in _norm(pedido).split() if len(p) > 2]
    saida = []
    for c in candidatos:
        rotulo = _norm(c.rotulo)
        nota = sum(1.0 for p in palavras if p in rotulo)
        if rotulo and rotulo in _norm(pedido):
            nota += 1.5                       # o rótulo inteiro foi dito
        saida.append(Candidato(id=c.id, rotulo=c.rotulo, tipo=c.tipo, nota=nota, extra=c.extra))
    return sorted(saida, key=lambda c: -c.nota)


def escolher(pedido: str, candidatos: Sequence[Candidato], *, margem: float = 0.5
             ) -> tuple[Candidato | None, list[Candidato]]:
    """(escolhido, empatados). Escolhido só quando ele está na frente por `margem`."""
    if not candidatos:
        return None, []
    ordenados = pontuar(pedido, candidatos)
    if len(ordenados) == 1:
        return ordenados[0], []
    primeiro, segundo = ordenados[0], ordenados[1]
    if primeiro.nota - segundo.nota >= margem and primeiro.nota > 0:
        return primeiro, []
    empatados = [c for c in ordenados if c.nota >= primeiro.nota - 1e-9]
    if len(empatados) == 1:                   # todos zerados: sem pista nenhuma
        empatados = list(ordenados)
    return None, empatados


def perguntar(empatados: Sequence[Candidato], acao: str = "", tratamento: str = "Senhor",
              limite: int = 4) -> str:
    """A pergunta curta, citando as opções pelo nome."""
    nomes = [c.rotulo for c in empatados[:limite]]
    if not nomes:
        return f"Qual deles, {tratamento}?"
    lista = nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " ou " + nomes[-1]
    verbo = f"{acao} " if acao else ""
    a_mais = len(empatados) - len(nomes)
    frase = f"Qual {verbo}o senhor quer, {tratamento}: {lista}?"
    return frase + (f" (tenho mais {a_mais})" if a_mais > 0 else "")


def resolver(pedido: str, candidatos: Sequence[Candidato], acao: str = "",
             tratamento: str = "Senhor") -> tuple[Candidato | None, str]:
    """(escolhido, pergunta). Com pergunta preenchida, NÃO execute nada."""
    escolhido, empatados = escolher(pedido, candidatos)
    if escolhido is not None:
        return escolhido, ""
    return None, perguntar(empatados, acao, tratamento)


def de_objetos(itens: Iterable[Any], rotulo: Callable[[Any], str], tipo: str = "",
               ident: Callable[[Any], str] | None = None) -> list[Candidato]:
    """Transforma uma lista qualquer (documentos, objetos, peças) em candidatos."""
    saida = []
    for x in itens:
        saida.append(Candidato(id=(ident(x) if ident else str(getattr(x, "id", rotulo(x)))),
                               rotulo=rotulo(x), tipo=tipo, extra=x))
    return saida
