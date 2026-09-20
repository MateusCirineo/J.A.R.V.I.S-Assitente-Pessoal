"""Contratos com armazenamento real temporário; modelo e dispositivos são fixtures."""
import json
import sqlite3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hud_runtime.entrada import Entrada
from hud_runtime.execucao_modelo import executar_plano, validar_argumentos
from hud_runtime.comandos import FERRAMENTAS
from hud_runtime.estado import Estado


def runtime(tmp_path):
    conversa = SimpleNamespace(_pedido_lock=threading.RLock(), _cancelado=threading.Event(),
                               _historico=[], interromper=Mock())
    comandos = SimpleNamespace(_ultimo=None, ultima_lista=[], ultima_lista_em=0)
    rt = SimpleNamespace(conversa=conversa, comandos=comandos, estado=Estado())
    def atender(texto, falar=False):
        (tmp_path / 'efeitos.txt').open('a').write(texto + '\n')
        return 'Conferido: ' + texto
    conversa.atender = Mock(side_effect=atender)
    return rt


def test_reconexao_e_reinicio_nao_repetem_escrita(tmp_path):
    rt = runtime(tmp_path)
    db = tmp_path / 'pedidos.sqlite'
    entrada = Entrada(rt, db)
    pedido = dict(sessao_id='chat1', pedido_id='p1', texto='escrita')
    assert entrada.atender(pedido)['estado'] == 'respondida'
    assert entrada.atender(pedido)['repetido']
    entrada.db.close()
    assert Entrada(rt, db).atender(pedido)['repetido']
    assert (tmp_path / 'efeitos.txt').read_text().splitlines() == ['escrita']


def test_id_mesmo_com_conteudo_diferente_recusado(tmp_path):
    e = Entrada(runtime(tmp_path), tmp_path / 'p.db')
    p = dict(sessao_id='a', pedido_id='b', texto='primeiro')
    e.atender(p)
    with pytest.raises(ValueError):
        e.atender(dict(p, texto='diferente'))


def test_modelos_do_pedido_persistem_sem_herdar_modelo_de_outra_sessao(tmp_path):
    rt = runtime(tmp_path)
    rt.conversa._modelos_pedido = ['voz-anterior']
    def atender(texto, falar=False):
        if texto == 'modelo':
            rt.conversa._modelos_pedido += ['principal', 'reserva']
        return 'resultado'
    rt.conversa.atender = atender
    banco = tmp_path / 'modelos.db'
    entrada = Entrada(rt, banco)
    pedido = dict(sessao_id='a', pedido_id='m1', texto='modelo')
    assert entrada.atender(pedido)['modelos'] == ['principal', 'reserva']
    assert entrada.atender(dict(sessao_id='b', pedido_id='m2', texto='local'))['modelos'] == []
    assert rt.conversa._modelos_pedido == ['voz-anterior']
    entrada.db.close()
    assert Entrada(rt, banco).atender(pedido)['modelos'] == ['principal', 'reserva']


def test_migracao_do_recibo_antigo_nao_inventa_modelo_nem_repete(tmp_path):
    banco = tmp_path / 'legado.db'
    import hashlib
    db = sqlite3.connect(banco)
    db.execute('CREATE TABLE pedidos (sessao TEXT,id TEXT,hash TEXT,estado TEXT,resposta TEXT,em REAL,PRIMARY KEY(sessao,id))')
    db.execute('INSERT INTO pedidos VALUES (?,?,?,?,?,?)', ('s', 'p', hashlib.sha256(b'antigo').hexdigest(), 'respondida', 'preservado', 1))
    db.commit(); db.close()
    rt = runtime(tmp_path)
    r = Entrada(rt, banco).atender(dict(sessao_id='s', pedido_id='p', texto='antigo'))
    assert r['repetido'] and r['modelos'] == [] and r['resposta'] == 'preservado'
    rt.conversa.atender.assert_not_called()


def test_cancelado_antes_de_iniciar_nao_executa(tmp_path):
    rt = runtime(tmp_path)
    e = Entrada(rt, tmp_path / 'p.db')
    e.cancelar('s', 'p')
    assert e.atender(dict(sessao_id='s', pedido_id='p', texto='x'))['estado'] == 'cancelada'
    rt.conversa.atender.assert_not_called()


