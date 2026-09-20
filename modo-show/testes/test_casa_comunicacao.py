"""Casa (descoberta e controle pela rede local) e comunicacao (Telegram pareado, WhatsApp pronto)."""

import json
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime import casa as cs  # noqa: E402
from hud_runtime import comandos as cmd  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402
from hud_runtime.telegram import PonteTelegram, link_whatsapp  # noqa: E402


def nome(n):
    return b"".join(bytes([len(p)]) + p.encode() for p in n.split(".")) + b"\0"


def rr(n, tipo, dado):
    return nome(n) + struct.pack("!HHIH", tipo, 1, 120, len(dado)) + dado


class TestDescoberta(unittest.TestCase):
    def test_resposta_mdns(self):
        inst = "Shelly Plug Sala._shelly._tcp.local"
        txt = bytes([7]) + b"fn=Sala"
        srv = struct.pack("!HHH", 0, 0, 80) + nome("shelly-plug.local")
        pacote = struct.pack("!6H", 0, 0x8400, 0, 1, 0, 3) + rr("_shelly._tcp.local", 12, nome(inst)) \
            + rr(inst, 33, srv) + rr("shelly-plug.local", 1, socket.inet_aton("192.168.0.50")) + rr(inst, 16, txt)
        regs = cs.ler_resposta_mdns(pacote)
        self.assertIn(("_shelly._tcp.local", 12, inst), regs)
        self.assertIn((inst, 33, ("shelly-plug.local", 80)), regs)
        self.assertIn(("shelly-plug.local", 1, "192.168.0.50"), regs)
        self.assertIn((inst, 16, {"fn": "Sala"}), regs)

    def test_descricao_upnp(self):
        xml = b"""<?xml version="1.0"?><root xmlns="urn:schemas-upnp-org:device-1-0"><device>
          <deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType><friendlyName>TV da Sala</friendlyName>
          <manufacturer>Samsung</manufacturer><modelName>QLED</modelName><UDN>uuid:tv1</UDN><serviceList>
          <service><serviceType>urn:schemas-upnp-org:service:RenderingControl:1</serviceType><controlURL>/rc</controlURL></service>
          <service><serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType><controlURL>/av</controlURL></service>
          </serviceList></device></root>"""
        with mock.patch("hud_runtime.casa._http", return_value=xml):
            d = cs.descrever_upnp("http://192.168.0.20:9197/dmr")
        self.assertEqual((d["nome"], d["tipo"], d["ip"]), ("TV da Sala", "midia", "192.168.0.20"))
        self.assertEqual(d["servicos"]["RenderingControl"]["url"], "http://192.168.0.20:9197/rc")
        enviados = []
        with mock.patch("hud_runtime.casa._http", side_effect=lambda url, dados=None, cab=None, *a, **k: enviados.append((url, dados, cab))):
            cs.upnp(d, "volume", 20)
        self.assertIn(b"<DesiredVolume>20</DesiredVolume>", enviados[0][1])
        self.assertIn("#SetVolume", enviados[0][2]["SOAPACTION"])

    def test_entidade_do_home_assistant(self):
        estados = [{"entity_id": "light.sala", "attributes": {"friendly_name": "Luz da Sala"}},
                   {"entity_id": "light.quarto", "attributes": {"friendly_name": "Luz do Quarto"}},
                   {"entity_id": "sensor.temp", "attributes": {"friendly_name": "Temperatura da Sala"}}]
        self.assertEqual(cs.achar_entidade(estados, "luz da sala")["entity_id"], "light.sala")
        self.assertEqual(cs.achar_entidade(estados, "luzes do quarto")["entity_id"], "light.quarto")
        self.assertIsNone(cs.achar_entidade(estados, "cafeteira"))


