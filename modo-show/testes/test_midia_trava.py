"""Regressao (18/09): a API de midia do Windows travou e congelou a telemetria
inteira (clima, sistema e noticias sumiram). Agora ela nunca bloqueia."""

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "_libs"))

from hud_runtime import midia  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402


class TestMidiaNaoTrava(unittest.TestCase):
    def setUp(self):
        self._salvo = (midia._leitor, dict(midia._cache))
        midia._leitor = None
        midia._cache.update(valor={"status": "aguardando"}, em=0.0)

    def tearDown(self):
        midia._leitor = self._salvo[0]
        midia._cache.update(self._salvo[1])

    def test_windows_travado_nao_segura_ninguem(self):
        liberar = threading.Event()
        with mock.patch.object(midia, "_ler_uma_vez", lambda: (liberar.wait(60), {"status": "medido"})[1]):
            t0 = time.time()
            r = midia.estado_midia()
            self.assertLess(time.time() - t0, 3)                          # so a primeira espera, e pouco
            self.assertEqual(r["status"], "erro")
            t0 = time.time()
            midia.estado_midia()
            self.assertLess(time.time() - t0, 0.2)                        # as seguintes voltam na hora
            liberar.set()

    def test_valor_recente_volta_do_cache(self):
        with mock.patch.object(midia, "_ler_uma_vez", lambda: {"status": "medido", "titulo": "Back in Black"}):
            self.assertEqual(midia.estado_midia()["titulo"], "Back in Black")


class TestCidadesSemRepetir(unittest.TestCase):
    def test_extras_sem_duplicar_nem_repetir_a_principal(self):
        sp = {"nome": "São Paulo", "lat": -23.5475, "lon": -46.6361}
        ang = {"nome": "Angatuba", "lat": -23.4897, "lon": -48.4128}
        p = validar({"local_clima": sp, "climas_extras": [ang, sp, sp, ang]})
        self.assertEqual([c["nome"] for c in p["climas_extras"]], ["Angatuba"])


if __name__ == "__main__":
    unittest.main()