def test_cancelamento_antes_da_entrada_sobrevive_ao_reinicio(tmp_path):
    rt = runtime(tmp_path)
    banco = tmp_path / 'cancelar.db'
    e = Entrada(rt, banco)
    e.cancelar('s', 'p')
    e.db.close()
    e = Entrada(rt, banco)
    assert e.atender(dict(sessao_id='s', pedido_id='p', texto='não executar'))['estado'] == 'cancelada'
    rt.conversa.atender.assert_not_called()


def test_historicos_e_referencias_isolados(tmp_path):
    rt = runtime(tmp_path)
    rt.conversa._historico = [{'role': 'user', 'content': 'voz privada'}]
    vistos = []
    def atender(texto, falar=False):
        vistos.append((texto, list(rt.conversa._historico), list(rt.comandos.ultima_lista)))
        rt.comandos.ultima_lista = [{'titulo': texto}]
        return texto
    rt.conversa.atender = atender
    e = Entrada(rt, tmp_path / 'p.db')
    e.atender(dict(sessao_id='a', pedido_id='1', texto='noticia A'))
    e.atender(dict(sessao_id='b', pedido_id='1', texto='noticia B'))
    e.atender(dict(sessao_id='a', pedido_id='2', texto='continue'))
    assert vistos[1][1:] == ([], [])
    assert vistos[2][2] == [{'titulo': 'noticia A'}]
    assert rt.conversa._historico == [{'role': 'user', 'content': 'voz privada'}]


def chamada(nome='executar_comando', args=None, id='call1'):
    return {'tool_calls': [{'id': id, 'type': 'function', 'function': {
        'name': nome, 'arguments': json.dumps(args if args is not None else {'frase': 'quanto é 2 mais 2'})}}]}


def test_resultado_real_volta_ao_modelo(tmp_path):
    calls = []
    def executar(nome, args):
        path = tmp_path / 'saida.txt'
        path.write_text('resultado verificado')
        return path.read_text()
    def consultar(pedido):
        calls.append(pedido)
        return {'choices': [{'message': {'content': 'revisado'}}]}
    pedido = {'tools': FERRAMENTAS, 'messages': [{'role': 'user', 'content': 'teste'}]}
    resposta, rastros = executar_plano(chamada(), pedido, consultar, executar, threading.Event(), Mock())
    assert resposta == 'resultado verificado'
    assert calls[0]['messages'][-1]['role'] == 'tool'
    assert calls[0]['messages'][-1]['content'] == 'resultado verificado'
    assert rastros[0]['tool_calls'][0]['id'] == rastros[1]['tool_call_id']


def test_repeticoes_e_orcamento_nao_duplicam_ferramenta():
    executar = Mock(return_value='salvo')
    pedido = {'tools': FERRAMENTAS, 'messages': []}
    consultar = Mock(return_value={'choices': [{'message': chamada()}]})
    resposta, _ = executar_plano(chamada(), pedido, consultar, executar, threading.Event(), Mock())
    assert executar.call_count == 1
    assert consultar.call_count == 4
    assert 'limite de cinco' in resposta


def test_cancelamento_antes_da_ferramenta():
    cancel = threading.Event()
    cancel.set()
    executar = Mock()
    resultado, _ = executar_plano(chamada(), {'tools': FERRAMENTAS, 'messages': []}, Mock(), executar, cancel, Mock())
    assert resultado is None
    executar.assert_not_called()


@pytest.mark.parametrize('nome,args', [
    ('ligar_camera', {'ligada': 'false'}), ('ligar_camera', {}),
    ('volume', {'percentual': True}), ('volume', {'percentual': 101}),
    ('volume', {}), ('executar_comando', {'frase': 'x', 'shell': True}),
    ('executar_comando', []), ('nao_existe', {}),
])
def test_argumentos_invalidos_nao_passam(nome, args):
    assert validar_argumentos(nome, args, FERRAMENTAS)


