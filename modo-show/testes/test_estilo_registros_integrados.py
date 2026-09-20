"""Fluxos acessíveis: comando real→prévia→disco; API local→memória revisável."""
from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hud_runtime.comandos import Comandos
from hud_runtime.estado import Estado
from hud_runtime.pecas import Pecas
from hud_runtime.projetos import Projetos
from hud_runtime.registros import executar
from hud_runtime.memoria import Episodios
from hud_runtime.aprendizado import Aprendizado


@pytest.fixture
def contexto(tmp_path):
    rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}),
                         estado=Estado(), pecas=Pecas(tmp_path / "pecas.json", tmp_path / "stl"),
                         projetos=Projetos(tmp_path / "projetos.json"),
                         episodios=Episodios(tmp_path / "hud-episodios.sqlite"),
                         aprendizado=Aprendizado(tmp_path / "hud-aprendizado.sqlite"))
    c = Comandos(rt, lambda p: None)
    c.mostrar_modelo = lambda a: None
    p, _ = rt.pecas.criar("caixa", {"c": 80, "l": 50, "a": 30, "parede": 2})
    def dizer(frase):
        achado = c.interpretar(frase)
        assert achado is not None, frase
        return c.executar(*achado, frase)
    yield rt, c, p, dizer
    rt.episodios.fechar()
    rt.aprendizado.fechar()


def test_estilo_comando_confirmacao_reinicio_reversao(contexto):
    rt, c, p, dizer = contexto
    stl_v1 = Path(p.atual().arquivo).read_bytes()
    assert "Prévia" in dizer("altere o material da peça para PETG")
    assert p.material == "PLA" and p.versao == 1
    assert rt.estado.ler("previa")["material"] == "petg"
    assert "Versão 2" in dizer("confirme a alteração da peça")
    assert p.material == "petg" and p.atual().material == "petg"
    assert "Prévia" in dizer("altere a cor da peça para azul")
    dizer("confirme a alteração da peça")
    assert p.cor == "#2196f3" and rt.estado.ler("peca")["cor"] == p.cor
    assert "material" in dizer("compare as versões 1 e 3")
    assert "cor" in dizer("compare as versões 1 e 3")
    rt.pecas = Pecas(rt.pecas._arq, rt.pecas.pasta())
    p = rt.pecas.ativa()
    assert p.cor == "#2196f3" and p.versao == 3
    dizer("volte para a versão 1")
    assert (p.material, p.cor, p.versao) == ("PLA", "#26c6da", 4)
    assert Path(p.versoes[0].arquivo).read_bytes() == stl_v1
    assert rt.estado.ler("previa")["estado"] == "inativo"


def test_estilo_falha_de_disco_reverte_estado_e_recusa_previa_antiga(contexto):
    rt, c, p, dizer = contexto
    dizer("altere a cor para azul")
    with patch.object(rt.pecas, "salvar", side_effect=OSError("disco indisponível")):
        assert "Não consolidei" in dizer("confirme a alteração da peça")
    assert p.versao == 1 and p.cor == "#26c6da"
    rt.pecas.alterar(p, "l", delta=1)
    assert "peça mudou" in dizer("confirme a alteração da peça")
    assert p.versao == 2 and p.cor == "#26c6da"


def test_cores_invalidas_nao_modificam_peca(contexto):
    rt, _, p, dizer = contexto
    assert "Não preparei" in dizer("altere a cor para javascript:alert(1)")
    assert p.versao == 1 and p.cor == "#26c6da"


def test_episodio_rota_corrige_e_remove_derivados(contexto):
    rt, c, _, _ = contexto
    rota = "/api/memoria/episodios"
    episodio = executar(c, rota, {"acao": "registrar", "atividade": "ensaio da caixa",
                                 "resultado": "encaixou", "escopo": "caixa", "origem": "sensor"})["episodio"]
    assert episodio["origem"] == "usuario" and not episodio["verificacao_automatica"]
    assert executar(c, rota, {"acao": "listar", "escopo": "caixa"})["episodios"][0]["id"] == episodio["id"]
    executar(c, "/api/aprendizado", {"acao": "optar", "ativo": True})
    exemplo = executar(c, "/api/aprendizado", {
        "acao": "registrar", "pedido": "qual o encaixe", "contexto": "ensaio documentado",
        "acao_executada": "consultar ensaio", "resultado": "encaixou", "correcao": "dizer que foi um relato",
        "verificado": True, "aprovado": True, "sucesso": True,
        "fontes": [{"tipo": "episodio", "id": episodio["id"]}]})["exemplo"]
    assert exemplo["id"]
    executar(c, rota, {"acao": "corrigir", "id": episodio["id"], "resultado": "não encaixou"})
    assert executar(c, "/api/aprendizado", {"acao": "listar"})["exemplos"] == []
    assert executar(c, rota, {"acao": "esquecer", "id": episodio["id"]})["apagado"]
    assert executar(c, rota, {"acao": "listar"})["episodios"] == []


def test_coleta_nunca_e_ativada_implicitamente(contexto):
    _, c, _, _ = contexto
    rota = "/api/aprendizado"
    assert executar(c, rota, {})["estado"]["coleta_ativa"] is False
    with pytest.raises(ValueError, match="desativada"):
        executar(c, rota, {"acao": "registrar"})
    with pytest.raises(ValueError):
        executar(c, rota, {"acao": "optar", "ativo": "true"})


def test_requisitos_acessiveis_e_hud_sem_argumentos_internos(contexto):
    rt, c, _, _ = contexto
    t = rt.projetos.criar("prototipar caixa")
    r = executar(c, "/api/projetos/requisitos", {"id": t.id, "conclusao_quando": "encaixe conferido",
                                                "restricoes": ["sem colar"], "recursos": ["paquímetro"], "depende_de": []})
    assert r["tarefa"]["versao"] == 2
    canal = rt.estado.ler("projeto")["tarefa"]
    assert canal["restricoes"] == ["sem colar"]
    assert "ferramentas_modelo" not in canal
    with pytest.raises(ValueError, match="cíclica"):
        executar(c, "/api/projetos/requisitos", {"id": t.id, "depende_de": [t.id]})


def test_modelo_nao_consegue_conferir_etapa_nem_retomar_recursivamente(contexto):
    _, c, _, _ = contexto
    for frase in ("etapa 2 não foi executada", "continue de ontem"):
        assert "Não executei" in c.executar_ferramenta("executar_comando", {"frase": frase})
