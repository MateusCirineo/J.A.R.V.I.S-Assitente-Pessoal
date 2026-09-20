"""Reconhecer QUEM e (rosto e voz), como o Jarvis reconhece o Tony -- autorizado pelo
Senhor em 19/09/2026, com estas regras:

- So reconhece quem foi CADASTRADO por comando ("memorize meu rosto", "memorize o
  rosto da Maria", "memorize minha voz"), com a pessoa presente e de acordo.
  Qualquer outra pessoa e "desconhecido": nada de adivinhar pela aparencia, nada de
  buscar na internet.
- Guarda so numeros (embeddings), nunca fotos nem gravacoes, em
  ~/.openjarvis/hud-identidades.json. "Esqueca o rosto/a voz de X" apaga.
- Nada sai do computador.

Modelos locais:
- Rosto: YuNet (deteccao, ja instalado) + SFace (OpenCV Zoo, Apache-2.0, 38,7 MB);
  semelhanca de cosseno >= 0,363 = mesma pessoa (limiar do exemplo oficial do OpenCV).
- Voz: WeSpeaker ResNet34-LM (VoxCeleb, CC BY 4.0, 26,5 MB) com fbank Kaldi
  (80 bandas, 25/10 ms, janela de Hamming, media subtraida) calculado aqui em numpy.
"""

from __future__ import annotations

import io
import json
import math
import os
import threading
import time
import wave
from pathlib import Path
from typing import Any

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
MODELOS = Path(__file__).resolve().parent.parent / "modelos"
ARQ = HOME / "hud-identidades.json"
DONO = "dono"                              # o Senhor (o nome falado vem de "Como o Jarvis te chama")
LIMIAR_ROSTO = 0.363
LIMIAR_VOZ = 0.5


def _norm_vetor(v):
    import numpy as np
    v = np.asarray(v, np.float32).ravel()
    if not v.size or not np.isfinite(v).all():
        raise ValueError("amostra biométrica vazia ou inválida")
    n = float(np.linalg.norm(v))
    if not math.isfinite(n) or n <= 0:
        raise ValueError("amostra biométrica sem sinal")
    return v / n


def similaridade(a, b) -> float:
    import numpy as np
    return float(np.dot(_norm_vetor(a), _norm_vetor(b)))


class Cadastro:
    """Embeddings cadastrados: {"rostos": {nome: [...]}, "vozes": {nome: [...]}} (so numeros)."""

    def __init__(self, arquivo: Path = ARQ) -> None:
        self._arquivo = arquivo
        self._trava = threading.Lock()

    def ler(self) -> dict[str, dict[str, list[float]]]:
        try:
            d = json.loads(self._arquivo.read_text(encoding="utf-8"))
            return {"rostos": dict(d.get("rostos") or {}), "vozes": dict(d.get("vozes") or {})}
        except (OSError, ValueError, AttributeError):
            return {"rostos": {}, "vozes": {}}

    def _gravar(self, d: dict[str, Any]) -> None:
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(d), encoding="utf-8")
        os.replace(tmp, self._arquivo)

    def salvar(self, tipo: str, nome: str, vetor) -> None:
        with self._trava:
            d = self.ler()
            d[tipo][nome] = [round(float(x), 6) for x in _norm_vetor(vetor)]
            self._gravar(d)

    def esquecer(self, tipo: str | None, nome: str | None) -> list[str]:
        """Apaga um nome (ou todos com nome=None) de rostos, vozes ou dos dois. Devolve o que saiu."""
        with self._trava:
            d = self.ler()
            saiu = []
            for t in ([tipo] if tipo else ["rostos", "vozes"]):
                for n in list(d[t]):
                    if nome is None or n == nome:
                        del d[t][n]
                        saiu.append(f"{t}:{n}")
            self._gravar(d)
        return saiu

    def comparar(self, tipo: str, vetor, limiar: float) -> tuple[str | None, float]:
        import numpy as np
        v = _norm_vetor(vetor)
        melhor, nota, segunda = None, -1.0, -1.0
        for nome, ref in self.ler()[tipo].items():
            try:
                r = _norm_vetor(ref)
                if r.shape != v.shape:
                    continue
                s = float(np.dot(v, r))
            except (TypeError, ValueError):
                continue
            if s > nota:
                segunda = nota
                melhor, nota = nome, s
            elif s > segunda:
                segunda = s
        # Empates/mesmo vetor associado a dois nomes nao identificam uma pessoa.
        return (melhor if nota >= limiar and nota - segunda > 1e-6 else None), nota


