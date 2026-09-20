"""Discordar com fundamento e alternativa (F05, §4).

Regra: só discordo do que consigo conferir, sempre digo o número que caberia, e
nunca invento risco. Quem decide continua sendo o Senhor.
"""

import sys
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.discordancia import (  # noqa: E402
    Conflito,
    conflito_de_horario,
    conflito_de_recurso,
    conflitos_de_peca,
    falar,
)


class Peca(unittest.TestCase):
    def test_parede_que_nao_cabe_vem_com_o_maximo(self):
        c = conflitos_de_peca("caixa", {"c": 80, "l": 50, "a": 30, "parede": 20})
        self.assertTrue(c)
        self.assertIn("não cabe", c[0].motivo)
        self.assertIn("14,9 mm", c[0].alternativa)            # (30 - 0,2) / 2
        self.assertTrue(c[0].grave)

    def test_parede_fina_e_alerta_nao_impedimento(self):
        c = conflitos_de_peca("caixa", {"c": 40, "l": 40, "a": 20, "parede": 0.4})
        self.assertEqual(len(c), 1)
        self.assertFalse(c[0].grave)
        self.assertIn("0,8 mm", c[0].alternativa)
        self.assertIn("Dá para fazer, mas", falar(c))

    def test_peca_maior_que_a_mesa_avisa_o_limite(self):
        c = conflitos_de_peca("cilindro", {"diametro": 500, "altura": 10})
        self.assertIn("não cabe na mesa", c[0].motivo)
        self.assertIn("300 mm", c[0].alternativa)
        self.assertFalse(c[0].grave)                          # dá para fatiar em partes

    def test_furo_maior_que_o_tubo(self):
        c = conflitos_de_peca("tubo", {"externo": 10, "interno": 20, "altura": 5})
        self.assertIn("maior que o tubo", c[0].motivo)
        self.assertIn("8,4 mm", c[0].alternativa)

    def test_engrenagem_com_poucos_dentes_ensina_o_minimo(self):
        c = conflitos_de_peca("engrenagem", {"dentes": 3, "externo": 40, "espessura": 5, "furo": 5})
        self.assertIn("não formam uma engrenagem", c[0].motivo)
        self.assertIn("6 dentes", c[0].alternativa)

    def test_peca_boa_nao_gera_discordancia(self):
        self.assertEqual(conflitos_de_peca("caixa", {"c": 80, "l": 50, "a": 30, "parede": 2}), [])
        self.assertEqual(falar([]), "")


class Horario(unittest.TestCase):
    def test_lembrete_em_cima_de_compromisso_avisa(self):
        agora = time.time()
        eventos = [{"inicio": agora + 3600, "titulo": "Reunião com o time"}]
        c = conflito_de_horario(agora + 3600 + 600, eventos)
        self.assertIsNotNone(c)
        self.assertIn("Reunião com o time", c.motivo)
        self.assertIn("posso marcar depois", c.alternativa)

    def test_longe_do_compromisso_nao_ha_conflito(self):
        agora = time.time()
        eventos = [{"inicio": agora + 3600, "titulo": "Reunião"}]
        self.assertIsNone(conflito_de_horario(agora + 3600 * 5, eventos))

    def test_agenda_vazia_nao_inventa_conflito(self):
        self.assertIsNone(conflito_de_horario(time.time(), []))
        self.assertIsNone(conflito_de_horario(time.time(), None))


class Recurso(unittest.TestCase):
    def test_camera_desligada_e_conflito_com_caminho(self):
        c = conflito_de_recurso("camera", {"camera": {"ativa": False}})
        self.assertIn("câmera está desligada", c.motivo)
        self.assertIn("ligue a câmera", c.alternativa)

    def test_camera_ligada_nao_e_conflito(self):
        self.assertIsNone(conflito_de_recurso("camera", {"camera": {"ativa": True}}))

    def test_servidor_fora_aponta_o_botao(self):
        c = conflito_de_recurso("servidor", {"conexao": {"servidor": {"estado": "erro"}}})
        self.assertIn("não está respondendo", c.motivo)
        self.assertIn("Religar", c.alternativa)

    def test_recurso_desconhecido_nao_inventa(self):
        self.assertIsNone(conflito_de_recurso("teletransporte", {}))


class PelaVoz(unittest.TestCase):
    """A discordância chega na fala, com a alternativa junto."""

    def setUp(self):
        import tempfile
        from types import SimpleNamespace
        from hud_runtime.comandos import Comandos
        from hud_runtime.pecas import Pecas
        from hud_runtime.projetos import Projetos
        from hud_runtime.secretario import Secretario
        self.pasta = Path(tempfile.mkdtemp())
        self.agora = time.time()
        self.tel = {"agenda": {"status": "medido",
                               "eventos": [{"inicio": self.agora + 3600, "titulo": "Reunião com o time"}]}}
        rt = SimpleNamespace(
            prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}),
            estado=SimpleNamespace(atualizar=lambda *a, **k: None, registrar=lambda *a, **k: None,
                                   telemetria=self.tel),
            pecas=Pecas(self.pasta / "p.json", pasta=self.pasta),
            projetos=Projetos(self.pasta / "j.json"),
            secretario=Secretario(pasta=self.pasta),
            ultimo_projeto=None, selecao=None)
        self.c = Comandos(rt, lambda pagina: None)
        self.c.mostrar_modelo = lambda caminho: None

    def dizer(self, frase):
        achado = self.c.interpretar(frase)
        self.assertIsNotNone(achado, frase)
        return self.c.executar(achado[0], achado[1], frase)

    def test_alteracao_impossivel_traz_o_maximo_que_cabe(self):
        self.dizer("Jarvis, projete uma caixa de 80 por 50 por 30 milímetros com parede de 2")
        r = self.dizer("Jarvis, deixe a parede com 20 milímetros")
        self.assertIn("não cabe", r)
        self.assertIn("14,9 mm", r)                       # o número que caberia
        self.assertEqual(self.c._pecas().ativa().parametros["parede"], 2)     # nada mudou

    def test_engrenagem_impossivel_ensina_o_minimo(self):
        r = self.dizer("Jarvis, projete uma engrenagem de 3 dentes com 40 mm")
        self.assertIn("não formam uma engrenagem", r)
        self.assertIn("6 dentes", r)

    def test_lembrete_em_cima_da_agenda_avisa_sem_recusar(self):
        r = self.dizer("Jarvis, me lembre de ligar para o Pedro daqui a uma hora")
        self.assertIn("Vou lembrar", r)                   # o lembrete FOI criado
        self.assertIn("Reunião com o time", r)            # e o choque foi dito
        self.assertIn("posso marcar depois", r)

    def test_sem_agenda_conectada_nao_inventa_choque(self):
        self.tel["agenda"] = {"status": "indisponivel"}
        r = self.dizer("Jarvis, me lembre de ligar para o Pedro daqui a uma hora")
        self.assertIn("Vou lembrar", r)
        self.assertNotIn("Atenção", r)


class Fala(unittest.TestCase):
    def test_a_frase_traz_motivo_alternativa_e_fonte(self):
        frase = falar([Conflito("a parede não cabe", "o máximo é 14,9 mm", "duas paredes")])
        self.assertIn("Não dá assim, Senhor", frase)
        self.assertIn("o máximo é 14,9 mm", frase)
        self.assertIn("(duas paredes)", frase)


if __name__ == "__main__":
    unittest.main()
