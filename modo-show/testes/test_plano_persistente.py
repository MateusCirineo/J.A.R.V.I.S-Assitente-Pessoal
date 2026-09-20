"""Planos do modelo usam Projetos e arquivos reais isolados; modelo é fixture."""
import json
import sys
import threading
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hud_runtime.execucao_modelo import executar_plano, retomar_plano, validar_argumentos
from hud_runtime.projetos import Projetos
from hud_runtime.comandos import FERRAMENTAS

TOOLS = [{"type": "function", "function": {"name": "gravar", "parameters": {
    "type": "object", "properties": {"arquivo": {"type": "string"}}, "required": ["arquivo"]}}}]
PEDIDO = {"tools": TOOLS, "messages": [{"role": "user", "content": "grave dois resultados"}]}


def lote(*arquivos):
    return {"tool_calls": [{"id": f"c{i}", "type": "function", "function": {
        "name": "gravar", "arguments": json.dumps({"arquivo": str(p)})}}
        for i, p in enumerate(arquivos)]}


def revisado(_):
    return {"choices": [{"message": {"content": "Resultados revisados pela fixture"}}]}


def executar_arquivo(nome, args):
    assert nome == "gravar"
    arq = Path(args["arquivo"])
    assert not arq.exists(), "escrita duplicada"
    arq.write_text("resultado da ferramenta real", encoding="utf-8")
    return {"ok": True, "texto": str(arq)}


def iniciar(projetos, primeira, executar=executar_arquivo, cancelado=None, consultar=revisado, **extra):
    return executar_plano(primeira, PEDIDO, consultar, executar, cancelado or threading.Event(), Mock(),
                          projetos=projetos, objetivo="grave dois resultados", sessao_id="s1", pedido_id="p1", **extra)


def test_lote_e_ids_persistem_antes_de_executar_e_preservam_projeto(tmp_path):
    p = Projetos(tmp_path / "projetos.json")
    pai = p.criar("projeto caixa", projeto="caixa", restricoes=["milímetros"], recursos=["manual autorizado"])
    def gravar(nome, args):
        dados = json.loads(p._arq.read_text(encoding="utf-8"))
        t = next(t for t in dados["tarefas"] if t["origem"] == "modelo")
        assert len(t["etapas"]) == 2
        executando = next(e for e in t["etapas"] if e["estado"] == "em_execucao")
        assert executando["acao_id"]
        assert t["sessao_id"] == "s1" and t["pedido_id"] == "p1"
        return executar_arquivo(nome, args)
    resposta, rastros = iniciar(p, lote(tmp_path / "a", tmp_path / "b"), gravar)
    t = p.por_pedido("s1", "p1")
    assert t.projeto == "caixa" and t.tarefa_pai == pai.id
    assert "milímetros" in t.restricoes and "manual autorizado" in t.recursos
    assert t.etapas[1].depende_de == [0]
    assert t.estado == "executada_sem_verificacao" and t.plano_encerrado
    assert t.chamadas_usadas == 2 and len(t.prontas()) == 2
    assert all(e["acao_id"] for e in t.eventos_execucao)
    assert str(tmp_path / "a") in resposta and str(tmp_path / "b") in resposta
    assert p.inspecionar(t.id)["restricoes_fonte"].startswith("declaradas")
    assert pai.estado == "planejada"


def test_pausa_e_reinicio_retomam_so_segunda_escrita(tmp_path):
    p = Projetos(tmp_path / "p.json")
    cancelado = threading.Event()
    def primeira(nome, args):
        retorno = executar_arquivo(nome, args)
        cancelado.set()
        return retorno
    resultado, _ = iniciar(p, lote(tmp_path / "a", tmp_path / "b"), primeira, cancelado)
    assert resultado is None
    t = p.ativa()
    assert t.estado == "pausada" and t.etapas[0].pronta and not t.etapas[1].pronta
    reiniciado = Projetos(p._arq)
    cancelado.clear()
    resposta, _ = retomar_plano(reiniciado, t.id, TOOLS, executar_arquivo, cancelado, Mock(), consultar=revisado)
    t = reiniciado.obter(t.id)
    assert t.estado == "executada_sem_verificacao"
    assert t.chamadas_usadas == 2
    assert all(e.tentativas == 1 for e in t.etapas)
    assert str(tmp_path / "a") in resposta and str(tmp_path / "b") in resposta


