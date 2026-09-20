"""Ativacao por duas palmas: abre o Jarvis sem tocar no computador.

Recurso proprio desta instalacao (nao existe no OpenJarvis). Privacidade: le
o microfone so para medir o pico de cada bloco de 16 ms. Nada e gravado,
transcrito, salvo ou enviado.

Modos:
    escuta_palmas.py --uma-vez    espera as palmas, abre o Jarvis e sai
                                  (icone "Jarvis - Modo Show")
    escuta_palmas.py --continuo   fica sempre de prontidao (inicio do Windows);
                                  enquanto o Jarvis estiver aberto, larga o
                                  microfone e so volta a escutar quando ele fechar

Ajustes:
    JARVIS_CLAP_THRESH   limiar minimo do pico (0.05..0.9, padrao 0.25). O
                         detector tambem sobe o limiar sozinho com o ruido.
    JARVIS_MIC           numero ou parte do nome do microfone
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import sounddevice as sd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

from hud_runtime.palmas import BLOCO, TAXA, DetectorPalmas  # noqa: E402

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
TRAVA = HOME / "palmas.pid"
PYTHON = AQUI.parent / ".venv" / "Scripts" / "python.exe"
RUNTIME = AQUI / "jarvis_runtime.py"


def log(msg: str) -> None:
    print(f"[palmas {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def limiar() -> float:
    try:
        return min(max(float(os.environ.get("JARVIS_CLAP_THRESH", "0.25")), 0.05), 0.9)
    except ValueError:
        return 0.25


def microfone() -> int | None:
    alvo = os.environ.get("JARVIS_MIC", "").strip()
    if not alvo:
        return None
    if alvo.isdigit():
        return int(alvo)
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and alvo.lower() in d["name"].lower():
            return i
    return None


def runtime_ativo() -> dict | None:
    try:
        inst = json.loads((HOME / "hud-runtime.json").read_text(encoding="utf-8"))
        with urllib.request.urlopen(f"http://127.0.0.1:{inst['porta']}/api/saude", timeout=2) as r:
            if json.load(r).get("servico") == "jarvis-hud":
                return inst
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        pass
    return None


def abrir_jarvis() -> None:
    inst = runtime_ativo()
    if inst:
        req = urllib.request.Request(
            f"http://127.0.0.1:{inst['porta']}/api/janela",
            data=json.dumps({"nome": "jarvis"}).encode(),
            headers={"Content-Type": "application/json", "X-Jarvis-Token": inst["token"]})
        urllib.request.urlopen(req, timeout=5).read()
        log("Jarvis ja estava aberto: janela trazida para frente")
        return
    pythonw = PYTHON.with_name("pythonw.exe")                 # tela de "Inicializando" enquanto sobe
    if pythonw.exists():
        subprocess.Popen([str(pythonw), str(AQUI / "splash.py"), "--show"], cwd=AQUI.parent)
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 7                                  # minimizada, sem roubar foco
    subprocess.Popen([str(PYTHON), str(RUNTIME), "--janelas", "jarvis,painel"],
                     cwd=AQUI.parent, startupinfo=info,
                     creationflags=subprocess.CREATE_NEW_CONSOLE)
    log("Jarvis iniciado")


def esperar_palmas(det: DetectorPalmas, ceder_ao_jarvis: bool) -> bool:
    """True quando ouve duas palmas. False se o Jarvis abriu por outro caminho
    (icone): larga o microfone para nao haver duas capturas ao mesmo tempo."""
    checar_a_cada = int(2.0 * TAXA / BLOCO)
    with sd.InputStream(samplerate=TAXA, blocksize=BLOCO, channels=1,
                        dtype="float32", device=microfone()) as fluxo:
        n = 0
        while True:
            bloco, _ = fluxo.read(BLOCO)
            if det.processar(bloco[:, 0]):
                return True
            n += 1
            if ceder_ao_jarvis and n % checar_a_cada == 0 and runtime_ativo():
                return False


def motivo_sem_microfone(erro: Exception) -> str:
    """Motivo legivel: a privacidade do Windows costuma ser a causa do "MME error 1"."""
    try:
        from hud_runtime.audio import bloqueio_privacidade
        motivo = bloqueio_privacidade()
    except Exception:  # noqa: BLE001
        motivo = None
    return f"o Windows está bloqueando o microfone: {motivo}" if motivo else f"microfone indisponível ({erro})"


def unica_instancia() -> bool:
    try:
        pid = int(TRAVA.read_text())
        vivo = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True,
                              text=True, creationflags=0x08000000).stdout
        if str(pid) in vivo and pid != os.getpid():
            return False
    except (OSError, ValueError):
        pass
    TRAVA.write_text(str(os.getpid()))
    return True


def main() -> int:
    continuo = "--continuo" in sys.argv
    if sys.stdout is None:             # pythonw (inicio do Windows): sem console
        sys.stdout = sys.stderr = open(HOME / "palmas.log", "a", encoding="utf-8")  # noqa: SIM115
    if continuo and not unica_instancia():
        return 0                       # ja ha uma escuta continua rodando
    det = DetectorPalmas(limiar())
    ultimo_motivo = None
    try:
        while True:
            if continuo:
                if runtime_ativo():
                    log("Jarvis aberto: microfone liberado para ele")
                    while runtime_ativo():     # o microfone e do Jarvis agora
                        time.sleep(3)
                log(f"escutando palmas (limiar minimo {limiar()})")
            else:
                print("\n  MODO SHOW - bata palma duas vezes.")
                print("  (feche esta janela para cancelar)\n")
            try:
                palmas = esperar_palmas(det, ceder_ao_jarvis=continuo)
            except sd.PortAudioError as e:
                motivo = motivo_sem_microfone(e)
                if not continuo:
                    # sem microfone nao ha palmas: em vez de fechar, abre o Jarvis direto
                    print(f"  Não consigo ouvir as palmas: {motivo}.")
                    print("  Abrindo o Jarvis direto (o microfone volta sozinho quando for liberado).")
                    print()
                    log(f"modo show sem microfone: {motivo}; abrindo o Jarvis direto")
                    try:
                        abrir_jarvis()
                    except Exception as e2:  # noqa: BLE001
                        print(f"  Falhou ao abrir o Jarvis: {e2}")
                        log(f"falha ao abrir: {e2}")
                        time.sleep(15)
                        return 1
                    time.sleep(6)                       # tempo de ler a mensagem
                    return 0
                if motivo != ultimo_motivo:             # registra uma vez, nao a cada 10 s
                    log(f"sem palmas por enquanto: {motivo}")
                    ultimo_motivo = motivo
                time.sleep(10)
                continue
            ultimo_motivo = None
            if not palmas:
                continue               # Jarvis abriu pelo icone: volta ao topo e cede
            log("duas palmas")
            try:
                abrir_jarvis()
            except Exception as e:  # noqa: BLE001
                log(f"falha ao abrir: {e}")
            if not continuo:
                return 0
            time.sleep(8)              # da tempo do runtime subir e registrar a instancia
            det = DetectorPalmas(limiar())
    except KeyboardInterrupt:
        return 0
    finally:
        if continuo:
            try:
                if TRAVA.read_text() == str(os.getpid()):
                    TRAVA.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
