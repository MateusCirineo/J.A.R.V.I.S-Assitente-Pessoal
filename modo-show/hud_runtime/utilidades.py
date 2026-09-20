"""O que uma Alexa responde na hora, sem o modelo (e sem errar conta):

- contas: "quanto é 15% de 230", "12 vezes 8", "raiz quadrada de 144", "2 elevado a 10"
- conversoes: "10 milhas em km", "30 graus celsius em fahrenheit", "5 quilos em libras",
  "100 dólares em reais", "meio bitcoin em reais" (cotacao do momento, com fonte)
- mundo: "que horas são em Tóquio", "clima em Paris" (qualquer cidade, Open-Meteo)
- datas: "quantos dias faltam para o Natal", "que dia da semana cai 25 de dezembro",
  "que dia será daqui a 45 dias"
- sorte: "jogue uma moeda", "role um dado", "sorteie um número de 1 a 100",
  "escolha entre pizza e hambúrguer"

Numeros falados por extenso ("vinte e cinco", "mil e duzentos") viram digitos.
As contas sao feitas por uma arvore de expressao so com numeros e + - * / ** (nada
de eval de texto).
"""

from __future__ import annotations

import ast
import math
import operator
import random
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

# ---- numeros por extenso ---------------------------------------------------------
_UNI = {"zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
        "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "quatorze": 14,
        "catorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
        "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70,
        "oitenta": 80, "noventa": 90, "cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200,
        "trezentos": 300, "quatrocentos": 400, "quinhentos": 500, "seiscentos": 600, "setecentos": 700,
        "oitocentos": 800, "novecentos": 900}
_PALAVRA_NUM = "|".join(sorted(_UNI, key=len, reverse=True))
_SEQ = re.compile(rf"\b(?:(?:{_PALAVRA_NUM}|mil)(?:\s+e\s+|\s+)?)+\b")


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def _valor_extenso(trecho: str) -> int | None:
    total, parcial = 0, 0
    for p in re.findall(rf"{_PALAVRA_NUM}|mil", trecho):
        if p == "mil":
            total += (parcial or 1) * 1000
            parcial = 0
        else:
            parcial += _UNI[p]
    return total + parcial


def digitos(texto: str) -> str:
    """ "quanto é vinte e cinco por cento de mil e duzentos" -> "... 25 por cento de 1200"."""
    n = _norm(texto)
    n = re.sub(r"\bmeio\b|\bmeia\b(?= (?:bitcoin|quilo|litro|metro|hora|xicara))", "0,5", n)
    n = re.sub(r"\bpor cento\b", "%", n)                 # senao o "cento" vira 100
    n = re.sub(r"\bum %", "1 %", n)

    def troca(m: re.Match) -> str:
        if m.group(0).strip() in ("um", "uma"):              # "jogue uma moeda": artigo, nao numero
            return m.group(0)
        v = _valor_extenso(m.group(0))
        fim = " " if m.group(0).endswith(" ") else ""
        return f"{v}{fim}" if v is not None else m.group(0)
    return _SEQ.sub(troca, n)


def _num(txt: str) -> float:
    txt = txt.strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", txt):             # 1.200,50
        return float(txt.replace(".", "").replace(",", "."))
    return float(txt.replace(",", "."))


def falar_numero(v: float) -> str:
    if abs(v - round(v)) < 1e-9:
        return f"{round(v):,}".replace(",", ".")
    s = f"{v:,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ---- contas ------------------------------------------------------------------------
NUM = r"-?\d+(?:[.,]\d+)*"
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg}


def _avaliar(no: ast.AST) -> float:
    if isinstance(no, ast.Expression):
        return _avaliar(no.body)
    if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
        return float(no.value)
    if isinstance(no, ast.BinOp) and type(no.op) in _OPS:
        a, b = _avaliar(no.left), _avaliar(no.right)
        if isinstance(no.op, ast.Pow) and abs(b) > 100:
            raise ValueError("expoente grande demais")
        return _OPS[type(no.op)](a, b)
    if isinstance(no, ast.UnaryOp) and type(no.op) in _OPS:
        return _OPS[type(no.op)](_avaliar(no.operand))
    raise ValueError("expressão não permitida")


