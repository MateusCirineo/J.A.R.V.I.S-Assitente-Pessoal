"""Leitura com eventos, texto e player fixtures; nenhuma fala real é reproduzida."""
import re
import sys
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hud_runtime.leitura import Leitura, dividir
from hud_runtime.audio import Reprodutor
from hud_runtime.estado import Estado


def esperar(leitor, estado, timeout=3):
    limite = time.monotonic() + timeout
    with leitor._cond:
        while leitor._dados["estado"] != estado:
            restante = limite - time.monotonic()
            assert restante > 0, leitor.estado()
            leitor._cond.wait(min(restante, 0.01))
    return leitor.estado()


def criar(**kwargs):
    padrao = dict(sintetizar=Mock(side_effect=lambda t: (t, 24000)),
                  tocar=Mock(return_value="concluido"), parar_audio=Mock(),
                  lock_audio=threading.Lock(), publicar=Mock(), tamanho_trecho=80)
    padrao.update(kwargs)
    return Leitura(**padrao), padrao


def test_divisao_nao_perde_texto_e_nao_trunca_silenciosamente():
    texto = ("Uma frase sobre um componente.\nOutra frase que explica a medida. " * 9).strip()
    trechos = dividir(texto, 80)
    assert all(0 < len(t) <= 80 for t in trechos)
    assert re.sub(r"\s", "", "".join(trechos)) == re.sub(r"\s", "", texto)
    with pytest.raises(ValueError, match="cem mil"):
        dividir("x" * 100001)


def test_indice_avanca_so_apos_confirmacao_e_painel_tem_o_mesmo_trecho():
    leitor, callbacks = criar()
    texto = "Primeiro trecho de leitura. " * 12
    try:
        leitor.iniciar(texto, titulo="Manual escolhido", fonte={"id": "manual-v1"})
        final = esperar(leitor, "concluido")
        falas = [a.args[0] for a in callbacks["sintetizar"].call_args_list]
        assert falas == dividir(texto, 80)
        assert final["indice"] == final["total"] == len(falas)
        snapshots = [a.args[0] for a in callbacks["publicar"].call_args_list]
        assert all(t in [s["trecho_atual"] for s in snapshots if s["estado"] == "lendo"] for t in falas)
        assert final["trecho_atual"] == ""
    finally:
        leitor.parar()


def test_interrompido_preserva_trecho_e_exige_retoma_explicita():
    tocar = Mock(side_effect=["interrompido", "concluido"])
    leitor, callbacks = criar(tocar=tocar)
    try:
        leitor.iniciar("Um trecho interrompido.")
        pausado = esperar(leitor, "pausado")
        assert pausado["indice"] == 0
        assert tocar.call_count == 1
        leitor.retomar()
        esperar(leitor, "concluido")
        assert [a.args[0] for a in callbacks["sintetizar"].call_args_list] == ["Um trecho interrompido."] * 2
    finally:
        leitor.parar()


def test_pausa_na_sintese_descarta_audio_tardio():
    entrou, liberar = threading.Event(), threading.Event()
    chamadas = []
    def sintetizar(texto):
        chamadas.append(texto)
        if len(chamadas) == 1:
            entrou.set()
            assert liberar.wait(3)
        return texto, 24000
    leitor, callbacks = criar(sintetizar=sintetizar)
    try:
        leitor.iniciar("Texto autorizado.")
        assert entrou.wait(2)
        leitor.pausar()
        liberar.set()
        # Adquirir a trava prova que a síntese velha terminou e foi descartada.
        assert callbacks["lock_audio"].acquire(timeout=2)
        callbacks["lock_audio"].release()
        callbacks["tocar"].assert_not_called()
        assert leitor.estado()["indice"] == 0
        leitor.retomar()
        esperar(leitor, "concluido")
        assert callbacks["tocar"].call_count == 1
    finally:
        liberar.set()
        leitor.parar()


