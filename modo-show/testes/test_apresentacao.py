"""F38: Estado real + HTTP local; confirmação da renderização ainda exige navegador."""
import json
import socket
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / '_libs'))
from hud_runtime.apresentacao import Apresentacao
from hud_runtime.comandos import Comandos
from hud_runtime.estado import Estado
from hud_runtime import servidor_http


class ApresentacaoComEstado(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.arquivo = Path(self.pasta.name)/'fixture.obj'
        self.arquivo.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
        self.estado = Estado()
        self.a = Apresentacao(lambda **c: self.estado.atualizar('apresentacao', **c))

    def test_id_antigo_nao_confirma_nova_apresentacao(self):
        antigo = self.a.preparar(self.arquivo)
        novo = self.a.preparar(self.arquivo)
        self.assertFalse(self.a.confirmar(antigo, 'holograma'))
        self.assertEqual(self.estado.ler('apresentacao')['estado'], 'solicitada')
        self.assertFalse(self.a.confirmar(novo, 'outra-tela'))
        self.assertTrue(self.a.confirmar(novo, 'holograma'))
        self.assertEqual(self.estado.ler('apresentacao')['estado'], 'carregada')
        self.assertFalse(self.estado.ler('apresentacao')['validacao_engenharia'])
        versao = self.estado.instantaneo()['versao']
        self.assertTrue(self.a.confirmar(novo, 'holograma'))
        self.assertEqual(self.estado.instantaneo()['versao'], versao)

    def test_timer_reutiliza_id_e_nao_reapresenta_solicitacao_superada(self):
        rt = SimpleNamespace(apresentacao=self.a, estado=self.estado,
                             prefs=SimpleNamespace(ler=lambda: {}))
        comandos = Comandos(rt, lambda *a: None)
        comandos._abrir_holograma = lambda: False
        eventos = []
        comandos._pagina = eventos.append
        with mock.patch('hud_runtime.comandos.threading.Timer') as timer:
            comandos.mostrar_modelo(self.arquivo)
            callback = timer.call_args.args[1]
            callback()
            self.assertEqual(eventos[0]['apresentacao_id'], eventos[1]['apresentacao_id'])
            self.a.preparar(self.arquivo)
            callback()
            self.assertEqual(len(eventos), 2)

    def test_http_modelo_e_ack_usam_o_mesmo_id(self):
        # Importa a classe real, mas não inicializa áudio/câmera/runtime.
        from jarvis_runtime import Runtime
        rt = SimpleNamespace(apresentacao=self.a, estado=self.estado, token='fixture-token',
                             holograma_modelo=self.arquivo, encerrando=threading.Event())
        rt.acao = lambda rota, corpo: Runtime.acao(rt, rota, corpo)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            porta = s.getsockname()[1]
        servidor = servidor_http.criar(rt, porta)
        servidor_http.rodar(servidor)
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        base = f'http://127.0.0.1:{porta}'
        ident = self.a.preparar(self.arquivo)
        with urllib.request.urlopen(urllib.request.Request(base+'/api/holograma/modelo',
                headers={'X-Jarvis-Token':rt.token}), timeout=5) as resposta:
            self.assertEqual(resposta.headers['X-Apresentacao-Id'], ident)
            self.assertEqual(resposta.read(), self.arquivo.read_bytes())
        pedido = urllib.request.Request(base+'/api/apresentacao/confirmar', method='POST',
            data=json.dumps(dict(id=ident, destino='holograma')).encode(),
            headers={'X-Jarvis-Token':rt.token, 'Origin':base, 'Content-Type':'application/json'})
        with urllib.request.urlopen(pedido, timeout=5) as resposta:
            self.assertTrue(json.load(resposta)['confirmado'])
        self.assertEqual(self.estado.ler('apresentacao')['estado'], 'carregada')


if __name__ == '__main__':
    unittest.main()
