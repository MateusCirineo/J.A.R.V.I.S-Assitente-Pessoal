"""Amostragem de telemetria, separada da animacao.

Dois ritmos, duas threads:
  - rapida (3 s): CPU, memoria, disco, GPU, bateria, rede, midia, volume,
    ollama e servidor.
  - lenta (5 s de ciclo, cada item no seu intervalo): dispositivos, pastas,
    apps abertos, temperatura, dados extras do OpenJarvis, clima e agenda.
    Chamadas de rede demoradas ficam aqui para nunca congelar o painel.

Cada dado sai com um `status`:
    medido       valor obtido agora, da fonte indicada
    aguardando   precisa de duas amostras (ex.: CPU) ou ainda nao houve evento
    indisponivel nao existe medidor nesta maquina / nesta configuracao
    nao_configurado depende de um ajuste seu (cidade, endereco da agenda)
    erro         a fonte existe mas falhou nesta amostra
"""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable

from . import OLLAMA, SERVIDOR_OPENJARVIS
from .estado import Estado

INTERVALO_S = 3.0
HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))


def _get_json(url: str, tempo: float = 3.0) -> Any:
    with urllib.request.urlopen(url, timeout=tempo) as r:
        return json.load(r)


# --------------------------------------------------------------------------
# sistema basico (ctypes: sem dependencias)
# --------------------------------------------------------------------------

class _Mem(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def memoria() -> dict[str, Any]:
    m = _Mem()
    m.dwLength = ctypes.sizeof(_Mem)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        return {"status": "erro", "fonte": "GlobalMemoryStatusEx"}
    g = 1024 ** 3
    total, livre = m.ullTotalPhys / g, m.ullAvailPhys / g
    return {"status": "medido", "fonte": "GlobalMemoryStatusEx",
            "total_gb": round(total, 2), "livre_gb": round(livre, 2),
            "uso_pct": round((total - livre) / total * 100, 1)}


class _Cpu:
    """Uso de CPU entre duas chamadas (GetSystemTimes)."""

    def __init__(self) -> None:
        self._anterior: tuple[int, int, int] | None = None

    @staticmethod
    def _tempos() -> tuple[int, int, int]:
        ocioso, kernel, usuario = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(ocioso), ctypes.byref(kernel),
                                              ctypes.byref(usuario))
        v = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime  # noqa: E731
        return v(ocioso), v(kernel), v(usuario)

    def medir(self) -> dict[str, Any]:
        atual = self._tempos()
        anterior, self._anterior = self._anterior, atual
        if anterior is None:
            return {"status": "aguardando", "fonte": "GetSystemTimes"}
        d_ocioso = atual[0] - anterior[0]
        d_total = (atual[1] - anterior[1]) + (atual[2] - anterior[2])  # kernel inclui ocioso
        if d_total <= 0:
            return {"status": "aguardando", "fonte": "GetSystemTimes"}
        return {"status": "medido", "fonte": "GetSystemTimes",
                "uso_pct": round(max(0.0, min(100.0, (1 - d_ocioso / d_total) * 100)), 1)}


def disco(unidade: str = "C:\\") -> dict[str, Any]:
    try:
        u = shutil.disk_usage(unidade)
    except OSError:
        return {"status": "erro", "fonte": "disk_usage"}
    g = 1024 ** 3
    return {"status": "medido", "fonte": "disk_usage", "unidade": unidade.rstrip("\\"),
            "total_gb": round(u.total / g, 1), "livre_gb": round(u.free / g, 1),
            "uso_pct": round(u.used / u.total * 100, 1)}


# --------------------------------------------------------------------------
# configuracao do OpenJarvis (somente leitura)
# --------------------------------------------------------------------------

def configuracao() -> dict[str, Any]:
    arq = HOME / "config.toml"
    try:
        import tomlkit
        c = tomlkit.parse(arq.read_text(encoding="utf-8")).unwrap()
    except Exception as e:  # noqa: BLE001
        return {"status": "erro", "detalhe": f"config.toml: {e}"}
    intel, motor, fala = c.get("intelligence", {}), c.get("engine", {}), c.get("speech", {})
    return {
        "status": "medido",
        "modelo_chat": intel.get("default_model"),
        "motor_padrao": motor.get("default"),
        "motor_preferido": intel.get("preferred_engine"),
        "tts": fala.get("tts_backend"),
        "voz": fala.get("voice_id"),
        "idioma": fala.get("language"),
        "stt_dispositivo": fala.get("device"),
    }


# --------------------------------------------------------------------------
# ollama e servidor
# --------------------------------------------------------------------------

