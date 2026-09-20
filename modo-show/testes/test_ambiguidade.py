"""Perguntar quando há duas leituras possíveis (F04).

A regra: candidato claramente na frente, eu sigo; empate, eu pergunto citando os
dois e **não faço nada** até a resposta.
"""

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.ambiguidade import (  # noqa: E402
    Candidato,
    de_objetos,
    escolher,
    perguntar,
    resolver,
)


def cands(*rotulos: str) -> list[Candidato]:
    return [Candidato(id=str(i), rotulo=r, tipo="documento") for i, r in enumerate(rotulos)]


class Escolher(unittest.TestCase):
    def test_um_candidato_so_e_escolhido(self):
        escolhido, empate = escolher("abra o manual", cands("manual da impressora"))
        self.assertEqual(escolhido.rotulo, "manual da impressora")
        self.assertEqual(empate, [])

    def test_o_mais_citado_ganha(self):
        escolhido, empate = escolher("abra o manual da impressora",
                                     cands("manual da impressora", "manual da furadeira"))
        self.assertEqual(escolhido.rotulo, "manual da impressora")
        self.assertEqual(empate, [])

    def test_empate_nao_escolhe_ninguem(self):
        escolhido, empate = escolher("abra o manual", cands("manual da impressora", "manual da furadeira"))
        self.assertIsNone(escolhido)
        self.assertEqual(len(empate), 2)

    def test_sem_pista_nenhuma_tudo_vira_opcao(self):
        escolhido, empate = escolher("apague isso", cands("caixa do Arduino", "luminária"))
        self.assertIsNone(escolhido)
        self.assertEqual(len(empate), 2)

    def test_lista_vazia(self):
        self.assertEqual(escolher("qualquer coisa", []), (None, []))


class Perguntar(unittest.TestCase):
    def test_a_pergunta_cita_as_opcoes(self):
        frase = perguntar(cands("manual da impressora", "manual da furadeira"), "manual")
        self.assertIn("Qual manual o senhor quer", frase)
        self.assertIn("manual da impressora ou manual da furadeira", frase)

    def test_muitas_opcoes_mostra_algumas_e_diz_quantas_faltam(self):
        frase = perguntar(cands("a", "b", "c", "d", "e", "f"))
        self.assertIn("(tenho mais 2)", frase)

    def test_resolver_devolve_pergunta_em_vez_de_escolher(self):
        escolhido, pergunta = resolver("esqueça a impressora",
                                       cands("impressora da mesa", "impressora da sala"), "impressora")
        self.assertIsNone(escolhido)
        self.assertIn("Qual impressora", pergunta)

        escolhido, pergunta = resolver("esqueça a impressora da sala",
                                       cands("impressora da mesa", "impressora da sala"), "impressora")
        self.assertEqual(escolhido.rotulo, "impressora da sala")
        self.assertEqual(pergunta, "")


class ComObjetosDeVerdade(unittest.TestCase):
    def test_dois_objetos_iguais_no_inventario_geram_pergunta(self):
        from hud_runtime.inventario import Inventario
        inv = Inventario(Path(tempfile.mkdtemp()) / "inv.json")
        inv.cadastrar("carregador da mochila", categoria="carregador")
        inv.cadastrar("carregador da mesa", categoria="carregador")
        candidatos = de_objetos(inv.parecidos("carregador"), lambda o: o.nome, "objeto")
        escolhido, pergunta = resolver("esqueça o carregador", candidatos, "carregador")
        self.assertIsNone(escolhido)
        self.assertIn("carregador da mochila", pergunta)
        self.assertIn("carregador da mesa", pergunta)

    def test_dois_documentos_do_mesmo_assunto_geram_pergunta(self):
        from hud_runtime.conhecimento import Conhecimento
        pasta = Path(tempfile.mkdtemp())
        con = Conhecimento(pasta / "c.json")
        for nome in ("manual-epson.txt", "manual-brother.txt"):
            arq = pasta / nome
            arq.write_text("Manual da impressora. Troque a tinta com cuidado.", encoding="utf-8")
            con.indexar(arq, assunto="impressora")
        candidatos = de_objetos(con.atuais(), lambda d: d.nome, "documento")
        escolhido, pergunta = resolver("abra o manual", candidatos, "manual")
        self.assertIsNone(escolhido)
        self.assertIn("manual-epson.txt", pergunta)
        self.assertIn("manual-brother.txt", pergunta)

        escolhido, pergunta = resolver("abra o manual-brother.txt", candidatos, "manual")
        self.assertEqual(escolhido.rotulo, "manual-brother.txt")


class PelaVoz(unittest.TestCase):
    """O comando pergunta em vez de apagar o objeto errado."""

    def setUp(self):
        from types import SimpleNamespace
        from hud_runtime.comandos import Comandos
        from hud_runtime.conhecimento import Conhecimento
        from hud_runtime.inventario import Inventario
        self.pasta = Path(tempfile.mkdtemp())
        self.inv = Inventario(self.pasta / "inv.json")
        self.con = Conhecimento(self.pasta / "con.json")
        rt = SimpleNamespace(
            prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}),
            estado=SimpleNamespace(atualizar=lambda *a, **k: None, registrar=lambda *a, **k: None,
                                   telemetria={}),
            inventario=self.inv, conhecimento=self.con, visao_continua=None)
        self.c = Comandos(rt, lambda pagina: None)

    def dizer(self, frase):
        achado = self.c.interpretar(frase)
        self.assertIsNotNone(achado, frase)
        return achado[0], self.c.executar(achado[0], achado[1], frase)

    def test_dois_carregadores_o_jarvis_pergunta_antes_de_apagar(self):
        self.inv.cadastrar("carregador da mochila", categoria="carregador")
        self.inv.cadastrar("carregador da mesa", categoria="carregador")
        nome, r = self.dizer("Jarvis, esqueça o meu carregador")
        self.assertEqual(nome, "inv_esquecer")
        self.assertIn("Qual carregador", r)
        self.assertEqual(len(self.inv.todos()), 2)          # nada foi apagado

        nome, r = self.dizer("Jarvis, esqueça o meu carregador da mesa")
        self.assertIn("Tirei carregador da mesa", r)
        self.assertEqual([o.nome for o in self.inv.todos()], ["carregador da mochila"])

    def test_um_objeto_so_nao_gera_pergunta(self):
        self.inv.cadastrar("impressora da mesa", categoria="impressora")
        nome, r = self.dizer("Jarvis, esqueça a minha impressora")
        self.assertIn("Tirei impressora da mesa", r)


if __name__ == "__main__":
    unittest.main()
