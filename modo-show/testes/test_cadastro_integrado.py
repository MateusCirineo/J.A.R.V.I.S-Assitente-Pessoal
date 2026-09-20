"""Integração local com câmera/STT/embeddings simulados; não valida acurácia humana.

Todos os cadastros usam tmp_path, nenhum dispositivo ou serviço é aberto.
"""

import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.comandos import Comandos, interpretar  # noqa: E402
from hud_runtime.estado import Estado  # noqa: E402
from hud_runtime.identidade import Cadastro  # noqa: E402
from hud_runtime.voz import Conversa  # noqa: E402


def vetor(indice=0):
    v = np.zeros(128, np.float32)
    v[indice] = 1.0
    return v


@pytest.fixture
def ambiente(tmp_path):
    prefs = SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor", "exigir_nome": False})
    estado = Estado()
    mic = SimpleNamespace(ativo=False)
    mic.ativar = mock.Mock(side_effect=lambda: setattr(mic, "ativo", True))
    mic.desativar = mock.Mock(side_effect=lambda: setattr(mic, "ativo", False))
    stt = SimpleNamespace(pronta=True, transcrever=lambda wav, idioma: wav.decode())
    with mock.patch.object(threading.Thread, "start"):
        conversa = Conversa(estado, prefs, mic, stt, SimpleNamespace(pronta=False),
                            SimpleNamespace(parar=mock.Mock(), falando=False), lambda: False)
    conversa.falar = mock.Mock()
    conversa.perguntar = mock.Mock(side_effect=AssertionError("cadastro não deve chegar ao LLM"))
    cad = Cadastro(tmp_path / "identidades.json")
    falantes = SimpleNamespace(disponivel=True, cadastro=cad,
                              vetor=mock.Mock(return_value=vetor()), quem=lambda _: (None, 0.0))
    rt = SimpleNamespace(prefs=prefs, estado=estado, identidades=cad, conversa=conversa, falantes=falantes,
                         rostos_id=SimpleNamespace(disponivel=True, vetor_de_um_rosto=mock.Mock(return_value=vetor())),
                         camera=SimpleNamespace(ativa=True), _ultimo_quadro=np.zeros((8, 8, 3), np.uint8))
    comandos = Comandos(rt, lambda _: None)
    comandos._correcoes = lambda: SimpleNamespace(aplicar=lambda _: None)
    conversa.comandos = comandos
    conversa.falantes = falantes
    rt.comandos, rt.mic, rt.stt = comandos, mic, stt
    yield rt
    conversa.encerrar()


def dizer(rt, texto):
    def novo_quadro(_espera):
        rt._ultimo_quadro = np.zeros((8, 8, 3), np.uint8)
    with mock.patch("hud_runtime.comandos.time.sleep", side_effect=novo_quadro):
        return rt.conversa.atender(texto, falar=False)


@pytest.mark.parametrize("texto", [
    "Jarvis, memorize meu rosto e minha voz",
    "Memorize a minha voz e o meu rosto",
    "Quero que você aprenda a reconhecer meu rosto e voz",
    "Cadastre meu rosto e a voz",
    "Guarde o rosto e a voz da Maria",
    "Registre a voz e o rosto do Pedro",
])
def test_variantes_conjuntas(texto):
    assert interpretar(texto)[0] == "id_pessoa_cadastrar"


def test_pedido_conjunto_executa_rosto_e_coleta_voz_sem_fingir_conclusao(ambiente):
    rt = ambiente
    resposta = dizer(rt, "Jarvis, memorize meu rosto e minha voz")
    assert "Cadastro do seu rosto salvo" in resposta
    assert "três amostras válidas" in resposta
    assert list(rt.identidades.ler()["rostos"]) == ["dono"]
    assert not rt.identidades.ler()["vozes"]
    assert rt.conversa.cadastro_voz is not None
    rt.mic.ativar.assert_called_once()
    for frase in (b"primeira frase de teste", b"segunda frase de teste", b"terceira frase de teste"):
        rt.conversa._turno(frase)
    assert list(rt.identidades.ler()["vozes"]) == ["dono"]
    assert rt.conversa.cadastro_voz is None
    rt.mic.desativar.assert_called_once()
    assert rt.estado.ler("conversa")["cadastro_voz"]["estado"] == "concluido"
    assert "vetores" not in json.dumps(rt.estado.instantaneo())
    rt.conversa.perguntar.assert_not_called()


def test_conjunto_informa_falha_da_camera_e_continua_voz(ambiente):
    with mock.patch.object(ambiente.comandos, "_quadro_agora", return_value=None):
        resposta = dizer(ambiente, "memorize meu rosto e minha voz")
    assert "o rosto não foi cadastrado" in resposta
    assert ambiente.conversa.cadastro_voz is not None
    assert not ambiente.identidades.ler()["rostos"]