def test_efeito_incerto_exige_conferencia_e_nao_repete(tmp_path):
    p = Projetos(tmp_path / "p.json")
    def queda(nome, args):
        executar_arquivo(nome, args)
        raise ConnectionError("fixture depois de escrever")
    iniciar(p, lote(tmp_path / "a", tmp_path / "b"), queda)
    t = p.ativa()
    assert t.etapas[0].estado == "resultado_incerto"
    executar = Mock()
    retomar_plano(p, t.id, TOOLS, executar, threading.Event(), Mock())
    executar.assert_not_called()
    p.conferir_etapa(t.id, 0, executada=True, evidencia="arquivo A lido e conferido")
    retomar_plano(p, t.id, TOOLS, executar_arquivo, threading.Event(), Mock(), consultar=revisado)
    assert t.etapas[0].tentativas == 1 and t.etapas[1].pronta
    assert "arquivo A lido" in " ".join(t.resultados)


def test_cancelar_durante_efeito_nao_reabre_nem_inicia_proxima(tmp_path):
    p = Projetos(tmp_path / "p.json")
    def cancelar(nome, args):
        retorno = executar_arquivo(nome, args)
        p.mudar_estado(p.ativa().id, "cancelada", "usuário cancelou")
        return retorno
    resposta, _ = iniciar(p, lote(tmp_path / "a", tmp_path / "b"), cancelar)
    t = p.por_pedido("s1", "p1")
    assert resposta is None and t.estado == "cancelada" and t.etapas[0].pronta
    retomar_plano(p, t.id, TOOLS, executar_arquivo, threading.Event(), Mock())
    assert not (tmp_path / "b").exists()


def test_reconexao_mesmo_pedido_nao_refaz_nem_consulta_modelo(tmp_path):
    p = Projetos(tmp_path / "p.json")
    primeira = lote(tmp_path / "a", tmp_path / "b")
    iniciar(p, primeira)
    consultar, executar = Mock(), Mock()
    resultado, _ = iniciar(Projetos(p._arq), primeira, executar, consultar=consultar)
    assert "já registrado" in resultado
    consultar.assert_not_called()
    executar.assert_not_called()


def test_schema_removido_ao_retomar_nao_executa(tmp_path):
    p = Projetos(tmp_path / "p.json")
    cancel = threading.Event()
    def primeira(nome, args):
        retorno = executar_arquivo(nome, args)
        cancel.set()
        return retorno
    iniciar(p, lote(tmp_path / "a", tmp_path / "b"), primeira, cancel)
    t = p.ativa()
    executar = Mock()
    resposta, _ = retomar_plano(p, t.id, [], executar, threading.Event(), Mock(), consultar=revisado)
    executar.assert_not_called()
    assert "ferramenta desconhecida" in resposta
    assert not t.plano_encerrado and not t.etapas[1].pronta


def test_dependencia_real_bloqueia_ate_tarefa_concluida(tmp_path):
    p = Projetos(tmp_path / "p.json")
    dep = p.criar("confirmar dimensões")
    pai = p.criar("caixa", depende_de=[dep.id], projeto="caixa")
    executar = Mock()
    iniciar(p, lote(tmp_path / "a"), executar)
    t = p.ativa()
    executar.assert_not_called()
    assert t.depende_de == [dep.id] and t.estado == "aguardando_informacao"
    p.mudar_estado(dep.id, "concluida", "usuário conferiu")
    retomar_plano(p, t.id, TOOLS, executar_arquivo, threading.Event(), Mock(), consultar=revisado)
    assert t.etapas[0].pronta and t.tarefa_pai == pai.id


def test_requisitos_versionados_rejeitam_ciclo_e_limpam_aprovacao(tmp_path):
    p = Projetos(tmp_path / "p.json")
    a, b = p.criar("A"), p.criar("B")
    p.aprovar(a.id, "editar", "anterior")
    p.definir_requisitos(a.id, depende_de=[b.id], conclusao_quando="dimensões conferidas",
                        restricoes=["largura máxima 80 mm"], recursos=["manual.txt"])
    assert a.versao == 2 and not a.aprovacoes
    with pytest.raises(ValueError, match="cíclica"):
        p.definir_requisitos(b.id, depende_de=[a.id])
    with pytest.raises(ValueError, match="inexistente"):
        p.definir_requisitos(a.id, depende_de=["ausente"])
    assert p.inspecionar(a.id)["dependencias"] == [{"id": b.id, "estado": b.estado}]


def test_plano_inteiro_precisa_persistir_antes_de_escrever(tmp_path):
    p = Projetos(tmp_path / "p.json")
    executar = Mock()
    with patch.object(p, "registrar_plano_modelo", side_effect=OSError("disco cheio")):
        with pytest.raises(OSError):
            iniciar(p, lote(tmp_path / "a"), executar)
    executar.assert_not_called()


