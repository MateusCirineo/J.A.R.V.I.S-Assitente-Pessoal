"""Manuais e documentos com evidência e versão (§7, F25; cenário T20).

O que precisa valer: a resposta vem do trecho certo COM a referência, "qual é a
fonte?" devolve a evidência usada, e um manual atualizado não deixa a versão
antiga responder calada.
"""

import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.conhecimento import (  # noqa: E402
    Conhecimento,
    falar_fontes,
    falar_indexado,
    falar_lista,
    palavras,
    partir,
)

MANUAL_V1 = """Manual da impressora Epson L3250.

Capítulo 1. Instalação
Retire a fita de proteção e ligue o cabo de força na tomada.

Capítulo 2. Tinta
Para trocar a tinta, abra a tampa do tanque, encaixe o frasco no bico e espere encher.
Use somente tinta original 664. Não force o frasco.

Capítulo 3. Papel
A bandeja aceita até 100 folhas de papel comum A4.

Capítulo 4. Erros
O erro 0x97 indica falha na placa lógica e exige assistência técnica.
"""

MANUAL_V2 = MANUAL_V1.replace(
    "Use somente tinta original 664. Não force o frasco.",
    "Use somente tinta original 673. A 664 foi descontinuada e entope o bico.")


def escrever(pasta: Path, nome: str, texto: str) -> Path:
    p = pasta / nome
    p.write_text(texto, encoding="utf-8")
    return p


class Partir(unittest.TestCase):
    def test_pedacos_com_sobreposicao_e_sem_perder_texto(self):
        texto = ". ".join(f"frase numero {i} com algum conteudo" for i in range(80))
        pedacos = partir(texto, tamanho=300, passo=200)
        self.assertGreater(len(pedacos), 3)
        self.assertTrue(all(p.strip() for _, p in pedacos))
        # nada se perde: a última posição alcança o fim do texto
        self.assertGreaterEqual(pedacos[-1][0] + len(pedacos[-1][1]), len(texto) - 5)

    def test_palavras_ignora_as_vazias(self):
        self.assertEqual(palavras("como eu faço para trocar a tinta?"), ["faco", "trocar", "tinta"])


