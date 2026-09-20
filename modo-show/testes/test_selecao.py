"""Uma autoridade só de seleção (§10; cenário T18).

Mouse, teclado, voz e (um dia) gesto apontam o MESMO alvo. Gesto está
indisponível de verdade nesta máquina, e isso é dito -- não simulado.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.selecao import (  # noqa: E402
    ENTRADAS,
    MOTIVO_GESTO,
    Selecionador,
    disponivel,
    entradas,
    falar_selecao,
)


class EstadoDasEntradas(unittest.TestCase):
    def test_gesto_e_toque_sao_declarados_indisponiveis(self):
        e = entradas()
        self.assertEqual(e["mouse"], "disponivel")
        self.assertEqual(e["teclado"], "disponivel")
        self.assertEqual(e["voz"], "disponivel")
        self.assertTrue(e["gesto"].startswith("indisponivel"))
        self.assertIn("MediaPipe", e["gesto"])              # diz POR QUE, com data
        self.assertTrue(e["toque"].startswith("indisponivel"))
        self.assertFalse(disponivel("gesto"))
        self.assertTrue(disponivel("mouse"))

    def test_gesto_nunca_e_chamado_de_toque(self):
        fonte = (RAIZ / "hud_runtime" / "selecao.py").read_text(encoding="utf-8").lower()
        # nenhuma linha trata gesto e toque como a mesma coisa
        self.assertNotIn('"gesto": "toque"', fonte)
        self.assertNotIn("gesto = toque", fonte)
        self.assertIn("gesto no ar e toque na superfície são coisas diferentes", fonte)


class MesmoAlvo(unittest.TestCase):
    def setUp(self):
        self.cartoes = []
        self.s = Selecionador(publicar=self.cartoes.append)

    def test_T18_mouse_e_voz_selecionam_o_mesmo_elemento(self):
        pelo_mouse = self.s.selecionar("peca", "caixa", "caixa do Arduino", por="mouse")
        self.assertEqual(self.s.atual().id, "caixa")

        por_voz = self.s.selecionar("peca", "caixa", "caixa do Arduino", por="voz")
        self.assertEqual(por_voz.id, pelo_mouse.id)         # mesmo alvo, entrada diferente
        self.assertEqual(self.s.atual().por, "voz")
        self.assertEqual(len(self.s.historico()), 2)

    def test_gesto_sem_rastreador_da_erro_honesto_e_nao_seleciona(self):
        self.s.selecionar("peca", "caixa", por="mouse")
        with self.assertRaises(RuntimeError) as e:
            self.s.selecionar("peca", "engrenagem", por="gesto")
        self.assertIn(MOTIVO_GESTO.split(";")[0], str(e.exception))
        self.assertEqual(self.s.atual().id, "caixa")        # a selecao do mouse continua valendo

    def test_entrada_desconhecida_e_recusada(self):
        with self.assertRaises(ValueError):
            self.s.selecionar("peca", "caixa", por="telepatia")
        self.assertIn("gesto", ENTRADAS)

    def test_a_tela_recebe_o_mesmo_cartao(self):
        self.s.selecionar("noticia", "2", "segunda manchete", por="mouse")
        cartao = self.cartoes[-1]
        self.assertEqual(cartao["alvo"]["id"], "2")
        self.assertEqual(cartao["alvo"]["por"], "mouse")
        self.assertTrue(cartao["entradas"]["gesto"].startswith("indisponivel"))

    def test_selecao_velha_nao_vale_como_isso(self):
        alvo = self.s.selecionar("peca", "caixa", por="mouse")
        alvo.em -= 400                                       # cinco minutos atrás
        self.assertIsNone(self.s.atual())
        self.assertIsNotNone(self.s.ultimo_do_tipo("peca"))  # mas o histórico lembra

    def test_limpar_e_falar(self):
        self.assertIn("Nada selecionado", falar_selecao(None))
        a = self.s.selecionar("componente", "tampa", "tampa da caixa", por="mouse")
        self.assertIn("pelo mouse", falar_selecao(a))
        self.assertIn("tampa da caixa", falar_selecao(a))
        self.s.limpar()
        self.assertIsNone(self.s.atual())


if __name__ == "__main__":
    unittest.main()
