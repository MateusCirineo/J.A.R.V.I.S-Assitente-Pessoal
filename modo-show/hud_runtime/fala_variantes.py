"""O que o Senhor disse != o que as regras esperam.

Dois problemas reais de 19/09:

1. "Jarvis, memore o meu rosto" nao casou com nenhuma regra (elas esperavam
   "memoriz..."), foi parar no modelo -- que nao sabia do cadastro de rostos e
   RECUSOU. Aqui ficam as variantes da fala do dia a dia; `corrigir()` so vale
   se a frase corrigida casar com alguma regra (quem decide e o chamador).

2. "Jarvis, que horas sao? Jarvis, me lembre de ligar" chegou como UMA frase
   (duas falas grudadas pelo microfone) e virou um lembrete com o texto errado.
   `separar_pedidos()` quebra a frase onde o Senhor chama o Jarvis de novo.

Nada aqui adivinha intencao: sao trocas de palavra por palavra, cada uma com o
motivo ao lado.
"""

from __future__ import annotations

import re
import unicodedata

# (regra, troca). O texto ja chega normalizado (minusculo, sem acento) quando
# vem de interpretar(); as regras abaixo funcionam nos dois casos.
VARIANTES: list[tuple[re.Pattern[str], str]] = [
    # "memore/memora/memoriza/memorizar" -> "memorize" (sem tocar em "memoria")
    (re.compile(r"\bmemor(?!ia|ias|izar\b)\w*\b", re.I), "memorize"),
    (re.compile(r"\bmemorizar\b", re.I), "memorize"),
    # "decore o meu rosto", "decora minha voz"
    (re.compile(r"\bdecor(?:e|a|ar|ou)\b", re.I), "memorize"),
    # "cadastra/cadastrar", "registra", "guarda", "salva", "grava" no imperativo falado
    (re.compile(r"\bcadastr(?:a|ar)\b", re.I), "cadastre"),
    (re.compile(r"\bregistr(?:a|ar)\b", re.I), "registre"),
    # a cara / a minha face -> rosto (so depois de um verbo de cadastro)
    (re.compile(r"\b(memorize|cadastre|registre|grave|guarde|salve|aprenda)\s+"
                r"(?:a\s+|minha\s+|a\s+minha\s+|o\s+meu\s+)?(?:cara|face|fisionomia)\b", re.I), r"\1 o meu rosto"),
    # "aprende", "aprenda a reconhecer" -> aprenda
    (re.compile(r"\baprend(?:e|er)\b", re.I), "aprenda"),
    # "se lembra de mim?" nao entra aqui de proposito: e pergunta, nao cadastro.
    # "quem ta ai", "quem que ta aqui" (com e sem acento: a fala chega dos dois jeitos)
    (re.compile(r"\bquem que (?:esta|está|ta|tá|e|é)\b", re.I), "quem esta"),
    # verbos de acao que a transcricao costuma trazer no infinitivo
    (re.compile(r"\bmedir\b", re.I), "meca"),
    (re.compile(r"\besquecer\b", re.I), "esqueca"),
    (re.compile(r"\bapagar\b", re.I), "apague"),
    (re.compile(r"\babrir\b", re.I), "abra"),
    (re.compile(r"\bdesligar\b", re.I), "desligue"),
    (re.compile(r"\bligar\b(?!\s+(?:para|pra|pro)\b)", re.I), "ligue"),
]

_CHAMADO = r"(?:jarvis|jarbas|jarvas|jervis|djarvis)"
# o Senhor chamando o Jarvis DE NOVO no meio da frase = comecou outro pedido
_OUTRO_PEDIDO = re.compile(rf"(?<=.)[\s,.;!?]+{_CHAMADO}\b[\s,]*", re.I)

