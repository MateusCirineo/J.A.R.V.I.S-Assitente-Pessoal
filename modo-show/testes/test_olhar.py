"""Olhar automatico (video de referencia 2): objeto mostrado na regiao definida
-> uma analise; nada de modelo por quadro, rosto e movimento nao disparam."""

import sys
import unittest
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime import comandos as cmd  # noqa: E402
from hud_runtime.olhar import ObservadorObjeto  # noqa: E402

W, H = 640, 360


def fundo(brilho=90):
    img = np.full((H, W, 3), brilho, np.uint8)
    img[::20, :, :] = brilho + 25                              # textura leve (parede, mesa)
    return img


def com_objeto(img, x=260, y=110, w=120, h=150, cor=(20, 60, 200)):
    out = img.copy()
    out[y:y + h, x:x + w] = cor
    return out


class TestObservador(unittest.TestCase):
    def setUp(self):
        self.recortes = []
        self.o = ObservadorObjeto(self.recortes.append, "centro")
        self.t = 0.0

    def passo(self, img, rostos=(), n=1, dt=1 / 15):
        for _ in range(n):
            self.t += dt
            fase = self.o.processar(img, list(rostos), agora=self.t)
        return fase

    def aprender(self):
        self.assertEqual(self.passo(fundo(), n=25), "vazio")

    def test_objeto_parado_dispara_uma_vez(self):
        self.aprender()
        obj = com_objeto(fundo())
        self.assertEqual(self.passo(obj, n=5), "candidato")
        self.passo(obj, n=20)                                   # ~1,3 s parado
        self.assertEqual(len(self.recortes), 1)
        rec = self.recortes[0]
        self.assertEqual(rec.shape[:2], (round(0.70 * H), round(0.56 * W)))   # so a regiao, nao o quadro todo
        self.passo(obj, n=60)                                   # continua ali: nao repete
        self.assertEqual(len(self.recortes), 1)
        self.assertEqual(self.o.fase, "aguardando_sair")

    def test_objeto_mexendo_nao_dispara(self):
        self.aprender()
        for i in range(60):
            self.passo(com_objeto(fundo(), x=180 + (i % 2) * 90))
        self.assertEqual(self.recortes, [])

    def test_so_o_rosto_mudando_nao_dispara(self):
        self.aprender()
        rosto = [{"x": 260 / W, "y": 110 / H, "w": 120 / W, "h": 90 / H}]
        cara = com_objeto(fundo(), x=260, y=110, w=120, h=90, cor=(150, 170, 200))
        self.passo(cara, rostos=rosto, n=40)
        self.assertEqual(self.recortes, [])

    def test_luz_mudando_devagar_nao_dispara(self):
        self.aprender()
        for b in range(90, 130):
            self.passo(fundo(b), n=3)
        self.assertEqual(self.recortes, [])

    def test_sai_e_intervalo_minimo(self):
        self.aprender()
        obj = com_objeto(fundo())
        self.passo(obj, n=25)
        self.passo(fundo(), n=30)                               # tirou o objeto
        self.assertEqual(self.o.fase, "vazio")
        outro = com_objeto(fundo(), cor=(200, 200, 30))
        self.passo(outro, n=25)                                 # cedo demais (< 25 s): nao analisa
        self.assertEqual(len(self.recortes), 1)
        self.passo(fundo(), n=30)
        self.t += 30
        self.passo(outro, n=25)
        self.assertEqual(len(self.recortes), 2)

    def test_regiao_mesa_ignora_o_centro_alto(self):
        o = ObservadorObjeto(self.recortes.append, "mesa")
        t = 0.0
        for _ in range(25):
            t += 1 / 15
            o.processar(fundo(), [], agora=t)
        for _ in range(30):                                      # objeto la em cima: fora da regiao
            t += 1 / 15
            o.processar(com_objeto(fundo(), y=20, h=80), [], agora=t)
        self.assertEqual(self.recortes, [])


class TestComandosOlhar(unittest.TestCase):
    def test_rotas(self):
        casos = {"Jarvis, ative o olhar automático": ("olhar_auto", "ative"),
                 "desligue o reconhecimento automático": ("olhar_auto", "desligue"),
                 "região de visão na mesa": ("olhar_auto", None)}
        for frase, (nome, acao) in casos.items():
            achado = cmd.interpretar(frase)
            self.assertEqual(achado[0], nome, frase)
            if acao:
                self.assertEqual(achado[1]["acao"], acao)
        self.assertEqual(cmd.interpretar("o que é isso?")[0], "visao")          # o pedido manual continua


if __name__ == "__main__":
    unittest.main()
