"""Correcoes da integracao (prompt mestre de 18/09/2026), itens A1-A4 da matriz
em modo-show/INVENTARIO.md."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest

from openjarvis.core.types import Message, Role
from openjarvis.engine._base import EngineConnectionError
from openjarvis.engine.openai_compat_engines import VLLMEngine
from openjarvis.system.orchestrator import (
    _construct_agent,
    _direct_messages,
    _is_negated_request,
    _mentions_only_in_quotes,
)


# --- A1: ramo direto preserva persona e historico -------------------------

def test_direct_messages_keep_persona_and_history():
    prior = [Message(role=Role.USER, content="oi"), Message(role=Role.ASSISTANT, content="ola")]
    msgs = _direct_messages([Message(role=Role.USER, content="e amanha?")], "Voce e o Jarvis.", prior)
    assert [m.role for m in msgs] == [Role.SYSTEM, Role.USER, Role.ASSISTANT, Role.USER]
    assert msgs[0].content == "Voce e o Jarvis."
    assert msgs[-1].content == "e amanha?"


def test_direct_messages_merge_memory_system_turn():
    com_contexto = [Message(role=Role.SYSTEM, content="[memoria] prefere cafe"),
                    Message(role=Role.USER, content="pergunta")]
    msgs = _direct_messages(com_contexto, "Persona.", None)
    assert sum(m.role == Role.SYSTEM for m in msgs) == 1          # um unico system
    assert "Persona." in msgs[0].content and "[memoria]" in msgs[0].content


def test_direct_messages_without_extras_is_unchanged():
    m = [Message(role=Role.USER, content="x")]
    assert _direct_messages(m, None, None) == m


def test_orchestrator_direct_branch_passes_them_to_engine():
    from openjarvis.system.orchestrator import QueryOrchestrator

    s = MagicMock()
    s.config.agent.context_from_memory = False
    s.agent_name = "none"
    s.engine.generate.return_value = {"content": "ok", "usage": {}}
    QueryOrchestrator(s).ask("e amanha?", agent="none", system_prompt="Persona.",
                             prior_messages=[Message(role=Role.USER, content="antes")])
    enviados = s.engine.generate.call_args[0][0]
    assert enviados[0].role == Role.SYSTEM and enviados[1].content == "antes"


# --- A2: intencao de briefing ----------------------------------------------

@pytest.fixture()
def system():
    from openjarvis.system import JarvisSystem

    sys_ = JarvisSystem.__new__(JarvisSystem)
    sys_.engine = MagicMock()
    sys_.model = "m"
    sys_.agent_name = "simple"
    sys_.tools = []
    sys_.bus = MagicMock()
    return sys_


@pytest.mark.parametrize("frase", ["Jarvis, prepare meu dia", "me atualize", "Quero o resumo do dia",
                                   "Good morning", "daily briefing please"])
def test_briefing_explicito_roteia(system, frase):
    with patch("openjarvis.core.registry.AgentRegistry") as reg:
        reg.contains.return_value = True
        assert system._detect_agent_intent(frase) == "morning_digest"


@pytest.mark.parametrize("frase", ["Bom dia, Jarvis!", "não quero o resumo do dia",
                                   'o que significa "morning briefing"?', "don't give me the daily briefing",
                                   "sem briefing hoje"])
def test_saudacao_negacao_e_citacao_nao_roteiam(system, frase):
    with patch("openjarvis.core.registry.AgentRegistry") as reg:
        reg.contains.return_value = True
        assert system._detect_agent_intent(frase) is None


def test_helpers_de_intencao():
    assert _mentions_only_in_quotes('o que é "resumo do dia"?')
    assert not _mentions_only_in_quotes("prepare meu dia")
    assert _is_negated_request("não me atualize agora")


# --- A3: 400 com tools nao vira resposta textual silenciosa ----------------

def _engine_com(handler) -> VLLMEngine:
    eng = VLLMEngine(host="http://testhost:8000")
    eng._client.close()
    eng._client = httpx.Client(base_url="http://testhost:8000", transport=httpx.MockTransport(handler))
    return eng


TOOLS = [{"type": "function", "function": {"name": "abrir", "parameters": {"type": "object", "properties": {}}}}]


def test_400_por_tools_refaz_sem_tools_e_avisa(caplog):
    pedidos = []

    def handler(req):
        corpo = json.loads(req.content)
        pedidos.append(corpo)
        if "tools" in corpo:
            return httpx.Response(400, text='{"error": "model does not support tools"}')
        return httpx.Response(200, json={"choices": [{"message": {"content": "texto"}}]})

    eng = _engine_com(handler)
    with caplog.at_level(logging.WARNING):
        r = eng.generate([Message(role=Role.USER, content="abra")], model="m", tools=TOOLS)
    eng.close()
    assert len(pedidos) == 2 and "tools" not in pedidos[1]
    assert r["capability_lost"] == ["tools"]
    assert "rejected tool calling" in caplog.text


def test_400_por_outro_parametro_nao_descarta_tools():
    pedidos = []

    def handler(req):
        pedidos.append(json.loads(req.content))
        return httpx.Response(400, text='{"error": "max_tokens must be <= 4096"}')

    eng = _engine_com(handler)
    with pytest.raises(EngineConnectionError, match="400"):
        eng.generate([Message(role=Role.USER, content="abra")], model="m", tools=TOOLS)
    eng.close()
    assert len(pedidos) == 1                                   # sem reenvio silencioso


# --- A4: construtor do agente --------------------------------------------

class _AgenteSimples:
    def __init__(self, engine, model, *, bus=None, temperature=0.7):
        self.engine, self.model, self.bus, self.temperature = engine, model, bus, temperature


class _AgenteQuebra:
    def __init__(self, engine, model, *, bus=None):
        raise TypeError("erro interno de configuracao")


class _AgenteLegado:
    def __init__(self):
        self.ok = True


def test_descarta_so_o_que_nao_existe_e_registra(caplog):
    with caplog.at_level(logging.WARNING):
        ag = _construct_agent(_AgenteSimples, "E", "M", {"bus": 1, "temperature": 0.2, "persona": "x"}, "t")
    assert (ag.bus, ag.temperature) == (1, 0.2)
    assert "persona" in caplog.text


def test_typeerror_interno_nao_e_engolido():
    with pytest.raises(TypeError, match="erro interno"):
        _construct_agent(_AgenteQuebra, "E", "M", {"bus": 1}, "t")


def test_agente_legado_sem_argumentos():
    assert _construct_agent(_AgenteLegado, "E", "M", {"bus": 1}, "t").ok


# ---- M1: esquecer um fato so (sem cair para clear) -----------------------


def test_remove_reviewed_esquece_so_o_fato_conferido(tmp_path):
    from openjarvis.memory.store import LocalFactStore

    store = LocalFactStore(tmp_path / "facts.jsonl")
    store.add("meu time é o Santos", source="hud-voz", trust="trusted")
    store.add("prefiro café sem açúcar", source="hud-voz", trust="trusted")
    assert not store.remove_reviewed(0, "texto que mudou")  # conferencia falhou
    assert store.remove_reviewed(0, "meu time é o Santos")
    assert [f.text for f in LocalFactStore(tmp_path / "facts.jsonl").list()] == [
        "prefiro café sem açúcar"
    ]
    assert not store.remove_reviewed(5, "x")


def test_remove_reviewed_padrao_nao_apaga_tudo():
    from openjarvis.memory.store import FactStore

    class SoAdd(FactStore):
        def add(self, text, source=""):
            return True

        def list(self):
            return []

        def clear(self):
            raise AssertionError("não pode cair para clear")

        def count(self):
            return 0

    with pytest.raises(NotImplementedError):
        SoAdd().remove_reviewed(0, "x")


def test_cli_memory_forget(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from openjarvis.cli import memory_cmd
    from openjarvis.memory.store import LocalFactStore

    store = LocalFactStore(tmp_path / "facts.jsonl")
    store.add("um", trust="trusted")
    store.add("dois", trust="trusted")
    monkeypatch.setattr(memory_cmd, "_get_fact_store", lambda: store)
    r = CliRunner().invoke(memory_cmd.memory, ["forget", "2"])
    assert r.exit_code == 0, r.output
    assert "dois" in r.output
    assert [f.text for f in store.list()] == ["um"]
    r = CliRunner().invoke(memory_cmd.memory, ["forget", "9"])
    assert r.exit_code == 1
