"""Rascunhos de comunicacao (G2): redige, copia, guarda, nunca envia."""

import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime import comandos as cmd, rascunhos  # noqa: E402


class TestRascunhos(unittest.TestCase):
    def test_rotas(self):
        casos = {"Jarvis, escreva um e-mail para o Pedro dizendo que vou atrasar": "rascunho",
                 "prepare uma mensagem para a Ana sobre a reunião": "rascunho",
                 "abra o rascunho no Gmail": "rascunho_gmail",
                 "Jarvis, leia meus e-mails": "emails", "tenho e-mails novos?": "emails"}
        for frase, esperado in casos.items():
            self.assertEqual(cmd.interpretar(frase)[0], esperado, frase)

    def test_criar_separa_assunto_copia_e_grava(self):
        pasta = Path(tempfile.mkdtemp())
        pedidos, copias = [], []
        modelo = "<think>ok</think>Assunto: Atraso na reunião\n\nOlá, Pedro,\n\nVou atrasar 20 minutos.\n\n[seu nome]"
        r = rascunhos.Rascunhos(lambda m: pedidos.append(m) or modelo, pasta,
                                copiar_fn=lambda t: copias.append(t) or True).criar(
            "escreva um e-mail para o Pedro dizendo que vou atrasar 20 minutos")
        self.assertEqual((r["tipo"], r["para"], r["assunto"]), ("email", "Pedro", "Atraso na reunião"))
        self.assertTrue(r["corpo"].startswith("Olá, Pedro"))
        self.assertNotIn("think", r["texto"])
        self.assertEqual(copias, [r["texto"]])
        self.assertIn("Não invente fatos", pedidos[0][0]["content"])
        self.assertTrue(Path(r["arquivo"]).read_text(encoding="utf-8").startswith("Pedido: escreva um e-mail"))
        fala = rascunhos.fala(r)
        self.assertIn("nada foi enviado", fala)
        u = urllib.parse.urlparse(rascunhos.url_gmail(r))
        q = urllib.parse.parse_qs(u.query)
        self.assertEqual((u.scheme, u.netloc, q["view"], q["su"]), ("https", "mail.google.com", ["cm"], ["Atraso na reunião"]))
        self.assertNotIn("to", q)                            # destinatario fica com o usuario

    def test_comando_nao_envia_e_abre_gmail_so_quando_pedido(self):
        rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor", "modelo_voz": "m"}),
                             estado=SimpleNamespace(atualizar=mock.Mock()))
        rt.rascunhos = rascunhos.Rascunhos(lambda m: "Oi Ana, a reunião mudou para [horário].",
                                           Path(tempfile.mkdtemp()), copiar_fn=lambda t: True)
        c = cmd.Comandos(rt, lambda x: None)
        with mock.patch.object(c, "_abrir_url") as abrir:
            fala = c.executar("rascunho", {}, "Jarvis, prepare uma mensagem para a Ana sobre a reunião")
            abrir.assert_not_called()
            self.assertIn("Rascunho pronto: mensagem para Ana", fala)
            c.executar("rascunho_gmail", {}, "abra o rascunho no Gmail")
            self.assertTrue(abrir.call_args[0][0].startswith("https://mail.google.com/mail/?"))

    def test_sem_rascunho(self):
        rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}))
        c = cmd.Comandos(rt, lambda x: None)
        self.assertIn("Ainda não fiz nenhum rascunho", c.executar("rascunho_gmail", {}, "abra o rascunho no gmail"))


if __name__ == "__main__":
    unittest.main()
