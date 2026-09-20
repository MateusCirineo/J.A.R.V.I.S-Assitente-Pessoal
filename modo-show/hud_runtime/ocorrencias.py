"""O que aconteceu, quando e onde -- juntando o que o Jarvis realmente registrou.

F17 do prompt mestre: cruzar ocorrências por período, lugar e atributo. As
fontes são as que já existem nesta casa, nada de sensor novo:

- o **rastreador** sabe o que entrou e saiu de vista, com hora e lado;
- o **inventário** guarda a última vez que vi cada objeto do Senhor;
- o **registro de eventos** tem falhas, avisos e comandos;
- os **projetos** e as **peças** têm datas e versões.

Duas linhas que eu não cruzo: nada aqui vira "está lá agora" (é sempre "vi às
tal hora") e nada aparece fora do que foi observado de verdade -- se a câmera
estava desligada, o período simplesmente não tem observação.
"""

from __future__ import annotations

import datetime
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

TIPOS = ("objeto_visto", "objeto_sumiu", "objeto_voltou", "pessoa", "evento", "tarefa", "peca", "documento")


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


@dataclass
class Ocorrencia:
    quando: float
    tipo: str
    texto: str
    onde: str = ""
    fonte: str = ""                  # câmera, inventário, registro, projeto
    extra: dict[str, Any] = field(default_factory=dict)

    def hora(self) -> str:
        return datetime.datetime.fromtimestamp(self.quando).strftime("%H:%M")

    def falado(self, com_data: bool = False) -> str:
        d = datetime.datetime.fromtimestamp(self.quando)
        quando = d.strftime("%d/%m às %H:%M") if com_data else d.strftime("%H:%M")
        onde = f", {self.onde}" if self.onde else ""
        return f"{quando}: {self.texto}{onde}"


# ---- de onde vêm as ocorrências ----------------------------------------
def de_rastreador(rastreador: Any) -> list[Ocorrencia]:
    saida: list[Ocorrencia] = []
    if callable(getattr(rastreador, "eventos", None)):
        verbos = {"objeto_visto": "apareceu", "objeto_sumiu": "saiu de vista",
                  "objeto_voltou": "voltou a aparecer"}
        for e in rastreador.eventos():
            saida.append(Ocorrencia(quando=e["quando"], tipo=e["tipo"],
                                    texto=f"{e['nome']} {verbos[e['tipo']]}", onde=e["onde"], fonte="câmera",
                                    extra={"trilha": e["trilha"], "classe": e["classe"],
                                           "motivo": e.get("motivo", "")}))
        return saida
    for t in getattr(rastreador, "todos", list)():
        if not getattr(t, "firme", False):
            continue
        saida.append(Ocorrencia(quando=t.nascido_em, tipo="objeto_visto",
                                texto=f"{t.nome} apareceu", onde=t.onde(), fonte="câmera",
                                extra={"trilha": t.id, "classe": t.classe}))
        if t.sumido and t.sumido_desde:
            saida.append(Ocorrencia(quando=t.sumido_desde, tipo="objeto_sumiu",
                                    texto=f"{t.nome} saiu de vista", onde=t.onde(), fonte="câmera",
                                    extra={"trilha": t.id, "classe": t.classe}))
        if t.voltou:
            saida.append(Ocorrencia(quando=t.visto_em, tipo="objeto_voltou",
                                    texto=f"{t.nome} voltou a aparecer", onde=t.onde(), fonte="câmera",
                                    extra={"trilha": t.id}))
    return saida


def de_inventario(inventario: Any) -> list[Ocorrencia]:
    saida: list[Ocorrencia] = []
    for o in getattr(inventario, "todos", list)():
        for obs in getattr(o, "observacoes", []):
            saida.append(Ocorrencia(quando=obs.em, tipo="objeto_visto",
                                    texto=f"vi {o.nome}", onde=obs.onde,
                                    fonte="inventário", extra={"objeto": o.id}))
    return saida


def de_eventos(eventos: Iterable[dict[str, Any]], niveis: tuple[str, ...] = ("aviso", "erro")) -> list[Ocorrencia]:
    saida = []
    for e in eventos or []:
        if e.get("nivel") in niveis:
            saida.append(Ocorrencia(quando=float(e.get("em") or 0), tipo="evento",
                                    texto=str(e.get("texto") or "")[:120],
                                    fonte=f"registro ({e.get('tipo')})"))
    return saida


