"""Audio real: captura, transcricao, sintese e reproducao.

Niveis e espectros enviados as telas sao calculados das amostras que de fato
passam pelo microfone ou que de fato sao entregues ao dispositivo de saida.
Nada aqui e aleatorio.

O estado "falando" comeca no primeiro bloco entregue ao dispositivo (callback
de saida), nao quando a sintese termina, e acaba no finished_callback do
stream, nao quando o buffer foi preenchido.
"""

from __future__ import annotations

import audioop
import io
import queue
import re
import threading
import time
import wave
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd

from .estado import Estado

# ---------------------------------------------------------------------------
# privacidade do Windows
# ---------------------------------------------------------------------------

CONSENTIMENTO_MIC = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
CAMINHO_CONFIG = "Configurações > Privacidade e segurança > Microfone"


def bloqueio_privacidade() -> str | None:
    """Se o Windows estiver negando o microfone, diz qual chave; senao None.

    So le o registro (nunca altera). Com o acesso negado, todas as APIs de
    audio falham com erros genericos ("MME error 1", "Invalid device").
    """
    try:
        import winreg
    except ImportError:
        return None

    def valor(raiz, sub: str) -> str | None:
        try:
            with winreg.OpenKey(raiz, sub) as k:
                return str(winreg.QueryValueEx(k, "Value")[0])
        except OSError:
            return None

    if valor(winreg.HKEY_LOCAL_MACHINE, CONSENTIMENTO_MIC) == "Deny":
        return f"acesso ao microfone desligado neste dispositivo ({CAMINHO_CONFIG} > Acesso ao microfone)"
    if valor(winreg.HKEY_CURRENT_USER, CONSENTIMENTO_MIC) == "Deny":
        return f"acesso ao microfone desligado para este usuário ({CAMINHO_CONFIG} > Acesso ao microfone)"
    if valor(winreg.HKEY_CURRENT_USER, CONSENTIMENTO_MIC + r"\NonPackaged") == "Deny":
        return (f"aplicativos da área de trabalho sem acesso ao microfone ({CAMINHO_CONFIG} > "
                "Permitir que aplicativos da área de trabalho acessem o microfone)")
    return None


def reiniciar_portaudio() -> None:
    """Refaz a lista de dispositivos do PortAudio (depois de mudar permissao/dispositivo)."""
    try:
        sd._terminate()
        sd._initialize()
    except Exception:  # noqa: BLE001
        pass

# ---------------------------------------------------------------------------
# espectro
# ---------------------------------------------------------------------------

N_BANDAS = 32


def bandas(amostras: np.ndarray, taxa: int, n: int = N_BANDAS) -> list[float]:
    """Magnitude por faixa log-espacada (80 Hz..8 kHz), em 0..1 (-60..0 dBFS)."""
    if amostras.size < 128:
        return [0.0] * n
    janela = amostras.astype(np.float32) * np.hanning(amostras.size).astype(np.float32)
    mag = np.abs(np.fft.rfft(janela)) / (amostras.size / 4.0)
    freqs = np.fft.rfftfreq(amostras.size, 1.0 / taxa)
    limites = np.geomspace(80.0, min(8000.0, taxa / 2.0), n + 1)
    saida = []
    for a, b in zip(limites[:-1], limites[1:]):
        sel = mag[(freqs >= a) & (freqs < b)]
        v = float(sel.max()) if sel.size else 0.0
        db = 20.0 * np.log10(max(v, 1e-6))
        saida.append(round(float(np.clip((db + 60.0) / 60.0, 0.0, 1.0)), 3))
    return saida


def forma_de_onda(amostras: np.ndarray, n: int = 48) -> list[float]:
    """Onda do bloco reduzida a n pontos: em cada trecho, o pico COM sinal
    (preserva o formato; media de trecho zeraria a onda)."""
    if amostras.size < n:
        return [0.0] * n
    trechos = np.array_split(amostras.astype(np.float32), n)
    return [round(float(t[np.argmax(np.abs(t))]), 3) for t in trechos]


# ---------------------------------------------------------------------------
# reproducao
# ---------------------------------------------------------------------------

