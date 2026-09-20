"""Sensores e estado do Windows para o Painel: energia, rede, GPU, temperatura,
apps abertos, downloads, pastas monitoradas e dispositivos.

Cada funcao devolve {"status": medido|indisponivel|aguardando|erro, ...}.
Nada aqui escreve em disco nem envia dados para fora da maquina.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from ctypes import wintypes
from pathlib import Path
from typing import Any

import psutil

SEM_JANELA = 0x08000000

# ---------------------------------------------------------------------------
# pastas conhecidas do Windows (a Area de Trabalho aqui esta no OneDrive)
# ---------------------------------------------------------------------------

_PASTAS_CONHECIDAS = {
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "area_de_trabalho": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "documentos": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
}


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


def pasta_conhecida(nome: str) -> Path:
    guid = _GUID()
    ctypes.windll.ole32.CLSIDFromString(_PASTAS_CONHECIDAS[nome], ctypes.byref(guid))
    caminho = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None,
                                                  ctypes.byref(caminho)) != 0:
        return Path.home() / nome.capitalize()
    try:
        return Path(caminho.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(caminho)


# ---------------------------------------------------------------------------
# energia
# ---------------------------------------------------------------------------

def bateria() -> dict[str, Any]:
    try:
        b = psutil.sensors_battery()
    except Exception as e:  # noqa: BLE001
        return {"status": "erro", "detalhe": str(e)[:100]}
    if b is None:
        return {"status": "indisponivel", "motivo": "sem bateria (ligado direto na tomada)"}
    restante = None
    if not b.power_plugged and b.secsleft not in (psutil.POWER_TIME_UNKNOWN,
                                                    psutil.POWER_TIME_UNLIMITED):
        restante = round(b.secsleft / 60)
    return {"status": "medido", "fonte": "psutil", "percentual": round(b.percent, 1),
            "na_tomada": bool(b.power_plugged), "restante_min": restante}


# ---------------------------------------------------------------------------
# rede
# ---------------------------------------------------------------------------

class Rede:
    """Taxas de envio/recebimento entre amostras, com historico curto."""

    def __init__(self, historico: int = 60) -> None:
        self._anterior: tuple[float, int, int] | None = None
        self.historico: deque[tuple[float, float]] = deque(maxlen=historico)

    @staticmethod
    def _interface() -> dict[str, Any]:
        stats = psutil.net_if_stats()
        for nome, enderecos in psutil.net_if_addrs().items():
            baixo = nome.lower()
            if (not stats.get(nome) or not stats[nome].isup or "loopback" in baixo
                    or baixo.startswith(("vethernet", "bluetooth"))):
                continue
            for e in enderecos:
                if e.family.name == "AF_INET" and not e.address.startswith("169.254"):
                    return {"nome": nome, "ipv4": e.address}
        return {"nome": None, "ipv4": None}

    def medir(self) -> dict[str, Any]:
        agora = time.monotonic()
        c = psutil.net_io_counters()
        anterior, self._anterior = self._anterior, (agora, c.bytes_sent, c.bytes_recv)
        base = {"fonte": "psutil", **self._interface()}
        if anterior is None:
            return {"status": "aguardando", **base}
        dt = agora - anterior[0]
        envio = max(0.0, (c.bytes_sent - anterior[1]) / dt)
        receb = max(0.0, (c.bytes_recv - anterior[2]) / dt)
        self.historico.append((round(envio), round(receb)))
        return {"status": "medido", **base, "envio_bps": round(envio), "recebimento_bps": round(receb),
                "historico": list(self.historico)}


# ---------------------------------------------------------------------------
# GPU: contador "GPU Engine" do Windows (sem administrador)
# ---------------------------------------------------------------------------

class _ValorPdh(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


class _ItemPdh(ctypes.Structure):
    _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", _ValorPdh)]


_INSTANCIA_GPU = re.compile(r"luid_(0x[0-9a-fA-F]+_0x[0-9a-fA-F]+)_phys_\d+_eng_(\d+)_engtype_(\w+)")


class Gpu:
    """Uso da GPU por adaptador. O contador vem por processo e por motor; o uso
    de um motor e a soma dos processos, e o do adaptador e o motor mais ocupado."""

    def __init__(self) -> None:
        self._pdh = ctypes.WinDLL("pdh")
        self._consulta = wintypes.HANDLE()
        self._contador = wintypes.HANDLE()
        self._ok = False
        self.nome = self._nome_placa()
        try:
            if self._pdh.PdhOpenQueryW(None, 0, ctypes.byref(self._consulta)) == 0 and \
                    self._pdh.PdhAddEnglishCounterW(self._consulta,
                                                    "\\GPU Engine(*)\\Utilization Percentage",
                                                    0, ctypes.byref(self._contador)) == 0:
                self._pdh.PdhCollectQueryData(self._consulta)      # linha de base
                self._ok = True
        except OSError:
            self._ok = False

    @staticmethod
    def _nome_placa() -> str | None:
        try:
            saida = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_VideoController).Name"],
                capture_output=True, text=True, timeout=20, creationflags=SEM_JANELA).stdout
        except (OSError, subprocess.TimeoutExpired):
            return None
        fisicas = [n.strip() for n in saida.splitlines()
                   if n.strip() and not re.search(r"virtual|parsec|remote|basic display", n, re.I)]
        return fisicas[0] if fisicas else None

    def medir(self) -> dict[str, Any]:
        if not self._ok:
            return {"status": "indisponivel", "motivo": "contador GPU Engine indisponivel"}
        if self._pdh.PdhCollectQueryData(self._consulta) != 0:
            return {"status": "erro", "detalhe": "falha ao coletar o contador"}
        tamanho, qtd = wintypes.DWORD(0), wintypes.DWORD(0)
        self._pdh.PdhGetFormattedCounterArrayW(self._contador, 0x200, ctypes.byref(tamanho),
                                               ctypes.byref(qtd), None)
        if not tamanho.value:
            return {"status": "aguardando"}
        buf = (ctypes.c_byte * tamanho.value)()
        if self._pdh.PdhGetFormattedCounterArrayW(self._contador, 0x200, ctypes.byref(tamanho),
                                                  ctypes.byref(qtd), buf) != 0:
            return {"status": "aguardando"}
        itens = ctypes.cast(buf, ctypes.POINTER(_ItemPdh))
        por_motor: dict[tuple[str, str], float] = defaultdict(float)
        for i in range(qtd.value):
            m = _INSTANCIA_GPU.search(itens[i].szName or "")
            if m and itens[i].FmtValue.CStatus in (0, 1):
                por_motor[(m.group(1), m.group(2))] += itens[i].FmtValue.doubleValue
        if not por_motor:
            return {"status": "aguardando"}
        por_adaptador: dict[str, float] = defaultdict(float)
        for (luid, _), v in por_motor.items():
            por_adaptador[luid] = max(por_adaptador[luid], v)
        uso = min(100.0, max(por_adaptador.values()))
        return {"status": "medido", "fonte": "contador GPU Engine do Windows",
                "nome": self.nome, "uso_pct": round(uso, 1)}


# ---------------------------------------------------------------------------
# temperatura: o Windows so libera com administrador
# ---------------------------------------------------------------------------

LHM = "http://127.0.0.1:8085/data.json"
# leitor de sensores do Jarvis (sensores/instalar-sensores.ps1): roda como SYSTEM
# e grava aqui a cada 1 s; o runtime (usuario comum) so le
SENSORES = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "JarvisSensores" / "sensores.json"
SENSORES_VALIDADE_S = 10


def sensores(arquivo: Path = SENSORES) -> dict[str, Any] | None:
    """Leitura recente do leitor de sensores, ou None (nao instalado / parado)."""
    try:
        d = json.loads(arquivo.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or time.time() - float(d.get("em") or 0) > SENSORES_VALIDADE_S:
        return None
    return d


def temperatura_sensores(d: dict[str, Any] | None = None) -> dict[str, Any] | None:
    d = d if d is not None else sensores()
    temps = (d or {}).get("temperaturas_c") or {}
    for nome in ("CPU Package", "Core Max", "Core Average"):
        v = temps.get(nome)
        if isinstance(v, (int, float)) and v > 0:
            return {"status": "medido", "fonte": "leitor de sensores (LibreHardwareMonitorLib)",
                    "sensor": nome, "celsius": float(v)}
    return None


def energia_cpu(d: dict[str, Any] | None = None) -> dict[str, Any]:
    """Potencia do pacote da CPU (contador RAPL) e energia acumulada em joules."""
    d = d if d is not None else sensores()
    if not d:
        return {"status": "indisponivel",
                "motivo": "leitor de sensores não instalado (modo-show\\sensores\\instalar-sensores.ps1)"}
    p = (d.get("potencias_w") or {}).get("CPU Package")
    if not isinstance(p, (int, float)) or p <= 0:
        return {"status": "indisponivel", "motivo": "a CPU não informou potência (driver PawnIO ausente?)"}
    return {"status": "medido", "potencia_w": float(p), "energia_j": float(d.get("energia_pacote_j") or 0),
            "fonte": "CPU Package (RAPL)"}


def temperatura() -> dict[str, Any]:
    """Leitor de sensores do Jarvis; senao o LibreHardwareMonitor com servidor web."""
    lida = temperatura_sensores()
    if lida:
        return lida
    try:
        with urllib.request.urlopen(LHM, timeout=1.5) as r:
            arvore = json.load(r)
    except (urllib.error.URLError, OSError, ValueError):
        return {"status": "indisponivel",
                "motivo": "o Windows só libera temperatura para administrador; instale o leitor "
                          "de sensores (modo-show\\sensores\\instalar-sensores.ps1, como administrador)"}
    achados: list[tuple[str, float]] = []

    def andar(no, caminho):
        texto = no.get("Text", "")
        valor = str(no.get("Value", ""))
        if "°C" in valor and ("cpu" in caminho.lower() or "package" in texto.lower()):
            try:
                achados.append((texto, float(valor.split()[0].replace(",", "."))))
            except ValueError:
                pass
        for filho in no.get("Children", []):
            andar(filho, caminho + "/" + texto)

    andar(arvore, "")
    if not achados:
        return {"status": "indisponivel", "motivo": "LibreHardwareMonitor sem sensor de CPU"}
    nome, valor = next(((n, v) for n, v in achados if "package" in n.lower()), achados[0])
    return {"status": "medido", "fonte": "LibreHardwareMonitor", "sensor": nome, "celsius": valor}


# ---------------------------------------------------------------------------
# apps abertos: janelas de nivel superior visiveis
# ---------------------------------------------------------------------------

_user32 = ctypes.windll.user32
_dwm = ctypes.windll.dwmapi


def apps_abertos(limite: int = 14) -> dict[str, Any]:
    janelas: dict[int, list[str]] = defaultdict(list)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cada(hwnd, _):
        if not _user32.IsWindowVisible(hwnd) or _user32.GetWindow(hwnd, 4):   # GW_OWNER
            return True
        if _user32.GetWindowLongW(hwnd, -20) & 0x80:                           # TOOLWINDOW
            return True
        oculta = ctypes.c_int(0)
        _dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(oculta), 4)          # CLOAKED
        n = _user32.GetWindowTextLengthW(hwnd)
        if oculta.value or not n:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        _user32.GetWindowTextW(hwnd, buf, n + 1)
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        janelas[pid.value].append(buf.value)
        return True

    _user32.EnumWindows(cada, 0)
    apps: dict[str, dict[str, Any]] = {}
    for pid, titulos in janelas.items():
        try:
            nome = psutil.Process(pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if nome.lower() in ("explorer.exe", "textinputhost.exe", "applicationframehost.exe"):
            titulos = [t for t in titulos if t not in ("Program Manager",)]
            if not titulos:
                continue
        chave = nome.lower()
        item = apps.setdefault(chave, {"app": nome.removesuffix(".exe"), "janelas": 0, "titulo": titulos[0]})
        item["janelas"] += len(titulos)
    lista = sorted(apps.values(), key=lambda a: -a["janelas"])
    return {"status": "medido", "fonte": "EnumWindows", "total": len(lista), "apps": lista[:limite]}


# ---------------------------------------------------------------------------
# arquivos: downloads e pastas monitoradas
# ---------------------------------------------------------------------------

_PARCIAIS = (".crdownload", ".part", ".partial", ".download", ".opdownload", ".tmp")


def _recentes(pasta: Path, limite: int) -> list[dict[str, Any]]:
    itens = []
    try:
        with os.scandir(pasta) as it:
            for e in it:
                if e.name.startswith((".", "~$")) or e.name.lower() == "desktop.ini":
                    continue
                try:
                    st = e.stat()
                except OSError:
                    continue
                itens.append({"nome": e.name, "pasta": e.is_dir(), "bytes": None if e.is_dir() else st.st_size,
                              "modificado": st.st_mtime})
    except OSError:
        return []
    itens.sort(key=lambda i: -i["modificado"])
    return itens[:limite]


def downloads(limite: int = 7) -> dict[str, Any]:
    pasta = pasta_conhecida("downloads")
    if not pasta.exists():
        return {"status": "indisponivel", "motivo": f"pasta {pasta} nao existe"}
    itens = _recentes(pasta, 40)
    andamento = [i for i in itens if i["nome"].lower().endswith(_PARCIAIS)]
    concluidos = [i for i in itens if not i["nome"].lower().endswith(_PARCIAIS)][:limite]
    return {"status": "medido", "pasta": str(pasta), "em_andamento": andamento,
            "recentes": concluidos}


def pastas_monitoradas(caminhos: list[str], janela_s: int = 900) -> dict[str, Any]:
    agora = time.time()
    saida = []
    for c in caminhos:
        p = Path(os.path.expandvars(os.path.expanduser(c)))
        if not p.is_dir():
            saida.append({"caminho": str(p), "status": "indisponivel"})
            continue
        itens = _recentes(p, 60)
        saida.append({"caminho": str(p), "status": "medido", "total": len(itens),
                      "alterados_recentes": [i for i in itens if agora - i["modificado"] < janela_s][:5],
                      "ultimos": itens[:4]})
    return {"status": "medido", "pastas": saida}


def pastas_padrao() -> list[str]:
    return [str(pasta_conhecida("area_de_trabalho")), str(pasta_conhecida("documentos"))]


# ---------------------------------------------------------------------------
# dispositivos e conectividade (lento: ~1-2 s de PowerShell, a cada 60 s)
# ---------------------------------------------------------------------------

_CLASSES = ("Camera", "Image", "AudioEndpoint", "Keyboard", "Mouse", "Monitor",
            "DiskDrive", "Printer", "WPD")
_PS_DISPOSITIVOS = (
    # PowerShell 5 responde na pagina de codigo do console; sem isto os acentos
    # chegavam corrompidos ("compat�vel")
    "[Console]::OutputEncoding = [Text.Encoding]::UTF8;"
    "$d = Get-CimInstance Win32_PnPEntity | Where-Object { $_.Status -eq 'OK' -and $_.PNPClass -in @("
    + ",".join(f"'{c}'" for c in _CLASSES)
    + ") } | Select-Object Name, PNPClass;"
    "$n = Get-NetConnectionProfile -ErrorAction SilentlyContinue | "
    "Select-Object Name, InterfaceAlias, @{n='IPv4';e={[string]$_.IPv4Connectivity}};"
    "@{dispositivos=@($d); redes=@($n)} | ConvertTo-Json -Depth 3 -Compress"
)


def dispositivos() -> dict[str, Any]:
    try:
        saida = subprocess.run(["powershell", "-NoProfile", "-Command", _PS_DISPOSITIVOS],
                               capture_output=True, text=True, timeout=30,
                               creationflags=SEM_JANELA, encoding="utf-8", errors="replace").stdout
        dados = json.loads(saida or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        return {"status": "erro", "detalhe": str(e)[:100]}
    grupos: dict[str, list[str]] = defaultdict(list)
    rotulos = {"Camera": "Câmeras", "Image": "Câmeras", "AudioEndpoint": "Áudio",
               "Keyboard": "Teclados", "Mouse": "Mouses", "Monitor": "Monitores",
               "DiskDrive": "Discos", "Printer": "Impressoras", "WPD": "Celulares e mídia"}
    for d in dados.get("dispositivos") or []:
        if not d or not d.get("Name"):
            continue
        g = rotulos.get(d.get("PNPClass"), "Outros")
        if d["Name"] not in grupos[g]:
            grupos[g].append(d["Name"])
    removiveis = [p.device for p in psutil.disk_partitions(all=False) if "removable" in p.opts]
    if removiveis:
        grupos["Unidades removíveis"] = removiveis
    redes = [{"nome": r.get("Name"), "interface": r.get("InterfaceAlias"), "ipv4": r.get("IPv4")}
             for r in (dados.get("redes") or []) if r]
    return {"status": "medido", "fonte": "Win32_PnPEntity + Get-NetConnectionProfile",
            "grupos": dict(grupos), "redes": redes,
            "internet": any(r.get("ipv4") == "Internet" for r in redes)}
