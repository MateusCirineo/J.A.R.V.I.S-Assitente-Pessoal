"""Cena consultável, com os buracos assumidos (F16, §10).

O teste que importa aqui é o negativo: região sem detecção **não** pode virar
"região vazia", e sem régua calibrada não sai centímetro nenhum.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.cena import (  # noqa: E402
    NAO_OBSERVADO,
    OBSERVADO,
    ULTIMA_VEZ,
    consultar,
    falar,
    montar,
    regiao_de,
)
from hud_runtime.rastreador import Rastreador  # noqa: E402


class Relogio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def obj(classe, x, nome, w=0.1):
    return {"classe": classe, "x": x, "y": 0.5, "w": w, "h": 0.1, "nome": nome, "conf": 0.9}


def cena_com(*deteccoes, quadros=3, camera=True, regua=None, rel=None):
    rel = rel or Relogio()
    r = Rastreador(relogio=rel)
    for _ in range(quadros):
        r.atualizar(list(deteccoes))
    return montar(r, camera_ligada=camera, regua=regua, agora=rel.t), r, rel


class Regioes(unittest.TestCase):
    def test_onde_cada_coisa_cai(self):
        self.assertEqual(regiao_de(0.05, 0.1), "esquerda")
        self.assertEqual(regiao_de(0.45, 0.1), "centro")
        self.assertEqual(regiao_de(0.80, 0.1), "direita")


class MontarACena(unittest.TestCase):
    def test_o_que_esta_em_vista_e_observado(self):
        cena, _, _ = cena_com(obj(41, 0.15, "copo"), obj(67, 0.8, "celular"))
        self.assertEqual({i.nome for i in cena.agora()}, {"copo", "celular"})
        self.assertEqual({i.regiao for i in cena.agora()}, {"esquerda", "direita"})
        self.assertTrue(all(i.estado == OBSERVADO for i in cena.agora()))

    def test_regiao_sem_deteccao_e_sem_observacao_nao_vazia(self):
        cena, _, _ = cena_com(obj(41, 0.15, "copo"))
        self.assertEqual(cena.regioes_observadas, ["esquerda"])
        self.assertEqual(sorted(cena.regioes_sem_observacao), ["centro", "direita"])
        frase = falar(cena)
        self.assertIn("Não observei", frase)
        self.assertIn("sem observação não quer dizer vazio", frase)
        self.assertNotIn("vazia", frase.replace("vazio", ""))

    def test_objeto_que_sumiu_vira_ultima_observacao(self):
        rel = Relogio()
        r = Rastreador(relogio=rel)
        for _ in range(3):
            r.atualizar([obj(41, 0.15, "copo")])
        r.atualizar([])                                   # sumiu
        rel.t += 120
        cena = montar(r, camera_ligada=True, agora=rel.t)
        self.assertEqual(cena.agora(), [])
        antes = cena.antes()
        self.assertEqual([i.nome for i in antes], ["copo"])
        self.assertEqual(antes[0].estado, ULTIMA_VEZ)
        self.assertIn("Antes eu vi", falar(cena))
        self.assertIn("vi há 2 min", falar(cena))

    def test_ruido_de_um_quadro_nao_entra_na_cena(self):
        cena, _, _ = cena_com(obj(41, 0.15, "copo"), quadros=1)
        self.assertTrue(cena.vazia)

    def test_camera_desligada_nao_tem_cena(self):
        cena, _, _ = cena_com(obj(41, 0.15, "copo"), camera=False)
        self.assertEqual(cena.regioes_observadas, [])
        self.assertEqual(len(cena.regioes_sem_observacao), 3)
        self.assertIn("câmera está desligada", falar(cena))


class Medidas(unittest.TestCase):
    def test_sem_regua_calibrada_nao_ha_centimetro(self):
        cena, r, _ = cena_com(obj(41, 0.15, "copo"))
        self.assertFalse(cena.regua_calibrada)
        self.assertTrue(all(i.medida_cm is None for i in cena.itens))
        self.assertIn("não dou centímetro de nada", falar(cena))

    def test_com_regua_calibrada_a_medida_e_dita_como_medida(self):
        from types import SimpleNamespace
        rel = Relogio()
        r = Rastreador(relogio=rel)
        for _ in range(3):
            r.atualizar([obj(41, 0.15, "copo")])
        trilha = r.ativos()[0].id
        cena = montar(r, camera_ligada=True, regua=SimpleNamespace(calibrada=True),
                      medidas={trilha: (7.4, 7.1)}, agora=rel.t)
        item = cena.agora()[0]
        self.assertEqual(item.medida_estado, "medido")
        self.assertIn("7,4 por 7,1 cm medidos", item.falado(cena.em))

    def test_medida_sem_calibracao_e_descartada(self):
        rel = Relogio()
        r = Rastreador(relogio=rel)
        for _ in range(3):
            r.atualizar([obj(41, 0.15, "copo")])
        trilha = r.ativos()[0].id
        cena = montar(r, camera_ligada=True, medidas={trilha: (7.4, 7.1)}, agora=rel.t)
        self.assertIsNone(cena.agora()[0].medida_cm)      # não inventa medida


class OlheiXNaoOlhei(unittest.TestCase):
    """A diferença que o §10 cobra: "não observei" ≠ "olhei e não reconheci"."""

    def test_detector_rodou_sem_achar_nada(self):
        rel = Relogio()
        r = Rastreador(relogio=rel)
        cena = montar(r, camera_ligada=True, detector_rodou=True, agora=rel.t)
        self.assertEqual(cena.regioes_sem_observacao, [])       # as três foram olhadas
        self.assertEqual(len(cena.regioes_observadas), 3)
        frase = falar(cena)
        self.assertIn("Olhei o quadro inteiro e não reconheci nada", frase)
        self.assertIn("pode haver coisa ali que eu não sei nomear", frase)
        self.assertNotIn("Não observei", frase)

    def test_detector_nao_rodou_e_dito_como_nao_observado(self):
        rel = Relogio()
        cena = montar(Rastreador(relogio=rel), camera_ligada=True, detector_rodou=False, agora=rel.t)
        self.assertEqual(len(cena.regioes_sem_observacao), 3)
        self.assertIn("Ainda não analisei nenhum quadro", falar(cena))

    def test_regiao_olhada_sem_objeto_responde_diferente(self):
        cena, _, _ = cena_com(obj(41, 0.15, "copo"))
        cena.detector_rodou = True
        cena.regioes_sem_observacao = []
        r = consultar(cena, "o que tem no centro?")
        self.assertIn("Olhei no centro e não reconheci nada", r)
        self.assertIn("não sei nomear", r)


class Consultar(unittest.TestCase):
    def setUp(self):
        self.cena, _, _ = cena_com(obj(41, 0.15, "copo"), obj(67, 0.8, "celular"))

    def test_perguntar_por_regiao(self):
        self.assertIn("copo", consultar(self.cena, "o que está à esquerda?"))
        self.assertIn("celular", consultar(self.cena, "o que tem na direita?"))

    def test_regiao_sem_observacao_responde_sem_chutar(self):
        r = consultar(self.cena, "o que tem no centro?")
        self.assertIn("Não estou observando nada no centro", r)
        self.assertIn("não quer dizer que esteja vazio", r)

    def test_perguntar_o_que_nao_foi_visto(self):
        r = consultar(self.cena, "o que você não viu?")
        self.assertIn("Não observei centro", r)
        self.assertIn("fora do enquadramento", r)

    def test_pergunta_generica_cai_na_descricao(self):
        r = consultar(self.cena, "descreva a cena")
        self.assertIn("Estou vendo", r)
        self.assertIn("copo", r)

    def test_nao_promete_reconstrucao_3d(self):
        fonte = (RAIZ / "hud_runtime" / "cena.py").read_text(encoding="utf-8").lower()
        self.assertIn("não é reconstrução", fonte.replace("nao e reconstrucao", "não é reconstrução"))
        for frase in ("Estou vendo", "Não observei"):
            self.assertIn(frase, falar(self.cena))
        self.assertNotIn("3d", falar(self.cena).lower())


if __name__ == "__main__":
    unittest.main()
