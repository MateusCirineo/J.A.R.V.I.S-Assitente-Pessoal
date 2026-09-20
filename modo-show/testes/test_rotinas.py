"""Rotinas de chegada/descanso (R1-R4): frase exata, sem duplicar, fechar com
WM_CLOSE so os apps da rotina, bloquear/suspender so com confirmacao."""

import subprocess
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "_libs"))

from hud_runtime import comandos as cmd, rotinas  # noqa: E402
from hud_runtime.preferencias import PADRAO, validar  # noqa: E402


class _Prefs:
    def __init__(self, **extra):
        self.d = validar({"nome_usuario": "Senhor", **extra})

    def ler(self):
        return dict(self.d)


def _rt(**prefs):
    return SimpleNamespace(prefs=_Prefs(**prefs), anunciador=mock.Mock(), camera=SimpleNamespace(ativa=True, desativar=mock.Mock()),
                           estado=mock.Mock(), reprodutor=mock.Mock(),
                           comandos=SimpleNamespace(briefing=lambda: "Boa tarde, Senhor. São 16h. Céu limpo."))


class TestFrases(unittest.TestCase):
    def test_so_frase_inteira(self):
        p = PADRAO
        self.assertEqual(rotinas.frase_da_rotina("Jarvis, cheguei!", p), "chegada")
        self.assertEqual(rotinas.frase_da_rotina("vou descansar, Jarvis", p), "descanso")
        for parcial in ("cheguei atrasado na reunião", "quando eu for descansar me avise", "hora de"):
            self.assertIsNone(rotinas.frase_da_rotina(parcial, p), parcial)
        meu = validar({"rotina_chegada": {"frases": ["acorda criança, papai chegou"]}})
        self.assertEqual(rotinas.frase_da_rotina("Jarvis, acorda criança papai chegou", meu), "chegada")
        self.assertIsNone(rotinas.frase_da_rotina("cheguei", meu))            # trocou as frases: as antigas saem

    def test_validacao(self):
        v = validar({"rotina_chegada": {"sites": ["http://inseguro.com", "https://g1.globo.com"], "volume": 300,
                                        "apps": ["Spotify"], "lixo": 1},
                     "rotina_descanso": {"acao_final": "formatar_disco", "fechar_apps": "sim"}})
        self.assertEqual(v["rotina_chegada"]["sites"], ["https://g1.globo.com"])
        self.assertIsNone(v["rotina_chegada"]["volume"])
        self.assertNotIn("lixo", v["rotina_chegada"])
        self.assertEqual(v["rotina_descanso"]["acao_final"], "nada")
        self.assertTrue(v["rotina_descanso"]["fechar_apps"])                  # texto nao vira booleano


class TestChegadaDescanso(unittest.TestCase):
    APPS = {"spotify": ("spotify", "Spotify.exe"), "vs code": ("visual studio code", r"C:\VS\Code.exe")}

    def achar(self, nome):
        return self.APPS.get(nome.lower())

    def test_chegada_nao_duplica(self):
        rt = _rt(rotina_chegada={"apps": ["Spotify", "VS Code", "Xyz"], "sites": ["https://g1.globo.com"]})
        r = rotinas.Rotinas(rt, self.achar)
        with mock.patch("os.startfile") as sf, \
             mock.patch.object(rotinas, "rodando", side_effect=lambda exe: exe == "spotify.exe"):
            fala = r.chegada()
        abertos = [c.args[0] for c in sf.call_args_list]
        self.assertEqual(abertos, [r"shell:AppsFolder\C:\VS\Code.exe", "https://g1.globo.com"])
        self.assertIn("Bem-vindo de volta, Senhor.", fala)
        self.assertIn("Spotify já estava aberto", fala)
        self.assertIn("Não achei Xyz", fala)
        self.assertIn("São 16h", fala)                                        # resumo, sem repetir o "Boa tarde"
        self.assertNotIn("Boa tarde", fala)

    def test_descanso_fecha_so_os_da_rotina_e_pede_confirmacao(self):
        rt = _rt(rotina_chegada={"apps": ["Spotify", "VS Code"]}, rotina_descanso={"acao_final": "bloquear"})
        r = rotinas.Rotinas(rt, self.achar)
        pedidos = []

        def fechar(exe, espera_s=6.0):
            pedidos.append(exe)
            return (1, 1) if exe == "code.exe" else (1, 0)                 # VS Code pediu para salvar
        with mock.patch.object(rotinas, "fechar_graciosamente", fechar), \
             mock.patch("hud_runtime.midia.estado_midia", return_value={"status": "medido", "situacao": "parado"}):
            fala, acao = r.descanso()
        self.assertEqual(pedidos, ["spotify.exe", "code.exe"])
        self.assertIn("Fechei Spotify", fala)
        self.assertIn("VS Code pediu para salvar", fala)
        self.assertEqual(acao, "bloquear")
        self.assertIn("confirmo bloquear", fala)
        rt.camera.desativar.assert_called_once()

    def test_protegidos_nunca(self):
        with mock.patch.object(rotinas, "janelas_do_exe") as j:
            self.assertEqual(rotinas.fechar_graciosamente("explorer.exe"), (0, 0))
            j.assert_not_called()


class TestConfirmacao(unittest.TestCase):
    def test_bloquear_so_com_pedido_valido(self):
        rt = _rt(rotina_descanso={"acao_final": "bloquear"})
        c = cmd.Comandos(rt, lambda x: None)
        self.assertEqual(c.interpretar("Jarvis, confirmo bloquear")[0], "confirmar_acao")
        with mock.patch.object(rotinas, "bloquear", return_value=True) as b:
            self.assertIn("Não havia pedido", c.executar("confirmar_acao", {"acao": "bloquear"}, ""))
            b.assert_not_called()
            with mock.patch.object(rotinas.Rotinas, "descanso", return_value=("ok", "bloquear")):
                nome, args = c.interpretar("Jarvis, vou descansar")
                c.executar(nome, args, "")
            self.assertIn("Não havia pedido para suspender", c.executar("confirmar_acao", {"acao": "suspender"}, ""))
            self.assertEqual(c.executar("confirmar_acao", {"acao": "bloquear"}, ""), "Bloqueando.")
            b.assert_called_once()
            self.assertIn("Não havia pedido", c.executar("confirmar_acao", {"acao": "bloquear"}, ""))   # vale uma vez


class TestJanelaReal(unittest.TestCase):
    def test_wm_close_fecha_janela_de_teste(self):
        """Janela Tk descartavel, num processo proprio: nada do usuario e tocado."""
        proc = subprocess.Popen([sys.executable, "-c",
                                 "import tkinter as t; r = t.Tk(); r.title('jarvis-teste-rotina'); r.geometry('300x200'); r.mainloop()"])
        try:
            janelas = []
            fim = time.time() + 15
            while not janelas and time.time() < fim:
                time.sleep(0.3)
                import psutil                                      # o python do venv e um lancador:
                pids = {proc.pid} | {c.pid for c in psutil.Process(proc.pid).children(recursive=True)}
                janelas = rotinas.janelas_de_pids(pids)                # a janela e do processo filho
            self.assertEqual(len(janelas), 1)
            self.assertEqual(rotinas.fechar_janelas(janelas, 6), (1, 0))
            self.assertEqual(proc.wait(10), 0)                                 # saiu sozinho, sem kill
        finally:
            if proc.poll() is None:
                proc.kill()


if __name__ == "__main__":
    unittest.main()
