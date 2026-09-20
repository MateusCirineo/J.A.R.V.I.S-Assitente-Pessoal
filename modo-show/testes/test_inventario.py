"""Inventário pessoal (§9; cenários T12 e T14).

Duas coisas que não podem dar errado: dois objetos iguais não podem virar a
mesma identidade pessoal, e "vi às 14h12" não pode virar "está lá agora".
"""

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.inventario import (  # noqa: E402
    MODELO,
    UNIDADE,
    Inventario,
    falar_lista,
    falar_objeto,
)


def novo() -> Inventario:
    return Inventario(Path(tempfile.mkdtemp()) / "hud-inventario.json")


class ModeloXUnidade(unittest.TestCase):
    def setUp(self):
        self.inv = novo()

    def test_T12_modelo_de_produto_e_unidade_sao_registros_diferentes(self):
        """T12. Cadastro distingue categoria, modelo e unidade física."""
        modelo = self.inv.modelo_de_produto("Epson L3250", fabricante="Epson", modelo="L3250",
                                            atributos={"tinta": "tanque"}, manual="epson-l3250.pdf")
        unidade = self.inv.cadastrar("a impressora da minha mesa", categoria="impressora",
                                     modelo_de=modelo.id, fabricante="Epson", modelo="L3250")
        self.assertTrue(modelo.e_modelo)
        self.assertFalse(unidade.e_modelo)
        self.assertEqual(unidade.categoria, "impressora")
        self.assertEqual(self.inv.do_modelo(modelo.id), [unidade])
        self.assertEqual(self.inv.obter(unidade.modelo_de).manual, "epson-l3250.pdf")

    def test_dois_objetos_iguais_sao_duas_unidades(self):
        modelo = self.inv.modelo_de_produto("Anker 65 W")
        a = self.inv.cadastrar("carregador da mochila", categoria="carregador", modelo_de=modelo.id)
        b = self.inv.cadastrar("carregador da mesa", categoria="carregador", modelo_de=modelo.id)
        self.assertNotEqual(a.id, b.id)                        # identidades diferentes
        self.assertEqual(len(self.inv.parecidos("carregador")), 2)
        self.assertEqual(len(self.inv.do_modelo(modelo.id)), 2)
        # e o mesmo modelo NAO vira dois registros de produto
        self.assertIs(self.inv.modelo_de_produto("Anker 65 W"), modelo)

    def test_achar_pelo_nome_e_pelo_apelido(self):
        o = self.inv.cadastrar("a impressora da minha mesa", categoria="impressora")
        self.inv.apelidar(o.id, "impressora")
        self.assertEqual(self.inv.achar("impressora").id, o.id)
        self.assertEqual(self.inv.achar("a impressora da minha mesa").id, o.id)
        self.assertIsNone(self.inv.achar("geladeira"))

    def test_confirmar_marca_o_que_veio_do_senhor(self):
        o = self.inv.cadastrar("carregador", categoria="carregador")
        self.inv.confirmar(o.id, "modelo", "Anker 65 W")
        self.assertEqual(o.modelo, "Anker 65 W")
        self.assertIn("modelo", o.confirmados)
        self.inv.corrigir(o.id, "modelo", "Anker 30 W")        # o Senhor corrigiu
        self.assertEqual(o.modelo, "Anker 30 W")
        self.assertEqual(o.confirmados.count("modelo"), 1)


class ObservacaoNaoEEstadoAtual(unittest.TestCase):
    def test_T14_ultima_observacao_nao_vira_esta_la(self):
        """T14. Observação antiga é apresentada como última observação."""
        inv = novo()
        o = inv.cadastrar("meu celular", categoria="celular")
        obs = inv.observar(o.id, onde="à esquerda da mesa", trilha="obj3")
        self.assertEqual(o.ultima().onde, "à esquerda da mesa")

        frase = falar_objeto(o, agora=obs.em + 7200)           # duas horas depois
        self.assertIn("vi por último", frase)
        self.assertIn("à esquerda da mesa", frase)
        self.assertIn("não sei se ainda está lá", frase)
        self.assertNotIn("está na mesa", frase)

    def test_sem_observacao_nao_inventa_lugar(self):
        inv = novo()
        o = inv.cadastrar("meu fone", categoria="fone")
        self.assertNotIn("vi por último", falar_objeto(o))

    def test_o_historico_de_observacoes_nao_cresce_sem_limite(self):
        inv = novo()
        o = inv.cadastrar("copo", categoria="copo")
        for _ in range(40):
            inv.observar(o.id, onde="no centro")
        self.assertEqual(len(o.observacoes), 30)


