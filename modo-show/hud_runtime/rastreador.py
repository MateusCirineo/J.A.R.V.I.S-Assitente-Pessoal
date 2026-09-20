"""Seguir o MESMO objeto entre quadros -- e admitir quando não dá para seguir.

O detector olha cada quadro do zero: dois copos na mesa viram "dois copos" e
pronto. Sem isto o Jarvis não consegue dizer "aquele copo saiu da mesa" nem
"ainda é o mesmo componente", e pior: pode trocar um pelo outro sem avisar.

Regras (§9 e §10 do prompt mestre de 19/09):

1. **Identificador é temporário.** "obj3" vale para esta cena; identidade de
   verdade só por cadastro (ver identidade.py e o inventário pessoal).
2. **Na dúvida, objeto novo.** Se a evidência para dizer "é o mesmo" for fraca,
   nasce outro identificador. Trocar identidade em silêncio é pior que perder.
3. **Sumir não é deixar de existir.** Um objeto tapado fica "sumido" por alguns
   segundos e pode voltar; depois disso, some de vez.
"""

from __future__ import annotations

import time
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable

# quanto as caixas precisam se sobrepor para eu dizer que e o mesmo objeto
IOU_MESMO = 0.35
# reaparecendo depois de tapado: exijo mais parecenca, porque a chance de erro cresce
IOU_VOLTOU = 0.5
SUMIDO_S = 6.0             # tempo que um objeto tapado continua "sumido" antes de morrer
FIRME_QUADROS = 2          # visto em 2 quadros para virar objeto de verdade (menos ruido)
TAMANHO_PARECIDO = 2.2     # area pode variar ate esse fator e ainda ser "o mesmo"
MARGEM_ASSOCIACAO = 0.12  # diferença mínima entre candidatos; não é probabilidade


def iou(a: dict[str, float], b: dict[str, float]) -> float:
    """Sobreposição de duas caixas (frações do quadro)."""
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    ix = max(0.0, min(ax2, bx2) - max(a["x"], b["x"]))
    iy = max(0.0, min(ay2, by2) - max(a["y"], b["y"]))
    inter = ix * iy
    uniao = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / uniao if uniao > 0 else 0.0


@dataclass
class Trilha:
    """Um objeto seguido. `id` é temporário: vale para esta cena, não para sempre."""
    id: str
    classe: int
    nome: str
    caixa: dict[str, float]
    conf: float
    visto_em: float
    nascido_em: float
    quadros: int = 1
    visto_no_quadro: int = 0              # numero do quadro, nao a hora: o relogio do
    sumido_desde: float | None = None     # Windows repete o mesmo valor por ~16 ms
    voltou: int = 0                       # quantas vezes reapareceu depois de sumir
    historico: list[tuple[float, dict[str, float]]] = field(default_factory=list)

    @property
    def firme(self) -> bool:
        return self.quadros >= FIRME_QUADROS

    @property
    def sumido(self) -> bool:
        return self.sumido_desde is not None

    def onde(self) -> str:
        """"à esquerda", "no centro", "à direita" -- pela última vez que eu vi."""
        cx = self.caixa["x"] + self.caixa["w"] / 2
        return "à esquerda" if cx < 0.38 else "à direita" if cx > 0.62 else "no centro"


