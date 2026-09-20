"""Agenda: conflitos e horarios livres (G1); persona do Chat sem sobrescrever
(A9); parecer falado no boot a partir das medidas (H3)."""

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime import agenda_analise as ag, openjarvis_info  # noqa: E402
from hud_runtime.boot import parecer, saudacao  # noqa: E402

DIA = datetime(2026, 9, 21)


def ev(titulo, h1, m1, h2, m2, dia_inteiro=False):
    return {"titulo": titulo, "inicio": DIA.replace(hour=h1, minute=m1).timestamp(),
            "fim": DIA.replace(hour=h2, minute=m2).timestamp(), "dia_inteiro": dia_inteiro}


EVENTOS = [ev("Reunião Aurora", 9, 0, 10, 0), ev("Dentista", 9, 30, 10, 30), ev("Almoço", 12, 0, 13, 0),
           ev("Feriado", 0, 0, 23, 59, dia_inteiro=True), ev("Aula", 17, 0, 19, 0)]


class TestAgenda(unittest.TestCase):
    def test_conflitos(self):
        pares = ag.conflitos(EVENTOS, DIA)
        self.assertEqual([(a["titulo"], b["titulo"]) for a, b in pares], [("Reunião Aurora", "Dentista")])
        fala = ag.fala_conflitos({"status": "medido", "eventos": EVENTOS}, DIA, "segunda")
        self.assertEqual(fala, "1 conflito segunda: Reunião Aurora às 9h bate com Dentista às 9h30.")

    def test_livres(self):
        livres = ag.horarios_livres(EVENTOS, DIA)
        self.assertEqual([(a.strftime("%H:%M"), b.strftime("%H:%M")) for a, b in livres],
                         [("08:00", "09:00"), ("10:30", "12:00"), ("13:00", "17:00")])
        agora = DIA.replace(hour=14, minute=20)
        self.assertEqual(ag.fala_livres({"status": "medido", "eventos": EVENTOS}, DIA, "hoje", agora=agora),
                         "Livre hoje: das 14h20 às 17h.")

    def test_agenda_desconectada_nao_e_vazia(self):
        nc = {"status": "nao_configurado"}
        self.assertIn("não está conectada", ag.fala_conflitos(nc, DIA, "hoje"))
        self.assertIn("não está conectada", ag.fala_livres(nc, DIA, "hoje"))
        self.assertNotIn("Nenhum", ag.fala_livres({"status": "erro"}, DIA, "hoje"))


class TestPersona(unittest.TestCase):
    def test_cria_so_o_que_falta_sem_inventar(self):
        home = Path(tempfile.mkdtemp())
        (home / "SOUL.md").write_text("minha persona", encoding="utf-8")
        with mock.patch.object(openjarvis_info, "HOME", home):
            r = openjarvis_info.criar_persona({"nome_usuario": "Senhor", "local_clima": {"nome": "São Paulo"},
                                               "climas_extras": [{"nome": "Angatuba"}]})
            self.assertEqual(r["criados"], ["USER.md"])
            self.assertEqual((home / "SOUL.md").read_text(encoding="utf-8"), "minha persona")     # nao sobrescreveu
            user = (home / "USER.md").read_text(encoding="utf-8")
            self.assertIn("Como chamar: Senhor", user)
            self.assertIn("São Paulo, Angatuba", user)
            self.assertEqual(openjarvis_info.criar_persona({})["criados"], [])


class TestParecer(unittest.TestCase):
    def test_parecer_medido(self):
        etapas = [{"id": "servidor", "estado": "ok"}, {"id": "memoria", "estado": "aviso"},
                  {"id": "microfone", "estado": "falha"}, {"id": "ollama", "estado": "ok"}]
        avisos = parecer(etapas)
        self.assertEqual(avisos, ["a memória do computador está apertada, então posso demorar para responder"])
        frase = saudacao("Senhor", {"servidor": True, "microfone": True, "memoria": False}, True, avisos=avisos)
        self.assertIn("Atenção: a memória do computador está apertada", frase)
        self.assertNotIn("Todas as verificações passaram", frase)                 # nada de "tudo verde" falso
        self.assertNotIn("Atenção", saudacao("Senhor", {"servidor": True, "microfone": True}, True, avisos=[]))


if __name__ == "__main__":
    unittest.main()
