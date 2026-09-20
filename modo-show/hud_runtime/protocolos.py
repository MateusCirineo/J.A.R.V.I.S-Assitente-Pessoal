"""Protocolos: sequencias de comandos com nome, como nos filmes ("Jarvis, protocolo
casa"). O Senhor cria por voz ("crie o protocolo trabalho: abra o VS Code, abra o
Gmail e me dê as notícias de tecnologia"), executa ("execute o protocolo trabalho")
e pode agendar ("todo dia às 8h execute o protocolo trabalho").

Cada passo precisa ser um comando que o Jarvis ja conhece (nada vai ao modelo) e
comandos destrutivos NUNCA entram num protocolo nem numa rotina agendada: apagar
memoria, quarentena, limpar listas, cancelar lembretes, descanso/desligar, gerar
programas. Guardados em ~/.openjarvis/hud-protocolos.json.
"""

from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
from pathlib import Path
from typing import Callable

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))

# o que NUNCA roda sozinho (protocolo ou horario marcado)
PROIBIDOS = {
    "peca_confirmar", "peca_apagar", "projeto_conferir_etapa", "projeto_concluir", "projeto_apagar",
    "id_rosto_cadastrar", "id_voz_cadastrar", "id_pessoa_cadastrar", "id_esquecer", "id_pessoa_esquecer",
    "id_cancelar", "memoria_guardar", "inv_cadastrar", "inv_definir", "inv_esquecer", "doc_esquecer",
    "correcao_ensinar", "correcao_aprovar", "correcao_apagar",
    "corrigir_apelido", "corrigir_esquecer", "corrigir_listar",
    "projeto_continuar", "projeto_etapa_nao_executada", "casa_confirmar",
    "confirmar_acao", "memoria_limpar", "memoria_limpar_confirmado", "memoria_esquecer", "memoria_corrigir",
    "quarentena_confirmar", "quarentena_mover", "quarentena_restaurar", "varredura", "lista_limpar",
    "lembretes_cancelar", "lembrete_remarcar", "rotina_descanso", "programa", "planilha", "despedida",
    "parar_fala", "protocolo_criar", "protocolo_apagar", "agendar", "notas_apagar",
    "protocolo_executar",  # orçamento não pode ser multiplicado por recursão
}
MAX_PASSOS = 10
PARAMETRO = re.compile(r"\{([a-z][a-z0-9_]{0,23})\}")


def comando_proibido(nome: str) -> bool:
    """Confirmação, consentimento e correções nunca nascem de um plano automático."""
    return (nome in PROIBIDOS or nome.startswith(("id_", "memoria_", "corrigir_", "correcao_"))
            or nome.endswith(("_confirmar", "_concluir", "_apagar", "_esquecer")))


def preencher(passos: list[str], valores: dict[str, str], *, previa: bool = False) -> list[str]:
    nomes = {n for passo in passos for n in PARAMETRO.findall(passo)}
    if any("{" in PARAMETRO.sub("", p) or "}" in PARAMETRO.sub("", p) for p in passos):
        raise ValueError("Use parâmetros simples como {tema} ou {valor}, sem expressões.")
    if previa:
        valores = {nome: "1" for nome in nomes}
    elif set(valores) != nomes:
        faltam = nomes - set(valores)
        extras = set(valores) - nomes
        raise ValueError(("Faltam parâmetros: " + ", ".join(sorted(faltam))) if faltam else
                         ("Parâmetros desconhecidos: " + ", ".join(sorted(extras))))
    for valor in valores.values():
        if not isinstance(valor, str) or not valor.strip() or len(valor) > 100 or not re.fullmatch(r"[\wÀ-ÿ .,/+%-]+", valor):
            raise ValueError("Valor de parâmetro inválido; não use comandos, separadores ou expressões.")
    return [PARAMETRO.sub(lambda m: valores[m[1]], passo) for passo in passos]


