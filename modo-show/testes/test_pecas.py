"""Peças com parâmetros e versões (§12 do prompt mestre; cenários T25 e T27).

O que precisa ser verdade: alterar UMA dimensão muda só ela, a versão anterior
continua salva, o volume dito foi medido na malha gerada, e salvar um STL não
vira "pronto para fabricação".
"""

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.cad import volume_mm3  # noqa: E402
from hud_runtime.engenharia import gerar_peca  # noqa: E402
from hud_runtime.pecas import (  # noqa: E402
    Pecas,
    descrever,
    dimensao_citada,
    dimensoes_do_tipo,
    falar_versao,
    falar_versoes,
    validar,
)


def nova() -> Pecas:
    pasta = Path(tempfile.mkdtemp())
    return Pecas(pasta / "hud-pecas.json", pasta=pasta)


class Criar(unittest.TestCase):
    def test_nasce_na_versao_1_com_arquivo_e_volume_medido(self):
        p, avisos = nova().criar("caixa", {"c": 80, "l": 50, "a": 30, "parede": 2}, nome="caixa do Arduino")
        v = p.atual()
        self.assertEqual((p.versao, v.numero), (1, 1))
        self.assertTrue(Path(v.arquivo).is_file())
        self.assertGreater(v.triangulos, 0)
        # o volume dito TEM de bater com a malha, nao ser uma conta de guardanapo
        tris, *_ = gerar_peca("caixa", {"c": 80, "l": 50, "a": 30, "parede": 2})
        self.assertAlmostEqual(v.volume_mm3, abs(volume_mm3(tris)), places=3)
        self.assertEqual(avisos, [])

    def test_valores_impossiveis_nao_viram_peca(self):
        pc = nova()
        with self.assertRaises(ValueError):
            pc.criar("caixa", {"c": 80, "l": 50, "a": 30, "parede": 40})     # parede nao cabe
        with self.assertRaises(ValueError):
            pc.criar("tubo", {"externo": 10, "interno": 20, "altura": 5})    # furo maior que a peca
        with self.assertRaises(ValueError):
            pc.criar("caixa", {"c": -5, "l": 50, "a": 30, "parede": 0})
        self.assertEqual(pc.todas(), [])

    def test_parede_fina_avisa_mas_nao_impede(self):
        p, avisos = nova().criar("caixa", {"c": 40, "l": 40, "a": 20, "parede": 0.4})
        self.assertEqual(p.versao, 1)
        self.assertTrue(any("fina" in a for a in avisos), avisos)

    def test_peca_grande_demais_avisa_da_mesa(self):
        _, avisos = nova().criar("cilindro", {"diametro": 500, "altura": 10})
        self.assertTrue(any("não cabe na mesa" in a for a in avisos), avisos)


class Alterar(unittest.TestCase):
    def setUp(self):
        self.pc = nova()
        self.p, _ = self.pc.criar("caixa", {"c": 80, "l": 50, "a": 30, "parede": 2}, nome="caixa")

    def test_muda_so_o_que_foi_pedido_e_guarda_a_anterior(self):
        antes = dict(self.p.parametros)
        arquivo_v1 = self.p.atual().arquivo
        v2, avisos = self.pc.alterar(self.p, "l", delta=2)

        self.assertEqual(self.p.parametros["l"], 52)
        self.assertEqual({k: v for k, v in self.p.parametros.items() if k != "l"},
                         {k: v for k, v in antes.items() if k != "l"})     # o resto intacto
        self.assertEqual(v2.numero, 2)
        self.assertEqual(self.p.versoes[0].parametros["l"], 50)            # a v1 guarda o valor antigo
        self.assertTrue(Path(arquivo_v1).is_file())                        # o arquivo v1 nao foi apagado
        self.assertNotEqual(v2.arquivo, arquivo_v1)
        self.assertIn("largura de 50 para 52", v2.motivo)

    def test_alteracao_impossivel_nao_estraga_a_peca(self):
        with self.assertRaises(ValueError):
            self.pc.alterar(self.p, "parede", valor=40)
        self.assertEqual(self.p.parametros["parede"], 2)                   # nada mudou
        self.assertEqual(self.p.versao, 1)

    def test_dimensao_que_a_peca_nao_tem(self):
        with self.assertRaises(KeyError):
            self.pc.alterar(self.p, "dentes", valor=20)

    def test_voltar_para_uma_versao_antiga(self):
        self.pc.alterar(self.p, "l", delta=2)
        self.pc.alterar(self.p, "a", valor=45)
        v4 = self.pc.reverter(self.p, 1)
        self.assertEqual(v4.numero, 4)                                     # volta criando versao nova
        self.assertEqual(self.p.parametros, {"c": 80, "l": 50, "a": 30, "parede": 2})
        self.assertEqual(len(self.p.versoes), 4)                           # nada foi apagado
        self.assertIsNone(self.pc.reverter(self.p, 99))

    def test_o_volume_muda_junto_com_a_peca(self):
        v1 = self.p.atual().volume_mm3
        v2, _ = self.pc.alterar(self.p, "a", valor=60)
        self.assertGreater(v2.volume_mm3, v1)

    def test_sobrevive_ao_reinicio(self):
        self.pc.alterar(self.p, "l", delta=2)
        outra = Pecas(self.pc._arq, pasta=self.pc.pasta())
        p2 = outra.ativa()
        self.assertEqual(p2.nome, "caixa")
        self.assertEqual(p2.versao, 2)
        self.assertEqual(p2.parametros["l"], 52)
        self.assertEqual(p2.versoes[0].parametros["l"], 50)


class Falar(unittest.TestCase):
    def test_qual_dimensao_o_senhor_citou(self):
        self.assertEqual(dimensao_citada("caixa", "aumente a largura em 2 mm"), "l")
        self.assertEqual(dimensao_citada("caixa", "deixe a parede mais grossa"), "parede")
        self.assertEqual(dimensao_citada("tubo", "aumente o diâmetro interno"), "interno")
        self.assertEqual(dimensao_citada("tubo", "aumente o diâmetro externo"), "externo")
        self.assertIsNone(dimensao_citada("caixa", "aumente isso"))        # ambiguo: tem de perguntar

    def test_lista_de_dimensoes_para_perguntar(self):
        self.assertEqual(sorted(dimensoes_do_tipo("caixa")),
                         sorted(["comprimento", "largura", "altura", "parede"]))

    def test_a_fala_diz_o_que_mediu_e_o_que_nao_conferiu(self):
        pc = nova()
        p, _ = pc.criar("cilindro", {"diametro": 20, "altura": 40}, nome="pino")
        frase = falar_versao(p, p.atual())
        self.assertIn("Medi na peça gerada", frase)
        self.assertIn("Não testei impressão", frase)
        v2, avisos = pc.alterar(p, "altura", valor=45)
        frase2 = falar_versao(p, v2, avisos)
        self.assertIn("A versão 1 continua salva", frase2)

    def test_descrever_e_listar_versoes(self):
        pc = nova()
        p, _ = pc.criar("caixa", {"c": 80, "l": 50, "a": 30, "parede": 0}, nome="bloco")
        self.assertIn("comprimento 80", descrever(p))
        pc.alterar(p, "c", valor=90)
        self.assertIn("versão 2", falar_versoes(p))

    def test_validar_aponta_o_problema_em_portugues(self):
        erros, _ = validar("engrenagem", {"dentes": 3, "externo": 40, "espessura": 5, "furo": 5})
        self.assertTrue(any("pelo menos 6 dentes" in e for e in erros), erros)


if __name__ == "__main__":
    unittest.main()