def calcular(frase: str) -> str | None:
    n = digitos(frase)
    m = re.search(rf"({NUM})\s*%\s+de\s+({NUM})", n)
    if m:
        a, b = _num(m.group(1)), _num(m.group(2))
        return f"{falar_numero(a)} por cento de {falar_numero(b)} é {falar_numero(a * b / 100)}."
    m = re.search(rf"raiz (?:quadrada )?de ({NUM})", n)
    if m:
        a = _num(m.group(1))
        return f"A raiz quadrada de {falar_numero(a)} é {falar_numero(math.sqrt(a))}." if a >= 0 else None
    expr = n
    for de, para in ((r"\bao quadrado\b", "**2"), (r"\bao cubo\b", "**3"), (r"\belevado (?:a|ao|na)\b", "**"),
                     (r"\bmultiplicado por\b|\bvezes\b|\bx\b", "*"), (r"\bdividido por\b|\bsobre\b", "/"),
                     (r"\bmais\b", "+"), (r"\bmenos\b", "-")):
        expr = re.sub(de, f" {para} ", expr)
    m = re.search(rf"{NUM}(?:\s*(?:\*\*|[-+*/])\s*{NUM})+", expr)
    if not m:
        return None
    texto = re.sub(NUM, lambda k: repr(_num(k.group(0))), m.group(0))
    try:
        v = _avaliar(ast.parse(texto, mode="eval"))
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
        return "Essa conta não tem resultado." if "/" in texto else None
    return f"Dá {falar_numero(v)}."


# ---- conversoes ----------------------------------------------------------------------
UNIDADES = {  # nome falado -> (grandeza, fator para a unidade base)
    "quilometros": ("dist", 1000), "quilometro": ("dist", 1000), "km": ("dist", 1000),
    "metros": ("dist", 1), "metro": ("dist", 1), "centimetros": ("dist", 0.01), "centimetro": ("dist", 0.01),
    "cm": ("dist", 0.01), "milhas": ("dist", 1609.344), "milha": ("dist", 1609.344), "pes": ("dist", 0.3048),
    "pe": ("dist", 0.3048), "polegadas": ("dist", 0.0254), "polegada": ("dist", 0.0254), "jardas": ("dist", 0.9144),
    "quilos": ("massa", 1), "quilo": ("massa", 1), "kg": ("massa", 1), "quilogramas": ("massa", 1),
    "gramas": ("massa", 0.001), "grama": ("massa", 0.001), "libras": ("massa", 0.45359237),
    "libra": ("massa", 0.45359237), "oncas": ("massa", 0.0283495), "onca": ("massa", 0.0283495),
    "litros": ("vol", 1), "litro": ("vol", 1), "mililitros": ("vol", 0.001), "ml": ("vol", 0.001),
    "galoes": ("vol", 3.78541), "galao": ("vol", 3.78541),
    "celsius": ("temp", "c"), "fahrenheit": ("temp", "f"), "kelvin": ("temp", "k"),
}
MOEDAS_CONV = {"dolares": "USD", "dolar": "USD", "euros": "EUR", "euro": "EUR", "libras esterlinas": "GBP",
               "reais": "BRL", "real": "BRL", "bitcoins": "bitcoin", "bitcoin": "bitcoin", "ethereum": "ethereum"}
_UNID_RX = "|".join(sorted(list(UNIDADES) + list(MOEDAS_CONV), key=len, reverse=True))
_CONV = re.compile(rf"({NUM})\s*(?:graus\s+)?({_UNID_RX})\b\s+(?:em|para|pra)\s+(?:graus\s+)?({_UNID_RX})\b")


def _temp(v: float, de: str, para: str) -> float:
    c = v if de == "c" else (v - 32) * 5 / 9 if de == "f" else v - 273.15
    return c if para == "c" else c * 9 / 5 + 32 if para == "f" else c + 273.15


def converter(frase: str, cotacoes: Any = None) -> str | None:
    m = _CONV.search(digitos(frase))
    if not m:
        return None
    v, de, para = _num(m.group(1)), m.group(2), m.group(3)
    if de in MOEDAS_CONV or para in MOEDAS_CONV:
        return _converter_moeda(v, MOEDAS_CONV.get(de), MOEDAS_CONV.get(para), de, para, cotacoes)
    (g1, f1), (g2, f2) = UNIDADES[de], UNIDADES[para]
    if g1 != g2:
        return f"Não dá para converter {de} em {para}."
    r = _temp(v, f1, f2) if g1 == "temp" else v * f1 / f2
    return f"{falar_numero(v)} {de} são {falar_numero(round(r, 2))} {para}."