def ler_parametros(texto: str) -> dict[str, str]:
    if not texto:
        return {}
    valores = {}
    for parte in re.split(r"\s+e\s+(?=[a-z][a-z0-9_]*\s*=)|;\s*", texto, flags=re.I):
        m = re.fullmatch(r"\s*([a-z][a-z0-9_]{0,23})\s*=\s*(.+?)\s*", parte)
        if not m or m[1] in valores:
            raise ValueError("Use parâmetros distintos: com tema=tecnologia e valor=2,5.")
        valores[m[1]] = m[2]
    return valores


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split()).strip(" .!?,:;")


def nome_protocolo(texto: str) -> str:
    n = _norm(texto)
    return re.sub(r"^(?:o|do|da|de|chamado)\s+", "", n)[:40]


def separar_passos(texto: str) -> list[str]:
    """ "abra o VS Code, abra o Gmail e me dê as notícias" -> 3 passos.
    Separa por virgula, ";", " e depois ", " depois " e pelo " e " antes de um verbo."""
    partes = re.split(r"\s*(?:,|;|\be depois\b|\bdepois\b|\bem seguida\b|\be entao\b)\s*", texto.strip(" ."))
    passos: list[str] = []
    for p in partes:
        p = p.strip(" .")
        if not p:
            continue
        # " e " seguido de verbo no imperativo ("... e me dê", "... e abra", "... e toque") = outro passo
        sub = re.split(r"\s+e\s+(?=(?:me |o |a )?(?:abr|toqu|toc|lig|deslig|ativ|desativ|mostr|diga|d[eê]|leia|fal|"
                       r"coloqu|pon|aument|diminu|mud|execut|inici|abaix|suba|baix|paus|continu)\w*)", p, flags=re.I)
        passos.extend(s.strip(" .") for s in sub if s.strip(" ."))
    return passos


def classificar_retorno(retorno) -> tuple[str, bool, bool]:
    """Texto, erro conhecido, efeito incerto; nunca promove uma falha textual a sucesso."""
    if isinstance(retorno, dict):
        texto = str(retorno.get("texto", retorno.get("resultado", "")))
        if not texto.strip():
            return "Ferramenta sem resultado verificável; confira o efeito antes de repetir.", True, True
        return texto, retorno.get("ok") is False, bool(retorno.get("incerto"))
    if retorno is None or not str(retorno).strip():
        return "Ferramenta sem resultado verificável; confira o efeito antes de repetir.", True, True
    texto = str(retorno)
    erro = bool(re.match(r"(?:não (?:executei|consegui|foi possível|encontrei|achei|sei|há|entendi)|"
                         r"ainda não|falh|erro|indisponível|qual (?:dimensão|arquivo|projeto)|"
                         r"preciso (?:de|que)|a ferramenta falhou)", texto.strip(), re.I))
    return texto, erro, False


