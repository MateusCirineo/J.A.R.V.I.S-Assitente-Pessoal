"""S7: landmarks sintéticos para contratos; teste do modelo separado e explícito."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / '_libs'))
from hud_runtime.gestos import Gestos
from hud_runtime.selecao import Selecionador


def mao(x=.5, y=.5, pinca=False):
    pontos = [SimpleNamespace(x=x, y=y+.2) for _ in range(21)]
    pontos[0] = SimpleNamespace(x=x, y=y+.25)
    pontos[9] = SimpleNamespace(x=x, y=y+.05)
    pontos[8] = SimpleNamespace(x=x, y=y)
    pontos[4] = SimpleNamespace(x=x+(.01 if pinca else .15), y=y)
    return pontos


class ContratoGestos(unittest.TestCase):
    def setUp(self):
        self.cartoes = []
        self.s = Selecionador()
        self.g = Gestos(self.s, self.cartoes.append, lambda: True)
        self.g.ativo, self.g.cliente = True, 'teste'
        self.g._heartbeat = self.g.relogio()
        self.g.calibracao = [(.1, .1), (.9, .9)]
        self.g.comando(dict(cliente='teste', acao='alvos', alvos=[
            dict(tipo='peca', id='caixa', rotulo='Caixa', caixa=[.25, .25, .5, .5])]))

    def test_T18_gesto_e_mouse_selecionam_mesmo_alvo(self):
        alvo = self.s.selecionar('peca', 'caixa', por='mouse')
        self.g.processar_pontos([mao()])
        self.g.processar_pontos([mao(pinca=True)])
        self.assertEqual(self.s.atual().id, alvo.id)
        self.assertEqual(self.s.atual().por, 'gesto')
        self.assertEqual(self.cartoes[-1]['acao']['tipo'], 'selecionar')

    def test_pinca_nao_duplica_selecao_e_movimento_reversivel(self):
        self.g.processar_pontos([mao(pinca=True)])
        self.g.processar_pontos([mao(.52, .5, True)])
        self.assertEqual(len(self.s.historico()), 1)
        self.assertEqual(self.cartoes[-1]['acao']['tipo'], 'girar')
        self.g.comando(dict(cliente='teste', acao='modo', modo='zoom'))
        self.g.processar_pontos([mao(.52, .51, True)])
        self.g.processar_pontos([mao(.52, .53, True)])
        self.assertEqual(self.cartoes[-1]['acao']['tipo'], 'zoom')

    def test_duas_maos_e_desligado_nao_selecionam(self):
        self.g.processar_pontos([mao(pinca=True), mao(pinca=True)])
        self.assertIsNone(self.s.atual())
        self.assertEqual(self.g.fase, 'ambiguo')
        self.g.desativar()
        self.g.processar_pontos([mao(pinca=True)])
        self.assertIsNone(self.s.atual())

    def test_sem_calibracao_nao_executa(self):
        self.g.calibracao = []
        self.g.processar_pontos([mao(pinca=True)])
        self.assertIsNone(self.s.atual())

    def test_dois_pontos_calibram_e_mesmo_ponto_e_rejeitado(self):
        self.g.calibracao = []
        self.g.processar_pontos([mao(.1, .1)])
        self.g.comando(dict(cliente='teste', acao='calibrar'))
        with self.assertRaises(ValueError):
            self.g.comando(dict(cliente='teste', acao='calibrar'))
        self.g.processar_pontos([mao(.9, .9)])
        self.g.comando(dict(cliente='teste', acao='calibrar'))
        self.assertEqual(len(self.g.calibracao), 2)

    def test_outra_tela_nao_controla_sessao(self):
        with self.assertRaises(ValueError):
            self.g.comando(dict(cliente='outro', acao='modo', modo='zoom'))

    def test_lease_expirado_nao_reabre_com_heartbeat(self):
        self.g._heartbeat -= 13
        with self.assertRaises(ValueError):
            self.g.comando(dict(cliente='teste', acao='heartbeat'))
        self.assertFalse(self.g.ativo)
        self.assertEqual(self.g.calibracao, [])
        self.assertIsNone(self.s.atual())

    def test_camera_desligada_revoga_antes_de_resultado_atrasado(self):
        self.g.camera_ativa = lambda: False
        self.g.processar_pontos([mao(pinca=True)])
        self.assertFalse(self.g.ativo)
        self.assertIsNone(self.s.atual())

    def test_alvos_nao_finitos_e_booleanos_rejeitados(self):
        for valor in (float('nan'), float('inf'), True, -0.1):
            with self.assertRaises(ValueError):
                self.g.comando(dict(cliente='teste', acao='alvos', alvos=[
                    dict(tipo='peca', id='caixa', caixa=[valor, .1, .2, .2])]))

    def test_retry_ativar_preserva_calibracao(self):
        self.g.ativar('teste')
        self.assertEqual(len(self.g.calibracao), 2)

    def test_landmarks_nao_finitos_limpam_gesto_anterior(self):
        self.g.processar_pontos([mao(pinca=True)])
        p = mao(pinca=True)
        p[8].x = float('nan')
        self.g.processar_pontos([p])
        self.assertIsNone(self.g.ultimo)
        self.assertFalse(self.g._pinch)

    def test_pinca_fora_do_alvo_nao_arrasta_selecao_antiga_do_mouse(self):
        self.s.selecionar('peca', 'caixa', por='mouse')
        self.g.processar_pontos([mao(.15, .2, True)])
        self.g.processar_pontos([mao(.17, .22, True)])
        self.assertIsNone(self.cartoes[-1]['acao'])
        self.assertEqual(self.s.atual().por, 'mouse')

    def test_desligar_camera_no_endpoint_revoga_antes_de_ligar_de_novo(self):
        from jarvis_runtime import Runtime
        camera = SimpleNamespace(ativar=Mock(), desativar=Mock())
        rt = SimpleNamespace(camera=camera, gestos=self.g)
        Runtime.acao(rt, '/api/camera', {'ativa': False})
        self.assertFalse(self.g.ativo)
        self.assertEqual(self.g.calibracao, [])
        Runtime.acao(rt, '/api/camera', {'ativa': True})
        self.assertFalse(self.g.ativo)

    def test_desligar_camera_por_comando_revoga_sincronicamente(self):
        from hud_runtime.comandos import Comandos
        rt = SimpleNamespace(camera=SimpleNamespace(desativar=Mock()), gestos=self.g,
                             prefs=SimpleNamespace(ler=lambda: {'nome_usuario':'Mateus'}))
        Comandos(rt, lambda *a: None).executar('camera_desligar', {}, 'desligue a câmera')
        self.assertFalse(self.g.ativo)
        self.assertEqual(self.g.calibracao, [])

    def test_modelo_real_carrega_e_imagem_vazia_nao_inventa_mao(self):
        import numpy as np
        self.g._carregar()
        self.addCleanup(self.g._detector.close)
        mp = self.g._mp
        r = self.g._detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,
                                                      data=np.zeros((240, 320, 3), np.uint8)), 1)
        self.assertEqual(r.hand_landmarks, [])


if __name__ == '__main__':
    unittest.main()