def test_conjunto_nao_esconde_modelo_de_voz_ausente(ambiente):
    ambiente.falantes.disponivel = False
    resposta = dizer(ambiente, "memorize minha voz e meu rosto")
    assert "Cadastro do seu rosto salvo" in resposta
    assert "a voz não foi cadastrada" in resposta
    assert ambiente.conversa.cadastro_voz is None
    ambiente.mic.ativar.assert_not_called()


def test_nome_conjunto_sem_sobrescrever_dono(ambiente):
    dizer(ambiente, "memorize o rosto e a voz da Maria da Silva")
    assert list(ambiente.identidades.ler()["rostos"]) == ["Maria da Silva"]
    assert ambiente.conversa.cadastro_voz["nome"] == "Maria da Silva"


def test_pessoas_diferentes_pedem_esclarecimento(ambiente):
    resposta = dizer(ambiente, "memorize o rosto da Maria e a voz do Pedro")
    assert "duas pessoas" in resposta
    ambiente.rostos_id.vetor_de_um_rosto.assert_not_called()
    ambiente.mic.ativar.assert_not_called()


@pytest.mark.parametrize("texto", ["não memorize meu rosto", "como cadastrar minha voz?", "não apague meu rosto"])
def test_negacao_e_ajuda_nao_iniciam_captura(ambiente, texto):
    dizer(ambiente, texto)
    ambiente.rostos_id.vetor_de_um_rosto.assert_not_called()
    ambiente.mic.ativar.assert_not_called()
    assert not ambiente.identidades._arquivo.exists()


def test_exclusao_sem_nome_nao_apaga_todos(ambiente):
    ambiente.identidades.salvar("rostos", "Maria", vetor())
    assert "De quem" in dizer(ambiente, "esqueça o rosto")
    assert "Maria" in ambiente.identidades.ler()["rostos"]


def test_exclusao_conjunta_preserva_outras_pessoas(ambiente):
    for tipo in ("rostos", "vozes"):
        ambiente.identidades.salvar(tipo, "dono", vetor())
        ambiente.identidades.salvar(tipo, "Maria", vetor(1))
    dizer(ambiente, "esqueça meu rosto e minha voz")
    assert ambiente.identidades.ler() == {"rostos": {"Maria": vetor(1).tolist()}, "vozes": {"Maria": vetor(1).tolist()}}


def test_exclusao_conjunta_de_pessoas_diferentes_nao_altera_nada(ambiente):
    ambiente.identidades.salvar("rostos", "Maria", vetor())
    ambiente.identidades.salvar("vozes", "Pedro", vetor(1))
    antes = ambiente.identidades.ler()
    assert "duas pessoas" in dizer(ambiente, "esqueça o rosto da Maria e a voz do Pedro")
    assert ambiente.identidades.ler() == antes


def test_quadro_congelado_nao_gera_cinco_amostras(ambiente):
    with mock.patch("hud_runtime.comandos.time.monotonic", side_effect=range(20)), mock.patch("hud_runtime.comandos.time.sleep"):
        resposta = ambiente.comandos._cadastrar_rosto("dono")
    assert "três imagens novas" in resposta
    assert not ambiente.identidades.ler()["rostos"]
    ambiente.rostos_id.vetor_de_um_rosto.assert_called_once()


def test_multiplos_rostos_no_meio_nao_sao_ignorados(ambiente):
    ambiente.rostos_id.vetor_de_um_rosto.side_effect = [vetor(), vetor(), vetor(), 2]
    resposta = dizer(ambiente, "memorize meu rosto")
    assert "mais de um rosto" in resposta
    assert not ambiente.identidades.ler()["rostos"]


def test_rosto_muda_nao_cadastra_media_de_pessoas(ambiente):
    ambiente.rostos_id.vetor_de_um_rosto.side_effect = [vetor(), vetor(1)]
    assert "rosto mudou" in dizer(ambiente, "memorize meu rosto")
    assert not ambiente.identidades.ler()["rostos"]


def test_cancelamento_de_rosto_nao_inicia_voz(ambiente):
    with mock.patch("hud_runtime.comandos.time.sleep", side_effect=lambda _: ambiente.conversa.interromper()):
        resposta = ambiente.conversa.atender("memorize meu rosto e minha voz", falar=False)
    assert "cancelado" in resposta
    assert not ambiente.identidades.ler()["rostos"]
    ambiente.mic.ativar.assert_not_called()


