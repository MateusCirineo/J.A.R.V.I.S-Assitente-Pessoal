"""Rotinas de chegada e de descanso (como no projeto B, adaptadas com seguranca).

Chegada ("Jarvis, cheguei"): cumprimenta, abre os apps e sites escolhidos
(sem abrir de novo o que ja esta aberto), toca o som do proprio usuario se
houver, ajusta o volume e da o resumo do dia.

Descanso ("Jarvis, vou descansar"): para a fala e a musica, desliga a camera
e FECHA SO OS APPS DA ROTINA, com o pedido normal de fechar (WM_CLOSE): se um
programa tiver trabalho nao salvo, ele pergunta e fica aberto. Nada de
taskkill /F nem de fechar tudo o que estiver visivel. Bloquear/suspender so
com confirmacao falada; "opcoes de desligar" so mostra o dialogo do Windows.

Disparo so por frase exata configurada (sem correspondencia parcial).
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import time
import unicodedata
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable

PADRAO_CHEGADA = {"frases": ["cheguei", "estou em casa", "voltei", "papai chegou"], "apps": [], "sites": [],
                  "som": "", "resumo": True, "volume": None}
PADRAO_DESCANSO = {"frases": ["vou descansar", "hora de descansar", "vou dormir", "encerrar o dia"],
                   "fechar_apps": True, "parar_musica": True, "desligar_camera": True, "acao_final": "nada"}
ACOES_FINAIS = {"nada", "bloquear", "suspender", "opcoes_desligar"}
PROTEGIDOS = {"explorer.exe", "python.exe", "pythonw.exe", "svchost.exe", "dwm.exe", "winlogon.exe", "csrss.exe",
              "lsass.exe", "ollama.exe", "ollama app.exe", "jarvis.exe"}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", t).split())


def frase_da_rotina(texto: str, prefs: dict[str, Any]) -> str | None:
    """ "chegada" | "descanso" | None. Frase inteira igual (tirando "Jarvis")."""
    n = _norm(texto)
    n = re.sub(r"^(?:jarvis|jarbas)\s+|\s+(?:jarvis|jarbas)$", "", n).strip()
    for rotina, chave in (("chegada", "rotina_chegada"), ("descanso", "rotina_descanso")):
        frases = (prefs.get(chave) or {}).get("frases") or []
        if n and any(n == _norm(f) for f in frases):
            return rotina
    return None


# ---- validacao (usada pelas preferencias) ----------------------------------
def _textos(v: Any, maximo: int = 10, tam: int = 120) -> list[str]:
    if not isinstance(v, list):
        return []
    return [s.strip()[:tam] for s in v if isinstance(s, str) and s.strip()][:maximo]


def validar_rotina(valor: Any, padrao: dict[str, Any]) -> dict[str, Any]:
    saida = dict(padrao)
    if not isinstance(valor, dict):
        return saida
    for k, v in valor.items():
        if k not in padrao:
            continue
        if k == "frases":
            frases = _textos(v, 8, 60)
            saida[k] = [f for f in frases if len(_norm(f).split()) >= 1] or padrao[k]
        elif k == "apps":
            saida[k] = _textos(v, 10, 260)
        elif k == "sites":
            saida[k] = [s for s in _textos(v, 10, 300) if s.startswith("https://")]
        elif k == "som":
            saida[k] = v.strip()[:260] if isinstance(v, str) else ""
        elif k == "volume":
            saida[k] = int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 100 else None
        elif k == "acao_final":
            saida[k] = v if v in ACOES_FINAIS else "nada"
        elif isinstance(padrao[k], bool) and isinstance(v, bool):
            saida[k] = v
    return saida


# ---- processos e janelas ----------------------------------------------------
def exe_do_app(app: str, achar_app: Callable[[str], tuple[str, str] | None]) -> tuple[str | None, str | None]:
    """(como abrir, nome do .exe) para um app dito pelo nome ou por caminho."""
    p = Path(os.path.expandvars(app))
    if p.suffix.lower() in (".exe", ".lnk") and p.is_file():
        return str(p), p.name.lower() if p.suffix.lower() == ".exe" else None
    achado = achar_app(app)
    if not achado:
        return None, None
    app_id = achado[1]
    exe = app_id.rsplit("\\", 1)[-1].lower() if app_id.lower().endswith(".exe") else None
    return f"shell:AppsFolder\\{app_id}", exe


def rodando(exe: str) -> bool:
    import psutil
    for p in psutil.process_iter(["name"]):
        if (p.info.get("name") or "").lower() == exe:
            return True
    return False


def janelas_do_exe(exe: str) -> list[int]:
    """Janelas principais visiveis de um executavel (sem as do Jarvis)."""
    import psutil
    return janelas_de_pids({p.pid for p in psutil.process_iter(["name"]) if (p.info.get("name") or "").lower() == exe})


def janelas_de_pids(pids: set[int]) -> list[int]:
    from .tela import e_do_jarvis, titulo
    if not pids:
        return []
    u = ctypes.windll.user32
    u.GetWindow.restype = wintypes.HWND
    achadas: list[int] = []
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cada(hwnd, _l):
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and u.IsWindowVisible(hwnd) and not u.GetWindow(hwnd, 4):   # GW_OWNER: so principais
            t = titulo(hwnd)
            if t and not e_do_jarvis(t):
                achadas.append(int(hwnd))
        return True
    u.EnumWindows(PROC(cada), 0)
    return achadas


def fechar_graciosamente(exe: str, espera_s: float = 6.0) -> tuple[int, int]:
    """Pede para fechar (WM_CLOSE). Devolve (janelas pedidas, janelas que ficaram)."""
    if exe in PROTEGIDOS:
        return 0, 0
    return fechar_janelas(janelas_do_exe(exe), espera_s)


def fechar_janelas(janelas: list[int], espera_s: float = 6.0) -> tuple[int, int]:
    for h in janelas:
        ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)          # WM_CLOSE, o mesmo do X da janela
    fim = time.time() + espera_s
    while janelas and time.time() < fim:
        time.sleep(0.4)
        if not [h for h in janelas if ctypes.windll.user32.IsWindow(h) and ctypes.windll.user32.IsWindowVisible(h)]:
            return len(janelas), 0
    ficaram = [h for h in janelas if ctypes.windll.user32.IsWindow(h) and ctypes.windll.user32.IsWindowVisible(h)]
    return len(janelas), len(ficaram)


# ---- acoes finais (com confirmacao) -----------------------------------------
def bloquear() -> bool:
    return bool(ctypes.windll.user32.LockWorkStation())


def suspender() -> bool:
    return bool(ctypes.windll.powrprof.SetSuspendState(False, True, False))


def opcoes_desligar() -> None:
    """So abre o dialogo do Windows (Desligar/Reiniciar/Suspender): o usuario escolhe."""
    subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                      "(New-Object -ComObject Shell.Application).ShutdownWindows()"], creationflags=0x08000000)


# ---- inicio com o Windows (R4): so quando o usuario liga no Painel ----------
def _atalho_inicio() -> Path:
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / \
        "Jarvis - iniciar com o Windows.lnk"


def inicio_com_windows() -> bool:
    return _atalho_inicio().is_file()


def definir_inicio_com_windows(ligar: bool, lancador: Path) -> bool:
    atalho = _atalho_inicio()
    if not ligar:
        if atalho.is_file():
            atalho.unlink()
        return False
    if not lancador.is_file():
        raise FileNotFoundError(f"lançador não encontrado: {lancador}")
    ps = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:ATALHO); "
          "$s.TargetPath = $env:ALVO; $s.Arguments = '--sem-janelas'; $s.WindowStyle = 7; "
          "$s.WorkingDirectory = Split-Path $env:ALVO; $s.Description = 'Jarvis (HUD) ao entrar no Windows'; $s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], check=True, timeout=30,
                   creationflags=0x08000000, env={**os.environ, "ATALHO": str(atalho), "ALVO": str(lancador)})
    return atalho.is_file()


class Rotinas:
    def __init__(self, rt: Any, achar_app: Callable[[str], tuple[str, str] | None]) -> None:
        self.rt = rt
        self._achar_app = achar_app

    def chegada(self) -> str:
        from . import midia
        p = self.rt.prefs.ler()
        cfg = p.get("rotina_chegada") or PADRAO_CHEGADA
        trat = p.get("nome_usuario") or "Senhor"
        abertos, ja, falhas = [], [], []
        for app in cfg.get("apps", []):
            alvo, exe = exe_do_app(app, self._achar_app)
            if not alvo:
                falhas.append(app)
                continue
            if exe and rodando(exe):
                ja.append(app)
                continue
            try:
                os.startfile(alvo)
                abertos.append(app)
                time.sleep(0.6)
            except OSError:
                falhas.append(app)
        for url in cfg.get("sites", []):
            if url.startswith("https://"):
                os.startfile(url)
                time.sleep(0.4)
        if isinstance(cfg.get("volume"), int):
            midia.definir_volume(cfg["volume"] / 100, False)
        som = cfg.get("som") or ""
        if som and Path(som).is_file():
            self._tocar_som(Path(som))
        frases = [f"Bem-vindo de volta, {trat}."]
        if abertos:
            frases.append("Abri " + ", ".join(abertos) + ".")
        if ja:
            frases.append(", ".join(ja) + (" já estava aberto." if len(ja) == 1 else " já estavam abertos."))
        if falhas:
            frases.append("Não achei " + ", ".join(falhas) + ".")
        if cfg.get("resumo", True) and getattr(self.rt, "comandos", None):
            frases.append(self.rt.comandos.briefing().split(". ", 1)[-1])      # sem repetir o cumprimento
        return " ".join(frases)

    def _tocar_som(self, caminho: Path) -> None:
        import threading

        from .vozes import de_mp3

        def tocar():
            try:
                audio, taxa = de_mp3(caminho.read_bytes())
                self.rt.reprodutor.tocar(audio, taxa)
            except Exception as e:  # noqa: BLE001 - o som e enfeite; a rotina segue
                self.rt.estado.registrar("rotina", f"som da chegada falhou: {e}", "aviso")
        threading.Thread(target=tocar, name="som-chegada", daemon=True).start()

    def descanso(self) -> tuple[str, str | None]:
        """(fala, acao_final pendente de confirmacao ou None)."""
        from . import midia
        p = self.rt.prefs.ler()
        cfg = p.get("rotina_descanso") or PADRAO_DESCANSO
        trat = p.get("nome_usuario") or "Senhor"
        if getattr(self.rt, "anunciador", None):
            self.rt.anunciador.limpar()
        if cfg.get("parar_musica", True):
            m = midia.estado_midia()
            if m.get("status") == "medido" and m.get("situacao") == "tocando":
                midia.controlar("tocar_pausar")
        if cfg.get("desligar_camera", True) and getattr(self.rt, "camera", None) and self.rt.camera.ativa:
            self.rt.camera.desativar()
        fechados, ficaram = [], []
        if cfg.get("fechar_apps", True):
            chegada = (p.get("rotina_chegada") or PADRAO_CHEGADA).get("apps", [])
            for app in chegada:
                _, exe = exe_do_app(app, self._achar_app)
                if not exe:
                    continue
                pedidas, restantes = fechar_graciosamente(exe)
                if pedidas and not restantes:
                    fechados.append(app)
                elif restantes:
                    ficaram.append(app)
        frases = []
        if fechados:
            frases.append("Fechei " + ", ".join(fechados) + ".")
        if ficaram:
            frases.append(", ".join(ficaram) + " pediu para salvar alguma coisa; deixei aberto para o senhor decidir.")
        acao = cfg.get("acao_final", "nada")
        if acao == "opcoes_desligar":
            opcoes_desligar()
            frases.append("Abri as opções de desligar.")
            acao = None
        elif acao in ("bloquear", "suspender"):
            frases.append(f"Para {'bloquear' if acao == 'bloquear' else 'suspender'} o computador, diga: "
                          f"Jarvis, confirmo {acao}.")
        else:
            acao = None
        frases.append(f"Bom descanso, {trat}.")
        return " ".join(frases), acao
