"""Catalogo de vozes, parada rapida, modo texto e palavra de ativacao
(itens V2, V4, V5, V6, V7 da matriz)."""

import io
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime import agenda, comandos as cmd, vozes  # noqa: E402
from hud_runtime.anunciador import Anunciador  # noqa: E402
from hud_runtime.voz import chamou_jarvis  # noqa: E402


class _Prefs:
    def __init__(self, d):
        self.d = d

    def ler(self):
        return dict(self.d)

    def aplicar(self, m):
        self.d.update(m)


class _Kokoro:
    def gerar(self, texto, voz="pm_alex"):
        return np.zeros(2400, np.float32)


class TestCatalogo(unittest.TestCase):
    def setUp(self):
        self.seg = Path(tempfile.mkdtemp()) / "segredos.json"
        self.p = mock.patch.object(agenda, "SEGREDOS", self.seg)
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_catalogo_sem_segredos(self):
        vozes.Vozes.definir_credenciais("fish", {"chave": "sk-SEGREDO-123", "modelo": "s1"})
        cat = vozes.Vozes(_Kokoro(), _Prefs({})).catalogo()
        texto = json.dumps(cat)
        self.assertNotIn("SEGREDO", texto)                      # a chave nunca sai
        fish = next(c for c in cat if c["id"] == "fish")
        self.assertTrue(fish["remoto"] and fish["pronto"] and fish["configurado"]["chave"])
        self.assertEqual(fish["vozes"], ["a5b93aeddcc948c19ea04f0afe9d178c"])
        kokoro = next(c for c in cat if c["id"] == "kokoro")
        self.assertFalse(kokoro["remoto"])
        azure = next(c for c in cat if c["id"] == "azure")
        self.assertFalse(azure["pronto"])
        self.assertEqual(azure["falta"], ["chave", "regiao"])

    def test_remover_credencial(self):
        vozes.Vozes.definir_credenciais("elevenlabs", {"chave": "x", "voz": "y", "lixo": "z"})
        self.assertEqual(set(vozes.Vozes.credenciais("elevenlabs")), {"chave", "voz"})
        vozes.Vozes.remover_credenciais("elevenlabs")
        self.assertEqual(vozes.Vozes.credenciais("elevenlabs"), {})
        with self.assertRaises(ValueError):
            vozes.Vozes.definir_credenciais("kokoro", {"chave": "x"})

    def test_remoto_sem_chave_cai_para_o_local(self):
        registros = []
        v = vozes.Vozes(_Kokoro(), _Prefs({"voz_provedor": "fish", "voz_tts": "pm_alex"}),
                        registrar=lambda t, n: registros.append((t, n)))
        audio, taxa = v.gerar("teste")
        self.assertEqual(taxa, 24000)
        self.assertIn("fish.audio sem chave", v.ultimo["erro"])
        self.assertTrue(any("usando Kokoro local" in t for t, _ in registros))

    def test_piper_sem_arquivos(self):
        with self.assertRaises(vozes.ErroVoz):
            vozes.piper_falar("oi", {"exe": "", "modelo": ""})    # Path("") nao conta como arquivo

    def test_decodificadores(self):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(22050)
            w.writeframes((np.ones(200, np.int16) * 16384).tobytes())
        audio, taxa = vozes.de_wav(buf.getvalue())
        self.assertEqual((taxa, audio.shape[0]), (22050, 100))  # estereo vira mono
        self.assertAlmostEqual(float(audio.max()), 0.5, places=3)
        a, t = vozes.de_pcm16((np.ones(10, np.int16) * -32768).tobytes(), 24000)
        self.assertEqual((t, float(a.min())), (24000, -1.0))


class TestParadaEModoTexto(unittest.TestCase):
    def test_regras(self):
        for frase in ("Jarvis, pare", "silêncio", "chega!", "Jarvis, cancela", "para de falar"):
            self.assertEqual(cmd.interpretar(frase)[0], "parar_fala", frase)
        self.assertEqual(cmd.interpretar("Jarvis, pare a música")[0], "musica_pausar")
        self.assertEqual(cmd.interpretar("Jarvis, desativar voz")[0], "voz_desativar")
        self.assertEqual(cmd.interpretar("Jarvis, modo texto")[0], "voz_desativar")
        self.assertEqual(cmd.interpretar("Jarvis, ative a voz")[0], "voz_ativar")
        self.assertEqual(cmd.interpretar("Jarvis, sem som")[0], "volume_mutar")   # mudo do sistema != voz

    def test_executar(self):
        interrupcoes = []
        prefs = _Prefs({"nome_usuario": "Senhor"})
        rt = SimpleNamespace(prefs=prefs, conversa=SimpleNamespace(interromper=lambda: interrupcoes.append(1)),
                             _publicar_prefs=lambda: None)
        c = cmd.Comandos(rt, lambda x: None)
        self.assertEqual(c.executar("parar_fala", {}, "pare"), "")         # sem fala
        self.assertEqual(interrupcoes, [1])
        self.assertIn("Voz desativada", c.executar("voz_desativar", {}, "desativar voz"))
        self.assertTrue(prefs.d["voz_muda"])
        c.executar("voz_ativar", {}, "ative a voz")
        self.assertFalse(prefs.d["voz_muda"])

    def test_anunciador_limpar(self):
        a = Anunciador(falar=lambda t: None, ocupado=lambda: True, prefs=_Prefs({"silencio_inicio": 0, "silencio_fim": 0}))
        a.anunciar("um", categoria="agenda")
        a.anunciar("dois", pedido_pelo_usuario=True)
        self.assertEqual(a.limpar(), 2)
        self.assertEqual(a.limpar(), 0)


class TestPalavraDeAtivacao(unittest.TestCase):
    def test_nao_herda_correspondencias_amplas(self):
        # o projeto B aceitava "jovens", "ja que", "james", "servis", qualquer "jarv"
        for frase in ("os jovens chegaram", "já que você está aí", "o james ligou", "servis de limpeza",
                      "vamos jardinar"):
            self.assertFalse(chamou_jarvis(frase), frase)
        for frase in ("Jarvis, que horas são?", "jarbas abre o painel", "Jarvi, pare"):
            self.assertTrue(chamou_jarvis(frase), frase)


if __name__ == "__main__":
    unittest.main()