def test_voz_aguarda_transcricao_e_microfone(ambiente):
    ambiente.stt.pronta = False
    assert "transcrição" in dizer(ambiente, "memorize minha voz")
    assert ambiente.conversa.cadastro_voz is None
    ambiente.mic.ativar.assert_not_called()


def test_nao_reinicia_cadastro_voz_em_andamento(ambiente):
    dizer(ambiente, "memorize minha voz")
    ambiente.conversa._turno(b"primeira frase")
    assert "Já há um cadastro" in dizer(ambiente, "memorize minha voz")
    assert len(ambiente.conversa.cadastro_voz["vetores"]) == 1


def test_cancelamento_digitado_descarta_coleta_e_desliga_microfone_temporario(ambiente):
    dizer(ambiente, "memorize minha voz")
    dizer(ambiente, "cancele o cadastro da minha voz")
    assert ambiente.conversa.cadastro_voz is None
    assert not ambiente.mic.ativo
    assert not ambiente.identidades.ler()["vozes"]


def test_amostra_atrasada_apos_cancelamento_nao_salva_nem_fala(ambiente):
    dizer(ambiente, "memorize minha voz")
    def terminou_depois(wav, minimo_s):
        ambiente.conversa.cancelar_cadastro_voz()
        return vetor()
    ambiente.falantes.vetor.side_effect = terminou_depois
    ambiente.conversa._turno(b"frase ainda processando")
    assert not ambiente.identidades.ler()["vozes"]
    ambiente.conversa.falar.assert_not_called()


def test_microfone_previamente_ligado_permanece_ligado(ambiente):
    ambiente.mic.ativo = True
    dizer(ambiente, "memorize minha voz")
    ambiente.conversa.cancelar_cadastro_voz()
    ambiente.mic.desativar.assert_not_called()


def test_cadastro_expira_sem_nova_fala(ambiente):
    dizer(ambiente, "memorize minha voz")
    ambiente.conversa.cadastro_voz["ate"] = 0
    assert ambiente.conversa._verificar_cadastro_voz()
    assert ambiente.conversa.cadastro_voz is None
    assert not ambiente.mic.ativo
    assert "expirou" in ambiente.estado.ler("conversa")["ultima_resposta"]


def test_revogacao_de_microfone_cancela_coleta(ambiente):
    dizer(ambiente, "memorize minha voz")
    ambiente.mic.ativo = False
    assert ambiente.conversa._verificar_cadastro_voz()
    assert ambiente.conversa.cadastro_voz is None


def test_erro_de_modelo_nao_e_rotulado_fala_curta(ambiente):
    dizer(ambiente, "memorize minha voz")
    ambiente.falantes.vetor.side_effect = RuntimeError("fixture: sessão indisponível")
    ambiente.conversa._turno(b"frase longa o suficiente")
    assert ambiente.conversa.cadastro_voz is None
    assert "modelo local" in ambiente.conversa.falar.call_args.args[0]
    assert not ambiente.identidades.ler()["vozes"]


def test_vozes_distintas_nao_viram_mesmo_cadastro(ambiente):
    dizer(ambiente, "memorize minha voz")
    ambiente.falantes.vetor.side_effect = [vetor(), vetor(1)]
    ambiente.conversa._turno(b"primeira pessoa")
    ambiente.conversa._turno(b"segunda pessoa")
    assert len(ambiente.conversa.cadastro_voz["vetores"]) == 1
    assert "voz mudou" in ambiente.conversa.falar.call_args.args[0]


def test_falha_de_gravacao_nao_anuncia_sucesso(ambiente):
    dizer(ambiente, "memorize minha voz")
    with mock.patch.object(ambiente.identidades, "salvar", side_effect=OSError("fixture: disco indisponível")):
        for _ in range(3):
            ambiente.conversa._turno(b"amostra de teste")
    assert ambiente.conversa.cadastro_voz is None
    assert "não foi concluído" in ambiente.conversa.falar.call_args.args[0]
    assert not ambiente.identidades.ler()["vozes"]


def test_embeddings_empatados_nao_inventam_identidade(ambiente):
    ambiente.identidades.salvar("rostos", "Maria", vetor())
    ambiente.identidades.salvar("rostos", "Pedro", vetor())
    assert ambiente.identidades.comparar("rostos", vetor(), 0.363)[0] is None


@pytest.mark.parametrize("v", [np.zeros(128), np.array([np.nan]), np.array([np.inf]), np.array([])])
def test_embedding_invalido_nao_e_persistido(ambiente, v):
    with pytest.raises(ValueError):
        ambiente.identidades.salvar("vozes", "dono", v)
    assert not ambiente.identidades._arquivo.exists()
