"""Funcoes estilo Alexa (contas, conversoes, datas, sorte, listas, musica, mundo),
percepcao do ambiente, pronuncia "Jarvis" e reconhecimento ("Jarvis, cheguei")."""

import json
import random
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime import audio, comandos as cmd, percepcao, utilidades as u  # noqa: E402
from hud_runtime.listas import Listas, separar_itens  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402


class TestUtilidades(unittest.TestCase):
    def test_contas(self):
        casos = {"quanto é 15% de 230": "15 por cento de 230 é 34,5.",
                 "quanto é vinte e cinco por cento de mil e duzentos": "25 por cento de 1.200 é 300.",
                 "quanto é 12 vezes 8": "Dá 96.", "quanto é 7 mais 5 vezes 2": "Dá 17.",
                 "raiz quadrada de 144": "A raiz quadrada de 144 é 12.", "2 elevado a 10": "Dá 1.024.",
                 "quanto é 10 dividido por 0": "Essa conta não tem resultado."}
        for frase, esperado in casos.items():
            self.assertEqual(u.calcular(frase), esperado, frase)
        self.assertIsNone(u.calcular("quanto está o dólar?"))
        with self.assertRaises(ValueError):
            u._avaliar(__import__("ast").parse("__import__('os')", mode="eval"))       # nada alem de numeros

    def test_conversoes(self):
        self.assertEqual(u.converter("quanto é 10 milhas em km"), "10 milhas são 16,09 km.")
        self.assertEqual(u.converter("converta 30 graus celsius para fahrenheit"), "30 celsius são 86 fahrenheit.")
        self.assertIn("Não dá para converter", u.converter("10 quilos em litros"))
        cot = SimpleNamespace(consultar=lambda a: {"status": "medido", "itens": [
            {"tipo": "moeda", "venda": 5.0, "fonte": "AwesomeAPI", "em": None}]})
        self.assertIn("500 reais", u.converter("quanto é 100 dólares em reais", cot))
        self.assertIn("20 dólares", u.converter("100 reais em dólares", cot))
        self.assertEqual(u.datas("que dia da semana cai 26 de setembro", date(2026, 9, 19)),
                         "26 de setembro de 2026 cai num sábado.")

    def test_datas_e_sorte(self):
        hoje = date(2026, 9, 19)
        self.assertEqual(u.datas("quantos dias faltam para o Natal?", hoje), "Faltam 97 dias para o Natal.")
        self.assertEqual(u.datas("que dia da semana cai 25 de dezembro", hoje),
                         "25 de dezembro de 2026 cai numa sexta-feira.")
        self.assertIn("03/11/2026", u.datas("que dia será daqui a 45 dias", hoje))
        r = random.Random(3)
        self.assertIn(u.sorte("jogue uma moeda", r), ("Deu cara.", "Deu coroa."))
        self.assertRegex(u.sorte("sorteie um número de 1 a 10", r), r"Saiu o ([1-9]|10)\.")
        self.assertIn(u.sorte("escolha entre pizza e hambúrguer", r), ("Escolho pizza.", "Escolho hambúrguer."))
        self.assertIsNone(u.sorte("escolha a voz do Jarvis", r))

    def test_cidade_mais_populosa(self):
        resp = {"results": [{"name": "Nova Iorque", "country": "Brasil", "population": 4320, "latitude": -6.7,
                             "longitude": -44.0, "timezone": "America/Fortaleza"},
                            {"name": "Nova Iorque", "country": "EUA", "population": 8804190, "latitude": 40.7,
                             "longitude": -74.0, "timezone": "America/New_York"}]}
        with mock.patch("hud_runtime.clima._get", return_value=resp):
            self.assertEqual(u.achar_cidade("Nova York")["pais"], "EUA")


class TestListas(unittest.TestCase):
    def test_ciclo(self):
        ls = Listas(Path(tempfile.mkdtemp()) / "listas.json")
        self.assertEqual(separar_itens("leite, o pão e 2 ovos"), ["leite", "pão", "2 ovos"])
        self.assertEqual(ls.adicionar("compras", ["leite", "pão"]), ["leite", "pão"])
        self.assertEqual(ls.adicionar("compras", ["Leite"]), [])                  # nao repete
        self.assertEqual(ls.remover("compras", "o leite"), "leite")
        self.assertEqual(ls.ler("compras"), ["pão"])
        self.assertEqual(ls.limpar("compras"), 1)


