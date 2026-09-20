"""Teste de integracao da cadeia de voz, a partir de uma fala limpa.

Por que nao pelo microfone: o array Realtek desta maquina tem cancelamento de
eco -- o que sai dos alto-falantes e subtraido da captacao. Tocar uma fala e
grava-la devolve residuo (RMS ~290 com pico ~32000) e o Whisper nao acha
nada. Entao a cadeia e testada a partir do WAV, como se o microfone tivesse
captado uma fala limpa:

    WAV -> transcricao -> servidor OpenJarvis (/v1/chat/completions) -> sintese

Requer o servidor em 127.0.0.1:8000.  Rodar:
    set HF_HUB_OFFLINE=1
    .venv\\Scripts\\python modo-show\\testes\\integracao_voz.py
"""

from __future__ import annotations

import io
import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime.audio import Sintese, Transcricao  # noqa: E402
from hud_runtime.estado import Estado  # noqa: E402
from hud_runtime.preferencias import Preferencias  # noqa: E402
from hud_runtime.voz import Conversa  # noqa: E402


def wav16k(audio24k: np.ndarray) -> bytes:
    x = np.interp(np.arange(0, len(audio24k), 1.5), np.arange(len(audio24k)), audio24k)
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def main() -> int:
    modelo = sys.argv[1] if len(sys.argv) > 1 else None
    tts, stt = Sintese(), Transcricao()
    t = time.time(); tts.carregar(); stt.carregar()
    print(f"carregados em {time.time() - t:.1f}s")

    pergunta = tts.gerar("Quanto é dois mais dois?")
    texto = stt.transcrever(wav16k(pergunta))
    print(f"transcricao: {texto!r}")
    assert "dois" in texto.lower(), "transcricao nao reconheceu a pergunta"

    estado = Estado()
    prefs = Preferencias()
    if modelo:
        prefs = type("P", (), {"ler": lambda self: {**Preferencias().ler(), "modelo_voz": modelo}})()
    conversa = Conversa(estado, prefs, None, stt, tts, None, ponte_conectada=lambda: False)
    t = time.time()
    resposta = conversa.perguntar(texto)
    print(f"resposta ({time.time() - t:.1f}s, modelo {prefs.ler()['modelo_voz']}): {resposta!r}")
    assert resposta, "servidor nao devolveu resposta"
    print("metrica registrada:", estado.ler("inferencia")["ultima"])

    audio = tts.gerar(resposta)
    print(f"sintese da resposta: {len(audio) / Sintese.TAXA:.1f}s de audio")
    assert len(audio) > Sintese.TAXA * 0.3
    print("OK: transcricao -> servidor -> sintese")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
