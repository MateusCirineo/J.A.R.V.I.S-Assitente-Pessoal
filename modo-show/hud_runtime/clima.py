"""Clima e previsao pelo Open-Meteo (https://open-meteo.com), sem chave de API.

So o nome da cidade (na busca) e as coordenadas (na previsao) saem da maquina.
Cache de 15 minutos: a tela pode pedir a vontade sem martelar o servico.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

GEOCODIFICACAO = "https://geocoding-api.open-meteo.com/v1/search"
PREVISAO = "https://api.open-meteo.com/v1/forecast"
VALIDADE_S = 15 * 60

# codigos WMO -> (descricao, icone)
WMO = {
    0: ("Céu limpo", "sol"), 1: ("Predomínio de sol", "sol"), 2: ("Parcialmente nublado", "parcial"),
    3: ("Nublado", "nuvem"), 45: ("Neblina", "neblina"), 48: ("Neblina com geada", "neblina"),
    51: ("Garoa fraca", "garoa"), 53: ("Garoa", "garoa"), 55: ("Garoa forte", "garoa"),
    56: ("Garoa congelante", "garoa"), 57: ("Garoa congelante forte", "garoa"),
    61: ("Chuva fraca", "chuva"), 63: ("Chuva", "chuva"), 65: ("Chuva forte", "chuva"),
    66: ("Chuva congelante", "chuva"), 67: ("Chuva congelante forte", "chuva"),
    71: ("Neve fraca", "neve"), 73: ("Neve", "neve"), 75: ("Neve forte", "neve"), 77: ("Grãos de neve", "neve"),
    80: ("Pancadas fracas", "chuva"), 81: ("Pancadas de chuva", "chuva"), 82: ("Pancadas fortes", "chuva"),
    85: ("Pancadas de neve", "neve"), 86: ("Pancadas fortes de neve", "neve"),
    95: ("Trovoada", "trovoada"), 96: ("Trovoada com granizo", "trovoada"), 99: ("Trovoada forte com granizo", "trovoada"),
}


def _get(url: str, params: dict[str, Any], tempo: float = 10.0) -> Any:
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=tempo) as r:
        return json.load(r)


def buscar_cidades(nome: str, limite: int = 5) -> list[dict[str, Any]]:
    dados = _get(GEOCODIFICACAO, {"name": nome, "count": limite, "language": "pt", "format": "json"})
    return [{"nome": r["name"], "regiao": r.get("admin1"), "pais": r.get("country"),
             "lat": round(r["latitude"], 4), "lon": round(r["longitude"], 4)}
            for r in dados.get("results") or []]


def _descrever(codigo: int | None) -> tuple[str, str]:
    return WMO.get(codigo, ("—", "nuvem")) if codigo is not None else ("—", "nuvem")


def previsao(lat: float, lon: float) -> dict[str, Any]:
    d = _get(PREVISAO, {
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 6,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
                   "precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max,sunrise,sunset",
    })
    atual = d.get("current", {})
    desc, icone = _descrever(atual.get("weather_code"))
    dia = d.get("daily", {})
    dias = []
    for i, data in enumerate(dia.get("time", [])):
        dd, di = _descrever(dia["weather_code"][i])
        dias.append({"data": data, "descricao": dd, "icone": di,
                     "max": dia["temperature_2m_max"][i], "min": dia["temperature_2m_min"][i],
                     "chuva_pct": dia["precipitation_probability_max"][i]})
    return {
        "atual": {"temperatura": atual.get("temperature_2m"), "sensacao": atual.get("apparent_temperature"),
                  "umidade": atual.get("relative_humidity_2m"), "vento_kmh": atual.get("wind_speed_10m"),
                  "chuva_mm": atual.get("precipitation"), "dia": bool(atual.get("is_day")),
                  "descricao": desc, "icone": icone, "hora": atual.get("time")},
        "nascer": (dia.get("sunrise") or [None])[0], "por": (dia.get("sunset") or [None])[0],
        "dias": dias,
    }


def _sem_acento(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def achar_locais(texto: str, locais: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cidades configuradas citadas na fala ("clima em Angatuba")."""
    t = _sem_acento(texto)
    return [lc for lc in locais if lc and _sem_acento(lc["nome"]) in t]


class Clima:
    def __init__(self) -> None:
        self._cache: dict[tuple, tuple[float, dict]] = {}     # (lat, lon) -> (quando, dados)
        self._trava = threading.Lock()

    def obter(self, local: dict[str, Any] | None, forcar: bool = False) -> dict[str, Any]:
        if not local:
            return {"status": "nao_configurado",
                    "motivo": "defina sua cidade em Preferências"}
        chave = (local["lat"], local["lon"])
        with self._trava:
            guardado = self._cache.get(chave)
            if not forcar and guardado and time.time() - guardado[0] < VALIDADE_S:
                return guardado[1]
        try:
            dados = {"status": "medido", "fonte": "Open-Meteo", "local": local,
                     "em": time.time(), **previsao(local["lat"], local["lon"])}
        except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
            antigo = guardado[1] if guardado else None
            if antigo:                       # mantem o ultimo dado, marcado como antigo
                return {**antigo, "status": "desatualizado", "detalhe": str(e)[:100]}
            return {"status": "erro", "local": local, "detalhe": str(e)[:100]}
        with self._trava:
            self._cache[chave] = (time.time(), dados)
        return dados

    def obter_todos(self, principal: dict[str, Any] | None,
                    extras: list[dict[str, Any]] | None) -> dict[str, Any]:
        """Cidade principal (com previsao) e as extras em `outros`."""
        dados = dict(self.obter(principal))
        dados["outros"] = [self.obter(e) for e in (extras or []) if e]
        return dados

    def resumo_falado(self, local: dict[str, Any] | None, curto: bool = False) -> str | None:
        d = self.obter(local)
        if d.get("status") not in ("medido", "desatualizado"):
            return None
        a = d["atual"]
        hoje = d["dias"][0] if d.get("dias") else None
        frase = f"Em {local['nome']}, {round(a['temperatura'])} graus, {a['descricao'].lower()}"
        if hoje and not curto:
            frase += (f". Hoje, mínima de {round(hoje['min'])} e máxima de {round(hoje['max'])}"
                      + (f", com {hoje['chuva_pct']}% de chance de chuva" if hoje.get("chuva_pct") else ""))
        return frase + "."
