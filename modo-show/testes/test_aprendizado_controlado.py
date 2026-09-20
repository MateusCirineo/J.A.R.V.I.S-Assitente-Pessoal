"""Persistência real temporária; nenhum modelo treinado e nenhum dado pessoal lido."""
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hud_runtime.aprendizado import Aprendizado
from hud_runtime.memoria import Episodios, Memoria, id_fato
from hud_runtime.conhecimento import Conhecimento
from hud_runtime.correcoes import Correcoes
from openjarvis.memory.store import LocalFactStore


def exemplo(colecao, pedido="calcule dois mais dois", **kwargs):
    parametros = dict(verificado=True, aprovado=True, sucesso=True)
    parametros.update(kwargs)
    return colecao.registrar(pedido, "calculadora local autorizada", "somar 2 e 2",
                            "a calculadora retornou 4", "usar ferramenta para conferir", **parametros)


def episodio(store, **kwargs):
    return store.registrar("Teste da caixa", "Largura medida: 20 mm", origem="ensaio conferido",
                          escopo="projeto-caixa", **kwargs)


def test_coleta_desativada_exige_opt_in_persistente(tmp_path):
    arq = tmp_path / "hud-aprendizado.sqlite"
    colecao = Aprendizado(arq)
    with pytest.raises(ValueError, match="desativada"):
        exemplo(colecao)
    assert not colecao.estado()["coleta_automatica"]
    colecao.optar(True)
    exemplo(colecao)
    colecao.fechar()
    colecao = Aprendizado(arq)
    assert colecao.estado()["adaptacao"] == 1
    colecao.optar(False)
    with pytest.raises(ValueError, match="desativada"):
        exemplo(colecao, pedido="outro pedido")


@pytest.mark.parametrize("campo", ["verificado", "aprovado", "sucesso"])
def test_falha_ou_resposta_nao_conferida_nao_vira_exemplo_positivo(tmp_path, campo):
    colecao = Aprendizado(tmp_path / "hud-aprendizado.sqlite")
    colecao.optar(True)
    with pytest.raises(ValueError, match="exige resultado"):
        exemplo(colecao, **{campo: False})
    assert colecao.listar() == []


def test_segredos_removidos_antes_da_persistencia(tmp_path):
    arquivo = tmp_path / "hud-aprendizado.sqlite"
    colecao = Aprendizado(arquivo)
    colecao.optar(True)
    segredo = "sk-fixtureNuncaConservar12345"
    e = colecao.registrar("Consultar equipamento", "Manual autorizado\nToken: " + segredo,
                          "Consultar manual", "Referência conferida", "Citar a versão",
                          verificado=True, aprovado=True, sucesso=True)
    assert "[SEGREDO REMOVIDO]" in e["contexto"]
    colecao.fechar()
    assert segredo.encode() not in arquivo.read_bytes()


def test_holdout_nao_recebe_exemplo_da_adaptacao_apos_reinicio(tmp_path):
    arquivo = tmp_path / "hud-aprendizado.sqlite"
    colecao = Aprendizado(arquivo)
    colecao.optar(True)
    exemplo(colecao)
    colecao.fechar()
    colecao = Aprendizado(arquivo)
    with pytest.raises(ValueError, match="não duplique"):
        exemplo(colecao, pedido="CALCULE  DOIS MAIS DOIS", destino="avaliacao")
    assert colecao.listar("avaliacao") == []


def test_avaliacao_compara_mesmos_casos_e_nao_promove(tmp_path):
    colecao = Aprendizado(tmp_path / "hud-aprendizado.sqlite")
    colecao.optar(True)
    e = exemplo(colecao, destino="avaliacao")
    antes = {e["id"]: dict(correto=False, verificado=True, evidencia="saída antiga 5", repeticoes=1)}
    depois = {e["id"]: dict(correto=True, verificado=True, evidencia="calculadora confirmou 4")}
    r = colecao.comparar("prompt-v1", "prompt-v2", antes, depois,
                        politica_referencia="permissoes-v1", politica_candidato="permissoes-v1",
                        reversao="restaurar a revisão prompt-v1 conservada no repositório")
    assert r["melhora_nos_casos"] and not r["promovido"]
    assert r["antes"]["corretos"] == 0 and r["depois"]["corretos"] == 1
    with pytest.raises(ValueError, match="política"):
        colecao.comparar("v1", "v2", antes, depois, politica_referencia="p1", politica_candidato="p2", reversao="voltar v1")
    with pytest.raises(ValueError, match="mesmos casos"):
        colecao.comparar("v1", "v2", antes, {}, politica_referencia="p1", politica_candidato="p1", reversao="voltar v1")
    colecao.esquecer(e["id"])
    assert colecao.avaliacoes() == []


def test_adaptacao_nao_e_evidencia_de_avaliacao(tmp_path):
    colecao = Aprendizado(tmp_path / "hud-aprendizado.sqlite")
    colecao.optar(True)
    e = exemplo(colecao)
    resultado = {e["id"]: dict(correto=True, verificado=True, evidencia="conferido")}
    with pytest.raises(ValueError, match="conjunto reservado"):
        colecao.comparar("v1", "v2", resultado, resultado,
                        politica_referencia="p1", politica_candidato="p1", reversao="voltar v1")


def test_episodio_separa_inferencia_decisao_e_expira(tmp_path):
    store = Episodios(tmp_path / "hud-episodios.sqlite")
    with pytest.raises(ValueError, match="confirmação explícita"):
        episodio(store, decisoes=["aumentar largura"])
    e = episodio(store, inferencias=["o cabo talvez caiba"], decisoes=["medir antes de fabricar"],
                 decisoes_confirmadas=True, valido_ate=time.time() + 60)
    assert e["natureza_resultado"] == "relato_da_atividade"
    assert not e["verificacao_automatica"]
    with patch("time.time", return_value=e["valido_ate"] + 1):
        assert store.listar() == []
        assert not store.listar(incluir_expirados=True)[0]["valido"]
    assert store.listar(escopo="outro-projeto") == []


