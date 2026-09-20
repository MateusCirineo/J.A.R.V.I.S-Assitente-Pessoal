"""Regua virtual: calibracao por folha A4 em perspectiva e medida de objetos."""

import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

import cv2  # noqa: E402

from hud_runtime import comandos as cmd  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402
from hud_runtime.regua import Regua, cm_falado, medida_falada  # noqa: E402

# mesa vista de lado: 60 x 40 cm -> trapezio na imagem 1280 x 720
_H = cv2.getPerspectiveTransform(np.array([[0, 0], [60, 0], [60, 40], [0, 40]], np.float32),
                                 np.array([[380, 180], [1000, 200], [1150, 650], [180, 620]], np.float32))
FUNDO = (60, 45, 35)


def poli(pts_cm):
    return cv2.perspectiveTransform(np.array(pts_cm, np.float32).reshape(-1, 1, 2), _H).reshape(-1, 2).astype(np.int32)


def cena(*objetos):
    img = np.full((720, 1280, 3), FUNDO, np.uint8)
    for pts, cor in objetos:
        cv2.fillPoly(img, [poli(pts)], cor)
    return img


A4 = ([[5, 5], [34.7, 5], [34.7, 26], [5, 26]], (245, 245, 245))
CELULAR = ([[30, 15], [44.6, 17], [43.6, 24.1], [29, 22.1]], (30, 30, 200))       # ~14,7 x 7,2 cm, girado


class TestRegua(unittest.TestCase):
    def setUp(self):
        self.r = Regua(Path(tempfile.mkdtemp()) / "regua.json")

    def test_mede_em_perspectiva_com_erro_de_milimetros(self):
        self.assertFalse(self.r.calibrada)
        self.assertIsNotNone(self.r.calibrar(cena(A4), "a4"))
        for pts, real in ((CELULAR[0], (14.74, 7.24)), ([[40, 28], [50, 28], [50, 38], [40, 38]], (10, 10)),
                          ([[8, 30], [28, 30], [28, 33], [8, 33]], (20, 3))):
            m = self.r.medir(cena((pts, (30, 30, 200))))
            self.assertAlmostEqual(m["comprimento"], real[0], delta=0.6, msg=real)
            self.assertAlmostEqual(m["largura"], real[1], delta=0.6, msg=real)
        self.assertTrue(Regua(self.r._arquivo).calibrada)                         # guardada: vale depois

    def test_sem_folha_nao_calibra(self):
        self.assertIsNone(self.r.calibrar(cena(), "a4"))

    def test_falas(self):
        self.assertEqual(cm_falado(10.0), "10 centímetros")
        self.assertEqual(cm_falado(7.4), "7,4 centímetros")
        self.assertEqual(cm_falado(150), "1,50 metro")
        self.assertEqual(medida_falada({"comprimento": 14.9, "largura": 7.4}, "o celular"),
                         "O celular mede cerca de 14,9 por 7,4 centímetros.")


class TestComandos(unittest.TestCase):
    def setUp(self):
        prefs = validar({"nome_usuario": "Senhor"})
        self.eventos = []
        self.rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: prefs), camera=SimpleNamespace(ativa=True, ativar=mock.Mock()),
                                  estado=SimpleNamespace(atualizar=mock.Mock(), publicar=lambda e, d: self.eventos.append((e, d))),
                                  regua=Regua(Path(tempfile.mkdtemp()) / "r.json"), _ultimo_quadro=None,
                                  visao_continua=None, _olhando=threading.Event())
        self.c = cmd.Comandos(self.rt, lambda x: None)
        self.c._contexto = lambda cartao: None

    def dizer(self, frase):
        nome, args = self.c.interpretar(frase)
        return self.c.executar(nome, args, frase)

    def test_fluxo_completo(self):
        self.assertIn("Ainda não calibrei a régua", self.dizer("quanto mede isso?"))
        self.rt._ultimo_quadro = cena()
        self.assertIn("Não achei uma folha A4", self.dizer("Jarvis, calibre a régua"))
        self.rt._ultimo_quadro = cena(A4)
        self.assertIn("Régua calibrada com uma folha A4", self.dizer("Jarvis, calibre a régua"))
        self.rt._ultimo_quadro = cena(CELULAR)
        caixa = cv2.boundingRect(poli(CELULAR[0]))
        det = {"classe": 67, "nome": "celular", "conf": 0.9, "x": caixa[0] / 1280, "y": caixa[1] / 720,
               "w": caixa[2] / 1280, "h": caixa[3] / 720}
        self.rt.visao_continua = SimpleNamespace(detector=SimpleNamespace(disponivel=True),
                                                 aguardar=lambda t=3.0: [det], recentes=lambda t=2.0: [det])
        r = self.dizer("qual o tamanho do meu celular?")
        self.assertRegex(r, r"^O celular mede cerca de 1[45],\d por [67],\d centímetros\.$")
        self.assertEqual(self.eventos[-1][0], "medida")                          # desenho no HUD
        self.assertEqual(self.dizer("quanto mede o livro?"), "Não vejo o livro na câmera agora.")


if __name__ == "__main__":
    unittest.main()
