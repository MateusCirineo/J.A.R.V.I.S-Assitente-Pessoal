"""Inteligencia: frase incompleta pelo contexto, dados reais para o modelo raciocinar
e o planejador (o modelo executa passos com os comandos do Jarvis, com filtro)."""

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime import comandos as cmd  # noqa: E402
from hud_runtime.contexto import continuar  # noqa: E402
from hud_runtime.listas import Listas  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402


class TestContinuar(unittest.TestCase):
    def test_frases(self):
        agora = time.time()
        u = lambda nome, frase: (nome, frase, agora - 10)                                   # noqa: E731
        self.assertEqual(continuar("e em Londres?", u("hora_mundo", "que horas são em Tóquio"), agora), "que horas são em londres")
        self.assertEqual(continuar("Jarvis, e o euro?", u("cotacao", "quanto está o dólar"), agora), "quanto está o euro")
        self.assertEqual(continuar("e de esportes?", u("noticias", "notícias de tecnologia"), agora), "notícias de esportes")
        self.assertEqual(continuar("e sobre a Nvidia?", u("noticias", "notícias de tecnologia"), agora), "notícias sobre a nvidia")
        self.assertEqual(continuar("adicione também ovos", u("lista_add", "adicione leite à lista de mercado"), agora),
                         "adicione ovos à lista de mercado")
        self.assertEqual(continuar("e em euros?", u("conversao", "quanto é 100 dólares em reais"), agora),
                         "quanto e 100 dolares em euros")
        self.assertIsNone(continuar("e em Londres?", ("hora_mundo", "x", agora - 300), agora))       # velho demais
        self.assertIsNone(continuar("e se eu te disser que amanhã vou viajar para Londres de avião?",
                                    u("hora_mundo", "x"), agora))                                  # frase longa: conversa


class TestComandos(unittest.TestCase):
    def setUp(self):
        prefs = validar({"nome_usuario": "Senhor"})
        pasta = Path(tempfile.mkdtemp())
        tel = {"sistema": {"cpu": {"status": "medido", "uso_pct": 35}, "memoria": {"status": "medido", "uso_pct": 96}},
               "agenda": {"status": "nao_configurado"}}
        self.rt = SimpleNamespace(
            prefs=SimpleNamespace(ler=lambda: prefs), listas=Listas(pasta / "l.json"),
            estado=SimpleNamespace(atualizar=mock.Mock(), ler=lambda c: {"ultima_resposta": "Em Tóquio são 15 e 10."}),
            tarefas=SimpleNamespace(listar=lambda: [{"texto": "estudar cálculo", "feita": False}, {"texto": "feita", "feita": True}]),
            secretario=SimpleNamespace(pendentes=lambda: [{"quando": time.time() + 3600, "texto": "ligar para o Pedro"}]),
            _olhando=threading.Event())
        self.c = cmd.Comandos(self.rt, lambda x: None)
        self.c._tel = lambda: tel

    def dizer(self, frase):
        nome, args = self.c.interpretar(frase)
        return self.c.executar(nome, args, frase)

    def test_continua_pelo_contexto(self):
        with mock.patch("hud_runtime.utilidades.hora_em", side_effect=lambda c: f"Em {c} são 9 horas."):
            self.assertEqual(self.dizer("que horas são em Tóquio?"), "Em Tóquio são 9 horas.")
            self.assertEqual(self.dizer("e em Londres?"), "Em londres são 9 horas.")
        self.dizer("adicione leite à lista de compras")
        self.assertEqual(self.dizer("adicione também ovos"), "Adicionei ovos à lista de compras.")
        self.assertEqual(self.dizer("repita"), "Em Tóquio são 15 e 10.")

    def test_dados_para_o_modelo(self):
        ctx = self.c.contexto_para_modelo("Jarvis, planeje meu dia")
        self.assertIn("tarefas pendentes: estudar cálculo", ctx)
        self.assertIn("ligar para o Pedro", ctx)
        self.assertIn("agenda: não conectada", ctx)
        self.assertIn("memória 96%", self.c.contexto_para_modelo("por que o PC está lento?"))
        self.assertIsNone(self.c.contexto_para_modelo("me conte uma piada sobre gatos"))

    def test_planejador_com_filtro(self):
        r = self.c.executar_ferramenta("executar_comando", {"frase": "adicione café à lista de compras"})
        self.assertEqual(r, "Adicionei café à lista de compras.")
        r = self.c.executar_ferramenta("executar_comando", {"frase": "apague toda a memória"})
        self.assertIn("não é um comando que eu rode sozinho", r)
        self.assertTrue(any(f["function"]["name"] == "executar_comando" for f in cmd.FERRAMENTAS))
        self.assertTrue(cmd.parece_acao("vou estudar agora, prepare tudo"))


if __name__ == "__main__":
    unittest.main()