# A conjunção sozinha não basta: dois verbos precisam iniciar cláusulas
# independentes. Isto só escolhe a rota; nunca corta o texto entregue ao modelo.
_ACAO_INDEPENDENTE = (
    r"(?:calcule|calcular|converta|converter|some|multiplique|divida|subtraia|"
    r"abra|abrir|feche|fechar|ligue|ligar|desligue|desligar|"
    r"mostre|mostrar|liste|listar|pesquise|pesquisar|procure|busque|"
    r"analise|analisar|compare|comparar|identifique|verifique|confira|"
    r"explique|explicar|resuma|resumir|leia|ler|diga|me diga|me mostre|"
    r"toque|tocar|pause|pausar|aumente|diminua|reduza|"
    r"crie|criar|gere|gerar|prepare|preparar|"
    r"quanto (?:e|eh)|que horas (?:sao|sao agora))\b"
)
_SEPARADOR_ACOES = re.compile(
    rf"(?:\s+(?:e\s+depois|e\s+em\s+seguida|em\s+seguida|depois|e\s+entao|e)\s+|[;,]\s*)"
    rf"(?=(?:por favor\s+)?{_ACAO_INDEPENDENTE})")
_INICIO_ACAO = re.compile(rf"^(?:por favor\s+)?{_ACAO_INDEPENDENTE}")
_CONTEUDO_LITERAL = re.compile(
    r"\b(?:protocolo|rascunho|mensagem|email|e-mail|lista|nota|anote|anotar|"
    r"memorize|memorizar|memore|cadastre|cadastrar|registre|registrar|"
    r"lembre|lembrar|guarde|guardar|escreva|escrever|dite|ditar)\b")


def pedido_composto(texto: str) -> bool:
    """Duas ações independentes devem chegar inteiras ao executor com ferramentas.

    Textos de cadastro, listas, notas, lembretes, protocolos e rascunhos ficam
    com os handlers próprios. Aspas e negações não são reinterpretadas aqui.
    Não tenta resolver linguagem aberta nem autoriza nenhuma ação.
    """
    normal = unicodedata.normalize("NFKD", texto or "").lower()
    normal = "".join(c for c in normal if not unicodedata.combining(c))
    normal = re.sub(rf"^\s*{_CHAMADO}\b[\s,;:]*", "", normal).strip()
    normal = re.sub(r"^(?:voce pode|pode|poderia|quero que voce)\s+", "", normal)
    if _CONTEUDO_LITERAL.search(normal) or re.search(r"\b(?:nao|nunca|nem|sem)\b", normal):
        return False
    if any(c in normal for c in ('"', "'", "“", "”", "‘", "’", '`')):
        return False
    partes = _SEPARADOR_ACOES.split(normal)
    return len(partes) >= 2 and all(_INICIO_ACAO.match(p.strip()) for p in partes)


def pedido_so_calculos(texto: str) -> bool:
    """Restringe o catálogo para contas explícitas, sem resolver ou executar nada.

    Cada cláusula precisa pedir cálculo com operandos numéricos. Referências,
    conteúdo literal, negações e mistura com outra ação mantêm o catálogo geral.
    """
    normal = unicodedata.normalize("NFKD", texto or "").lower()
    normal = "".join(c for c in normal if not unicodedata.combining(c))
    normal = re.sub(rf"^\s*{_CHAMADO}\b[\s,;:]*", "", normal).strip()
    normal = re.sub(r"^(?:voce pode|pode|poderia|quero que voce)\s+", "", normal)
    if _CONTEUDO_LITERAL.search(normal) or re.search(r"\b(?:nao|nunca|nem|sem|isso|isto|esse|essa|anterior)\b", normal):
        return False
    if any(c in normal for c in ('"', "'", "“", "”", "‘", "’", '`')):
        return False
    partes = _SEPARADOR_ACOES.split(normal)
    return bool(partes) and all(re.match(r"^(?:por favor\s+)?(?:calcule|calcular|some|multiplique|divida|subtraia)\b", p.strip())
                               and re.search(r"\d", p) for p in partes)


def corrigir(texto: str) -> str:
    """Troca as variantes conhecidas. Pode devolver o proprio texto."""
    saida = texto
    for regra, troca in VARIANTES:
        saida = regra.sub(troca, saida)
    return saida


def mudou(texto: str) -> bool:
    return corrigir(texto) != texto


def separar_pedidos(texto: str) -> list[str]:
    """Duas falas grudadas viram dois pedidos; uma fala so continua inteira.

    "Jarvis, que horas sao? Jarvis, me lembre de ligar" ->
    ["Jarvis, que horas sao?", "me lembre de ligar"]
    """
    t = (texto or "").strip()
    if not t:
        return []
    partes = [p.strip(" ,.;") for p in _OUTRO_PEDIDO.split(t)]
    partes = [p for p in partes if len(p) >= 3]
    return partes or [t]
