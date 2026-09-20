"""Montagem e vista explodida (F20).

O limite está no teste: só separo o que eu mesmo montei. De um STL pronto ou de
um objeto visto pela câmera, o Jarvis diz que não sabe o que tem dentro.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.cad import volume_mm3 as volume_da_malha  # noqa: E402
from hud_runtime.montagem import (  # noqa: E402
    Componente,
    Montagem,
    caixa_com_tampa,
    falar_componentes,
    falar_explosao,
    malha,
    recusa_de_explosao,
    volume_mm3,
)


class Montar(unittest.TestCase):
    def setUp(self):
        self.m = caixa_com_tampa(80, 50, 30, parede=2, tampa=2)

    def test_a_caixa_com_tampa_tem_duas_pecas_conhecidas(self):
        self.assertEqual([c.nome for c in self.m.componentes], ["corpo", "tampa"])
        self.assertEqual(self.m.componentes[1].deslocamento, (0.0, 0.0, 30))
        self.assertEqual(self.m.achar("tampa").tipo, "caixa")
        self.assertIsNone(self.m.achar("motor"))

    def test_a_malha_junta_as_duas_pecas(self):
        tris = malha(self.m)
        self.assertGreater(len(tris), 12)
        # a tampa esta ACIMA do corpo: o ponto mais alto passa dos 30 mm
        alto = max(z for tri in tris for (_, _, z) in tri)
        self.assertGreater(alto, 30)

    def test_vista_explodida_afasta_as_pecas_sem_mudar_o_tamanho(self):
        fechada = malha(self.m)
        aberta = malha(self.m, explodir=1.0)
        self.assertEqual(len(fechada), len(aberta))                  # as mesmas peças
        alto_fechada = max(z for tri in fechada for (_, _, z) in tri)
        alto_aberta = max(z for tri in aberta for (_, _, z) in tri)
        self.assertGreater(alto_aberta, alto_fechada + 10)           # separadas de verdade
        # e o volume de material não muda por separar
        self.assertAlmostEqual(abs(volume_da_malha(fechada)), abs(volume_da_malha(aberta)), places=3)

    def test_volume_soma_os_componentes(self):
        v = volume_mm3(self.m)
        self.assertGreater(v, 0)
        so_corpo = Montagem(nome="x", componentes=[self.m.componentes[0]])
        self.assertGreater(v, volume_mm3(so_corpo))

    def test_montagem_livre_com_componentes_do_senhor(self):
        m = Montagem(nome="suporte", componentes=[
            Componente("base", "caixa", {"c": 60, "l": 60, "a": 5, "parede": 0}),
            Componente("pino", "cilindro", {"diametro": 8, "altura": 20}, deslocamento=(0, 0, 5)),
        ])
        self.assertEqual(len(malha(m)) > 0, True)
        self.assertIn("base (caixa:", falar_componentes(m))
        self.assertIn("pino (cilindro:", falar_componentes(m))


class OsLimites(unittest.TestCase):
    def test_nao_invento_o_que_tem_dentro_do_que_nao_montei(self):
        frase = recusa_de_explosao("essa impressora")
        self.assertIn("Não sei as peças", frase)
        self.assertIn("não invento", frase)

    def test_a_fala_da_explosao_diz_de_onde_vieram_as_pecas(self):
        frase = falar_explosao(caixa_com_tampa(80, 50, 30))
        self.assertIn("2 peças", frase)
        self.assertIn("que eu mesmo montei", frase)

    def test_montagem_sem_componentes_e_dita_como_vazia(self):
        self.assertIn("não tem componentes", falar_componentes(Montagem(nome="vazia")))


class PelaVoz(unittest.TestCase):
    def setUp(self):
        import tempfile
        from types import SimpleNamespace
        from hud_runtime.comandos import Comandos
        from hud_runtime.pecas import Pecas
        from hud_runtime.projetos import Projetos
        self.pasta = Path(tempfile.mkdtemp())
        self.acervo = Pecas(self.pasta / "p.json", pasta=self.pasta)
        rt = SimpleNamespace(
            prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}),
            estado=SimpleNamespace(atualizar=lambda *a, **k: None, registrar=lambda *a, **k: None,
                                   telemetria={}),
            pecas=self.acervo, projetos=Projetos(self.pasta / "j.json"),
            ultimo_projeto=None, selecao=None)
        self.c = Comandos(rt, lambda pagina: None)
        self.mostrados = []
        self.c.mostrar_modelo = self.mostrados.append

    def dizer(self, frase):
        achado = self.c.interpretar(frase)
        self.assertIsNotNone(achado, frase)
        return achado[0], self.c.executar(achado[0], achado[1], frase)

    def test_montar_listar_explodir_e_alterar(self):
        nome, r = self.dizer("Jarvis, monte uma caixa com tampa de 80 por 50 por 30 milímetros")
        self.assertEqual(nome, "montagem_criar")
        self.assertIn("Versão 1", r)
        self.assertIn("2 peças", r)

        nome, r = self.dizer("Jarvis, quais peças tem isso?")
        self.assertEqual(nome, "montagem_pecas")
        self.assertIn("corpo", r)
        self.assertIn("tampa", r)

        nome, r = self.dizer("Jarvis, mostre a vista explodida")
        self.assertEqual(nome, "montagem_explodir")
        self.assertIn("Separei as 2 peças", r)
        self.assertTrue(str(self.mostrados[-1]).endswith("_explodida.stl"))
        self.assertTrue(Path(self.mostrados[-1]).is_file())

        # a montagem inteira aceita edição como qualquer peça
        nome, r = self.dizer("Jarvis, aumente a largura em 4 milímetros")
        self.assertIn("largura de 50 para 54", r)
        self.assertEqual(self.acervo.ativa().versao, 1)
        self.dizer("Jarvis, confirme a alteração da peça")
        self.assertEqual(self.acervo.ativa().versao, 2)

    def test_explodir_o_que_nao_e_montagem_e_recusado(self):
        self.dizer("Jarvis, projete um cilindro de 20 por 40")
        _, r = self.dizer("Jarvis, mostre a vista explodida")
        self.assertIn("Não sei as peças", r)
        self.assertIn("não invento", r)

    def test_tampa_maior_que_a_caixa_e_discordancia(self):
        from hud_runtime.pecas import validar
        erros, _ = validar("caixa_com_tampa", {"c": 80, "l": 50, "a": 5, "parede": 2, "tampa": 9})
        self.assertTrue(any("mais alta que a própria caixa" in e for e in erros), erros)


if __name__ == "__main__":
    unittest.main()