ACENTOS_MOEDA = {"dolares": "dólares", "dolar": "dólar"}


def _converter_moeda(v: float, de: str | None, para: str | None, nome_de: str, nome_para: str, cotacoes: Any) -> str:
    from .cotacoes import hora_curta, reais_falados
    nome_de, nome_para = ACENTOS_MOEDA.get(nome_de, nome_de), ACENTOS_MOEDA.get(nome_para, nome_para)
    if not de or not para or cotacoes is None:
        return "Só converto entre reais, dólar, euro, libra, bitcoin e ethereum."
    ativo = de if para == "BRL" else para
    if ativo == "BRL" or (de != "BRL" and para != "BRL"):
        return "Converto de ou para reais: por exemplo, 100 dólares em reais."
    classe = "cripto" if ativo in ("bitcoin", "ethereum") else "moeda"
    r = cotacoes.consultar([(classe, ativo)])
    if r.get("status") != "medido" or not r["itens"]:
        return "A cotação não respondeu agora."
    i = r["itens"][0]
    preco = i["venda"] if classe == "moeda" else i["brl"]
    fonte = f"cotação {i['fonte']}, {hora_curta(i['em'])}"
    if para == "BRL":
        return f"{falar_numero(v)} {nome_de} são {reais_falados(v * preco)}, pela {fonte}."
    return f"{reais_falados(v)} são {falar_numero(round(v / preco, 6 if classe == 'cripto' else 2))} {nome_para}, pela {fonte}."


# ---- mundo: hora e clima de qualquer cidade ----------------------------------------------
APELIDOS_CIDADE = {"nova york": "Nova Iorque", "ny": "Nova Iorque", "nova iorque": "Nova Iorque",
                   "la": "Los Angeles", "tokyo": "Tóquio", "toquio": "Tóquio", "londres": "Londres"}


def achar_cidade(nome: str) -> dict[str, Any] | None:
    """A mais populosa entre as candidatas ("Paris" e a da Franca, nao a do Texas)."""
    from .clima import GEOCODIFICACAO, _get
    nome = APELIDOS_CIDADE.get(_norm(nome).strip(" ?.!"), nome.strip(" ?.!"))
    d = _get(GEOCODIFICACAO, {"name": nome, "count": 5, "language": "pt", "format": "json"})
    candidatas = d.get("results") or []
    if not candidatas:
        return None
    r = max(candidatas, key=lambda c: c.get("population") or 0)
    return {"nome": r["name"], "regiao": r.get("admin1"), "pais": r.get("country"), "lat": r["latitude"],
            "lon": r["longitude"], "fuso": r.get("timezone")}


def hora_em(cidade: str, agora: datetime | None = None) -> str:
    from zoneinfo import ZoneInfo
    c = achar_cidade(cidade)
    if not c or not c.get("fuso"):
        return f"Não achei a cidade {cidade}."
    local = (agora or datetime.now(ZoneInfo("America/Sao_Paulo"))).astimezone(ZoneInfo(c["fuso"]))
    from .voz import hora_falada
    dia = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"][local.weekday()]
    return f"Em {c['nome']}, {c.get('pais') or ''}, são {hora_falada(local)} de {dia}.".replace(", ,", ",")


# ---- datas -----------------------------------------------------------------------------------
MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
         "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
FERIADOS = {"natal": (12, 25), "ano novo": (1, 1), "reveillon": (12, 31), "dia das criancas": (10, 12),
            "independencia": (9, 7), "tiradentes": (4, 21), "finados": (11, 2), "proclamacao da republica": (11, 15),
            "dia do trabalho": (5, 1), "dia dos namorados": (6, 12)}
