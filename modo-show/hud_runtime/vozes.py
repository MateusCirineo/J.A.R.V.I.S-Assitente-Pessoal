"""Catalogo de vozes (TTS): um so ponto para todos os motores.

| provedor   | onde roda | precisa de                          |
|------------|-----------|-------------------------------------|
| kokoro     | local     | nada (ja instalado)                  |
| sapi       | local     | voz do Windows (Maria pt-BR aqui)    |
| piper      | local     | piper.exe + modelo .onnx (download)  |
| edge       | REMOTO    | internet (Microsoft, sem conta)      |
| azure      | REMOTO    | chave + regiao (Azure Speech)        |
| google     | REMOTO    | chave (Google Cloud Text-to-Speech)  |
| elevenlabs | REMOTO    | chave + voice_id                     |
| fish       | REMOTO    | chave + reference_id (fish.audio)    |

Regras:
- Remoto so e usado se voce o escolher; o texto falado vai para o provedor.
- Se o escolhido falhar, cai para o Kokoro LOCAL (nunca o contrario).
- Chaves ficam em ~/.openjarvis/hud-segredos.json e nunca voltam para as telas.
"""

from __future__ import annotations

import io
import json
import threading
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .agenda import gravar_segredo, ler_segredo

PROVEDORES: dict[str, dict[str, Any]] = {
    "kokoro": {"nome": "Kokoro", "remoto": False, "precisa": [],
               "vozes": ["pm_alex", "pm_santa", "pf_dora"]},
    "sapi": {"nome": "Voz do Windows (SAPI)", "remoto": False, "precisa": [], "vozes": []},
    "piper": {"nome": "Piper", "remoto": False, "precisa": ["exe", "modelo"], "vozes": []},
    "edge": {"nome": "Microsoft Edge TTS", "remoto": True, "precisa": [],
             "vozes": ["pt-BR-AntonioNeural", "pt-BR-FranciscaNeural", "pt-BR-ThalitaMultilingualNeural"]},
    "azure": {"nome": "Azure Speech", "remoto": True, "precisa": ["chave", "regiao"],
              "vozes": ["pt-BR-AntonioNeural", "pt-BR-FranciscaNeural", "pt-BR-DonatoNeural", "pt-BR-JulioNeural"]},
    "google": {"nome": "Google Cloud TTS", "remoto": True, "precisa": ["chave"],
               "vozes": ["pt-BR-Neural2-B", "pt-BR-Wavenet-B", "pt-BR-Standard-B", "pt-BR-Neural2-A"]},
    "elevenlabs": {"nome": "ElevenLabs", "remoto": True, "precisa": ["chave", "voz"], "vozes": []},
    "fish": {"nome": "fish.audio", "remoto": True, "precisa": ["chave"],
             "vozes": ["a5b93aeddcc948c19ea04f0afe9d178c"],          # Jarvis (UCM) - Portugues Brasileiro
             "modelos": ["s2.1-pro-free", "s2.1-pro", "s2-pro", "s1"]},
}
TIMEOUT_REMOTO_S = 25


class ErroVoz(RuntimeError):
    """Mensagem segura para mostrar (sem chave)."""


def de_wav(dados: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(dados)) as w:
        taxa, canais, largura = w.getframerate(), w.getnchannels(), w.getsampwidth()
        bruto = w.readframes(w.getnframes())
    if largura != 2:
        raise ErroVoz(f"WAV com {8 * largura} bits não suportado")
    audio = np.frombuffer(bruto, dtype=np.int16).astype(np.float32) / 32768.0
    if canais > 1:
        audio = audio.reshape(-1, canais).mean(axis=1)
    return audio, taxa


def de_pcm16(dados: bytes, taxa: int) -> tuple[np.ndarray, int]:
    return np.frombuffer(dados, dtype=np.int16).astype(np.float32) / 32768.0, taxa