@pytest.mark.parametrize('message', [
    {'tool_calls': 'invalid'}, {'tool_calls': [False]},
    {'tool_calls': [{'function': ['invalid']}]},
    {'tool_calls': [{'function': 'invalid'}]},
    {'tool_calls': [{'function': 123}]},
])
def test_chamada_malformada_nao_executa_nem_levanta_excecao(message):
    executar = Mock()
    resposta, _ = executar_plano(message, {'tools': FERRAMENTAS, 'messages': []},
                                 Mock(), executar, threading.Event(), Mock())
    executar.assert_not_called()
    assert resposta and ('inválid' in resposta.lower() or 'não executei' in resposta.lower())


def test_chamada_malformada_posterior_preserva_resultado_executado():
    executar = Mock(return_value='arquivo realmente salvo')
    consultar = Mock(return_value={'choices': [{'message': {'tool_calls': 'invalid'}}]})
    resposta, _ = executar_plano(chamada(), {'tools': FERRAMENTAS, 'messages': []},
                                 consultar, executar, threading.Event(), Mock())
    assert executar.call_count == 1
    assert 'arquivo realmente salvo' in resposta
    assert 'inválid' in resposta.lower()


def test_prazo_esgotado_entre_passos_nao_inicia_segunda_ferramenta():
    relogio = [0.0]
    feitas = []
    def executar(nome, args):
        feitas.append(args)
        relogio[0] = 3.0
        return 'primeira ação concluída'
    primeira = chamada(args={'frase': 'quanto é 2 mais 2'})
    primeira['tool_calls'] += chamada(args={'frase': 'quanto é 3 mais 3'}, id='call2')['tool_calls']
    consultar = Mock()
    with patch('hud_runtime.execucao_modelo.time.monotonic', side_effect=lambda: relogio[0]):
        resposta, _ = executar_plano(primeira, {'tools': FERRAMENTAS, 'messages': []},
                                     consultar, executar, threading.Event(), Mock(), prazo_s=2)
    assert len(feitas) == 1
    consultar.assert_not_called()
    assert 'primeira ação concluída' in resposta


@pytest.mark.parametrize('frase', [
    'confirme a alteração da peça', 'confirme a etapa 1',
    'memorize meu rosto', 'memorize minha voz', 'memorize meu rosto e minha voz',
    'esqueça meu rosto', 'esqueça minha voz',
    'lembre que eu moro em uma cidade', 'corrija a memória: prefiro respostas longas',
    'apague o projeto caixa', 'terminei',
])
def test_modelo_nao_fabrica_consentimento_ou_confirmacao(frase):
    from hud_runtime.comandos import Comandos
    rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: {'nome_usuario': 'Senhor'}),
                         estado=SimpleNamespace(atualizar=Mock(), registrar=Mock()))
    comandos = Comandos(rt, lambda *args: None)
    assert comandos.interpretar(frase) is not None, 'O caso precisa alcançar uma intenção real'
    with patch.object(comandos, 'executar', return_value='efeito indevido') as efeito:
        resposta = comandos.executar_ferramenta('executar_comando', {'frase': frase})
    efeito.assert_not_called()
    assert 'não executei' in resposta.lower() or 'diret' in resposta.lower()


class _DiscoCheio:
    """Falha só no commit indicado; mantém as consultas no SQLite real temporário."""
    def __init__(self, db, commit_com_falha):
        self.db, self.commit_com_falha, self.commits = db, commit_com_falha, 0

    def execute(self, *args, **kwargs):
        return self.db.execute(*args, **kwargs)

    def commit(self):
        self.commits += 1
        if self.commits == self.commit_com_falha:
            raise sqlite3.OperationalError('fixture: disk full')
        return self.db.commit()

    def rollback(self):
        return self.db.rollback()


def _lock_disponivel_em_outro_thread(lock):
    resultado = []
    def obter():
        obteve = lock.acquire(blocking=False)
        resultado.append(obteve)
        if obteve:
            lock.release()
    worker = threading.Thread(target=obter)
    worker.start()
    worker.join(2)
    assert not worker.is_alive()
    return resultado == [True]


