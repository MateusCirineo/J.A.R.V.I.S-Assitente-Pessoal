"""As coisas do Senhor: o carregador dele, a impressora dele, aquele componente.

Diferente do detector (que sabe dizer "um carregador") e da identificação fina
(que sabe dizer "provavelmente um Anker 65 W"), aqui ficam os objetos que o
Senhor mandou cadastrar, com nome, apelido, manual e o que já foi confirmado.

Duas separações que o prompt mestre (§9) cobra e que são fáceis de errar:

1. **Modelo de produto × unidade física.** "Epson L3250" é um modelo; "a
   impressora da minha mesa" é uma unidade. Dois objetos iguais não podem virar
   a mesma identidade pessoal só porque parecem iguais.
2. **Última observação × estado atual.** "Vi às 14h12, à esquerda da mesa" não é
   "está lá agora". Quem guarda onde as coisas estavam é o rastreador; aqui fica
   só o registro, sempre com hora.

Nada de foto por padrão: o cadastro guarda texto. Foto só se o Senhor mandar,
e continua apagável.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
ARQ = HOME / "hud-inventario.json"

MODELO = "modelo"        # um produto: "Epson L3250"
UNIDADE = "unidade"      # uma coisa do Senhor: "a impressora da minha mesa"


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def texto_contem(texto: str, valor: str) -> bool:
    """Identificação inteira, sem confundir S23 com S23+ nem L325 com L3250."""
    texto, valor = _norm(texto), _norm(valor)
    return bool(valor) and bool(re.search(r"(?<![\w+/-])" + re.escape(valor) + r"(?![\w+/-])", texto))


@dataclass
class Observacao:
    """Onde e quando eu vi. NUNCA quer dizer "está lá agora"."""
    em: float
    onde: str = ""                 # "à esquerda", "no centro"
    trilha: str = ""               # id temporário do rastreador naquele momento
    fonte: str = "camera"


@dataclass
class Objeto:
    id: str
    nome: str
    categoria: str = ""
    tipo_registro: str = UNIDADE
    apelidos: list[str] = field(default_factory=list)
    fabricante: str = ""
    modelo: str = ""
    modelo_de: str = ""            # id do registro de MODELO, quando esta unidade tem um
    atributos: dict[str, str] = field(default_factory=dict)   # {"capacidade": "65 W"}
    confirmados: list[str] = field(default_factory=list)      # quais atributos o Senhor confirmou
    manual: str = ""               # caminho ou endereço
    projeto: str = ""
    foto: str = ""                 # só se o Senhor mandar guardar
    observacoes: list[Observacao] = field(default_factory=list)
    criado_em: float = 0.0
    mexido_em: float = 0.0

    @property
    def e_modelo(self) -> bool:
        return self.tipo_registro == MODELO

    def ultima(self) -> Observacao | None:
        return self.observacoes[-1] if self.observacoes else None

    def chamado(self) -> list[str]:
        return [self.nome, *self.apelidos]


class Inventario:
    def __init__(self, arquivo: Path | str | None = None) -> None:
        self._arq = Path(arquivo) if arquivo else ARQ
        self._trava = threading.RLock()
        self._objetos: dict[str, Objeto] = {}
        self._carregar()

    # ---- disco ----------------------------------------------------------
    def _carregar(self) -> None:
        try:
            d = json.loads(self._arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for bruto in d.get("objetos", []):
            try:
                obs = [Observacao(**o) for o in bruto.pop("observacoes", [])]
                self._objetos[bruto["id"]] = Objeto(observacoes=obs, **bruto)
            except (TypeError, KeyError):
                continue

    def salvar(self) -> None:
        with self._trava:
            dados = {"objetos": [asdict(o) for o in self._objetos.values()], "em": time.time()}
            self._arq.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._arq.with_suffix(".tmp")
            tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self._arq)

    # ---- cadastrar ------------------------------------------------------
    def cadastrar(self, nome: str, *, categoria: str = "", tipo_registro: str = UNIDADE,
                  fabricante: str = "", modelo: str = "", modelo_de: str = "",
                  apelidos: Iterable[str] = (), atributos: dict[str, str] | None = None,
                  manual: str = "", projeto: str = "") -> Objeto:
        agora = time.time()
        if not nome.strip() or tipo_registro not in (MODELO, UNIDADE):
            raise ValueError("nome ou tipo de cadastro inválido")
        with self._trava:
            oid = f"o{int(agora * 1000) % 10_000_000}"
            while oid in self._objetos:
                oid += "a"
            o = Objeto(id=oid, nome=nome.strip(), categoria=categoria, tipo_registro=tipo_registro,
                       fabricante=fabricante, modelo=modelo, modelo_de=modelo_de,
                       apelidos=[a.strip() for a in apelidos if a.strip()],
                       atributos=dict(atributos or {}), manual=manual, projeto=projeto,
                       criado_em=agora, mexido_em=agora)
            self._objetos[oid] = o
        self.salvar()
        return o

    def modelo_de_produto(self, nome: str, *, fabricante: str = "", modelo: str = "",
                          atributos: dict[str, str] | None = None, manual: str = "") -> Objeto:
        """Registro do PRODUTO (serve para várias unidades iguais)."""
        achado = next((o for o in self.todos(tipo=MODELO) if _norm(o.nome) == _norm(nome)), None)
        if achado is not None:
            return achado
        return self.cadastrar(nome, tipo_registro=MODELO, fabricante=fabricante, modelo=modelo,
                              atributos=atributos, manual=manual)

    # ---- achar ----------------------------------------------------------
    def obter(self, oid: str) -> Objeto | None:
        return self._objetos.get(oid)

    def achar(self, texto: str, tipo: str | None = None) -> Objeto | None:
        alvo = _norm(texto)
        if not alvo:
            return None
        candidatos = [o for o in self._objetos.values() if tipo is None or o.tipo_registro == tipo]
        exatos = [o for o in candidatos if any(_norm(n) == alvo for n in o.chamado())]
        if exatos:
            return exatos[0] if len(exatos) == 1 else None
        parciais = [o for o in candidatos if any(_norm(n) and (_norm(n) in alvo or alvo in _norm(n))
                                                 for n in o.chamado())]
        return parciais[0] if len(parciais) == 1 else None

    def parecidos(self, categoria: str) -> list[Objeto]:
        """Unidades da mesma categoria: é aqui que "dois iguais" aparece."""
        alvo = _norm(categoria)
        return [o for o in self._objetos.values()
                if not o.e_modelo and _norm(o.categoria) == alvo]

    def referencias_visuais(self, texto: str) -> list[Objeto]:
        """Todos os produtos compatíveis; nunca associa uma unidade física.

        Marca isolada não distingue modelos, mas mantém todos como candidatos.
        Apelidos pessoais não são identificação impressa em um produto.
        """
        with self._trava:
            return [o for o in self._objetos.values()
                    if texto_contem(texto, o.modelo) or texto_contem(texto, o.fabricante)]

    def do_modelo(self, oid_modelo: str) -> list[Objeto]:
        return [o for o in self._objetos.values() if o.modelo_de == oid_modelo]

    def todos(self, tipo: str | None = None) -> list[Objeto]:
        itens = [o for o in self._objetos.values() if tipo is None or o.tipo_registro == tipo]
        return sorted(itens, key=lambda o: -o.mexido_em)

    # ---- mexer ----------------------------------------------------------
    def confirmar(self, oid: str, atributo: str, valor: str) -> Objeto | None:
        """O Senhor disse que é assim: isso vira confirmado, não palpite."""
        with self._trava:
            o = self._objetos.get(oid)
            if o is None:
                return None
            o.atributos[atributo] = valor
            if atributo not in o.confirmados:
                o.confirmados.append(atributo)
            if atributo == "modelo":
                o.modelo = valor
            elif atributo in ("marca", "fabricante"):
                o.fabricante = valor
            o.mexido_em = time.time()
        self.salvar()
        return o

    def corrigir(self, oid: str, atributo: str, valor: str) -> Objeto | None:
        return self.confirmar(oid, atributo, valor)

    def observar(self, oid: str, onde: str = "", trilha: str = "", fonte: str = "camera") -> Observacao | None:
        with self._trava:
            o = self._objetos.get(oid)
            if o is None:
                return None
            obs = Observacao(em=time.time(), onde=onde, trilha=trilha, fonte=fonte)
            o.observacoes.append(obs)
            del o.observacoes[:-30]
            o.mexido_em = obs.em
        self.salvar()
        return obs

    def apelidar(self, oid: str, apelido: str) -> Objeto | None:
        with self._trava:
            o = self._objetos.get(oid)
            if o is None or not apelido.strip():
                return None
            if _norm(apelido) not in {_norm(a) for a in o.chamado()}:
                o.apelidos.append(apelido.strip())
                o.mexido_em = time.time()
        self.salvar()
        return o

    def esquecer(self, oid: str) -> bool:
        with self._trava:
            saiu = self._objetos.pop(oid, None) is not None
        if saiu:
            self.salvar()
        return saiu


# ---- como o Jarvis fala disso -------------------------------------------
def falar_objeto(o: Objeto, agora: float | None = None, tratamento: str = "Senhor") -> str:
    import datetime
    agora = agora if agora is not None else time.time()
    partes = [o.nome]
    if o.categoria and _norm(o.categoria) != _norm(o.nome):
        partes[0] = f"{o.nome} ({o.categoria})"
    ficha = []
    def com_fonte(nome, valor, chaves):
        fonte = "o senhor confirmou" if any(c in o.confirmados for c in chaves) else "não confirmado por você"
        return f"{nome} {valor} ({fonte})"
    if o.fabricante:
        ficha.append(com_fonte("marca", o.fabricante, ("marca", "fabricante")))
    if o.modelo:
        ficha.append(com_fonte("modelo", o.modelo, ("modelo",)))
    for nome, valor in list(o.atributos.items())[:3]:
        if nome not in ("marca", "modelo"):
            ficha.append(com_fonte(nome, valor, (nome,)))
    if ficha:
        partes.append(", ".join(ficha))
    if o.manual:
        partes.append("tenho o manual vinculado no cadastro; acesso não verificado")
    ultima = o.ultima()
    if ultima:
        quando = datetime.datetime.fromtimestamp(ultima.em)
        faz = agora - ultima.em
        quanto = ("agora há pouco" if faz < 120 else
                  f"há {int(faz // 60)} minutos" if faz < 3600 else f"às {quando:%H:%M}")
        onde = f" {ultima.onde}" if ultima.onde else ""
        partes.append(f"vi por último {quanto}{onde} — não sei se ainda está lá")
    return ". ".join(partes) + "."


def falar_lista(objetos: list[Objeto], tratamento: str = "Senhor") -> str:
    if not objetos:
        return f"Ainda não cadastrei nenhum objeto seu, {tratamento}. Diga: cadastre esta impressora."
    nomes = [o.nome for o in objetos[:6]]
    lista = nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
    return f"Conheço {len(objetos)} objeto{'s' if len(objetos) > 1 else ''} seu{'s' if len(objetos) > 1 else ''}, {tratamento}: {lista}."
