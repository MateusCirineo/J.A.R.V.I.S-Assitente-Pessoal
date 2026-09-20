"""Camera: presenca e deteccao de rosto, localmente.

- Desligada por padrao. Liga e desliga pela tela; ao desligar o dispositivo e
  liberado (a luz da webcam apaga).
- Nenhum quadro e gravado em disco nem enviado para fora. O ultimo quadro fica
  so na memoria, para o preview da propria tela (MJPEG com token).
- Deteccao: YuNet (OpenCV, rede de ~230 KB). Sem o modelo, cai no Haar cascade
  que vem com o OpenCV.
- Nao identifica QUEM e a pessoa: so detecta que ha um rosto e onde.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from .estado import Estado

MODELO = Path(__file__).resolve().parent.parent / "modelos" / "face_detection_yunet_2023mar.onnx"
LARG, ALT = 1280, 720          # HD; se a webcam nao tiver, fica com o que ela der
DET_LARG = 320                 # a deteccao roda numa copia pequena (altura proporcional)
FPS_ALVO = 15
PRESENCA_S = 1.5


class Camera(threading.Thread):
    def __init__(self, estado: Estado, indice: int = 0, ao_presenca=None, ao_quadro=None, ao_imagem=None) -> None:
        super().__init__(name="camera", daemon=True)
        self._estado = estado
        # ganchos do runtime: presenca mudou (boas-vindas) e rostos por quadro
        self._ao_presenca = ao_presenca or (lambda presente: None)
        self._ao_quadro = ao_quadro or (lambda n: None)
        self._ao_imagem = ao_imagem              # olhar automatico: (quadro BGR, rostos) por quadro
        self._indice = indice
        self._ativa = threading.Event()
        self._encerrar = threading.Event()
        self._quadro = threading.Condition()
        self.jpeg: bytes | None = None
        self.seq = 0

    @property
    def ativa(self) -> bool:
        return self._ativa.is_set()

    def ativar(self) -> None:
        self._ativa.set()

    def desativar(self) -> None:
        self._ativa.clear()

    def encerrar(self) -> None:
        self._encerrar.set()
        self._ativa.set()

    def proximo_jpeg(self, visto: int, tempo: float = 2.0) -> tuple[int, bytes | None]:
        with self._quadro:
            self._quadro.wait_for(lambda: self.seq != visto or not self.ativa, timeout=tempo)
            return self.seq, self.jpeg

    # ------------------------------------------------------------------

    def run(self) -> None:
        while not self._encerrar.is_set():
            self._ativa.wait()
            if self._encerrar.is_set():
                break
            try:
                self._sessao()
            except Exception as e:  # noqa: BLE001
                self._estado.atualizar("camera", ativa=False, presente=False, detalhe=str(e)[:140])
                self._estado.registrar("camera", f"falha: {e}", "erro")
                self._ativa.clear()
            with self._quadro:
                self.jpeg = None
                self.seq += 1
                self._quadro.notify_all()

    @staticmethod
    def _avisar(gancho, valor) -> None:
        try:
            gancho(valor)
        except Exception:  # noqa: BLE001 - um gancho com erro nao para a camera
            pass

    def _detector(self, cv2, det_alt: int):
        if MODELO.exists():
            return "yunet", cv2.FaceDetectorYN.create(str(MODELO), "", (DET_LARG, det_alt), 0.7)
        return "haar", cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def _sessao(self) -> None:
        import cv2

        cap = cv2.VideoCapture(self._indice, cv2.CAP_DSHOW)
        # MJPG: em YUY2 a maioria das webcams so entrega 720p a 5-10 quadros/s
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, LARG)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALT)
        if not cap.isOpened():
            raise RuntimeError("webcam indisponível (em uso por outro app?)")
        larg = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or LARG
        alt = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or ALT
        det_alt = max(90, round(DET_LARG * alt / larg))
        tipo, det = self._detector(cv2, det_alt)
        self._estado.atualizar("camera", ativa=True, presente=False, detalhe=None,
                               detector=tipo, desde=None, resolucao=f"{larg}x{alt}")
        self._estado.registrar("camera", f"ligada em {larg}x{alt} (detector {tipo})")
        ultimo_rosto = 0.0
        presente = False
        quadros, t_fps = 0, time.monotonic()
        try:
            while self._ativa.is_set() and not self._encerrar.is_set():
                t0 = time.monotonic()
                ok, img = cap.read()
                if not ok:
                    raise RuntimeError("a webcam parou de enviar imagem")
                h, w = img.shape[:2]
                peq = cv2.resize(img, (DET_LARG, det_alt), interpolation=cv2.INTER_AREA)
                rostos = []
                if tipo == "yunet":
                    _, achados = det.detect(peq)
                    for f in achados if achados is not None else []:
                        x, y, fw, fh = (float(v) for v in f[:4])
                        # 5 pontos do YuNet: olho direito, olho esquerdo, ponta do
                        # nariz, canto direito e canto esquerdo da boca (da pessoa)
                        pontos = [[round(float(f[4 + 2 * i]) / DET_LARG, 4),
                                   round(float(f[5 + 2 * i]) / det_alt, 4)] for i in range(5)]
                        rostos.append({"x": x / DET_LARG, "y": y / det_alt, "w": fw / DET_LARG,
                                       "h": fh / det_alt, "confianca": round(float(f[-1]), 2),
                                       "pontos": pontos})
                else:
                    cinza = cv2.cvtColor(peq, cv2.COLOR_BGR2GRAY)
                    for (x, y, fw, fh) in det.detectMultiScale(cinza, 1.15, 5, minSize=(40, 40)):
                        rostos.append({"x": x / DET_LARG, "y": y / det_alt, "w": fw / DET_LARG,
                                       "h": fh / det_alt, "confianca": None})
                agora = time.monotonic()
                if rostos:
                    ultimo_rosto = agora
                agora_presente = agora - ultimo_rosto < PRESENCA_S
                if agora_presente != presente:
                    presente = agora_presente
                    self._estado.atualizar("camera", presente=presente,
                                           desde=time.time() if presente else None)
                    self._estado.registrar("camera", "presença detectada" if presente else "ninguém à frente")
                    self._avisar(self._ao_presenca, presente)
                self._avisar(self._ao_quadro, len(rostos))
                if self._ao_imagem:
                    try:
                        self._ao_imagem(img, rostos)
                    except Exception:  # noqa: BLE001 - o olhar nunca derruba a camera
                        pass
                # posicoes dos rostos: evento leve, fora do estado versionado
                self._estado.publicar("rostos", {"rostos": rostos, "largura": w, "altura": h})

                ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if ok:
                    with self._quadro:
                        self.jpeg = buf.tobytes()
                        self.seq += 1
                        self._quadro.notify_all()

                quadros += 1
                if agora - t_fps >= 2.0:
                    self._estado.atualizar("camera", fps=round(quadros / (agora - t_fps), 1))
                    quadros, t_fps = 0, agora
                time.sleep(max(0.0, 1.0 / FPS_ALVO - (time.monotonic() - t0)))
        finally:
            cap.release()
            self._estado.atualizar("camera", ativa=False, presente=False, fps=None, desde=None)
            self._estado.publicar("rostos", {"rostos": [], "largura": larg, "altura": alt})
            self._estado.registrar("camera", "desligada")


def estado_inicial() -> dict[str, Any]:
    return {"ativa": False, "presente": False, "desde": None, "fps": None,
            "detector": None, "detalhe": None, "resolucao": None}