def de_projetos(projetos: Any) -> list[Ocorrencia]:
    saida: list[Ocorrencia] = []
    for t in getattr(projetos, "todas", list)():
        saida.append(Ocorrencia(quando=t.criada_em, tipo="tarefa",
                                texto=f"comecei {t.objetivo}", fonte="projeto",
                                extra={"tarefa": t.id}))
        for e in t.etapas:
            if e.em:
                verbo = "concluí" if e.pronta else "falhou"
                saida.append(Ocorrencia(quando=e.em, tipo="tarefa",
                                        texto=f"{verbo}: {e.descricao}", fonte="projeto",
                                        extra={"tarefa": t.id}))
    return saida


def de_pecas(pecas: Any) -> list[Ocorrencia]:
    saida: list[Ocorrencia] = []
    for p in getattr(pecas, "todas", list)():
        for v in p.versoes:
            saida.append(Ocorrencia(quando=v.em, tipo="peca",
                                    texto=f"{p.nome} versão {v.numero}: {v.motivo}", fonte="peça",
                                    extra={"peca": p.nome, "versao": v.numero}))
    return saida


# ---- período citado na fala --------------------------------------------
_RELATIVO = re.compile(r"\b(?:nos? ultimos?|nas? ultimas?|faz|ha)\s+(?P<n>\d+)\s*(?P<u>minutos?|horas?|dias?)\b")


def periodo_citado(frase: str, agora: float | None = None) -> tuple[float, float, str]:
    """"hoje de manhã" -> (início, fim, rótulo). Sem período citado: últimas 12 h."""
    agora = agora if agora is not None else time.time()
    n = _norm(frase)
    hoje = datetime.datetime.fromtimestamp(agora).replace(hour=0, minute=0, second=0, microsecond=0)
    meia_noite = hoje.timestamp()

    m = _RELATIVO.search(n)
    if m:
        q = int(m.group("n"))
        seg = {"minuto": 60, "minutos": 60, "hora": 3600, "horas": 3600,
               "dia": 86400, "dias": 86400}[m.group("u")]
        return agora - q * seg, agora, f"{'nos' if q > 1 else 'no'} últimos {q} {m.group('u')}"
    if re.search(r"\bontem\b", n):
        ini = meia_noite - 86400
        return ini, meia_noite, "ontem"
    if re.search(r"\b(?:de manha|pela manha|esta manha)\b", n):
        return meia_noite + 5 * 3600, meia_noite + 12 * 3600, "hoje de manhã"
    if re.search(r"\b(?:a tarde|de tarde|esta tarde)\b", n):
        return meia_noite + 12 * 3600, meia_noite + 18 * 3600, "hoje à tarde"
    if re.search(r"\b(?:a noite|de noite|esta noite)\b", n):
        return meia_noite + 18 * 3600, meia_noite + 24 * 3600, "hoje à noite"
    if re.search(r"\bhoje\b", n):
        return meia_noite, agora, "hoje"
    if re.search(r"\b(?:esta semana|nesta semana|na semana)\b", n):
        return meia_noite - 6 * 86400, agora, "esta semana"
    if re.search(r"\b(?:agora ha pouco|ha pouco|agorinha|recem)\b", n):
        return agora - 900, agora, "nos últimos 15 minutos"
    if re.search(r"\benquanto (?:eu )?(?:estava fora|sai|nao estava)\b", n):
        return agora - 4 * 3600, agora, "nas últimas 4 horas"
    return agora - 12 * 3600, agora, "nas últimas 12 horas"


ONDE = {"esquerda": "à esquerda", "direita": "à direita", "centro": "no centro", "meio": "no centro"}


def filtrar(ocorrencias: Iterable[Ocorrencia], inicio: float, fim: float,
            termo: str = "", onde: str = "", tipos: tuple[str, ...] = ()) -> list[Ocorrencia]:
    alvo = _norm(termo)
    palavras = [p for p in alvo.split() if len(p) > 2]
    saida = []
    for o in ocorrencias:
        if not (inicio <= o.quando <= fim):
            continue
        if tipos and o.tipo not in tipos:
            continue
        if onde and _norm(onde) not in _norm(o.onde):
            continue
        if palavras and not any(p in _norm(o.texto) for p in palavras):
            continue
        saida.append(o)
    return sorted(saida, key=lambda o: o.quando)


def falar(ocorrencias: list[Ocorrencia], rotulo: str, tratamento: str = "Senhor",
          limite: int = 6, com_data: bool = False) -> str:
    if not ocorrencias:
        return (f"Não registrei nada {rotulo}, {tratamento}. Só sei o que a câmera viu com ela "
                f"ligada e o que passou pelo registro.")
    itens = ocorrencias[-limite:]
    corpo = "; ".join(o.falado(com_data) for o in itens)
    a_mais = len(ocorrencias) - len(itens)
    frase = f"{rotulo.capitalize()}, {tratamento}: {corpo}"
    return frase + (f". E mais {a_mais} antes disso." if a_mais > 0 else ".")
