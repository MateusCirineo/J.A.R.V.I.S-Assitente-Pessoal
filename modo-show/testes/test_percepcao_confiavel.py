"""Regressões T08–T15/F17; imagens/landmarks explicitamente sintéticos.

Não testa reconhecimento humano nem desempenho de câmera ao vivo.
"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

import cv2
import numpy as np
from hud_runtime.identificacao import Identificacao, CONFIRMADO, COMPATIVEL, pistas_de_texto
from hud_runtime.inventario import Inventario
from hud_runtime.ocorrencias import de_rastreador
from hud_runtime.percepcao import Percepcao, ler_resposta
from hud_runtime.rastreador import Rastreador
from hud_runtime.visao import Visao
from hud_runtime.estado import Estado


class IdentificarReferencia(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.inv = Inventario(Path(self.temp.name) / 'objetos.json')
        for modelo in ('Galaxy S23', 'Galaxy S23+'):
            self.inv.cadastrar(modelo, fabricante='Samsung', modelo=modelo, manual='manual.pdf')

    def test_marca_sozinha_nao_confirma_modelo(self):
        ident = Identificacao('celular')
        ident.comparar_inventario('Samsung', self.inv)
        self.assertTrue(ident.ambiguo)
        self.assertNotIn('modelo', ident.atributos)

    def test_sufixo_distinto_nao_confunde_produtos(self):
        ident = Identificacao('celular')
        ident.comparar_inventario('Samsung Galaxy S23+', self.inv)
        self.assertEqual(ident.atributos['modelo'].valor, 'Galaxy S23+')
        self.assertEqual(ident.atributos['modelo'].estado, CONFIRMADO)
        self.assertIsNone(ident.atributos['unidade_fisica'].valor)
        self.assertIn('não consultado', ' '.join(ident.evidencias))

    def test_marca_na_referencia_nao_e_marca_lida(self):
        ident = Identificacao('celular')
        ident.comparar_inventario('Galaxy S23+', self.inv)
        self.assertEqual(ident.atributos['marca'].estado, COMPATIVEL)

    def test_reticencias_ascii_nao_completam_palavra(self):
        self.assertEqual(pistas_de_texto('SAM... HP')['legivel'], 'HP')

    def test_roi_e_realmente_a_imagem_do_modelo(self):
        img = np.zeros((600, 800, 3), np.uint8)
        img[:] = 150
        img[::6] = 50
        img[:, ::6] = 50
        _, jpg = cv2.imencode('.jpg', img)
        estado = Estado()
        v = Visao(estado, None,
                  SimpleNamespace(ler=lambda: {'nome_usuario': 'Mateus'}))
        v._quadro = lambda: jpg.tobytes()
        dimensoes = []
        def modelo(jpeg, *args):
            dimensoes.append(cv2.imdecode(np.frombuffer(jpeg, np.uint8), 1).shape)
            return 'CATEGORIA: celular\nTEXTO: Samsung Galaxy S23+\nLOGO: Samsung\nDESCRICAO: preto'
        v.perguntar_imagem = modelo
        _, cartao = v.identificar('este', caixa=(.25, .25, .5, .5), inventario=self.inv)
        self.assertEqual(dimensoes, [(300, 400, 3)])
        self.assertEqual(cartao['regiao'], [.25, .25, .5, .5])
        self.assertEqual(cartao['fonte'], 'camera')
        self.assertTrue(cartao['captura_id'])
        self.assertEqual(estado.ler('visao')['captura_id'], cartao['captura_id'])
        self.assertTrue(estado.ler('visao')['miniatura'].startswith('data:image/jpeg;base64,'))
        self.assertEqual(estado.ler('visao')['capturado_em'], cartao['capturado_em'])
        # Outra análise perde a captura anterior mesmo quando a câmera falha.
        v._quadro = Mock(side_effect=OSError('fixture câmera desligada'))
        v.analisar('novo quadro')
        self.assertIsNone(estado.ler('visao')['captura_id'])
        self.assertIsNone(estado.ler('visao')['miniatura'])
        self.assertEqual(estado.ler('identificacao')['captura_id'], cartao['captura_id'])


def objeto(x, largura=.25):
    return dict(classe=41, nome='copo', conf=.9, x=x, y=.3, w=largura, h=.25)


class Continuidade(unittest.TestCase):
    def setUp(self):
        self.agora = 100.0
        self.r = Rastreador(relogio=lambda: self.agora)

    def test_cruzamento_ambiguo_nao_escolhe_id_primeiro(self):
        for _ in range(2):
            self.r.atualizar([objeto(.2), objeto(.35)])
        ids = {t.id for t in self.r.ativos()}
        self.r.atualizar([objeto(.275)])
        self.assertEqual(set(self.r.ultimas_ambiguidades), ids)
        self.assertFalse(ids & {t.id for t in self.r.todos()})

    def test_reaparecer_apos_timeout_nao_herda_id(self):
        for _ in range(2):
            self.r.atualizar([objeto(.2)])
        velho = self.r.ativos()[0].id
        self.r.atualizar([])
        self.agora += 10
        self.r.atualizar([objeto(.2)])
        self.assertNotIn(velho, [t.id for t in self.r.todos()])
        self.assertTrue(any(o.tipo == 'objeto_sumiu' for o in de_rastreador(self.r)))

    def test_hora_do_retorno_nao_muda_com_quadros_posteriores(self):
        for _ in range(2):
            self.r.atualizar([objeto(.2)])
        self.r.atualizar([])
        self.agora += 1
        self.r.atualizar([objeto(.2)])
        retorno = self.agora
        self.agora += 2
        self.r.atualizar([objeto(.21)])
        self.assertEqual([o.quando for o in de_rastreador(self.r) if o.tipo == 'objeto_voltou'], [retorno])


class Cena(unittest.TestCase):
    def test_antiga_nao_e_agora_e_dois_alvos_nao_escolhe_primeiro(self):
        p = Percepcao(lambda *a: '')
        p.atual = dict(em=time.time() - 400, cena='mesa', objetos=[
            dict(nome='copo', detalhe='', x=.2, y=.3, w=.1, h=.1),
            dict(nome='copo', detalhe='', x=.7, y=.3, w=.1, h=.1)])
        self.assertIn('última observação', p.descrever())
        self.assertNotIn('Vejo:', p.descrever())
        self.assertIn('Qual deles', p.onde_esta('meu copo'))

    def test_modelo_json_invalido_nao_quebra_percepcao(self):
        for texto in ('[]', '{quebrado}', '{"objetos":[null]}', '{"objetos":[{"nome":"a","caixa":[NaN,0,500,500]}]}'):
            self.assertEqual(ler_resposta(texto)['objetos'], [])


class MedidaEMidia(unittest.TestCase):
    def test_coverage_desconhecida_nao_inventa_audio_inteiro(self):
        from hud_runtime.midia_arquivos import cobertura, falar_cobertura
        c = cobertura(0, [], [])
        self.assertIsNone(c['fracao_ouvida'])
        self.assertNotIn('inteiro', falar_cobertura(c))
        c = cobertura(100, [(0, 3, 'oi')], [])
        self.assertEqual(c['ouvido_ate_s'], 3)
        self.assertEqual(c['nao_analisado_s'], 97)

    def test_quadro_com_falha_nao_conta_como_visto(self):
        from hud_runtime import midia_arquivos as m
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(m, 'transcrever', return_value=([(0, 2, 'oi')], 10)), \
                 mock.patch.object(m, 'quadros', return_value=[(3, b'fixture')]):
                resultado = m.analisar(Path(temp)/'fixture.mp4', None, Path(temp),
                                       descrever=Mock(side_effect=RuntimeError('fixture indisponível')))
            self.assertEqual(resultado['cobertura']['quadros_vistos_s'], [])
            self.assertEqual(resultado['cobertura']['quadros_falharam_s'], [3])

    def test_homografia_singular_ou_antiga_nao_mede(self):
        from hud_runtime.regua import Regua
        with tempfile.TemporaryDirectory() as temp:
            arq = Path(temp)/'regua.json'
            dados = dict(h=[[0,0,0],[0,0,0],[0,0,0]], largura=100, altura=100, em=time.time())
            arq.write_text(json.dumps(dados))
            self.assertFalse(Regua(arq).calibrada)
            dados.update(h=[[1,0,0],[0,1,0],[0,0,1]], em=time.time()-90000)
            arq.write_text(json.dumps(dados))
            r = Regua(arq)
            self.assertFalse(r.calibrada)
            self.assertIsNone(r.medir(np.zeros((100, 100, 3), np.uint8)))


if __name__ == '__main__':
    unittest.main()
