"""Laço limitado de ferramentas: validar, executar, devolver evidências ao modelo."""
from __future__ import annotations

import json
import copy
import time
import uuid


def validar_argumentos(nome: str, args, ferramentas: list[dict]) -> str | None:
    spec = next((t["function"]["parameters"] for t in ferramentas if t["function"]["name"] == nome), None)
    if spec is None:
        return "ferramenta desconhecida"
    if not isinstance(args, dict):
        return "argumentos devem ser um objeto"
    props = spec.get("properties", {})
    if set(args) - set(props):
        return "parâmetros desconhecidos"
    if any(k not in args for k in spec.get("required", [])):
        return "parâmetro obrigatório ausente"
    tipos = {"string": str, "integer": int, "boolean": bool, "number": (int, float)}
    for k, value in args.items():
        p = props[k]
        tipo = tipos.get(p.get("type"))
        if tipo and (not isinstance(value, tipo) or (p.get("type") in {"integer", "number"} and isinstance(value, bool))):
            return f"tipo inválido em {k}"
        if isinstance(value, str) and (not value.strip() or len(value) > 8000):
            return f"texto vazio ou excessivo em {k}"
        if "enum" in p and value not in p["enum"]:
            return f"valor não permitido em {k}"
        if "minimum" in p and value < p["minimum"] or "maximum" in p and value > p["maximum"]:
            return f"valor fora do limite em {k}"
    if nome == "volume" and len(args) != 1:
        return "informe somente percentual, mudo ou ajuste"
    if nome == "criar_lembrete" and bool(args.get("em_minutos")) == bool(args.get("horario")):
        return "informe em_minutos OU horario"
    if nome == "executar_comando":
        from .fala_variantes import pedido_composto
        if pedido_composto(args.get("frase", "")):
            return "use uma única ação por chamada; o pedido composto não pode ser cortado pelo primeiro comando"
    return None