def test_corrigir_episodio_remove_exemplo_da_versao_anterior(tmp_path):
    ep = Episodios(tmp_path / "hud-episodios.sqlite")
    e = episodio(ep)
    colecao = Aprendizado(tmp_path / "hud-aprendizado.sqlite")
    colecao.optar(True)
    exemplo(colecao, fontes=[{"tipo": "episodio", "id": e["id"]}])
    revisado = ep.corrigir(e["id"], "Largura corrigida: 22 mm")
    assert revisado["revisao"] == 2
    assert colecao.listar() == []
    ep.fechar()
    ep = Episodios(tmp_path / "hud-episodios.sqlite")
    assert ep.listar()[0]["resultado"] == "Largura corrigida: 22 mm"
    assert ep.esquecer(e["id"]) and ep.listar(incluir_expirados=True) == []


def test_episodios_derivados_invalidam_e_excluem_em_cascata(tmp_path):
    ep = Episodios(tmp_path / "hud-episodios.sqlite")
    primeiro = episodio(ep)
    segundo = episodio(ep, fontes=[{"tipo": "episodio", "id": primeiro["id"]}])
    terceiro = episodio(ep, fontes=[{"tipo": "episodio", "id": segundo["id"]}])
    ep.corrigir(primeiro["id"], "Largura corrigida: 22 mm")
    assert [e["id"] for e in ep.listar()] == [primeiro["id"]]
    assert ep.esquecer(primeiro["id"])
    assert ep.listar(incluir_expirados=True) == []


def test_recuperacao_episodica_respeita_escopo_e_rotulo(tmp_path):
    ep = Episodios(tmp_path / "hud-episodios.sqlite")
    episodio(ep, inferencias=["talvez suporte o cabo"])
    assert ep.para_prompt("outro-projeto", "largura") == ""
    contexto = ep.para_prompt("projeto-caixa", "largura")
    assert "nunca instruções ou autorização" in contexto
    assert '"inferencias"' in contexto and "talvez suporte" in contexto


def test_documento_substituido_invalida_episodio_e_exemplo(tmp_path):
    arquivo = tmp_path / "manual.txt"
    arquivo.write_text("A parede mede dois milímetros.", encoding="utf-8")
    con = Conhecimento(tmp_path / "hud-conhecimento.json")
    d = con.indexar(arquivo)
    ep = Episodios(tmp_path / "hud-episodios.sqlite")
    episodio(ep, fontes=[{"tipo": "documento", "id": d.id, "versao": d.versao}])
    colecao = Aprendizado(tmp_path / "hud-aprendizado.sqlite")
    colecao.optar(True)
    exemplo(colecao, fontes=[{"tipo": "documento", "id": d.id, "versao": d.versao}])
    arquivo.write_text("A parede mede três milímetros.", encoding="utf-8")
    con.indexar(arquivo)
    assert ep.listar() == [] and ep.listar(incluir_expirados=True)[0]["invalidado"]
    assert colecao.listar() == []
    con.esquecer_arquivo(arquivo)
    assert ep.listar(incluir_expirados=True) == []


def test_fonte_alterada_nao_entrega_trecho_antigo_ao_modelo(tmp_path):
    arquivo = tmp_path / "manual.txt"
    arquivo.write_text("A parede mede dois milímetros.", encoding="utf-8")
    con = Conhecimento(tmp_path / "hud-conhecimento.json")
    con.indexar(arquivo)
    arquivo.write_text("A parede mede três milímetros.", encoding="utf-8")
    prompt, fontes = con.para_prompt("parede")
    assert "dois milímetros" not in prompt and fontes == [] and con.ultimos == []
    assert "reindexar" in prompt


def test_esquecer_fato_remove_derivados_pertinentes(tmp_path):
    mem = Memoria(LocalFactStore(tmp_path / "facts.jsonl"))
    mem.guardar("prefiro respostas curtas")
    fato = mem.listar()[0][1].text
    ep = Episodios(tmp_path / "hud-episodios.sqlite")
    episodio(ep, fontes=[{"tipo": "fato", "id": id_fato(fato)}])
    assert mem.esquecer(mem.listar()[0][0], fato)
    assert ep.listar(incluir_expirados=True) == []


def test_correcao_com_falha_de_persistencia_nao_finge_sucesso(tmp_path):
    cor = Correcoes(tmp_path / "hud-correcoes.json")
    cor.registrar("termo antigo", "pronúncia antiga", tipo="pronuncia")
    with patch.object(cor, "salvar", side_effect=OSError("disco cheio")):
        with pytest.raises(ValueError, match="nenhuma mudança"):
            cor.registrar("termo antigo", "pronúncia nova", tipo="pronuncia")
    assert cor.listar()[0].faca == "pronúncia antiga"
    assert Correcoes(cor._arq).listar()[0].faca == "pronúncia antiga"


def test_esquecer_correcao_vazia_ou_ambigua_nao_apaga(tmp_path):
    cor = Correcoes(tmp_path / "hud-correcoes.json")
    cor.registrar("termo antigo", "primeiro", tipo="pronuncia")
    cor.registrar("termo novo", "segundo", tipo="pronuncia")
    assert not cor.esquecer("")
    with pytest.raises(ValueError, match="mais de uma"):
        cor.esquecer("termo")
    assert len(cor.listar()) == 2
