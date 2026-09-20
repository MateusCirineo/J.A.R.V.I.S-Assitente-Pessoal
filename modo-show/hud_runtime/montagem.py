"""Montagens: uma peça feita de peças, e a vista explodida delas.

F20 do prompt mestre, com o limite que ele mesmo impõe: **vista explodida exige
conhecer os componentes**. Então só separo o que foi montado aqui, componente a
componente. De um STL que chegou pronto, ou de um objeto que a câmera viu, eu
não invento o que tem por dentro -- eu digo que não sei.

Cada componente guarda o seu tipo, os seus parâmetros e onde ele fica na
montagem. A malha sai da mesma `cad.py` das peças soltas: nada de geometria
paralela.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

FOLGA_EXPLOSAO_MM = 12.0        # espaço entre as peças na vista explodida


@dataclass
class Componente:
    nome: str
    tipo: str                             # caixa, cilindro, tubo, engrenagem...
    parametros: dict[str, float]
    deslocamento: tuple[float, float, float] = (0.0, 0.0, 0.0)   # onde fica na montagem (mm)
    material: str = ""

    def altura(self) -> float:
        p = self.parametros
        return float(p.get("a") or p.get("altura") or p.get("espessura") or 1.0)


@dataclass
class Montagem:
    nome: str
    componentes: list[Componente] = field(default_factory=list)
    projeto: str = ""
    criada_em: float = field(default_factory=time.time)
    mexida_em: float = field(default_factory=time.time)

    def achar(self, texto: str) -> Componente | None:
        from .pecas import _norm
        alvo = _norm(texto)
        if not alvo:
            return None
        for c in self.componentes:
            if _norm(c.nome) == alvo:
                return c
        for c in self.componentes:
            n = _norm(c.nome)
            if n and (n in alvo or alvo in n):
                return c
        return None


def malha(m: Montagem, explodir: float = 0.0) -> list[tuple]:
    """Triângulos da montagem inteira. `explodir` afasta as peças no eixo Z.

    explodir = 0 é a montagem fechada; 1 separa com a folga padrão.
    """
    from .engenharia import gerar_peca
    saida: list[tuple] = []
    altura_acumulada = 0.0
    for i, c in enumerate(m.componentes):
        tris, _nome, _desc = gerar_peca(c.tipo, c.parametros)
        dx, dy, dz = c.deslocamento
        dz += explodir * (altura_acumulada + i * FOLGA_EXPLOSAO_MM)
        if (dx, dy, dz) != (0.0, 0.0, 0.0):
            tris = [tuple((x + dx, y + dy, z + dz) for (x, y, z) in tri) for tri in tris]
        saida.extend(tris)
        altura_acumulada += c.altura()
    return saida


def volume_mm3(m: Montagem) -> float:
    from .cad import volume_mm3 as volume
    return sum(abs(volume(malha(Montagem(nome=c.nome, componentes=[c])))) for c in m.componentes)


def caixa_com_tampa(c: float, l: float, a: float, parede: float = 2.0,
                    tampa: float = 2.0) -> Montagem:
    """A montagem que eu sei fazer sozinho: caixa aberta + tampa que encaixa."""
    corpo = Componente(nome="corpo", tipo="caixa",
                       parametros={"c": c, "l": l, "a": a, "parede": parede})
    tampa_c = Componente(nome="tampa", tipo="caixa",
                         parametros={"c": c, "l": l, "a": tampa, "parede": 0},
                         deslocamento=(0.0, 0.0, a))
    return Montagem(nome="caixa com tampa", componentes=[corpo, tampa_c])


def falar_componentes(m: Montagem, tratamento: str = "Senhor") -> str:
    if not m.componentes:
        return f"{m.nome} não tem componentes cadastrados, {tratamento}."
    itens = []
    for c in m.componentes:
        medidas = ", ".join(f"{k} {v:g}" for k, v in c.parametros.items() if v)
        itens.append(f"{c.nome} ({c.tipo}: {medidas})")
    return (f"{m.nome} tem {len(m.componentes)} peça{'s' if len(m.componentes) > 1 else ''}, "
            f"{tratamento}: " + "; ".join(itens) + ".")


def falar_explosao(m: Montagem, tratamento: str = "Senhor") -> str:
    return (f"Separei as {len(m.componentes)} peças de {m.nome} na mesa, {tratamento}. "
            f"São as peças que eu mesmo montei; de um objeto que eu não montei, "
            f"não sei o que tem por dentro.")


def recusa_de_explosao(o_que: str, tratamento: str = "Senhor") -> str:
    """Quando pedem para explodir o que eu não montei (§12: não invento peças)."""
    return (f"Não sei as peças de {o_que}, {tratamento}. Só consigo separar montagens que eu "
            f"mesmo fiz, como a caixa com tampa. De um arquivo pronto ou de um objeto da câmera, "
            f"eu não invento o que tem por dentro.")
