"""Condições do ensaio (F22/F26) e dependência entre etapas (F41).

Duas coisas que não podem se perder:

- um resultado sem as condições não serve para comparar depois ("imprimiu bem"
  com PLA a 210 não é o mesmo que com PETG a 240);
- uma etapa que depende de outra não pode ser oferecida como "a próxima".

As condições moram no experimento (`registrar_experimento`), que é a casa delas
desde a sessão do Codex; aqui eu testo que o relato falado chega lá completo.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))
os.environ.setdefault("OPENJARVIS_HOME", tempfile.mkdtemp())

from hud_runtime.comandos import Comandos  # noqa: E402
from hud_runtime.projetos import Projetos, resumo_falado  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.p = Projetos(self.pasta / "p.json")
        rt = SimpleNamespace(
            prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}),
            estado=SimpleNamespace(atualizar=lambda *a, **k: None, registrar=lambda *a, **k: None,
                                   telemetria={}),
            projetos=self.p)
        self.c = Comandos(rt, lambda pagina: None)

    def dizer(self, frase):
        achado = self.c.interpretar(frase)
        self.assertIsNotNone(achado, f"nenhuma regra entendeu: {frase}")
        return achado[0], self.c.executar(achado[0], achado[1], frase)


class DependenciaEntreEtapas(Base):
    """F41: a próxima etapa respeita o que precisa vir antes."""

    def test_etapa_bloqueada_nao_e_oferecida_como_proxima(self):
        self.dizer("Jarvis, comece o projeto caixa")
        self.dizer("Jarvis, falta furar a tampa")
        self.dizer("Jarvis, falta exportar o STL")
        nome, r = self.dizer("Jarvis, exportar o STL depende de furar a tampa")
        self.assertEqual(nome, "projeto_depende")
        self.assertIn("só depois de", r)

        t = self.p.ativa()
        self.assertEqual(t.proxima_etapa().descricao, "furar a tampa")
        travadas = t.bloqueadas()
        self.assertEqual(travadas[0][0].descricao, "exportar o STL")
        self.assertEqual(travadas[0][1], ["furar a tampa"])
        self.assertIn("exportar o STL depende de furar a tampa", resumo_falado(t))

    def test_concluir_a_anterior_libera_a_seguinte(self):
        self.dizer("Jarvis, comece o projeto caixa")
        self.dizer("Jarvis, falta furar a tampa")
        self.dizer("Jarvis, falta exportar o STL")
        self.dizer("Jarvis, exportar o STL depende de furar a tampa")
        t = self.p.ativa()
        self.p.concluir_etapa(t.id, "furar a tampa", "furo de 6 mm")
        self.assertEqual(t.proxima_etapa().descricao, "exportar o STL")
        self.assertEqual(t.bloqueadas(), [])

    def test_etapa_nao_pode_depender_de_si_mesma(self):
        self.dizer("Jarvis, comece o projeto caixa")
        self.dizer("Jarvis, falta furar a tampa")
        t = self.p.ativa()
        with self.assertRaises(ValueError):
            self.p.depender(t.id, "furar a tampa", "furar a tampa")

    def test_a_etapa_anterior_e_criada_se_nao_existir(self):
        self.dizer("Jarvis, comece o projeto caixa")
        self.dizer("Jarvis, falta pintar")
        self.dizer("Jarvis, pintar depende de lixar")
        t = self.p.ativa()
        self.assertEqual([e.descricao for e in t.etapas], ["lixar", "pintar"])
        self.assertEqual(t.proxima_etapa().descricao, "lixar")


class CondicoesDoEnsaio(Base):
    """F22/F26: o relato guarda material, temperatura e o que não foi medido."""

    def test_o_relato_falado_vira_experimento_com_condicoes(self):
        self.dizer("Jarvis, comece o projeto caixa")
        nome, r = self.dizer("Jarvis, registre o experimento primeira impressão: "
                             "imprimi com PLA a 210 graus e ficou boa")
        self.assertEqual(nome, "projeto_experimento")
        self.assertIn("relato seu", r)                      # não vira medição minha
        self.assertIn("não declara o projeto validado", r)

        ensaio = self.p.ativa().experimentos[-1]
        self.assertIn("PLA", ensaio["condicoes"])
        self.assertIn("210 graus", ensaio["condicoes"])
        self.assertEqual(ensaio["validacao"], "relato_usuario")

    def test_extrator_de_condicoes(self):
        cond, limites = self.c._condicoes_do_texto(
            "imprimi em PETG a 240 graus com 30 por cento de preenchimento a 50 mm por segundo")
        self.assertEqual(cond["material"].upper(), "PETG")
        self.assertEqual(cond["temperatura"], "240 graus")
        self.assertEqual(cond["preenchimento"], "30%")
        self.assertEqual(cond["velocidade"], "50 mm/s")
        self.assertIn("medida com instrumento", limites)    # nada foi medido de fato

    def test_quando_ele_mediu_o_limite_some(self):
        _, limites = self.c._condicoes_do_texto("medi com o paquímetro: deu 52,1 mm")
        self.assertEqual(limites, [])

    def test_o_resumo_cita_o_ultimo_ensaio(self):
        self.dizer("Jarvis, comece o projeto caixa")
        self.dizer("Jarvis, registre o experimento teste 1: imprimi com PLA a 210 graus, ficou boa")
        frase = resumo_falado(self.p.ativa())
        self.assertIn("Último ensaio: teste 1", frase)
        self.assertIn("material PLA", frase)

    def test_falha_e_registrada_como_falha(self):
        self.dizer("Jarvis, comece o projeto caixa")
        self.dizer("Jarvis, registre o experimento teste 2: quebrou na primeira camada com ABS")
        ensaio = self.p.ativa().experimentos[-1]
        self.assertTrue(ensaio["falha"])
        self.assertIn("ABS", ensaio["condicoes"].upper())


if __name__ == "__main__":
    unittest.main()
