"""VOSK (reconhecimento do projeto B) e NudeNet 320/640 (varredura do projeto C),
baixados com autorizacao em 18/09/2026."""

import io
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime import audio, varredura  # noqa: E402


def silencio_wav(seg=0.5):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(np.zeros(int(16000 * seg), np.int16).tobytes())
    return b.getvalue()


class TestVosk(unittest.TestCase):
    def test_primeira_palavra_vira_jarvis_so_no_comeco(self):
        sub = lambda t: audio._VOSK_JARVIS.sub("Jarvis,", t, count=1)  # noqa: E731
        self.assertEqual(sub("árvores que horas são"), "Jarvis, que horas são")
        self.assertEqual(sub("arvoredo bonito"), "arvoredo bonito")          # palavra inteira, nao prefixo
        self.assertEqual(sub("plante árvores no quintal"), "plante árvores no quintal")

    def test_motor_escolhido_e_volta_ao_whisper(self):
        t = audio.Transcricao(motor=lambda: "vosk")
        with mock.patch.object(t, "transcrever_vosk", return_value="Jarvis, notícias") as v:
            self.assertEqual(t.transcrever(silencio_wav()), "Jarvis, notícias")
            v.assert_called_once()
        t._modelo, t.nome_modelo = mock.Mock(), t._tamanho()          # ja carregado: nao recarrega
        seg = mock.Mock(text=" pelo whisper", no_speech_prob=0.1, avg_logprob=-0.2)
        t._modelo.transcribe.return_value = ([seg], None)
        with mock.patch.object(t, "transcrever_vosk", side_effect=RuntimeError("falhou")):
            self.assertEqual(t.transcrever(silencio_wav()), "pelo whisper")      # a frase nao se perde

    @unittest.skipUnless(audio.MODELO_VOSK.is_dir(), "modelo VOSK nao instalado")
    def test_modelo_real_carrega_e_silencio_nao_vira_texto(self):
        t = audio.Transcricao(motor=lambda: "vosk")
        self.assertEqual(t.transcrever_vosk(silencio_wav(1.0)), "")


class TestNudeNet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._c = [varredura.classificador_nudenet()]      # numa lista: funcao em atributo de classe viraria metodo

    def setUp(self):
        self.classificar = self._c[0]
        if self.classificar is None:
            self.skipTest("NudeNet nao instalado")

    def test_situacoes_sem_condenar_o_que_nao_analisou(self):
        import cv2
        pasta = Path(tempfile.mkdtemp()) / "Fotos de férias"
        pasta.mkdir()
        img = np.full((600, 800, 3), (200, 170, 120), np.uint8)
        (pasta / "paisagem ção.jpg").write_bytes(cv2.imencode(".jpg", img)[1].tobytes())      # acento no caminho
        (pasta / "icone.png").write_bytes(cv2.imencode(".png", np.zeros((32, 32, 3), np.uint8))[1].tobytes())
        (pasta / "quebrada.jpg").write_bytes(b"nao e imagem")
        rel = varredura.Varredura(self.classificar, home=Path(tempfile.mkdtemp())).analisar(pasta)
        sit = {Path(x["caminho"]).name: x["situacao"] for x in rel["itens"]}
        self.assertEqual(sit, {"paisagem ção.jpg": "ok", "icone.png": "ignorada", "quebrada.jpg": "nao_analisada"})
        self.assertEqual(rel["sinalizadas"], 0)

    def test_incerto_nunca_vai_para_a_quarentena(self):
        base = Path(tempfile.mkdtemp())
        fotos = base / "f"
        fotos.mkdir()
        for n in ("a.jpg", "b.jpg"):
            (fotos / n).write_bytes(n.encode() * 50)
        sits = {"a.jpg": ("incerto", "320 suspeitou"), "b.jpg": ("sensivel", "640 confirmou")}
        vr = varredura.Varredura(lambda c: sits[c.name], home=base / "h")
        rel = vr.analisar(fotos)
        self.assertEqual((rel["sinalizadas"], rel["incertas"]), (1, 1))
        vr.quarentenar(rel)
        self.assertTrue((fotos / "a.jpg").exists())                              # incerto ficou
        self.assertFalse((fotos / "b.jpg").exists())                             # so o confirmado foi


if __name__ == "__main__":
    unittest.main()
