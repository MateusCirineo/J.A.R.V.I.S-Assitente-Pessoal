"""Manchetes por RSS publico, como o Jarvis do filme mostrando o noticiario.

- Fontes gerais (G1, BBC...) para o painel e o resumo do dia.
- Catalogo por categoria (tecnologia, economia, esportes...) para "noticias
  de tecnologia"; cada feed foi testado de verdade em 18/09/2026 (os que
  estavam fora do ar ou devolviam HTML ficaram de fora).
- Tema livre ("noticias sobre o Corinthians") pelo RSS de busca do Google
  Noticias, com o nome do veiculo de cada manchete.

So as manchetes sao baixadas; nada e enviado aos sites alem do pedido do feed
(e, na busca, o tema). TLS sempre verificado. Cache de 10 minutos por fonte;
uma fonte fora do ar nao derruba as outras.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from datetime import datetime
from typing import Any

from .rede import baixar

FONTES: dict[str, tuple[str, str]] = {
    # gerais
    "g1": ("G1", "https://g1.globo.com/rss/g1/"),
    "bbc": ("BBC News Brasil", "https://feeds.bbci.co.uk/portuguese/rss.xml"),
    "folha": ("Folha de S.Paulo", "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"),
    "cnn": ("CNN Brasil", "https://www.cnnbrasil.com.br/feed/"),
    "oglobo": ("O Globo", "https://oglobo.globo.com/rss/oglobo"),
    "metropoles": ("Metrópoles", "https://www.metropoles.com/feed"),
    "terra": ("Terra", "https://www.terra.com.br/rss.xml"),
    "istoe": ("IstoÉ", "https://istoe.com.br/feed/"),
    # tecnologia
    "g1_tec": ("G1 Tecnologia", "https://g1.globo.com/rss/g1/tecnologia/"),
    "olhar_digital": ("Olhar Digital", "https://olhardigital.com.br/feed/"),
    "canaltech": ("Canaltech", "https://canaltech.com.br/rss/"),
    "tecnoblog": ("Tecnoblog", "https://tecnoblog.net/feed/"),
    "tudocelular": ("TudoCelular", "https://www.tudocelular.com/feed/"),
    "adrenaline": ("Adrenaline", "https://adrenaline.com.br/feed/"),
    # economia
    "g1_eco": ("G1 Economia", "https://g1.globo.com/rss/g1/economia/"),
    "infomoney": ("InfoMoney", "https://www.infomoney.com.br/feed/"),
    "folha_mercado": ("Folha Mercado", "https://feeds.folha.uol.com.br/mercado/rss091.xml"),
    "exame": ("Exame", "https://exame.com/feed/"),
    # esportes
    "ge": ("ge", "https://ge.globo.com/dynamo/rss2.xml"),
    "gazeta_esportiva": ("Gazeta Esportiva", "https://www.gazetaesportiva.com/feed/"),
    "espn": ("ESPN Brasil", "https://www.espn.com.br/rss/"),
    # entretenimento
    "g1_pop": ("G1 Pop & Arte", "https://g1.globo.com/rss/g1/pop-arte/"),
    "rolling_stone": ("Rolling Stone Brasil", "https://rollingstone.com.br/feed/"),
    "terra_diversao": ("Terra Diversão", "https://www.terra.com.br/diversao/rss.xml"),
    # politica
    "g1_pol": ("G1 Política", "https://g1.globo.com/rss/g1/politica/"),
    "g1_mundo": ("G1 Mundo", "https://g1.globo.com/rss/g1/mundo/"),
    "poder360": ("Poder360", "https://www.poder360.com.br/feed/"),
    "cartacapital": ("CartaCapital", "https://www.cartacapital.com.br/feed/"),
    # saude e ciencia
    "g1_saude": ("G1 Ciência e Saúde", "https://g1.globo.com/rss/g1/ciencia-e-saude/"),
    "drauzio": ("Drauzio Varella", "https://drauziovarella.uol.com.br/feed/"),
    "tua_saude": ("Tua Saúde", "https://www.tuasaude.com/feed/"),
    "inovacao": ("Inovação Tecnológica", "https://www.inovacaotecnologica.com.br/boletim/rss.xml"),
}

CATEGORIAS: dict[str, list[str]] = {
    "geral": ["g1", "bbc", "folha", "cnn", "oglobo", "metropoles"],
    "tecnologia": ["g1_tec", "olhar_digital", "canaltech", "tecnoblog", "tudocelular", "adrenaline"],
    "economia": ["g1_eco", "infomoney", "folha_mercado", "exame"],
    "esportes": ["ge", "gazeta_esportiva", "espn"],
    "entretenimento": ["g1_pop", "rolling_stone", "terra_diversao"],
    "politica": ["g1_pol", "poder360", "cartacapital"],
    "saude": ["g1_saude", "drauzio", "tua_saude"],
    "ciencia": ["g1_saude", "inovacao"],
    "mundo": ["g1_mundo", "bbc"],
}

# so palavras GENERICAS de cada categoria; nomes proprios (times, pessoas,
# empresas) viram busca por tema, que acerta mais
_PALAVRAS_CATEGORIA = {
    "tecnologia": r"tecnologia|tech|tecnologicas?|celulares?|smartphones?|internet|aplicativos?|computadores?"
                  r"|informatica|inteligencia artificial|games?|videogames?|software|hardware|programacao|robotica|startups?",
    "economia": r"economia|economicas?|financas|dinheiro|bolsa|mercado financeiro|mercados?|investimentos?|empregos?"
                r"|inflacao|juros|impostos?|negocios",
    "esportes": r"esportes?|esportivas?|futebol|basquete|volei|tenis|formula 1|automobilismo|olimpiadas",
    "entretenimento": r"entretenimento|famosos|celebridades|filmes?|series?|musica|cinema|novelas?|cultura|pop"
                      r"|televisao|tv",
    "politica": r"politica|politicas|governo|eleicoes?|congresso|senado|brasilia",
    "saude": r"saude|medicina|doencas?|vacinas?|bem estar|nutricao",
    "ciencia": r"ciencia|cientificas?|espaco|astronomia|fisica|biologia|universo",
    "mundo": r"mundo|do mundo|mundiais|internacionais|internacional|exterior|global|globais|fora do brasil",
    "geral": r"gerais|geral|brasil|dia|hoje|principais|ultimas",
}
NOMES_CATEGORIA = {"tecnologia": "tecnologia", "economia": "economia", "esportes": "esportes",
                   "entretenimento": "entretenimento", "politica": "política", "saude": "saúde",
                   "ciencia": "ciência", "mundo": "do mundo", "geral": "gerais"}
BUSCA_URL = "https://news.google.com/rss/search?"
VALIDADE_S = 10 * 60
LIMITE_BYTES = 3_000_000
_ATOM = "{http://www.w3.org/2005/Atom}"
_ERROS = (urllib.error.URLError, OSError, ValueError, EOFError, ET.ParseError)


def _quando(texto: str | None) -> float | None:
    if not texto:
        return None
    try:
        return parsedate_to_datetime(texto.strip()).timestamp()
    except (TypeError, ValueError):
        pass
    try:                                              # Atom: ISO 8601
        from datetime import datetime
        return datetime.fromisoformat(texto.strip().replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _link_seguro(link: str | None) -> str | None:
    link = (link or "").strip()
    return link if link.startswith(("https://", "http://")) else None


_RUIDO = re.compile(r"\bao vivo\b|\bclique aqui\b|\bassista\b|^v[ií]deo\b|\bpodcast\b|^em instantes\b", re.I)


def manchete_de_verdade(titulo: str) -> bool:
    """Descarta chamadas de transmissao, video e propaganda ("Clique aqui")."""
    return len(titulo.split()) >= 5 and not _RUIDO.search(titulo)


def ler_feed(conteudo: bytes, fonte: str) -> list[dict[str, Any]]:
    """RSS 2.0 ou Atom -> [{titulo, link, em, fonte}], so manchetes de verdade."""
    return [i for i in _ler_feed(conteudo, fonte) if manchete_de_verdade(i["titulo"])]


def _ler_feed(conteudo: bytes, fonte: str) -> list[dict[str, Any]]:
    raiz = ET.fromstring(conteudo)
    itens = []
    for it in raiz.iter("item"):
        titulo = " ".join((it.findtext("title") or "").split())
        if titulo:
            itens.append({"titulo": titulo[:220], "link": _link_seguro(it.findtext("link")),
                          "em": _quando(it.findtext("pubDate")), "fonte": fonte})
    for it in raiz.iter(f"{_ATOM}entry"):
        titulo = " ".join((it.findtext(f"{_ATOM}title") or "").split())
        link = it.find(f"{_ATOM}link")
        if titulo:
            itens.append({"titulo": titulo[:220], "link": _link_seguro(link.get("href") if link is not None else None),
                          "em": _quando(it.findtext(f"{_ATOM}updated") or it.findtext(f"{_ATOM}published")),
                          "fonte": fonte})
    return itens


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def detectar_categoria(tema: str) -> str | None:
    """ "tecnologia", "de esporte", "do dia" -> categoria; nome proprio -> None."""
    n = _normalizar(tema).strip(" .!?,")
    n = re.sub(r"^(?:(?:as|os|a|o|de|do|da|dos|das|sobre|em|mais)\s+)+", "", n)
    for cat, pal in _PALAVRAS_CATEGORIA.items():
        if re.fullmatch(rf"(?:{pal})(?: de hoje| do dia| hoje)?", n):
            return cat
    return None


def separar_veiculo(item: dict[str, Any]) -> dict[str, Any]:
    """Google Noticias poe o veiculo no fim do titulo: "Titulo - Folha de S.Paulo"."""
    t = item["titulo"]
    if " - " in t:
        titulo, veiculo = t.rsplit(" - ", 1)
        if 1 <= len(veiculo.split()) <= 6 and len(titulo.split()) >= 4:
            return {**item, "titulo": titulo.strip(), "fonte": veiculo.strip()}
    return item


def _atualidade(itens: list[dict[str, Any]]) -> dict[str, Any]:
    horarios = [i["consultado_em"] for i in itens if isinstance(i.get("consultado_em"), (int, float))]
    return {"em": min(horarios) if horarios else None, "cobertura": "manchetes",
            "cache": any(i.get("cache") for i in itens),
            "desatualizado": any(i.get("desatualizado") for i in itens),
            "falhas_cache": sorted({i["falha_atualizacao"] for i in itens if i.get("falha_atualizacao")})}


class Noticias:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._trava = threading.Lock()

    def _baixar(self, chave: str) -> list[dict[str, Any]]:
        nome, url = FONTES[chave]
        return self._baixar_url(chave, nome, url)

    def _baixar_url(self, chave: str, nome: str, url: str) -> list[dict[str, Any]]:
        with self._trava:
            guardado = self._cache.get(chave)
        if guardado and time.time() - guardado[0] < VALIDADE_S:
            return [dict(i, consultado_em=guardado[0], cache=True, desatualizado=False, cobertura="manchete")
                    for i in guardado[1]]
        try:
            itens = ler_feed(baixar(url, LIMITE_BYTES), nome)
        except _ERROS as erro:
            if guardado:                               # mantem o ultimo, mesmo velho
                return [dict(i, consultado_em=guardado[0], cache=True, desatualizado=True,
                             cobertura="manchete", falha_atualizacao=f"{nome}: {type(erro).__name__}")
                        for i in guardado[1]]
            raise
        agora = time.time()
        with self._trava:
            self._cache[chave] = (agora, itens)
        return [dict(i, consultado_em=agora, cache=False, desatualizado=False, cobertura="manchete") for i in itens]

    def obter(self, fontes: list[str] | None = None, limite: int = 24) -> dict[str, Any]:
        fontes = [f for f in (fontes or ["g1", "bbc"]) if f in FONTES]
        todas: list[dict[str, Any]] = []
        falhas: list[str] = []
        for chave in fontes:
            try:
                todas += self._baixar(chave)[:15]
            except _ERROS as e:
                falhas.append(f"{FONTES[chave][0]}: {type(e).__name__}")
        if not todas:
            return {"status": "erro" if falhas else "nao_configurado", "detalhe": "; ".join(falhas),
                    "itens": []}
        # intercala as fontes (mais recente de cada uma primeiro)
        todas.sort(key=lambda n: -(n["em"] or 0))
        itens = _intercalar(todas)[:limite]
        return {"status": "medido", **_atualidade(itens), "fontes": [FONTES[f][0] for f in fontes],
                "falhas": falhas, "itens": itens}

    def por_categoria(self, categoria: str, limite: int = 12) -> dict[str, Any]:
        categoria = categoria if categoria in CATEGORIAS else "geral"
        chaves = CATEGORIAS[categoria]
        todas: list[dict[str, Any]] = []
        falhas: list[str] = []

        def um(chave: str):
            try:
                return self._baixar(chave)[:10], None
            except _ERROS as e:
                return [], f"{FONTES[chave][0]}: {type(e).__name__}"

        with ThreadPoolExecutor(max_workers=6) as ex:
            for itens, falha in ex.map(um, chaves):
                todas += itens
                if falha:
                    falhas.append(falha)
        if not todas:
            return {"status": "erro", "detalhe": "; ".join(falhas) or "sem manchetes", "itens": [],
                    "categoria": categoria}
        todas.sort(key=lambda n: -(n["em"] or 0))
        itens = _intercalar(todas)[:limite]
        return {"status": "medido", **_atualidade(itens), "categoria": categoria,
                "fontes": [FONTES[c][0] for c in chaves], "falhas": falhas,
                "itens": itens}

    def buscar(self, tema: str, limite: int = 8) -> dict[str, Any]:
        """Manchetes recentes sobre um tema livre (Google Noticias, pt-BR)."""
        tema = " ".join(tema.split())[:100]
        url = BUSCA_URL + urllib.parse.urlencode({"q": tema, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"})
        try:
            itens = self._baixar_url("busca:" + _normalizar(tema), "Google Notícias", url)
        except _ERROS as e:
            return {"status": "erro", "detalhe": type(e).__name__, "itens": [], "tema": tema}
        itens = sorted((separar_veiculo(i) for i in itens), key=lambda n: -(n["em"] or 0))
        itens = itens[:limite]
        return {"status": "medido", **_atualidade(itens), "tema": tema, "fontes": ["Google Notícias"],
                "falhas": [], "itens": itens}


def _intercalar(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    por_fonte: dict[str, list[dict[str, Any]]] = {}
    for n in itens:
        por_fonte.setdefault(n["fonte"], []).append(n)
    saida = []
    while any(por_fonte.values()):
        for lista in por_fonte.values():
            if lista:
                saida.append(lista.pop(0))
    return saida


ORDINAIS = ["Primeira", "Segunda", "Terceira", "Quarta", "Quinta", "Sexta", "Sétima", "Oitava", "Nona", "Décima"]


def manchetes_faladas(dados: dict[str, Any], quantas: int = 3, numerar: bool = False,
                      titulo: str = "As principais manchetes") -> str:
    itens = (dados or {}).get("itens") or []
    if (dados or {}).get("status") != "medido" or not itens:
        return "Não consegui buscar as notícias agora."
    if numerar:
        partes = [f"{ORDINAIS[i]}, {n['fonte']}: {n['titulo'].strip()}" for i, n in enumerate(itens[:quantas])]
    else:
        partes = [f"{n['fonte']}: {n['titulo'].strip()}" for n in itens[:quantas]]
    # manchete que termina em "?" ou "!" fica assim (sem virar "?.")
    aviso = ""
    if dados.get("desatualizado"):
        quando = datetime.fromtimestamp(dados["em"]).strftime("%d/%m às %H:%M") if dados.get("em") else "horário desconhecido"
        aviso = f"A atualização falhou; são manchetes da consulta de {quando}. "
    elif dados.get("cache"):
        aviso = "Há manchetes reaproveitadas de consultas em cache. "
    return aviso + f"{titulo}. " + " ".join(p if p[-1:] in ".?!…" else p + "." for p in partes) + " Li apenas as manchetes."