# como se fala cada data ("faltam 97 dias para o Natal")
NOME_FERIADO = {"natal": "o Natal", "ano novo": "o Ano Novo", "reveillon": "o Réveillon",
                "dia das criancas": "o Dia das Crianças", "independencia": "a Independência",
                "tiradentes": "Tiradentes", "finados": "Finados", "proclamacao da republica": "a Proclamação da República",
                "dia do trabalho": "o Dia do Trabalho", "dia dos namorados": "o Dia dos Namorados"}
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def _data_citada(n: str, hoje: date) -> tuple[date, str] | None:
    for nome, (mes, dia) in FERIADOS.items():
        if re.search(rf"\b{nome}\b", n):
            d = date(hoje.year, mes, dia)
            return (d if d >= hoje else date(hoje.year + 1, mes, dia)), NOME_FERIADO.get(nome, nome.title())
    m = re.search(rf"\b(\d{{1,2}}) de ({'|'.join(MESES)})(?: de (\d{{4}}))?", n)
    if m:
        ano = int(m.group(3)) if m.group(3) else hoje.year
        try:
            d = date(ano, MESES[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
        if not m.group(3) and d < hoje:
            d = date(ano + 1, d.month, d.day)
        return d, f"{d.day} de {m.group(2)}"
    return None


def datas(frase: str, hoje: date | None = None) -> str | None:
    hoje = hoje or date.today()
    n = digitos(frase)
    m = re.search(r"daqui a (\d+) (dias|semanas|meses)", n)
    if m and re.search(r"\bque dia\b|\bqual (?:e|sera) a data\b|\bquando\b", n):
        k = int(m.group(1))
        d = hoje + (timedelta(days=k) if m.group(2) == "dias" else timedelta(weeks=k) if m.group(2) == "semanas"
                    else timedelta(days=30 * k))
        return f"Daqui a {k} {m.group(2)} será {DIAS[d.weekday()]}, {d.day:02d}/{d.month:02d}/{d.year}."
    alvo = _data_citada(n, hoje)
    if not alvo:
        return None
    d, rotulo = alvo
    if re.search(r"\bquantos dias\b|\bfaltam?\b|\bfalta\b", n):
        k = (d - hoje).days
        if k == 0:
            return f"Hoje é {rotulo.removeprefix('o ').removeprefix('a ')}!"
        return f"Falta{'m' if k != 1 else ''} {k} dia{'s' if k != 1 else ''} para {rotulo}."
    if re.search(r"\bdia da semana\b|\bque dia (?:cai|e|sera)\b|\bcai (?:em|num|numa)\b", n):
        dia = DIAS[d.weekday()]
        return f"{rotulo[0].upper() + rotulo[1:]} de {d.year} cai {'num' if d.weekday() >= 5 else 'numa'} {dia}."
    return None


def detectar(frase: str) -> tuple[str, dict[str, str]] | None:
    """Sem rede: contas, datas e sorte ja respondidas; conversao so reconhecida."""
    if _CONV.search(digitos(frase)):
        return "conversao", {}
    for f in (calcular, datas, sorte):
        r = f(frase)
        if r:
            return "utilidade", {"resposta": r}
    return None


# ---- sorte -------------------------------------------------------------------------------
def sorte(frase: str, rnd: random.Random | None = None) -> str | None:
    rnd = rnd or random.Random()
    n = digitos(frase)
    if re.search(r"\b(?:jog\w*|lanc\w*|tir\w*) (?:uma |a )?moeda\b|\bcara ou coroa\b", n):
        return f"Deu {rnd.choice(['cara', 'coroa'])}."
    if re.search(r"\b(?:rol\w*|jog\w*|lanc\w*) (?:um |o )?dado\b", n):
        return f"Deu {rnd.randint(1, 6)}."
    m = re.search(r"\bsorte\w* (?:um )?numero (?:de|entre) (\d+) (?:a|e|ate) (\d+)", n)
    if m:
        a, b = sorted((int(m.group(1)), int(m.group(2))))
        return f"Saiu o {rnd.randint(a, b)}."
    m = re.search(r"\b(?:escolh\w*|decid\w*|sorte\w*) entre\s+(.+)$", frase, re.I)
    if m and re.search(r"\s(?:e|ou)\s", m.group(1)):
        opcoes = [o.strip(" .?!,") for o in re.split(r",|\s+ou\s+|\s+e\s+", m.group(1)) if o.strip(" .?!,")]
        if len(opcoes) >= 2:
            return f"Escolho {rnd.choice(opcoes)}."
    return None
