"""Inicializacao real: cada etapa do boot corresponde a uma verificacao.

A animacao das telas acompanha estas etapas. Nada aqui espera de proposito
para "encher" a animacao, e nenhuma etapa marca ok sem ter verificado.
"""

from __future__ import annotations

import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import sounddevice as sd

from . import OLLAMA, SERVIDOR_OPENJARVIS
from .audio import bloqueio_privacidade
from .telemetria import HOME, configuracao, memoria, ollama

PROJETO = Path(r"C:\Linguagem_C\projeto pessoal\Jarvis")
JARVIS_EXE = PROJETO / ".venv" / "Scripts" / "jarvis.exe"
OLLAMA_EXE = Path(r"C:\Users\mateu\AppData\Local\Programs\Ollama\ollama.exe")
SEM_JANELA = 0x08000000


def _no_ar(url: str, tempo: float = 2.0) -> bool:
    try:
        urllib.request.urlopen(url, timeout=tempo)
        return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError):
        return False


def _pid_vivo(pid: int) -> bool:
    saida = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                           capture_output=True, text=True, check=False,
                           creationflags=SEM_JANELA).stdout
    return str(pid) in saida


def limpar_registro_orfao() -> str | None:
    """server.pid apontando para processo morto impede o servidor de subir."""
    arq = HOME / "server.pid"
    if not arq.exists():
        return None
    try:
        pid = int(arq.read_text().strip())
    except (ValueError, OSError):
        arq.unlink(missing_ok=True)
        return "registro invalido removido"
    if _pid_vivo(pid):
        return None
    arq.unlink(missing_ok=True)
    (HOME / "server.json").unlink(missing_ok=True)
    return f"registro orfao do PID {pid} removido"


def subir_servidor() -> bool:
    # `jarvis serve`, nao `jarvis start`: o start registra o PID do processo
    # que lanca, mas o python.exe do venv do uv e um trampolim -- o servidor
    # real nasce com outro PID e se recusa a subir ("Another server is
    # already registered").
    with open(HOME / "serve.log", "a", encoding="utf-8") as log:
        subprocess.Popen([str(JARVIS_EXE), "serve", "--host", "127.0.0.1", "--port", "8000"],
                         cwd=PROJETO, stdout=log, stderr=log,
                         creationflags=0x00000008 | 0x00000200)  # DETACHED | NEW_GROUP
    for _ in range(45):
        time.sleep(1)
        if _no_ar(f"{SERVIDOR_OPENJARVIS}/health"):
            return True
    return False