class TestComandosNovos(unittest.TestCase):
    def setUp(self):
        prefs = validar({"nome_usuario": "Senhor", "local_clima": {"nome": "São Paulo", "lat": -23.5, "lon": -46.6}})
        self.rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: prefs), estado=SimpleNamespace(atualizar=mock.Mock()),
                                  listas=Listas(Path(tempfile.mkdtemp()) / "l.json"))
        self.c = cmd.Comandos(self.rt, lambda x: None)

    def dizer(self, frase):
        nome, args = self.c.interpretar(frase)
        return self.c.executar(nome, args, frase)

    def test_rotas(self):
        casos = {"Jarvis, cheguei": "rotina_chegada", "quanto é 100 dólares em reais": "conversao",
                 "que horas são em Tóquio?": "hora_mundo", "como está o clima em Paris?": "clima_mundo",
                 "toque Back in Black": "tocar", "coloque para tocar Legião Urbana": "tocar", "toque a música": "musica_tocar",
                 "coloque o capacete": "capacete_ligar", "o que você está vendo?": "percepcao_ver",
                 "onde está meu celular?": "percepcao_onde", "o que mudou?": "percepcao_mudou",
                 "o que é isso?": "visao", "quanto está o dólar?": "cotacao", "notícias do mundo": "noticias"}
        for frase, esperado in casos.items():
            self.assertEqual(self.c.interpretar(frase)[0], esperado, frase)
        self.assertIsNone(self.c.interpretar("onde fica a padaria mais próxima"))            # lugar: vai ao modelo

    def test_listas_por_voz(self):
        self.assertEqual(self.dizer("adicione leite e pão à lista de compras"), "Adicionei leite e pão à lista de compras.")
        self.assertEqual(self.dizer("o que tem na lista de mercado?"), "Na lista de compras: leite e pão.")
        self.assertEqual(self.dizer("tire o leite da lista de compras"), "Tirei leite da lista de compras.")

    def test_tocar_abre_o_video(self):
        pagina = b'... "videoId":"pAgnJDJN4VA" ...'
        with mock.patch("hud_runtime.rede.baixar", return_value=pagina), mock.patch.object(self.c, "_abrir_url") as ab:
            self.assertEqual(self.dizer("toque Back in Black"), "Tocando Back in Black, Senhor.")
        ab.assert_called_once_with("https://www.youtube.com/watch?v=pAgnJDJN4VA")

    def test_cidade_configurada_fica_com_a_voz(self):
        self.assertIsNone(self.c.mundo("clima_mundo", "clima em São Paulo"))

    def test_manchetes_do_mundo_bem_faladas(self):
        from hud_runtime import noticias
        dados = {"status": "medido", "itens": [{"fonte": "G1 Mundo", "titulo": "O que está por trás disso?"},
                                               {"fonte": "BBC", "titulo": "Acordo fechado."}]}
        with mock.patch.object(noticias.Noticias, "por_categoria", return_value=dados):
            r = self.dizer("notícias do mundo")
        self.assertTrue(r.startswith("Manchetes do mundo. "), r)
        self.assertNotIn("?.", r)
        self.assertIn("BBC: Acordo fechado.", r)
        self.assertTrue(r.endswith("Li apenas as manchetes."), r)


class TestPercepcao(unittest.TestCase):
    def test_ler_resposta_sanitiza(self):
        bruto = json.dumps({"objetos": [{"nome": "livro", "detalhe": "A Origem das Espécies", "caixa": [60, 250, 360, 830]},
                                        {"nome": "homem", "caixa": [400, 0, 900, 900]},
                                        {"nome": "caneca", "caixa": [650, 470, 5000, 810]},
                                        {"nome": "", "caixa": [1, 2, 3, 4]}, {"nome": "x", "caixa": [1, 2]}],
                           "cena": "uma mesa"})
        r = percepcao.ler_resposta(bruto)
        self.assertEqual([o["nome"] for o in r["objetos"]], ["livro", "pessoa", "caneca"])   # nunca quem e
        self.assertAlmostEqual(r["objetos"][2]["x"] + r["objetos"][2]["w"], 1.0)             # caixa limitada
        self.assertEqual(percepcao.posicao(r["objetos"][0]), "à esquerda")

    def test_observar_onde_e_mudou(self):
        import numpy as np
        respostas = iter([json.dumps({"objetos": [{"nome": "celular", "caixa": [700, 600, 900, 900]}], "cena": "mesa"}),
                          json.dumps({"objetos": [{"nome": "celular", "caixa": [700, 600, 900, 900]},
                                                  {"nome": "caneca", "caixa": [100, 100, 300, 300]}], "cena": "mesa"})])
        estado = SimpleNamespace(atualizar=mock.Mock())
        p = percepcao.Percepcao(lambda *a, **k: next(respostas), estado)
        p.observar(np.zeros((100, 100, 3), np.uint8), "centro", (0.2, 0.1, 0.6, 0.8))
        self.assertIn("à direita, embaixo", p.onde_esta("meu celular"))
        self.assertIn("Não vi", p.onde_esta("chaves"))
        p.observar(np.zeros((100, 100, 3), np.uint8), "centro", (0.2, 0.1, 0.6, 0.8))
        self.assertEqual(p.mudou(), "Apareceu caneca.")
        tela = estado.atualizar.call_args.kwargs["objetos"][0]
        self.assertAlmostEqual(tela["x"], 0.2 + 0.7 * 0.6)                                    # fracao do QUADRO


class TestVozEEscuta(unittest.TestCase):
    def test_pronuncia(self):
        self.assertEqual(audio.pronuncia("Olá, eu sou o Jarvis."), "Olá, eu sou o Járvis.")
        self.assertEqual(audio.pronuncia("J.A.R.V.I.S. online"), "Járvis online")
        self.assertEqual(audio.pronuncia("Jarvisson"), "Jarvisson")

    def test_dica_e_troca_de_modelo_sem_reiniciar(self):
        escolhido = {"v": "small"}
        t = audio.Transcricao(tamanho=lambda: escolhido["v"])
        t._modelo, t.nome_modelo = mock.Mock(), "small"
        t._modelo.transcribe.return_value = ([], None)
        t.transcrever(b"")
        self.assertEqual(t._modelo.transcribe.call_args.kwargs["initial_prompt"], audio.DICA_STT)
        self.assertIn("Jarvis, cheguei", audio.DICA_STT)
        escolhido["v"] = "base"
        with mock.patch.object(t, "carregar") as carregar:
            t.transcrever(b"")
            carregar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
