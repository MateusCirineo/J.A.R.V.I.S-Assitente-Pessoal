"""Revalidação de avisos no caminho real da fila, sem sintetizar áudio."""

import sys
import threading
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime.anunciador import Anunciador  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402


@pytest.fixture
def fila():
    prefs = validar({"modo_proativo": "proativo", "silencio_inicio": 0, "silencio_fim": 0})
    falas, painel = [], []
    a = Anunciador(falas.append, lambda: False, SimpleNamespace(ler=lambda: prefs), mostrar=painel.append)
    yield a, prefs, falas, painel
    a.encerrar()


@pytest.mark.parametrize("mudanca", [{"modo_foco": True}, {"avisos_canal": "painel"}, {"voz_muda": True}])
def test_politica_revalidada_depois_de_enfileirar(fila, mudanca):
    a, prefs, falas, painel = fila
    assert a.anunciar("o arquivo terminou", categoria="aviso")
    prefs.update(mudanca)
    assert a.processar_proximo()
    assert not falas
    assert painel == ["o arquivo terminou"]


def test_silencio_comeca_antes_da_entrega(fila):
    a, prefs, falas, painel = fila
    assert a.anunciar("uma observação", categoria="observacao")
    prefs.update(silencio_inicio=22, silencio_fim=7)
    with mock.patch("hud_runtime.anunciador.datetime") as relogio:
        relogio.now.return_value = datetime(2026, 9, 20, 23)
        assert a.processar_proximo()
    assert not falas
    assert painel == ["uma observação"]


def test_modo_restringido_descarta_aviso_pendente(fila):
    a, prefs, falas, painel = fila
    a.anunciar("mais alguém na sala", categoria="observacao")
    prefs["modo_proativo"] = "sob_demanda"
    assert not a.processar_proximo()
    assert not falas and not painel


def test_pare_cancela_aviso_ja_retirado_da_fila(fila):
    a, _, falas, painel = fila
    esperando = threading.Event()
    def ocupado():
        esperando.set()
        return True
    a._ocupado = ocupado
    a.anunciar("aviso atrasado", categoria="aviso")
    fio = threading.Thread(target=a.processar_proximo)
    fio.start()
    assert esperando.wait(1)
    assert a.limpar() == 1
    fio.join(2)
    assert not fio.is_alive()
    assert not falas and not painel


def test_foco_mudado_durante_espera_mostra_sem_interromper(fila):
    a, prefs, falas, painel = fila
    esperando = threading.Event()
    a._ocupado = lambda: esperando.set() or True
    a.anunciar("aviso relevante", categoria="aviso")
    fio = threading.Thread(target=a.processar_proximo)
    fio.start()
    assert esperando.wait(1)
    prefs["modo_foco"] = True
    fio.join(2)
    assert not fio.is_alive()
    assert not falas and painel == ["aviso relevante"]


def test_deduplica_fila_e_repeticao_de_ocorrencia(fila):
    a, _, falas, _ = fila
    assert a.anunciar("serviço caiu", categoria="aviso", chave="ollama:fora")
    assert not a.anunciar("serviço caiu de novo", categoria="aviso", chave="ollama:fora")
    assert a.processar_proximo()
    assert not a.anunciar("serviço caiu", categoria="aviso", chave="ollama:fora")
    assert a.anunciar("serviço voltou", categoria="aviso", chave="ollama:ok")
    assert falas == ["serviço caiu"]


def test_timers_distintos_nao_sao_confundidos(fila):
    a, _, falas, _ = fila
    assert a.anunciar("o tempo acabou", pedido_pelo_usuario=True)
    assert a.anunciar("o tempo acabou", pedido_pelo_usuario=True)
    a.processar_proximo()
    a.processar_proximo()
    assert falas == ["o tempo acabou", "o tempo acabou"]


def test_mesmo_timer_com_chave_e_deduplicado(fila):
    a, _, _, _ = fila
    assert a.anunciar("o tempo acabou", pedido_pelo_usuario=True, chave="timer1:2026-09-20T10:00")
    assert not a.anunciar("o tempo acabou", pedido_pelo_usuario=True, chave="timer1:2026-09-20T10:00")


def test_limite_frequencia_mantem_informacao_no_painel(fila):
    a, _, falas, painel = fila
    a.anunciar("primeiro aviso", categoria="aviso")
    a.processar_proximo()
    a.anunciar("segundo aviso", categoria="aviso")
    a.processar_proximo()
    assert falas == ["primeiro aviso"]
    assert painel == ["segundo aviso"]


def test_prioridade_alta_precede_observacao_comum(fila):
    a, _, falas, painel = fila
    a.anunciar("observação comum", categoria="observacao", prioridade="baixa")
    a.anunciar("bateria crítica medida", categoria="aviso", prioridade="alta")
    a.processar_proximo()
    assert falas == ["bateria crítica medida"]
    a.processar_proximo()
    assert painel == ["observação comum"]


def test_lembrete_pedido_preserva_excecao_de_silencio(fila):
    a, prefs, falas, _ = fila
    prefs.update(modo_foco=True, silencio_inicio=22, silencio_fim=7)
    a.anunciar("seu lembrete", pedido_pelo_usuario=True)
    with mock.patch("hud_runtime.anunciador.datetime") as relogio:
        relogio.now.return_value = datetime(2026, 9, 20, 23)
        a.processar_proximo()
    assert falas == ["seu lembrete"]


def test_aviso_vencido_nao_vira_fato_atual(fila):
    a, _, falas, painel = fila
    with mock.patch("hud_runtime.anunciador.time.time", return_value=100):
        a.anunciar("pessoa na sala", categoria="observacao", validade_s=10)
    with mock.patch("hud_runtime.anunciador.time.time", return_value=111):
        assert not a.processar_proximo()
    assert not falas and not painel


def test_preferencias_invalidas_nao_ampliam_politica():
    p = validar({"modo_foco": "sim", "avisos_canal": "externo", "avisos_intervalo_s": -1,
                 "avisos_deduplicacao_s": 1e20})
    assert p["modo_foco"] is False
    assert p["avisos_canal"] == "voz"
    assert p["avisos_intervalo_s"] == 0
    assert p["avisos_deduplicacao_s"] == 86400
