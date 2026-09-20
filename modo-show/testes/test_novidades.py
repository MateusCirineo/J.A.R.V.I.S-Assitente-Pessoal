"""Testes das partes novas: cidades extras, agenda Google, avisos do Windows,
leitor de sensores, energia por resposta, agenda por voz e tratamento."""

import json
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "_libs"))

from hud_runtime import agenda, google_agenda, sistema  # noqa: E402
from hud_runtime.avisos_windows import vai_para_o_windows, xml_toast  # noqa: E402
from hud_runtime.clima import Clima, achar_locais  # noqa: E402
from hud_runtime.estado import Estado  # noqa: E402
from hud_runtime.notificacoes import Notificacoes  # noqa: E402
from hud_runtime.ponte import Ponte  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402
from hud_runtime.voz import contexto_sistema, detectar_intencao, resumo_agenda  # noqa: E402

SP = {"nome": "São Paulo", "lat": -23.5, "lon": -46.6, "regiao": "São Paulo", "pais": "Brasil"}
ANG = {"nome": "Angatuba", "lat": -23.49, "lon": -48.41, "regiao": "São Paulo", "pais": "Brasil"}


class TestClima(unittest.TestCase):
    def test_cidade_citada_sem_acento(self):
        self.assertEqual(achar_locais("jarvis, como está o clima em angatuba?", [SP, ANG]), [ANG])
        self.assertEqual(achar_locais("clima em sao paulo", [SP, ANG]), [SP])
        self.assertEqual(achar_locais("vai chover?", [SP, ANG]), [])

    def test_cache_por_cidade(self):
        c = Clima()
        chamadas = []

        def falsa(lat, lon):
            chamadas.append((lat, lon))
            return {"atual": {"temperatura": 20, "descricao": "Nublado"}, "dias": []}

        with mock.patch("hud_runtime.clima.previsao", falsa):
            d = c.obter_todos(SP, [ANG])
            c.obter_todos(SP, [ANG])                  # segunda vez: tudo do cache
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(d["local"]["nome"], "São Paulo")
        self.assertEqual([o["local"]["nome"] for o in d["outros"]], ["Angatuba"])

    def test_resumo_curto_sem_previsao(self):
        c = Clima()
        with mock.patch("hud_runtime.clima.previsao", lambda la, lo: {
                "atual": {"temperatura": 15.4, "descricao": "Parcialmente nublado"},
                "dias": [{"min": 13, "max": 23, "chuva_pct": 4}]}):
            self.assertEqual(c.resumo_falado(ANG, curto=True), "Em Angatuba, 15 graus, parcialmente nublado.")
            self.assertIn("máxima de 23", c.resumo_falado(ANG))

    def test_preferencia_extras_valida(self):
        p = validar({"climas_extras": [ANG, {"nome": "x", "lat": 999, "lon": 0}, "lixo", SP, ANG, SP]})
        self.assertEqual([c["nome"] for c in p["climas_extras"]], ["Angatuba", "São Paulo"])   # so validas, sem repetir
        self.assertEqual(p["climas_extras"][0]["nome"], "Angatuba")


