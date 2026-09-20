"""Regressão: primeiro match determinístico não pode engolir a segunda ação.

O modelo HTTP é fixture; o cálculo e o executor usados abaixo são reais.
Nenhum dispositivo, arquivo pessoal ou serviço externo é acionado.
"""
import io
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hud_runtime.comandos import Comandos
from hud_runtime.estado import Estado
from hud_runtime.fala_variantes import pedido_composto, pedido_so_calculos
from hud_runtime.voz import Conversa


COMPOSTO = 'calcule 17 vezes 19 e depois calcule 25 por cento de 480'


@pytest.mark.parametrize('texto', [
    COMPOSTO,
    'Jarvis, calcule 17 vezes 19 e depois calcule 25 por cento de 480',
    'calcule 1,5 vezes 2 e depois calcule 3,5 vezes 4',
    'abra o painel e mostre o status do sistema',
    'pesquise cobre; compare com alumínio',
    'por favor calcule 10 vezes 3, converta 20 centímetros para metros',
    'mostre o status e depois diga que horas são',
])
def test_duas_acoes_independentes_sao_compostas(texto):
    assert pedido_composto(texto)


@pytest.mark.parametrize('texto', [
    'memorize meu rosto e voz',
    'memorize meu rosto e memorize minha voz',
    'adicione leite e ovos à lista de compras',
    'adicione calcule impostos e abra chamado à lista de tarefas',
    'escreva um rascunho: abra o painel e mostre os dados',
    'crie o protocolo manhã: calcule 2 mais 2 e depois calcule 3 mais 3',
    'anote que preciso abrir a caixa e depois calcular o peso',
    'me lembre de abrir a janela e depois desligar a luz',
    'calcule 1,5 vezes 2',
    'calcule 1.5 vezes 2',
    'não abra o painel e depois feche a janela',
    'abra o painel e não desligue a câmera',
    'explique a frase "abra o painel e depois desligue a câmera"',
    'compare cobre e alumínio',
    'o que significa calcule e depois converta?',
])
def test_singular_conteudo_literal_e_negacao_nao_sao_separados(texto):
    assert not pedido_composto(texto)


def conversa_fixture():
    c = Conversa.__new__(Conversa)
    c._estado = Estado()
    c._cancelado = threading.Event()
    rt = SimpleNamespace(estado=c._estado, prefs=SimpleNamespace(ler=lambda: {}))
    c.comandos = Comandos(rt, lambda *args: None)
    c.responder_localmente = Mock(return_value='resultado local parcial indevido')
    c.perguntar = Mock(return_value='323 e 120, ferramentas conferidas')
    return c


def test_primeiro_match_nao_engole_restante_do_pedido():
    c = conversa_fixture()
    assert c.comandos.interpretar(COMPOSTO) is not None  # gatilho do corte antigo
    with patch.object(c.comandos, 'executar', return_value='somente 323') as executar:
        resposta = c._processar_um(COMPOSTO, {}, falar=False)
    executar.assert_not_called()
    c.responder_localmente.assert_not_called()
    assert c.perguntar.call_args.args[0] == COMPOSTO
    assert resposta == '323 e 120, ferramentas conferidas'


def test_calculo_singular_preserva_caminho_deterministico():
    c = conversa_fixture()
    resposta = c._processar_um('calcule 17 vezes 19', {}, falar=False)
    c.perguntar.assert_not_called()
    assert '323' in resposta


def test_pedido_composto_envia_ferramentas_e_calcula_ambas_com_resultado_real():
    c = conversa_fixture()
    c.clima, c.falante, c.memoria = None, None, None
    c._historico = []
    c._imagem_para = lambda *args: (None, None, None)
    c._ponte_conectada = lambda: True
    pedidos = []
    def resposta_http(request, **kwargs):
        body = json.loads(request.data)
        pedidos.append(body)
        if len(pedidos) == 1:
            tools = [{'id': f'c{i}', 'type': 'function', 'function': {
                'name': 'executar_comando', 'arguments': json.dumps({'frase': frase})}}
                for i, frase in enumerate(['calcule 17 vezes 19', 'calcule 25 por cento de 480'])]
            result = {'choices': [{'message': {'content': '', 'tool_calls': tools}}]}
        else:
            result = {'choices': [{'message': {'content': 'cálculos conferidos'}}]}
        return io.BytesIO(json.dumps(result).encode())
    with patch('hud_runtime.voz.urllib.request.urlopen', side_effect=resposta_http):
        resposta = c._perguntar_com(COMPOSTO, {'ferramentas_voz': True}, 'fixture-model', None, False, None)
    assert pedidos[0]['tools']
    assert COMPOSTO in pedidos[0]['messages'][-1]['content']
    assert '323' in resposta and '120' in resposta
    resultados = [m['content'] for m in pedidos[1]['messages'] if m['role'] == 'tool']
    assert len(resultados) == 2
    assert '323' in resultados[0] and '120' in resultados[1]
    assert [f['function']['name'] for f in pedidos[0]['tools']] == ['executar_comando']
    assert 'Calculadora real' in pedidos[0]['tools'][0]['function']['description']
    assert pedidos[0]['temperature'] == 0
    assert pedidos[0]['messages'][-1]['content'] == COMPOSTO
    assert c._modelos_pedido == ['fixture-model']


@pytest.mark.parametrize('texto', [COMPOSTO, 'calcule 1,5 vezes 2', 'some 12 e 13',
                                  'Jarvis, por favor calcule 9 dividido por 3'])
def test_catalogo_matematico_so_para_contas_explicitas(texto):
    assert pedido_so_calculos(texto)


@pytest.mark.parametrize('texto', [
    'calcule 2 vezes 3 e abra o painel',
    'calcule isso vezes 3',
    'memorize a frase calcule 3 vezes 5',
    'não calcule 9 vezes 4',
    'calcule "abra o painel" 20',
    'pesquise aplicações de 3 e 4',
])
def test_catalogo_misto_ou_dependente_de_contexto_nao_e_reduzido(texto):
    assert not pedido_so_calculos(texto)


def test_modelo_sem_chamadas_nao_entrega_calculo_inventado_nem_muda_catalogo():
    from hud_runtime.comandos import FERRAMENTAS
    original = json.dumps(FERRAMENTAS, sort_keys=True)
    c = conversa_fixture()
    c.clima, c.falante, c.memoria = None, None, None
    c._historico = []
    c._imagem_para = lambda *args: (None, None, None)
    c._ponte_conectada = lambda: True
    dados = {'choices': [{'message': {'content': '17 vezes 19 é 999 e 25% de 480 é 204'}}]}
    with patch('hud_runtime.voz.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(dados).encode())):
        resposta = c._perguntar_com(COMPOSTO, {'ferramentas_voz': True}, 'fixture-model', None, False, None)
    assert 'Nenhuma ação foi executada' in resposta
    assert '999' not in resposta and '204' not in resposta
    assert '999' not in c._historico[-1]['content']
    assert json.dumps(FERRAMENTAS, sort_keys=True) == original
