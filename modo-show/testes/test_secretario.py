"""Secretario do filme: horarios falados, comandos por voz, noticias, falas
proativas e o resumo do dia."""

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime import comandos as cmd  # noqa: E402
from hud_runtime.anunciador import em_silencio  # noqa: E402
from hud_runtime.estado import Estado  # noqa: E402
from hud_runtime.noticias import _intercalar, ler_feed, manchetes_faladas  # noqa: E402
from hud_runtime.secretario import (Secretario, falar_quando, interpretar_quando,  # noqa: E402
                                    limpar_texto_lembrete)

AGORA = datetime(2026, 9, 18, 10, 0, 0)


class TestHorarioFalado(unittest.TestCase):
    def q(self, frase):
        return interpretar_quando(frase, AGORA)

    def test_relativo(self):
        self.assertEqual(self.q("me lembre de tirar o bolo em 10 minutos")[0], datetime(2026, 9, 18, 10, 10))
        self.assertEqual(self.q("daqui a 2 horas")[0], datetime(2026, 9, 18, 12, 0))
        self.assertEqual(self.q("em meia hora")[0], datetime(2026, 9, 18, 10, 30))
        self.assertEqual(self.q("em cinco minutos")[0], datetime(2026, 9, 18, 10, 5))
        self.assertEqual(self.q("timer de 30 segundos")[0], datetime(2026, 9, 18, 10, 0, 30))
        self.assertEqual(self.q("em uma hora e meia")[0], datetime(2026, 9, 18, 11, 30))

    def test_absoluto(self):
        self.assertEqual(self.q("às 15h")[0], datetime(2026, 9, 18, 15, 0))
        self.assertEqual(self.q("às 15:30")[0], datetime(2026, 9, 18, 15, 30))
        self.assertEqual(self.q("as 3 da tarde")[0], datetime(2026, 9, 18, 15, 0))
        self.assertEqual(self.q("às 9 e meia")[0], datetime(2026, 9, 18, 9, 30) .replace(day=19))  # ja passou: amanha
        self.assertEqual(self.q("amanhã às 7")[0], datetime(2026, 9, 19, 7, 0))
        self.assertEqual(self.q("ao meio-dia")[0], datetime(2026, 9, 18, 12, 0))
        self.assertEqual(self.q("às 8 da noite")[0], datetime(2026, 9, 18, 20, 0))

    def test_sem_horario(self):
        self.assertEqual(self.q("me lembre de comprar pão"), (None, "me lembre de comprar pão"))

    def test_texto_do_lembrete(self):
        _, resto = self.q("Jarvis, me lembre de ligar para o Pedro às 15h")
        self.assertEqual(limpar_texto_lembrete(resto), "ligar para o Pedro")
        _, resto = self.q("lembre-me que tenho dentista amanhã às 9")
        self.assertEqual(limpar_texto_lembrete(resto), "tenho dentista")

    def test_falar_quando(self):
        self.assertEqual(falar_quando(datetime(2026, 9, 18, 10, 20), AGORA), "daqui a 20 minutos")
        self.assertEqual(falar_quando(datetime(2026, 9, 18, 15, 0), AGORA), "hoje às 15h")
        self.assertEqual(falar_quando(datetime(2026, 9, 19, 7, 30), AGORA), "amanhã às 7h30")


