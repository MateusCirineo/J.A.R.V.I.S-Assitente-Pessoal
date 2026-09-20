"""Cruzar o que aconteceu, por período e por objeto (F17).

Só entra aqui o que foi registrado de verdade: o que a câmera viu com ela
ligada, o que o inventário anotou e o que passou pelo registro de eventos.
Nada vira "está lá agora".
"""

import sys
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.ocorrencias import (  # noqa: E402
    Ocorrencia,
    de_eventos,
    de_inventario,
    de_pecas,
    de_projetos,
    de_rastreador,
    falar,
    filtrar,
    periodo_citado,
)
from hud_runtime.rastreador import Rastreador  # noqa: E402


def meia_noite(agora: float) -> float:
    return datetime.fromtimestamp(agora).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


class PeriodoCitado(unittest.TestCase):
    def setUp(self):
        # 20/09/2026 às 15h30, para as contas serem previsíveis
        self.agora = datetime(2026, 9, 20, 15, 30).timestamp()
        self.zero = meia_noite(self.agora)

    def test_hoje_de_manha_e_a_tarde(self):
        ini, fim, rot = periodo_citado("o que apareceu hoje de manhã?", self.agora)
        self.assertEqual(rot, "hoje de manhã")
        self.assertEqual(ini, self.zero + 5 * 3600)
        self.assertEqual(fim, self.zero + 12 * 3600)

        ini, fim, rot = periodo_citado("o que mudou hoje à tarde?", self.agora)
        self.assertEqual(rot, "hoje à tarde")
        self.assertEqual(ini, self.zero + 12 * 3600)

    def test_ontem_e_hoje(self):
        ini, fim, rot = periodo_citado("o que aconteceu ontem?", self.agora)
        self.assertEqual(rot, "ontem")
        self.assertEqual(fim, self.zero)
        self.assertEqual(ini, self.zero - 86400)
        self.assertEqual(periodo_citado("o que fiz hoje?", self.agora)[2], "hoje")

    def test_relativo_em_minutos_e_horas(self):
        ini, fim, rot = periodo_citado("o que apareceu nos últimos 20 minutos?", self.agora)
        self.assertEqual(round(fim - ini), 1200)
        self.assertIn("20 minutos", rot)
        ini, _, _ = periodo_citado("o que mudou nas últimas 3 horas?", self.agora)
        self.assertEqual(round(self.agora - ini), 3 * 3600)

    def test_enquanto_eu_estava_fora(self):
        ini, fim, rot = periodo_citado("o que aconteceu enquanto eu estava fora?", self.agora)
        self.assertEqual(round(fim - ini), 4 * 3600)

    def test_sem_periodo_citado_usa_as_ultimas_12h(self):
        self.assertIn("12 horas", periodo_citado("o que aconteceu?", self.agora)[2])