class Rastreador:
    """Casa as detecções de cada quadro com as trilhas abertas."""

    def __init__(self, sumido_s: float = SUMIDO_S, relogio=time.time) -> None:
        self._trilhas: dict[str, Trilha] = {}
        self._proximo = 1
        self._quadro_n = 0
        self._sumido_s = sumido_s
        self._relogio = relogio
        self.ultimos_sumiram: list[Trilha] = []
        self.ultimos_apareceram: list[Trilha] = []
        self.ultimas_ambiguidades: list[str] = []
        self._eventos: deque[dict[str, Any]] = deque(maxlen=500)

    # ---- consulta -------------------------------------------------------
    def ativos(self) -> list[Trilha]:
        return [t for t in self._trilhas.values() if not t.sumido and t.firme]

    def sumidos(self) -> list[Trilha]:
        return [t for t in self._trilhas.values() if t.sumido and t.firme]

    def todos(self) -> list[Trilha]:
        return list(self._trilhas.values())

    def obter(self, tid: str) -> Trilha | None:
        return self._trilhas.get(tid)

    def da_classe(self, classe: int) -> list[Trilha]:
        return [t for t in self.ativos() if t.classe == classe]

    def eventos(self) -> list[dict[str, Any]]:
        """Histórico limitado desta sessão, sem fotos nem persistência implícita."""
        return [dict(e) for e in self._eventos]

    def _registrar(self, trilha: Trilha, tipo: str, quando: float, motivo: str = "") -> None:
        self._eventos.append({"quando": quando, "tipo": tipo, "nome": trilha.nome,
                              "onde": trilha.onde(), "trilha": trilha.id,
                              "classe": trilha.classe, "motivo": motivo})

    # ---- atualizacao ----------------------------------------------------
    def atualizar(self, deteccoes: Iterable[dict[str, Any]]) -> list[Trilha]:
        """Recebe as detecções de UM quadro e devolve as trilhas ativas."""
        agora = self._relogio()
        self._quadro_n += 1
        livres = [d for d in deteccoes if all(isinstance(d.get(k), (int, float))
                   and math.isfinite(d[k]) for k in ("x", "y", "w", "h"))
                   and d["w"] > 0 and d["h"] > 0 and "classe" in d]
        self.ultimos_sumiram, self.ultimos_apareceram = [], []
        self.ultimas_ambiguidades = []

        # Expirar ANTES de associar: um quadro depois de longa pausa não prova continuidade.
        for tid, trilha in list(self._trilhas.items()):
            if agora - trilha.visto_em > self._sumido_s:
                if not trilha.sumido and trilha.firme:
                    self._registrar(trilha, "objeto_sumiu", agora, "continuidade expirada")
                del self._trilhas[tid]

        # Associação precisa ser inequívoca nos dois sentidos. Em cruzamentos,
        # encerrar as trilhas evita a escolha gulosa e sua troca silenciosa de IDs.
        pares = []
        for t in self._trilhas.values():
            minimo = IOU_VOLTOU if t.sumido else IOU_MESMO
            for indice, d in enumerate(livres):
                _, nota = self._melhor(t, [d], minimo)
                if nota > minimo:
                    pares.append((t.id, indice, nota))
        incertos = set()
        for t in self._trilhas.values():
            escolhas = sorted((p for p in pares if p[0] == t.id), key=lambda p: -p[2])
            if len(escolhas) > 1 and escolhas[0][2] - escolhas[1][2] < MARGEM_ASSOCIACAO:
                incertos.add(t.id)
        for indice in range(len(livres)):
            escolhas = sorted((p for p in pares if p[1] == indice), key=lambda p: -p[2])
            if len(escolhas) > 1 and escolhas[0][2] - escolhas[1][2] < MARGEM_ASSOCIACAO:
                incertos.update(p[0] for p in escolhas)
        for tid in incertos:
            trilha = self._trilhas.pop(tid)
            trilha.sumido_desde = agora
            self.ultimas_ambiguidades.append(tid)
            if trilha.firme:
                self.ultimos_sumiram.append(trilha)
                self._registrar(trilha, "objeto_sumiu", agora, "associação ambígua; identidade temporária encerrada")

        # 1) casar com quem eu estava vendo agora mesmo (o caso comum)
        for trilha in sorted((t for t in self._trilhas.values() if not t.sumido),
                             key=lambda t: -t.quadros):
            melhor, nota = self._melhor(trilha, livres, IOU_MESMO)
            if melhor is not None:
                livres.remove(melhor)
                self._casar(trilha, melhor, agora, self._quadro_n)

        # 2) quem sobrou pode ser alguem que estava tapado voltando
        for trilha in sorted((t for t in self._trilhas.values() if t.sumido),
                             key=lambda t: t.sumido_desde or 0, reverse=True):
            melhor, nota = self._melhor(trilha, livres, IOU_VOLTOU)
            if melhor is not None:
                livres.remove(melhor)
                trilha.voltou += 1
                trilha.sumido_desde = None
                self._casar(trilha, melhor, agora, self._quadro_n)
                self.ultimos_apareceram.append(trilha)
                self._registrar(trilha, "objeto_voltou", agora)

        # 3) o que ainda sobrou e objeto novo (na duvida, id novo)
        for d in livres:
            t = Trilha(id=f"obj{self._proximo}", classe=d["classe"], nome=d.get("nome", ""),
                       caixa={k: d[k] for k in ("x", "y", "w", "h")}, conf=d.get("conf", 0.0),
                       visto_em=agora, nascido_em=agora, visto_no_quadro=self._quadro_n)
            self._proximo += 1
            self._trilhas[t.id] = t

        # 4) quem eu nao vi neste quadro: marca como sumido; passou do tempo, morre
        for tid, trilha in list(self._trilhas.items()):
            if trilha.visto_no_quadro == self._quadro_n:
                continue
            if not trilha.sumido:
                trilha.sumido_desde = agora
                if trilha.firme:
                    self.ultimos_sumiram.append(trilha)
                    self._registrar(trilha, "objeto_sumiu", agora)
            elif agora - trilha.sumido_desde > self._sumido_s:
                del self._trilhas[tid]
        return self.ativos()

    def _melhor(self, trilha: Trilha, candidatos: list[dict], minimo: float):
        melhor, nota_melhor = None, minimo
        for d in candidatos:
            if d["classe"] != trilha.classe:
                continue                                  # categoria diferente: nem penso
            area_d = d["w"] * d["h"]
            area_t = trilha.caixa["w"] * trilha.caixa["h"]
            if area_t > 0 and not (1 / TAMANHO_PARECIDO <= area_d / area_t <= TAMANHO_PARECIDO):
                continue                                  # tamanho muito diferente: outro objeto
            nota = iou({k: d[k] for k in ("x", "y", "w", "h")}, trilha.caixa)
            if nota > nota_melhor:
                melhor, nota_melhor = d, nota
        return melhor, nota_melhor

    def _casar(self, trilha: Trilha, d: dict, agora: float, quadro: int) -> None:
        if not trilha.firme and trilha.quadros + 1 >= FIRME_QUADROS:
            self._registrar(trilha, "objeto_visto", trilha.nascido_em)
        trilha.historico.append((trilha.visto_em, dict(trilha.caixa)))
        del trilha.historico[:-20]
        trilha.caixa = {k: d[k] for k in ("x", "y", "w", "h")}
        trilha.conf = d.get("conf", trilha.conf)
        trilha.nome = d.get("nome", trilha.nome)
        trilha.visto_em = agora
        trilha.visto_no_quadro = quadro
        trilha.quadros += 1