def executar_plano(primeira: dict, pedido: dict, consultar, executar, cancelado,
                   registrar, *, max_passos: int = 5, prazo_s: float = 180,
                   projetos=None, objetivo: str = "", sessao_id: str = "", pedido_id: str = "",
                   projeto: str = "", publicar=None, tarefa_id: str | None = None,
                   catalogo_atual: list[dict] | None = None) -> tuple[str | None, list[dict]]:
    """Returns actual results even when the final model summary fails.

    The budget includes invalid calls. A repeated call cannot repeat a write.
    No fallback model may replay a partially executed plan.
    """
    from .protocolos import classificar_retorno
    from .projetos import resumo_falado
    if not 1 <= max_passos <= 5:
        raise ValueError("o orçamento permitido é de uma a cinco chamadas")
    inicio = time.monotonic()
    mensagens = list(pedido["messages"])
    ferramentas = pedido.get("tools", [])
    tarefa = None
    if projetos is not None:
        if tarefa_id:
            tarefa = projetos.obter(tarefa_id)
            if tarefa is None or tarefa.origem != "modelo":
                raise ValueError("tarefa de ferramentas inexistente")
        else:
            existente = projetos.por_pedido(sessao_id, pedido_id)
            if existente is not None:
                if objetivo and existente.objetivo != objetivo.strip():
                    raise ValueError("pedido_id reutilizado para outro objetivo")
                return "Pedido já registrado. " + resumo_falado(existente), []
            objetivo = objetivo or next((m.get("content", "") for m in reversed(mensagens)
                                         if m.get("role") == "user"), "Pedido de ferramentas")
            pai = projetos.ativa()
            if pai and ((projeto and pai.projeto != projeto)
                        or (pai.sessao_id and sessao_id and pai.sessao_id != sessao_id)):
                pai = None
            tarefa = projetos.criar(objetivo, projeto=projeto, origem="modelo", sessao_id=sessao_id,
                                     pedido_id=pedido_id, conclusao_quando="o pedido e os resultados forem conferidos",
                                     restricoes=(list(pai.restricoes) if pai else []) +
                                     ["No máximo cinco chamadas; somente ferramentas permitidas; "
                                      "efeito incerto exige conferência antes de repetir."],
                                     recursos=list(pai.recursos) if pai else [],
                                     depende_de=list(pai.depende_de) if pai else [], tarefa_pai=pai.id if pai else "")
            tarefa.limite_acoes = max_passos
            tarefa.ferramentas_modelo = copy.deepcopy(ferramentas)
            projetos.salvar()
        max_passos = min(max_passos, tarefa.limite_acoes)
    msg, passos, vistos, resultados = primeira, tarefa.chamadas_usadas if tarefa else 0, {}, []
    if tarefa and tarefa_id:
        resultados.extend(tarefa.resultados)
    if tarefa:
        vistos = {e.assinatura: e.resultado for e in tarefa.etapas if e.pronta}
    rastros = []
    encerrado = ""

    def publicar_estado():
        if tarefa and publicar and projetos.ativa() is tarefa:
            publicar(tarefa)

    def pausar(motivo):
        if tarefa and tarefa.estado not in ("cancelada", "concluida"):
            projetos.mudar_estado(tarefa.id, "pausada", motivo)
            publicar_estado()

    publicar_estado()
    while msg.get("tool_calls"):
        if cancelado.is_set():
            pausar("Pedido interrompido; etapas e resultados preservados.")
            return None, rastros
        chamadas = msg["tool_calls"]
        if not isinstance(chamadas, list):
            resultados.append("O modelo retornou chamadas inválidas; interrompi o plano.")
            break
        chamadas = chamadas[:max(0, max_passos - passos)]
        if not chamadas:
            encerrado = "Atingi o limite de cinco chamadas deste pedido; confira os resultados antes de continuar."
            break
        if time.monotonic() - inicio > prazo_s:
            encerrado = "O prazo deste pedido acabou; preservei os resultados anteriores."
            break
        assistant = {"role": "assistant", "content": msg.get("content") or "", "tool_calls": []}
        ids_do_lote = set()
        for chamada in chamadas:
            if not isinstance(chamada, dict):
                encerrado = "O modelo retornou uma chamada inválida; interrompi o plano."
                continue
            f = chamada.get("function") or {}
            if not isinstance(f, dict):
                encerrado = "O modelo retornou argumentos de função inválidos; interrompi o plano."
                continue
            ident = str(chamada.get("id") or uuid.uuid4().hex)
            if ident in ids_do_lote:
                encerrado = "O modelo repetiu um identificador de chamada; interrompi o lote ambíguo."
                assistant["tool_calls"] = []
                break
            ids_do_lote.add(ident)
            assistant["tool_calls"].append({"id": ident,
                "type": "function", "function": {"name": str(f.get("name") or ""),
                "arguments": f.get("arguments") if isinstance(f.get("arguments"), str) else json.dumps(f.get("arguments") or {})}})
        if not assistant["tool_calls"]:
            resultados.append(encerrado or "O modelo retornou chamadas inválidas; interrompi o plano.")
            break
        mensagens.append(assistant)
        rastros.append(assistant)
        preparados, indices = {}, {}
        for chamada in assistant["tool_calls"]:
            f = chamada["function"]
            try:
                args = json.loads(f["arguments"])
                erro = validar_argumentos(f["name"], args, ferramentas)
                if not erro and catalogo_atual is not None:
                    erro = validar_argumentos(f["name"], args, catalogo_atual)
            except (ValueError, TypeError):
                args, erro = {}, "JSON inválido"
            assinatura = json.dumps([f["name"], args], sort_keys=True, ensure_ascii=False)
            preparados[chamada["id"]] = args, erro, assinatura
        if tarefa:
            lote = []
            for chamada in assistant["tool_calls"]:
                args, erro, assinatura = preparados[chamada["id"]]
                if not erro:
                    nome = chamada["function"]["name"]
                    recursos = [f"{k}:{v}" for k, v in args.items()
                                if k in ("arquivo", "caminho", "recurso", "peca", "url") and isinstance(v, str)]
                    lote.append({"ferramenta": nome, "argumentos": args, "assinatura": assinatura,
                                 "chamada_id": chamada["id"], "descricao": str(args.get("frase") or nome),
                                 "recursos": recursos})
            try:
                indices = projetos.registrar_plano_modelo(tarefa.id, lote)
            except ValueError as exc:
                encerrado = str(exc)
                break
            publicar_estado()
        for chamada in assistant["tool_calls"]:
            if cancelado.is_set():
                pausar("Pedido interrompido; etapas e resultados preservados.")
                return None, rastros
            if time.monotonic() - inicio >= prazo_s:
                encerrado = "O prazo deste pedido acabou; preservei os resultados anteriores."
                break
            f = chamada["function"]
            args, erro, assinatura = preparados[chamada["id"]]
            if tarefa and not projetos.registrar_tentativa_modelo(tarefa.id, chamada["id"], erro=erro or ""):
                encerrado = "A tarefa está pausada, cancelada ou atingiu seu orçamento; nenhuma nova ação foi iniciada."
                break
            passos += 1
            indice, acao = indices.get(chamada["id"]), None
            falhou = incerto = False
            if erro:
                resultado = "Não executei: " + erro + "."
            elif assinatura in vistos:
                resultado = "Chamada repetida; resultado anterior: " + vistos[assinatura]
            else:
                if tarefa:
                    acao = projetos.iniciar_etapa(tarefa.id, indice)
                    if acao is None:
                        encerrado = (tarefa.motivo or "A etapa depende de conferência ou de outra etapa pendente.")
                        break
                try:
                    resultado, falhou, incerto = classificar_retorno(executar(f["name"], args))
                except Exception as exc:
                    resultado = f"A ferramenta falhou ({type(exc).__name__}); confira o estado antes de repetir."
                    falhou = incerto = True
                if tarefa:
                    projetos.finalizar_execucao(tarefa.id, indice, acao, resultado, erro=falhou, incerto=incerto)
                    publicar_estado()
                vistos[assinatura] = resultado
            registrar("comando", f"ferramenta {passos}/{max_passos}: {f['name']}")
            resultados.append(resultado)
            evento = {"role": "tool", "tool_call_id": chamada["id"], "content": resultado}
            mensagens.append(evento)
            rastros.append(evento)
            if falhou or incerto:
                encerrado = "O plano parou nesta etapa; confira o resultado antes de retomar."
                break
        if cancelado.is_set():
            pausar("Pedido interrompido; etapas e resultados preservados.")
            return None, rastros
        if tarefa and tarefa.estado in ("cancelada", "pausada"):
            return None, rastros
        if encerrado or passos >= max_passos or time.monotonic() - inicio >= prazo_s:
            break
        if consultar is None:
            encerrado = "As etapas gravadas foram processadas; a revisão do pedido pelo modelo ficou pendente."
            break
        try:
            if tarefa:
                projetos.mudar_estado(tarefa.id, "em_execucao", "Resultados registrados; aguardando revisão do plano.")
                publicar_estado()
            proximo = dict(pedido, messages=mensagens, stream=False)
            dados = consultar(proximo)
            msg = (dados.get("choices") or [{}])[0].get("message") or {}
            if not isinstance(msg, dict):
                encerrado = "O modelo devolveu uma resposta inválida; preservei os resultados das ferramentas."
                break
        except Exception:
            encerrado = "As ferramentas responderam, mas não consegui concluir a revisão pelo modelo."
            break
    if passos >= max_passos and msg.get("tool_calls"):
        resultados.append("Atingi o limite de cinco chamadas deste pedido; confira os resultados antes de continuar.")
    if encerrado:
        resultados.append(encerrado)
    if tarefa and tarefa.estado not in ("cancelada", "pausada", "aguardando_informacao", "falha"):
        tarefa.plano_encerrado = bool(tarefa.etapas) and not tarefa.pendentes() and not encerrado and not msg.get("tool_calls")
        estado = "executada_sem_verificacao" if tarefa.plano_encerrado and not tarefa.pendentes() else "parcialmente_concluida"
        if not tarefa.prontas():
            estado = "aguardando_informacao"
            encerrado = encerrado or "Nenhuma etapa executada; revise o plano e os argumentos."
        projetos.mudar_estado(tarefa.id, estado, encerrado)
        publicar_estado()
    # Evidence is authoritative; generated claims never replace tool results.
    return " ".join(resultados) or None, rastros