class Persistencia(unittest.TestCase):
    def test_sobrevive_ao_reinicio_e_apaga_quando_mandam(self):
        inv = novo()
        o = inv.cadastrar("a impressora da minha mesa", categoria="impressora", modelo="L3250")
        inv.observar(o.id, onde="no centro")

        outro = Inventario(inv._arq)
        achado = outro.achar("impressora")
        self.assertEqual(achado.modelo, "L3250")
        self.assertEqual(len(achado.observacoes), 1)
        self.assertTrue(outro.esquecer(achado.id))
        self.assertEqual(Inventario(inv._arq).todos(), [])

    def test_nenhuma_foto_por_padrao(self):
        inv = novo()
        o = inv.cadastrar("meu carregador")
        self.assertEqual(o.foto, "")                            # nada de imagem sem o Senhor pedir


class PelaVoz(unittest.TestCase):
    """Do pedido falado até o arquivo, com dados isolados."""

    def setUp(self):
        from types import SimpleNamespace
        from hud_runtime.comandos import Comandos
        self.inv = novo()
        rt = SimpleNamespace(
            prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}),
            estado=SimpleNamespace(atualizar=lambda *a, **k: None, registrar=lambda *a, **k: None,
                                   telemetria={}),
            inventario=self.inv, visao_continua=None)
        self.c = Comandos(rt, lambda pagina: None)

    def dizer(self, frase):
        achado = self.c.interpretar(frase)
        self.assertIsNotNone(achado, f"nenhuma regra entendeu: {frase}")
        return achado[0], self.c.executar(achado[0], achado[1], frase)

    def test_cadastrar_confirmar_consultar_e_esquecer(self):
        nome, r = self.dizer("Jarvis, cadastre esta impressora")
        self.assertEqual(nome, "inv_cadastrar")
        self.assertIn("Cadastrei", r)

        self.dizer("Jarvis, a marca da impressora é Epson")
        nome, r = self.dizer("Jarvis, o modelo da impressora é L3250")
        self.assertEqual(nome, "inv_definir")
        o = self.inv.achar("impressora")
        self.assertEqual((o.fabricante, o.modelo), ("Epson", "L3250"))
        self.assertIn("modelo", o.confirmados)

        nome, r = self.dizer("Jarvis, o que você sabe sobre a minha impressora?")
        self.assertIn("Epson", r)
        self.assertIn("o senhor confirmou", r)

        nome, r = self.dizer("Jarvis, esqueça a minha impressora")
        self.assertEqual(nome, "inv_esquecer")
        self.assertIsNone(self.inv.achar("impressora"))

    def test_cadastro_de_objeto_nao_rouba_cadastro_de_pessoa(self):
        # "cadastre o meu rosto" e de gente (id_*), nunca do inventario
        for frase, esperado in (("Jarvis, cadastre o meu rosto", "id_rosto_cadastrar"),
                                ("Jarvis, cadastre a minha voz", "id_voz_cadastrar"),
                                ("Jarvis, registre o rosto da Maria", "id_rosto_cadastrar"),
                                ("Jarvis, esqueça o meu rosto", "id_esquecer")):
            with self.subTest(frase=frase):
                self.assertEqual(self.c.interpretar(frase)[0], esperado)

    def test_consultar_o_que_nao_existe_diz_a_verdade(self):
        _, r = self.dizer("Jarvis, o que você sabe sobre o meu drone?")
        self.assertIn("Não tenho", r)
        self.assertIn("cadastre", r.lower())


class Falar(unittest.TestCase):
    def test_ficha_diz_o_que_foi_confirmado(self):
        inv = novo()
        o = inv.cadastrar("a impressora da minha mesa", categoria="impressora",
                          fabricante="Epson", modelo="L3250", manual="epson.pdf")
        self.assertIn("não confirmado por você", falar_objeto(o))
        inv.confirmar(o.id, "modelo", "L3250")
        frase = falar_objeto(o)
        self.assertIn("o senhor confirmou", frase)
        self.assertIn("tenho o manual", frase)

    def test_lista_vazia_ensina_o_comando(self):
        self.assertIn("cadastre esta impressora", falar_lista([]))


if __name__ == "__main__":
    unittest.main()
