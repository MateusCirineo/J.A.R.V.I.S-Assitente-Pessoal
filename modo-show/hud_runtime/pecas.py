"""Peças com parâmetros e versões -- não só um STL solto.

Antes disto o Jarvis gerava a malha, salvava o arquivo e esquecia tudo: não dava
para dizer "aumente dois milímetros" nem "volte para a de ontem", porque a peça
não existia em lugar nenhum depois de salva. Aqui ficam os parâmetros de origem,
cada versão e o que foi medido de fato (§12 do prompt mestre de 19/09).

Três regras:

1. **Alterar não apaga.** Cada mudança cria uma versão nova; a anterior continua
   no disco e dá para voltar.
2. **O que eu digo foi medido.** O volume sai da malha gerada, não de uma conta
   de guardanapo. Se eu não conferi, eu digo que não conferi.
3. **STL salvo não é peça pronta para imprimir.** A validação aqui vê unidades,
   valores impossíveis, relações entre dimensões e espessura mínima -- e só.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
ARQ = HOME / "hud-pecas.json"

# bico comum de 0,4 mm: abaixo de 0,8 a parede sai com um perimetro so e quebra
PAREDE_MINIMA_MM = 0.8
MAIOR_MM = 300.0            # mesa da maioria das impressoras caseiras

# como o Senhor fala cada dimensao, por tipo de peca
DIMENSOES: dict[str, dict[str, str]] = {
    "caixa": {"comprimento": "c", "largura": "l", "altura": "a", "parede": "parede",
              "espessura": "parede", "profundidade": "l"},
    "cilindro": {"diametro": "diametro", "altura": "altura"},
    "tubo": {"externo": "externo", "interno": "interno", "altura": "altura",
             "diametro externo": "externo", "diametro interno": "interno", "furo": "interno"},
    "esfera": {"diametro": "diametro"},
    "cone": {"diametro": "diametro", "altura": "altura", "base": "diametro"},
    "engrenagem": {"dentes": "dentes", "externo": "externo", "diametro": "externo",
                   "espessura": "espessura", "furo": "furo"},
    # montagem que o Jarvis sabe fazer inteira (ver montagem.py): da para explodir
    "caixa_com_tampa": {"comprimento": "c", "largura": "l", "altura": "a", "parede": "parede",
                        "tampa": "tampa", "espessura da tampa": "tampa", "profundidade": "l"},
}
MONTAGENS = ("caixa_com_tampa",)      # tipos com componentes conhecidos (F20)
NOME_FALADO = {"c": "comprimento", "l": "largura", "a": "altura", "parede": "parede",
               "diametro": "diâmetro", "altura": "altura", "externo": "diâmetro externo",
               "interno": "diâmetro interno", "dentes": "dentes", "espessura": "espessura",
               "furo": "furo"}


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def dimensao_citada(tipo: str, frase: str) -> str | None:
    """"aumente a largura" -> "l". Devolve None quando ele não disse qual."""
    n = _norm(frase)
    mapa = DIMENSOES.get(tipo, {})
    # nome mais longo primeiro: "diametro externo" ganha de "diametro"
    for falado in sorted(mapa, key=len, reverse=True):
        if _norm(falado) in n:
            return mapa[falado]
    return None


def dimensoes_do_tipo(tipo: str) -> list[str]:
    """Nomes falados, sem repetir o mesmo parâmetro (para perguntar ao Senhor)."""
    vistos: dict[str, str] = {}
    for falado, chave in DIMENSOES.get(tipo, {}).items():
        vistos.setdefault(chave, falado)
    return list(vistos.values())


@dataclass
class Versao:
    numero: int
    parametros: dict[str, float]
    arquivo: str = ""
    volume_mm3: float = 0.0          # medido na malha gerada, nao estimado
    triangulos: int = 0
    motivo: str = ""                 # o que mudou nesta versao
    em: float = 0.0
    material: str | None = None
    cor: str | None = None


@dataclass
class Peca:
    nome: str
    tipo: str
    parametros: dict[str, float]
    projeto: str = ""
    material: str = "PLA"
    versoes: list[Versao] = field(default_factory=list)
    criada_em: float = 0.0
    mexida_em: float = 0.0
    cor: str = "#26c6da"

    @property
    def versao(self) -> int:
        return self.versoes[-1].numero if self.versoes else 0

    def atual(self) -> Versao | None:
        return self.versoes[-1] if self.versoes else None


def validar(tipo: str, p: dict[str, float]) -> tuple[list[str], list[str]]:
    """(erros que impedem, avisos que só alertam). Só o que dá para conferir de fato."""
    erros: list[str] = []
    avisos: list[str] = []
    obrigatorios = {
        "caixa": {"c", "l", "a", "parede"}, "caixa_com_tampa": {"c", "l", "a", "parede", "tampa"},
        "cilindro": {"diametro", "altura"}, "esfera": {"diametro"}, "cone": {"diametro", "altura"},
        "tubo": {"externo", "interno", "altura"}, "engrenagem": {"dentes", "externo", "espessura", "furo"},
    }
    if tipo not in obrigatorios:
        return ["tipo de peça desconhecido"], []
    faltantes = obrigatorios[tipo] - p.keys()
    if faltantes:
        return ["faltam parâmetros: " + ", ".join(sorted(faltantes))], []
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in p.values()):
        return ["parâmetros precisam ser números finitos"], []
    extras = p.keys() - obrigatorios[tipo]
    if extras:
        return ["parâmetros desconhecidos: " + ", ".join(sorted(extras))], []
    for chave, valor in p.items():
        if chave in ("parede", "furo") and valor == 0:
            continue                                  # 0 = maciça, é opção
        if valor <= 0:
            erros.append(f"{NOME_FALADO.get(chave, chave)} não pode ser {valor:g}")
        elif valor > MAIOR_MM and chave != "dentes":
            avisos.append(f"{NOME_FALADO.get(chave, chave)} de {valor:g} mm não cabe na mesa da impressora")
    if tipo == "tubo" and p.get("interno", 0) >= p.get("externo", 0):
        erros.append("o diâmetro interno precisa ser menor que o externo")
    if tipo == "engrenagem":
        if p["dentes"] != int(p["dentes"]):
            erros.append("o número de dentes precisa ser inteiro")
        if p.get("dentes", 0) < 6:
            erros.append("uma engrenagem precisa de pelo menos 6 dentes")
        if p.get("furo", 0) >= p.get("externo", 0) * 0.8:
            erros.append("o furo está grande demais para o diâmetro da engrenagem")
    if tipo == "caixa_com_tampa":
        if (p.get("tampa") or 0) <= 0:
            erros.append("a tampa precisa de uma espessura maior que zero")
        elif p.get("tampa", 0) >= p.get("a", 0):
            erros.append("a tampa ficaria mais alta que a própria caixa")
    if tipo in ("caixa", "caixa_com_tampa"):
        parede = p.get("parede") or 0
        if parede:
            menor = min(p.get("c", 0), p.get("l", 0), p.get("a", 0))
            if parede * 2 >= menor:
                erros.append("a parede não cabe: seria maior que metade da menor dimensão")
            elif parede < PAREDE_MINIMA_MM:
                avisos.append(f"parede de {parede:g} mm é fina para um bico de 0,4; "
                              f"abaixo de {PAREDE_MINIMA_MM:g} costuma quebrar")
    return erros, avisos


class Pecas:
    """Peças do Senhor, com histórico. Uma instância por runtime."""

    def __init__(self, arquivo: Path | str | None = None, pasta: Path | None = None) -> None:
        self._arq = Path(arquivo) if arquivo else ARQ
        self._pasta = pasta
        self._trava = threading.RLock()
        self._pecas: dict[str, Peca] = {}
        self._ativa: str | None = None
        self._focos: dict[str, str] = {}
        self._carregar()

    # ---- disco ----------------------------------------------------------
    def _carregar(self) -> None:
        try:
            d = json.loads(self._arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for bruta in d.get("pecas", []):
            try:
                versoes = [Versao(**v) for v in bruta.pop("versoes", [])]
                self._pecas[_norm(bruta["nome"])] = Peca(versoes=versoes, **bruta)
            except (TypeError, KeyError):
                continue
        self._ativa = d.get("ativa")
        self._focos = {str(projeto): chave for projeto, chave in d.get("focos", {}).items()
                       if chave in self._pecas and _norm(self._pecas[chave].projeto) == projeto}
        if self.ativa() is not None:
            self._focos[_norm(self.ativa().projeto)] = self._ativa

    def salvar(self) -> None:
        with self._trava:
            dados = {"pecas": [asdict(p) for p in self._pecas.values()],
                     "ativa": self._ativa, "focos": dict(self._focos), "em": time.time()}
            self._arq.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._arq.with_suffix(".tmp")
            tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self._arq)

    def pasta(self) -> Path:
        from .cad import pasta_projetos
        return self._pasta or pasta_projetos()

    # ---- criar e achar --------------------------------------------------
    def criar(self, tipo: str, parametros: dict[str, float], *, nome: str = "",
              projeto: str = "", material: str = "PLA", motivo: str = "primeira versão") -> tuple[Peca, list[str]]:
        erros, avisos = validar(tipo, parametros)
        if erros:
            raise ValueError("; ".join(erros))
        material = self.validar_estilo("material", material)
        agora = time.time()
        with self._trava:
            p = Peca(nome=nome or tipo, tipo=tipo, parametros=dict(parametros), projeto=projeto,
                     material=material, criada_em=agora, mexida_em=agora)
            chave = _norm(p.nome)
            n = 2
            while chave in self._pecas:                 # "caixa", "caixa 2"...
                p.nome = f"{nome or tipo} {n}"
                chave, n = _norm(p.nome), n + 1
            # Não publicar uma peça cuja geração/escrita falhou.
            self._gerar_versao(p, motivo)
            self._pecas[chave] = p
            self._ativa = chave
            self._focos[_norm(p.projeto)] = chave
            self.salvar()
        return p, avisos

    def ativa(self) -> Peca | None:
        return self._pecas.get(self._ativa or "")

    def focar(self, nome: str) -> Peca | None:
        with self._trava:
            p = self.achar(nome)
            if p is not None:
                self._ativa = _norm(p.nome)
                self._focos[_norm(p.projeto)] = self._ativa
                self.salvar()
        return p

    def focar_projeto(self, projeto: str) -> Peca | None:
        """Retoma o foco desse projeto, sem reutilizar uma peça de outro."""
        with self._trava:
            chave = _norm(projeto)
            p = self._pecas.get(self._focos.get(chave, ""))
            if p is None or _norm(p.projeto) != chave:
                p = next((item for item in self.todas() if _norm(item.projeto) == chave), None)
            self._ativa = _norm(p.nome) if p else None
            if p is not None:
                self._focos[chave] = self._ativa
            self.salvar()
            return p

    def achar(self, texto: str) -> Peca | None:
        alvo = _norm(texto)
        if not alvo:
            return None
        if alvo in self._pecas:
            return self._pecas[alvo]
        for chave, p in sorted(self._pecas.items(), key=lambda kv: kv[1].mexida_em, reverse=True):
            if alvo in chave or chave in alvo or _norm(p.tipo) == alvo:
                return p
        return None

    def todas(self) -> list[Peca]:
        return sorted(self._pecas.values(), key=lambda p: p.mexida_em, reverse=True)

    # ---- gerar e alterar -------------------------------------------------
    def _gerar_versao(self, p: Peca, motivo: str) -> Versao:
        """Gera a malha AGORA e mede o volume nela. Nada é prometido sem medir."""
        from .cad import salvar_stl, volume_mm3
        from .engenharia import gerar_peca
        if p.tipo in MONTAGENS:
            tris, nome_curto = self._malha_da_montagem(p), p.nome
        else:
            tris, nome_curto, _desc = gerar_peca(p.tipo, p.parametros)
        numero = p.versao + 1
        nome_arquivo = re.sub(r"[^a-z0-9_-]+", "_", _norm(p.nome)).strip("_") or "peca"
        arquivo = self.pasta() / f"{nome_arquivo}_v{numero}.stl"
        temporario = arquivo.with_suffix(".stl.tmp")
        salvar_stl(tris, temporario, nome_curto)
        if temporario.stat().st_size != 84 + 50 * len(tris):
            raise OSError("STL incompleto: tamanho não corresponde à malha")
        temporario.replace(arquivo)
        caminho = str(arquivo)
        v = Versao(numero=numero, parametros=dict(p.parametros), arquivo=caminho,
                   volume_mm3=abs(volume_mm3(tris)), triangulos=len(tris), motivo=motivo,
                   em=time.time(), material=p.material, cor=p.cor)
        with self._trava:
            p.versoes.append(v)
            p.mexida_em = time.time()
        return v

    @staticmethod
    def montagem_de(p: Peca):
        """A montagem (com componentes) por trás de uma peça composta."""
        from .montagem import caixa_com_tampa
        if p.tipo == "caixa_com_tampa":
            q = p.parametros
            return caixa_com_tampa(q["c"], q["l"], q["a"], q.get("parede", 2.0), q.get("tampa", 2.0))
        return None

    def _malha_da_montagem(self, p: Peca, explodir: float = 0.0):
        from .montagem import malha
        m = self.montagem_de(p)
        if m is None:
            raise ValueError(f"{p.tipo} não é uma montagem conhecida")
        return malha(m, explodir)

    def explodir(self, p: Peca, fator: float = 1.0):
        """STL com as peças separadas, para a mesa. Só de montagem conhecida."""
        from .cad import salvar_stl
        tris = self._malha_da_montagem(p, fator)
        arquivo = self.pasta() / f"{_norm(p.nome).replace(' ', '_')}_v{p.versao}_explodida.stl"
        try:
            salvar_stl(tris, arquivo, f"{p.nome} explodida")
        except OSError:
            return None
        return arquivo

    def alterar(self, p: Peca, chave: str, *, valor: float | None = None,
                delta: float | None = None, motivo: str = "", versao_esperada: int | None = None) -> tuple[Versao, list[str]]:
        """Muda UMA dimensão e gera outra versão. A anterior continua intacta."""
        with self._trava:
            if versao_esperada is not None and p.versao != versao_esperada:
                raise ValueError("a peça mudou desde a prévia; gere uma nova prévia")
            previa = self.prever_alteracao(p, chave, valor=valor, delta=delta)
            candidatos, avisos = previa["parametros"], previa["avisos"]
            candidato = replace(p, parametros=candidatos, versoes=list(p.versoes))
            v = self._gerar_versao(candidato, motivo or previa["motivo"])
            antigos, versoes, instante = p.parametros, p.versoes, p.mexida_em
            p.parametros, p.versoes, p.mexida_em = candidatos, candidato.versoes, candidato.mexida_em
            try:
                self.salvar()
            except OSError:
                p.parametros, p.versoes, p.mexida_em = antigos, versoes, instante
                raise
        return v, avisos

    def prever_alteracao(self, p: Peca, chave: str, *, valor: float | None = None,
                         delta: float | None = None) -> dict[str, Any]:
        """Prévia de parâmetros validada, sem consolidar uma versão."""
        if chave not in p.parametros:
            raise KeyError(f"{p.tipo} não tem {NOME_FALADO.get(chave, chave)}")
        if (valor is None) == (delta is None):
            raise ValueError("informe um valor ou uma variação")
        antes = p.parametros[chave]
        novo = float(valor) if valor is not None else antes + float(delta)
        candidatos = dict(p.parametros)
        candidatos[chave] = novo
        erros, avisos = validar(p.tipo, candidatos)
        if erros:
            raise ValueError("; ".join(erros))
        return {"parametros": candidatos, "avisos": avisos, "versao_base": p.versao,
                "motivo": f"{NOME_FALADO.get(chave, chave)} de {antes:g} para {novo:g} "
                          + ("dentes" if chave == "dentes" else "mm")}

    def gerar_previa(self, p: Peca, chave: str, *, valor: float | None = None,
                     delta: float | None = None) -> dict[str, Any]:
        """Exporta uma malha de prévia isolada; não muda a peça nem seu histórico."""
        with self._trava:
            previa = self.prever_alteracao(p, chave, valor=valor, delta=delta)
            candidato = replace(p, nome=f"{p.nome} previa {uuid.uuid4().hex[:12]}",
                                parametros=dict(previa["parametros"]), versoes=[])
            versao = self._gerar_versao(candidato, previa["motivo"])
            previa.update(arquivo=versao.arquivo, volume_mm3=versao.volume_mm3,
                          triangulos=versao.triangulos, unidade="mm", estado="previa",
                          chave=chave, valor=previa["parametros"][chave])
            previa.update(material=p.material, cor=p.cor, tipo_alteracao="dimensao")
            return previa

    @staticmethod
    def validar_estilo(chave: str, valor: str) -> str:
        if not isinstance(valor, str):
            raise ValueError("material e cor precisam ser texto")
        if chave == "material":
            valor = valor.strip()
            if not valor or len(valor) > 80 or any(ord(c) < 32 for c in valor):
                raise ValueError("informe um material com até 80 caracteres")
            return valor
        if chave == "cor":
            cores = {"azul": "#2196f3", "vermelho": "#f44336", "vermelha": "#f44336",
                     "verde": "#4caf50", "amarelo": "#ffeb3b", "amarela": "#ffeb3b",
                     "branco": "#ffffff", "branca": "#ffffff", "preto": "#222222",
                     "preta": "#222222", "cinza": "#9e9e9e", "laranja": "#ff9800",
                     "roxo": "#9c27b0", "roxa": "#9c27b0", "ciano": "#26c6da"}
            cor = cores.get(_norm(valor), valor.strip().lower())
            if not re.fullmatch(r"#[0-9a-f]{6}", cor):
                raise ValueError("use uma cor como azul, vermelho ou #2196f3")
            return cor
        raise ValueError("a aparência editável inclui material e cor")

    def previa_estilo(self, p: Peca, chave: str, valor: str) -> dict[str, Any]:
        """A mesma geometria, com metadados explícitos; STL não armazena cor."""
        with self._trava:
            valor = self.validar_estilo(chave, valor)
            atual = p.atual()
            if atual is None or not Path(atual.arquivo).is_file():
                raise ValueError("a malha atual não está disponível para a prévia")
            return {"tipo_alteracao": "estilo", "chave": chave, "valor": valor,
                    "material": valor if chave == "material" else p.material,
                    "cor": valor if chave == "cor" else p.cor,
                    "parametros": dict(p.parametros), "versao_base": p.versao,
                    "motivo": f"{chave} de {getattr(p, chave)} para {valor}",
                    "arquivo": atual.arquivo, "volume_mm3": atual.volume_mm3,
                    "triangulos": atual.triangulos, "unidade": "mm", "estado": "previa",
                    "avisos": ["Material e cor são metadados locais; o STL contém somente geometria."]}

    def alterar_estilo(self, p: Peca, chave: str, valor: str, *, versao_esperada: int) -> tuple[Versao, list[str]]:
        with self._trava:
            if p.versao != versao_esperada:
                raise ValueError("a peça mudou desde a prévia; gere uma nova prévia")
            previa = self.previa_estilo(p, chave, valor)
            candidato = replace(p, **{chave: previa["valor"]}, versoes=list(p.versoes))
            v = self._gerar_versao(candidato, previa["motivo"])
            anterior = getattr(p, chave), p.versoes, p.mexida_em
            setattr(p, chave, previa["valor"])
            p.versoes, p.mexida_em = candidato.versoes, candidato.mexida_em
            try:
                self.salvar()
            except OSError:
                setattr(p, chave, anterior[0])
                p.versoes, p.mexida_em = anterior[1:]
                raise
            return v, previa["avisos"]

    def comparar(self, p: Peca, primeira: int, segunda: int) -> dict[str, Any]:
        with self._trava:
            a = next((v for v in p.versoes if v.numero == primeira), None)
            b = next((v for v in p.versoes if v.numero == segunda), None)
            if a is None or b is None:
                raise ValueError("uma das versões não existe")
            mudancas = [{"campo": k, "antes": a.parametros.get(k), "depois": b.parametros.get(k),
                         "unidade": "dentes" if k == "dentes" else "mm"}
                        for k in sorted(a.parametros.keys() | b.parametros.keys())
                        if a.parametros.get(k) != b.parametros.get(k)]
            for campo in ("material", "cor"):
                if getattr(a, campo) != getattr(b, campo):
                    mudancas.append({"campo": campo, "antes": getattr(a, campo), "depois": getattr(b, campo)})
            return {"peca": p.nome, "de": primeira, "para": segunda, "mudancas": mudancas,
                    "volume_antes_mm3": a.volume_mm3, "volume_depois_mm3": b.volume_mm3,
                    "limite": "Dados ausentes em versões antigas permanecem desconhecidos; não houve teste físico."}

    def reverter(self, p: Peca, numero: int) -> Versao | None:
        """Volta os parâmetros de uma versão antiga -- criando uma versão nova."""
        alvo = next((v for v in p.versoes if v.numero == numero), None)
        if alvo is None:
            return None
        with self._trava:
            candidato = replace(p, parametros=dict(alvo.parametros), versoes=list(p.versoes),
                                material=alvo.material if alvo.material is not None else p.material,
                                cor=alvo.cor if alvo.cor is not None else p.cor)
            v = self._gerar_versao(candidato, f"voltou para a versão {numero}")
            estilo_anterior = p.material, p.cor
            p.material, p.cor = candidato.material, candidato.cor
            antigos, versoes, instante = p.parametros, p.versoes, p.mexida_em
            p.parametros, p.versoes, p.mexida_em = candidato.parametros, candidato.versoes, candidato.mexida_em
            try:
                self.salvar()
            except OSError:
                p.parametros, p.versoes, p.mexida_em = antigos, versoes, instante
                p.material, p.cor = estilo_anterior
                raise
        return v

    def esquecer(self, nome: str) -> bool:
        with self._trava:
            chave = _norm(nome)
            saiu = self._pecas.pop(chave, None) is not None
            if self._ativa == chave:
                self._ativa = None
            self._focos = {projeto: alvo for projeto, alvo in self._focos.items() if alvo != chave}
        if saiu:
            self.salvar()
        return saiu


# ---- como o Jarvis fala disso -------------------------------------------
def _num(x: float) -> str:
    return f"{x:.10g}".replace(".", ",")


def descrever(p: Peca) -> str:
    """"caixa 80 por 50 por 30 milímetros, parede 2" -- do jeito que se fala."""
    itens = [f"{NOME_FALADO.get(k, k)} {_num(v)}" for k, v in p.parametros.items() if v]
    return f"{p.tipo} com " + ", ".join(itens) if itens else p.tipo


def falar_versao(p: Peca, v: Versao, avisos: list[str] | None = None,
                 tratamento: str = "Senhor") -> str:
    """O que mudou, o que foi medido e o que NÃO foi conferido."""
    cm3 = v.volume_mm3 / 1000
    frases = [f"Versão {v.numero} de {p.nome}: {v.motivo}"]
    frases.append(f"Medi na peça gerada, por cálculo da malha: {_num(round(cm3, 1))} centímetros cúbicos")
    from .engenharia import MATERIAIS
    material = next((m for m in MATERIAIS if _norm(p.material) in [_norm(m[0]), *map(_norm, m[1])]), None)
    if material:
        frases.append(f"Massa teórica estimada: {_num(round(cm3 * material[2], 1))} gramas em {p.material} "
                      f"maciço, densidade típica de referência {_num(material[2])} g/cm³; "
                      "não é pesagem nem considera preenchimento de impressão")
    else:
        frases.append(f"Não estimei massa: falta densidade documentada para {p.material}")
    if v.numero > 1:
        frases.append(f"A versão {v.numero - 1} continua salva; para voltar, diga: "
                      f"volte para a versão {v.numero - 1}")
    for a in (avisos or []):
        frases.append(f"Atenção: {a}")
    frases.append("Não testei impressão: isso só o Cura e a impressora dizem")
    return ". ".join(frases) + "."


def falar_versoes(p: Peca, tratamento: str = "Senhor") -> str:
    if not p.versoes:
        return f"{p.nome} ainda não tem versão salva, {tratamento}."
    linhas = [f"versão {v.numero}, {v.motivo}" for v in p.versoes[-5:]]
    return f"{p.nome} está na versão {p.versao}, {tratamento}: " + "; ".join(linhas) + "."
