"""Engenharia: contas de eletrica/fisica, materiais, pecas em STL e analise de dados."""

import math
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime import cad, comandos as cmd, engenharia as eng  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402


def assinado(tris):
    return sum((a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
               for a, b, c in tris)


class TestContas(unittest.TestCase):
    def test_eletrica_e_consumo(self):
        self.assertEqual(eng.eletrica("qual a corrente com 12 volts e 4 ohms"), "A corrente é de 3 ampères (3.000 miliampères).")
        self.assertEqual(eng.eletrica("qual a resistência para 5 volts e 20 miliamperes"), "A resistência é de 250 ohms.")
        self.assertEqual(eng.eletrica("qual a potência de doze volts e dois amperes"), "A potência é de 24 watts.")
        self.assertIn("82,5 por mês, uns 70,12 reais",
                      eng.consumo("quanto gasta um chuveiro de 5500 watts ligado 30 minutos por dia", tarifa=0.85))
        self.assertIn("diga: a tarifa de luz é", eng.consumo("quanto gasta um aparelho de 1500 watts ligado 2 horas por dia"))
        self.assertEqual(eng.tarifa_dita("a tarifa de luz é 0,85"), 0.85)

    def test_fisica(self):
        fala, gr = eng.fisica("lançamento a 20 metros por segundo com 45 graus")
        self.assertIn("alcance de 40,8 metros", fala)
        self.assertAlmostEqual(gr["series"][0]["pontos"][-1][0], 40.77, delta=0.05)          # cai no alcance
        self.assertIn("2,02 segundos", eng.fisica("quanto tempo leva para cair de 20 metros")[0])
        self.assertEqual(eng.fisica("energia cinética de 2 kg a 10 metros por segundo")[0], "A energia cinética é de 100 joules.")

    def test_materiais(self):
        self.assertIn("2,9 vezes mais leve", eng.material("compare alumínio e aço"))
        r = eng.material("compare aço inox e titânio")
        self.assertTrue(r.startswith("aço inox 304") and "titânio" in r, r)                  # "aco inox" nao vira "aco"
        self.assertIn("Pesam quase o mesmo", eng.material("compare aço e aço inox"))
        self.assertIn("2,7 quilos", eng.peso_de_peca("quanto pesa um cubo de alumínio de 10 cm"))
        self.assertIn("742,2 gramas", eng.peso_de_peca("quanto pesa uma esfera de chumbo de 5 cm"))


class TestPecas(unittest.TestCase):
    def test_volumes_exatos_e_faces_para_fora(self):
        casos = [(cad.caixa(10, 10, 10), 1000), (cad.caixa(50, 30, 20, 2), 50 * 30 * 20 - 46 * 26 * 18),
                 (cad.cilindro(20, 50), math.pi * 100 * 50), (cad.tubo(30, 26, 40), math.pi * (225 - 169) * 40),
                 (cad.esfera(30), 4 / 3 * math.pi * 15 ** 3), (cad.cone(20, 30), math.pi * 100 * 10)]
        for tris, esperado in casos:
            v = assinado(tris)
            self.assertGreater(v, 0)                                                        # normais para fora
            self.assertAlmostEqual(v / esperado, 1, delta=0.005)
        self.assertGreater(assinado(cad.engrenagem(20, 40, 8, 5)), 0)

    def test_engrenagem_evolvente(self):
        pts = cad.perfil_engrenagem(20, 40)
        raios = [math.hypot(x, y) for x, y in pts]
        self.assertAlmostEqual(max(raios), 20, delta=0.01)                                  # cabeca = diametro externo
        self.assertLess(min(raios), 18.2 - 1.8)                                             # pe abaixo do primitivo
        with self.assertRaises(ValueError):
            cad.engrenagem(4, 40, 8)

    def test_pedidos(self):
        self.assertEqual(eng.pedido_de_peca("projete uma engrenagem de 20 dentes com 40 mm"),
                         ("engrenagem", {"dentes": 20, "externo": 40.0, "espessura": 8.0, "furo": 5.0}))
        self.assertEqual(eng.pedido_de_peca("crie uma caixa organizadora de 10 por 8 por 5 cm")[1],
                         {"c": 100.0, "l": 80.0, "a": 50.0, "parede": 2.0})
        self.assertIn("Quantos dentes", eng.pedido_de_peca("projete uma engrenagem"))

    def test_stl_binario_valido(self):
        caminho = cad.salvar_stl(cad.caixa(10, 10, 10), Path(tempfile.mkdtemp()) / "c.stl")
        dados = caminho.read_bytes()
        n = struct.unpack("<I", dados[80:84])[0]
        self.assertEqual((n, len(dados)), (12, 84 + 12 * 50))


class TestComandos(unittest.TestCase):
    def setUp(self):
        self.prefs = validar({"nome_usuario": "Senhor"})
        self.pasta = Path(tempfile.mkdtemp())
        self.paginas = []
        self.rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: self.prefs, aplicar=lambda d: self.prefs.update(d)),
                                  estado=SimpleNamespace(atualizar=mock.Mock(), publicar=mock.Mock()),
                                  holograma_modelo=None, ultimo_projeto=None, porta=8765, _olhando=threading.Event())
        self.c = cmd.Comandos(self.rt, self.paginas.append)
        self.c._contexto = lambda cartao: None
        self.c._abrir_holograma = lambda: True

    def dizer(self, frase):
        nome, args = self.c.interpretar(frase)
        return self.c.executar(nome, args, frase)

    def test_projeta_salva_e_mostra_na_mesa(self):
        # a peca agora entra no acervo com versao (hud_runtime/pecas.py), entao a
        # fala diz a versao e o que foi MEDIDO -- sem perder a descricao da peca
        with mock.patch("hud_runtime.cad.pasta_projetos", return_value=self.pasta):
            r = self.dizer("Jarvis, projete uma engrenagem de 20 dentes com 40 mm")
        self.assertIn("engrenagem de 20 dentes, 40 milímetros de diâmetro", r)
        self.assertIn("Versão 1", r)
        self.assertIn("Medi na peça gerada", r)
        self.assertIn("gramas em PLA", r)
        self.assertIn("Não testei impressão", r)          # STL salvo nao e peca aprovada
        arquivos = list(self.pasta.glob("*.stl"))
        self.assertEqual(len(arquivos), 1)
        self.assertEqual(self.rt.holograma_modelo, arquivos[0])
        apresentados = [p for p in self.paginas if p.get("acao") == "holograma" and p.get("tipo") == "modelo"]
        self.assertEqual(len(apresentados), 1)
        self.assertEqual(apresentados[0]["apresentacao_id"], self.rt.apresentacao.atual()["id"])

    def test_a_peca_projetada_pode_ser_alterada_depois(self):
        # era a lacuna F21: gerava o STL e esquecia. Agora "aumente" tem alvo.
        with mock.patch("hud_runtime.cad.pasta_projetos", return_value=self.pasta):
            self.dizer("Jarvis, projete uma caixa de 80 por 50 por 30 milímetros")
            r = self.dizer("Jarvis, aumente a largura em 2 milímetros")
            self.assertIn("Prévia", r)
            self.assertEqual(self.c._pecas().ativa().versao, 1)
            r = self.dizer("Jarvis, confirme a alteração da peça")
        self.assertIn("largura de 50 para 52", r)
        self.assertIn("Versão 2", r)
        self.assertEqual(len(list(self.pasta.glob("*.stl"))), 3)  # v1, prévia e v2 preservadas

    def test_tarifa_e_consumo_em_reais(self):
        self.assertEqual(self.dizer("a tarifa de luz é 0,85"), "Anotado: 0,85 reais por quilowatt-hora.")
        self.assertIn("reais pela tarifa de 0,85", self.dizer("quanto gasta um chuveiro de 5500 watts ligado 30 minutos por dia"))

    def test_analise_de_planilha(self):
        csv = self.pasta / "gastos do mes.csv"
        csv.write_text("dia;valor;categoria\n1;10,50;mercado\n2;20;luz\n3;30;mercado\n4;40,5;agua\n", encoding="utf-8")
        with mock.patch("hud_runtime.documentos.achar", return_value=csv):
            r = self.dizer("analise a planilha de gastos")
        self.assertIn("gastos do mes: 4 linhas", r)
        self.assertIn("valor: soma 101", r)
        self.assertTrue(any(p.get("tipo") == "grafico" for p in self.paginas))

    def test_trajetoria_vai_para_a_mesa(self):
        r = self.dizer("qual o alcance de um lançamento a 20 metros por segundo com 45 graus?")
        self.assertIn("Desenhei a trajetória", r)


if __name__ == "__main__":
    unittest.main()
