"""Secretario: lembretes, timers e notas, falados e na tela.

"Jarvis, me lembre de ligar para o Pedro as 15h" / "timer de 5 minutos" /
"anote: comprar cabo HDMI" / "todo dia as 8h me lembre do remedio" /
"adie o lembrete em 10 minutos" / "mude o lembrete das 15h para as 16h" /
"cancele o lembrete do Pedro". Guardado em ~/.openjarvis (hud-lembretes.json
e hud-notas.json). Um fio confere os horarios a cada segundo e chama
`ao_vencer`, que fala e notifica. Lembrete repetido nao "acaba": ao vencer,
e remarcado para a proxima ocorrencia.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))

_NUMEROS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "três": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13,
    "quatorze": 14, "catorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18,
    "dezenove": 19, "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
}
_NUM = r"\d{1,3}|" + "|".join(sorted(_NUMEROS, key=len, reverse=True))


def _n(txt: str | None) -> int | None:
    if txt is None:
        return None
    txt = txt.strip().lower()
    return int(txt) if txt.isdigit() else _NUMEROS.get(txt)


_REL = re.compile(rf"\b(?:em|daqui\s+a|daqui|dentro\s+de|de)\s+(?:(?P<meia>meia\s+hora)|(?P<n>{_NUM})\s*"
                  r"(?P<u>segundos?|seg|minutos?|min|horas?|h)\b(?:\s+e\s+meia)?)", re.I)
_ABS = re.compile(rf"\b(?:[àa]s|as|para\s+as|pras|ao)\s+(?P<h>{_NUM}|meio[- ]dia|meia[- ]noite)"
                  rf"(?:\s*(?:h|horas?|:)\s*(?P<m>\d{{1,2}})?|\s+e\s+(?P<m2>\d{{1,2}}|meia|{_NUM}))?"
                  r"(?:\s+(?:horas?))?(?:\s+(?:da|de)\s+(?P<p>manh[ãa]|tarde|noite|madrugada))?", re.I)
_DIA = re.compile(r"\b(?P<d>amanh[ãa]|hoje|depois\s+de\s+amanh[ãa])\b", re.I)


def interpretar_quando(texto: str, agora: datetime | None = None) -> tuple[datetime | None, str]:
    """Acha um horario na frase. Devolve (quando, frase sem o horario)."""
    agora = agora or datetime.now()
    resto = texto
    m = _REL.search(texto)
    if m:
        if m.group("meia"):
            delta = timedelta(minutes=30)
        else:
            n = _n(m.group("n")) or 0
            u = m.group("u").lower()
            delta = (timedelta(seconds=n) if u.startswith("seg") else
                     timedelta(hours=n) if u.startswith("h") else timedelta(minutes=n))
            if "e meia" in m.group(0).lower():
                delta += timedelta(minutes=30)
        return agora + delta, (texto[:m.start()] + texto[m.end():]).strip()
    m = _ABS.search(texto)
    if m:
        h_txt = m.group("h").lower()
        if h_txt.startswith("meio"):
            h, mi = 12, 0
        elif h_txt.startswith("meia"):
            h, mi = 0, 0
        else:
            h = _n(h_txt)
            m2 = (m.group("m2") or "").lower()
            mi = int(m.group("m")) if m.group("m") else 30 if m2 == "meia" else (_n(m2) or 0)
            p = (m.group("p") or "").lower()
            if p in ("tarde", "noite") and h is not None and h < 12:
                h += 12
        if h is None or not (0 <= h <= 23 and 0 <= mi <= 59):
            return None, texto
        resto = (texto[:m.start()] + texto[m.end():]).strip()
        quando = agora.replace(hour=h, minute=mi, second=0, microsecond=0)
        d = _DIA.search(resto)
        if d:
            palavra = d.group("d").lower()
            if palavra.startswith("depois"):
                quando += timedelta(days=2)
            elif palavra.startswith("amanh"):
                quando += timedelta(days=1)
            resto = (resto[:d.start()] + resto[d.end():]).strip()
        elif quando <= agora:
            quando += timedelta(days=1)        # "as 9" dito as 10 = amanha as 9
        return quando, resto
    return None, texto


_PREFIXO = re.compile(r"^\W*(?:jarvis\W+)?(?:por\s+favor\W+)?(?:me\s+)?(?:lembr[ae]\w*(?:-me)?|avis[ae]\w*(?:-me)?)"
                      r"(?:\s+(?:de|que|para|pra|sobre|do|da))?\s*", re.I)


DIAS_SEMANA = {"segunda": 0, "terca": 1, "terça": 1, "quarta": 2, "quinta": 3, "sexta": 4,
               "sabado": 5, "sábado": 5, "domingo": 6}
NOMES_DIA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
_REPETE = re.compile(
    r"\b(?:(?P<uteis>(?:tod[oa]s? (?:os )?)?dias? [uú]teis|de segunda a sexta)"
    r"|(?P<diario>tod[oa]s? (?:os )?dias?|diariamente|toda manh[ãa]|toda noite)"
    r"|(?:tod[oa]s? (?:as? )?|nas? |aos )(?P<dia>segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)s?(?:-feiras?)?"
    r"|(?P<semanal>toda semana|semanalmente|uma vez por semana))\b", re.I)


def interpretar_repeticao(texto: str) -> tuple[str | None, int | None, str]:
    """ "todo dia as 8h tomar remedio" -> ("diario", None, "as 8h tomar remedio")."""
    m = _REPETE.search(texto)
    if not m:
        return None, None, texto
    resto = (texto[:m.start()] + texto[m.end():]).strip()
    if m.group("uteis"):
        return "dias_uteis", None, resto
    if m.group("diario"):
        return "diario", None, resto
    if m.group("dia"):
        return "semanal", DIAS_SEMANA[m.group("dia").lower()], resto
    return "semanal", None, resto


def proxima_ocorrencia(quando: datetime, regra: str, dia_semana: int | None, agora: datetime) -> datetime:
    """Primeira ocorrencia estritamente depois de `agora`, no mesmo horario."""
    q = quando
    if regra == "semanal" and dia_semana is not None:
        q += timedelta(days=(dia_semana - q.weekday()) % 7)
    for _ in range(400):
        ok_dia = regra != "dias_uteis" or q.weekday() < 5
        if q > agora and ok_dia:
            return q
        q += timedelta(days=7 if regra == "semanal" else 1)
    return q


def falar_repeticao(item: dict[str, Any]) -> str:
    q = datetime.fromtimestamp(item["quando"])
    hm = f"{q.hour}h" if q.minute == 0 else f"{q.hour}h{q.minute:02d}"
    regra = item.get("repetir")
    if regra == "diario":
        return f"todos os dias às {hm}"
    if regra == "dias_uteis":
        return f"nos dias úteis às {hm}"
    if regra == "semanal":
        dia = NOMES_DIA[q.weekday()]
        return f"{'todo' if dia in ('sábado', 'domingo') else 'toda'} {dia} às {hm}"
    return falar_quando(q)


def limpar_texto_lembrete(frase: str) -> str:
    t = _PREFIXO.sub("", frase.strip())
    t = re.sub(r"^(?:de|que|para|pra)\s+", "", t, flags=re.I)
    return t.strip(" ,.!?") or "lembrete"


def falar_quando(quando: datetime, agora: datetime | None = None) -> str:
    agora = agora or datetime.now()
    hm = f"{quando.hour}h" if quando.minute == 0 else f"{quando.hour}h{quando.minute:02d}"
    if quando.date() == agora.date():
        falta = quando - agora
        if falta < timedelta(hours=1):
            minutos = max(1, round(falta.total_seconds() / 60))
            return f"daqui a {minutos} minuto{'s' if minutos > 1 else ''}"
        return f"hoje às {hm}"
    if quando.date() == (agora + timedelta(days=1)).date():
        return f"amanhã às {hm}"
    return f"{quando:%d/%m} às {hm}"


class _Loja:
    def __init__(self, arquivo: Path) -> None:
        self._arquivo = arquivo
        self._trava = threading.Lock()

    def ler(self) -> list[dict[str, Any]]:
        try:
            dados = json.loads(self._arquivo.read_text(encoding="utf-8"))
            return dados if isinstance(dados, list) else []
        except (OSError, ValueError):
            return []

    def gravar(self, itens: list[dict[str, Any]]) -> None:
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._arquivo)


class Secretario(threading.Thread):
    def __init__(self, ao_mudar: Callable[[dict], None] | None = None,
                 ao_vencer: Callable[[dict], None] | None = None,
                 pasta: Path = HOME) -> None:
        super().__init__(name="secretario", daemon=True)
        self._lembretes = _Loja(pasta / "hud-lembretes.json")
        self._notas = _Loja(pasta / "hud-notas.json")
        self._ao_mudar = ao_mudar or (lambda d: None)
        self._ao_vencer = ao_vencer or (lambda i: None)
        self._trava = threading.RLock()
        self._encerrar = threading.Event()
        self.ultimo_vencido: dict[str, Any] | None = None     # para "mais 10 minutos" (soneca)

    # ---- consulta -------------------------------------------------------
    def publico(self) -> dict[str, Any]:
        pend = sorted((x for x in self._lembretes.ler() if not x.get("feito")), key=lambda x: x["quando"])
        return {"lembretes": pend[:30], "notas": list(reversed(self._notas.ler()))[:30]}

    def _publicar(self) -> None:
        self._ao_mudar(self.publico())

    # ---- lembretes e timers --------------------------------------------
    def lembrar(self, texto: str, quando: datetime, tipo: str = "lembrete",
                repetir: str | None = None, comando: str | None = None) -> dict[str, Any]:
        with self._trava:
            itens = self._lembretes.ler()
            item = {"id": max([x["id"] for x in itens] + [0]) + 1, "texto": texto.strip()[:200],
                    "quando": quando.timestamp(), "tipo": tipo, "criado": time.time(), "feito": False}
            if repetir in ("diario", "dias_uteis", "semanal"):
                item["repetir"] = repetir
            if comando:                                  # rotina agendada: na hora, EXECUTA o comando
                item["comando"] = comando.strip()[:200]
            itens.append(item)
            self._lembretes.gravar(itens[-200:])
        self._publicar()
        return item

    @staticmethod
    def quando_da_frase(frase: str, agora: datetime | None = None) -> tuple[datetime | None, str | None, str]:
        """ "todo dia às 7h leia as notícias" -> (próximas 7h, "diario", "leia as notícias")."""
        agora = agora or datetime.now()
        regra, dia, sem_rep = interpretar_repeticao(frase)
        quando, resto = interpretar_quando(sem_rep, agora)
        if quando and regra:
            base = quando.replace(year=agora.year, month=agora.month, day=agora.day)
            quando = proxima_ocorrencia(base, regra, dia, agora)
        return quando, regra, resto

    def lembrar_por_frase(self, frase: str, agora: datetime | None = None) -> dict[str, Any] | None:
        quando, regra, resto = self.quando_da_frase(frase, agora)
        if not quando:
            return None
        return self.lembrar(limpar_texto_lembrete(resto), quando, repetir=regra)

    def cancelar(self, ident: int | None = None, ids: list[int] | None = None) -> int:
        """Cancela um lembrete, uma lista deles, ou todos os pendentes. Devolve quantos."""
        with self._trava:
            itens = self._lembretes.ler()
            n = 0
            for x in itens:
                alvo = (ident is None and ids is None) or x["id"] == ident or (ids is not None and x["id"] in ids)
                if not x.get("feito") and alvo:
                    x["feito"], x["cancelado"] = True, True
                    n += 1
            self._lembretes.gravar(itens)
        self._publicar()
        return n

    def remarcar(self, ident: int, quando: datetime) -> dict[str, Any] | None:
        with self._trava:
            itens = self._lembretes.ler()
            achado = None
            for x in itens:
                if x["id"] == ident and not x.get("feito"):
                    x["quando"] = quando.timestamp()
                    achado = x
            if achado:
                self._lembretes.gravar(itens)
        if achado:
            self._publicar()
        return achado

    def achar(self, frase: str, agora: datetime | None = None) -> list[dict[str, Any]]:
        """Pendentes que a frase descreve: pelo horario ("das 15h"), pelo tipo
        ("o timer") ou por palavras do texto ("o do Pedro")."""
        import unicodedata

        def norm(t: str) -> str:
            t = unicodedata.normalize("NFKD", t.lower())
            return "".join(c for c in t if not unicodedata.combining(c))
        pend = self.pendentes()
        n = norm(frase)
        m = re.search(r"\b(?:das|de|da|marcado para as|para as)\s+(\d{1,2})(?:\s*(?:h|:|horas?)\s*(\d{2})?)?\b", n)
        if m:
            h, mi = int(m.group(1)), int(m.group(2)) if m.group(2) else None
            por_hora = [x for x in pend if datetime.fromtimestamp(x["quando"]).hour in (h, h + 12)
                        and (mi is None or datetime.fromtimestamp(x["quando"]).minute == mi)]
            if por_hora:
                return por_hora
        tipos = [t for t in ("timer", "alarme") if re.search(rf"\b{t}s?\b", n)]
        if tipos:
            return [x for x in pend if x.get("tipo") in tipos]
        vazias = {"o", "a", "os", "as", "de", "do", "da", "dos", "das", "meu", "minha", "lembrete", "lembretes",
                  "cancele", "cancela", "cancelar", "apague", "apaga", "remova", "tire", "jarvis", "para", "pra",
                  "que", "e", "um", "uma", "esse", "aquele", "sobre", "com", "em", "no", "na"}
        palavras = {p for p in re.findall(r"\w{3,}", n) if p not in vazias}
        if palavras:
            por_texto = [x for x in pend if palavras & set(re.findall(r"\w{3,}", norm(x["texto"])))]
            if por_texto:
                return por_texto
        return []

    def pendentes(self) -> list[dict[str, Any]]:
        return self.publico()["lembretes"]

    # ---- notas ----------------------------------------------------------
    def anotar(self, texto: str) -> dict[str, Any]:
        with self._trava:
            itens = self._notas.ler()
            item = {"id": max([x["id"] for x in itens] + [0]) + 1, "texto": texto.strip()[:500], "em": time.time()}
            itens.append(item)
            self._notas.gravar(itens[-300:])
        self._publicar()
        return item

    def apagar_nota(self, ident: int) -> bool:
        with self._trava:
            itens = self._notas.ler()
            novos = [x for x in itens if x["id"] != ident]
            self._notas.gravar(novos)
        self._publicar()
        return len(novos) != len(itens)

    def notas(self) -> list[dict[str, Any]]:
        return self.publico()["notas"]

    # ---- relogio --------------------------------------------------------
    def verificar(self, agora: float | None = None) -> list[dict[str, Any]]:
        """Marca e devolve os que venceram. Atrasados ha mais de 12 h (PC
        desligado) sao encerrados sem aviso."""
        agora = agora or time.time()
        vencidos = []
        with self._trava:
            itens = self._lembretes.ler()
            mudou = False
            for x in itens:
                if not x.get("feito") and x["quando"] <= agora:
                    mudou = True
                    if agora - x["quando"] < 12 * 3600:
                        vencidos.append({**x, "atrasado": agora - x["quando"] > 120})
                    if x.get("repetir"):             # repetido: vai para a proxima vez
                        proxima = proxima_ocorrencia(datetime.fromtimestamp(x["quando"]), x["repetir"], None,
                                                     datetime.fromtimestamp(agora))
                        x["quando"] = proxima.timestamp()
                    else:
                        x["feito"] = True
            if vencidos:
                self.ultimo_vencido = {**vencidos[-1], "vencido_em": agora}
            if mudou:
                self._lembretes.gravar(itens)
        if vencidos:
            self._publicar()
        return vencidos

    def encerrar(self) -> None:
        self._encerrar.set()

    def run(self) -> None:
        self._publicar()
        while not self._encerrar.wait(1.0):
            for item in self.verificar():
                try:
                    self._ao_vencer(item)
                except Exception:  # noqa: BLE001 - um aviso nao derruba o relogio
                    pass
