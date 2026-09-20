"""Seguir o mesmo objeto entre quadros (F14; cenário T13).

O que não pode acontecer: dois objetos parecidos trocarem de identidade em
silêncio quando um tapa o outro. Prefiro perder o rastro a mentir.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.rastreador import (  # noqa: E402
    Rastreador,
    descrever_mudancas,
    falar_ultima_vez,
    iou,
)


def obj(classe: int, x: float, y: float, w: float = 0.1, h: float = 0.1, nome: str = "copo", conf: float = 0.8):
    return {"classe": classe, "x": x, "y": y, "w": w, "h": h, "nome": nome, "conf": conf}


class Relogio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def passar(self, s: float):
        self.t += s
        return self.t


class Caixas(unittest.TestCase):
    def test_sobreposicao(self):
        a = {"x": 0, "y": 0, "w": 0.2, "h": 0.2}
        self.assertEqual(iou(a, dict(a)), 1.0)
        self.assertEqual(iou(a, {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.2}), 0.0)
        self.assertGreater(iou(a, {"x": 0.02, "y": 0.0, "w": 0.2, "h": 0.2}), 0.8)


class SeguirUmObjeto(unittest.TestCase):
    def setUp(self):
        self.r = Rastreador(relogio=Relogio())

    def test_objeto_parado_mantem_o_mesmo_id(self):
        self.r.atualizar([obj(41, 0.4, 0.4)])
        self.r._relogio.passar(0.3)
        self.r.atualizar([obj(41, 0.41, 0.4)])
        self.r._relogio.passar(0.3)
        ativos = self.r.atualizar([obj(41, 0.42, 0.41)])
        self.assertEqual(len(ativos), 1)
        self.assertEqual(ativos[0].id, "obj1")
        self.assertEqual(ativos[0].quadros, 3)

    def test_objeto_novo_ganha_id_novo(self):
        self.r.atualizar([obj(41, 0.2, 0.2)])
        self.r._relogio.passar(0.3)
        self.r.atualizar([obj(41, 0.2, 0.2), obj(41, 0.7, 0.7)])
        self.r._relogio.passar(0.3)
        ativos = self.r.atualizar([obj(41, 0.2, 0.2), obj(41, 0.7, 0.7)])
        self.assertEqual(sorted(t.id for t in ativos), ["obj1", "obj2"])

    def test_um_quadro_solto_nao_vira_objeto(self):
        # ruido do detector: apareceu num quadro so e sumiu
        ativos = self.r.atualizar([obj(41, 0.5, 0.5)])
        self.assertEqual(ativos, [])                       # ainda nao e "firme"


class OclusaoEVolta(unittest.TestCase):
    def setUp(self):
        self.rel = Relogio()
        self.r = Rastreador(relogio=self.rel)

    def _firmar(self, deteccoes, vezes=3):
        for _ in range(vezes):
            self.r.atualizar(deteccoes)
            self.rel.passar(0.3)

    def test_objeto_tapado_fica_sumido_e_volta_como_o_mesmo(self):
        self._firmar([obj(41, 0.4, 0.4)])
        self.assertEqual([t.id for t in self.r.ativos()], ["obj1"])

        self.r.atualizar([])                               # alguem passou na frente
        self.assertEqual(self.r.ativos(), [])
        self.assertEqual([t.id for t in self.r.sumidos()], ["obj1"])
        self.assertEqual([t.nome for t in self.r.ultimos_sumiram], ["copo"])

        self.rel.passar(1.0)
        self.r.atualizar([obj(41, 0.4, 0.4)])              # voltou no mesmo lugar
        self.assertEqual([t.id for t in self.r.ativos()], ["obj1"])
        self.assertEqual(self.r.obter("obj1").voltou, 1)
        self.assertEqual([t.id for t in self.r.ultimos_apareceram], ["obj1"])

    def test_objeto_que_volta_em_OUTRO_lugar_nao_herda_a_identidade(self):
        # o coracao do T13: na duvida, id novo -- nunca trocar em silencio
        self._firmar([obj(41, 0.1, 0.1)])
        self.r.atualizar([])
        self.rel.passar(1.0)
        self.r.atualizar([obj(41, 0.8, 0.8)])              # longe demais
        self.rel.passar(0.3)
        self.r.atualizar([obj(41, 0.8, 0.8)])
        ativos = self.r.ativos()
        self.assertEqual([t.id for t in ativos], ["obj2"])  # id NOVO
        self.assertEqual(ativos[0].voltou, 0)

    def test_depois_de_muito_tempo_o_sumido_morre(self):
        self._firmar([obj(41, 0.4, 0.4)])
        self.r.atualizar([])
        self.rel.passar(10.0)
        self.r.atualizar([])
        self.assertEqual(self.r.todos(), [])

    def test_dois_objetos_parecidos_nao_trocam_de_id(self):
        esquerda, direita = obj(41, 0.15, 0.5), obj(41, 0.75, 0.5)
        self._firmar([esquerda, direita])
        ids = {t.id: t.onde() for t in self.r.ativos()}
        self.assertEqual(sorted(ids), ["obj1", "obj2"])
        self.assertEqual(ids["obj1"], "à esquerda")
        self.assertEqual(ids["obj2"], "à direita")

        # o da esquerda some; o da direita continua parado
        for _ in range(2):
            self.r.atualizar([direita])
            self.rel.passar(0.3)
        atual = {t.id: t.onde() for t in self.r.ativos()}
        self.assertEqual(atual, {"obj2": "à direita"})      # obj2 NAO virou o da esquerda
        self.assertEqual([t.id for t in self.r.sumidos()], ["obj1"])

    def test_classe_diferente_nunca_casa(self):
        self._firmar([obj(41, 0.4, 0.4, nome="copo")])
        self.r.atualizar([obj(67, 0.4, 0.4, nome="celular")])   # mesmo lugar, outra coisa
        self.rel.passar(0.3)
        self.r.atualizar([obj(67, 0.4, 0.4, nome="celular")])
        ativos = self.r.ativos()
        self.assertEqual([t.nome for t in ativos], ["celular"])
        self.assertEqual([t.id for t in ativos], ["obj2"])


class RelogioDeVerdade(unittest.TestCase):
    """Com o relógio real do Windows (resolução ~16 ms), quadros seguidos têm o
    MESMO horário. Marcar o sumiço pela hora não funcionava; é por quadro."""

    def test_sumico_e_detectado_mesmo_no_mesmo_milissegundo(self):
        r = Rastreador()                                   # sem relógio falso de propósito
        for _ in range(3):
            r.atualizar([obj(41, 0.15, 0.5, nome="copo"),
                         obj(67, 0.8, 0.5, nome="celular")])
        self.assertEqual(len(r.ativos()), 2)
        r.atualizar([obj(41, 0.15, 0.5, nome="copo")])     # o celular sumiu
        self.assertEqual([t.nome for t in r.sumidos()], ["celular"])
        self.assertEqual([t.nome for t in r.ultimos_sumiram], ["celular"])
        self.assertEqual([t.nome for t in r.ativos()], ["copo"])


class Falar(unittest.TestCase):
    def test_ultima_vez_nao_afirma_que_ainda_esta_la(self):
        rel = Relogio()
        r = Rastreador(relogio=rel)
        for _ in range(3):
            r.atualizar([obj(41, 0.1, 0.5, nome="copo")])
            rel.passar(0.3)
        t = r.ativos()[0]
        agora = r.atualizar([]) or rel.t
        frase = falar_ultima_vez(t, rel.t + 300)
        self.assertIn("por último", frase)
        self.assertIn("à esquerda", frase)
        self.assertIn("Não posso afirmar que ainda esteja lá", frase)

    def test_vendo_agora_e_dito_como_agora(self):
        rel = Relogio()
        r = Rastreador(relogio=rel)
        for _ in range(3):
            r.atualizar([obj(41, 0.5, 0.5, nome="copo")])
            rel.passar(0.3)
        self.assertIn("Estou vendo", falar_ultima_vez(r.ativos()[0], rel.t))

    def test_frase_de_mudancas(self):
        rel = Relogio()
        r = Rastreador(relogio=rel)
        for _ in range(3):
            r.atualizar([obj(41, 0.5, 0.5, nome="copo")])
            rel.passar(0.3)
        r.atualizar([])
        self.assertIn("copo saiu de vista", descrever_mudancas(r.ultimos_sumiram, []))
        self.assertEqual(descrever_mudancas([], []), "")


if __name__ == "__main__":
    unittest.main()