def test_falha_ao_gravar_resultado_deixa_reserva_incerta_apos_restart(tmp_path):
    p = Projetos(tmp_path / "p.json")
    salvar = p.salvar
    def disco():
        t = p.por_pedido("s1", "p1")
        if t and t.etapas and t.etapas[0].pronta:
            raise OSError("fixture depois do efeito")
        salvar()
    with patch.object(p, "salvar", side_effect=disco):
        with pytest.raises(OSError):
            iniciar(p, lote(tmp_path / "a", tmp_path / "b"))
    reiniciado = Projetos(p._arq)
    t = reiniciado.por_pedido("s1", "p1")
    assert t.etapas[0].estado == "resultado_incerto"
    retomar_plano(reiniciado, t.id, TOOLS, executar_arquivo, threading.Event(), Mock())
    assert not (tmp_path / "b").exists()


@pytest.mark.parametrize("retorno", [{"ok": False, "texto": "arquivo indisponível"},
                                    "Não executei: comando não permitido.", None, {"ok": True}])
def test_falha_da_ferramenta_nao_termina_tarefa_nem_avanca(tmp_path, retorno):
    p = Projetos(tmp_path / "p.json")
    executar = Mock(return_value=retorno)
    iniciar(p, lote(tmp_path / "a", tmp_path / "b"), executar)
    t = p.por_pedido("s1", "p1")
    assert t.estado in ("falha", "aguardando_informacao")
    assert not t.plano_encerrado and executar.call_count == 1


def test_limite_persistido_nao_reinicia_quando_retomar(tmp_path):
    p = Projetos(tmp_path / "p.json")
    consultar = Mock(return_value={"choices": [{"message": lote(tmp_path / "a")} ]})
    iniciar(p, lote(tmp_path / "a"), consultar=consultar)
    t = p.ativa()
    assert t.chamadas_usadas == 5 and t.etapas[0].tentativas == 1
    executar = Mock()
    retomar_plano(p, t.id, TOOLS, executar, threading.Event(), Mock(),
                 consultar=lambda _: {"choices": [{"message": lote(tmp_path / "b")}]})
    executar.assert_not_called()
    assert t.chamadas_usadas == 5


def test_retomada_nao_amplia_catalogo_e_revalida_restricoes_atuais(tmp_path):
    p = Projetos(tmp_path / "p.json")
    cancel = threading.Event()
    def primeira(nome, args):
        retorno = executar_arquivo(nome, args)
        cancel.set()
        return retorno
    iniciar(p, lote(tmp_path / "a", tmp_path / "b"), primeira, cancel)
    t = p.ativa()
    novas = [{"type": "function", "function": {"name": "nova_permissao", "parameters": {
        "type": "object", "properties": {}}}}]
    atual = json.loads(json.dumps(TOOLS))
    atual[0]["function"]["parameters"]["properties"]["arquivo"]["enum"] = [str(tmp_path / "a")]
    vistos = []
    def consultar(pedido):
        vistos.append(pedido)
        return revisado(pedido)
    executar = Mock()
    resposta, _ = retomar_plano(p, t.id, atual + novas, executar, threading.Event(), Mock(), consultar=consultar)
    executar.assert_not_called()
    assert "não permitido" in resposta
    assert [f["function"]["name"] for f in vistos[0]["tools"]] == ["gravar"]


