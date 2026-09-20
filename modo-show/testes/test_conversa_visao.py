"""Conversa como no video de referencia (Copilot): fala frase a frase enquanto o
modelo escreve e, com a camera ligada, manda a imagem quando a pergunta e sobre
o que se ve (ou a tela, quando fala do jogo/programa)."""

import json
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime import voz  # noqa: E402
from hud_runtime.estado import Estado  # noqa: E402
from hud_runtime.fala_fluxo import FalaEmFluxo, cortar_frases, ler_ndjson_ollama, ler_sse_openai  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402


class TestFrases(unittest.TestCase):
    def test_cortar(self):
        frases, resto = cortar_frases("Olá, Senhor, tudo pronto por aqui. O dólar está a R$ 5.14 hoje! E amanh")
        self.assertEqual(frases, ["Olá, Senhor, tudo pronto por aqui.", "O dólar está a R$ 5.14 hoje!"])
        self.assertEqual(resto.strip(), "E amanh")
        self.assertEqual(cortar_frases("Sr. Stark")[0], [])                      # curto: espera juntar

    def test_leitores(self):
        sse = [b'data: {"choices":[{"delta":{"role":"assistant"}}]}', b"",
               'data: {"choices":[{"delta":{"content":"Olá"}}]}'.encode(),
               'data: {"choices":[{"delta":{"content":", Senhor."}}]}'.encode(), b"data: [DONE]",
               'data: {"choices":[{"delta":{"content":"depois do fim"}}]}'.encode()]
        self.assertEqual("".join(ler_sse_openai(sse)), "Olá, Senhor.")
        nd = [json.dumps({"message": {"content": "Vejo "}, "done": False}).encode(),
              json.dumps({"message": {"content": "um copo."}, "done": True}).encode(), b"lixo"]
        self.assertEqual("".join(ler_ndjson_ollama(nd)), "Vejo um copo.")

    def test_fala_na_ordem_sem_raciocinio_e_para_quando_pedem(self):
        tocados = []
        f = FalaEmFluxo(lambda s: (s, 1), lambda a, t: tocados.append(a) or "ok", threading.Event())
        for p in ["<think>calculando", " coisas</think>Primeira frase ", "completa aqui. Segunda ", "frase termina. Resto"]:
            f.receber(p)
        texto = f.terminar()
        self.assertEqual(tocados, ["Primeira frase completa aqui.", "Segunda frase termina.", "Resto"])
        self.assertEqual(texto, "Primeira frase completa aqui. Segunda frase termina. Resto")
        self.assertTrue(f.falou)
        parar = threading.Event()
        tocados.clear()
        f = FalaEmFluxo(lambda s: (s, 1), lambda a, t: tocados.append(a) or "interrompido", parar)
        f.receber("Uma frase bem comprida para tocar. Outra frase que nao deve tocar. ")
        f.terminar()
        self.assertEqual(tocados, ["Uma frase bem comprida para tocar."])        # "pare": o resto e descartado


class TestPedeImagem(unittest.TestCase):
    def test_quando_manda_imagem(self):
        for frase in ("Jarvis, o que você acha disso?", "você está vendo a minha mão?", "qual a cor desse objeto?",
                      "o que é esse frasco?", "quanto mede isso aqui na mesa?"):
            self.assertEqual(voz.pede_imagem(frase), "camera", frase)
        for frase in ("me ajude nesse jogo", "o que está na minha tela?", "explique esse erro nessa janela"):
            self.assertEqual(voz.pede_imagem(frase), "tela", frase)
        for frase in ("que horas são?", "me conte uma curiosidade sobre Marte"):
            self.assertIsNone(voz.pede_imagem(frase), frase)


