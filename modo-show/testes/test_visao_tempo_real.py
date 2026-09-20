"""Visao em tempo real (detector local YOLOX), respostas na hora e modo vigia."""

import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime import comandos as cmd  # noqa: E402
from hud_runtime import deteccao as d  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402


def obj(classe, conf=0.9, x=0.4, y=0.4, w=0.2, h=0.2):
    return {"classe": classe, "nome": d.CLASSES[classe][0], "conf": conf, "x": x, "y": y, "w": w, "h": h}


PESSOA, COPO, CELULAR = 0, 41, 67


class TestNomes(unittest.TestCase):
    def test_classes_e_falas(self):
        self.assertEqual(len(d.CLASSES), 80)
        self.assertEqual(d.classe_citada("meu celular"), CELULAR)
        self.assertEqual(d.classe_citada("a caneca"), COPO)
        self.assertEqual(d.classe_citada("pessoas"), PESSOA)
        self.assertEqual(d.classe_citada("o controle"), 65)
        self.assertIsNone(d.classe_citada("chaves"))                     # nao esta entre os 80: vai ao modelo
        self.assertEqual(d.quantidade(1, PESSOA), "uma pessoa")
        self.assertEqual(d.quantidade(2, CELULAR), "dois celulares")
        self.assertEqual(d.resumo([obj(COPO), obj(PESSOA), obj(COPO), obj(CELULAR)]),
                         "uma pessoa, dois copos e um celular")          # pessoas primeiro
        self.assertTrue(d.no_retangulo(obj(COPO), (0.22, 0.15, 0.56, 0.70)))
        self.assertFalse(d.no_retangulo(obj(COPO, x=0.0, w=0.1), (0.22, 0.15, 0.56, 0.70)))


class TestContinua(unittest.TestCase):
    def fazer(self, respostas, ativo=lambda: True):
        publicados = []
        det = SimpleNamespace(detectar=mock.Mock(side_effect=respostas), disponivel=True)
        quadros = iter([np.zeros((4, 4, 3), np.uint8) for _ in range(50)])
        v = d.VisaoContinua(det, quadro=lambda: next(quadros, None), ativo=ativo,
                            publicar=lambda o, ms: publicados.append(o), intervalo=0.01)
        return v, publicados

    def test_so_fala_o_que_se_repete(self):
        v, _ = self.fazer([])
        v.ultimos, v.em = [obj(COPO, 0.58), obj(CELULAR, 0.9)], time.time()
        v._historico.extend([[obj(CELULAR, 0.9)], v.ultimos])
        self.assertEqual([o["classe"] for o in v.estaveis()], [CELULAR])      # copo de 58% so num quadro: nao
        v._historico.appendleft([obj(COPO, 0.6)])
        self.assertEqual(sorted(o["classe"] for o in v.estaveis()), [COPO, CELULAR])
        v.em = time.time() - 10
        self.assertIsNone(v.estaveis())                                       # velho: camera parada/desligada

    def test_publica_e_limpa_ao_desligar(self):
        ligado = {"v": True}
        v, publicados = self.fazer([[obj(COPO)]] * 40, ativo=lambda: ligado["v"])
        v.start()
        fim = time.time() + 3
        while len(publicados) < 3 and time.time() < fim:
            time.sleep(0.02)
        self.assertGreaterEqual(len(publicados), 3)
        self.assertIsNotNone(v.aguardar(2))
        ligado["v"] = False
        fim = time.time() + 3
        while publicados[-1] != [] and time.time() < fim:
            time.sleep(0.05)
        v.parar()
        self.assertEqual(publicados[-1], [])                                   # caixas somem com a camera
        self.assertEqual(v.ultimos, [])


