"""Identificação fina com evidência (§8; cenários T08, T09, T10, T11).

A regra que estes testes defendem: o Jarvis pode dizer "provável", pode dizer
"confirmado por etiqueta", pode dizer "não sei" -- mas nunca pode inventar marca,
completar letra ilegível ou escolher um dos dois candidatos no par ou ímpar.
"""

import sys
import unittest
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.identificacao import (  # noqa: E402
    COMPATIVEL,
    CONFIRMADO,
    CONFLITANTE,
    NAO_DETERMINADO,
    PROVAVEL,
    Identificacao,
    Qualidade,
    avaliar_regiao,
    pistas_de_texto,
)


def imagem(lado=400, nitida=True, brilho=128):
    """Fixture: quadro sintético. É fixture, e está dito."""
    img = np.full((lado, lado, 3), brilho, np.uint8)
    if nitida:                                    # xadrez = muita borda = nitidez alta
        img[::8] = max(0, brilho - 90)
        img[:, ::8] = max(0, brilho - 90)
    return img


class AvaliarRegiao(unittest.TestCase):
    def test_imagem_boa_passa(self):
        q = avaliar_regiao(imagem())
        self.assertTrue(q.boa, q.problemas)

    def test_objeto_pequeno_demais_nao_da(self):
        q = avaliar_regiao(imagem(), (0.45, 0.45, 0.08, 0.08))
        self.assertIn("pequeno demais", " ".join(q.problemas))
        self.assertFalse(q.boa)

    def test_borrado_nao_da(self):
        q = avaliar_regiao(imagem(nitida=False))
        self.assertIn("tremida ou fora de foco", " ".join(q.problemas))

    def test_escuro_e_estourado(self):
        self.assertIn("escuro", " ".join(avaliar_regiao(imagem(brilho=10)).problemas))
        self.assertIn("estourado", " ".join(avaliar_regiao(imagem(brilho=250)).problemas))

    def test_objeto_cortado_pela_borda(self):
        q = avaliar_regiao(imagem(), (0.0, 0.2, 0.5, 0.5))
        self.assertTrue(q.cortado)
        self.assertIn("cortado pela borda", " ".join(q.problemas))


class PistasDeTexto(unittest.TestCase):
    def test_trecho_cortado_continua_cortado(self):
        p = pistas_de_texto("SAM… Galaxy S23")
        self.assertEqual(p["legivel"], "Galaxy S23")
        self.assertEqual(p["parcial"], "SAM…")
        self.assertNotIn("Samsung", p["legivel"] + p["parcial"])   # ninguem completa a palavra

    def test_texto_limpo_e_todo_legivel(self):
        self.assertEqual(pistas_de_texto("Epson L3250")["legivel"], "Epson L3250")


