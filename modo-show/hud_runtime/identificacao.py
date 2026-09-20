"""De "é um carro" para "é um Civic" -- só até onde a evidência deixa.

O prompt mestre (§8) pede a sequência: selecionar o alvo, avaliar se dá para
ver, classificar a categoria, extrair pistas (logotipo, texto, etiqueta),
consultar referências, comparar candidatos, pedir mais evidência quando falta e
só então responder separando o que é certo do que é palpite.

Aqui ficam as REGRAS dessa decisão, sem câmera nem rede -- por isso dá para
testar de verdade. Quem tira a foto é camera.py; quem lê a imagem é visao.py;
quem guarda os objetos do Senhor é inventario.py.

O que este módulo não faz, de propósito:

- não transforma nota de detector em porcentagem de certeza de marca;
- não completa letra ilegível ("SAM…" não vira "Samsung" sozinho);
- não escolhe o primeiro resultado de busca como confirmação;
- não infere dono, preço ou histórico pela aparência.
"""

from __future__ import annotations

import time
import math
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

# estados de evidência de cada atributo, do mais forte ao mais fraco
CONFIRMADO = "confirmado"        # li a identificação (texto/etiqueta/código) e ela bate
COMPATIVEL = "compativel"        # a referência consultada é compatível com o que vejo
PROVAVEL = "provavel"            # pista parcial (logotipo cortado, formato típico)
CONFLITANTE = "conflitante"      # duas evidências discordam
NAO_DETERMINADO = "nao_determinado"

_FALADO = {
    CONFIRMADO: "confirmado",
    COMPATIVEL: "compatível com a referência",
    PROVAVEL: "provável",
    CONFLITANTE: "conflitante",
    NAO_DETERMINADO: "não determinado",
}

# qualidade mínima da região para eu me arriscar a falar de marca/modelo
MIN_LADO_PX = 96                 # menor que isto, texto pequeno não se lê
MIN_NITIDEZ = 60.0               # variância do laplaciano
MIN_BRILHO, MAX_BRILHO = 35, 225
BORDA = 0.02                     # a caixa encostando na borda = objeto cortado


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


@dataclass
class Atributo:
    """Um pedaço da identificação, com o estado da evidência ao lado."""
    nome: str                      # "marca", "modelo", "ano", "capacidade"
    valor: str | None
    estado: str = NAO_DETERMINADO
    fonte: str = ""                # "texto lido na etiqueta", "catálogo local", "inventário"
    em: float = field(default_factory=time.time)

    def falado(self) -> str:
        if self.valor is None or self.estado == NAO_DETERMINADO:
            return f"{self.nome}: não determinado"
        return f"{self.nome}: {self.valor} ({_FALADO.get(self.estado, self.estado)})"


@dataclass
class Candidato:
    """Uma hipótese de produto, com o que bate e o que não bate."""
    nome: str
    concordam: list[str] = field(default_factory=list)
    conflitam: list[str] = field(default_factory=list)
    fonte: str = ""

    @property
    def nota(self) -> int:
        """Quantas evidências a favor menos as contra. NÃO é porcentagem de certeza."""
        return len(self.concordam) - 2 * len(self.conflitam)


@dataclass
class Qualidade:
    """A região dá para identificar? Se não, eu digo o que atrapalha."""
    lado_px: int = 0
    nitidez: float = 0.0
    brilho: float = 0.0
    cortado: bool = False
    problemas: list[str] = field(default_factory=list)

    @property
    def boa(self) -> bool:
        return not self.problemas


def avaliar_regiao(img_bgr: Any, caixa: tuple[float, float, float, float] | None = None) -> Qualidade:
    """Nitidez, luz, tamanho e corte da região (frações do quadro)."""
    import cv2
    import numpy as np
    altura, largura = img_bgr.shape[:2]
    if caixa is None:
        x, y, w, h = 0.0, 0.0, 1.0, 1.0
    else:
        x, y, w, h = caixa
    if not all(math.isfinite(v) for v in (x, y, w, h)) or w <= 0 or h <= 0:
        return Qualidade(problemas=["a região selecionada é inválida"])
    x0, y0 = max(0, int(x * largura)), max(0, int(y * altura))
    x1, y1 = min(largura, int((x + w) * largura)), min(altura, int((y + h) * altura))
    recorte = img_bgr[y0:y1, x0:x1]
    q = Qualidade()
    if recorte.size == 0:
        q.problemas.append("a região ficou vazia")
        return q
    cinza = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    q.lado_px = int(min(cinza.shape[:2]))
    q.nitidez = float(cv2.Laplacian(cinza, cv2.CV_64F).var())
    q.brilho = float(np.mean(cinza))
    q.cortado = bool(caixa and (x <= BORDA or y <= BORDA or x + w >= 1 - BORDA or y + h >= 1 - BORDA))
    if q.lado_px < MIN_LADO_PX:
        q.problemas.append("o objeto está pequeno demais na imagem")
    if q.nitidez < MIN_NITIDEZ:
        q.problemas.append("a imagem está tremida ou fora de foco")
    if q.brilho < MIN_BRILHO:
        q.problemas.append("está escuro")
    elif q.brilho > MAX_BRILHO:
        q.problemas.append("está estourado de luz")
    if q.cortado:
        q.problemas.append("o objeto está cortado pela borda")
    return q


