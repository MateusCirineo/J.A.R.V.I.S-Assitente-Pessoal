"""Diagnóstico contextual baseado exclusivamente nas evidências locais existentes.

Não inicia hardware, rede, contas nem modelos. Disponibilidade de um arquivo de
modelo não é tratada como uma inferência bem-sucedida.
"""

from __future__ import annotations

import math
import time
from typing import Any


def _numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _situacao(dado: dict, agora: float, *, em: float | None = None, validade: float = 30) -> str:
    status = dado.get("status")
    if status not in ("ok", "medido", "estimado"):
        return "aguardando_configuracao" if status == "nao_configurado" else "indisponivel"
    quando = dado.get("em", em)
    if not _numero(quando) or quando > agora + 5:
        return "nao_verificado"
    if agora - quando > validade:
        return "desatualizado"
    return "estimado" if status == "estimado" else "disponivel"


def relatorio_capacidades(rt: Any, agora: float | None = None) -> dict[str, Any]:
    agora = time.time() if agora is None else agora
    tel = getattr(rt.estado, "telemetria", None) or {}
    estado = rt.estado.instantaneo()
    prefs = rt.prefs.ler()
    componentes: list[dict[str, Any]] = []

    def item(ident: str, titulo: str, situacao: str, detalhe: str, fonte: str,
             efeitos: list[str], quando=None, dependencias=None, **extra):
        componentes.append({"id": ident, "titulo": titulo, "estado": situacao, "detalhe": detalhe,
                            "fonte": fonte, "em": quando, "efeitos": efeitos,
                            "dependencias": dependencias or [], **extra})

    for chave, titulo, efeitos in (
        ("servidor", "Servidor OpenJarvis", ["chat com modelo", "ferramentas do servidor"]),
        ("ollama", "Ollama", ["inferência local", "análise visual por modelo"]),
    ):
        d = tel.get(chave) or {}
        situacao = _situacao(d, agora, em=tel.get("em"))
        detalhe = "Endpoint respondeu à última verificação." if situacao == "disponivel" else {
            "desatualizado": "Última resposta antiga; a disponibilidade atual não foi confirmada.",
            "nao_verificado": "Falta o horário da verificação; disponibilidade atual não confirmada.",
        }.get(situacao, "Endpoint não respondeu ou ainda não foi verificado.")
        item(chave, titulo, situacao, detalhe, "verificação HTTP local", efeitos, d.get("em", tel.get("em")))

    modelo = prefs.get("modelo_voz")
    instalados = {m.get("nome") for m in (tel.get("ollama") or {}).get("instalados", []) if isinstance(m, dict)}
    item("modelo_voz", "Modelo da conversa", "instalado" if modelo in instalados else "nao_verificado",
         f"{modelo or 'modelo não selecionado'}; presença em disco não comprova resposta por inferência.",
         "inventário informado pelo Ollama", ["conversa local", "seleção de ferramentas"],
         tel.get("em"), ["servidor", "ollama"])

    for chave, titulo, efeitos in (("transcricao", "Transcrição", ["pedidos por voz", "cadastro da voz"]),
                                  ("sintese", "Síntese de voz", ["respostas faladas"])):
        pronta = bool(getattr(getattr(rt, chave, None), "pronta", False))
        item(chave, titulo, "carregado" if pronta else "indisponivel",
             "Componente carregado; não foi gerado áudio nesta verificação." if pronta else "Componente ainda não carregado.",
             "estado do componente local", efeitos, agora)

    mic = estado.get("microfone") or {}
    mic_estado = mic.get("estado")
    ativo = bool(getattr(getattr(rt, "microfone", None), "ativo", False))
    situacao = ("ativo" if ativo and mic_estado in ("ouvindo", "captando", "pausado") else
                "indisponivel" if mic_estado in ("erro", "bloqueado") else "em_espera")
    item("microfone", "Microfone", situacao,
         f"Estado informado: {mic_estado or 'sem evidência de captura'}. Ativação não é prova de fala captada.",
         "captura local de áudio", ["pedidos por voz", "cadastro da voz"], agora, ["transcricao"])

    cam = getattr(rt, "camera", None)
    ligado = bool(getattr(cam, "ativa", False))
    item("camera", "Câmera", "aguardando_imagem_atual" if ligado else "em_espera",
         "Ativada; cada tarefa deve conferir quadros novos antes de descrever ou cadastrar." if ligado else
         "Desligada; tarefas visuais aguardam ativação autorizada. A conversa textual continua disponível.",
         "estado da câmera local", ["visão ao vivo", "cadastro do rosto", "gestos"], agora)

    for chave, titulo, efeitos in (("agenda", "Agenda", ["briefing de compromissos", "preparação de reunião"]),
                                  ("email", "E-mails", ["resumo de mensagens autorizadas"]),
                                  ("noticias", "Notícias", ["briefing de notícias", "monitoramento de temas"])):
        d = tel.get(chave) or {}
        situacao = _situacao(d, agora, validade=900)
        detalhe = {
            "disponivel": "Leitura disponível na última consulta; nenhuma permissão de envio é conferida.",
            "desatualizado": "A última consulta está antiga; atualize antes de tratar o conteúdo como atual.",
            "aguardando_configuracao": "Integração não conectada. As demais fontes podem continuar.",
            "nao_verificado": "Conteúdo sem horário de consulta; atualidade não confirmada.",
        }.get(situacao, "Fonte indisponível nesta consulta; as demais fontes podem continuar.")
        item(chave, titulo, situacao, detalhe, str(d.get("fonte") or "consulta da integração"), efeitos, d.get("em"))

    sistema = tel.get("sistema") or {}
    for chave, titulo, campo, unidade, efeitos in (
        ("cpu", "Processador", "uso_pct", "%", ["desempenho do processamento"]),
        ("memoria", "Memória", "uso_pct", "%", ["carregamento de modelos"]),
        ("disco", "Disco", "livre_gb", "GB", ["gravação de arquivos", "persistência de tarefas"]),
        ("temperatura", "Temperatura", "celsius", "°C", ["desempenho do processamento"]),
        ("bateria", "Bateria", "percentual", "%", ["disponibilidade elétrica"]),
        ("energia_cpu", "Potência da CPU", "potencia_w", "W", ["estimativas de consumo"]),
    ):
        d = sistema.get(chave) or {}
        situacao = _situacao(d, agora, em=tel.get("em"))
        valor = d.get(campo)
        if not _numero(valor):
            valor = None
            if situacao in ("disponivel", "estimado"):
                situacao = "indisponivel"
        alerta = False
        if situacao == "disponivel" and valor is not None:
            alerta = ((chave == "cpu" and valor >= 85) or (chave == "memoria" and valor >= 90)
                      or (chave == "temperatura" and valor >= 85) or (chave == "disco" and valor < 10)
                      or (chave == "bateria" and valor < 20 and not d.get("na_tomada")))
            if alerta:
                situacao = "atencao"
        item(chave, titulo, situacao,
             f"{valor:g} {unidade}; {'estimativa' if situacao == 'estimado' else 'última leitura'} da fonte indicada." if valor is not None else
             "Sem medição disponível. Ausência não significa zero.",
             str(d.get("fonte") or "sensor não informado"), efeitos, d.get("em", tel.get("em")),
             valor=valor, unidade=unidade)

    for chave, titulo, detalhe in (
        ("gps", "Posição GPS", "Nenhuma fonte GPS autorizada vinculada; não inferida da cidade do clima."),
        ("fisiologia", "Sinais fisiológicos", "Nenhum sensor apropriado vinculado; webcam não fornece diagnóstico médico."),
        ("chamadas", "Chamadas telefônicas", "Nenhuma integração de chamadas verificada; rascunhos não são envios."),
    ):
        item(chave, titulo, "indisponivel", detalhe, "nenhuma fonte verificada", [titulo.lower()])
    indisponiveis = [c["titulo"] for c in componentes if c["estado"] in ("indisponivel", "desatualizado", "nao_verificado", "atencao")]
    return {"em": agora, "componentes": componentes,
            "texto": "Diagnóstico das evidências disponíveis. " +
                     ("Atenção: " + ", ".join(indisponiveis) + ". " if indisponiveis else "") +
                     "O painel relaciona cada componente às tarefas afetadas; recursos em espera exigem ativação ou verificação."}