class Reprodutor:
    def __init__(self, estado: Estado) -> None:
        self._estado = estado
        self._volume = 1.0
        self._parar = threading.Event()
        self._livre = threading.Event()
        self._livre.set()
        self._trava = threading.Lock()

    @property
    def falando(self) -> bool:
        return not self._livre.is_set()

    def volume(self, v: float) -> None:
        self._volume = float(min(max(v, 0.0), 1.0))
        self._estado.atualizar("reproducao", volume=self._volume)

    def parar(self) -> bool:
        """Interrompe so a reproducao. Nao cancela nenhuma geracao."""
        if self.falando:
            self._parar.set()
            return True
        return False

    def tocar(self, audio: np.ndarray, taxa: int, *, cancelado: threading.Event | None = None) -> str:
        """Toca e bloqueia ate terminar. Devolve 'concluido', 'interrompido' ou 'erro'."""
        with self._trava:
            if cancelado is not None and cancelado.is_set():
                return "interrompido"
            self._parar.clear()
            self._livre.clear()
            audio = np.asarray(audio, dtype=np.float32).reshape(-1)
            pos = 0
            iniciou = False
            fim = threading.Event()
            self._estado.atualizar("reproducao", estado="preparando", detalhe=None)

            def callback(saida, frames, _tempo, _status):
                nonlocal pos, iniciou
                if self._parar.is_set() or cancelado is not None and cancelado.is_set():
                    saida.fill(0)
                    raise sd.CallbackStop
                bloco = audio[pos:pos + frames] * self._volume
                n = bloco.size
                saida[:n, 0] = bloco
                saida[n:, 0] = 0
                pos += frames
                if not iniciou:
                    iniciou = True
                    self._estado.atualizar("reproducao", estado="falando", inicio=time.time())
                if n:
                    rms = float(np.sqrt(np.mean(bloco * bloco)))
                    self._estado.nivel("saida", rms, bandas(bloco, taxa), onda=forma_de_onda(bloco))
                if n < frames:
                    raise sd.CallbackStop

            try:
                dispositivo = sd.query_devices(kind="output")["name"]
                with sd.OutputStream(samplerate=taxa, channels=1, dtype="float32",
                                     blocksize=1024, callback=callback,
                                     finished_callback=fim.set):
                    self._estado.atualizar("reproducao", dispositivo=dispositivo)
                    fim.wait()
            except Exception as e:  # noqa: BLE001
                self._estado.atualizar("reproducao", estado="erro", detalhe=str(e)[:160])
                self._livre.set()
                return "erro"

            interrompido = self._parar.is_set() or cancelado is not None and cancelado.is_set()
            self._estado.nivel("saida", 0.0, [0.0] * N_BANDAS, taxa_hz=1000)
            self._estado.atualizar("reproducao", estado="parado", inicio=None)
            self._livre.set()
            return "interrompido" if interrompido else "concluido"


# ---------------------------------------------------------------------------
# sintese e transcricao (carregadas uma vez)
# ---------------------------------------------------------------------------

class Sintese:
    TAXA = 24000

    def __init__(self) -> None:
        self._pipe = None
        self._trava = threading.Lock()

    @property
    def pronta(self) -> bool:
        return self._pipe is not None

    def carregar(self) -> None:
        from kokoro import KPipeline
        # "p" = portugues brasileiro; carregado uma vez so (antes era recriado
        # a cada fala, somando segundos em toda resposta)
        self._pipe = KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M")

    def gerar(self, texto: str, voz: str = "pf_dora", velocidade: float = 1.0) -> np.ndarray:
        texto = pronuncia(texto)
        with self._trava:
            partes = [np.asarray(a, dtype=np.float32)
                      for _, _, a in self._pipe(texto, voice=voz, speed=velocidade)]
        return np.concatenate(partes) if partes else np.zeros(1, dtype=np.float32)


# Pela regra do portugues, "Jarvis" (terminada em -is) e oxitona: a voz dizia
# "Jarviz". Escrito "Jarvis" com acento no "a", a silaba forte vira o "Ja".
# Vale so para a VOZ; na tela continua "Jarvis".
_NOME = re.compile(r"\bJ\.A\.R\.V\.I\.S\.?(?=\s|$)|\bJarvis\b", re.I)


def pronuncia(texto: str) -> str:
    return _NOME.sub("Járvis", texto)


# dica de vocabulario para o Whisper: puxa para os comandos do Jarvis (medido:
# no base, de 3 para 6 frases certas em 6; "Jarvis, cheguei" deixou de virar "Shiggy")
DICA_STT = ("Jarvis, cheguei. Jarvis, vou descansar. Jarvis, que horas são? Jarvis, notícias de tecnologia. "
            "Jarvis, me lembre de ligar às 15h. Jarvis, quanto está o dólar? Jarvis, olhe minha tela.")

