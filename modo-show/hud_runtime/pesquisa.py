"""Pesquisa com fontes: responde citando de onde veio.

Ordem: Wikipedia em portugues (resumo do verbete), DuckDuckGo (resposta
instantanea) e, para assuntos do momento, manchetes do Google Noticias.
Sem fonte encontrada = diz que nao encontrou (nunca inventa). O modelo nao
entra aqui: o texto falado e o proprio resumo da fonte, com o nome dela.

So a consulta sai do computador (para essas APIs publicas); TLS verificado.
"""

from __future__ import annotations

import re
import copy
import threading
import time
import unicodedata
import urllib.parse
from datetime import datetime
from typing import Any

from .rede import ERROS_REDE, baixar_json

WIKI_BUSCA = "https://pt.wikipedia.org/w/api.php?"
WIKI_RESUMO = "https://pt.wikipedia.org/api/rest_v1/page/summary/"
DDG = "https://api.duckduckgo.com/?"
VALIDADE_S = 30 * 60
MAX_SUBCONSULTAS = 3


def frases(texto: str, n: int = 2, limite: int = 360) -> str:
    """Primeiras n frases, sem cortar no meio de "Dr." ou de numeros."""
    partes = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", " ".join(texto.split()))
    saida = ""
    for p in partes[:n]:
        if len(saida) + len(p) > limite and saida:
            break
        saida = f"{saida} {p}".strip()
    saida = saida[:limite].rstrip(" ,;:")
    return saida if saida.endswith((".", "!", "?")) else saida + "."


def limpar_consulta(q: str) -> str:
    q = " ".join(q.split()).strip(" .!?,;:")
    q = re.sub(r"^(?:sobre|a respeito de|acerca de|por|o que (?:e|é)|quem (?:e|é|foi))\s+", "", q, flags=re.I)
    q = re.sub(r"^(?:o|a|os|as|um|uma)\s+(?=\S)", "", q, flags=re.I)
    return q[:120]


def decompor_consulta(consulta: str) -> dict[str, Any]:
    """Planejamento determinístico limitado; nenhum texto recuperado cria novas consultas."""
    if not isinstance(consulta, str) or any(ord(c) < 32 and c not in "\n\t" for c in consulta):
        raise ValueError("consulta inválida")
    bruto = " ".join(consulta.split()).strip(" .!?")
    if not 2 <= len(bruto) <= 500:
        raise ValueError("use uma consulta entre 2 e 500 caracteres")
    comparacao = re.sub(r"^(?:compare|comparar|comparação entre|comparacao entre|diferenças entre|diferencas entre)\s+", "", bruto, flags=re.I)
    separar_e = comparacao != bruto
    partes = re.split(r"\s*(?:;|\bversus\b|\bvs\.?\b|\be também\b|\be tambem\b)\s*", comparacao, flags=re.I)
    if separar_e and len(partes) == 1:
        partes = re.split(r"\s+(?:e|com)\s+", comparacao, maxsplit=1, flags=re.I)
    consultas = []
    for p in partes:
        q = limpar_consulta(p)
        if len(q) >= 2 and q.casefold() not in {x.casefold() for x in consultas}:
            consultas.append(q)
    estrategia = "subperguntas explícitas" if len(consultas) > 1 else "visão geral, características e limitações"
    if len(consultas) == 1:
        base = consultas[0][:95]
        consultas.extend([base + " características", base + " limitações"])
    return {"consultas": consultas[:MAX_SUBCONSULTAS], "omitidas": consultas[MAX_SUBCONSULTAS:],
            "estrategia": estrategia, "limite": MAX_SUBCONSULTAS,
            "truncada": any(len(p.strip()) > 120 for p in partes)}


def _chave_fonte(fonte: dict) -> str:
    return str(fonte.get("link") or (fonte.get("fonte", "") + ":" + fonte.get("titulo", ""))).rstrip("/").casefold()


def comparar_evidencias(fontes: list[dict]) -> list[dict]:
    """Compara trechos literalmente; diferenças não viram contradições inventadas."""
    resumos = [f for f in fontes if f.get("texto") and f.get("cobertura") != "manchete"]
    comparacoes = []
    for i, a in enumerate(resumos):
        for b in resumos[i + 1:]:
            norm = lambda s: " ".join(unicodedata.normalize("NFKC", s).casefold().split())
            iguais = norm(a["texto"]) == norm(b["texto"])
            comparacoes.append({"fontes": [a["id"], b["id"]],
                                "estado": "trecho_repetido" if iguais else "trechos_distintos",
                                "trechos": [frases(a["texto"], 1, 240), frases(b["texto"], 1, 240)],
                                "conclusao": "Os resumos repetem o mesmo conteúdo; não são confirmação independente." if iguais else
                                "Os resumos têm conteúdos diferentes. Isso, por si só, não demonstra contradição."})
            if len(comparacoes) >= 3:
                return comparacoes
    return comparacoes


