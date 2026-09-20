"""Quem e quem (autorizado pelo Senhor em 19/09): so pessoas CADASTRADAS por comando,
so numeros guardados, apagavel; desconhecido nunca e adivinhado."""

import io
import json
import sys
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime import comandos as cmd  # noqa: E402
from hud_runtime import identidade as idn  # noqa: E402
from hud_runtime import voz  # noqa: E402
from hud_runtime.deteccao import Vigia  # noqa: E402
from hud_runtime.estado import Estado  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402


def wav_de(amostras: np.ndarray, taxa: int = 16000) -> bytes:
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(np.clip(amostras, -32767, 32767).astype(np.int16).tobytes())
    return b.getvalue()


def vetor(i: int, n: int = 128) -> np.ndarray:
    v = np.zeros(n, np.float32)
    v[i] = 1.0
    return v


class TestCadastro(unittest.TestCase):
    def test_so_numeros_comparar_e_esquecer(self):
        arq = Path(tempfile.mkdtemp()) / "id.json"
        c = idn.Cadastro(arq)
        c.salvar("rostos", "dono", vetor(0))
        c.salvar("rostos", "Maria", vetor(1))
        self.assertEqual(c.comparar("rostos", vetor(0) + 0.1 * vetor(5), 0.363)[0], "dono")
        self.assertIsNone(c.comparar("rostos", vetor(7), 0.363)[0])                        # desconhecido
        salvo = json.loads(arq.read_text(encoding="utf-8"))
        self.assertTrue(all(isinstance(x, float) for x in salvo["rostos"]["dono"]))       # nada de imagem
        self.assertEqual(c.esquecer("rostos", "Maria"), ["rostos:Maria"])
        self.assertEqual(list(c.ler()["rostos"]), ["dono"])


class TestFbankEVoz(unittest.TestCase):
    def test_fbank_no_padrao_kaldi(self):
        t = np.arange(16000) / 16000
        x = (np.sin(2 * np.pi * 440 * t) * 8000).astype(np.float32)
        f = idn.fbank(x)
        self.assertEqual(f.shape, (98, 80))                                                  # 1 + (16000-400)//160
        self.assertLess(float(np.abs(f.mean(axis=0)).max()), 1e-4)                           # media subtraida
        banda_440 = int(np.argmax(f.std(axis=0) + (f - f.min()).mean(axis=0)))
        self.assertLess(banda_440, 30)                                                       # energia nas bandas baixas

    @unittest.skipUnless((idn.MODELOS / "wespeaker_voxceleb_resnet34_LM.onnx").is_file(), "modelo de voz ausente")
    def test_modelo_real_da_256_numeros(self):
        f = idn.Falantes(idn.Cadastro(Path(tempfile.mkdtemp()) / "i.json"))
        rng = np.random.default_rng(1)
        v = f.vetor(wav_de(rng.normal(0, 3000, 32000)))
        self.assertEqual(v.shape, (256,))
        self.assertIsNone(f.vetor(wav_de(rng.normal(0, 3000, 8000))))                       # meio segundo: curto


class TestComandos(unittest.TestCase):
    def setUp(self):
        self.prefs = validar({"nome_usuario": "Senhor"})
        self.cad = idn.Cadastro(Path(tempfile.mkdtemp()) / "id.json")
        self.rostos = SimpleNamespace(disponivel=True, vetor_de_um_rosto=mock.Mock(return_value=vetor(0)),
                                      identificar=mock.Mock(return_value=[]))
        self.conversa = SimpleNamespace(iniciar_cadastro_voz=mock.Mock(), falante=None)
        self.rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: self.prefs, aplicar=lambda d: self.prefs.update(d)),
                                  estado=SimpleNamespace(atualizar=mock.Mock(), registrar=mock.Mock()),
                                  identidades=self.cad, rostos_id=self.rostos, conversa=self.conversa,
                                  falantes=SimpleNamespace(disponivel=True), camera=SimpleNamespace(ativa=True, ativar=mock.Mock()),
                                  _ultimo_quadro=np.zeros((10, 10, 3), np.uint8), pessoas=(0.0, []), _olhando=threading.Event())
        self.c = cmd.Comandos(self.rt, lambda x: None)

    def dizer(self, frase):
        nome, args = self.c.interpretar(frase)
        def proximo_quadro(_segundos):
            self.rt._ultimo_quadro = np.zeros((10, 10, 3), np.uint8)
        with mock.patch("time.sleep", side_effect=proximo_quadro):
            return self.c.executar(nome, args, frase)

    def test_cadastro_de_rosto_e_quem_esta_aqui(self):
        self.assertIn("Ainda não conheço o rosto de ninguém", self.dizer("quem está aqui?"))
        self.assertEqual(self.dizer("Jarvis, memorize meu rosto"), "Pronto, Senhor. Cadastro do seu rosto salvo neste computador.")
        self.rostos.vetor_de_um_rosto.return_value = vetor(1)
        r = self.dizer("este é o Pedro, memorize o rosto dele")
        self.assertIn("Cadastro do rosto de Pedro salvo neste computador. Só cadastro quem está de acordo", r)
        self.assertEqual(sorted(self.cad.ler()["rostos"]), ["Pedro", "dono"])
        self.rostos.identificar.return_value = [{"nome": "dono"}, {"nome": None}]
        self.assertEqual(self.dizer("quem está aqui?"), "Estou vendo o Senhor e uma pessoa que não conheço.")
        self.assertEqual(self.dizer("quem você conhece?"),
                         "De rosto, conheço o Senhor e Pedro. De voz, ninguém ainda.")
        self.assertIn("Apaguei o de Pedro", self.dizer("esqueça o rosto do Pedro"))

    def test_dois_rostos_nao_cadastra(self):
        self.rostos.vetor_de_um_rosto.return_value = 2
        self.assertIn("Vejo mais de um rosto", self.dizer("memorize o rosto da Maria"))
        self.assertEqual(self.cad.ler()["rostos"], {})

    def test_voz_e_so_o_dono(self):
        self.assertIn("Primeiro preciso conhecer a sua voz", self.dizer("só atenda a minha voz"))
        self.assertIn("Fale três frases", self.dizer("memorize minha voz"))
        self.conversa.iniciar_cadastro_voz.assert_called_once_with("dono")
        self.cad.salvar("vozes", "dono", vetor(3, 256))
        self.assertIn("só atendo a sua voz", self.dizer("só atenda a minha voz"))
        self.assertTrue(self.prefs["so_o_dono"])
        self.conversa.falante = ("dono", 0.8, time.time())
        self.assertEqual(self.dizer("quem está falando?"), "Pela voz, é o Senhor.")