def descrever_mudancas(sumiram: list[Trilha], apareceram: list[Trilha],
                       novos: list[Trilha] | None = None) -> str:
    """Frase honesta sobre a cena; vazia quando nada mudou."""
    partes = []
    for t in apareceram:
        partes.append(f"{t.nome} voltou a aparecer {t.onde()}")
    for t in (novos or []):
        partes.append(f"apareceu {t.nome} {t.onde()}")
    for t in sumiram:
        partes.append(f"{t.nome} saiu de vista")
    return "; ".join(partes)


def falar_ultima_vez(t: Trilha, agora: float | None = None, tratamento: str = "Senhor") -> str:
    """"Vi por último às 14h12, à esquerda" -- NUNCA "está lá agora" (§9)."""
    import datetime
    agora = agora if agora is not None else time.time()
    quando = datetime.datetime.fromtimestamp(t.visto_em)
    faz = agora - t.visto_em
    if not t.sumido and faz < 3:
        return f"Estou vendo {t.nome} agora, {t.onde()}."
    quanto = ("agora há pouco" if faz < 60 else
              f"há {int(faz // 60)} minutos" if faz < 3600 else
              f"às {quando:%H:%M}")
    return (f"Vi {t.nome} por último {quanto}, {t.onde()}. "
            f"Não posso afirmar que ainda esteja lá.")