class TestVigia(unittest.TestCase):
    def test_arma_depois_e_alerta_uma_vez_por_minuto(self):
        t = {"v": 1000.0}
        vg = d.Vigia(espera_s=20, relogio=lambda: t["v"])
        vg.ligar()
        self.assertFalse(vg.conferir([obj(PESSOA)]))                           # ainda saindo da sala
        t["v"] += 21
        self.assertFalse(vg.conferir([obj(PESSOA)]))                           # precisa ficar 1,5 s
        t["v"] += 1.6
        self.assertTrue(vg.conferir([obj(PESSOA)]))
        t["v"] += 5
        self.assertFalse(vg.conferir([obj(PESSOA)]))                           # nao repete logo
        t["v"] += 60
        self.assertTrue(vg.conferir([obj(PESSOA)]))
        self.assertFalse(vg.conferir([obj(COPO)]))                             # objeto nao e alerta
        self.assertTrue(vg.desligar())
        t["v"] += 120
        self.assertFalse(vg.conferir([obj(PESSOA)]))


class TestComandos(unittest.TestCase):
    def setUp(self):
        prefs = validar({"nome_usuario": "Senhor"})
        self.camera = SimpleNamespace(ativa=False, ativar=mock.Mock())
        self.visao = SimpleNamespace(detector=SimpleNamespace(disponivel=True),
                                     aguardar=mock.Mock(return_value=[obj(PESSOA, x=0.3), obj(CELULAR, x=0.8, y=0.75)]))
        self.rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: prefs), camera=self.camera,
                                  visao_continua=self.visao, estado=SimpleNamespace(atualizar=mock.Mock(), registrar=mock.Mock()),
                                  percepcao=SimpleNamespace(recente=lambda: False), _olhando=threading.Event(),
                                  vigia_ligar=mock.Mock(return_value=None), vigia_desligar=mock.Mock(return_value=True))
        self.c = cmd.Comandos(self.rt, lambda x: None)

    def dizer(self, frase):
        nome, args = self.c.interpretar(frase)
        return self.c.executar(nome, args, frase)

    def test_respostas_na_hora(self):
        with mock.patch.object(self.c, "_detalhar"):
            r = self.dizer("o que você está vendo?")
        self.assertTrue(r.startswith("Agora vejo uma pessoa e um celular."), r)
        self.camera.ativar.assert_called_once()                                # pediu para ver: liga a camera
        self.assertEqual(self.dizer("onde está meu celular?"), "O celular está à direita, embaixo, Senhor.")
        self.assertEqual(self.dizer("quantas pessoas tem aqui?"), "Vejo uma pessoa.")
        self.assertEqual(self.dizer("quantos copos você vê?"), "Não vejo nenhum copo agora.")
        self.assertEqual(self.dizer("onde está a caneca?"), "Não vejo o copo na câmera agora.")

    def test_desligado_nas_preferencias_nao_liga_camera(self):
        self.rt.prefs = SimpleNamespace(ler=lambda: validar({"visao_tempo_real": False}))
        self.assertEqual(self.dizer("quantas pessoas tem aqui?"), "Para contar, preciso da visão em tempo real e da câmera.")
        self.camera.ativar.assert_not_called()

    def test_vigia_e_chegada(self):
        self.assertIn("Modo vigia armado", self.dizer("ative o modo vigia"))
        self.assertEqual(self.dizer("desative o modo vigia"), "Modo vigia desativado.")
        with mock.patch.object(self.c, "_rotinas", return_value=SimpleNamespace(chegada=lambda: "Bem-vindo.")):
            self.assertEqual(self.dizer("Jarvis, cheguei"), "Modo vigia desativado. Bem-vindo.")


@unittest.skipUnless(d.MODELO.is_file(), "detector nao baixado")
class TestDetectorReal(unittest.TestCase):
    def test_quadro_vazio_nao_inventa_e_e_rapido(self):
        det = d.Detector()
        img = np.full((720, 1280, 3), 40, np.uint8)
        det.detectar(img)
        t0 = time.perf_counter()
        self.assertEqual(det.detectar(img), [])
        self.assertLess(time.perf_counter() - t0, 2.0)                         # medido ~0,2 s nesta CPU


if __name__ == "__main__":
    unittest.main()