def subir_ollama() -> bool:
    if not OLLAMA_EXE.exists():
        return False
    subprocess.Popen([str(OLLAMA_EXE), "serve"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=SEM_JANELA)
    for _ in range(30):
        time.sleep(1)
        if _no_ar(f"{OLLAMA}/api/tags"):
            return True
    return False


def verificar_memoria(modelo_voz: str | None, instalados: list[dict]) -> tuple[str, str]:
    """(estado, detalhe): RAM livre contra o modelo da voz + backend de memoria do OpenJarvis."""
    avisos, partes = [], []
    m = memoria()
    tamanho = next((i["tamanho_gb"] for i in instalados if i["nome"] == modelo_voz), None)
    if m.get("status") == "medido":
        partes.append(f"RAM {m['livre_gb']:.1f} GB livres")
        if tamanho and m["livre_gb"] < tamanho * 1.1:
            avisos.append(f"modelo da voz ({tamanho:.1f} GB) maior que a RAM livre: vai usar memória virtual")
    try:
        with urllib.request.urlopen(f"{SERVIDOR_OPENJARVIS}/v1/memory/stats", timeout=5) as r:
            r.read()
        partes.append("memória do OpenJarvis ok")
    except urllib.error.HTTPError as e:
        motivo = "extensão Rust ausente" if b"openjarvis_rust" in e.read() else f"HTTP {e.code}"
        avisos.append(f"memória do OpenJarvis indisponível ({motivo})")
    except (urllib.error.URLError, OSError):
        avisos.append("memória do OpenJarvis sem resposta")
    return ("aviso" if avisos else "ok"), " · ".join(partes + avisos)


# parecer falado a partir das etapas medidas (servidor e microfone tem frase propria)
PARECER = {
    "memoria": "a memória do computador está apertada, então posso demorar para responder",
    "ollama": "o Ollama não respondeu",
    "modelo_chat": "o modelo do chat não está instalado",
    "modelo_voz": "o modelo da voz não está instalado",
    "transcricao": "a transcrição de voz não carregou",
    "sintese": "a síntese de voz falhou",
    "saida_audio": "não achei a saída de áudio",
    "eventos": "estou sem os eventos do servidor, então algumas métricas ficam sem dados",
}


def parecer(etapas: list[dict]) -> list[str]:
    return [PARECER[x["id"]] for x in etapas if x.get("estado") not in ("ok", None) and x.get("id") in PARECER]


def saudacao(nome: str, resultados: dict[str, bool], escutando: bool,
             exigir_nome: bool = True, mic_bloqueado: bool = False, avisos: list[str] | None = None) -> str:
    hora = datetime.now().hour
    parte = "Bom dia" if hora < 12 else ("Boa tarde" if hora < 19 else "Boa noite")
    frases = [f"{parte}, {nome}." if nome else f"{parte}."]
    if resultados and all(resultados.values()):
        frases.append("Todas as verificações passaram. Sistema online.")
    if not resultados.get("servidor"):
        frases.append("O servidor do OpenJarvis nao respondeu, entao ainda nao consigo conversar.")
    elif escutando:
        frases.append("Estou ouvindo. Me chame de Jarvis quando quiser falar comigo."
                      if exigir_nome else "Estou ouvindo.")
    elif mic_bloqueado:
        frases.append("O Windows está bloqueando o microfone. Libere em Configurações, Privacidade, "
                      "Microfone, e eu volto a ouvir sozinho. Até lá, digite o comando.")
    elif not resultados.get("microfone"):
        frases.append("Nao consegui acessar o microfone; use o chat.")
    else:
        frases.append("Estou pronto.")
    if avisos:
        frases.append("Atenção: " + "; ".join(avisos[:2]) + ".")
    return " ".join(frases)


def executar(rt) -> None:
    """rt: o Runtime (estado, prefs, sintese, transcricao, microfone, conversa, ponte)."""
    e = rt.estado
    ok: dict[str, bool] = {}

    def etapa(nome, estado, detalhe=None):
        e.etapa_boot(nome, estado, detalhe)
        ok[nome] = estado == "ok"

    # 1. servidor
    etapa("servidor", "verificando")
    if _no_ar(f"{SERVIDOR_OPENJARVIS}/health"):
        etapa("servidor", "ok", "ja estava no ar")
    else:
        aviso = limpar_registro_orfao()
        if aviso:
            e.registrar("boot", aviso, "aviso")
        e.etapa_boot("servidor", "verificando", "iniciando jarvis serve...")
        if subir_servidor():
            etapa("servidor", "ok", "iniciado agora")
        else:
            etapa("servidor", "falha", "nao respondeu em 45 s (ver ~/.openjarvis/serve.log)")
    e.atualizar("conexao", servidor={"estado": "ok" if ok["servidor"] else "fora",
                                      "em": time.time()})

    # 2. ollama
    etapa("ollama", "verificando")
    if not _no_ar(f"{OLLAMA}/api/tags"):
        e.etapa_boot("ollama", "verificando", "iniciando ollama serve...")
        subir_ollama()
    info = ollama()
    etapa("ollama", "ok" if info["status"] == "ok" else "falha",
          OLLAMA if info["status"] == "ok" else info.get("detalhe"))
    e.atualizar("conexao", ollama={"estado": "ok" if ok["ollama"] else "fora", "em": time.time()})
    instalados = {m["nome"] for m in info.get("instalados", [])}

    # 3-4. modelos (verifica instalacao; nao carrega nada na memoria)
    cfg = configuracao()
    chat, voz = cfg.get("modelo_chat"), rt.prefs.ler()["modelo_voz"]
    e.atualizar("modelos", chat=chat, voz=voz)
    for nome, modelo in (("modelo_chat", chat), ("modelo_voz", voz)):
        if not modelo:
            etapa(nome, "falha", "nao configurado")
        elif modelo in instalados:
            etapa(nome, "ok", f"{modelo} instalado")
        else:
            etapa(nome, "falha", f"{modelo} nao esta instalado no Ollama")

    # 5-6. audio
    etapa("microfone", "verificando")
    mic_bloqueado = None
    try:
        nome = sd.query_devices(kind="input")["name"]
        with sd.RawInputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1024) as s:
            s.read(1024)
        etapa("microfone", "ok", nome)
    except Exception as ex:  # noqa: BLE001
        mic_bloqueado = bloqueio_privacidade()
        etapa("microfone", "falha", f"bloqueado pelo Windows: {mic_bloqueado}" if mic_bloqueado
              else str(ex)[:120])
    etapa("saida_audio", "verificando")
    try:
        nome = sd.query_devices(kind="output")["name"]
        e.atualizar("reproducao", dispositivo=nome)
        etapa("saida_audio", "ok", nome)
    except Exception as ex:  # noqa: BLE001
        etapa("saida_audio", "falha", str(ex)[:120])

    # 7-8. sintese e transcricao carregam em paralelo (as mais lentas)
    def carregar(nome, obj, rotulo):
        e.etapa_boot(nome, "verificando", f"carregando {rotulo()}...")
        t0 = time.time()
        try:
            obj.carregar()
            etapa(nome, "ok", f"{rotulo()} em {time.time() - t0:.1f} s")
        except Exception as ex:  # noqa: BLE001
            etapa(nome, "falha", str(ex)[:140])

    # rotulos do que carregou DE FATO (voz e tamanho do Whisper vem das preferencias)
    def rotulo_voz():
        return f"Kokoro / {rt.prefs.ler().get('voz_tts') or cfg.get('voz') or 'pf_dora'}"

    def rotulo_stt():
        return f"faster-whisper {getattr(rt.transcricao, 'nome_modelo', None) or rt.prefs.ler().get('stt_modelo', 'small')}"

    fios = [threading.Thread(target=carregar, args=("sintese", rt.sintese, rotulo_voz)),
            threading.Thread(target=carregar, args=("transcricao", rt.transcricao, rotulo_stt))]
    for f in fios:
        f.start()
    for f in fios:
        f.join()

    # 9. eventos
    etapa("eventos", "verificando")
    for _ in range(10):
        if rt.ponte.conectada:
            break
        time.sleep(0.5)
    etapa("eventos", "ok" if rt.ponte.conectada else "falha",
          "/v1/agents/events" if rt.ponte.conectada else "WebSocket nao conectou")

    # 10. memoria: RAM para o modelo + backend de memoria do OpenJarvis
    etapa("memoria", "verificando")
    est_mem, det_mem = verificar_memoria(voz, info.get("instalados", []))
    etapa("memoria", est_mem, det_mem)

    falhas = [n for n, v in ok.items() if not v]
    # "online" so com TODAS as etapas ok; aviso ou falha vira "limitado"
    e.atualizar("boot", concluido=True, resultado="limitado" if falhas else "online")
    e.registrar("boot", "concluido" + (f" com limitações: {', '.join(falhas)}" if falhas else
                                       ": sistema online"),
                "aviso" if falhas else "info")
    if rt.prefs.ler().get("camera_ao_iniciar") and getattr(rt, "camera", None):
        rt.camera.ativar()

    # escuta: so se a preferencia pedir e o que ela precisa estiver de pe
    prefs = rt.prefs.ler()
    # bloqueio do Windows: liga mesmo assim; o microfone espera a liberacao e reabre sozinho
    escutar = (prefs["escuta_automatica"] and (ok.get("microfone") or mic_bloqueado)
               and ok.get("transcricao") and ok.get("servidor"))

    if prefs["saudacao"] and ok.get("sintese") and ok.get("saida_audio"):
        frase = saudacao(prefs["nome_usuario"], ok, bool(escutar and ok.get("microfone")),
                         prefs["exigir_nome"], mic_bloqueado=bool(mic_bloqueado),
                         avisos=parecer(e.ler("boot").get("etapas", [])))
        e.registrar("voz", f"saudacao: {frase}")
        rt.conversa.falar(frase)        # voz das preferencias (pm_alex por padrao)
    if escutar:
        rt.microfone.ativar()
