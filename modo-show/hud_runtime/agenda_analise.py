"""Conflitos e horarios livres na agenda ja lida (G1).

"Jarvis, tenho conflito na agenda?" / "quais horários livres amanhã?"
Trabalha sobre os eventos que o HUD ja leu (Google ou iCal): so leitura, nada e
criado ou alterado. Agenda nao conectada = diz isso (nunca "agenda vazia").
Eventos de dia inteiro nao contam como conflito nem ocupam horario.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def _do_dia(eventos: list[dict[str, Any]], dia: datetime) -> list[dict[str, Any]]:
    ini = dia.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    fim = ini + 86400
    return sorted((e for e in eventos if not e.get("dia_inteiro") and e["inicio"] < fim and e["fim"] > ini),
                  key=lambda e: e["inicio"])


def conflitos(eventos: list[dict[str, Any]], dia: datetime) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    evs = _do_dia(eventos, dia)
    pares = []
    for i, a in enumerate(evs):
        for b in evs[i + 1:]:
            if b["inicio"] >= a["fim"]:
                break
            pares.append((a, b))
    return pares


def horarios_livres(eventos: list[dict[str, Any]], dia: datetime, das: int = 8, ate: int = 19,
                    minimo_min: int = 30, agora: datetime | None = None) -> list[tuple[datetime, datetime]]:
    base = dia.replace(hour=0, minute=0, second=0, microsecond=0)
    ini, fim = base + timedelta(hours=das), base + timedelta(hours=ate)
    if agora and agora.date() == base.date():
        ini = max(ini, agora.replace(second=0, microsecond=0))
    livres, cursor = [], ini
    for e in _do_dia(eventos, dia):
        a, b = datetime.fromtimestamp(e["inicio"]), datetime.fromtimestamp(e["fim"])
        if a > cursor and (min(a, fim) - cursor) >= timedelta(minutes=minimo_min):
            livres.append((cursor, min(a, fim)))
        cursor = max(cursor, b)
        if cursor >= fim:
            break
    if fim - cursor >= timedelta(minutes=minimo_min):
        livres.append((cursor, fim))
    return livres


def _hm(d: datetime) -> str:
    return f"{d.hour}h" if d.minute == 0 else f"{d.hour}h{d.minute:02d}"


def fala_conflitos(ag: dict[str, Any], dia: datetime, rotulo: str) -> str:
    if ag.get("status") == "nao_configurado":
        return "Sua agenda ainda não está conectada, então não sei se há conflitos. Conecte no cartão Agenda do painel."
    if ag.get("status") != "medido":
        return "Não consegui ler a agenda agora; não dá para saber se há conflitos."
    pares = conflitos(ag.get("eventos", []), dia)
    if not pares:
        return f"Nenhum conflito na agenda {rotulo}."
    partes = [f"{a['titulo']} às {_hm(datetime.fromtimestamp(a['inicio']))} bate com {b['titulo']} às "
              f"{_hm(datetime.fromtimestamp(b['inicio']))}" for a, b in pares[:3]]
    return f"{len(pares)} conflito{'s' if len(pares) > 1 else ''} {rotulo}: " + "; ".join(partes) + "."


def fala_livres(ag: dict[str, Any], dia: datetime, rotulo: str, agora: datetime | None = None) -> str:
    if ag.get("status") == "nao_configurado":
        return "Sua agenda ainda não está conectada, então não sei seus horários livres. Conecte no cartão Agenda do painel."
    if ag.get("status") != "medido":
        return "Não consegui ler a agenda agora."
    livres = horarios_livres(ag.get("eventos", []), dia, agora=agora)
    if not livres:
        return f"Nenhum horário livre de meia hora ou mais {rotulo}, entre 8h e 19h."
    partes = [f"das {_hm(a)} às {_hm(b)}" for a, b in livres[:4]]
    return f"Livre {rotulo}: " + "; ".join(partes) + "."