def de_mp3(dados: bytes) -> tuple[np.ndarray, int]:
    """MP3 -> PCM mono 24 kHz com o PyAV (dependencia do faster-whisper, ja instalada)."""
    import av
    with av.open(io.BytesIO(dados)) as cont:
        fluxo = cont.streams.audio[0]
        reamostra = av.AudioResampler(format="s16", layout="mono", rate=24000)
        partes = []
        for quadro in cont.decode(fluxo):
            for q in reamostra.resample(quadro):
                partes.append(q.to_ndarray().reshape(-1))
        for q in reamostra.resample(None):
            partes.append(q.to_ndarray().reshape(-1))
    audio = np.concatenate(partes).astype(np.float32) / 32768.0 if partes else np.zeros(1, np.float32)
    return audio, 24000


def _post(url: str, corpo: bytes, cabecalhos: dict[str, str], nome: str) -> bytes:
    req = urllib.request.Request(url, data=corpo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_REMOTO_S) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        detalhe = ""
        try:
            detalhe = e.read(300).decode("utf-8", "replace")
        except OSError:
            pass
        motivo = {401: "chave inválida ou ausente", 402: "sem créditos na conta", 403: "sem permissão para essa voz",
                  429: "limite de uso atingido; tente mais tarde", 503: "serviço ocupado agora"}.get(e.code)
        raise ErroVoz(f"{nome}: {motivo} ({e.code})" if motivo else
                      f"{nome} respondeu {e.code} {detalhe[:120]}".strip()) from None
    except (urllib.error.URLError, OSError) as e:
        raise ErroVoz(f"{nome} fora de alcance ({type(e).__name__})") from None


class Vozes:
    """Gera (audio float32, taxa) com o provedor escolhido; cai para o Kokoro."""

    def __init__(self, kokoro: Any, prefs: Any, registrar: Callable[[str, str], None] | None = None) -> None:
        self._kokoro = kokoro                # hud_runtime.audio.Sintese
        self._prefs = prefs
        self._registrar = registrar or (lambda t, n: None)
        self._trava = threading.Lock()
        self.ultimo: dict[str, Any] = {}

    # ---- configuracao ------------------------------------------------------
    @staticmethod
    def credenciais(provedor: str) -> dict[str, str]:
        c = ler_segredo(f"tts_{provedor}")
        return c if isinstance(c, dict) else {}

    @staticmethod
    def definir_credenciais(provedor: str, dados: dict[str, Any]) -> None:
        if provedor not in PROVEDORES or not PROVEDORES[provedor]["remoto"] and provedor != "piper":
            raise ValueError("provedor sem credenciais")
        permitidos = {"chave", "regiao", "voz", "modelo", "exe"}
        limpos = {k: str(v).strip()[:300] for k, v in dados.items() if k in permitidos and str(v).strip()}
        atuais = Vozes.credenciais(provedor)
        gravar_segredo(f"tts_{provedor}", {**atuais, **limpos} or None)

    @staticmethod
    def remover_credenciais(provedor: str) -> None:
        gravar_segredo(f"tts_{provedor}", None)

    def catalogo(self) -> list[dict[str, Any]]:
        """O que as telas podem saber: provedores, vozes, se estao prontos (sem chaves)."""
        saida = []
        for chave, info in PROVEDORES.items():
            cred = self.credenciais(chave)
            falta = [p for p in info["precisa"] if not cred.get(p)]
            if chave == "sapi":
                vozes, pronto = sapi_vozes(), bool(sapi_vozes())
            elif chave == "edge":
                vozes, pronto = info["vozes"], _tem("edge_tts")
                if not pronto:
                    falta = ["pacote edge-tts"]
            elif chave == "piper":
                vozes = [Path(cred["modelo"]).stem] if cred.get("modelo") else []
                pronto = (not falta and Path(cred["exe"]).is_file() and Path(cred["modelo"]).is_file())
            else:
                vozes, pronto = info["vozes"], not falta
            saida.append({"id": chave, "nome": info["nome"], "remoto": info["remoto"], "pronto": pronto,
                          "falta": falta, "vozes": vozes, "modelos": info.get("modelos", []),
                          "configurado": {k: bool(cred.get(k)) for k in ("chave", "regiao", "voz", "modelo", "exe")}})
        return saida

    # ---- sintese --------------------------------------------------------------
    def gerar(self, texto: str, provedor: str | None = None, voz: str | None = None) -> tuple[np.ndarray, int]:
        p = self._prefs.ler()
        provedor = provedor or p.get("voz_provedor") or "kokoro"
        voz = voz or (p.get("voz_tts") if provedor == "kokoro" else p.get("voz_remota")) or None
        t0 = time.time()
        from .audio import pronuncia
        texto = pronuncia(texto)                     # "Jarvis" com o "Ja" tonico em todos os motores
        try:
            audio, taxa = self._gerar(provedor, texto, voz, p)
            self.ultimo = {"provedor": provedor, "voz": voz, "remoto": PROVEDORES.get(provedor, {}).get("remoto"),
                           "s": round(time.time() - t0, 2), "erro": None, "em": time.time()}
            return audio, taxa
        except Exception as e:  # noqa: BLE001 - cai para o local e diz o porque
            self.ultimo = {"provedor": provedor, "voz": voz, "erro": str(e)[:160], "em": time.time()}
            if provedor == "kokoro":
                raise
            self._registrar(f"voz {provedor} falhou ({str(e)[:100]}); usando Kokoro local", "aviso")
            return self._gerar("kokoro", texto, p.get("voz_tts") or "pm_alex", p)

    def _gerar(self, provedor: str, texto: str, voz: str | None, p: dict) -> tuple[np.ndarray, int]:
        if provedor == "kokoro":
            from .audio import Sintese
            return self._kokoro.gerar(texto, voz=voz or "pm_alex"), Sintese.TAXA
        if provedor == "sapi":
            return sapi_falar(texto, voz)
        if provedor == "piper":
            return piper_falar(texto, self.credenciais("piper"))
        if provedor == "edge":
            return edge_falar(texto, voz or "pt-BR-AntonioNeural")
        cred = self.credenciais(provedor)
        if provedor == "azure":
            return azure_falar(texto, voz or "pt-BR-AntonioNeural", cred)
        if provedor == "google":
            return google_falar(texto, voz or "pt-BR-Neural2-B", cred)
        if provedor == "elevenlabs":
            return elevenlabs_falar(texto, cred)
        if provedor == "fish":
            return fish_falar(texto, voz or PROVEDORES["fish"]["vozes"][0], cred)
        raise ErroVoz(f"provedor desconhecido: {provedor}")


