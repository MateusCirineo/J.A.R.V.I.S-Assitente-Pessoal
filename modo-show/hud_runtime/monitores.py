"""Monitores que o proprio usuario cria por voz (P2), listaveis e pausaveis.

"me avise quando sair notícia sobre a Nvidia"   -> noticia (30 min)
"me avise quando o dólar passar de 5,50"          -> cotacao (10 min, dispara uma vez)
"monitore o site g1.globo.com/economia"          -> site (30 min, mudanca real de texto)
"fique de olho na pasta Downloads"               -> pasta (2 min, arquivo novo)
"quais são meus monitores" / "pause o monitor da Nvidia" / "remova o monitor do dólar"

A primeira verificacao so registra o estado atual (linha de base): nada do que
ja existia e anunciado. Fica em ~/.openjarvis/hud-monitores.json. So paginas
publicas https; nada de login, cookie ou formulario.
"""

from __future__ import annotations

import difflib
import html
import json
import os
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
INTERVALOS = {"noticia": 30 * 60, "cotacao": 10 * 60, "site": 30 * 60, "pasta": 120}
MAX_MONITORES = 20
LIMIAR_SITE = 0.93                     # texto menos parecido que isso = mudou de verdade (anuncio rotativo nao)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def numero_falado(txt: str) -> float | None:
    """ "5,50" -> 5.5; "400 mil" -> 400000; "1.200" -> 1200."""
    m = re.fullmatch(r"\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?\s*(mil)?\s*", txt)
    if not m:
        m2 = re.fullmatch(r"\s*(\d+)\.(\d{1,2})\s*(mil)?\s*", txt)            # "5.50" dito como decimal
        if not m2:
            return None
        v = float(f"{m2.group(1)}.{m2.group(2)}")
        return v * 1000 if m2.group(3) else v
    v = float(m.group(1).replace(".", "") + (f".{m.group(2)}" if m.group(2) else ""))
    return v * 1000 if m.group(3) else v