class TestAgendaGoogle(unittest.TestCase):
    def test_cliente_validado(self):
        with self.assertRaises(ValueError):
            google_agenda.validar_cliente("abc", "segredo-grande")
        with self.assertRaises(ValueError):
            google_agenda.validar_cliente("1-x.apps.googleusercontent.com", "curto")
        self.assertEqual(google_agenda.validar_cliente(" 1-x.apps.googleusercontent.com ", " GOCSPX-abcdef123 "),
                         ("1-x.apps.googleusercontent.com", "GOCSPX-abcdef123"))

    def test_url_de_login_so_leitura_com_pkce(self):
        g = google_agenda.GoogleAgenda(8765)
        with mock.patch.object(g, "cliente", return_value={"id": "1-x.apps.googleusercontent.com", "chave": "k" * 20}):
            url = g.url_login()
        self.assertIn("calendar.readonly", url)
        self.assertIn("gmail.metadata", url)          # so remetente/assunto
        for amplo in ("gmail.readonly", "gmail.modify", "drive", "contacts", "auth%2Fcalendar+"):
            self.assertNotIn(amplo, url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("redirect_uri=http%3A%2F%2F127.0.0.1%3A8765%2Foauth%2Fgoogle", url)
        self.assertEqual(len(g._pedidos), 1)

    def test_state_desconhecido_recusado(self):
        g = google_agenda.GoogleAgenda(8765)
        with self.assertRaises(google_agenda.ErroGoogle):
            g.concluir_login("codigo", "state-inventado")

    def test_converter_eventos(self):
        dia = google_agenda.converter_evento({"summary": "Feriado", "start": {"date": "2026-09-18"},
                                              "end": {"date": "2026-09-19"}}, "Pessoal")
        self.assertTrue(dia["dia_inteiro"])
        self.assertEqual(dia["agenda"], "Pessoal")
        hora = google_agenda.converter_evento({"summary": "Reunião", "start": {"dateTime": "2026-09-18T14:00:00-03:00"},
                                               "end": {"dateTime": "2026-09-18T15:00:00-03:00"}})
        self.assertEqual(hora["fim"] - hora["inicio"], 3600)
        self.assertIsNone(google_agenda.converter_evento({"status": "cancelled", "start": {}}))

    def test_email_do_id_token(self):
        import base64
        corpo = base64.urlsafe_b64encode(json.dumps({"email": "a@b.com"}).encode()).rstrip(b"=").decode()
        self.assertEqual(google_agenda._email_do_id_token(f"x.{corpo}.y"), "a@b.com")
        self.assertIsNone(google_agenda._email_do_id_token(None))

    def test_pagina_do_google_nao_e_ical(self):
        with self.assertRaises(ValueError) as e:
            agenda.normalizar_url("https://calendar.google.com/calendar/u/0/r")
        self.assertIn("iCal", str(e.exception))
        self.assertTrue(agenda.normalizar_url("webcal://calendar.google.com/calendar/ical/x/private-y/basic.ics")
                        .startswith("https://"))
        with self.assertRaises(ValueError):
            agenda.ler_ics("https://calendar.google.com/calendar/u/0/r", datetime.now(), datetime.now())


class TestAvisosWindows(unittest.TestCase):
    def test_xml_escapado(self):
        x = xml_toast('Download concluído: <a&b>.pdf', "aviso")
        self.assertIn("&lt;a&amp;b&gt;", x)
        self.assertIn("Jarvis · aviso", x)

    def test_filtro(self):
        self.assertTrue(vai_para_o_windows({"nivel": "erro", "texto": "x"}))
        self.assertTrue(vai_para_o_windows({"nivel": "info", "tipo": "agenda", "texto": "Em 5 min: x"}))
        self.assertTrue(vai_para_o_windows({"nivel": "info", "texto": "Download concluído: a.zip"}))
        self.assertFalse(vai_para_o_windows({"nivel": "info", "texto": "Servidor OpenJarvis voltou."}))

    def test_callback_de_notificacao(self):
        vistos = []
        n = Notificacoes(Estado(), ao_notificar=vistos.append)
        n.notificar("Memória quase cheia", "aviso", "sistema", "ram", 600)
        n.notificar("Memória quase cheia", "aviso", "sistema", "ram", 600)   # repetido: filtrado
        self.assertEqual([v["texto"] for v in vistos], ["Memória quase cheia"])

    def test_callback_com_erro_nao_derruba(self):
        def ruim(_):
            raise RuntimeError("sem toast")
        self.assertTrue(Notificacoes(Estado(), ao_notificar=ruim).notificar("x", "erro"))


class TestSensores(unittest.TestCase):
    def _arquivo(self, dados):
        d = tempfile.mkdtemp()
        p = Path(d) / "sensores.json"
        p.write_text(json.dumps(dados), encoding="utf-8")
        return p

    def test_leitura_recente(self):
        p = self._arquivo({"em": time.time(), "temperaturas_c": {"CPU Package": 61.5},
                           "potencias_w": {"CPU Package": 9.2}, "energia_pacote_j": 1234.5})
        d = sistema.sensores(p)
        self.assertEqual(sistema.temperatura_sensores(d)["celsius"], 61.5)
        e = sistema.energia_cpu(d)
        self.assertEqual((e["status"], e["potencia_w"], e["energia_j"]), ("medido", 9.2, 1234.5))

    def test_leitura_velha_ou_ausente(self):
        p = self._arquivo({"em": time.time() - 60, "temperaturas_c": {"CPU Package": 60}})
        self.assertIsNone(sistema.sensores(p))
        self.assertIsNone(sistema.sensores(Path(tempfile.mkdtemp()) / "nao-existe.json"))
        self.assertEqual(sistema.energia_cpu({})["status"], "indisponivel")
        # sem driver a biblioteca devolve 0: nao vira "0 W medido"
        self.assertEqual(sistema.energia_cpu({"potencias_w": {"CPU Package": 0}})["status"], "indisponivel")
        self.assertIsNone(sistema.temperatura_sensores({"temperaturas_c": {}}))


class TestEnergiaPorResposta(unittest.TestCase):
    def test_energia_entre_inicio_e_fim(self):
        e = Estado()
        leituras = iter([100.0, 412.5])
        p = Ponte(e, medidor=lambda: next(leituras))
        for tipo in ("inference_start", "inference_start"):
            p.processar({"type": tipo, "data": {"model": "m"}})
        p.processar({"type": "inference_end", "data": {"model": "m", "latency": 2.0}})
        p.processar({"type": "inference_end", "data": {}})
        eu = e.ler("inferencia")["energia_ultima"]
        self.assertEqual(eu["joules"], 312.5)
        self.assertIn("medido", eu["fonte"])

    def test_sem_medidor_sem_energia(self):
        e = Estado()
        p = Ponte(e)
        p.processar({"type": "inference_start", "data": {"model": "m"}})
        p.processar({"type": "inference_end", "data": {}})
        self.assertNotIn("energia_ultima", e.ler("inferencia"))


class TestAmostra(unittest.TestCase):
    def test_amostra_completa_sem_erro(self):
        # pegou um NameError real: a amostra rapida quebrava inteira
        from hud_runtime import telemetria
        with mock.patch.object(telemetria, "ollama", lambda: {"status": "fora"}), \
             mock.patch.object(telemetria, "servidor", lambda: {"status": "fora"}):
            d = telemetria.Amostrador(Estado()).amostrar()
        self.assertIn("energia_cpu", d["sistema"])
        self.assertIn("temperatura", d["sistema"])


class TestVoz(unittest.TestCase):
    def test_intencao_agenda(self):
        for frase in ("Jarvis, o que tenho hoje?", "Jarvis, minha agenda", "tenho reunião?"):
            self.assertEqual(detectar_intencao(frase)[0], "agenda", frase)

    def test_resumo_agenda(self):
        agora = datetime(2026, 9, 18, 10, 0)
        ts = lambda h: datetime(2026, 9, 18, h, 0).timestamp()  # noqa: E731
        ag = {"status": "medido", "eventos": [
            {"titulo": "Dentista", "inicio": ts(14), "fim": ts(15), "dia_inteiro": False},
            {"titulo": "Antiga", "inicio": ts(8), "fim": ts(9), "dia_inteiro": False}]}
        frase = resumo_agenda(ag, agora)
        self.assertIn("Dentista às 14 horas", frase)
        self.assertNotIn("Antiga", frase)                         # ja passou
        self.assertIn("não tem compromissos amanhã", resumo_agenda(ag, agora, amanha=True))
        self.assertIn("não está conectada", resumo_agenda({"status": "nao_configurado"}, agora))

    def test_tratamento(self):
        self.assertIn('Dirija-se ao usuário como "Senhor"', contexto_sistema(tratamento="Senhor"))
        self.assertNotIn("Dirija-se", contexto_sistema())


if __name__ == "__main__":
    unittest.main()