def _tem(modulo: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(modulo) is not None


# ---- locais --------------------------------------------------------------------
_SAPI_CACHE: list[str] | None = None


def sapi_vozes() -> list[str]:
    global _SAPI_CACHE
    if _SAPI_CACHE is None:
        try:
            import comtypes
            import comtypes.client as cc
            comtypes.CoInitialize()
            vs = cc.CreateObject("SAPI.SpVoice").GetVoices()
            _SAPI_CACHE = [vs.Item(i).GetDescription() for i in range(vs.Count)]
        except Exception:  # noqa: BLE001
            _SAPI_CACHE = []
    return _SAPI_CACHE


def sapi_falar(texto: str, voz: str | None) -> tuple[np.ndarray, int]:
    import comtypes
    import comtypes.client as cc
    comtypes.CoInitialize()
    sp = cc.CreateObject("SAPI.SpVoice")
    vs = sp.GetVoices()
    alvo = voz or next((d for d in sapi_vozes() if "Portuguese" in d or "Brazil" in d), None)
    for i in range(vs.Count):
        if alvo and vs.Item(i).GetDescription() == alvo:
            sp.Voice = vs.Item(i)
    mem = cc.CreateObject("SAPI.SpMemoryStream")
    fmt = cc.CreateObject("SAPI.SpAudioFormat")
    fmt.Type = 22                                  # SAFT22kHz16BitMono
    mem.Format = fmt
    sp.AudioOutputStream = mem
    sp.Speak(texto)
    return de_pcm16(bytes(mem.GetData()), 22050)


def piper_falar(texto: str, cred: dict) -> tuple[np.ndarray, int]:
    import subprocess
    import tempfile
    exe, modelo = cred.get("exe", ""), cred.get("modelo", "")
    # Path("") e a pasta atual (existe!): exige arquivos de verdade
    if not (exe and modelo and Path(exe).is_file() and Path(modelo).is_file()):
        raise ErroVoz("Piper não instalado (configure piper.exe e o modelo .onnx)")
    with tempfile.TemporaryDirectory() as d:
        saida = Path(d) / "fala.wav"
        r = subprocess.run([exe, "--model", modelo, "--output_file", str(saida)], input=texto.encode("utf-8"),
                           capture_output=True, timeout=60, creationflags=0x08000000)
        if r.returncode != 0 or not saida.exists():
            raise ErroVoz(f"Piper falhou ({r.returncode})")
        return de_wav(saida.read_bytes())


# ---- remotos ---------------------------------------------------------------------
def edge_falar(texto: str, voz: str) -> tuple[np.ndarray, int]:
    import asyncio

    import edge_tts

    async def juntar() -> bytes:
        partes = []
        async for pedaco in edge_tts.Communicate(texto, voz).stream():
            if pedaco.get("type") == "audio":
                partes.append(pedaco["data"])
        return b"".join(partes)

    try:
        dados = asyncio.run(asyncio.wait_for(juntar(), TIMEOUT_REMOTO_S))
    except Exception as e:  # noqa: BLE001
        raise ErroVoz(f"Edge TTS falhou ({type(e).__name__})") from None
    if not dados:
        raise ErroVoz("Edge TTS não devolveu áudio")
    return de_mp3(dados)


def azure_falar(texto: str, voz: str, cred: dict) -> tuple[np.ndarray, int]:
    from xml.sax.saxutils import escape
    if not (cred.get("chave") and cred.get("regiao")):
        raise ErroVoz("Azure sem chave/região")
    ssml = (f"<speak version='1.0' xml:lang='pt-BR'><voice name='{escape(voz)}'>{escape(texto)}</voice></speak>")
    dados = _post(f"https://{cred['regiao']}.tts.speech.microsoft.com/cognitiveservices/v1", ssml.encode("utf-8"),
                  {"Ocp-Apim-Subscription-Key": cred["chave"], "Content-Type": "application/ssml+xml",
                   "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm", "User-Agent": "JarvisHUD"}, "Azure")
    return de_wav(dados)


def google_falar(texto: str, voz: str, cred: dict) -> tuple[np.ndarray, int]:
    import base64
    if not cred.get("chave"):
        raise ErroVoz("Google TTS sem chave")
    corpo = json.dumps({"input": {"text": texto}, "voice": {"languageCode": "pt-BR", "name": voz},
                        "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}}).encode()
    # chave no cabecalho, nunca na URL (URLs vao para logs e historicos)
    r = json.loads(_post("https://texttospeech.googleapis.com/v1/text:synthesize", corpo,
                         {"Content-Type": "application/json", "X-Goog-Api-Key": cred["chave"]}, "Google TTS"))
    return de_wav(base64.b64decode(r["audioContent"]))


def elevenlabs_falar(texto: str, cred: dict) -> tuple[np.ndarray, int]:
    if not (cred.get("chave") and cred.get("voz")):
        raise ErroVoz("ElevenLabs sem chave/voice_id")
    corpo = json.dumps({"text": texto, "model_id": cred.get("modelo") or "eleven_multilingual_v2"}).encode()
    dados = _post(f"https://api.elevenlabs.io/v1/text-to-speech/{cred['voz']}?output_format=pcm_24000", corpo,
                  {"xi-api-key": cred["chave"], "Content-Type": "application/json"}, "ElevenLabs")
    return de_pcm16(dados, 24000)


def fish_falar(texto: str, referencia: str, cred: dict) -> tuple[np.ndarray, int]:
    if not cred.get("chave"):
        raise ErroVoz("fish.audio sem chave")
    corpo = json.dumps({"text": texto, "reference_id": referencia, "format": "wav", "sample_rate": 24000,
                        "latency": "balanced", "normalize": True}).encode()
    dados = _post("https://api.fish.audio/v1/tts", corpo,
                  {"Authorization": f"Bearer {cred['chave']}", "Content-Type": "application/json",
                   "model": cred.get("modelo") or "s2.1-pro-free"}, "fish.audio")
    return de_wav(dados)
