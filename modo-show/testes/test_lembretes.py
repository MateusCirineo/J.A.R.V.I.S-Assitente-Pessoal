"""Lembretes (Q3): repetir, adiar/soneca, remarcar e cancelar so o certo."""

import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime import comandos as cmd  # noqa: E402
from hud_runtime import secretario as sec  # noqa: E402

SEX = datetime(2026, 9, 18, 16, 0)          # sexta-feira, 16h


class TestRepeticao(unittest.TestCase):
    def test_interpretar(self):
        self.assertEqual(sec.interpretar_repeticao("todo dia às 8h tomar remédio")[:2], ("diario", None))
        self.assertEqual(sec.interpretar_repeticao("nos dias úteis às 7h")[:2], ("dias_uteis", None))
        self.assertEqual(sec.interpretar_repeticao("de segunda a sexta às 7h")[:2], ("dias_uteis", None))
        self.assertEqual(sec.interpretar_repeticao("toda terça às 19h aula")[:2], ("semanal", 1))
        self.assertEqual(sec.interpretar_repeticao("me lembre às 15h")[:2], (None, None))

    def test_proxima(self):
        self.assertEqual(sec.proxima_ocorrencia(SEX.replace(hour=8), "diario", None, SEX), datetime(2026, 9, 19, 8))
        self.assertEqual(sec.proxima_ocorrencia(SEX.replace(hour=8), "dias_uteis", None, SEX), datetime(2026, 9, 21, 8))
        self.assertEqual(sec.proxima_ocorrencia(SEX.replace(hour=19), "semanal", 1, SEX), datetime(2026, 9, 22, 19))
        self.assertEqual(sec.proxima_ocorrencia(SEX.replace(hour=17), "diario", None, SEX), datetime(2026, 9, 18, 17))

    def test_repetido_volta_depois_de_vencer(self):
        s = sec.Secretario(pasta=Path(tempfile.mkdtemp()))
        item = s.lembrar_por_frase("todo dia às 8h me lembre de tomar o remédio", agora=SEX)
        self.assertEqual(item["texto"], "tomar o remédio")
        self.assertEqual(item["repetir"], "diario")
        self.assertEqual(datetime.fromtimestamp(item["quando"]), datetime(2026, 9, 19, 8))
        vencidos = s.verificar(datetime(2026, 9, 19, 8, 0, 1).timestamp())
        self.assertEqual(len(vencidos), 1)
        pend = s.pendentes()
        self.assertEqual(len(pend), 1)                              # nao acabou
        self.assertEqual(datetime.fromtimestamp(pend[0]["quando"]), datetime(2026, 9, 20, 8))
        self.assertEqual(sec.falar_repeticao(pend[0]), "todos os dias às 8h")


def _comandos():
    s = sec.Secretario(pasta=Path(tempfile.mkdtemp()))
    rt = SimpleNamespace(secretario=s, prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}))
    return cmd.Comandos(rt, lambda x: None), s


class TestComandosLembrete(unittest.TestCase):
    def test_cancelar_so_o_citado(self):
        c, s = _comandos()
        amanha = datetime.now() + timedelta(days=1)
        s.lembrar("ligar para o Pedro", amanha.replace(hour=15, minute=0))
        s.lembrar("comprar pão", amanha.replace(hour=18, minute=0))
        frase = "cancele o lembrete de ligar para o Pedro"
        self.assertEqual(cmd.interpretar(frase)[0], "lembretes_cancelar")
        self.assertEqual(c.executar("lembretes_cancelar", {}, frase), "Cancelado: ligar para o Pedro.")
        self.assertEqual([x["texto"] for x in s.pendentes()], ["comprar pão"])

    def test_cancelar_ambiguo_pergunta(self):
        c, s = _comandos()
        amanha = datetime.now() + timedelta(days=1)
        s.lembrar("a", amanha.replace(hour=9, minute=0))
        s.lembrar("b", amanha.replace(hour=10, minute=0))
        fala = c.executar("lembretes_cancelar", {}, "cancele o lembrete")
        self.assertIn("Qual devo cancelar", fala)
        self.assertEqual(len(s.pendentes()), 2)                     # nada apagado por engano
        self.assertEqual(c.executar("lembretes_cancelar", {}, "cancele o lembrete das 10h"), "Cancelado: b.")
        self.assertEqual(c.executar("lembretes_cancelar", {}, "cancele todos os lembretes"), "Cancelado: a.")

    def test_cancelar_so_timers(self):
        c, s = _comandos()
        s.lembrar("Tempo esgotado", datetime.now() + timedelta(minutes=5), "timer")
        s.lembrar("reunião", datetime.now() + timedelta(hours=3))
        self.assertEqual(c.executar("lembretes_cancelar", {}, "cancele o timer"), "Cancelado: Tempo esgotado.")
        self.assertEqual([x["texto"] for x in s.pendentes()], ["reunião"])

    def test_adiar_e_remarcar(self):
        c, s = _comandos()
        base = (datetime.now() + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
        item = s.lembrar("ligar para o Pedro", base)
        frase = "adie o lembrete em 30 minutos"
        self.assertEqual(cmd.interpretar(frase)[0], "lembrete_adiar")
        self.assertIn("Adiado", c.executar("lembrete_adiar", {}, frase))
        self.assertEqual(datetime.fromtimestamp(s.pendentes()[0]["quando"]), base + timedelta(minutes=30))
        frase = "mude o lembrete das 15h para as 17h"
        self.assertEqual(cmd.interpretar(frase)[0], "lembrete_remarcar")
        self.assertIn("Mudado: ligar para o Pedro", c.executar("lembrete_remarcar", {}, frase))
        self.assertEqual(datetime.fromtimestamp(s.pendentes()[0]["quando"]).hour, 17)
        self.assertEqual(s.pendentes()[0]["id"], item["id"])

    def test_soneca_depois_de_tocar(self):
        c, s = _comandos()
        s.ultimo_vencido = {"texto": "Alarme", "tipo": "alarme", "vencido_em": time.time() - 30}
        frase = "Jarvis, mais 5 minutos"
        nome, args = cmd.interpretar(frase)
        self.assertEqual(nome, "lembrete_adiar")
        self.assertIn("Aviso de novo daqui a 5 minutos", c.executar(nome, args, frase))
        self.assertEqual(s.pendentes()[0]["texto"], "Alarme")

    def test_adiar_repetido_so_esta_vez(self):
        c, s = _comandos()
        amanha8 = (datetime.now() + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
        s.lembrar("remédio", amanha8, repetir="diario")
        fala = c.executar("lembrete_adiar", {}, "adie o lembrete do remédio em 20 minutos")
        self.assertIn("só desta vez", fala)
        horas = sorted(datetime.fromtimestamp(x["quando"]) for x in s.pendentes())
        self.assertEqual(horas, [amanha8 + timedelta(minutes=20), amanha8 + timedelta(days=1)])

    def test_criar_repetido_por_voz(self):
        c, s = _comandos()
        frase = "Jarvis, me lembre todo dia às 8h de tomar remédio"
        self.assertEqual(cmd.interpretar(frase)[0], "lembrete")
        self.assertEqual(c.executar("lembrete", {}, frase), "Certo. Vou lembrar todos os dias às 8h: tomar remédio.")


if __name__ == "__main__":
    unittest.main()
