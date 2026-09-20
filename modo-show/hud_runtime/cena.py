"""A cena como uma coisa consultável -- e com os buracos assumidos.

F16 do prompt mestre: "Organizar registros, imagens e medidas em uma
representação consultável; **não inventar áreas não observadas**." E §10:
"diferencie observado, interpolado, estimado e desconhecido".

A tentação aqui é grande: com três objetos detectados dá para escrever uma
descrição bonita da sala inteira. Este módulo recusa isso. Ele junta o que o
rastreador viu de fato, em que região, quando, e marca todo o resto como **não
observado** -- que é diferente de "vazio".

Regras, na ordem de importância:

1. **Região sem detecção não é região vazia.** É região sem observação. A câmera
   vê um pedaço da mesa, não a sala.
2. **Medida só com régua calibrada.** Sem calibração não há centímetro nenhum,
   nem "mais ou menos" -- o tamanho aparente fica como tamanho aparente.
3. **O que sumiu vira última observação**, com hora, nunca "está ali".
4. **Nada de 3D.** Isto é um plano de imagem com regiões; não é reconstrução
   métrica da sala e não se apresenta como tal.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

# estados de evidência de cada pedaço da cena (§10)
OBSERVADO = "observado"          # a câmera viu agora
ULTIMA_VEZ = "ultima_observacao"  # viu antes; pode não estar mais lá
ESTIMADO = "estimado"            # deduzido de outra coisa (e dito como dedução)
NAO_OBSERVADO = "nao_observado"  # ninguém olhou: não sei, e não vou chutar

# as regiões do quadro, em fração de largura
REGIOES: dict[str, tuple[float, float]] = {
    "esquerda": (0.0, 0.38),
    "centro": (0.38, 0.62),
    "direita": (0.62, 1.0),
}
VALIDADE_S = 3.0                 # depois disso, "vi" em vez de "estou vendo"


def regiao_de(x: float, largura: float = 0.0) -> str:
    centro = x + largura / 2
    for nome, (a, b) in REGIOES.items():
        if a <= centro < b:
            return nome
    return "direita"


@dataclass
class ItemCena:
    nome: str
    regiao: str
    estado: str                      # observado | ultima_observacao
    visto_em: float
    classe: int = -1
    trilha: str = ""
    medida_cm: tuple[float, float] | None = None
    medida_estado: str = ""          # "medido" (régua calibrada) ou vazio
    fonte: str = "câmera"

    def falado(self, agora: float | None = None) -> str:
        agora = agora if agora is not None else time.time()
        quando = ""
        if self.estado == ULTIMA_VEZ:
            faz = agora - self.visto_em
            quando = (" (vi agora há pouco)" if faz < 60 else
                      f" (vi há {int(faz // 60)} min)" if faz < 3600 else
                      f" (vi às {time.strftime('%H:%M', time.localtime(self.visto_em))})")
        medida = ""
        if self.medida_cm and self.medida_estado == "medido":
            c, l = self.medida_cm
            medida = f", {c:.1f} por {l:.1f} cm medidos".replace(".", ",")
        return f"{self.nome} {self._onde()}{medida}{quando}"

    def _onde(self) -> str:
        return {"esquerda": "à esquerda", "centro": "no centro", "direita": "à direita"}.get(
            self.regiao, self.regiao)


@dataclass
class Cena:
    em: float
    itens: list[ItemCena] = field(default_factory=list)
    regioes_observadas: list[str] = field(default_factory=list)
    regioes_sem_observacao: list[str] = field(default_factory=list)
    camera_ligada: bool = False
    regua_calibrada: bool = False
    detector_rodou: bool = False     # o detector olhou os quadros (mesmo sem achar nada)
    observando_ha_s: float = 0.0
    fonte: str = "câmera do computador"

    @property
    def vazia(self) -> bool:
        return not self.itens

    def na_regiao(self, regiao: str) -> list[ItemCena]:
        return [i for i in self.itens if i.regiao == regiao]

    def agora(self) -> list[ItemCena]:
        return [i for i in self.itens if i.estado == OBSERVADO]

    def antes(self) -> list[ItemCena]:
        return [i for i in self.itens if i.estado == ULTIMA_VEZ]

    def cartao(self) -> dict[str, Any]:
        return {"em": self.em, "camera_ligada": self.camera_ligada,
                "regua_calibrada": self.regua_calibrada,
                "itens": [asdict(i) for i in self.itens],
                "observadas": list(self.regioes_observadas),
                "sem_observacao": list(self.regioes_sem_observacao),
                "fonte": self.fonte}


def montar(rastreador: Any = None, *, camera_ligada: bool = False, regua: Any = None,
           medidas: dict[str, tuple[float, float]] | None = None, detector_rodou: bool = False,
           agora: float | None = None, validade_s: float = VALIDADE_S) -> Cena:
    """Junta o que o rastreador viu numa cena consultável. Nada além disso.

    `detector_rodou` é a diferença entre "não olhei aquela região" e "olhei e não
    reconheci nada ali" -- duas coisas que não podem virar a mesma frase.
    """
    agora = agora if agora is not None else time.time()
    calibrada = bool(getattr(regua, "calibrada", False))
    cena = Cena(em=agora, camera_ligada=camera_ligada, regua_calibrada=calibrada,
                detector_rodou=bool(detector_rodou and camera_ligada))

    trilhas = list(getattr(rastreador, "todos", list)()) if rastreador is not None else []
    for t in trilhas:
        if not getattr(t, "firme", False):
            continue                                   # ruído de um quadro só não é cena
        estado = OBSERVADO if (not t.sumido and agora - t.visto_em <= validade_s) else ULTIMA_VEZ
        item = ItemCena(nome=t.nome or "objeto", regiao=regiao_de(t.caixa["x"], t.caixa["w"]),
                        estado=estado, visto_em=t.visto_em, classe=t.classe, trilha=t.id)
        medida = (medidas or {}).get(t.id)
        if medida and calibrada:                       # medida só com régua calibrada
            item.medida_cm, item.medida_estado = medida, "medido"
        cena.itens.append(item)

    vistas = {i.regiao for i in cena.itens if i.estado == OBSERVADO}
    if cena.detector_rodou:
        # o detector passou os olhos no quadro inteiro: a região FOI observada,
        # mesmo que nada com nome tenha aparecido nela
        cena.regioes_observadas = list(REGIOES)
        cena.regioes_sem_observacao = []
    else:
        # região sem detecção NÃO é região vazia: é região sem observação
        cena.regioes_observadas = [r for r in REGIOES if r in vistas]
        cena.regioes_sem_observacao = [r for r in REGIOES if r not in vistas]
    if not camera_ligada:
        cena.regioes_observadas = []
        cena.regioes_sem_observacao = list(REGIOES)
    return cena


# ---- como o Jarvis fala da cena -----------------------------------------
def _lista(itens: list[str]) -> str:
    if not itens:
        return ""
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def falar(cena: Cena, tratamento: str = "Senhor", limite: int = 6) -> str:
    """Descrição da cena que não promete o que não foi visto."""
    if not cena.camera_ligada:
        return (f"A câmera está desligada, {tratamento}, então não tenho cena nenhuma agora. "
                f"Ligue a câmera e eu monto.")
    agora_itens = cena.agora()
    antes_itens = cena.antes()
    partes: list[str] = []
    if agora_itens:
        partes.append("Estou vendo " + _lista([i.falado(cena.em) for i in agora_itens[:limite]]))
    elif cena.detector_rodou:
        partes.append("Olhei o quadro inteiro e não reconheci nada das categorias que eu conheço"
                      " — pode haver coisa ali que eu não sei nomear")
    else:
        partes.append("Ainda não analisei nenhum quadro")
    if antes_itens:
        partes.append("Antes eu vi " + _lista([i.falado(cena.em) for i in antes_itens[:3]]))
    if cena.regioes_sem_observacao:
        partes.append("Não observei " + _lista(cena.regioes_sem_observacao)
                      + " — sem observação não quer dizer vazio")
    if not cena.regua_calibrada:
        partes.append("Sem régua calibrada eu não dou centímetro de nada")
    return ". ".join(partes) + f", {tratamento}."


def consultar(cena: Cena, pergunta: str, tratamento: str = "Senhor") -> str:
    """"o que está à esquerda?", "o que você não viu?", "o que tem no centro?"."""
    import re
    import unicodedata
    n = unicodedata.normalize("NFKD", (pergunta or "").lower())
    n = "".join(c for c in n if not unicodedata.combining(c))

    if re.search(r"\bnao (?:viu|observou|olhou)\b|\bo que falta olhar\b|\bnao observad\w*\b", n):
        if not cena.camera_ligada:
            return f"Com a câmera desligada, {tratamento}, eu não observei nada."
        if not cena.regioes_sem_observacao:
            return (f"Olhei as três regiões do quadro, {tratamento} — o que está fora do "
                    f"enquadramento da câmera continua desconhecido, e coisas que o meu "
                    f"detector não conhece podem ter passado batido.")
        return (f"Não observei {_lista(cena.regioes_sem_observacao)}, {tratamento}, "
                f"e o que está fora do enquadramento da câmera também é desconhecido.")

    for regiao in REGIOES:
        if re.search(rf"\b{regiao}\b", n):
            if not cena.camera_ligada:
                return f"A câmera está desligada, {tratamento}."
            itens = [i for i in cena.na_regiao(regiao) if i.estado == OBSERVADO]
            if itens:
                return (f"{_lista([i.nome for i in itens])} "
                        f"{'está' if len(itens) == 1 else 'estão'} {itens[0]._onde()}, {tratamento}.")
            antes = [i for i in cena.na_regiao(regiao) if i.estado == ULTIMA_VEZ]
            if antes:
                return (f"Agora não vejo nada {antes[0]._onde()}, {tratamento}. "
                        f"Antes eu vi {_lista([i.falado(cena.em) for i in antes[:2]])}.")
            onde = ItemCena('', regiao, OBSERVADO, 0)._onde()
            if cena.detector_rodou:
                return (f"Olhei {onde} e não reconheci nada, {tratamento} — pode haver coisa "
                        f"que eu não sei nomear.")
            return (f"Não estou observando nada {onde}, {tratamento} — isso não quer dizer "
                    f"que esteja vazio.")
    return falar(cena, tratamento)