MODELO_VOSK = Path(__file__).resolve().parent.parent / "modelos" / "vosk-model-small-pt-0.3"
# o modelo pequeno do VOSK nao tem a palavra "Jarvis" (ouve "arvores"): so a
# PRIMEIRA palavra, e so no VOSK, vira "Jarvis" (medido com a voz Maria do Windows)
_VOSK_JARVIS = re.compile(r"^(?:árvores?|arvores?|jardins?|jarvis|jarbas|garvis|charles)\b", re.I)


class Transcricao:
    """Whisper (padrao, mais preciso) ou VOSK (projeto B: offline, leve, menos preciso).

    O motor vem da preferencia "stt_motor" a cada frase; o VOSK carrega na
    primeira vez que for escolhido. Se ele falhar, a frase vai para o Whisper."""

    def __init__(self, motor: Callable[[], str] | None = None, tamanho: Callable[[], str] | None = None) -> None:
        self._modelo = None
        self._motor = motor or (lambda: "whisper")
        self._tamanho = tamanho or (lambda: "small")
        self.nome_modelo: str | None = None
        self._vosk = None
        self._trava = threading.Lock()      # conversa e vigia de "pare" usam o mesmo modelo

    @property
    def pronta(self) -> bool:
        return self._modelo is not None

    def carregar(self) -> None:
        """Whisper "small" por padrao (mais preciso em portugues; ~3 s por frase
        nesta CPU); "base" e mais rapido (~1 s) e erra mais."""
        from faster_whisper import WhisperModel
        nome = self._tamanho() if self._tamanho() in ("base", "small") else "small"
        self._modelo = WhisperModel(nome, device="cpu", compute_type="int8")
        self.nome_modelo = nome

    def _conferir_modelo(self) -> None:
        """Trocou a preferencia: recarrega na proxima frase (sem reiniciar o Jarvis)."""
        if self._modelo is not None and self._tamanho() in ("base", "small") and self._tamanho() != self.nome_modelo:
            self.carregar()

    def _vosk_modelo(self):
        if self._vosk is None:
            import vosk
            vosk.SetLogLevel(-1)
            self._vosk = vosk.Model(str(MODELO_VOSK))
        return self._vosk

    def transcrever_vosk(self, wav: bytes) -> str:
        import json as _json

        import vosk
        with wave.open(io.BytesIO(wav)) as w:
            taxa, quadros = w.getframerate(), w.readframes(w.getnframes())
        rec = vosk.KaldiRecognizer(self._vosk_modelo(), taxa)
        rec.AcceptWaveform(quadros)
        texto = _json.loads(rec.FinalResult()).get("text", "")
        return filtrar_transcricao(_VOSK_JARVIS.sub("Jarvis,", texto, count=1))

    def transcrever(self, wav: bytes, idioma: str = "pt") -> str:
        if self._motor() == "vosk" and MODELO_VOSK.is_dir():
            try:
                return self.transcrever_vosk(wav)
            except Exception:  # noqa: BLE001 - VOSK falhou: a frase nao se perde, vai ao Whisper
                pass
        # vad_filter (Silero, embutido no faster-whisper) corta trechos sem voz;
        # sem ele o Whisper "ouve" frases em ruido -- aqui chegou a devolver
        # "..." e o modelo respondeu a isso.
        # hotwords puxa a transcricao para "Jarvis" (sem isso vinha "Jarbas",
        # "Chaves"... e a fala era descartada por nao chamar o Jarvis)
        with self._trava:
            self._conferir_modelo()
            segmentos, _ = self._modelo.transcribe(io.BytesIO(wav), language=idioma, vad_filter=True,
                                                   hotwords="Jarvis", initial_prompt=DICA_STT)
            segmentos = list(segmentos)
        partes = [s.text for s in segmentos
                  if not (s.no_speech_prob > 0.6 and s.avg_logprob < -0.8)]
        return filtrar_transcricao(" ".join(partes))


# Frases que o Whisper inventa sobre silencio/ruido (vem das legendas do treino).
_ALUCINACOES = {"legendas pela comunidade amaraorg", "legenda adriana zanotto",
                "inscrevase no canal", "subtitles by the amaraorg community"}


def filtrar_transcricao(texto: str) -> str:
    """Devolve '' quando a transcricao nao tem fala de verdade."""
    texto = (texto or "").strip()
    letras = sum(c.isalpha() for c in texto)
    if letras < 2:
        return ""
    normal = "".join(c for c in texto.lower() if c.isalnum() or c == " ")
    normal = " ".join(normal.split())
    if normal.replace(" ", "") in {a.replace(" ", "") for a in _ALUCINACOES}:
        return ""
    return texto