def pistas_de_texto(texto_lido: str) -> dict[str, str]:
    """Separa o que foi REALMENTE lido: texto legível e trechos cortados.

    "SAM… Galaxy S23" -> {"legivel": "Galaxy S23", "parcial": "SAM…"}
    Nada aqui completa palavra: parcial continua parcial.
    """
    legivel, parcial = [], []
    for pedaco in (texto_lido or "").replace("\n", " ").split():
        limpo = pedaco.strip(" ,;:")
        if not limpo:
            continue
        if "…" in limpo or "..." in limpo or limpo.endswith("-"):
            parcial.append(limpo)
        else:
            legivel.append(limpo.strip("."))
    return {"legivel": " ".join(legivel), "parcial": " ".join(parcial)}


class Identificacao:
    """Junta categoria, pistas e referências numa resposta honesta."""

    def __init__(self, categoria: str | None = None, qualidade: Qualidade | None = None) -> None:
        self.categoria = categoria
        self.qualidade = qualidade or Qualidade(lado_px=MIN_LADO_PX, nitidez=MIN_NITIDEZ + 1,
                                                brilho=128)
        self.atributos: dict[str, Atributo] = {}
        self.candidatos: list[Candidato] = []
        self.evidencias: list[str] = []        # o que eu de fato olhei/consultei
        self.em = time.time()

    # ---- montar ---------------------------------------------------------
    def anotar(self, nome: str, valor: str | None, estado: str, fonte: str) -> Atributo:
        antigo = self.atributos.get(nome)
        if antigo is not None and antigo.valor and valor and _norm(antigo.valor) != _norm(valor):
            # duas evidências dizendo coisas diferentes: isso é conflito, não "a mais nova ganha"
            estado, valor = CONFLITANTE, f"{antigo.valor} ou {valor}"
            fonte = f"{antigo.fonte}; {fonte}"
        a = Atributo(nome=nome, valor=valor, estado=estado, fonte=fonte)
        self.atributos[nome] = a
        return a

    def candidato(self, nome: str, concordam: Iterable[str] = (), conflitam: Iterable[str] = (),
                  fonte: str = "") -> Candidato:
        c = Candidato(nome=nome, concordam=list(concordam), conflitam=list(conflitam), fonte=fonte)
        self.candidatos.append(c)
        return c

    def evidencia(self, texto: str) -> None:
        if texto and texto not in self.evidencias:
            self.evidencias.append(texto)

    def comparar_inventario(self, texto_lido: str, inventario: Any) -> None:
        """Compara a identificação lida, atributo por atributo, ao cadastro.

        O texto continua sendo uma leitura do modelo visual, não OCR validado
        nem autenticação de unidade. Um manual apenas vinculado não foi lido.
        """
        from .inventario import texto_contem
        referencias = inventario.referencias_visuais(texto_lido)
        produtos: dict[tuple[str, str], Any] = {}
        for objeto in referencias:
            chave = (_norm(objeto.fabricante), _norm(objeto.modelo))
            produtos.setdefault(chave, objeto)
        exatos = [o for o in produtos.values() if texto_contem(texto_lido, o.modelo)]
        candidatos = exatos or list(produtos.values())
        for objeto in candidatos:
            concordam = [f"{campo} lido: {valor}" for campo, valor in
                         (("marca", objeto.fabricante), ("modelo", objeto.modelo))
                         if texto_contem(texto_lido, valor)]
            self.candidato(" ".join(filter(None, (objeto.fabricante, objeto.modelo))) or objeto.nome,
                           concordam=concordam, fonte=f"inventário: {objeto.id}")
        if len(exatos) != 1:
            if not candidatos and texto_lido:
                self.candidato(texto_lido, concordam=["texto lido pelo modelo visual"],
                               fonte="imagem; sem referência consultada")
            return
        objeto = exatos[0]
        self.evidencia(f"referência de produto no inventário: {objeto.id} ({objeto.nome})")
        for campo, valor in (("marca", objeto.fabricante), ("modelo", objeto.modelo)):
            if valor:
                lido = texto_contem(texto_lido, valor)
                self.anotar(campo, valor, CONFIRMADO if lido else COMPATIVEL,
                            "identificação lida pelo modelo visual e cadastro" if lido else "cadastro; não lido na imagem")
        for nome, valor in objeto.atributos.items():
            if nome not in ("marca", "fabricante", "modelo"):
                self.anotar(nome, valor, COMPATIVEL, "especificação do cadastro; não medida pela câmera")
        if objeto.manual:
            self.evidencia(f"manual vinculado, não consultado nesta análise: {objeto.manual}")
        self.anotar("unidade_fisica", None, NAO_DETERMINADO,
                    "modelo de produto não identifica a unidade; associação exige confirmação")

    # ---- decidir --------------------------------------------------------
    def melhores(self) -> list[Candidato]:
        if not self.candidatos:
            return []
        vivos = [c for c in self.candidatos if c.nota > 0] or self.candidatos
        ordenados = sorted(vivos, key=lambda c: -c.nota)
        topo = ordenados[0].nota
        return [c for c in ordenados if c.nota == topo]

    @property
    def ambiguo(self) -> bool:
        """Dois candidatos igualmente compatíveis continuam ambíguos (T10)."""
        return len(self.melhores()) > 1

    def falta(self) -> str | None:
        """O que pedir ao Senhor para sair do palpite."""
        if not self.qualidade.boa:
            problema = self.qualidade.problemas[0]
            return ("chegue mais perto" if "pequeno" in problema else
                    "segure firme e espere focar" if "tremida" in problema else
                    "acenda uma luz" if "escuro" in problema else
                    "tire o reflexo" if "estourado" in problema else
                    "mostre o objeto inteiro")
        if self.ambiguo:
            return "mostre a etiqueta ou a parte de trás, onde fica o modelo"
        marca = self.atributos.get("marca")
        modelo = self.atributos.get("modelo")
        if modelo is None or modelo.estado != CONFIRMADO:
            if marca is not None and marca.estado != NAO_DETERMINADO:
                return "mostre onde está escrito o modelo"
            return "mostre o logotipo ou a etiqueta"
        return None

    # ---- falar ----------------------------------------------------------
    def frase(self, tratamento: str = "Senhor") -> str:
        """Categoria confirmada, marca provável, modelo confirmado e o que falta."""
        partes: list[str] = []
        if self.categoria:
            partes.append(f"É {self.categoria}")
        else:
            partes.append("Não consegui nem dizer a categoria")
        if not self.qualidade.boa:
            partes.append("mas " + " e ".join(self.qualidade.problemas))
            pedido = self.falta()
            frase = ", ".join(partes) + f", {tratamento}."
            return frase + (f" Se {pedido}, eu tento de novo." if pedido else "")

        for nome in ("marca", "modelo", "ano", "versao", "capacidade"):
            a = self.atributos.get(nome)
            if a is None or a.valor is None:
                continue
            if a.estado == CONFIRMADO:
                partes.append(f"{nome} {a.valor}, confirmado por {a.fonte}")
            elif a.estado == COMPATIVEL:
                partes.append(f"{nome} {a.valor}, compatível com {a.fonte}")
            elif a.estado == PROVAVEL:
                partes.append(f"a {nome} parece {a.valor}, mas não posso confirmar")
            elif a.estado == CONFLITANTE:
                partes.append(f"a {nome} está conflitante: {a.valor}")

        melhores = self.melhores()
        if self.ambiguo:
            partes.append("há " + ("dois" if len(melhores) == 2 else str(len(melhores)))
                          + " candidatos igualmente compatíveis: " + ", ".join(c.nome for c in melhores))
        elif melhores and "modelo" not in self.atributos:
            partes.append(f"o mais compatível é {melhores[0].nome}")

        nao_sei = [n for n in ("marca", "modelo", "ano") if n not in self.atributos]
        if nao_sei:
            partes.append("não determinei " + (" nem ".join(nao_sei)))

        frase = ", ".join(partes) + f", {tratamento}."
        pedido = self.falta()
        return frase + (f" Se {pedido}, eu comparo melhor." if pedido else "")

    def cartao(self) -> dict[str, Any]:
        """Para o HUD: cada atributo com o estado da evidência, sem porcentagem inventada."""
        return {
            "categoria": self.categoria,
            "qualidade": asdict(self.qualidade),
            "atributos": [asdict(a) | {"estado_falado": _FALADO.get(a.estado, a.estado)}
                          for a in self.atributos.values()],
            # O HUD precisa mostrar também por que um candidato foi descartado.
            "candidatos": [asdict(c) for c in self.candidatos],
            "evidencias": list(self.evidencias),
            "proximo_passo": self.falta(),
            "em": self.em,
        }
