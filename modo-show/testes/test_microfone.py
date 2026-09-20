"""Microfone: bloqueio de privacidade do Windows e novas tentativas."""

import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime import audio  # noqa: E402


class _Estado:
    def __init__(self):
        self.estados, self.logs = [], []

    def atualizar(self, secao, **kw):
        if secao == "microfone" and "estado" in kw:
            self.estados.append(kw["estado"])

    def registrar(self, _secao, texto, _nivel="info"):
        self.logs.append(texto)

    def nivel(self, *a, **kw):
        pass


def _winreg(valores):
    """winreg falso: valores = {(raiz, sub): "Allow"|"Deny"}."""
    class Chave:
        def __init__(self, v):
            self.v = v

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def abrir(raiz, sub):
        if (raiz, sub) not in valores:
            raise OSError("sem chave")
        return Chave(valores[(raiz, sub)])

    return SimpleNamespace(HKEY_LOCAL_MACHINE="HKLM", HKEY_CURRENT_USER="HKCU", OpenKey=abrir,
                           QueryValueEx=lambda k, _n: (k.v, 1))


class TestBloqueio(unittest.TestCase):
    def test_leitura_do_registro(self):
        sub = audio.CONSENTIMENTO_MIC
        casos = [({("HKLM", sub): "Deny", ("HKCU", sub): "Allow"}, "neste dispositivo"),
                 ({("HKLM", sub): "Allow", ("HKCU", sub): "Deny"}, "para este usuário"),
                 ({("HKCU", sub + r"\NonPackaged"): "Deny"}, "área de trabalho"),
                 ({("HKLM", sub): "Allow", ("HKCU", sub): "Allow"}, None),
                 ({}, None)]                                    # sem chaves: nao inventa bloqueio
        for valores, esperado in casos:
            with mock.patch.dict(sys.modules, {"winreg": _winreg(valores)}):
                r = audio.bloqueio_privacidade()
            if esperado is None:
                self.assertIsNone(r, valores)
            else:
                self.assertIn(esperado, r)
                self.assertIn("Privacidade e segurança > Microfone", r)


class TestNovasTentativas(unittest.TestCase):
    def _mic(self):
        est = _Estado()
        m = audio.Microfone(est, ocupado=lambda: False)
        m.ESPERA_BLOQUEIO_S = 0.01
        m.ESPERA_ERRO_S = (0.01, 0.01, 0.01)
        return m, est

    def test_bloqueado_espera_e_reabre(self):
        m, est = self._mic()
        chamadas = []
        bloqueios = iter(["acesso desligado", "acesso desligado", None])
        abriu = threading.Event()

        def sessao():
            chamadas.append(1)
            if len(chamadas) == 1:
                raise RuntimeError("MME error 1")
            abriu.set()
            m.encerrar()

        with mock.patch.object(audio, "bloqueio_privacidade", lambda: next(bloqueios)), \
             mock.patch.object(audio, "reiniciar_portaudio", lambda: None), \
             mock.patch.object(m, "_sessao", sessao):
            m.ativar()
            m.start()
            self.assertTrue(abriu.wait(3))
            m.join(3)
        self.assertEqual(len(chamadas), 2)
        self.assertIn("bloqueado", est.estados)
        self.assertTrue(any("liberado" in t for t in est.logs))
        self.assertNotIn("desativado", est.estados[:-1])      # nao desligou enquanto esperava

    def test_erro_comum_tenta_de_novo_e_depois_desliga(self):
        m, est = self._mic()
        chamadas = []
        desligou = threading.Event()

        def sessao():
            chamadas.append(1)
            raise RuntimeError("dispositivo ocupado")

        def atualizar(secao, **kw):
            _Estado.atualizar(est, secao, **kw)
            if kw.get("estado") == "desativado":
                desligou.set()

        est.atualizar = atualizar
        with mock.patch.object(audio, "bloqueio_privacidade", lambda: None), \
             mock.patch.object(audio, "reiniciar_portaudio", lambda: None), \
             mock.patch.object(m, "_sessao", sessao):
            m.ativar()
            m.start()
            self.assertTrue(desligou.wait(3))
            m.encerrar()
            m.join(3)
        self.assertEqual(len(chamadas), 1 + len(m.ESPERA_ERRO_S))
        self.assertFalse(m.ativo is True and not m._encerrar.is_set())


class TestSaudacao(unittest.TestCase):
    def test_bloqueio_explica_em_vez_de_mandar_usar_o_chat(self):
        from hud_runtime.boot import saudacao
        ok = {"servidor": True, "microfone": False}
        frase = saudacao("Senhor", ok, escutando=False, mic_bloqueado=True)
        self.assertIn("Windows está bloqueando o microfone", frase)
        self.assertNotIn("Estou ouvindo", frase)
        self.assertIn("use o chat", saudacao("Senhor", ok, escutando=False))


if __name__ == "__main__":
    unittest.main()