class Fontes(unittest.TestCase):
    def test_do_rastreador_vem_apareceu_sumiu_e_voltou(self):
        class Relogio:
            t = 1000.0

            def __call__(self):
                return self.t

        rel = Relogio()
        r = Rastreador(relogio=rel)

        def copo(x):
            return {"classe": 41, "x": x, "y": 0.5, "w": 0.1, "h": 0.1, "nome": "copo", "conf": 0.9}

        for _ in range(3):
            r.atualizar([copo(0.15)])
            rel.t += 0.3
        r.atualizar([])                       # sumiu
        rel.t += 1
        r.atualizar([copo(0.15)])             # voltou

        oc = de_rastreador(r)
        tipos = {o.tipo for o in oc}
        self.assertIn("objeto_visto", tipos)
        self.assertIn("objeto_voltou", tipos)
        self.assertTrue(all(o.fonte == "câmera" for o in oc))
        self.assertTrue(any("à esquerda" in o.onde for o in oc))

    def test_do_inventario_vem_a_ultima_vez_que_vi(self):
        import tempfile
        from hud_runtime.inventario import Inventario
        inv = Inventario(Path(tempfile.mkdtemp()) / "inv.json")
        o = inv.cadastrar("meu celular", categoria="celular")
        inv.observar(o.id, onde="à direita")
        oc = de_inventario(inv)
        self.assertEqual(len(oc), 1)
        self.assertIn("vi meu celular", oc[0].texto)
        self.assertEqual(oc[0].fonte, "inventário")

    def test_do_registro_so_avisos_e_erros(self):
        agora = time.time()
        eventos = [{"em": agora, "tipo": "voz", "texto": "ouvi algo", "nivel": "info"},
                   {"em": agora, "tipo": "servidor", "texto": "servidor parou", "nivel": "erro"}]
        oc = de_eventos(eventos)
        self.assertEqual(len(oc), 1)
        self.assertIn("servidor parou", oc[0].texto)

    def test_de_projetos_e_pecas(self):
        import tempfile
        from hud_runtime.pecas import Pecas
        from hud_runtime.projetos import Projetos
        pasta = Path(tempfile.mkdtemp())
        pj = Projetos(pasta / "p.json")
        t = pj.criar("terminar a caixa", projeto="caixa", etapas=["furar"])
        pj.concluir_etapa(t.id, "furar", "furo de 6 mm")
        oc = de_projetos(pj)
        self.assertTrue(any("comecei terminar a caixa" in o.texto for o in oc))
        self.assertTrue(any("concluí: furar" in o.texto for o in oc))

        pc = Pecas(pasta / "pc.json", pasta=pasta)
        peca, _ = pc.criar("cilindro", {"diametro": 20, "altura": 40}, nome="pino")
        pc.alterar(peca, "altura", valor=45)
        oc = de_pecas(pc)
        self.assertEqual(len(oc), 2)
        self.assertIn("versão 2", oc[1].texto)


class Cruzar(unittest.TestCase):
    def setUp(self):
        self.agora = datetime(2026, 9, 20, 15, 30).timestamp()
        zero = meia_noite(self.agora)
        self.oc = [
            Ocorrencia(zero + 9 * 3600, "objeto_visto", "copo apareceu", "à esquerda", "câmera"),
            Ocorrencia(zero + 13 * 3600, "objeto_visto", "celular apareceu", "à direita", "câmera"),
            Ocorrencia(zero + 14 * 3600, "objeto_sumiu", "celular saiu de vista", "à direita", "câmera"),
            Ocorrencia(zero - 3600, "evento", "servidor parou", "", "registro"),
        ]

    def test_filtra_por_periodo(self):
        ini, fim, _ = periodo_citado("o que apareceu hoje à tarde?", self.agora)
        achados = filtrar(self.oc, ini, fim)
        self.assertEqual([o.texto for o in achados],
                         ["celular apareceu", "celular saiu de vista"])

    def test_filtra_por_objeto(self):
        ini, fim, _ = periodo_citado("hoje", self.agora)
        self.assertEqual([o.texto for o in filtrar(self.oc, ini, fim, termo="copo")],
                         ["copo apareceu"])

    def test_filtra_por_lugar_e_tipo(self):
        ini, fim, _ = periodo_citado("hoje", self.agora)
        so_direita = filtrar(self.oc, ini, fim, onde="direita")
        self.assertEqual(len(so_direita), 2)
        so_sumiu = filtrar(self.oc, ini, fim, tipos=("objeto_sumiu",))
        self.assertEqual([o.texto for o in so_sumiu], ["celular saiu de vista"])

    def test_periodo_sem_registro_diz_isso_sem_inventar(self):
        frase = falar([], "ontem")
        self.assertIn("Não registrei nada ontem", frase)
        self.assertIn("com ela ligada", frase)       # explica o limite da observação

    def test_fala_lista_com_hora_e_lugar(self):
        ini, fim, rot = periodo_citado("hoje", self.agora)
        frase = falar(filtrar(self.oc, ini, fim), rot)
        self.assertIn("copo apareceu, à esquerda", frase)
        self.assertIn(":", frase)                    # as horas aparecem
        self.assertTrue(frase.startswith("Hoje, Senhor:"))


if __name__ == "__main__":
    unittest.main()
