"""Modelo principal x reserva (autorizado pelo Senhor em 19/09).

O que aconteceu de verdade naquele dia: o gemma4:e4b (9,6 GB) nao coube na
memoria, o Ollama ficou 604 s tentando carregar e devolveu
"timed out waiting for llama-server to start". O Jarvis ficou MUDO.

Aqui: quando nao cabe, usa o reserva e AVISA; quando cabe (ou ja esta
carregado), usa o principal; quando o principal falha no meio, repete no
reserva em vez de deixar o Senhor sem resposta.
"""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime import modelos_ia, voz  # noqa: E402
from hud_runtime.estado import Estado  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402

PREFS = {"modelo_voz": "gemma4:e4b", "modelo_reserva": "qwen3.5:4b"}


def limpar():
    modelos_ia._cache.clear()
    modelos_ia._falhas.clear()
    modelos_ia._ultimo_aviso = 0.0


class Escolha(unittest.TestCase):
    def setUp(self):
        limpar()
        self.addCleanup(limpar)

    def _ollama(self, carregados=(), tamanho_gb=9.6):
        def consultar(caminho, dados=None):
            if caminho == "/api/tags":
                return {"models": [{"name": "gemma4:e4b", "size": int(tamanho_gb * 1e9)},
                                   {"name": "qwen3.5:4b", "size": 3_390_000_000}]}
            return {"models": [{"name": n} for n in carregados]}
        return mock.patch.object(modelos_ia, "_consultar", consultar)

    def test_ja_carregado_usa_o_principal(self):
        with self._ollama(carregados=["gemma4:e4b"]), \
             mock.patch.object(modelos_ia, "memoria_livre_gb", lambda: 0.5):
            self.assertEqual(modelos_ia.escolher(PREFS), ("gemma4:e4b", None))

    def test_sem_memoria_usa_a_reserva_e_diz_por_que(self):
        with self._ollama(), mock.patch.object(modelos_ia, "memoria_livre_gb", lambda: 0.9):
            modelo, motivo = modelos_ia.escolher(PREFS)
        self.assertEqual(modelo, "qwen3.5:4b")
        self.assertIn("não cabe", motivo)
        self.assertIn("9.6 GB", motivo)

    def test_com_memoria_sobrando_usa_o_principal(self):
        with self._ollama(), mock.patch.object(modelos_ia, "memoria_livre_gb", lambda: 12.0):
            self.assertEqual(modelos_ia.escolher(PREFS), ("gemma4:e4b", None))

    def test_depois_de_falhar_fica_de_molho(self):
        modelos_ia.marcar_falha("gemma4:e4b")
        with self._ollama(carregados=["gemma4:e4b"]), \
             mock.patch.object(modelos_ia, "memoria_livre_gb", lambda: 12.0):
            modelo, motivo = modelos_ia.escolher(PREFS)
        self.assertEqual(modelo, "qwen3.5:4b")
        self.assertIn("falhar", motivo)

    def test_sem_reserva_configurada_nao_troca_nem_pergunta(self):
        chamou = []
        with mock.patch.object(modelos_ia, "_consultar", lambda *a, **k: chamou.append(a) or None):
            self.assertEqual(modelos_ia.escolher({"modelo_voz": "gemma4:e4b", "modelo_reserva": ""}),
                             ("gemma4:e4b", None))
        self.assertEqual(chamou, [])

    def test_o_aviso_nao_vira_ladainha(self):
        primeiro = modelos_ia.aviso_de_reserva("a memória está cheia", "Senhor")
        segundo = modelos_ia.aviso_de_reserva("a memória está cheia", "Senhor")
        self.assertIn("reserva", primeiro)
        self.assertIn("Senhor", primeiro)
        self.assertEqual(segundo, "")                 # no maximo um aviso a cada 30 min

    def test_a_reserva_entra_nas_preferencias(self):
        p = validar({"modelo_reserva": "qwen3.5:2b", "espera_modelo_s": 90})
        self.assertEqual(p["modelo_reserva"], "qwen3.5:2b")
        self.assertEqual(p["espera_modelo_s"], 90)
        self.assertEqual(validar({"espera_modelo_s": 9999})["espera_modelo_s"], 600)   # teto


class Conversa(unittest.TestCase):
    """O caminho inteiro: o principal trava, o Jarvis responde pelo reserva."""

    def setUp(self):
        limpar()
        self.addCleanup(limpar)
        self.prefs = validar({"nome_usuario": "Senhor", "modelo_voz": "gemma4:e4b",
                              "modelo_reserva": "qwen3.5:4b", "espera_modelo_s": 30,
                              "fala_em_fluxo": False, "voz_muda": True})
        rep = SimpleNamespace(tocar=lambda a, t: "ok", falando=False, parar=lambda: None)
        tts = SimpleNamespace(pronta=True, gerar=lambda texto, voz=None: texto)
        self.c = voz.Conversa(Estado(), SimpleNamespace(ler=lambda: self.prefs), None, None, tts, rep,
                              ponte_conectada=lambda: True)
        self.addCleanup(self.c.encerrar)
        self.modelos = []

    def _servidor(self, falhar_no):
        """Responde a todo mundo, menos ao modelo `falhar_no` (que 'trava')."""
        class R:
            def __init__(self, dados):
                self.dados = dados

            def read(self):
                return self.dados

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def urlopen(req, timeout=None):
            corpo = json.loads(req.data) if req.data else {}
            modelo = corpo.get("model", "")
            if "/v1/chat/completions" in req.full_url or "/api/chat" in req.full_url:
                self.modelos.append(modelo)
                if modelo == falhar_no:
                    raise TimeoutError("timed out waiting for llama-server to start")
                return R(json.dumps({"choices": [{"message": {"content": "Pronto, Senhor."}}]}).encode())
            return R(json.dumps({"models": []}).encode())
        return mock.patch("urllib.request.urlopen", urlopen)

    def test_o_principal_trava_e_a_reserva_responde(self):
        with mock.patch.object(voz, "escolher", lambda p: (p["modelo_voz"], None)), \
             self._servidor(falhar_no="gemma4:e4b"):
            resposta = self.c.perguntar("me conte uma novidade", falar=False)
        self.assertEqual(self.modelos, ["gemma4:e4b", "qwen3.5:4b"])   # tentou e trocou
        self.assertIn("Pronto", resposta)

    def test_o_aviso_sai_tambem_no_texto(self):
        with mock.patch.object(voz, "escolher", lambda p: ("qwen3.5:4b", "a memória está cheia")), \
             self._servidor(falhar_no="nenhum"):
            resposta = self.c.perguntar("me conte uma novidade", falar=False)
        self.assertTrue(resposta.startswith("Usando o modelo reserva"), resposta)
        self.assertIn("Pronto", resposta)

    def test_quando_o_principal_responde_a_reserva_nao_entra(self):
        with mock.patch.object(voz, "escolher", lambda p: (p["modelo_voz"], None)), \
             self._servidor(falhar_no="nenhum"):
            self.c.perguntar("me conte uma novidade", falar=False)
        self.assertEqual(self.modelos, ["gemma4:e4b"])


if __name__ == "__main__":
    unittest.main()