def retomar_plano(projetos, tarefa_id: str, ferramentas: list[dict], executar, cancelado,
                  registrar, *, consultar=None, pedido: dict | None = None, publicar=None,
                  prazo_s: float = 180) -> tuple[str | None, list[dict]]:
    """Revalida o plano persistido; etapa concluída ou incerta nunca é repetida.

    Sem consultar, executa somente as etapas gravadas. Com consultar/pedido,
    reconstrói o histórico de resultados e permite revisão dentro do orçamento original.
    """
    from .projetos import resumo_falado
    t = projetos.obter(tarefa_id)
    if t is None or t.origem != "modelo":
        raise ValueError("tarefa de ferramentas inexistente")
    if t.estado in ("cancelada", "concluida") or (t.plano_encerrado and not t.pendentes()):
        return resumo_falado(t), []
    incerta = next((e for e in t.etapas if e.estado in ("resultado_incerto", "em_execucao", "falha")), None)
    if incerta:
        projetos.mudar_estado(t.id, "aguardando_informacao", "Confira a etapa antes de retomar: " + incerta.descricao)
        return resumo_falado(t), []
    if cancelado.is_set():
        return None, []
    if t.estado == "pausada":
        projetos.mudar_estado(t.id, "planejada", "Retomada explícita das etapas pendentes.")
    mensagens = list((pedido or {}).get("messages", []))
    if not mensagens:
        mensagens = [{"role": "user", "content": t.objetivo}]
    for e in t.etapas:
        if e.pronta:
            chamada = {"id": e.chamada_id, "type": "function", "function": {
                "name": e.ferramenta, "arguments": json.dumps(e.argumentos, ensure_ascii=False)}}
            mensagens += [{"role": "assistant", "content": "", "tool_calls": [chamada]},
                          {"role": "tool", "tool_call_id": e.chamada_id, "content": e.resultado or ""}]
    nomes_atuais = {f["function"]["name"] for f in ferramentas}
    # Retomar não amplia o catálogo autorizado na solicitação original.
    anteriores = t.ferramentas_modelo or [f for f in ferramentas
                                         if f["function"]["name"] in {e.ferramenta for e in t.etapas}]
    permitidas = [f for f in anteriores if f["function"]["name"] in nomes_atuais]
    proximo = dict(pedido or {}, tools=permitidas, messages=mensagens, stream=False)
    pendentes = [{"id": e.chamada_id, "type": "function", "function": {
        "name": e.ferramenta, "arguments": json.dumps(e.argumentos, ensure_ascii=False)}}
        for e in t.etapas if not e.pronta]
    if pendentes:
        primeira = {"content": "", "tool_calls": pendentes}
    elif consultar is not None:
        try:
            primeira = (consultar(proximo).get("choices") or [{}])[0].get("message") or {}
            if not isinstance(primeira, dict):
                raise ValueError("resposta inválida do modelo")
        except Exception:
            projetos.mudar_estado(t.id, "parcialmente_concluida", "A revisão do pedido pelo modelo permanece pendente.")
            return resumo_falado(t), []
    else:
        projetos.mudar_estado(t.id, "parcialmente_concluida", "Não há etapa gravada pendente, mas falta a revisão do pedido pelo modelo.")
        return resumo_falado(t), []
    return executar_plano(primeira, proximo, consultar, executar, cancelado, registrar,
                          projetos=projetos, tarefa_id=t.id, max_passos=t.limite_acoes,
                          publicar=publicar, prazo_s=prazo_s, catalogo_atual=ferramentas)
