"""Contexto de conversa para comandos (o Jarvis entende a frase incompleta):

    "que horas são em Tóquio?"  ->  "e em Londres?"
    "quanto está o dólar?"      ->  "e o euro?"
    "notícias de tecnologia"    ->  "e de esportes?" / "e sobre a Nvidia?"
    "adicione leite à lista"    ->  "adicione também ovos"
    "onde está meu celular?"    ->  "e o controle?"

Vale por 2 minutos depois do ultimo comando. Frases longas (mais de 7
palavras) nao sao tratadas como continuacao.
"""

from __future__ import annotations

import re
import unicodedata

VALIDADE_S = 120


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"^\W*(?:jarvis|jarbas)\W*", "", t)
    return " ".join(t.strip(" ?.!,").split())


def continuar(texto: str, ultimo: tuple[str, str, float] | None, agora: float) -> str | None:
    """Frase curta de continuacao -> frase completa, usando o ultimo comando. None = nao e continuacao."""
    if not ultimo or agora - ultimo[2] > VALIDADE_S:
        return None
    n = _norm(texto)
    if not n or len(n.split()) > 7:
        return None
    nome, frase, _ = ultimo
    e = re.match(r"^(?:e|e ai|e quanto a|e sobre|tambem)\b\s*(?P<resto>.*)$", n)
    if nome == "lista_add":
        m = re.match(r"^(?:adicion\w*|coloq\w*|pon\w*|bot\w*|inclu\w*|acrescent\w*) (?:tambem|mais) (?P<x>.+)$", n)
        lista = re.search(r"\blista(?: (?:de|do|da) (?P<l>[\w\s]+?))?\W*$", _norm(frase))
        if m:
            return f"adicione {m.group('x')} à lista de {(lista.group('l') if lista and lista.group('l') else 'compras')}"
    if not e:
        return None
    resto = e.group("resto").strip()
    lugar = re.sub(r"^(?:la |em |no |na |nos |nas |de |do |da )+", "", resto)
    coisa = re.sub(r"^(?:o |a |os |as |do |da |de |meu |minha )+", "", resto)
    if not resto:
        return None
    if nome == "hora_mundo":
        return f"que horas são em {lugar}"
    if nome == "clima_mundo":
        return f"como está o clima em {lugar}"
    if nome == "cotacao":
        return f"quanto está o {coisa}"
    if nome == "noticias":
        if resto.startswith("sobre ") or not re.match(r"^(?:de |do |da )", resto):
            return f"notícias sobre {re.sub(r'^sobre ', '', resto)}"
        return f"notícias de {lugar}"
    if nome == "percepcao_onde":
        return f"onde está o {coisa}"
    if nome == "percepcao_contar":
        return f"quantos {coisa} você vê"
    if nome == "medir":
        return f"quanto mede o {coisa}"
    if nome == "conversao" and re.match(r"^(?:em|para) ", resto):
        return re.sub(r"\b(?:em|para|pra) [\w\s]+?\W*$", resto, _norm(frase))
    return None
