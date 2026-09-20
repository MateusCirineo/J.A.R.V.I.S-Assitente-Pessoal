"""Correções do Senhor que ficam valendo (§17; cenário T32).

A linha que estes testes defendem: guardar um apelido é uma REGRA revisável, não
treinamento. E um apelido nunca pode virar permissão nova -- o destino tem de ser
um comando que já existe.
"""

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.comandos import interpretar  # noqa: E402
from hud_runtime.correcoes import (  # noqa: E402
    Correcoes,
    falar_lista,
    falar_registro,
)


def novo() -> Correcoes:
    return Correcoes(Path(tempfile.mkdtemp()) / "hud-correcoes.json")


class Apelidos(unittest.TestCase):
    def setUp(self):
        self.c = novo()

    def test_apelido_vira_regra_e_e_aplicado(self):
        c = self.c.registrar("modo oficina", "abra o VS Code", interpretar=interpretar)
        self.assertEqual(c.comando, "app")                  # conferido contra as regras reais
        # a fala deixa claro o que É: regra, não treinamento (§17)
        self.assertIn("É uma regra minha, não um modelo treinado", falar_registro(c))
        achada = self.c.aplicar("Jarvis, modo oficina")
        self.assertIsNotNone(achada)
        self.assertEqual(achada.faca, "abra o VS Code")
        self.assertEqual(self.c.listar()[0].usos, 1)

    def test_destino_que_nao_e_comando_e_recusado(self):
        with self.assertRaises(ValueError) as e:
            self.c.registrar("modo mágico", "faça mágica", interpretar=interpretar)
        self.assertIn("não é um comando que eu conheça", str(e.exception))
        self.assertEqual(self.c.listar(), [])

    def test_apelido_nao_amplia_permissao(self):
        # o destino resolve para um comando existente; nada aqui cria capacidade nova
        c = self.c.registrar("modo casa", "ligue a câmera", interpretar=interpretar)
        self.assertEqual(c.comando, "camera_ligar")
        self.assertEqual(interpretar(c.faca)[0], "camera_ligar")

    def test_frase_igual_ao_comando_e_recusada(self):
        with self.assertRaises(ValueError):
            self.c.registrar("ligue a câmera", "ligue a câmera", interpretar=interpretar)

    def test_apelido_novo_substitui_o_antigo(self):
        self.c.registrar("modo oficina", "abra o VS Code", interpretar=interpretar)
        self.c.registrar("modo oficina", "ligue a câmera", interpretar=interpretar)
        self.assertEqual(len(self.c.listar("apelido")), 1)
        self.assertEqual(self.c.aplicar("modo oficina").comando, "camera_ligar")

    def test_frase_parecida_mas_diferente_nao_dispara(self):
        self.c.registrar("modo oficina", "abra o VS Code", interpretar=interpretar)
        self.assertIsNone(self.c.aplicar("modo oficinas mecânicas do bairro"))
        self.assertIsNone(self.c.aplicar("que horas são?"))

    def test_apelido_nao_sequestra_comando_sobre_o_apelido(self):
        # "esqueça a correção modo oficina" e sobre a correcao, nao o apelido
        self.c.registrar("modo oficina", "abra o VS Code", interpretar=interpretar)
        self.assertIsNone(self.c.aplicar("esqueça a correção modo oficina"))
        self.assertIsNone(self.c.aplicar("quando eu disser modo oficina, ligue a câmera"))
        self.assertIsNotNone(self.c.aplicar("Jarvis, modo oficina"))       # com o chamado, vale


class InspecionarEApagar(unittest.TestCase):
    def test_listar_esquecer_e_limpar(self):
        c = novo()
        c.registrar("modo oficina", "abra o VS Code", interpretar=interpretar)
        c.registrar("modo foco", "ligue a câmera", interpretar=interpretar)
        self.assertIn("2 correções suas", falar_lista(c.listar()))
        self.assertTrue(c.esquecer("modo foco"))
        self.assertEqual(len(c.listar()), 1)
        self.assertFalse(c.esquecer("modo que não existe"))
        self.assertEqual(c.limpar(), 1)
        self.assertIn("Não guardei nenhuma correção", falar_lista(c.listar()))

    def test_sobrevive_ao_reinicio(self):
        c = novo()
        c.registrar("modo oficina", "abra o VS Code", interpretar=interpretar)
        outro = Correcoes(c._arq)
        self.assertEqual(outro.aplicar("modo oficina").comando, "app")


class NadaDeTreino(unittest.TestCase):
    def test_o_modulo_nao_treina_nem_ajusta_pesos(self):
        fonte = (RAIZ / "hud_runtime" / "correcoes.py").read_text(encoding="utf-8")
        for proibido in ("torch", "optim", "backward", "fine_tune", "lora", "train("):
            self.assertNotIn(proibido, fonte.lower())

    def test_pronuncia_e_guardada_separada_do_apelido(self):
        c = novo()
        c.registrar("jarvis", "járvis", tipo="pronuncia")
        self.assertEqual(c.pronuncias(), {"jarvis": "járvis"})
        self.assertEqual(c.listar("apelido"), [])
        self.assertIsNone(c.aplicar("jarvis"))               # pronúncia não vira comando


if __name__ == "__main__":
    unittest.main()