class TestComandos(unittest.TestCase):
    def setUp(self):
        self.prefs = validar({"nome_usuario": "Senhor"})
        self.segredos = {"ha_url": "http://192.168.0.10:8123", "ha_token": "x" * 40}
        self.abertos = []
        self.rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: self.prefs), estado=SimpleNamespace(atualizar=mock.Mock()),
                                  casa=cs.Casa(Path(tempfile.mkdtemp()) / "casa.json"), _olhando=threading.Event(),
                                  telegram=None)
        self.c = cmd.Comandos(self.rt, lambda x: None)
        self.c._contexto = lambda cartao: None
        self.c._abrir_url = self.abertos.append
        self.chamadas = []
        estados = [{"entity_id": "light.sala", "attributes": {"friendly_name": "Luz da Sala"}},
                   {"entity_id": "lock.frente", "attributes": {"friendly_name": "Porta da Frente"}}]

        def http(url, dados=None, cabecalhos=None, metodo=None, timeout=3.0):
            self.chamadas.append((url, json.loads(dados) if dados else None))
            return json.dumps(estados).encode() if url.endswith("/api/states") else b"[]"
        self.p1 = mock.patch("hud_runtime.casa._http", side_effect=http)
        self.p2 = mock.patch("hud_runtime.agenda.ler_segredo", side_effect=lambda k: self.segredos.get(k))
        self.p1.start()
        self.p2.start()

    def tearDown(self):
        self.p1.stop()
        self.p2.stop()

    def dizer(self, frase):
        nome, args = self.c.interpretar(frase)
        return self.c.executar(nome, args, frase)

    def test_home_assistant_e_confirmacao(self):
        self.assertEqual(self.dizer("Jarvis, ligue a luz da sala"), "Luz da Sala: ligado.")
        self.assertIn(("http://192.168.0.10:8123/api/services/light/turn_on", {"entity_id": "light.sala"}), self.chamadas)
        self.assertEqual(self.dizer("destranque a porta da frente"), "Por segurança, confirme: diga confirmo destrancar.")
        self.assertFalse(any("unlock" in u for u, _ in self.chamadas))                          # ainda nao destrancou
        self.assertEqual(self.dizer("confirmo destrancar"), "Porta da Frente destrancada.")
        self.assertTrue(any(u.endswith("/lock/unlock") for u, _ in self.chamadas))
        self.assertEqual(self.dizer("confirmo destrancar"), "Não havia nada esperando confirmação.")

    def test_tomada_shelly_manual(self):
        self.segredos.clear()
        with mock.patch("hud_runtime.casa.sondar_rele", return_value={"tipo": "Shelly", "geracao": 1, "modelo": "SHPLG-S"}):
            self.assertIn("ventilador (Shelly) adicionado", self.dizer("adicione a tomada 192.168.0.50 como ventilador"))
        self.assertEqual(self.dizer("ligue o ventilador"), "Ventilador ligado.")
        self.assertEqual(self.chamadas[-1][0], "http://192.168.0.50/relay/0?turn=on")
        self.assertIn("Não achei cafeteira", self.dizer("ligue a cafeteira"))

    def test_whatsapp_so_abre_pronto(self):
        r = self.dizer("mande no WhatsApp para 11 91234 5678 dizendo que vou atrasar")
        self.assertIn("aperte enviar: eu não envio sozinho", r)
        self.assertEqual(self.abertos, ["https://wa.me/5511912345678?text=vou%20atrasar"])
        self.assertIsNone(link_whatsapp("123", "oi"))


class TestTelegram(unittest.TestCase):
    def setUp(self):
        self.cofre = {"telegram_token": "123:ABC"}
        self.mandados, self.atendidos = [], []
        self.p = PonteTelegram(lambda t: self.atendidos.append(t) or f"ok: {t}", self.cofre.get,
                               lambda k, v: self.cofre.__setitem__(k, v) if v is not None else self.cofre.pop(k, None),
                               lambda *a, **k: None)
        self.p._chamar = lambda token, metodo, dados=None, timeout=35: self.mandados.append((metodo, dados)) or {}

    def test_pareamento_e_so_o_dono_manda(self):
        estranho = {"chat": {"id": 666}, "text": "abra o Gmail"}
        self.p.tratar(estranho, "123:ABC")
        self.assertEqual((self.atendidos, self.mandados), ([], []))                             # ignorado
        self.p.tratar({"chat": {"id": 42}, "text": "/parear 000000"}, "123:ABC")
        self.assertIsNone(self.p.chat)                                                           # codigo errado
        self.p.tratar({"chat": {"id": 42}, "text": f"/parear {self.p.codigo}"}, "123:ABC")
        self.assertEqual(self.p.chat, 42)
        self.p.tratar({"chat": {"id": 42}, "text": "notícias do mundo"}, "123:ABC")
        self.assertEqual(self.atendidos, ["notícias do mundo"])
        self.assertEqual(self.mandados[-1], ("sendMessage", {"chat_id": 42, "text": "ok: notícias do mundo"}))
        self.p.tratar(estranho, "123:ABC")
        self.assertEqual(self.atendidos, ["notícias do mundo"])                                  # continua ignorado
        self.assertTrue(self.p.enviar("alerta do vigia"))
        self.assertEqual(self.mandados[-1][1]["chat_id"], 42)

    def test_token_invalido(self):
        with self.assertRaises(ValueError):
            self.p.definir_token("nao e token")


if __name__ == "__main__":
    unittest.main()