# ---------------------------------------------------------------------------
# microfone
# ---------------------------------------------------------------------------

TAXA_MIC = 16000
BLOCO_MIC = 1024
BLOCOS_S = TAXA_MIC / BLOCO_MIC


def calcular_limiar(niveis: list[int], margem: float = 2.6,
                    piso: int = 380, teto: int = 2600) -> tuple[int, int]:
    """(ruido, limiar) pela MEDIANA: um barulho isolado nao contamina a conta."""
    ruido = int(np.median(niveis)) if niveis else 0
    return ruido, int(min(max(ruido * margem, piso), teto))


class Microfone(threading.Thread):
    """Escuta continua enquanto ativo; entrega cada fala completa em `falas`.

    Durante a resposta (inferencia ou reproducao) a captura normal fica
    pausada: evita transcrever o eco da propria voz. Se `ouvir_interrupcao`
    permitir, frases CURTAS e mais altas que o normal ainda sao captadas e vao
    para `interrupcoes`, onde so um "pare"/"silencio" tem efeito.
    """

    INTERRUPCAO_MAX_S = 3.0
    INTERRUPCAO_GANHO = 1.8                 # limiar mais alto: a propria voz nao dispara

    ESPERA_ERRO_S = (2, 5, 10)             # novas tentativas antes de desligar
    ESPERA_BLOQUEIO_S = 3

    INICIO_FALA = 3
    SILENCIO_S = 1.1
    MAX_FALA_S = 25.0
    MIN_FALA_S = 0.45

    def __init__(self, estado: Estado, ocupado: Callable[[], bool],
                 ouvir_interrupcao: Callable[[], bool] | None = None) -> None:
        super().__init__(name="microfone", daemon=True)
        self._estado = estado
        self._ocupado = ocupado
        self._ouvir_interrupcao = ouvir_interrupcao or (lambda: False)
        self._ativo = threading.Event()
        self._encerrar = threading.Event()
        self.falas: queue.Queue[bytes] = queue.Queue(maxsize=3)
        self.interrupcoes: queue.Queue[bytes] = queue.Queue(maxsize=2)

    @property
    def ativo(self) -> bool:
        return self._ativo.is_set()

    def ativar(self) -> None:
        self._ativo.set()

    def desativar(self) -> None:
        self._ativo.clear()

    def encerrar(self) -> None:
        self._encerrar.set()
        self._ativo.set()     # destrava a espera

    def _nivel(self, dados: bytes, rms: int) -> None:
        amostras = np.frombuffer(dados, dtype=np.int16).astype(np.float32) / 32768.0
        self._estado.nivel("entrada", rms / 32768.0, bandas(amostras, TAXA_MIC), taxa_hz=15,
                           onda=forma_de_onda(amostras))

    def run(self) -> None:
        falhas = 0
        while not self._encerrar.is_set():
            self._ativo.wait()
            if self._encerrar.is_set():
                break
            self._abriu = False
            try:
                self._sessao()
                falhas = 0
            except Exception as e:  # noqa: BLE001
                if self._abriu:                 # caiu depois de funcionar: conta do zero
                    falhas = 0
                motivo = bloqueio_privacidade()
                if motivo:
                    self._aguardar_liberacao(motivo)
                    falhas = 0
                    continue
                falhas += 1
                if falhas <= len(self.ESPERA_ERRO_S):
                    espera = self.ESPERA_ERRO_S[falhas - 1]
                    self._estado.atualizar("microfone", estado="erro",
                                           detalhe=f"{str(e)[:120]} (nova tentativa em {espera} s)")
                    self._estado.registrar("microfone", f"falha ({falhas}): {e}", "aviso")
                    if falhas >= 2 and not self._ocupado():
                        reiniciar_portaudio()
                    self._encerrar.wait(espera)
                    continue
                self._estado.atualizar("microfone", estado="erro", detalhe=str(e)[:160])
                self._estado.registrar("microfone", f"falha: {e}", "erro")
                self._ativo.clear()
                falhas = 0
            if not self._ativo.is_set():
                self._estado.atualizar("microfone", estado="desativado", detalhe=None)
                self._estado.nivel("entrada", 0.0, None, taxa_hz=1000)

    def _aguardar_liberacao(self, motivo: str) -> None:
        """Microfone continua "ligado" na intencao; reabre sozinho quando o Windows liberar."""
        self._estado.atualizar("microfone", estado="bloqueado", detalhe=f"Windows: {motivo}")
        self._estado.registrar("microfone", f"bloqueado pelo Windows: {motivo}", "aviso")
        self._estado.nivel("entrada", 0.0, None, taxa_hz=1000)
        while self._ativo.is_set() and not self._encerrar.is_set():
            if self._encerrar.wait(self.ESPERA_BLOQUEIO_S):
                return
            if bloqueio_privacidade() is None:
                self._estado.registrar("microfone", "acesso ao microfone liberado; reabrindo")
                if not self._ocupado():
                    reiniciar_portaudio()
                return

    def _sessao(self) -> None:
        nome = sd.query_devices(kind="input")["name"]
        with sd.RawInputStream(samplerate=TAXA_MIC, channels=1, dtype="int16",
                               blocksize=BLOCO_MIC) as fluxo:
            self._abriu = True
            self._estado.atualizar("microfone", estado="calibrando", dispositivo=nome,
                                   detalhe="medindo o ruido do ambiente")
            niveis = []
            for _ in range(int(2.0 * BLOCOS_S)):
                raw, _ = fluxo.read(BLOCO_MIC)
                dados = bytes(raw)
                rms = audioop.rms(dados, 2)
                niveis.append(rms)
                self._nivel(dados, rms)
            ruido, limiar = calcular_limiar(niveis)
            self._estado.atualizar("microfone", estado="ouvindo", ruido_rms=ruido,
                                   limiar_rms=limiar, detalhe=None)
            self._estado.registrar("microfone", f"ouvindo (ruido {ruido}, limiar {limiar})")

            quadros: list[bytes] = []
            acima = silencio = 0
            captando = False
            pausado = False
            lim_silencio = int(self.SILENCIO_S * BLOCOS_S)
            lim_max = int(self.MAX_FALA_S * BLOCOS_S)

            breve: list[bytes] = []            # frase curta durante a resposta
            breve_acima = breve_silencio = 0
            while self._ativo.is_set() and not self._encerrar.is_set():
                raw, _ = fluxo.read(BLOCO_MIC)
                dados = bytes(raw)

                if self._ocupado() and self._ouvir_interrupcao():
                    rms = audioop.rms(dados, 2)
                    alto = rms > limiar * self.INTERRUPCAO_GANHO
                    if not breve:
                        breve_acima = breve_acima + 1 if alto else 0
                        if breve_acima >= self.INICIO_FALA:
                            breve = [dados]
                    else:
                        breve.append(dados)
                        breve_silencio = 0 if alto else breve_silencio + 1
                        if breve_silencio >= lim_silencio or len(breve) / BLOCOS_S >= self.INTERRUPCAO_MAX_S:
                            if len(breve) / BLOCOS_S >= self.MIN_FALA_S:
                                self._entregar(breve, self.interrupcoes)
                            breve, breve_acima, breve_silencio = [], 0, 0
                elif breve:
                    breve, breve_acima, breve_silencio = [], 0, 0

                if self._ocupado():
                    if not pausado:
                        pausado = True
                        quadros.clear()
                        acima = silencio = 0
                        captando = False
                        self._estado.atualizar("microfone", estado="pausado",
                                               detalhe="aguardando a resposta terminar")
                        self._estado.nivel("entrada", 0.0, None, taxa_hz=1000)
                    continue
                if pausado:
                    pausado = False
                    self._estado.atualizar("microfone", estado="ouvindo", detalhe=None)

                rms = audioop.rms(dados, 2)
                self._nivel(dados, rms)

                if not captando:
                    if rms > limiar:
                        acima += 1
                        quadros.append(dados)
                        if acima >= self.INICIO_FALA:
                            captando = True
                            self._estado.atualizar("microfone", estado="captando")
                    else:
                        acima = 0
                        quadros.clear()
                    continue

                quadros.append(dados)
                silencio = 0 if rms > limiar else silencio + 1
                if silencio >= lim_silencio or len(quadros) >= lim_max:
                    if len(quadros) / BLOCOS_S >= self.MIN_FALA_S:
                        self._entregar(quadros)
                    quadros = []
                    acima = silencio = 0
                    captando = False
                    self._estado.atualizar("microfone", estado="ouvindo")

    def _entregar(self, quadros: list[bytes], fila: "queue.Queue[bytes] | None" = None) -> None:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(TAXA_MIC)
            w.writeframes(b"".join(quadros))
        try:
            (fila if fila is not None else self.falas).put_nowait(buf.getvalue())
        except queue.Full:
            self._estado.registrar("microfone", "fala descartada: fila cheia", "aviso")