def ollama() -> dict[str, Any]:
    base = {"endpoint": OLLAMA}
    try:
        tags = _get_json(f"{OLLAMA}/api/tags")
        ps = _get_json(f"{OLLAMA}/api/ps")
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {**base, "status": "fora", "detalhe": str(e)[:120]}
    g = 1e9      # GB decimal, como o `ollama list` mostra (9,6 GB e nao 9,0 GiB)
    instalados = [{"nome": m["name"], "tamanho_gb": round(m.get("size", 0) / g, 2)}
                  for m in tags.get("models", [])]
    carregados = [{"nome": m["name"], "tamanho_gb": round(m.get("size", 0) / g, 2),
                   "vram_gb": round(m.get("size_vram", 0) / g, 2),
                   "expira": m.get("expires_at")}
                  for m in ps.get("models", [])]
    return {**base, "status": "ok", "instalados": sorted(instalados, key=lambda m: m["nome"]),
            "carregados": carregados}


def servidor() -> dict[str, Any]:
    base = {"endpoint": SERVIDOR_OPENJARVIS}
    try:
        _get_json(f"{SERVIDOR_OPENJARVIS}/health", 2.5)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {**base, "status": "fora", "detalhe": str(e)[:120]}
    saida: dict[str, Any] = {**base, "status": "ok"}
    for chave, rota in (("info", "/v1/info"), ("fala", "/v1/speech/health"),
                        ("estatisticas", "/v1/telemetry/stats"),
                        ("energia", "/v1/telemetry/energy"),
                        ("canais", "/v1/channels/status")):
        try:
            saida[chave] = _get_json(SERVIDOR_OPENJARVIS + rota, 4.0)
        except (urllib.error.URLError, OSError, ValueError) as e:
            saida[chave] = {"erro": str(e)[:120]}
    return saida


def servidor_extra() -> dict[str, Any]:
    """Custos, historico, automacoes, aprovacoes, memoria e conectores.
    Do historico sai so a pergunta, o modelo e o tempo -- nunca a resposta."""
    s = SERVIDOR_OPENJARVIS
    out: dict[str, Any] = {"em": time.time()}

    def pegar(rota, tempo=6.0):
        try:
            return _get_json(s + rota, tempo)
        except urllib.error.HTTPError as e:
            # o corpo do erro traz o motivo (ex.: "extensao Rust ausente" no 503)
            try:
                return json.load(e)
            except ValueError:
                return {"_erro": f"HTTP {e.code}"}
        except (urllib.error.URLError, OSError, ValueError) as e:
            return {"_erro": str(e)[:100]}

    sv = pegar("/v1/savings")
    if "_erro" not in sv:
        out["custos"] = {
            "chamadas": sv.get("total_calls"), "tokens_entrada": sv.get("total_prompt_tokens"),
            "tokens_saida": sv.get("total_completion_tokens"), "custo_local": sv.get("local_cost"),
            "provedores": [{"nome": p.get("label") or p.get("provider"), "custo": p.get("total_cost"),
                            "energia_wh": p.get("energy_wh")} for p in sv.get("per_provider", [])],
        }
    tr = pegar("/v1/traces?limit=12")
    if "_erro" not in tr:
        hist = []
        for t in tr.get("traces", []):
            passos = t.get("steps") or []
            inicio = passos[0].get("timestamp") if passos else t.get("started_at")
            hist.append({"consulta": (t.get("query") or "")[:160], "modelo": t.get("model"),
                         "agente": t.get("agent"), "em": inicio,
                         "duracao_s": round(sum(p.get("duration_seconds") or 0 for p in passos), 1)})
        out["historico"] = hist
    ag = pegar("/v1/managed-agents")
    if "_erro" not in ag:
        out["automacoes"] = [{"nome": a.get("name"), "tipo": a.get("agent_type"),
                              "agenda": (a.get("config") or {}).get("schedule_type"),
                              "valor": (a.get("config") or {}).get("schedule_value"),
                              "situacao": a.get("status")} for a in ag.get("agents", [])]
    dg = pegar("/api/digest/schedule")
    if "_erro" not in dg:
        out["resumo_diario"] = {"ativo": dg.get("enabled"), "cron": dg.get("cron")}
    ap = pegar("/v1/approvals/pending")
    out["aprovacoes"] = ap.get("count") if "_erro" not in ap else None
    me = pegar("/v1/memory/stats")
    if "detail" in me:
        motivo = ("requer a extensão Rust (openjarvis_rust), que não compila sem o MSVC"
                  if "openjarvis_rust" in str(me["detail"]) else str(me["detail"]).split(".")[0])
        out["memoria"] = {"status": "indisponivel", "motivo": motivo}
    elif "_erro" in me:
        out["memoria"] = {"status": "erro", "motivo": me["_erro"]}
    else:
        out["memoria"] = {"status": "medido", **me}
    co = pegar("/v1/connectors")
    if "_erro" not in co:
        out["conectores"] = [{"id": c["connector_id"], "nome": c.get("display_name"),
                              "conectado": c.get("connected")} for c in co.get("connectors", [])]
    return out


# --------------------------------------------------------------------------

