"""S7: mão por MediaPipe local, seleção e manipulação reversível no mesmo HUD.

Sem captura própria: recebe quadros da câmera compartilhada. Desligado no boot,
calibração por sessão, uma mão por vez, pinça com histerese e nenhuma ação externa.
O controlador perde a autorização operacional quando a tela deixa de enviar
heartbeat ou a câmera para; resultados atrasados são descartados por geração.
"""
from __future__ import annotations

import math
import sys
import threading
import time
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / "modelos" / "hand_landmarker.task"


class Gestos:
    def __init__(self, selecao, publicar, camera_ativa=lambda: False, relogio=time.monotonic):
        self.selecao, self.publicar, self.camera_ativa = selecao, publicar, camera_ativa
        self.relogio = relogio
        self._trava = threading.RLock()
        self._evento = threading.Event()
        self._fim = threading.Event()
        self._thread = None
        self._geracao = 0
        self._imagem = None
        self._detector = None
        self._mp = None
        self._tick = 0
        self._seq = 0
        self.ativo = False
        self.cliente = None
        self.modo = "girar"
        self.calibracao = []
        self.alvos = []
        self.ultimo = None
        self._ultima_mao = -1e10
        self._heartbeat = -1e10
        self._pinch = False
        self._anterior = None
        self._acao = None
        self._alvo_gesto = None
        self.fase = "desativado"
        self.selecao.gesto_disponivel = lambda: self.ativo and len(self.calibracao) == 2

    def _publicar(self, ponteiro=None, detalhe=""):
        self.publicar({"ativo": self.ativo, "fase": self.fase, "calibrado": len(self.calibracao) == 2,
                       "pontos_calibrados": len(self.calibracao), "ponteiro": ponteiro,
                       "acao": self._acao, "cliente": self.cliente, "modo": self.modo,
                       "detalhe": detalhe, "em": time.time(), "tipo": "gesto no ar"})

    def validar_ativacao(self, cliente: str):
        if not cliente or len(cliente) > 100:
            raise ValueError("identificador de tela inválido")
        with self._trava:
            if self.ativo and self.cliente != cliente:
                raise ValueError("os gestos já estão em uso por outra tela")

    def ativar(self, cliente: str):
        with self._trava:
            self.validar_ativacao(cliente)
            if self.ativo:
                return  # retry da mesma tela não apaga a calibração
            self.ativo, self.cliente = True, cliente
            self._geracao += 1
            self._heartbeat = self.relogio()
            self.calibracao, self.alvos = [], []
            self.modo = "girar"
            self.ultimo, self._imagem = None, None
            self._alvo_gesto = None
            self._pinch, self._anterior, self._acao = False, None, None
            self.fase = "carregando"
            self._publicar(detalhe="Mostre apenas uma mão e calibre os dois cantos.")
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._rodar, name="gestos-s7", daemon=True)
                self._thread.start()
            self._evento.set()

    def desativar(self, motivo="desativado"):
        with self._trava:
            self.ativo = False
            self._geracao += 1
            self._imagem = self.ultimo = self._acao = None
            self._alvo_gesto = None
            self._pinch, self._anterior = False, None
            self.calibracao, self.alvos = [], []
            self.fase = "desativado"
            self._publicar(detalhe=motivo)
            self._evento.set()

    def comando(self, dados):
        cliente, acao = str(dados.get("cliente") or ""), dados.get("acao")
        if acao == "ativar":
            self.ativar(cliente)
            return {"ok": True}
        with self._trava:
            if cliente != self.cliente:
                raise ValueError("esta tela não controla a sessão de gestos")
            if acao == "desativar":
                self.desativar("desativado pelo usuário")
            elif not self._verificar_sessao():
                raise ValueError("ative os gestos nesta tela primeiro")
            elif acao == "heartbeat":
                self._heartbeat = self.relogio()
            elif acao == "calibrar":
                if self.ultimo is None or self.relogio() - self._ultima_mao > 0.7:
                    raise ValueError("mostre apenas uma mão, com o indicador visível, para calibrar")
                if len(self.calibracao) >= 2:
                    self.calibracao = []
                ponto = tuple(self.ultimo)
                if self.calibracao and (abs(ponto[0] - self.calibracao[0][0]) < 0.15
                                         or abs(ponto[1] - self.calibracao[0][1]) < 0.15):
                    raise ValueError("os cantos estão próximos; mova o indicador para o canto oposto")
                self.calibracao.append(ponto)
                self._pinch, self._anterior = False, None
                self._publicar(detalhe="Calibração concluída." if len(self.calibracao) == 2 else "Agora aponte para o canto inferior direito.")
            elif acao == "modo":
                if dados.get("modo") not in ("girar", "zoom"):
                    raise ValueError("modo deve ser girar ou zoom")
                self.modo = dados["modo"]
                self._anterior = None
                self._publicar()
            elif acao == "alvos":
                alvos = dados.get("alvos")
                if not isinstance(alvos, list) or len(alvos) > 40:
                    raise ValueError("lista de alvos inválida")
                validos = []
                for a in alvos:
                    if not isinstance(a, dict) or a.get("tipo") not in ("peca", "componente", "objeto", "regiao"):
                        raise ValueError("tipo de alvo não permitido por gesto")
                    caixa = a.get("caixa")
                    if not isinstance(caixa, list) or len(caixa) != 4 or not all(
                            isinstance(v, (float, int)) and not isinstance(v, bool)
                            and math.isfinite(v) and 0 <= v <= 1 for v in caixa):
                        raise ValueError("região do alvo inválida")
                    if caixa[2] <= 0 or caixa[3] <= 0 or caixa[0] + caixa[2] > 1.001 or caixa[1] + caixa[3] > 1.001:
                        raise ValueError("região do alvo fora da tela")
                    if not a.get("id") or len(str(a["id"])) > 160:
                        raise ValueError("identificador de alvo inválido")
                    validos.append({"tipo": a["tipo"], "id": str(a["id"]),
                                    "rotulo": str(a.get("rotulo") or a["id"])[:160], "caixa": caixa})
                self.alvos = validos
            else:
                raise ValueError("ação de gestos desconhecida")
        return {"ok": True}

    def _verificar_sessao(self):
        if not self.ativo:
            return False
        if self.relogio() - self._heartbeat > 12 or not self.camera_ativa():
            self.desativar("tela desconectada ou câmera desligada; calibre novamente ao retomar")
            return False
        return True

    def oferecer(self, imagem):
        if not self.ativo:
            return
        with self._trava:
            if self.ativo:
                self._imagem = (imagem, self._geracao, self.relogio())
                self._evento.set()

    def _carregar(self):
        if self._detector is not None:
            return
        pasta = str(RAIZ / "_gestos_libs")
        if pasta not in sys.path:
            sys.path.append(pasta)
        import mediapipe as mp
        if not MODELO.is_file():
            raise RuntimeError("modelo local de mãos ausente")
        opcoes = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(MODELO)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
            min_hand_detection_confidence=0.65, min_hand_presence_confidence=0.65,
            min_tracking_confidence=0.65)
        self._detector = mp.tasks.vision.HandLandmarker.create_from_options(opcoes)
        self._mp = mp

    def _rodar(self):
        try:
            while not self._fim.is_set():
                self._evento.wait(0.25)
                self._evento.clear()
                with self._trava:
                    if not self._verificar_sessao():
                        continue
                    imagem, self._imagem = self._imagem, None
                if imagem is None:
                    continue
                quadro, geracao, capturado = imagem
                self._carregar()
                import cv2
                h, w = quadro.shape[:2]
                if w > 640:
                    quadro = cv2.resize(quadro, (640, max(1, round(h * 640 / w))))
                rgb = cv2.cvtColor(quadro, cv2.COLOR_BGR2RGB)
                self._tick = max(self._tick + 1, int(self.relogio() * 1000))
                resultado = self._detector.detect_for_video(
                    self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb), self._tick)
                with self._trava:
                    if self.ativo and geracao == self._geracao and self.relogio() - capturado < 0.8:
                        self.processar_pontos(resultado.hand_landmarks)
                self._fim.wait(0.07)
        except Exception as exc:
            self.desativar(f"falha no rastreador: {type(exc).__name__}: {str(exc)[:140]}")
        finally:
            if self._detector is not None:
                self._detector.close()
                self._detector = None

    def processar_pontos(self, maos):
        """Contrato testável com landmarks; em produção só chamado pelo modelo local."""
        if not self._verificar_sessao():
            return
        agora = self.relogio()
        if len(maos) != 1 or len(maos[0]) != 21:
            self.ultimo = None
            self._pinch, self._anterior = False, None
            self.fase = "sem_mao" if not maos else "ambiguo"
            self._publicar(detalhe="Mostre apenas uma mão; nenhuma ação executada.")
            return
        p = maos[0]
        if not all(math.isfinite(v) for ponto in p for v in (ponto.x, ponto.y)):
            self.ultimo = None
            self._pinch, self._anterior = False, None
            self.fase = "sem_mao"
            self._publicar(detalhe="Landmarks inválidos; nenhuma ação executada.")
            return
        if agora - self._ultima_mao > 0.6:
            self._pinch, self._anterior = False, None
        self.ultimo, self._ultima_mao = (p[8].x, p[8].y), agora
        self.fase = "calibrando" if len(self.calibracao) != 2 else "rastreando"
        if len(self.calibracao) != 2:
            self._publicar()
            return
        a, b = self.calibracao
        x, y = (p[8].x - a[0]) / (b[0] - a[0]), (p[8].y - a[1]) / (b[1] - a[1])
        if not (0 <= x <= 1 and 0 <= y <= 1):
            self._pinch, self._anterior = False, None
            self._publicar(detalhe="Mão fora da região calibrada.")
            return
        palma = math.hypot(p[0].x - p[9].x, p[0].y - p[9].y)
        if palma < 0.035:
            self._pinch, self._anterior = False, None
            self._publicar(detalhe="Aproxime a mão para rastrear com segurança.")
            return
        razao = math.hypot(p[4].x - p[8].x, p[4].y - p[8].y) / palma
        fechada = razao < (0.55 if self._pinch else 0.30)
        acao = None
        if fechada and not self._pinch:
            self._alvo_gesto = None
            alvos = [a for a in self.alvos if a["caixa"][0] <= x <= a["caixa"][0] + a["caixa"][2]
                     and a["caixa"][1] <= y <= a["caixa"][1] + a["caixa"][3]]
            if len(alvos) == 1:
                alvo = alvos[0]
                self.selecao.selecionar(alvo["tipo"], alvo["id"], alvo["rotulo"], por="gesto")
                self._alvo_gesto = alvo["id"]
                acao = {"tipo": "selecionar", "id": alvo["id"]}
        elif fechada and self._pinch and self._anterior is not None:
            alvo = self.selecao.atual()
            if alvo and alvo.id == self._alvo_gesto and any(a["id"] == alvo.id for a in self.alvos):
                dx, dy = x - self._anterior[0], y - self._anterior[1]
                if abs(dx) <= 0.15 and abs(dy) <= 0.15:
                    acao = {"tipo": self.modo, "id": alvo.id, "dx": dx, "dy": dy}
        self._pinch, self._anterior = fechada, (x, y) if fechada else None
        if not fechada:
            self._alvo_gesto = None
        if acao:
            self._seq += 1
            self._acao = dict(acao, seq=self._seq)
        self._publicar({"x": x, "y": y, "pinca": fechada})

    def encerrar(self):
        self.desativar("runtime encerrado")
        self._fim.set()
        self._evento.set()