@pytest.mark.parametrize('commit_com_falha', [1, 2])
def test_erro_disco_libera_lock_e_preserva_historico(tmp_path, commit_com_falha):
    rt = runtime(tmp_path)
    rt.conversa._historico = [{'role': 'user', 'content': 'histórico anterior'}]
    entrada = Entrada(rt, tmp_path / 'pedidos.sqlite')
    entrada.db = _DiscoCheio(entrada.db, commit_com_falha)
    pedido = dict(sessao_id='s1', pedido_id='p1', texto='escrita')
    resposta = None
    try:
        resposta = entrada.atender(pedido)
    except sqlite3.Error:
        assert commit_com_falha == 1
    assert entrada.ativo is None
    assert _lock_disponivel_em_outro_thread(rt.conversa._pedido_lock)
    assert rt.conversa._historico == [{'role': 'user', 'content': 'histórico anterior'}]
    if commit_com_falha == 1:
        rt.conversa.atender.assert_not_called()
        assert not (tmp_path / 'efeitos.txt').exists()
    else:
        assert resposta['estado'] == 'incerto'
        assert entrada.atender(pedido)['repetido']
        assert (tmp_path / 'efeitos.txt').read_text().splitlines() == ['escrita']


def test_cancelar_pedido_lento_nao_repete_efeito_na_reconexao(tmp_path):
    rt = runtime(tmp_path)
    iniciou, liberar = threading.Event(), threading.Event()
    def atender(texto, falar=False):
        iniciou.set()
        assert liberar.wait(3)
        (tmp_path / 'efeito.txt').write_text(texto)
        return 'efeito já concluído'
    rt.conversa.atender = Mock(side_effect=atender)
    rt.conversa.interromper = Mock(side_effect=rt.conversa._cancelado.set)
    entrada = Entrada(rt, tmp_path / 'pedidos.sqlite')
    pedido = dict(sessao_id='chat1', pedido_id='r1', texto='escrita')
    respostas = []
    worker = threading.Thread(target=lambda: respostas.append(entrada.atender(pedido)))
    worker.start()
    try:
        assert iniciou.wait(3)
        assert entrada.cancelar('chat1', 'r1')['estado'] == 'cancelamento_solicitado'
        liberar.set()
        worker.join(3)
        assert not worker.is_alive()
        assert respostas[0]['estado'] == 'cancelada'
        assert entrada.atender(pedido)['repetido']
        assert rt.conversa.atender.call_count == 1
        assert (tmp_path / 'efeito.txt').read_text() == 'escrita'
    finally:
        liberar.set()
        worker.join(3)


def test_identificadores_entrada_chegam_ao_protocolo_e_etapas(tmp_path):
    from hud_runtime.comandos import Comandos
    from hud_runtime.estado import Estado
    from hud_runtime.projetos import Projetos
    from hud_runtime.protocolos import Protocolos

    rt = runtime(tmp_path)
    rt.prefs = SimpleNamespace(ler=lambda: {'nome_usuario': 'Senhor'})
    rt.estado = Estado()
    rt.projetos = Projetos(tmp_path / 'projetos.json')
    rt.protocolos = Protocolos(tmp_path / 'protocolos.json')
    rt.protocolos.salvar('teste', ['quanto é 2 mais 2'])
    rt.comandos = Comandos(rt, lambda *args: None)
    falhas = []
    def atender(texto, falar=False):
        try:
            nome, args = rt.comandos.interpretar(texto)
            return rt.comandos.executar(nome, args, texto)
        except Exception as exc:
            falhas.append(repr(exc))
            raise
    rt.conversa.atender = atender
    rt.entrada = Entrada(rt, tmp_path / 'pedidos.sqlite')
    retorno = rt.entrada.atender(dict(sessao_id='sessaoX', pedido_id='pedidoY', texto='execute o protocolo teste'))
    assert rt.projetos.todas(), (retorno, falhas)
    tarefa = rt.projetos.todas()[0]
    assert tarefa.sessao_id == 'sessaoX'
    assert tarefa.pedido_id == 'pedidoY'
    assert tarefa.etapas[0].acao_id
    assert tarefa.etapas[0].pronta
    recarregada = Projetos(rt.projetos._arq).obter(tarefa.id)
    assert recarregada.etapas[0].acao_id == tarefa.etapas[0].acao_id
