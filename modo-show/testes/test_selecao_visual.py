"""T15: a seleção usa trilha atual e fonte correta; fixtures sem câmera real."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / '_libs'))
from hud_runtime.comandos import Comandos
from hud_runtime.rastreador import Rastreador
from hud_runtime.selecao import Selecionador


def objeto(x):
    return dict(classe=41, nome='copo', conf=.9, x=x, y=.2, w=.15, h=.3)


class SelecaoVisual(unittest.TestCase):
    def setUp(self):
        self.r = Rastreador()
        for _ in range(2):
            self.r.atualizar([objeto(.2), objeto(.65)])
        self.s = Selecionador()
        self.visao = SimpleNamespace(identificar=Mock(return_value=('identificado', {})))
        rt = SimpleNamespace(selecao=self.s, visao=self.visao,
                             visao_continua=SimpleNamespace(rastreador=self.r),
                             prefs=SimpleNamespace(ler=lambda: {'nome_usuario': 'Mateus'}),
                             estado=SimpleNamespace(registrar=Mock()))
        self.c = Comandos(rt, lambda *a: None)
        self.c._inventario = lambda: None

    def dizer(self):
        return self.c.executar('visao', {}, 'qual a marca desse objeto?')

    def test_trilha_atual_substitui_caixa_velha(self):
        self.s.selecionar('objeto', 'obj1', por='mouse', fonte='camera', caixa=[.6, .6, .1, .1])
        self.r.atualizar([objeto(.21), objeto(.65)])
        self.assertEqual(self.dizer(), 'identificado')
        self.assertEqual(self.visao.identificar.call_args.kwargs['caixa'], (.21, .2, .15, .3))

    def test_trilha_sumida_exige_reselecao(self):
        self.s.selecionar('objeto', 'obj1', por='mouse', fonte='camera', caixa=[.2, .2, .15, .3])
        self.r.atualizar([objeto(.65)])
        self.assertIn('Perdi a continuidade', self.dizer())
        self.visao.identificar.assert_not_called()

    def test_caixa_de_mesa_nao_e_usada_como_camera(self):
        self.s.selecionar('regiao', 'mesa', por='mouse', fonte='mesa', caixa=[.2, .2, .2, .2])
        self.assertIn('mais de um objeto', self.dizer())
        self.visao.identificar.assert_not_called()

    def test_regiao_fixa_explicita_camera_e_respeitada(self):
        self.s.selecionar('regiao', 'centro', por='mouse', fonte='camera', caixa=[.2, .2, .2, .2])
        self.assertEqual(self.dizer(), 'identificado')
        self.assertEqual(self.visao.identificar.call_args.kwargs['caixa'], [.2, .2, .2, .2])

    def test_trilha_sem_frame_recente_nao_tem_identidade_atual(self):
        self.s.selecionar('objeto', 'obj1', por='mouse', fonte='camera')
        self.r.obter('obj1').visto_em -= 3
        self.assertIn('Perdi a continuidade', self.dizer())
        self.visao.identificar.assert_not_called()


class ValidacaoSelecao(unittest.TestCase):
    def test_coordenadas_nao_finitas_nao_entram_no_estado(self):
        s = Selecionador()
        for valor in (float('nan'), float('inf'), True, -1, 2):
            with self.assertRaises(ValueError):
                s.selecionar('regiao', 'centro', caixa=[valor, .2, .2, .2], fonte='camera')
        self.assertIsNone(s.atual())

    def test_tipo_e_fonte_fora_do_contrato_sao_recusados(self):
        s = Selecionador()
        for tipo, identificador, extra in [('shell', 'x', {}), ('regiao', '', {}),
                                          ('regiao', 'x', {'fonte': 'camera_remota'})]:
            with self.assertRaises(ValueError):
                s.selecionar(tipo, identificador, **extra)

    def test_endpoint_preserva_fonte_e_recusa_gesto_injetado(self):
        from jarvis_runtime import Runtime
        rt = SimpleNamespace(selecao=Selecionador())
        dados = dict(tipo='regiao', id='centro', por='mouse',
                     extra={'fonte':'camera', 'caixa':[.2,.2,.3,.3]})
        resposta = Runtime.acao(rt, '/api/selecao', {'alvo':dados})
        self.assertTrue(resposta['ok'])
        self.assertEqual(rt.selecao.atual().extra['fonte'], 'camera')
        invalidos = [dict(dados, por='gesto'), [], dict(dados, extra=[]),
                     dict(dados, extra={'fonte':'camera','caixa':[float('nan'),.2,.3,.3]})]
        for invalido in invalidos:
            with self.assertRaises(ValueError):
                Runtime.acao(rt, '/api/selecao', {'alvo':invalido})
        self.assertEqual(rt.selecao.atual().id, 'centro')


if __name__ == '__main__':
    unittest.main()
