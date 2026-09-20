"""Testes dos modulos novos do HUD (widgets, agenda, tarefas, notificacoes, voz local)."""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AQUI))
sys.path.append(str(AQUI / "_libs"))

from hud_runtime import agenda, audio, clima, preferencias, sistema  # noqa: E402
from hud_runtime.estado import Estado  # noqa: E402
from hud_runtime.notificacoes import Notificacoes, Vigia  # noqa: E402
from hud_runtime.tarefas import Tarefas  # noqa: E402
from hud_runtime.voz import contexto_sistema, detectar_intencao, hora_falada  # noqa: E402


def _ics(hoje: datetime) -> bytes:
    d = hoje.strftime("%Y%m%d")
    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//teste//PT
BEGIN:VEVENT
UID:1
SUMMARY:Reunião diária
DTSTART:{d}T090000
DTEND:{d}T093000
RRULE:FREQ=DAILY;COUNT=5
END:VEVENT
BEGIN:VEVENT
UID:2
SUMMARY:Aniversário
DTSTART;VALUE=DATE:{d}
DTEND;VALUE=DATE:{(hoje + timedelta(days=1)).strftime('%Y%m%d')}
END:VEVENT
BEGIN:VEVENT
UID:3
SUMMARY:Evento antigo
DTSTART:20000101T100000
DTEND:20000101T110000
END:VEVENT
END:VCALENDAR
""".encode()


class TestAgenda(unittest.TestCase):
    def test_recorrente_e_dia_inteiro_e_ignora_antigos(self):
        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).astimezone()
        evs = agenda.eventos_de(_ics(hoje), hoje, hoje + timedelta(days=3))
        titulos = [e["titulo"] for e in evs]
        self.assertEqual(titulos.count("Reunião diária"), 3)      # 3 dias da janela
        self.assertIn("Aniversário", titulos)
        self.assertNotIn("Evento antigo", titulos)
        self.assertTrue(next(e for e in evs if e["titulo"] == "Aniversário")["dia_inteiro"])

    def test_url_webcal_vira_https_e_http_e_recusado(self):
        self.assertEqual(agenda.normalizar_url("webcal://x.com/a.ics"), "https://x.com/a.ics")
        with self.assertRaises(ValueError):
            agenda.normalizar_url("http://x.com/a.ics")

    def test_segredo_nunca_aparece_no_erro(self):
        with tempfile.TemporaryDirectory() as d:
            agenda.SEGREDOS = Path(d) / "s.json"
            ag = agenda.Agenda()
            ag.definir("https://invalido.invalid/segredo123.ics")
            r = ag.obter(forcar=True)
            self.assertEqual(r["status"], "erro")
            self.assertNotIn("segredo123", str(r))


class TestTarefas(unittest.TestCase):
    def test_ciclo_completo_e_persistencia(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "t.json"
            mudancas = []
            t = Tarefas(arq, ao_mudar=mudancas.append)
            a = t.adicionar("  comprar   pão ")
            self.assertEqual(a["texto"], "comprar pão")
            t.adicionar("ligar para o banco")
            t.alternar(a["id"])
            self.assertTrue(Tarefas(arq).listar()[0]["feita"])    # persistiu
            self.assertEqual(t.concluir_por_texto("banco")["texto"], "ligar para o banco")
            self.assertEqual(t.limpar_feitas(), 2)
            self.assertEqual(t.listar(), [])
            self.assertTrue(mudancas)
            with self.assertRaises(ValueError):
                t.adicionar("   ")


class TestNotificacoes(unittest.TestCase):
    def _amostra(self, **k):
        base = {"sistema": {"bateria": {"status": "medido", "percentual": 50, "na_tomada": True},
                            "memoria": {"status": "medido", "uso_pct": 50, "livre_gb": 5},
                            "disco": {"status": "medido", "livre_gb": 80, "unidade": "C:"}},
                "servidor": {"status": "ok"}, "ollama": {"status": "ok"},
                "arquivos": {"downloads": {"status": "medido", "em_andamento": [], "recentes": []}}}
        for chave, valor in k.items():
            base["sistema"][chave] = valor
        return base

    def test_so_avisa_em_mudanca_real_e_sem_repetir(self):
        e = Estado()
        n = Notificacoes(e)
        v = Vigia(n)
        v.observar(self._amostra())
        self.assertEqual(e.ler("notificacoes")["itens"], [])          # nada mudou, nada avisado
        baixa = {"status": "medido", "percentual": 15, "na_tomada": False, "restante_min": 20}
        v.observar(self._amostra(bateria=baixa))
        v.observar(self._amostra(bateria=baixa))                       # repetida: nao duplica
        textos = [i["texto"] for i in e.ler("notificacoes")["itens"]]
        self.assertEqual(sum("Bateria baixa" in t for t in textos), 1)
        self.assertIn("Carregador desconectado.", textos)

    def test_servico_caiu_e_download_concluido(self):
        e = Estado()
        v = Vigia(Notificacoes(e))
        a = self._amostra()
        a["arquivos"]["downloads"]["em_andamento"] = [{"nome": "video.mp4.crdownload"}]
        v.observar(a)
        b = self._amostra()
        b["servidor"] = {"status": "fora"}
        b["arquivos"]["downloads"]["recentes"] = [{"nome": "video.mp4"}]
        v.observar(b)
        textos = [i["texto"] for i in e.ler("notificacoes")["itens"]]
        self.assertIn("Servidor OpenJarvis parou de responder.", textos)
        self.assertIn("Download concluído: video.mp4", textos)


class TestVozLocal(unittest.TestCase):
    def test_intencoes(self):
        casos = {
            "Jarvis, que horas são?": ("horas", None),
            "Jarvis, que dia é hoje": ("data", None),
            "Jarvis, vai chover amanhã?": ("clima", None),
            "Jarvis, como está a bateria": ("bateria", None),
            "Jarvis, adicione a tarefa comprar pão.": ("adicionar", "comprar pão"),
            "Jarvis anota tarefa: pagar a conta de luz": ("adicionar", "pagar a conta de luz"),
            "Jarvis, marque a tarefa pão como feita": ("concluir", "pão"),
            "Jarvis, quais são minhas tarefas?": ("listar", None),
        }
        for frase, esperado in casos.items():
            self.assertEqual(detectar_intencao(frase), esperado, frase)
        self.assertIsNone(detectar_intencao("Jarvis, me conte uma piada"))   # vai para o modelo

    def test_contexto_tem_data_e_hora_reais(self):
        d = datetime(2026, 9, 17, 23, 35)
        s = contexto_sistema("Em Campinas, 20 graus.", agora=d)
        self.assertIn("23:35", s)
        self.assertIn("quinta-feira, 17 de setembro de 2026", s)
        self.assertIn("Campinas", s)
        self.assertEqual(hora_falada(d), "23 e 35")


class TestDiversos(unittest.TestCase):
    def test_forma_de_onda_preserva_sinal(self):
        onda = audio.forma_de_onda(np.sin(np.linspace(0, 2 * np.pi, 960)).astype(np.float32), 48)
        self.assertEqual(len(onda), 48)
        self.assertGreater(max(onda), 0.9)
        self.assertLess(min(onda), -0.9)

    def test_regex_da_instancia_de_gpu(self):
        m = sistema._INSTANCIA_GPU.search("pid_1234_luid_0x00000000_0x0000D0F0_phys_0_eng_3_engtype_3D")
        self.assertEqual((m.group(1), m.group(2), m.group(3)), ("0x00000000_0x0000D0F0", "3", "3D"))

    def test_clima_descreve_codigos_wmo(self):
        self.assertEqual(clima._descrever(61), ("Chuva fraca", "chuva"))
        self.assertEqual(clima._descrever(None)[0], "—")
        self.assertEqual(clima.Clima().obter(None)["status"], "nao_configurado")

    def test_preferencias_novas_validadas(self):
        p = preferencias.validar({"local_clima": {"nome": "Campinas", "lat": -22.9, "lon": -47.06},
                                  "pastas_monitoradas": ["C:\\x", 3, "  "],
                                  "estilo_nucleo": "reator", "camera_ao_iniciar": "sim"})
        self.assertEqual(p["local_clima"]["nome"], "Campinas")
        self.assertEqual(p["pastas_monitoradas"], ["C:\\x"])
        self.assertEqual(p["estilo_nucleo"], "reator")
        self.assertFalse(p["camera_ao_iniciar"])                        # string nao vira bool
        ruim = preferencias.validar({"local_clima": {"nome": "X", "lat": 999, "lon": 0}})
        self.assertIsNone(ruim["local_clima"])


if __name__ == "__main__":
    unittest.main()