class Protocolos:
    def __init__(self, arquivo: Path = HOME / "hud-protocolos.json") -> None:
        self._arquivo = arquivo
        self._trava = threading.Lock()

    def _ler(self) -> dict[str, list[str]]:
        try:
            d = json.loads(self._arquivo.read_text(encoding="utf-8"))
            return {k: v for k, v in d.items() if isinstance(v, list)} if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _gravar(self, d: dict[str, list[str]]) -> None:
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._arquivo)

    def nomes(self) -> list[str]:
        return sorted(self._ler())

    def passos(self, nome: str) -> list[str] | None:
        return self._ler().get(nome_protocolo(nome))

    def salvar(self, nome: str, passos: list[str]) -> None:
        with self._trava:
            d = self._ler()
            d[nome_protocolo(nome)] = passos[:MAX_PASSOS]
            self._gravar(d)

    def apagar(self, nome: str) -> bool:
        with self._trava:
            d = self._ler()
            if d.pop(nome_protocolo(nome), None) is None:
                return False
            self._gravar(d)
            return True

    def executar(self, nome: str, projetos, interpretar, executar, *, tarefa_id: str | None = None,
                 sessao_id: str = "", pedido_id: str = "", cancelado=None, parametros: dict | None = None):
        """Executa no worker existente, persistindo cada passo antes/depois.

        Retomar usa o plano gravado na tarefa, não uma definição de protocolo
        que pode ter sido alterada. Textos são resultados sem verificação;
        ferramentas podem devolver {ok: bool, texto: str, incerto: bool}.
        """
        rotulo = nome_protocolo(nome)
        def interrompido():
            return bool(cancelado and (cancelado.is_set() if hasattr(cancelado, "is_set") else cancelado()))

        def pausar_interrompida():
            if tarefa.estado not in ("cancelada", "concluida"):
                projetos.mudar_estado(tarefa.id, "pausada",
                                      "Pedido interrompido; resultados preservados. Retome explicitamente.")
        if tarefa_id:
            tarefa = projetos.obter(tarefa_id)
            if tarefa is None or tarefa.origem != "protocolo":
                raise ValueError("tarefa de protocolo inexistente")
            if tarefa.estado in ("cancelada", "concluida"):
                return tarefa
        else:
            passos = self.passos(nome)
            if passos is None:
                raise ValueError(f"protocolo {rotulo} inexistente")
            originais = preencher(passos, {}, previa=True)
            passos = preencher(passos, parametros or {})
            for original, preenchido in zip(originais, passos):
                antes, depois = interpretar(original), interpretar(preenchido)
                if not antes or not depois or antes[0] != depois[0]:
                    raise ValueError("O parâmetro mudou o tipo de ação; revise o protocolo antes de executar.")
            passos, erro = validar_passos(passos, interpretar)
            if erro:
                raise ValueError(erro)
            tarefa = projetos.criar(f"protocolo {rotulo}", etapas=passos, origem="protocolo",
                                    conclusao_quando="os resultados forem conferidos",
                                    sessao_id=sessao_id, pedido_id=pedido_id)
        if tarefa.estado in ("cancelada", "concluida", "executada_sem_verificacao"):
            return tarefa
        if interrompido():
            pausar_interrompida()
            return tarefa
        if tarefa.estado == "pausada":
            projetos.mudar_estado(tarefa.id, "planejada", "Retomada solicitada pelo usuário.")
        for indice, etapa in enumerate(tarefa.etapas):
            if interrompido():
                pausar_interrompida()
                break
            if etapa.pronta:
                continue
            achado = interpretar(etapa.descricao)
            if achado is None or comando_proibido(achado[0]):
                projetos.mudar_estado(tarefa.id, "aguardando_informacao",
                                      f"O comando não está disponível ou permitido: {etapa.descricao}")
                break
            acao = projetos.iniciar_etapa(tarefa.id, indice)
            if acao is None:
                break
            try:
                retorno = executar(achado[0], achado[1], etapa.descricao)
                texto, erro, incerto = classificar_retorno(retorno)
            except Exception as exc:
                texto = f"Etapa interrompida ({type(exc).__name__}); confira o efeito antes de repetir."
                erro, incerto = True, True
            pode_continuar = projetos.finalizar_execucao(tarefa.id, indice, acao, texto,
                                                          erro=erro, incerto=incerto)
            if interrompido():
                pausar_interrompida()
                break
            if not pode_continuar or erro or incerto:
                break
        if tarefa.etapas and not tarefa.pendentes() and tarefa.estado in ("planejada", "em_execucao"):
            projetos.mudar_estado(tarefa.id, "executada_sem_verificacao")
        return tarefa


def validar_passos(passos: list[str], interpretar: Callable[[str], tuple[str, dict] | None]) -> tuple[list[str], str | None]:
    """Todos os passos precisam ser comandos conhecidos e permitidos. Devolve (passos, erro)."""
    if not passos:
        return [], "Não entendi os passos. Diga, por exemplo: crie o protocolo trabalho: abra o VS Code e me dê as notícias."
    if len(passos) > MAX_PASSOS:
        return [], f"No máximo {MAX_PASSOS} passos por protocolo."
    try:
        previas = preencher(passos, {}, previa=True)
    except ValueError as exc:
        return [], str(exc)
    for p in previas:
        achado = interpretar(p)
        if achado is None:
            return [], f"Não sei executar sozinho o passo \"{p}\". Use comandos que eu já conheço."
        if comando_proibido(achado[0]):
            return [], f"O passo \"{p}\" não pode rodar sozinho, por segurança."
    return passos, None