def texto_da_pagina(conteudo: bytes) -> str:
    s = conteudo.decode("utf-8", "replace")
    s = re.sub(r"(?is)<(script|style|noscript|svg|head)\b.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return " ".join(html.unescape(s).split())[:20000]


def descrever(m: dict[str, Any]) -> str:
    if m["tipo"] == "noticia":
        return f"notícias sobre {m['alvo']}"
    if m["tipo"] == "cotacao":
        v = f"{m['limite']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{m['nome']} {'acima' if m['direcao'] == 'acima' else 'abaixo'} de R$ {v}"
    if m["tipo"] == "site":
        endereco = re.sub(r"^https://(?:www\.)?", "", m["alvo"])
        return f"o site {endereco[:60]}"
    return f"a pasta {Path(m['alvo']).name}"


class Monitores(threading.Thread):
    def __init__(self, avisar: Callable[[str], None], noticias: Any = None, cotacoes: Any = None,
                 baixar: Callable[[str], bytes] | None = None, arquivo: Path = HOME / "hud-monitores.json",
                 ao_mudar: Callable[[list[dict[str, Any]]], None] | None = None) -> None:
        super().__init__(name="monitores", daemon=True)
        self._avisar = avisar
        self._noticias = noticias
        self._cotacoes = cotacoes
        self._baixar = baixar
        self._arquivo = arquivo
        self._ao_mudar = ao_mudar or (lambda itens: None)
        self._trava = threading.RLock()
        self._encerrar = threading.Event()

    # ---- persistencia -------------------------------------------------------
    def listar(self) -> list[dict[str, Any]]:
        try:
            dados = json.loads(self._arquivo.read_text(encoding="utf-8"))
            return dados if isinstance(dados, list) else []
        except (OSError, ValueError):
            return []

    def _gravar(self, itens: list[dict[str, Any]]) -> None:
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._arquivo)
        self._ao_mudar(self.publico(itens))

    def publico(self, itens: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        return [{"id": m["id"], "tipo": m["tipo"], "descricao": descrever(m), "ativo": m["ativo"],
                 "disparos": m.get("disparos", 0), "verificado_em": m.get("verificado_em")}
                for m in (itens if itens is not None else self.listar())]

    # ---- criar / mudar -------------------------------------------------------
    def criar(self, tipo: str, alvo: str, **extra: Any) -> dict[str, Any]:
        if tipo not in INTERVALOS:
            raise ValueError("tipo de monitor desconhecido")
        if tipo == "site" and not alvo.startswith("https://"):
            raise ValueError("só monitoro sites https")
        if tipo == "pasta" and not Path(alvo).is_dir():
            raise ValueError("essa pasta não existe")
        with self._trava:
            itens = self.listar()
            if len([m for m in itens if m["ativo"]]) >= MAX_MONITORES:
                raise ValueError(f"já há {MAX_MONITORES} monitores ativos")
            for m in itens:
                if m["tipo"] == tipo and _norm(m["alvo"]) == _norm(alvo) and m.get("limite") == extra.get("limite"):
                    m["ativo"] = True
                    self._gravar(itens)
                    return m
            m = {"id": max([x["id"] for x in itens] + [0]) + 1, "tipo": tipo, "alvo": alvo[:300], "ativo": True,
                 "criado": time.time(), "verificado_em": None, "base": None, "disparos": 0, **extra}
            itens.append(m)
            self._gravar(itens)
        return m

    def achar(self, frase: str) -> list[dict[str, Any]]:
        n = _norm(frase)
        palavras = {p for p in re.findall(r"\w{3,}", n)} - {"monitor", "monitores", "remova", "remove", "apague",
                                                             "pause", "pausa", "retome", "reative", "cancele", "desative",
                                                             "jarvis", "sobre", "noticias", "noticia", "site", "pasta"}
        itens = self.listar()
        if not palavras:
            return itens if len(itens) == 1 else []
        return [m for m in itens if palavras & set(re.findall(r"\w{3,}", _norm(descrever(m) + " " + m["alvo"])))]

    def mudar(self, ids: list[int], ativo: bool | None) -> int:
        """ativo=True/False pausa ou retoma; None remove."""
        with self._trava:
            itens = self.listar()
            n = 0
            novos = []
            for m in itens:
                if m["id"] in ids:
                    n += 1
                    if ativo is None:
                        continue
                    m["ativo"] = ativo
                novos.append(m)
            self._gravar(novos)
        return n

    # ---- verificacao ---------------------------------------------------------
    def _checar(self, m: dict[str, Any]) -> str | None:
        """Atualiza m['base'] e devolve o aviso (ou None)."""
        tipo, base = m["tipo"], m.get("base")
        if tipo == "noticia":
            r = self._noticias.buscar(m["alvo"], limite=10)
            if r.get("status") != "medido":
                return None
            links = [i["link"] for i in r["itens"] if i.get("link")]
            if base is None:
                m["base"] = links[:50]
                return None
            novos = [i for i in r["itens"] if i.get("link") and i["link"] not in base]
            m["base"] = (links + base)[:80]
            if novos:
                n = novos[0]
                return f"saiu notícia sobre {m['alvo']}: {n['titulo'].rstrip('.')}, {n['fonte']}."
            return None
        if tipo == "cotacao":
            r = self._cotacoes.consultar([(m["classe"], m["codigo"])])
            if r.get("status") != "medido" or not r["itens"]:
                return None
            i = r["itens"][0]
            valor = i["venda"] if i["tipo"] == "moeda" else i["brl"]
            passou = valor > m["limite"] if m["direcao"] == "acima" else valor < m["limite"]
            m["base"] = valor
            if passou:
                m["ativo"] = False                     # dispara uma vez
                from .cotacoes import reais_falados
                return (f"o {i['nome']} {'passou de' if m['direcao'] == 'acima' else 'caiu abaixo de'} "
                        f"{reais_falados(m['limite'])}: está em {reais_falados(valor)}. Desativei esse monitor.")
            return None
        if tipo == "site":
            texto = texto_da_pagina(self._baixar(m["alvo"]))
            if base is None:
                m["base"] = texto
                return None
            parecido = difflib.SequenceMatcher(None, base, texto, autojunk=False).quick_ratio()
            if parecido < LIMIAR_SITE:
                m["base"] = texto
                return f"{descrever(m)} mudou."
            return None
        if tipo == "pasta":
            try:
                nomes = sorted(p.name for p in Path(m["alvo"]).iterdir() if p.is_file() and not p.name.startswith("~$")
                               and not p.suffix.lower() in (".tmp", ".crdownload", ".part"))
            except OSError:
                return None
            if base is None:
                m["base"] = nomes[-500:]
                return None
            novos = [n for n in nomes if n not in set(base)]
            m["base"] = nomes[-500:]
            if novos:
                return f"arquivo novo em {Path(m['alvo']).name}: {novos[0]}" + (f" e mais {len(novos) - 1}." if len(novos) > 1 else ".")
            return None
        return None

    def verificar(self, agora: float | None = None, forcar: bool = False) -> list[str]:
        agora = agora or time.time()
        avisos = []
        with self._trava:
            itens = self.listar()
            mudou = False
            for m in itens:
                if not m["ativo"]:
                    continue
                if not forcar and m.get("verificado_em") and agora - m["verificado_em"] < INTERVALOS[m["tipo"]]:
                    continue
                try:
                    aviso = self._checar(m)
                except Exception:  # noqa: BLE001 - site fora do ar nao derruba os outros monitores
                    aviso = None
                m["verificado_em"] = agora
                mudou = True
                if aviso:
                    m["disparos"] = m.get("disparos", 0) + 1
                    avisos.append(aviso)
            if mudou:
                self._gravar(itens)
        for a in avisos:
            try:
                self._avisar(a)
            except Exception:  # noqa: BLE001
                pass
        return avisos

    def encerrar(self) -> None:
        self._encerrar.set()

    def run(self) -> None:
        self._ao_mudar(self.publico())
        while not self._encerrar.wait(60):
            self.verificar()