class Pesquisa:
    def __init__(self, noticias=None) -> None:
        self._noticias = noticias
        self._cache: dict[tuple[str, bool, bool], tuple[float, dict]] = {}
        self._trava = threading.Lock()

    def wikipedia(self, q: str) -> dict[str, Any] | None:
        busca = baixar_json(WIKI_BUSCA + urllib.parse.urlencode(
            {"action": "query", "list": "search", "srsearch": q, "format": "json", "srlimit": 3}))
        for r in (busca.get("query") or {}).get("search", []):
            titulo = r["title"]
            p = baixar_json(WIKI_RESUMO + urllib.parse.quote(titulo.replace(" ", "_"), safe=""))
            if p.get("type") == "disambiguation" or not p.get("extract"):
                continue
            url = ((p.get("content_urls") or {}).get("desktop") or {}).get("page")
            return {"fonte": "Wikipédia", "titulo": p.get("title") or titulo, "texto": p["extract"],
                    "cobertura": "resumo", "alterado_em": p.get("timestamp"),
                    "link": url if isinstance(url, str) and url.startswith("https://") else None}
        return None

    def duckduckgo(self, q: str) -> dict[str, Any] | None:
        d = baixar_json(DDG + urllib.parse.urlencode({"q": q, "format": "json", "no_html": 1, "skip_disambig": 1}))
        texto = d.get("AbstractText") or d.get("Answer")
        if not texto:
            return None
        url = d.get("AbstractURL")
        return {"fonte": d.get("AbstractSource") or "DuckDuckGo", "titulo": d.get("Heading") or q, "texto": str(texto),
                "cobertura": "resposta_instantanea",
                "link": url if isinstance(url, str) and url.startswith("https://") else None}

    def responder(self, consulta: str, com_noticias: bool = True, comparar_fontes: bool = False) -> dict[str, Any]:
        q = limpar_consulta(consulta)
        if len(q) < 2:
            return {"status": "vazio", "consulta": q, "fala": "O que devo pesquisar?", "fontes": []}
        chave = (q.lower(), com_noticias, comparar_fontes)
        with self._trava:
            g = self._cache.get(chave)
        if g and time.time() - g[0] < VALIDADE_S:
            r = copy.deepcopy(g[1])
            r.update(cache=True, atendido_em=time.time(), idade_cache_s=round(time.time() - g[0], 1))
            r["fala"] = f"Consulta em cache de {datetime.fromtimestamp(r['em']):%H:%M}. " + r["fala"]
            for f in r["fontes"]:
                f["cache"] = True
            return r
        principal, falhas, fontes = None, [], []
        for nome, f in (("Wikipédia", self.wikipedia), ("DuckDuckGo", self.duckduckgo)):
            try:
                achado = f(q)
            except (*ERROS_REDE, KeyError) as e:
                falhas.append(f"{nome}: {type(e).__name__}")
                achado = None
            if achado:
                achado = dict(achado, consultado_em=time.time(), cache=False,
                              cobertura=achado.get("cobertura", "resumo"))
                principal = principal or achado
                if _chave_fonte(achado) not in {_chave_fonte(x) for x in fontes}:
                    fontes.append(achado)
                if not comparar_fontes:
                    break
        noticias = []
        if com_noticias and self._noticias:
            try:
                n = self._noticias.buscar(q, limite=3)
            except ERROS_REDE as e:
                n = {"status": "erro", "itens": []}
                falhas.append(f"Notícias: {type(e).__name__}")
            noticias = n.get("itens", []) if n.get("status") == "medido" else []
            fontes += [{"fonte": x["fonte"], "titulo": x["titulo"], "link": x.get("link"), "texto": None,
                        "cobertura": "manchete", "publicado_em": x.get("em"),
                        "consultado_em": x.get("consultado_em", n.get("em")), "cache": x.get("cache", False),
                        "desatualizado": x.get("desatualizado", n.get("desatualizado", False))} for x in noticias]
            falhas.extend((n.get("falhas") or []) + (n.get("falhas_cache") or []))
        if principal:
            fala = f"Segundo a {principal['fonte']}: {frases(principal['texto'])}"
            if noticias:
                fala += f" Nas manchetes consultadas, {noticias[0]['fonte']}: {noticias[0]['titulo'].rstrip('.')}."
        elif noticias:
            fala = (f"Não achei um verbete sobre {q}, mas consultei manchetes. "
                    f"{noticias[0]['fonte']}: {noticias[0]['titulo'].rstrip('.')}.")
        else:
            fala = f"Não encontrei fontes consultáveis sobre {q}."
            if falhas:
                fala += " As fontes de pesquisa não responderam."
        if noticias:
            fala += " Li apenas as manchetes dessas notícias."
        if any(f.get("desatualizado") for f in fontes):
            fala += " Parte das manchetes veio de uma consulta antiga, pois a atualização falhou."
        for i, f in enumerate(fontes, 1):
            f["id"] = f"fonte-{i}"
        r = {"status": "medido" if fontes else "sem_fontes", "consulta": q, "fala": fala, "fontes": fontes,
             "falhas": falhas, "em": time.time(), "cache": False, "idade_cache_s": 0,
             "cobertura": "resumos e manchetes; páginas integrais não analisadas"}
        if fontes:
            with self._trava:
                self._cache[chave] = (time.time(), copy.deepcopy(r))
        return r

    def investigar(self, consulta: str, cancelado=None) -> dict[str, Any]:
        plano = decompor_consulta(consulta)
        resultados, fontes, lacunas = [], [], []
        iniciou = time.time()
        for q in plano["consultas"]:
            if cancelado and cancelado():
                lacunas.append("Pesquisa interrompida antes de terminar todas as subconsultas.")
                break
            r = self.responder(q, comparar_fontes=True)
            resultados.append(r)
            for f in r.get("fontes", []):
                chave = _chave_fonte(f)
                existente = next((x for x in fontes if _chave_fonte(x) == chave), None)
                if existente is not None:
                    existente["consultas"].append(q)
                else:
                    fontes.append(dict(f, id=f"fonte-{len(fontes) + 1}", consultas=[q]))
            if not r.get("fontes"):
                lacunas.append(f"Sem fonte recuperada para: {q}.")
            if r.get("falhas"):
                lacunas.append(f"Fontes indisponíveis em {q}: {'; '.join(r['falhas'])}.")
        if plano["omitidas"]:
            lacunas.append(f"Limite de três subconsultas: {len(plano['omitidas'])} parte(s) não foram pesquisadas.")
        if plano["truncada"]:
            lacunas.append("Uma subconsulta foi reduzida ao limite de 120 caracteres; refine o pedido para não perder detalhes.")
        lacunas.append("Cobertura limitada a resumos e manchetes. Divergências semânticas e textos integrais não foram verificados.")
        comparacoes = comparar_evidencias(fontes)
        if len([f for f in fontes if f.get("texto")]) < 2:
            lacunas.append("Menos de dois resumos distintos; não há material suficiente para confrontar afirmações.")
        trechos = [f"{f['fonte']}, {f['titulo']}: {frases(f['texto'], 1, 240)}" for f in fontes if f.get("texto")][:3]
        fala = f"Consultei {len(resultados)} de {len(plano['consultas'])} subconsultas e recuperei {len(fontes)} fonte(s). "
        fala += " ".join(trechos) if trechos else "Não encontrei resumos suficientes para responder com evidências."
        fala += (" Comparei os trechos disponíveis; diferenças de redação não comprovam contradições." if comparacoes else
                 " Não há resumos distintos suficientes para confrontar afirmações.")
        fala += " Resumos, fontes e lacunas estão no painel."
        return {"status": "medido" if fontes else "sem_fontes", "consulta": consulta, "plano": plano,
                "subconsultas": [{"consulta": r["consulta"], "status": r["status"], "em": r.get("em"),
                                  "cache": r.get("cache", False)} for r in resultados],
                "fontes": fontes, "comparacoes": comparacoes, "lacunas": lacunas,
                "em": time.time(), "duracao_s": round(time.time() - iniciou, 2), "fala": fala,
                "cache": any(r.get("cache") for r in resultados)}


def cartao(r: dict[str, Any]) -> dict[str, Any]:
    itens = [{"titulo": f["titulo"], "detalhe": (frases(f["texto"], 1, 300) if f.get("texto") else "Somente manchete; corpo não lido.") +
              f" Cobertura: {f.get('cobertura', 'não informada')}." + (" Consulta em cache." if f.get("cache") else ""),
              "fonte": f["fonte"], "link": f.get("link"), "em": f.get("consultado_em"),
              "publicado_em": f.get("publicado_em"), "cobertura": f.get("cobertura")} for f in r.get("fontes", [])]
    itens.extend({"titulo": "Comparação de trechos", "detalhe": c["conclusao"], "fonte": ", ".join(c["fontes"])}
                 for c in r.get("comparacoes", []))
    itens.extend({"titulo": "Lacuna", "detalhe": lacuna, "fonte": "limite da pesquisa"} for lacuna in r.get("lacunas", []))
    return {"tipo": "pesquisa", "titulo": f"Pesquisa: {r.get('consulta', '')}", "itens": itens}
