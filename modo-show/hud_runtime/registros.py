"""Controles locais explícitos de memória revisável e requisitos de tarefas.

São chamados pelas rotas autenticadas; não fazem parte das ferramentas do modelo.
Não extraem exemplos do histórico nem treinam/promovem modelos.
"""
from __future__ import annotations

ROTAS = {"/api/memoria/episodios", "/api/aprendizado", "/api/projetos/requisitos"}


def _campos(corpo, permitidos):
    extras = corpo.keys() - set(permitidos) - {"acao"}
    if extras:
        raise ValueError("campos desconhecidos: " + ", ".join(sorted(extras)))


def executar(comandos, rota, corpo):
    from .aprendizado import Aprendizado
    from .memoria import Episodios
    acao = corpo.get("acao", "estado" if rota == "/api/aprendizado" else "listar")
    if rota == "/api/projetos/requisitos":
        _campos(corpo, {"id", "conclusao_quando", "restricoes", "recursos", "depende_de"})
        p = comandos._projetos()
        ident = corpo.get("id")
        if not isinstance(ident, str) or p.obter(ident) is None:
            raise ValueError("informe uma tarefa existente")
        dados = {k: v for k, v in corpo.items() if k not in {"id", "acao"}}
        for k in ("restricoes", "recursos", "depende_de"):
            if k in dados and (not isinstance(dados[k], list) or len(dados[k]) > 40
                              or any(not isinstance(x, str) or len(x) > 500 for x in dados[k])):
                raise ValueError(f"{k} exige até quarenta textos de até 500 caracteres")
        if "conclusao_quando" in dados and (not isinstance(dados["conclusao_quando"], str)
                                           or len(dados["conclusao_quando"]) > 2000):
            raise ValueError("condição de conclusão exige texto com até 2000 caracteres")
        t = p.definir_requisitos(ident, **dados)
        comandos._projeto_na_tela(t)
        return {"ok": True, "tarefa": p.inspecionar(ident)}

    if rota == "/api/memoria/episodios":
        servico = comandos._servico("episodios", Episodios)
        if acao == "listar":
            _campos(corpo, {"escopo", "incluir_expirados"})
            if corpo.get("escopo") is not None and not isinstance(corpo["escopo"], str):
                raise ValueError("escopo precisa ser texto")
            return {"ok": True, "episodios": servico.listar(corpo.get("escopo"), corpo.get("incluir_expirados") is True)}
        if acao == "registrar":
            _campos(corpo, {"atividade", "resultado", "escopo", "origem", "fontes", "inferencias", "decisoes", "decisoes_confirmadas", "valido_ate"})
            # O endpoint é uma declaração do usuário, não uma medição de ferramenta.
            dado = servico.registrar(corpo.get("atividade"), corpo.get("resultado"), origem="usuario",
                    escopo=corpo.get("escopo") or comandos._projetos().projeto or "pessoal",
                    **{k: corpo[k] for k in ("fontes", "inferencias", "decisoes", "decisoes_confirmadas", "valido_ate") if k in corpo})
            return {"ok": True, "episodio": dado}
        if acao == "corrigir":
            _campos(corpo, {"id", "resultado", "inferencias", "decisoes", "decisoes_confirmadas"})
            dado = servico.corrigir(corpo.get("id"), corpo.get("resultado"),
                    **{k: corpo[k] for k in ("inferencias", "decisoes", "decisoes_confirmadas") if k in corpo})
            return {"ok": True, "episodio": dado}
        if acao == "esquecer":
            _campos(corpo, {"id"})
            return {"ok": True, "apagado": servico.esquecer(corpo.get("id"))}
        raise ValueError("ação de memória desconhecida")

    if rota != "/api/aprendizado":
        raise ValueError("rota de registros desconhecida")
    servico = comandos._servico("aprendizado", Aprendizado)
    if acao == "estado":
        _campos(corpo, set())
        return {"ok": True, "estado": servico.estado()}
    if acao == "optar":
        _campos(corpo, {"ativo"})
        return {"ok": True, "estado": servico.optar(corpo.get("ativo"))}
    if acao == "listar":
        _campos(corpo, {"destino"})
        if corpo.get("destino") not in (None, "adaptacao", "avaliacao"):
            raise ValueError("destino inválido")
        return {"ok": True, "estado": servico.estado(), "exemplos": servico.listar(corpo.get("destino")),
                "avaliacoes": servico.avaliacoes()}
    if acao == "registrar":
        campos = {"pedido", "contexto", "acao_executada", "resultado", "correcao", "verificado", "aprovado", "sucesso", "destino", "fontes"}
        _campos(corpo, campos)
        dado = servico.registrar(corpo.get("pedido"), corpo.get("contexto"), corpo.get("acao_executada"),
                corpo.get("resultado"), corpo.get("correcao"), verificado=corpo.get("verificado"),
                aprovado=corpo.get("aprovado"), sucesso=corpo.get("sucesso"),
                destino=corpo.get("destino", "adaptacao"), fontes=corpo.get("fontes", []))
        return {"ok": True, "exemplo": dado, "estado": servico.estado()}
    if acao == "esquecer":
        _campos(corpo, {"id"})
        return {"ok": True, "apagado": servico.esquecer(corpo.get("id")), "estado": servico.estado()}
    if acao == "comparar":
        campos = {"referencia", "candidato", "resultados_referencia", "resultados_candidato", "politica_referencia", "politica_candidato", "reversao"}
        _campos(corpo, campos)
        return {"ok": True, "comparacao": servico.comparar(**{k: corpo.get(k) for k in campos})}
    raise ValueError("ação de aprendizado desconhecida")