class BuscarComReferencia(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.c = Conhecimento(self.pasta / "hud-conhecimento.json")
        self.arq = escrever(self.pasta, "manual-epson.txt", MANUAL_V1)
        self.doc = self.c.indexar(self.arq, assunto="impressora")

    def test_indexar_guarda_trechos_e_versao(self):
        self.assertGreaterEqual(len(self.doc.trechos), 1)     # manual curto cabe num trecho só
        self.assertEqual(len(self.doc.versao), 12)
        self.assertIn("Li manual-epson.txt", falar_indexado(self.doc))

    def test_documento_longo_nao_inventa_pagina_sem_offsets(self):
        longo = "\n".join(f"Seção {i}. Procedimento número {i} do equipamento." for i in range(200))
        doc = self.c.indexar(escrever(self.pasta, "longo.txt", longo), assunto="equipamento",
                             texto=longo, paginas=10)
        self.assertGreater(len(doc.trechos), 5)
        self.assertTrue(all(t.pagina is None for t in doc.trechos))

    def test_acha_o_trecho_certo(self):
        achados = self.c.buscar("como trocar a tinta?")
        self.assertTrue(achados)
        self.assertIn("trocar a tinta", achados[0].trecho.texto)
        self.assertIn("manual-epson.txt", achados[0].citar())

    def test_pergunta_sem_resposta_no_documento_nao_inventa(self):
        # o manual nao fala de wi-fi: a busca nao pode devolver trecho relevante
        achados = self.c.buscar("qual a senha do wi-fi do escritório?")
        for a in achados:
            self.assertNotIn("senha", a.trecho.texto.lower())

    def test_prompt_leva_trecho_e_referencia(self):
        texto, achados = self.c.para_prompt("como trocar a tinta?")
        self.assertIn("Responda SÓ com o que está escrito aqui", texto)
        self.assertIn("manual-epson.txt", texto)
        self.assertIn("frasco no bico", texto)
        self.assertTrue(achados)

    def test_qual_e_a_fonte_devolve_a_evidencia_usada(self):
        self.c.buscar("como trocar a tinta?")
        frase = falar_fontes(self.c.ultimos)
        self.assertIn("manual-epson.txt", frase)
        self.assertIn("versão de", frase)


class VersaoDoManual(unittest.TestCase):
    """T20. Manual atualizado não deixa a resposta usar a versão antiga."""

    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.c = Conhecimento(self.pasta / "hud-conhecimento.json")
        self.arq = escrever(self.pasta, "manual-epson.txt", MANUAL_V1)
        self.v1 = self.c.indexar(self.arq, assunto="impressora")

    def test_T20_versao_nova_aposenta_a_antiga(self):
        self.assertIn("664", self.c.buscar("qual tinta usar?")[0].trecho.texto)

        time.sleep(0.01)
        escrever(self.pasta, "manual-epson.txt", MANUAL_V2)
        v2 = self.c.indexar(self.arq, assunto="impressora")

        self.assertNotEqual(v2.versao, self.v1.versao)
        self.assertTrue(self.c._docs[self.v1.id].obsoleto)       # a antiga saiu de cena
        self.assertFalse(v2.obsoleto)
        achados = self.c.buscar("qual tinta usar?")
        textos = " ".join(a.trecho.texto for a in achados)
        self.assertIn("673", textos)
        self.assertIn("descontinuada", textos)
        self.assertNotIn("Use somente tinta original 664", textos)   # a velha nao responde mais

    def test_reindexar_o_mesmo_conteudo_nao_cria_versao(self):
        de_novo = self.c.indexar(self.arq, assunto="impressora")
        self.assertEqual(de_novo.id, self.v1.id)
        self.assertEqual(len(self.c.atuais()), 1)

    def test_arquivo_mudou_no_disco_e_avisado(self):
        escrever(self.pasta, "manual-epson.txt", MANUAL_V2)          # mudou, mas NAO reindexei
        self.assertTrue(self.c.atuais()[0].mudou_no_disco())
        texto, _ = self.c.para_prompt("qual tinta usar?")
        self.assertIn("foi alterado depois que eu indexei", texto)
        self.assertIn("vale reindexar", texto)
        self.assertNotIn("Use somente tinta original 664", texto)
        self.assertEqual(self.c.ultimos, [])
        self.assertIn("mudou no disco", falar_lista(self.c.todos()))

    def test_esquecer_alcanca_todas_as_versoes(self):
        escrever(self.pasta, "manual-epson.txt", MANUAL_V2)
        self.c.indexar(self.arq)
        self.assertEqual(len(self.c.todos()), 2)
        self.assertEqual(self.c.esquecer_arquivo(self.arq), 2)       # inclusive a obsoleta
        self.assertEqual(self.c.todos(), [])


class VariosDocumentos(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.c = Conhecimento(self.pasta / "hud-conhecimento.json")
        self.c.indexar(escrever(self.pasta, "manual-epson.txt", MANUAL_V1), assunto="impressora")
        self.c.indexar(escrever(self.pasta, "notas-caixa.txt",
                                "Projeto da caixa do Arduino. A parede tem 2 mm e o furo do cabo "
                                "fica no lado direito, a 12 mm da base."), assunto="caixa")

    def test_a_pergunta_escolhe_o_documento(self):
        self.assertIn("manual-epson", self.c.buscar("tinta original")[0].documento.nome)
        self.assertIn("notas-caixa", self.c.buscar("furo do cabo da caixa")[0].documento.nome)

    def test_buscar_dentro_de_um_documento_so(self):
        caixa = self.c.achar_documento("caixa")
        achados = self.c.buscar("parede", documento=caixa)
        self.assertTrue(achados)
        self.assertTrue(all(a.documento.id == caixa.id for a in achados))

    def test_lista_e_persistencia(self):
        self.assertIn("2 documentos indexados", falar_lista(self.c.todos()))
        outro = Conhecimento(self.c._arq)
        self.assertEqual(len(outro.atuais()), 2)
        self.assertTrue(outro.buscar("tinta"))


class PelaVoz(unittest.TestCase):
    """Do "leia o manual" até a resposta com fonte, tudo em pasta isolada."""

    def setUp(self):
        from types import SimpleNamespace
        from unittest import mock
        from hud_runtime.comandos import Comandos
        self.pasta = Path(tempfile.mkdtemp())
        self.arq = escrever(self.pasta, "manual-epson.txt", MANUAL_V1)
        self.con = Conhecimento(self.pasta / "hud-conhecimento.json")
        self.cartoes = []
        rt = SimpleNamespace(
            prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}),
            estado=SimpleNamespace(atualizar=lambda *a, **k: None, registrar=lambda *a, **k: None,
                                   telemetria={}),
            conhecimento=self.con)
        self.c = Comandos(rt, lambda pagina: None)
        self.c._contexto = self.cartoes.append
        self._achar = mock.patch("hud_runtime.documentos.achar", return_value=self.arq)
        self._achar.start()
        self.addCleanup(self._achar.stop)

    def dizer(self, frase):
        achado = self.c.interpretar(frase)
        self.assertIsNotNone(achado, f"nenhuma regra entendeu: {frase}")
        return achado[0], self.c.executar(achado[0], achado[1], frase)

    def test_ler_perguntar_e_citar_a_fonte(self):
        nome, r = self.dizer("Jarvis, leia o manual da impressora")
        self.assertEqual(nome, "doc_indexar")
        self.assertIn("Li manual-epson.txt", r)

        nome, r = self.dizer("Jarvis, o que o manual diz sobre trocar a tinta?")
        self.assertEqual(nome, "doc_perguntar")
        self.assertIn("Segundo manual-epson.txt", r)
        self.assertIn("frasco no bico", r)
        self.assertTrue(self.cartoes and self.cartoes[-1]["tipo"] == "documento")

        nome, r = self.dizer("Jarvis, qual é a fonte?")
        self.assertEqual(nome, "doc_fonte")
        self.assertIn("manual-epson.txt", r)

    def test_o_que_nao_esta_no_manual_nao_e_inventado(self):
        self.dizer("Jarvis, leia o manual da impressora")
        _, r = self.dizer("Jarvis, o que o manual diz sobre a senha do wi-fi?")
        self.assertIn("não está escrito", r)
        self.assertIn("Não vou inventar", r)

    def test_sem_documento_nenhum_ele_diz_isso(self):
        _, r = self.dizer("Jarvis, o que o manual diz sobre tinta?")
        self.assertIn("Ainda não li nenhum documento", r)

    def test_o_trecho_vai_ao_modelo_junto_da_pergunta(self):
        self.dizer("Jarvis, leia o manual da impressora")
        contexto = self.c.contexto_para_modelo("quantas folhas cabem na bandeja?")
        self.assertIn("Responda SÓ com o que está escrito aqui", contexto)
        self.assertIn("100 folhas", contexto)
        self.assertIn("manual-epson.txt", contexto)


if __name__ == "__main__":
    unittest.main()
