"""Agenda: contas Google (login so de leitura, ver google_agenda.py) e/ou o
endereco secreto iCal (Google Agenda, Outlook, iCloud...).

O endereco iCal e os tokens sao segredos: ficam em ~/.openjarvis/hud-segredos.json
e nunca sao devolvidos pela API -- a tela so sabe o que esta configurado.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
SEGREDOS = HOME / "hud-segredos.json"
VALIDADE_S = 10 * 60


def ler_segredo(chave: str) -> str | None:
    try:
        return json.loads(SEGREDOS.read_text(encoding="utf-8")).get(chave)
    except (OSError, ValueError):
        return None


def gravar_segredo(chave: str, valor: str | None) -> None:
    try:
        dados = json.loads(SEGREDOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    if valor:
        dados[chave] = valor
    else:
        dados.pop(chave, None)
    SEGREDOS.parent.mkdir(parents=True, exist_ok=True)
    tmp = SEGREDOS.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados), encoding="utf-8")
    os.replace(tmp, SEGREDOS)


PAGINA_GOOGLE = ("esse é o endereço da página do Google Agenda, não da agenda em si: use o "
                 "“Endereço secreto no formato iCal” ou o botão Conectar conta Google")


def normalizar_url(url: str) -> str:
    url = url.strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    if not url.startswith("https://"):
        raise ValueError("o endereço iCal precisa começar com https:// ou webcal://")
    if "calendar.google.com" in url and "/ical/" not in url:
        raise ValueError(PAGINA_GOOGLE)
    return url


def _local(v) -> tuple[datetime, bool]:
    """(datetime local, dia_inteiro)."""
    if isinstance(v, datetime):
        return (v.astimezone() if v.tzinfo else v.astimezone()), False
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day).astimezone(), True
    raise ValueError(v)


def eventos_de(conteudo: bytes, inicio: datetime, fim: datetime) -> list[dict[str, Any]]:
    import icalendar
    import recurring_ical_events
    cal = icalendar.Calendar.from_ical(conteudo)
    saida = []
    for ev in recurring_ical_events.of(cal).between(inicio, fim):
        ini, dia_todo = _local(ev.get("DTSTART").dt)
        fim_ev = ev.get("DTEND")
        fim_local = _local(fim_ev.dt)[0] if fim_ev else ini
        saida.append({"titulo": str(ev.get("SUMMARY") or "(sem título)"),
                      "local": str(ev.get("LOCATION")) if ev.get("LOCATION") else None,
                      "inicio": ini.timestamp(), "fim": fim_local.timestamp(),
                      "dia_inteiro": dia_todo})
    saida.sort(key=lambda e: (e["inicio"], not e["dia_inteiro"]))
    return saida


def ler_ics(url: str, inicio: datetime, fim: datetime) -> list[dict[str, Any]]:
    """Mensagens de erro nunca incluem a URL (e secreta)."""
    if "calendar.google.com" in url and "/ical/" not in url:
        raise ValueError(PAGINA_GOOGLE)
    req = urllib.request.Request(url, headers={"User-Agent": "JarvisHUD/1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            conteudo = r.read(5_000_000)
    except urllib.error.HTTPError as e:
        raise ValueError(f"o endereço iCal respondeu {e.code}") from None
    except (urllib.error.URLError, OSError) as e:
        raise ValueError(f"sem conexão ({type(e).__name__})") from None
    if conteudo.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
        raise ValueError("o endereço devolveu uma página da web, não uma agenda iCal")
    try:
        return eventos_de(conteudo, inicio, fim)
    except Exception:  # noqa: BLE001 - arquivo iCal invalido
        raise ValueError("o conteúdo não é uma agenda iCal válida") from None


class Agenda:
    def __init__(self, google: Any = None) -> None:
        self._cache: tuple[float, dict] | None = None
        self._trava = threading.Lock()
        self.google = google

    def configurada(self) -> bool:
        return bool(ler_segredo("agenda_ics")) or bool(self.google and self.google.contas())

    def esquecer_cache(self) -> None:
        with self._trava:
            self._cache = None

    def definir(self, url: str | None) -> None:
        gravar_segredo("agenda_ics", normalizar_url(url) if url else None)
        with self._trava:
            self._cache = None

    def obter(self, forcar: bool = False) -> dict[str, Any]:
        url = ler_segredo("agenda_ics")
        contas = self.google.contas() if self.google else []
        if not url and not contas:
            return {"status": "nao_configurado",
                    "motivo": "conecte sua conta Google ou cole o endereço secreto iCal"}
        with self._trava:
            if not forcar and self._cache and time.time() - self._cache[0] < VALIDADE_S:
                return self._cache[1]
        agora = datetime.now().astimezone()
        inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        fim = inicio + timedelta(days=3)
        evs: list[dict[str, Any]] = []
        avisos: list[str] = []
        fontes: list[str] = []
        if url:
            try:
                evs += ler_ics(url, inicio, fim)
                fontes.append("iCal")
            except ValueError as e:
                avisos.append(f"iCal: {e}")
        if contas:
            achados, erros = self.google.eventos(inicio, fim)
            evs += achados
            avisos += erros
            if len(erros) < len(contas):
                fontes.append("Google")
        if not fontes:
            return {"status": "erro", "detalhe": "; ".join(avisos)[:300], "avisos": avisos}
        evs.sort(key=lambda e: (e["inicio"], not e["dia_inteiro"]))
        dados = {"status": "medido", "fonte": " + ".join(fontes), "em": time.time(), "avisos": avisos,
                 "eventos": [e for e in evs if e["fim"] >= agora.timestamp() or e["dia_inteiro"]][:15]}
        with self._trava:
            self._cache = (time.time(), dados)
        return dados