def test_cancelamento_na_janela_antes_do_player_e_entregue_ao_player():
    entrou, liberar = threading.Event(), threading.Event()
    recebidos = []
    def tocar(audio, taxa, *, cancelado):
        entrou.set()
        assert liberar.wait(3)
        recebidos.append(cancelado.is_set())
        return "interrompido" if cancelado.is_set() else "concluido"
    leitor, callbacks = criar(tocar=tocar)
    try:
        leitor.iniciar("Texto autorizado.")
        assert entrou.wait(2)
        leitor.pausar()
        liberar.set()
        assert callbacks["lock_audio"].acquire(timeout=2)
        callbacks["lock_audio"].release()
        assert recebidos == [True] and leitor.estado()["indice"] == 0
    finally:
        liberar.set()
        leitor.parar()


def test_leitor_aguarda_trava_compartilhada_e_nao_para_fala_alheia():
    lock = threading.Lock()
    lock.acquire()
    leitor, callbacks = criar(lock_audio=lock)
    try:
        leitor.iniciar("Texto selecionado.")
        assert leitor.estado()["estado"] == "aguardando_audio"
        leitor.pausar()
        callbacks["sintetizar"].assert_not_called()
        callbacks["parar_audio"].assert_not_called()
        lock.release()
        leitor.retomar()
        esperar(leitor, "concluido")
    finally:
        if lock.locked():
            lock.release()
        leitor.parar()


def test_novo_documento_nao_recebe_audio_tardio_do_anterior():
    entrou, liberar = threading.Event(), threading.Event()
    def sintetizar(texto):
        if texto == "Documento anterior.":
            entrou.set()
            assert liberar.wait(3)
        return texto, 24000
    leitor, callbacks = criar(sintetizar=sintetizar)
    try:
        leitor.iniciar("Documento anterior.")
        assert entrou.wait(2)
        leitor.iniciar("Documento novo.")
        liberar.set()
        esperar(leitor, "concluido")
        assert [a.args[0] for a in callbacks["tocar"].call_args_list] == ["Documento novo."]
    finally:
        liberar.set()
        leitor.parar()


@pytest.mark.parametrize("falha", ["erro", "resultado inventado"])
def test_falha_do_player_nao_avanca(falha):
    leitor, _ = criar(tocar=Mock(return_value=falha))
    try:
        leitor.iniciar("Texto escolhido.")
        assert esperar(leitor, "erro")["indice"] == 0
    finally:
        leitor.parar()


def test_fonte_mudou_antes_de_ler_bloqueia_sintese():
    leitor, callbacks = criar(validar_fonte=Mock(return_value=False))
    try:
        leitor.iniciar("Versão antiga.", fonte={"id": "v1"})
        assert "fonte mudou" in esperar(leitor, "erro")["erro"]
        callbacks["sintetizar"].assert_not_called()
    finally:
        leitor.parar()


def test_parar_nao_retoma_automaticamente_nem_com_comando_de_retoma():
    leitor, _ = criar()
    leitor.iniciar("Texto escolhido.")
    leitor.parar()
    with pytest.raises(ValueError, match="pausada"):
        leitor.retomar()


def test_reprodutor_cancelado_antes_da_chamada_nao_acessa_dispositivo():
    cancelado = threading.Event()
    cancelado.set()
    player = Reprodutor(Estado())
    with patch("hud_runtime.audio.sd.query_devices") as dispositivo:
        assert player.tocar(np.zeros(20), 24000, cancelado=cancelado) == "interrompido"
    dispositivo.assert_not_called()


def test_reprodutor_cancelado_depois_da_entrada_antes_do_primeiro_bloco():
    cancelado = threading.Event()
    estado = Estado()
    player = Reprodutor(estado)
    saidas = []
    class Stream:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
        def __enter__(self):
            from hud_runtime import audio
            cancelado.set()
            bloco = np.ones((10, 1), dtype=np.float32)
            try:
                self.kwargs["callback"](bloco, 10, None, None)
            except audio.sd.CallbackStop:
                pass
            saidas.append(bloco.copy())
            self.kwargs["finished_callback"]()
            return self
        def __exit__(self, *args):
            pass
    with patch("hud_runtime.audio.sd.query_devices", return_value={"name": "fixture"}), patch("hud_runtime.audio.sd.OutputStream", Stream):
        assert player.tocar(np.ones(20), 24000, cancelado=cancelado) == "interrompido"
    assert not np.any(saidas[0])
    assert not player.falando
