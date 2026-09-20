"""T05/T19: trocar projeto nunca altera a peça do trabalho anterior.

Persistência JSON e STL reais em tmp_path; apenas a entrega ao renderizador
é capturada, sem afirmar validação visual humana.
"""

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hud_runtime.comandos import Comandos
from hud_runtime.estado import Estado
from hud_runtime.pecas import Pecas
from hud_runtime.projetos import Projetos
from hud_runtime.selecao import Selecionador


@pytest.fixture
def contexto(tmp_path):
    rt = SimpleNamespace(
        prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}),
        estado=Estado(), pecas=Pecas(tmp_path / "pecas.json", pasta=tmp_path / "stl"),
        projetos=Projetos(tmp_path / "projetos.json"), selecao=Selecionador(),
        ultimo_projeto=None, holograma_modelo=None,
    )
    c = Comandos(rt, lambda pagina: None)
    mostrados = []
    c.mostrar_modelo = mostrados.append

    def dizer(frase):
        achado = c.interpretar(frase)
        assert achado is not None, frase
        return c.executar(achado[0], achado[1], frase)

    return rt, c, dizer, mostrados


def criar_caixa(rt, nome):
    return rt.pecas.criar("caixa", {"c": 80, "l": 50, "a": 30, "parede": 2},
                         nome=nome, projeto=rt.projetos.projeto)[0]


def test_trocar_projeto_invalida_previa_e_nao_edita_peca_anterior(contexto):
    rt, c, dizer, _ = contexto
    dizer("comece o projeto caixa A")
    a = criar_caixa(rt, "corpo A")
    arquivo = Path(a.atual().arquivo)
    bytes_originais = arquivo.read_bytes()
    rt.selecao.selecionar("peca", a.nome)
    assert "Prévia" in dizer("aumente a largura em 2 milimetros")
    assert c._previa_peca is not None

    dizer("comece o projeto luminaria B")
    assert rt.pecas.ativa() is None
    assert rt.selecao.atual() is None
    assert c._previa_peca is None
    assert rt.estado.ler("peca")["nome"] is None
    assert rt.estado.ler("previa")["estado"] == "inativo"
    assert rt.ultimo_projeto is None
    assert rt.holograma_modelo is None
    assert "não há peça aberta" in dizer("aumente a largura em 2 milimetros")
    assert "não há peça aberta" in dizer("confirme a alteracao da peca")
    assert a.versao == 1 and a.parametros["l"] == 50
    assert arquivo.read_bytes() == bytes_originais
    assert rt.projetos.ativa().resultados == []


def test_retomar_restabelece_peca_e_preserva_historico_dos_dois_projetos(contexto):
    rt, _, dizer, mostrados = contexto
    dizer("comece o projeto caixa A")
    a = criar_caixa(rt, "corpo A")
    tarefa_a = rt.projetos.ativa()
    arquivo_a = Path(a.atual().arquivo)
    bytes_a = arquivo_a.read_bytes()
    dizer("comece o projeto luminaria B")
    b = criar_caixa(rt, "corpo B")
    tarefa_b = rt.projetos.ativa()
    arquivo_b = Path(b.atual().arquivo)
    bytes_b = arquivo_b.read_bytes()

    dizer("continue o projeto caixa A")
    assert rt.projetos.ativa().id == tarefa_a.id
    assert rt.pecas.ativa() is a
    assert mostrados[-1] == a.atual().arquivo
    assert "Prévia" in dizer("aumente a largura em 2 milimetros")
    assert a.versao == 1
    assert "Versão 2" in dizer("confirme a alteracao da peca")
    assert a.parametros["l"] == 52
    assert tarefa_a.resultados and tarefa_b.resultados == []
    assert b.versao == 1 and b.parametros["l"] == 50
    assert arquivo_a.read_bytes() == bytes_a
    assert arquivo_b.read_bytes() == bytes_b

    dizer("continue o projeto luminaria B")
    assert rt.pecas.ativa() is b
    assert rt.ultimo_projeto == b.atual().arquivo
    reaberto = Pecas(rt.pecas._arq, pasta=rt.pecas.pasta())
    assert reaberto.focar_projeto("caixa A").versao == 2
    assert reaberto.focar_projeto("luminaria B").versao == 1


def test_foco_por_projeto_preserva_escolha_entre_varias_pecas(tmp_path):
    acervo = Pecas(tmp_path / "pecas.json", pasta=tmp_path / "stl")
    params = {"diametro": 20, "altura": 30}
    a1, _ = acervo.criar("cilindro", params, nome="primeira", projeto="A")
    acervo.criar("cilindro", params, nome="segunda", projeto="A")
    acervo.focar(a1.nome)
    b, _ = acervo.criar("cilindro", params, nome="terceira", projeto="B")
    reaberto = Pecas(acervo._arq, pasta=acervo.pasta())
    assert reaberto.focar_projeto("A").nome == a1.nome
    assert reaberto.focar_projeto("B").nome == b.nome
    assert reaberto.focar_projeto("novo") is None


def test_selecao_tardia_de_outro_projeto_nao_edita_nem_consolida(contexto):
    rt, c, dizer, _ = contexto
    dizer("comece o projeto caixa A")
    a = criar_caixa(rt, "corpo A")
    dizer("comece o projeto luminaria B")
    b = criar_caixa(rt, "corpo B")
    dizer("aumente a largura em 2 milimetros")
    rt.selecao.selecionar("peca", a.nome, a.nome)
    resposta = dizer("aumente isso na largura em 2 milimetros")
    assert "outro projeto" in resposta
    assert rt.pecas.ativa() is b
    assert c._previa_peca is None
    assert "Não há prévia" in dizer("confirme a alteracao da peca")
    assert a.versao == b.versao == 1


def test_foco_legado_inconsistente_e_recusado_antes_de_editar(contexto):
    rt, _, dizer, _ = contexto
    dizer("comece o projeto caixa A")
    a = criar_caixa(rt, "corpo A")
    rt.projetos.abrir_projeto("B")  # Simula JSON antigo ou foco trocado por outra entrada.
    assert "outro projeto" in dizer("aumente a largura em 2 milimetros")
    assert rt.pecas.ativa() is None
    assert a.versao == 1 and a.parametros["l"] == 50


def test_componente_selecionado_nao_muda_montagem_inteira_por_substring(contexto):
    rt, c, dizer, mostrados = contexto
    dizer("comece o projeto caixa A")
    dizer("monte uma caixa com tampa de 80 por 50 por 30 milimetros")
    peca = rt.pecas.ativa()
    dizer("aumente a largura em 2 milimetros")
    exibidos = len(mostrados)
    rt.selecao.selecionar("componente", "tampa", "tampa")
    resposta = dizer("aumente isso na largura em 2 milimetros")
    assert "componente tampa" in resposta
    assert "compartilham" in resposta
    assert len(mostrados) == exibidos
    assert c._previa_peca is None
    assert "Não há prévia" in dizer("confirme a alteracao da peca")
    assert peca.versao == 1 and peca.parametros["l"] == 50
    assert "Prévia" in dizer("aumente a espessura da tampa em 1 milimetro")
    dizer("confirme a alteracao da peca")
    assert peca.versao == 2 and peca.parametros["tampa"] == 3
    assert peca.parametros["l"] == 50
