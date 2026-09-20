"""Rascunhos de comunicacao (e-mail, mensagem) que NUNCA sao enviados.

"Jarvis, escreva um e-mail para o Pedro dizendo que vou atrasar 20 minutos."
O modelo local redige; o texto vai para a tela, para a area de transferencia e
para ~/.openjarvis/rascunhos/. "Abra o rascunho no Gmail" abre a janela de
escrever do Gmail ja preenchida: quem aperta Enviar e o usuario.

O modelo e instruido a nao inventar fatos, datas ou nomes: o que faltar vira
[colchetes] para completar. Sem assinatura com nome inventado.
"""

from __future__ import annotations

import os
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
PASTA = HOME / "rascunhos"

SISTEMA = ("Você redige rascunhos curtos em português do Brasil para o usuário revisar e enviar ele mesmo. "
           "Escreva só o texto pedido, sem comentários antes ou depois. "
           "Para e-mail, a primeira linha é 'Assunto: ...', depois uma linha em branco e o corpo. "
           "Não invente fatos, datas, números, endereços ou nomes que não estejam no pedido: "
           "o que faltar, escreva entre [colchetes] para o usuário completar. "
           "Termine com [seu nome] no lugar da assinatura.")


def tipo_do_pedido(pedido: str) -> str:
    return "email" if re.search(r"\be-?mails?\b", pedido, re.I) else "mensagem"


def destinatario(pedido: str) -> str | None:
    m = re.search(r"\bpara (?:o |a |os |as |meu |minha )?(?P<p>(?!dizer|avisar|falar|pedir|contar|que\b)"
                  r"[A-Za-zÀ-ÿ][\wÀ-ÿ]*(?: [A-Z][\wÀ-ÿ]*)?)", pedido)
    return m.group("p") if m else None


def separar(texto: str, tipo: str) -> tuple[str | None, str]:
    """ "Assunto: X\\n\\ncorpo" -> ("X", "corpo")."""
    texto = texto.strip().strip("`").strip()
    m = re.match(r"^\s*\**assunto\**\s*:\s*(?P<a>.+?)\s*(?:\n|$)", texto, re.I)
    if m:
        return m.group("a").strip(" *"), texto[m.end():].strip()
    return None, texto


def copiar(texto: str) -> bool:
    """Area de transferencia do Windows (texto Unicode)."""
    try:
        import ctypes
        from ctypes import wintypes
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        k32.GlobalAlloc.restype = wintypes.HGLOBAL
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        dados = (texto + "\0").encode("utf-16-le")
        if not u32.OpenClipboard(None):
            return False
        try:
            u32.EmptyClipboard()
            h = k32.GlobalAlloc(0x0042, len(dados))            # GMEM_MOVEABLE | GMEM_ZEROINIT
            p = k32.GlobalLock(h)
            ctypes.memmove(p, dados, len(dados))
            k32.GlobalUnlock(h)
            return bool(u32.SetClipboardData(13, h))           # CF_UNICODETEXT
        finally:
            u32.CloseClipboard()
    except (OSError, AttributeError):
        return False


def url_gmail(r: dict[str, Any]) -> str:
    q = {"view": "cm", "fs": "1", "body": r["corpo"]}
    if r.get("assunto"):
        q["su"] = r["assunto"]
    return "https://mail.google.com/mail/?" + urllib.parse.urlencode(q)


class Rascunhos:
    def __init__(self, gerar: Callable[[list[dict[str, Any]]], str], pasta: Path = PASTA,
                 copiar_fn: Callable[[str], bool] = copiar) -> None:
        self._gerar = gerar
        self._pasta = pasta
        self._copiar = copiar_fn
        self.ultimo: dict[str, Any] | None = None

    def criar(self, pedido: str) -> dict[str, Any]:
        tipo = tipo_do_pedido(pedido)
        bruto = self._gerar([{"role": "system", "content": SISTEMA},
                             {"role": "user", "content": f"Redija {'um e-mail' if tipo == 'email' else 'uma mensagem curta'}: {pedido}"}])
        from .modelo import limpar
        assunto, corpo = separar(limpar(bruto), tipo)
        texto = (f"Assunto: {assunto}\n\n{corpo}" if assunto else corpo).strip()
        self._pasta.mkdir(parents=True, exist_ok=True)
        arquivo = self._pasta / f"rascunho-{datetime.now():%Y%m%d-%H%M%S}.txt"
        arquivo.write_text(f"Pedido: {pedido}\n\n{texto}\n", encoding="utf-8")
        r = {"tipo": tipo, "para": destinatario(pedido), "assunto": assunto, "corpo": corpo, "texto": texto,
             "arquivo": str(arquivo), "copiado": self._copiar(texto), "em": time.time()}
        self.ultimo = r
        return r


def fala(r: dict[str, Any]) -> str:
    que = "E-mail" if r["tipo"] == "email" else "Mensagem"
    para = f" para {r['para']}" if r.get("para") else ""
    assunto = f", assunto: {r['assunto']}" if r.get("assunto") else ""
    copia = " Copiei o texto." if r.get("copiado") else ""
    return f"Rascunho pronto: {que.lower()}{para}{assunto}.{copia} Está na tela; nada foi enviado."


def cartao(r: dict[str, Any]) -> dict[str, Any]:
    que = "e-mail" if r["tipo"] == "email" else "mensagem"
    return {"tipo": "rascunho", "titulo": f"Rascunho · {que}{' para ' + r['para'] if r.get('para') else ''}",
            "itens": [{"titulo": r.get("assunto") or "Mensagem", "detalhe": r["corpo"][:700],
                       "fonte": ("copiado · " if r.get("copiado") else "") + "não enviado · " + Path(r["arquivo"]).name}]}