class Resposta:
    def __init__(self, linhas):
        self.linhas = linhas

    def __iter__(self):
        return iter(self.linhas)

    def read(self):                                   # caminho sem stream (resposta inteira)
        return b"".join(self.linhas)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestConversa(unittest.TestCase):
    def setUp(self):
        self.prefs = validar({"nome_usuario": "Senhor", "modelo_voz": "gemma4:e4b"})
        estado = Estado()
        self.tocados = []
        rep = SimpleNamespace(tocar=lambda a, t: self.tocados.append(a) or "ok", falando=False, parar=lambda: None)
        tts = SimpleNamespace(pronta=True, gerar=lambda texto, voz=None: texto)
        self.c = voz.Conversa(estado, SimpleNamespace(ler=lambda: self.prefs), None, None, tts, rep,
                              ponte_conectada=lambda: True)
        self.c.visao_contexto = lambda: (b"JPEG-DA-CAMERA", "uma pessoa e um copo")
        self.pedidos = []
        # a escolha principal/reserva pergunta ao Ollama: aqui o assunto e a conversa
        # (a reserva tem os testes dela em test_modelo_reserva.py)
        self._escolha = mock.patch.object(voz, "escolher", lambda prefs: (prefs["modelo_voz"], None))
        self._escolha.start()

    def tearDown(self):
        self._escolha.stop()
        self.c.encerrar()

    def abrir(self, linhas):
        def urlopen(req, timeout=None):
            self.pedidos.append((req.full_url, json.loads(req.data), dict(req.header_items())))
            return Resposta(linhas)
        return mock.patch("urllib.request.urlopen", urlopen)

    def test_pergunta_visual_vai_com_a_imagem_e_fala_frase_a_frase(self):
        nd = [json.dumps({"message": {"content": c}, "done": False}).encode()
              for c in ["Vejo um copo azul ", "em cima da mesa. Parece ", "de vidro, Senhor."]]
        with self.abrir(nd):
            r = self.c.atender("Jarvis, o que você acha disso aqui na mesa?", self.prefs, falar=True)
        url, corpo, _ = self.pedidos[0]
        self.assertTrue(url.endswith("/api/chat"))                                # direto ao Ollama local
        self.assertEqual(corpo["messages"][-1]["images"], ["SlBFRy1EQS1DQU1FUkE="])
        self.assertIn("o detector de objetos vê agora: uma pessoa e um copo", corpo["messages"][-1]["content"])
        self.assertEqual(r, "Vejo um copo azul em cima da mesa. Parece de vidro, Senhor.")
        self.assertEqual(self.tocados, ["Vejo um copo azul em cima da mesa.", "Parece de vidro, Senhor."])
        self.assertIn("[imagem da camera]", self.c._historico[-2]["content"])    # historico sem a imagem

    def test_pergunta_comum_vai_ao_servidor_em_stream_sem_imagem(self):
        sse = ['data: {"choices":[{"delta":{"content":"Marte tem duas luas, Fobos e Deimos. "}}]}'.encode(),
               'data: {"choices":[{"delta":{"content":"Ambas são pequenas."}}]}'.encode(), b"data: [DONE]"]
        with self.abrir(sse):
            r = self.c.atender("me conte uma curiosidade sobre Marte", self.prefs, falar=True)
        url, corpo, cab = self.pedidos[0]
        self.assertTrue(url.endswith("/v1/chat/completions"))                    # servidor do OpenJarvis
        self.assertTrue(corpo["stream"])
        self.assertEqual(cab.get("X-openjarvis-direct"), "1")
        self.assertNotIn("images", corpo["messages"][-1])
        self.assertIn("uma pessoa e um copo", corpo["messages"][-1]["content"])  # contexto barato, em texto
        self.assertEqual(r, "Marte tem duas luas, Fobos e Deimos. Ambas são pequenas.")
        self.assertEqual(len(self.tocados), 2)                                    # nao fala de novo no fim

    def test_camera_desligada_nao_manda_imagem(self):
        self.c.visao_contexto = lambda: (None, None)
        inteira = [json.dumps({"choices": [{"message": {"content": "Não estou vendo nada agora, Senhor."}}]}).encode()]
        with self.abrir(inteira):
            self.c.atender("o que você acha disso?", self.prefs, falar=False)
        url, corpo, _ = self.pedidos[0]
        self.assertTrue(url.endswith("/v1/chat/completions"))
        self.assertFalse(corpo["stream"])                                         # sem falar: resposta inteira

    def test_planejar_vai_ao_modelo_com_os_dados(self):
        self.c.tarefas = SimpleNamespace(listar=lambda: [], adicionar=None, concluir_por_texto=None)
        self.c.comandos = SimpleNamespace(interpretar=lambda t: ("raciocinio", {}), executar=lambda *a: None,
                                          contexto_para_modelo=lambda t: "[Dados reais: tarefas pendentes: estudar cálculo]")
        sse = ['data: {"choices":[{"delta":{"content":"Comece por cálculo às 14h, Senhor."}}]}'.encode(), b"data: [DONE]"]
        with self.abrir(sse):
            r = self.c.atender("planeje minha tarde considerando minhas tarefas", self.prefs, falar=True)
        self.assertEqual(r, "Comece por cálculo às 14h, Senhor.")               # nao a resposta local de "tarefas"
        self.assertIn("tarefas pendentes: estudar cálculo", self.pedidos[0][1]["messages"][-1]["content"])

    def test_preferencia_nunca(self):
        self.prefs = dict(self.prefs, visao_na_conversa="nunca")
        with self.abrir([b"data: [DONE]"]):
            self.c.atender("o que você acha disso?", self.prefs, falar=True)
        self.assertTrue(self.pedidos[0][0].endswith("/v1/chat/completions"))


if __name__ == "__main__":
    unittest.main()