class TestSecretario(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.mudancas, self.vencidos = [], []
        self.s = Secretario(ao_mudar=self.mudancas.append, ao_vencer=self.vencidos.append, pasta=self.pasta)

    def test_lembrete_vence_uma_vez(self):
        item = self.s.lembrar("beber água", datetime.fromtimestamp(1_000_000))
        self.assertEqual(self.s.pendentes()[0]["id"], item["id"])
        vencidos = self.s.verificar(agora=1_000_010)
        self.assertEqual([v["texto"] for v in vencidos], ["beber água"])
        self.assertEqual(self.s.verificar(agora=1_000_020), [])       # nao repete
        self.assertEqual(self.s.pendentes(), [])

    def test_atrasado_demais_nao_fala(self):
        self.s.lembrar("velho", datetime.fromtimestamp(1_000_000))
        self.assertEqual(self.s.verificar(agora=1_000_000 + 13 * 3600), [])

    def test_cancelar_e_notas(self):
        self.s.lembrar("a", datetime(2030, 1, 1))
        self.s.lembrar("b", datetime(2030, 1, 2))
        self.assertEqual(self.s.cancelar(), 2)
        n = self.s.anotar("comprar cabo HDMI")
        self.assertEqual(self.s.notas()[0]["texto"], "comprar cabo HDMI")
        self.assertTrue(self.s.apagar_nota(n["id"]))
        self.assertEqual(self.s.notas(), [])
        self.assertTrue(self.mudancas)                                 # a tela e avisada

    def test_persistencia(self):
        self.s.anotar("fica salvo")
        outro = Secretario(pasta=self.pasta)
        self.assertEqual(outro.notas()[0]["texto"], "fica salvo")


class TestComandos(unittest.TestCase):
    CASOS = {
        "Jarvis, o que é isso?": "visao",
        "Jarvis, que modelo de celular é esse?": "visao",
        "Jarvis, identifique este objeto": "visao",
        "Jarvis, ligue a câmera": "camera_ligar",
        "desliga a câmera": "camera_desligar",
        "Jarvis, modo capacete": "capacete_ligar",
        "Jarvis, saia do capacete": "capacete_desligar",
        "Jarvis, tela cheia": "tela_cheia",
        "Jarvis, abra o painel": "janela",
        "Jarvis, abre o YouTube": "site",
        "Jarvis, toque Back in Black no YouTube": "tocar",                 # abre o 1o video (tocar cobre o YouTube)
        "Jarvis, pesquise sobre buracos negros": "pesquisar",
        "Jarvis, pause a música": "musica_pausar",
        "próxima música": "musica_proxima",
        "Jarvis, aumente o volume": "volume_aumentar",
        "Jarvis, volume em 30": "volume_definir",
        "Jarvis, me lembre de ligar para o Pedro às 15h": "lembrete",
        "Jarvis, timer de 5 minutos": "timer",
        "Jarvis, quais são meus lembretes?": "lembretes_listar",
        "Jarvis, anote: comprar cabo HDMI": "nota",
        "Jarvis, quais as notícias?": "noticias",
        "Jarvis, bom dia": "briefing",
        "Jarvis, me atualize": "briefing",
        "Jarvis, tenho e-mails novos?": "emails",
        "Jarvis, relatório de status": "status",
        "Jarvis, está aí?": "presenca",
        "Obrigado, Jarvis": "obrigado",
        "Jarvis, abra a calculadora": "app",
        "Jarvis, abre o Visual Studio Code": "app",
        "Jarvis, deixa o som mais alto": "volume_aumentar",
        "Jarvis, o som tá alto, deixa mais baixo": "volume_diminuir",
    }

    def test_so_acao_leva_ferramentas(self):
        self.assertTrue(cmd.parece_acao("Jarvis, guarde a informação de que a chave fica na gaveta"))
        self.assertTrue(cmd.parece_acao("Jarvis, deixa a tela mais clara"))
        self.assertFalse(cmd.parece_acao("Jarvis, qual é a capital do Japão?"))
        self.assertFalse(cmd.parece_acao("Jarvis, quanto é dois mais dois?"))

    def test_frases(self):
        for frase, esperado in self.CASOS.items():
            achado = cmd.interpretar(frase)
            self.assertIsNotNone(achado, frase)
            self.assertEqual(achado[0], esperado, frase)

    def test_nao_rouba_perguntas(self):
        for frase in ("Jarvis, qual a capital da França?", "Jarvis, quanto é 2 mais 2?",
                      "Jarvis, adicione a tarefa comprar pão", "Jarvis, que horas são?"):
            self.assertIsNone(cmd.interpretar(frase), frase)

    def test_texto_da_nota_e_consulta(self):
        self.assertEqual(cmd.texto_depois_do_verbo("Jarvis, anote que amanhã tem prova", r"anot"), "amanhã tem prova")
        c = cmd.Comandos(SimpleNamespace(), lambda c: None)
        self.assertEqual(c._consulta("Jarvis, pesquise sobre buracos negros",
                                     r"(?:pesquis\w*)(?:\s+(?:por|sobre|a))?", r"$^"), "buracos negros")

    def test_achar_app(self):
        apps = {"visual studio code": "VSC", "calculadora": "CALC", "microsoft teams": "TEAMS", "steam": "STEAM"}
        self.assertEqual(cmd.achar_app("vs code", apps), ("visual studio code", "VSC"))
        self.assertEqual(cmd.achar_app("Teams", apps), ("microsoft teams", "TEAMS"))
        self.assertEqual(cmd.achar_app("a calculadora", {**apps}) , None)          # artigo ja sai na regra
        self.assertIsNone(cmd.achar_app("photoshop", apps))

    def test_ferramentas_bem_formadas(self):
        nomes = [f["function"]["name"] for f in cmd.FERRAMENTAS]
        self.assertEqual(len(nomes), len(set(nomes)))
        for f in cmd.FERRAMENTAS:
            self.assertEqual(f["type"], "function")
            self.assertEqual(f["function"]["parameters"]["type"], "object")


class _Prefs:
    def __init__(self, d):
        self.d = d

    def ler(self):
        return dict(self.d)

    def aplicar(self, m):
        self.d.update(m)


class TestExecucao(unittest.TestCase):
    def setUp(self):
        est = Estado()
        est.telemetria = {"sistema": {"memoria": {"status": "medido", "uso_pct": 93, "livre_gb": 0.8},
                                      "cpu": {"status": "medido", "uso_pct": 20},
                                      "disco": {"status": "medido", "livre_gb": 63.2},
                                      "bateria": {"status": "medido", "percentual": 100, "na_tomada": True}},
                          "noticias": {"status": "medido", "itens": [{"fonte": "G1", "titulo": "Manchete A."},
                                                                     {"fonte": "BBC News Brasil", "titulo": "Manchete B"}]},
                          "email": {"status": "medido", "nao_lidos": 2, "contas": [{"email": "a@b", "nao_lidos": 2,
                                    "recentes": [{"id": "1", "de": "Pepper", "assunto": "Reunião", "em": 0}]}]},
                          "agenda": {"status": "nao_configurado"}}
        self.sec = Secretario(pasta=Path(tempfile.mkdtemp()))
        self.camera = SimpleNamespace(ativa=False, ativar=lambda: setattr(self.camera, "ativa", True),
                                      desativar=lambda: setattr(self.camera, "ativa", False))
        self.paginas = []
        self.rt = SimpleNamespace(estado=est, prefs=_Prefs({"nome_usuario": "Senhor", "local_clima": None}),
                                  secretario=self.sec, camera=self.camera, clima=None, tarefas=None,
                                  noticias=None, porta=8765, _publicar_prefs=lambda: None)
        self.c = cmd.Comandos(self.rt, self.paginas.append)

    def fazer(self, frase):
        nome, args = cmd.interpretar(frase)
        return self.c.executar(nome, args, frase)

    def test_lembrete_e_timer(self):
        r = self.fazer("Jarvis, me lembre de ligar para o Pedro em 20 minutos")
        self.assertIn("ligar para o Pedro", r)
        self.assertEqual(self.sec.pendentes()[0]["texto"], "ligar para o Pedro")
        self.assertIn("Timer marcado", self.fazer("Jarvis, timer de 5 minutos"))
        self.assertIn("Para quando", self.fazer("Jarvis, me lembre de comprar pão"))

    def test_nota_camera_capacete(self):
        self.assertEqual(self.fazer("Jarvis, anote: comprar cabo HDMI"), "Anotado.")
        self.assertEqual(self.sec.notas()[0]["texto"], "comprar cabo HDMI")
        self.fazer("Jarvis, ligue a câmera")
        self.assertTrue(self.camera.ativa)
        self.fazer("Jarvis, modo capacete")
        self.assertEqual(self.paginas[-1], {"acao": "capacete", "ligado": True})

    def test_falas_compostas(self):
        self.assertIn("2 e-mails não lidos", self.fazer("Jarvis, tenho e-mails novos?"))
        self.assertIn("Pepper", self.fazer("Jarvis, tenho e-mails novos?"))
        self.assertIn("memória em 93 por cento, acima do ideal", self.fazer("Jarvis, relatório de status"))
        self.assertIn("G1: Manchete A", self.fazer("Jarvis, quais as notícias?"))
        b = self.c.briefing(datetime(2026, 9, 18, 8, 5))
        for trecho in ("Bom dia, Senhor. São 8 e 05.", "2 e-mails não lidos", "Manchete A", "memória do computador"):
            self.assertIn(trecho, b)

    def test_ferramenta_lembrete_do_modelo(self):
        r = self.c.executar_ferramenta("criar_lembrete", {"texto": "reunião", "em_minutos": 15})
        self.assertIn("reunião", r)
        r = self.c.executar_ferramenta("criar_lembrete", {"texto": "x", "horario": "25:99"})
        self.assertIn("Para quando", r)


class TestNoticiasEFalas(unittest.TestCase):
    RSS = b"""<?xml version="1.0"?><rss><channel><title>t</title>
      <item><title><![CDATA[Chuva forte atinge a capital paulista nesta sexta]]></title><link>https://g1.globo.com/a</link>
        <pubDate>Fri, 18 Sep 2026 10:00:00 -0300</pubDate></item>
      <item><title>Governo anuncia novo programa de moradia popular</title><link>javascript:alert(1)</link></item>
      <item><title>EPTV 1 Piracicaba ao vivo</title><link>https://g1.globo.com/v</link></item>
      <item><title><![CDATA[Clique aqui]]></title></item>
    </channel></rss>"""

    def test_rss(self):
        itens = ler_feed(self.RSS, "G1")
        self.assertEqual(len(itens), 2)                      # "ao vivo" e "Clique aqui" saem
        self.assertEqual(itens[0]["titulo"], "Chuva forte atinge a capital paulista nesta sexta")
        self.assertEqual(itens[0]["link"], "https://g1.globo.com/a")
        self.assertIsNone(itens[1]["link"])                   # link perigoso descartado
        self.assertIsNotNone(itens[0]["em"])

    def test_intercala_fontes(self):
        itens = [{"fonte": "A", "titulo": "a1"}, {"fonte": "A", "titulo": "a2"}, {"fonte": "B", "titulo": "b1"}]
        self.assertEqual([x["titulo"] for x in _intercalar(itens)], ["a1", "b1", "a2"])
        self.assertIn("Não consegui", manchetes_faladas({"status": "erro"}))

    def test_silencio(self):
        self.assertTrue(em_silencio(datetime(2026, 9, 18, 23, 0), 22, 7))
        self.assertTrue(em_silencio(datetime(2026, 9, 18, 3, 0), 22, 7))
        self.assertFalse(em_silencio(datetime(2026, 9, 18, 12, 0), 22, 7))
        self.assertFalse(em_silencio(datetime(2026, 9, 18, 12, 0), 0, 0))


if __name__ == "__main__":
    unittest.main()