def test_conversa_comando_retoma_plano_persistido_e_publica_mesmo_resultado(tmp_path):
    import io
    from types import SimpleNamespace
    from hud_runtime.comandos import Comandos
    from hud_runtime.estado import Estado
    from hud_runtime.pecas import Pecas
    from hud_runtime.voz import Conversa
    c = Conversa.__new__(Conversa)
    c._estado, c._cancelado = Estado(), threading.Event()
    c._prefs = SimpleNamespace(ler=lambda: {"voz_rapida": True})
    rt = SimpleNamespace(estado=c._estado, prefs=c._prefs, conversa=c,
                         projetos=Projetos(tmp_path / "projetos.json"),
                         pecas=Pecas(tmp_path / "pecas.json", pasta=tmp_path / "stl"), selecao=None)
    c.comandos = Comandos(rt, lambda *a: None)
    c.comandos.contexto_para_modelo = lambda texto: None
    c.clima = c.falante = c.memoria = None
    c._historico = []
    c._imagem_para = lambda *args: (None, None, None)
    c._ponte_conectada = lambda: True
    c._estado.atualizar("pedido", sessao_id="chat-A", pedido_id="pedido-A")
    objetivo = "calcule 17 vezes 19 e depois calcule 25 por cento de 480"
    chamadas = [{"id": f"c{i}", "type": "function", "function": {"name": "executar_comando",
                "arguments": json.dumps({"frase": frase})}} for i, frase in enumerate(
                ["calcule 17 vezes 19", "calcule 25 por cento de 480"])]
    original = c.comandos.executar_ferramenta
    def primeira(nome, args):
        retorno = original(nome, args)
        c._cancelado.set()
        return retorno
    resposta = {"choices": [{"message": {"tool_calls": chamadas}}]}
    with patch("hud_runtime.voz.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(resposta).encode())), \
         patch.object(c.comandos, "executar_ferramenta", side_effect=primeira):
        assert c._perguntar_com(objetivo, {}, "modelo-fixture", None, False, None) is None
    rt.projetos = Projetos(rt.projetos._arq)
    t = rt.projetos.por_pedido("chat-A", "pedido-A")
    assert t.estado == "pausada" and len(t.prontas()) == 1
    c._cancelado.clear()
    pedidos = []
    def http(request, **kwargs):
        pedidos.append(json.loads(request.data))
        return io.BytesIO(json.dumps(revisado(None)).encode())
    with patch("hud_runtime.voz.escolher", return_value=("modelo-fixture", None)), \
         patch("hud_runtime.voz.urllib.request.urlopen", side_effect=http):
        resposta = c.comandos.executar("projeto_continuar", {}, "continue de ontem")
    assert "323" in resposta and "120" in resposta
    assert t.estado == "executada_sem_verificacao" and all(e.tentativas == 1 for e in t.etapas)
    assert c._estado.ler("projeto")["tarefa"]["id"] == t.id
    assert c._estado.ler("projeto")["tarefa"]["resultados"] == t.resultados
    assert len(pedidos[0]["tools"]) == 1
    assert "Calculadora real" in pedidos[0]["tools"][0]["function"]["description"]
    assert any(m["role"] == "tool" and "323" in m["content"] for m in pedidos[0]["messages"])
def test_duas_calls_com_mesmo_id_nao_associam_argumentos_errados(tmp_path):
    p = Projetos(tmp_path / "p.json")
    primeira = lote(tmp_path / "a", tmp_path / "b")
    primeira["tool_calls"][1]["id"] = primeira["tool_calls"][0]["id"]
    executar = Mock()
    resposta, _ = iniciar(p, primeira, executar)
    assert "identificador" in resposta
    executar.assert_not_called()


def test_comando_composto_em_uma_toolcall_nao_corta_segunda_acao():
    erro = validar_argumentos("executar_comando", {"frase": "calcule 17 vezes 19 e depois calcule 25 por cento de 480"}, FERRAMENTAS)
    assert "única ação" in erro


def test_restart_durante_efeito_cancelado_nao_reabre_tarefa(tmp_path):
    p = Projetos(tmp_path / "p.json")
    t = p.criar("operação", etapas=["escrever"], origem="modelo")
    p.iniciar_etapa(t.id, 0)
    p.mudar_estado(t.id, "cancelada", "parada explícita")
    reiniciado = Projetos(p._arq)
    salvo = reiniciado.obter(t.id)
    assert salvo.estado == "cancelada"
    assert salvo.etapas[0].estado == "resultado_incerto"
    executar = Mock()
    retomar_plano(reiniciado, t.id, TOOLS, executar, threading.Event(), Mock())
    executar.assert_not_called()


@pytest.mark.parametrize("comando", ["projeto_continuar", "projeto_etapa_nao_executada", "corrigir_apelido",
                                     "corrigir_esquecer", "corrigir_ensinar", "casa_confirmar",
                                     "id_registro_futuro", "memoria_guardar"])
def test_protocolo_nao_fabrica_consentimento_nem_retomada_recursiva(tmp_path, comando):
    from hud_runtime.protocolos import Protocolos, validar_passos
    interpretar = lambda texto: (comando, {})
    _, erro = validar_passos(["frase da fixture"], interpretar)
    assert "não pode rodar sozinho" in erro
    pr = Protocolos(tmp_path / "protocolos.json")
    pr.salvar("teste", ["frase da fixture"])
    p = Projetos(tmp_path / "projetos.json")
    executar = Mock()
    with pytest.raises(ValueError, match="não pode rodar sozinho"):
        pr.executar("teste", p, interpretar, executar)
    executar.assert_not_called()
