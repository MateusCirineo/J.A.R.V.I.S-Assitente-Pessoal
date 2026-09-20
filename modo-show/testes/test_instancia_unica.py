"""Um unico runtime (V11): so ele toca audio e executa acoes; as tres janelas
sao so telas. Garantia: a porta exclusiva impede um segundo runtime (ja
aconteceu: SO_REUSEADDR deixava dois processos na mesma porta = duas vozes)."""

import socket
import sys
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime.servidor_http import ServidorExclusivo  # noqa: E402


class TestInstanciaUnica(unittest.TestCase):
    def test_segundo_runtime_nao_pega_a_mesma_porta(self):
        primeiro = ServidorExclusivo(("127.0.0.1", 0), BaseHTTPRequestHandler)
        porta = primeiro.server_address[1]
        try:
            with self.assertRaises(OSError):
                ServidorExclusivo(("127.0.0.1", porta), BaseHTTPRequestHandler)
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)      # nem com REUSEADDR, como antes
            with self.assertRaises(OSError):
                s.bind(("127.0.0.1", porta))
            s.close()
        finally:
            primeiro.server_close()

    def test_so_o_runtime_toca_audio(self):
        raiz = Path(__file__).resolve().parent.parent / "hud"
        for js in raiz.glob("*.js"):
            texto = js.read_text(encoding="utf-8")
            for proibido in ("new Audio(", "speechSynthesis", "AudioContext("):
                if proibido == "AudioContext(" and js.name in ("jarvis.js",):
                    continue                                            # bipes de interface opcionais (sons_interface)
                self.assertNotIn(proibido, texto, f"{js.name} toca áudio próprio: {proibido}")


if __name__ == "__main__":
    unittest.main()