class TestConversaVoz(unittest.TestCase):
    def setUp(self):
        self.prefs = validar({"nome_usuario": "Senhor", "exigir_nome": True})
        self.falados = []
        rep = SimpleNamespace(tocar=lambda a, t: "ok", falando=False, parar=lambda: None)
        stt = SimpleNamespace(pronta=True, transcrever=lambda wav, idioma="pt": self.texto)
        self.mic = SimpleNamespace(ativo=True, ativar=mock.Mock(), desativar=mock.Mock())
        self.c = voz.Conversa(Estado(), SimpleNamespace(ler=lambda: self.prefs), self.mic, stt,
                              SimpleNamespace(pronta=True, gerar=lambda *a, **k: None), rep, ponte_conectada=lambda: True)
        self.c.falar = self.falados.append
        self.cad = idn.Cadastro(Path(tempfile.mkdtemp()) / "id.json")
        self.vetores = iter([vetor(2, 256), vetor(2, 256) + 0.05 * vetor(4, 256), vetor(2, 256)])
        self.c.falantes = SimpleNamespace(disponivel=True, cadastro=self.cad,
                                          vetor=lambda wav, minimo_s=1.5: next(self.vetores),
                                          quem=lambda wav: self.cad.comparar("vozes", vetor(9, 256), 0.5))
        self.c.atender = mock.Mock(return_value="ok")

    def tearDown(self):
        self.c.encerrar()

    def test_cadastro_de_voz_em_tres_frases(self):
        self.c.iniciar_cadastro_voz("dono")
        for frase in ("primeira frase qualquer", "segunda frase", "terceira frase"):
            self.texto = frase
            self.c._turno(b"wav")
        self.assertEqual(self.falados, ["Mais uma frase, por favor.", "Só mais uma.", "Pronto, Senhor. Cadastro da sua voz salvo neste computador."])
        self.assertIn("dono", self.cad.ler()["vozes"])
        self.c.atender.assert_not_called()                                                  # amostras nao viram comando

    def test_so_o_dono_ignora_outra_voz(self):
        self.cad.salvar("vozes", "dono", vetor(2, 256))
        self.prefs = dict(self.prefs, so_o_dono=True)
        self.texto = "Jarvis, abra o Gmail"
        self.c._turno(b"wav")                                                                # voz 9: nao e o dono
        self.c.atender.assert_not_called()
        self.assertEqual(self.falados, ["Desculpe, só atendo a voz do Senhor."])


class TestVigiaConhecidos(unittest.TestCase):
    def test_ignorar_recomeca_a_contagem(self):
        t = {"v": 0.0}
        vg = Vigia(espera_s=0, relogio=lambda: t["v"])
        vg.ligar()
        pessoa = [{"classe": 0, "conf": 0.9}]
        vg.conferir(pessoa)
        t["v"] = 1.0
        vg.ignorar_agora()                                                                   # era o Senhor
        t["v"] = 2.0
        self.assertFalse(vg.conferir(pessoa))                                                # recomecou do zero
        t["v"] = 3.6
        self.assertTrue(vg.conferir(pessoa))


if __name__ == "__main__":
    unittest.main()