class AmostradorLento(threading.Thread):
    """Itens lentos, cada um no seu intervalo. O rapido le `dados` pronto."""

    def __init__(self, itens: dict[str, tuple[float, Callable[[], Any]]]) -> None:
        super().__init__(name="telemetria-lenta", daemon=True)
        self._itens = itens
        self._ultimo: dict[str, float] = {}
        self.dados: dict[str, Any] = {}
        self._parar = threading.Event()
        self._forcar: set[str] = set()

    def forcar(self, chave: str) -> None:
        self._forcar.add(chave)

    def run(self) -> None:
        while not self._parar.is_set():
            for chave, (intervalo, func) in self._itens.items():
                if chave in self._forcar or time.monotonic() - self._ultimo.get(chave, -1e9) >= intervalo:
                    self._forcar.discard(chave)
                    try:
                        self.dados[chave] = func()
                    except Exception as e:  # noqa: BLE001 - um item nao derruba os outros
                        self.dados[chave] = {"status": "erro", "detalhe": str(e)[:120]}
                    self._ultimo[chave] = time.monotonic()
                if self._parar.is_set():
                    return
            self._parar.wait(1.0)

    def parar(self) -> None:
        self._parar.set()


class Amostrador(threading.Thread):
    def __init__(self, estado: Estado, prefs=None, clima=None, agenda=None, vigia=None,
                 extras: dict[str, tuple[float, Callable[[], dict[str, Any]]]] | None = None) -> None:
        super().__init__(name="telemetria", daemon=True)
        from . import sistema
        self._estado = estado
        self._prefs = prefs
        self._vigia = vigia
        self._sis = sistema
        self._cpu = _Cpu()
        self._rede = sistema.Rede()
        self._gpu = sistema.Gpu()
        self._parar = threading.Event()

        def pastas():
            escolhidas = (prefs.ler().get("pastas_monitoradas") if prefs else None) or sistema.pastas_padrao()
            return sistema.pastas_monitoradas(escolhidas)

        self.lento = AmostradorLento({
            "apps": (5, sistema.apps_abertos),
            "temperatura": (30, sistema.temperatura),
            "pastas": (15, pastas),
            "servidor_extra": (15, servidor_extra),
            "dispositivos": (60, sistema.dispositivos),
            "clima": (60, lambda: clima.obter_todos(prefs.ler().get("local_clima"),
                                                     prefs.ler().get("climas_extras")) if clima else
                      {"status": "indisponivel"}),
            "agenda": (60, lambda: agenda.obter() if agenda else {"status": "indisponivel"}),
            **(extras or {}),                      # noticias, e-mail...
        })
        self._extras = list(extras or {})

    def amostrar(self) -> dict[str, Any]:
        from . import midia
        lento = self.lento.dados
        sens = self._sis.sensores()
        return {
            "em": time.time(),
            "intervalo_s": INTERVALO_S,
            "sistema": {
                "memoria": memoria(),
                "cpu": self._cpu.medir(),
                "disco": disco(),
                "gpu": self._gpu.medir(),
                "bateria": self._sis.bateria(),
                # com o leitor de sensores a temperatura vem a cada amostra
                "temperatura": (self._sis.temperatura_sensores(sens)
                                or lento.get("temperatura", {"status": "aguardando"})),
                "energia_cpu": self._sis.energia_cpu(sens),
                "rede": self._rede.medir(),
            },
            "ollama": ollama(),
            "servidor": servidor(),
            "config": configuracao(),
            "midia": midia.estado_midia(),
            "volume": midia.volume_sistema(),
            "apps": lento.get("apps", {"status": "aguardando"}),
            "arquivos": {"downloads": self._sis.downloads(),
                         "pastas": lento.get("pastas", {"status": "aguardando"})},
            "dispositivos": lento.get("dispositivos", {"status": "aguardando"}),
            "servidor_extra": lento.get("servidor_extra", {}),
            "clima": lento.get("clima", {"status": "aguardando"}),
            "agenda": lento.get("agenda", {"status": "aguardando"}),
            **{k: lento.get(k, {"status": "aguardando"}) for k in self._extras},
        }

    def run(self) -> None:
        self.lento.start()
        while not self._parar.is_set():
            try:
                amostra = self.amostrar()
                self._estado.definir_telemetria(amostra)
                self._sincronizar_conexoes(amostra)
                if self._vigia:
                    self._vigia.observar(amostra)
            except Exception as e:  # noqa: BLE001 - um sensor quebrado nao derruba o painel
                self._estado.registrar("telemetria", f"falha na amostra: {e}", "aviso")
            self._parar.wait(INTERVALO_S)

    def _sincronizar_conexoes(self, amostra: dict[str, Any]) -> None:
        """Mantem o estado de conexao atual: sem isto a tela Jarvis so via o
        servidor cair no boot ou quando uma pergunta falhava."""
        atual = self._estado.ler("conexao")
        for chave in ("servidor", "ollama"):
            novo = "ok" if amostra[chave].get("status") == "ok" else "fora"
            if atual[chave].get("estado") != novo:
                self._estado.atualizar("conexao", **{chave: {
                    "estado": novo, "detalhe": amostra[chave].get("detalhe"), "em": time.time()}})

    def parar(self) -> None:
        self._parar.set()
        self.lento.parar()