# ---- rosto --------------------------------------------------------------------------------
class Rostos:
    def __init__(self, cadastro: Cadastro, largura: int = 640) -> None:
        self.cadastro = cadastro
        self._largura = largura
        self._trava = threading.Lock()
        self._det = self._rec = None
        self._det_tam = None

    @property
    def disponivel(self) -> bool:
        return (MODELOS / "face_recognition_sface_2021dec.onnx").is_file() and \
            (MODELOS / "face_detection_yunet_2023mar.onnx").is_file()

    def _carregar(self) -> None:
        import cv2
        self._rec = cv2.FaceRecognizerSF_create(str(MODELOS / "face_recognition_sface_2021dec.onnx"), "")
        self._det = cv2.FaceDetectorYN_create(str(MODELOS / "face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.85, 0.3, 50)

    def rostos_com_vetor(self, img_bgr) -> list[tuple[Any, Any]]:
        """[(linha do YuNet na imagem reduzida, embedding)] + escala para voltar ao quadro original."""
        import cv2
        with self._trava:
            if self._rec is None:
                self._carregar()
            h, w = img_bgr.shape[:2]
            esc = min(1.0, self._largura / w)
            peq = cv2.resize(img_bgr, (int(w * esc), int(h * esc))) if esc < 1 else img_bgr
            tam = (peq.shape[1], peq.shape[0])
            if tam != self._det_tam:
                self._det.setInputSize(tam)
                self._det_tam = tam
            _, faces = self._det.detect(peq)
            saida = []
            for f in (faces if faces is not None else [])[:4]:
                vetor = self._rec.feature(self._rec.alignCrop(peq, f))
                saida.append((f, vetor))
            return [(f, v, esc, w, h) for f, v in saida]

    def identificar(self, img_bgr) -> list[dict[str, Any]]:
        """[{x, y, w, h (fracoes do quadro), nome (ou None = desconhecido), semelhanca}]"""
        pessoas = []
        for f, vetor, esc, w, h in self.rostos_com_vetor(img_bgr):
            nome, nota = self.cadastro.comparar("rostos", vetor, LIMIAR_ROSTO)
            x, y, fw, fh = (float(v) / esc for v in f[:4])
            pessoas.append({"x": round(x / w, 4), "y": round(y / h, 4), "w": round(fw / w, 4), "h": round(fh / h, 4),
                            "nome": nome, "semelhanca": round(nota, 3)})
        return pessoas

    def vetor_de_um_rosto(self, img_bgr) -> Any | None:
        """Embedding se houver EXATAMENTE um rosto (cadastro sem confundir pessoas)."""
        achados = self.rostos_com_vetor(img_bgr)
        return achados[0][1] if len(achados) == 1 else (len(achados) if achados else 0)


# ---- voz ----------------------------------------------------------------------------------
def pcm_de_wav(wav: bytes):
    import numpy as np
    with wave.open(io.BytesIO(wav)) as w:
        taxa, canais, bytes_amostra = w.getframerate(), w.getnchannels(), w.getsampwidth()
        dados = w.readframes(w.getnframes())
    if bytes_amostra != 2:
        raise ValueError("so WAV de 16 bits")
    x = np.frombuffer(dados, np.int16).astype(np.float32)
    if canais > 1:
        x = x.reshape(-1, canais).mean(axis=1)
    if taxa != 16000:                                     # reamostragem linear simples
        n = int(len(x) * 16000 / taxa)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    return x                                               # escala int16, como o WeSpeaker espera


_BANCOS = None


def _bancos_mel(n_fft: int = 512, n_mel: int = 80, taxa: int = 16000, baixa: float = 20.0):
    """Filtros triangulares na escala mel do Kaldi (1127 ln(1 + f/700))."""
    import numpy as np
    global _BANCOS
    if _BANCOS is not None:
        return _BANCOS
    mel = lambda f: 1127.0 * np.log(1.0 + f / 700.0)       # noqa: E731
    alta = taxa / 2
    mb, ma = mel(baixa), mel(alta)
    delta = (ma - mb) / (n_mel + 1)
    freqs_bins = np.arange(n_fft // 2) * taxa / n_fft
    mel_bins = mel(freqs_bins)
    bancos = np.zeros((n_mel, n_fft // 2 + 1), np.float32)
    for m in range(n_mel):
        esq, centro, dir_ = mb + m * delta, mb + (m + 1) * delta, mb + (m + 2) * delta
        subida = (mel_bins - esq) / (centro - esq)
        descida = (dir_ - mel_bins) / (dir_ - centro)
        bancos[m, :n_fft // 2] = np.maximum(0, np.minimum(subida, descida))
    _BANCOS = bancos
    return bancos


def fbank(x, taxa: int = 16000):
    """Fbank no padrao do Kaldi/torchaudio (dither 0, pre-enfase 0,97, DC removido,
    janela de Hamming, FFT 512, potencia, 80 bandas, log) com media subtraida (CMN)."""
    import numpy as np
    tam, passo = int(taxa * 0.025), int(taxa * 0.010)
    if len(x) < tam:
        return None
    n = 1 + (len(x) - tam) // passo
    idx = np.arange(tam)[None, :] + passo * np.arange(n)[:, None]
    quadros = x[idx].astype(np.float64)
    quadros -= quadros.mean(axis=1, keepdims=True)
    anteriores = np.concatenate([quadros[:, :1], quadros[:, :-1]], axis=1)
    quadros = quadros - 0.97 * anteriores
    quadros *= np.hamming(tam)[None, :]                    # 0,54 - 0,46 cos(2 pi n / (N-1)), igual ao Kaldi
    espectro = np.abs(np.fft.rfft(quadros, n=512)) ** 2
    energia = espectro @ _bancos_mel().T.astype(np.float64)
    feats = np.log(np.maximum(energia, np.finfo(np.float32).eps)).astype(np.float32)
    return feats - feats.mean(axis=0, keepdims=True)


class Falantes:
    def __init__(self, cadastro: Cadastro) -> None:
        self.cadastro = cadastro
        self._sessao = None
        self._trava = threading.Lock()

    @property
    def disponivel(self) -> bool:
        return (MODELOS / "wespeaker_voxceleb_resnet34_LM.onnx").is_file()

    def vetor(self, wav: bytes, minimo_s: float = 1.0) -> Any | None:
        """Embedding de 256 numeros da voz (None = fala curta demais)."""
        import numpy as np
        x = pcm_de_wav(wav)
        if len(x) < minimo_s * 16000:
            return None
        feats = fbank(x)
        if feats is None:
            return None
        with self._trava:
            if self._sessao is None:
                import onnxruntime as ort
                so = ort.SessionOptions()
                so.intra_op_num_threads = 2                     # a CPU tambem atende a voz e o modelo
                self._sessao = ort.InferenceSession(str(MODELOS / "wespeaker_voxceleb_resnet34_LM.onnx"), so,
                                                    providers=["CPUExecutionProvider"])
            return self._sessao.run(None, {"feats": feats[None].astype(np.float32)})[0][0]

    def quem(self, wav: bytes) -> tuple[str | None, float]:
        if not self.cadastro.ler()["vozes"]:
            return None, 0.0
        v = self.vetor(wav)
        if v is None:
            return None, 0.0
        return self.cadastro.comparar("vozes", v, LIMIAR_VOZ)


def media(vetores: list) -> Any:
    import numpy as np
    return _norm_vetor(np.mean([_norm_vetor(v) for v in vetores], axis=0))


def nome_falado(nome: str | None, tratamento: str) -> str:
    return tratamento if nome == DONO else (nome or "desconhecido")


def distancia_angular(a, b) -> float:
    import numpy as np
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(_norm_vetor(a), _norm_vetor(b)))))))


def agora() -> float:
    return time.time()
