"""Capacidades declaradas por canal (F37, §14).

A regra que estes testes defendem: capacidade não declarada é capacidade
ausente, e canal autenticado não é o mesmo que canal capaz.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.canais import (  # noqa: E402
    APRESENTACAO,
    ARQUIVO,
    AUDIO,
    CONTROLE,
    TEXTO,
    Canais,
    falar_lista,
)


class OQueCadaCanalFaz(unittest.TestCase):
    def setUp(self):
        self.c = Canais()

    def test_a_tela_faz_tudo_e_o_telegram_so_texto(self):
        self.assertTrue(self.c.pode("tela", AUDIO))
        self.assertTrue(self.c.pode("tela", APRESENTACAO))
        self.assertTrue(self.c.pode("telegram", TEXTO))
        self.assertFalse(self.c.pode("telegram", AUDIO))
        self.assertFalse(self.c.pode("telegram", APRESENTACAO))
        self.assertFalse(self.c.pode("telegram", CONTROLE))

    def test_chat_tem_texto_e_arquivo_mas_a_fala_sai_no_computador(self):
        self.assertTrue(self.c.pode("chat", ARQUIVO))
        self.assertFalse(self.c.pode("chat", AUDIO))
        frase = self.c.porque_nao("chat", AUDIO)
        self.assertIn("não faz áudio falado", frase)
        self.assertIn("no computador", frase)

    def test_canal_desconhecido_nao_pode_nada(self):
        self.assertFalse(self.c.pode("whatsapp", TEXTO))
        self.assertIn("Não conheço esse canal", self.c.porque_nao("whatsapp", TEXTO))

    def test_capacidade_inventada_e_ignorada(self):
        c = self.c.registrar("teste", "Canal de teste", ("texto", "telepatia"))
        self.assertEqual(c.capacidades, ("texto",))

    def test_autenticado_nao_e_o_mesmo_que_capaz(self):
        # telegram comeca sem pareamento: nem o texto vale para contexto privado
        self.assertFalse(self.c.obter("telegram").autenticado)
        frase = self.c.porque_nao("telegram", TEXTO)
        self.assertIn("não está autenticado", frase)
        self.assertIn("não recupero contexto privado", frase)

        self.c.autenticar("telegram")                      # pareou
        self.assertTrue(self.c.obter("telegram").autenticado)
        self.assertTrue(self.c.pode("telegram", TEXTO))
        self.assertFalse(self.c.pode("telegram", AUDIO))   # pareado continua sem áudio

    def test_a_lista_falada_diz_canal_por_canal(self):
        frase = falar_lista(self.c.listar())
        self.assertIn("Telegram (sem autenticação): texto", frase)
        self.assertIn("controle do computador", frase)

    def test_cartao_para_a_tela(self):
        cartao = self.c.cartao()
        ids = {c["id"] for c in cartao["canais"]}
        self.assertEqual(ids, {"voz", "tela", "chat", "telegram"})


class PelaVoz(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        from hud_runtime.comandos import Comandos
        self.canais = Canais()
        rt = SimpleNamespace(
            prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}),
            estado=SimpleNamespace(atualizar=lambda *a, **k: None, registrar=lambda *a, **k: None,
                                   telemetria={}),
            canais=self.canais)
        self.c = Comandos(rt, lambda pagina: None)

    def dizer(self, frase):
        achado = self.c.interpretar(frase)
        self.assertIsNotNone(achado, f"nenhuma regra entendeu: {frase}")
        return achado[0], self.c.executar(achado[0], achado[1], frase)

    def test_perguntar_o_que_cada_canal_faz(self):
        nome, r = self.dizer("Jarvis, quais canais você tem?")
        self.assertEqual(nome, "canais_listar")
        self.assertIn("Telegram", r)
        self.assertIn("texto", r)

    def test_perguntar_se_um_canal_faz_algo(self):
        nome, r = self.dizer("Jarvis, o Telegram toca áudio?")
        self.assertEqual(nome, "canais_pode")
        self.assertIn("não faz áudio falado", r)


if __name__ == "__main__":
    unittest.main()