class ResponderComEvidencia(unittest.TestCase):
    def test_T08_objeto_ruim_na_imagem_nao_ganha_marca(self):
        """T08. Parcialmente visível: identificação limitada e pedido de evidência."""
        ident = Identificacao("um carro", avaliar_regiao(imagem(), (0.0, 0.3, 0.3, 0.3)))
        frase = ident.frase()
        self.assertIn("cortado pela borda", frase)
        self.assertIn("eu tento de novo", frase)
        for palavra in ("Honda", "Civic", "marca", "modelo"):
            self.assertNotIn(palavra, frase.replace("modelo", "", 0))
        self.assertIsNotNone(ident.falta())

    def test_T09_etiqueta_legivel_vira_confirmacao(self):
        """T09. Identificação legível é associada à referência, com evidência
        por atributo."""
        ident = Identificacao("uma impressora")
        ident.anotar("marca", "Epson", CONFIRMADO, "texto lido na etiqueta")
        ident.anotar("modelo", "L3250", CONFIRMADO, "texto lido na etiqueta")
        ident.anotar("capacidade", "tanque de tinta", COMPATIVEL, "manual no inventário")
        ident.evidencia("quadro da câmera às 14h12")
        ident.evidencia("manual Epson L3250 no inventário do Senhor")

        frase = ident.frase()
        self.assertIn("marca Epson, confirmado por texto lido na etiqueta", frase)
        self.assertIn("modelo L3250, confirmado", frase)
        self.assertIn("compatível com manual no inventário", frase)
        cartao = ident.cartao()
        self.assertEqual(len(cartao["evidencias"]), 2)
        estados = {a["nome"]: a["estado"] for a in cartao["atributos"]}
        self.assertEqual(estados["marca"], CONFIRMADO)
        self.assertEqual(estados["capacidade"], COMPATIVEL)

    def test_T10_dois_candidatos_iguais_continuam_ambiguos(self):
        """T10. Dois modelos semelhantes permanecem ambíguos sem elemento
        diferenciador."""
        ident = Identificacao("um celular")
        ident.anotar("marca", "Samsung", PROVAVEL, "logotipo parcialmente visível")
        ident.candidato("Galaxy S23", concordam=["formato", "três câmeras"])
        ident.candidato("Galaxy S23+", concordam=["formato", "três câmeras"])
        self.assertTrue(ident.ambiguo)
        frase = ident.frase()
        self.assertIn("dois candidatos igualmente compatíveis", frase)
        self.assertIn("Galaxy S23", frase)
        self.assertIn("mostre a etiqueta", frase)
        self.assertNotIn("confirmado", frase)

    def test_um_candidato_com_mais_evidencia_ganha_sem_virar_certeza(self):
        ident = Identificacao("um carregador")
        ident.candidato("Anker 65 W", concordam=["texto 65W", "formato"], fonte="catálogo local")
        ident.candidato("Anker 30 W", concordam=["formato"], conflitam=["texto 65W"])
        self.assertFalse(ident.ambiguo)
        self.assertEqual(ident.melhores()[0].nome, "Anker 65 W")
        self.assertIn("o mais compatível é Anker 65 W", ident.frase())
        self.assertEqual([c['nome'] for c in ident.cartao()['candidatos']], ['Anker 65 W', 'Anker 30 W'])
        self.assertEqual(ident.cartao()['candidatos'][1]['conflitam'], ['texto 65W'])

    def test_evidencias_que_se_contradizem_viram_conflito(self):
        ident = Identificacao("uma impressora")
        ident.anotar("modelo", "L3250", CONFIRMADO, "etiqueta")
        ident.anotar("modelo", "L3150", COMPATIVEL, "catálogo")
        a = ident.atributos["modelo"]
        self.assertEqual(a.estado, CONFLITANTE)
        self.assertIn("L3250 ou L3150", a.valor)
        self.assertIn("conflitante", ident.frase())

    def test_o_que_nao_foi_determinado_e_dito(self):
        ident = Identificacao("um livro")
        frase = ident.frase()
        self.assertIn("não determinei marca nem modelo nem ano", frase)

    def test_nota_de_candidato_nao_vira_porcentagem(self):
        """T11. Pontuação não aparece como certeza."""
        ident = Identificacao("um carro")
        ident.candidato("Civic 2018", concordam=["faróis", "grade"])
        frase = ident.frase()
        self.assertNotIn("%", frase)
        self.assertNotIn("certeza", frase)
        for a in ident.cartao()["atributos"]:
            self.assertNotIn("%", str(a.get("valor")))

    def test_cartao_tem_o_proximo_passo(self):
        ident = Identificacao("um celular", Qualidade(lado_px=300, nitidez=200, brilho=120))
        ident.anotar("marca", "Samsung", PROVAVEL, "logotipo parcial")
        cartao = ident.cartao()
        self.assertEqual(cartao["categoria"], "um celular")
        self.assertIn("modelo", cartao["proximo_passo"])
        self.assertTrue(cartao["qualidade"]["nitidez"] > 0)


if __name__ == "__main__":
    unittest.main()
