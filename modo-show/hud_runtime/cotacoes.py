"""Cotacoes: moedas (AwesomeAPI) e criptomoedas (CoinGecko).

Sempre com fonte e horario da cotacao. "Quanto esta o dolar?" e cotacao;
"o que e bitcoin?" nao e (vai para a pesquisa com fontes). Nada de conta,
chave ou dado pessoal: sao APIs publicas de leitura.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from datetime import datetime
from typing import Any

from .rede import ERROS_REDE, baixar_json

AWESOME = "https://economia.awesomeapi.com.br/json/last/"
COINGECKO = "https://api.coingecko.com/api/v3/simple/price?"
VALIDADE_S = 60

# nome falado -> (codigo, nome para falar, genero do artigo)
MOEDAS: dict[str, tuple[str, str, str]] = {
    "dolar": ("USD", "dólar", "o"), "dolares": ("USD", "dólar", "o"), "euro": ("EUR", "euro", "o"),
    "libra": ("GBP", "libra", "a"), "peso argentino": ("ARS", "peso argentino", "o"),
    "iene": ("JPY", "iene", "o"), "yuan": ("CNY", "yuan", "o"), "franco suico": ("CHF", "franco suíço", "o"),
    "dolar canadense": ("CAD", "dólar canadense", "o"), "dolar australiano": ("AUD", "dólar australiano", "o"),
}
CRIPTOS: dict[str, tuple[str, str]] = {
    "bitcoin": ("bitcoin", "bitcoin"), "btc": ("bitcoin", "bitcoin"),
    "ethereum": ("ethereum", "ethereum"), "ether": ("ethereum", "ethereum"), "eth": ("ethereum", "ethereum"),
    "solana": ("solana", "solana"), "dogecoin": ("dogecoin", "dogecoin"), "doge": ("dogecoin", "dogecoin"),
    "cardano": ("cardano", "cardano"), "xrp": ("ripple", "XRP"), "ripple": ("ripple", "XRP"),
    "litecoin": ("litecoin", "litecoin"), "ltc": ("litecoin", "litecoin"),
}
_ALTERNATIVAS = "|".join(sorted((re.escape(k) for k in list(MOEDAS) + list(CRIPTOS)), key=len, reverse=True))
RE_ATIVO = re.compile(rf"\b({_ALTERNATIVAS})\b")


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def ativos_citados(texto: str) -> list[tuple[str, str]]:
    """[("moeda","USD"), ("cripto","bitcoin")] na ordem em que aparecem, sem repetir."""
    vistos, saida = set(), []
    for m in RE_ATIVO.finditer(_norm(texto)):
        k = m.group(1)
        par = ("moeda", MOEDAS[k][0]) if k in MOEDAS else ("cripto", CRIPTOS[k][0])
        if par not in vistos:
            vistos.add(par)
            saida.append(par)
    return saida


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def reais_falados(v: float) -> str:
    """5.1463 -> "5 reais e 15 centavos"; 416322 -> "416 mil 322 reais"."""
    if v >= 1000:
        n = round(v)
        mil, resto = divmod(n, 1000)
        if mil >= 1000:
            mi, mil = divmod(mil, 1000)
            base = f"{mi} milh{'ão' if mi == 1 else 'ões'}" + (f" {mil} mil" if mil else "")
            return base + " de reais" if not resto else f"{base} e {resto} reais"
        return f"{mil} mil reais" if not resto else f"{mil} mil {resto} reais"
    reais, cent = divmod(round(v * 100), 100)
    if reais == 0:
        return f"{cent} centavos"
    r = f"{reais} rea{'l' if reais == 1 else 'is'}"
    return r if not cent else f"{r} e {cent} centavos"


def pct_falado(p: float) -> str:
    if abs(p) < 0.05:
        return "estável"
    s = f"{abs(p):.1f}".replace(".", ",").replace(",0", "")
    return f"{'alta' if p > 0 else 'queda'} de {s} por cento"


def hora_curta(ts: float | None) -> str:
    if not ts:
        return "horário não informado"
    d = datetime.fromtimestamp(ts)
    return f"{d.hour}h{d.minute:02d}" if d.date() == datetime.now().date() else d.strftime("%d/%m %Hh%M")


class Cotacoes:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._trava = threading.Lock()

    def _json(self, url: str) -> Any:
        with self._trava:
            g = self._cache.get(url)
        if g and time.time() - g[0] < VALIDADE_S:
            return g[1]
        dados = baixar_json(url)
        with self._trava:
            self._cache[url] = (time.time(), dados)
        return dados

    def moedas(self, codigos: list[str]) -> list[dict[str, Any]]:
        pares = ",".join(f"{c}-BRL" for c in codigos)
        dados = self._json(AWESOME + pares)
        saida = []
        for c in codigos:
            d = dados.get(f"{c}BRL")
            if not d:
                continue
            saida.append({"tipo": "moeda", "codigo": c, "nome": next(v[1] for v in MOEDAS.values() if v[0] == c),
                          "compra": float(d["bid"]), "venda": float(d["ask"]),
                          "variacao_pct": float(d.get("pctChange") or 0), "em": float(d.get("timestamp") or 0) or None,
                          "fonte": "AwesomeAPI", "url": "https://economia.awesomeapi.com.br/"})
        return saida

    def cripto(self, ids: list[str]) -> list[dict[str, Any]]:
        import urllib.parse
        url = COINGECKO + urllib.parse.urlencode({"ids": ",".join(ids), "vs_currencies": "brl,usd",
                                                   "include_24hr_change": "true", "include_last_updated_at": "true"})
        dados = self._json(url)
        saida = []
        for i in ids:
            d = dados.get(i)
            if not d or "brl" not in d:
                continue
            saida.append({"tipo": "cripto", "codigo": i, "nome": next(v[1] for v in CRIPTOS.values() if v[0] == i),
                          "brl": float(d["brl"]), "usd": float(d.get("usd") or 0),
                          "variacao_pct": float(d.get("brl_24h_change") or 0), "em": d.get("last_updated_at"),
                          "fonte": "CoinGecko", "url": f"https://www.coingecko.com/pt/moedas/{i}"})
        return saida

    def consultar(self, ativos: list[tuple[str, str]]) -> dict[str, Any]:
        moedas = [c for t, c in ativos if t == "moeda"]
        criptos = [c for t, c in ativos if t == "cripto"]
        itens: list[dict[str, Any]] = []
        falhas: list[str] = []
        if moedas:
            try:
                itens += self.moedas(moedas)
            except (*ERROS_REDE, KeyError) as e:
                falhas.append(f"AwesomeAPI: {type(e).__name__}")
        if criptos:
            try:
                itens += self.cripto(criptos)
            except (*ERROS_REDE, KeyError) as e:
                falhas.append(f"CoinGecko: {type(e).__name__}")
        return {"status": "medido" if itens else "erro", "itens": itens, "falhas": falhas, "em": time.time()}


def cotacao_falada(r: dict[str, Any]) -> str:
    if r.get("status") != "medido":
        return "Não consegui a cotação agora; a fonte não respondeu."
    frases = []
    for i in r["itens"]:
        if i["tipo"] == "moeda":
            art = next(v[2] for v in MOEDAS.values() if v[0] == i["codigo"])
            frases.append(f"{art.upper()} {i['nome']} está em {reais_falados(i['venda'])} na venda, "
                          f"{pct_falado(i['variacao_pct'])} no dia")
        else:
            frases.append(f"O {i['nome']} está em {reais_falados(i['brl'])}, "
                          f"{pct_falado(i['variacao_pct'])} em 24 horas")
    fontes = sorted({f"{i['fonte']}, {hora_curta(i['em'])}" for i in r["itens"]})
    return ". ".join(frases) + ". Fonte: " + "; ".join(fontes) + "."


def cartao(r: dict[str, Any]) -> dict[str, Any]:
    """Itens para o cartao de contexto do HUD."""
    itens = []
    for i in r.get("itens", []):
        valor = (f"R$ {i['venda']:.4f}".replace(".", ",") if i["tipo"] == "moeda"
                 else "R$ " + _milhar(round(i["brl"])) if i["brl"] >= 100 else f"R$ {i['brl']:.2f}".replace(".", ","))
        itens.append({"titulo": f"{i['nome']}: {valor}",
                      "detalhe": f"{'+' if i['variacao_pct'] >= 0 else ''}{i['variacao_pct']:.2f}%".replace(".", ",")
                                 + (" no dia" if i["tipo"] == "moeda" else " em 24 h"),
                      "fonte": f"{i['fonte']} · {hora_curta(i['em'])}", "link": i["url"]})
    return {"tipo": "cotacao", "titulo": "Cotações", "itens": itens}
