"""O que estamos fazendo, o que já ficou pronto e o que falta.

Sem isto o Jarvis atende pedidos soltos: cada frase começa do zero e "continue
de ontem" não tem o que recuperar. Aqui fica o estado de verdade -- objetivo,
condição de conclusão, etapas, resultados, aprovações e datas -- num arquivo
JSON, não num resumo escrito pelo modelo (§6 do prompt mestre de 19/09).

Duas regras que valem mais que o resto:

1. **Retomar não repete.** Cada etapa concluída fica marcada com o resultado; ao
   voltar, o Jarvis segue da primeira etapa que ainda não terminou.
2. **O estado diz a verdade.** "executada_sem_verificacao" existe de propósito:
   é diferente de "concluida". Salvar um arquivo não é o mesmo que conferir que
   ele presta.
"""

from __future__ import annotations

import json
import copy
import os
import threading
import time
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
ARQ = HOME / "hud-projetos.json"

# A ordem importa para o resumo falado: do que ainda nem começou ao que morreu.
ESTADOS = (
    "planejada",                    # combinada, ninguem comecou
    "aguardando_informacao",        # falta um dado que so o Senhor tem
    "aguardando_autorizacao",       # falta ele aprovar
    "em_execucao",
    "pausada",
    "parcialmente_concluida",       # parte pronta, parte nao
    "executada_sem_verificacao",    # rodou, mas ninguem conferiu o resultado
    "concluida",
    "falha",
    "cancelada",
)
ABERTOS = ("planejada", "aguardando_informacao", "aguardando_autorizacao",
           "em_execucao", "pausada", "parcialmente_concluida", "executada_sem_verificacao")
FECHADOS = ("concluida", "falha", "cancelada")

_POR_EXTENSO = {
    "planejada": "planejada",
    "aguardando_informacao": "esperando uma informação sua",
    "aguardando_autorizacao": "esperando sua autorização",
    "em_execucao": "em andamento",
    "pausada": "pausada",
    "parcialmente_concluida": "parcialmente concluída",
    "executada_sem_verificacao": "executada, mas ainda não conferida",
    "concluida": "concluída",
    "falha": "falhou",
    "cancelada": "cancelada",
}


def por_extenso(estado: str) -> str:
    return _POR_EXTENSO.get(estado, estado)


_ultimo_instante = 0.0
_trava_relogio = threading.Lock()


def _agora() -> float:
    """time.time() com garantia de ser ESTRITAMENTE crescente.

    Duas tarefas mexidas no mesmo milissegundo empatavam, e aí "continue de
    ontem" podia pegar a errada (o teste pegou isso).
    """
    global _ultimo_instante
    with _trava_relogio:
        t = max(time.time(), _ultimo_instante + 1e-6)
        _ultimo_instante = t
        return t


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


@dataclass
class Etapa:
    """Um passo. `resultado` é o que ficou dele -- é isso que evita repetir.

    As condições de um ensaio (material, temperatura) NÃO ficam aqui: ficam no
    experimento (`registrar_experimento`), que é a casa delas. Uma ideia, um lugar.
    """
    descricao: str
    estado: str = "planejada"           # planejada | concluida | falha | cancelada
    resultado: str | None = None
    em: float = 0.0
    acao_id: str = ""
    tentativas: int = 0
    ferramenta: str = ""
    argumentos: dict[str, Any] = field(default_factory=dict)
    assinatura: str = ""
    chamada_id: str = ""
    depende_de: list[int] = field(default_factory=list)
    recursos: list[str] = field(default_factory=list)

    @property
    def pronta(self) -> bool:
        return self.estado == "concluida"


@dataclass
class Tarefa:
    id: str
    objetivo: str                        # o pedido do Senhor, como ele falou
    projeto: str = ""
    conclusao_quando: str = ""           # como saberemos que terminou
    estado: str = "planejada"
    restricoes: list[str] = field(default_factory=list)
    recursos: list[str] = field(default_factory=list)      # arquivos, aparelhos, contas
    depende_de: list[str] = field(default_factory=list)    # ids de outras tarefas
    etapas: list[Etapa] = field(default_factory=list)
    resultados: list[str] = field(default_factory=list)    # o que foi produzido
    aprovacoes: list[dict[str, Any]] = field(default_factory=list)
    origem: str = "voz"                  # voz | painel | telegram | rotina | protocolo
    versao: int = 1
    criada_em: float = 0.0
    mexida_em: float = 0.0
    motivo: str = ""                     # por que parou, falhou ou ficou esperando
    sessao_id: str = ""
    pedido_id: str = ""
    tarefa_pai: str = ""
    experimentos: list[dict[str, Any]] = field(default_factory=list)
    limite_acoes: int = 5
    chamadas_usadas: int = 0
    plano_encerrado: bool = False
    eventos_execucao: list[dict[str, Any]] = field(default_factory=list)
    ferramentas_modelo: list[dict[str, Any]] = field(default_factory=list)

    @property
    def aberta(self) -> bool:
        return self.estado in ABERTOS

    def _falta_antes(self, e: Etapa) -> list[str]:
        """Descrições das etapas de que `e` depende e que ainda não ficaram prontas."""
        faltam = []
        for i in e.depende_de:
            if isinstance(i, int) and 0 <= i < len(self.etapas) and not self.etapas[i].pronta:
                faltam.append(self.etapas[i].descricao)
        return faltam

    def proxima_etapa(self) -> Etapa | None:
        """A primeira que ainda não terminou E não está bloqueada (F41)."""
        for e in self.etapas:
            if e.estado in ("planejada", "falha") and not self._falta_antes(e):
                return e
        return None

    def bloqueadas(self) -> list[tuple[Etapa, list[str]]]:
        """(etapa, o que falta antes dela). Vazio = nada travado."""
        saida = []
        for e in self.etapas:
            if e.estado in ("planejada", "falha"):
                faltam = self._falta_antes(e)
                if faltam:
                    saida.append((e, faltam))
        return saida

    def pendentes(self) -> list[Etapa]:
        return [e for e in self.etapas if e.estado != "concluida"]

    def prontas(self) -> list[Etapa]:
        return [e for e in self.etapas if e.pronta]


class Projetos:
    """Guarda tarefas e projetos em JSON. Uma instância por runtime."""

    def __init__(self, arquivo: Path | str | None = None) -> None:
        self._arq = Path(arquivo) if arquivo else ARQ
        self._trava = threading.RLock()
        self._tarefas: dict[str, Tarefa] = {}
        self._ativa: str | None = None        # tarefa em foco ("isso", "continue")
        self._projeto: str = ""               # projeto em foco
        self._carregar()

    # ---- disco ----------------------------------------------------------
    def _carregar(self) -> None:
        try:
            d = json.loads(self._arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for bruta in d.get("tarefas", []):
            try:
                etapas = [Etapa(**e) for e in bruta.pop("etapas", [])]
                self._tarefas[bruta["id"]] = Tarefa(etapas=etapas, **bruta)
                t = self._tarefas[bruta["id"]]
                # Uma chamada interrompida pode ter produzido efeito externo.
                # Nunca repetir automaticamente depois de reiniciar.
                if t.estado == "em_execucao":
                    t.estado = "pausada"
                    t.motivo = "Runtime reiniciado; retome explicitamente."
                for e in t.etapas:
                    if e.estado == "em_execucao":
                        e.estado = "resultado_incerto"
                        if t.estado not in ("cancelada", "concluida"):
                            t.estado = "aguardando_informacao"
                            t.motivo = "Confira o efeito da etapa interrompida antes de repetir: " + e.descricao
            except (TypeError, KeyError):
                continue          # registro de uma versao antiga: ignora, nao derruba o Jarvis
        self._ativa = d.get("ativa")
        self._projeto = d.get("projeto", "")
        if self._ativa not in self._tarefas:
            self._ativa = None

    def salvar(self) -> None:
        with self._trava:
            dados = {"tarefas": [self._como_dict(t) for t in self._tarefas.values()],
                     "ativa": self._ativa, "projeto": self._projeto, "em": time.time()}
            self._arq.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._arq.with_suffix(".tmp")
            tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self._arq)          # troca atômica: nunca deixa o arquivo pela metade

    @staticmethod
    def _como_dict(t: Tarefa) -> dict[str, Any]:
        d = asdict(t)
        return d

    # ---- criar e achar --------------------------------------------------
    def criar(self, objetivo: str, *, projeto: str = "", conclusao_quando: str = "",
              etapas: Iterable[str] = (), origem: str = "voz", restricoes: Iterable[str] = (),
              recursos: Iterable[str] = (), sessao_id: str = "", pedido_id: str = "",
              depende_de: Iterable[str] = (), tarefa_pai: str = "") -> Tarefa:
        agora = _agora()
        with self._trava:
            if pedido_id:
                existente = next((t for t in self._tarefas.values()
                                  if t.pedido_id == pedido_id and t.sessao_id == sessao_id), None)
                if existente:
                    if existente.objetivo != objetivo.strip():
                        raise ValueError("pedido_id reutilizado para outro objetivo")
                    return existente
            tid = f"t{int(agora * 1000) % 10_000_000}"
            while tid in self._tarefas:
                tid += "a"
            dependencias = list(dict.fromkeys(depende_de))
            if any(dep not in self._tarefas for dep in dependencias):
                raise ValueError("dependência de tarefa inexistente")
            if tarefa_pai and tarefa_pai not in self._tarefas:
                raise ValueError("tarefa de origem inexistente")
            t = Tarefa(id=tid, objetivo=objetivo.strip(), projeto=(projeto or self._projeto).strip(),
                       conclusao_quando=conclusao_quando.strip(), origem=origem,
                       restricoes=list(restricoes), recursos=list(recursos),
                       depende_de=dependencias,
                       etapas=[Etapa(descricao=e) for e in etapas],
                       sessao_id=sessao_id, pedido_id=pedido_id,
                       tarefa_pai=tarefa_pai,
                       criada_em=agora, mexida_em=agora)
            self._tarefas[tid] = t
            self._ativa = tid
            if t.projeto:
                self._projeto = t.projeto
        self.salvar()
        return t

    def obter(self, tid: str) -> Tarefa | None:
        return self._tarefas.get(tid)

    def por_pedido(self, sessao_id: str, pedido_id: str) -> Tarefa | None:
        if not pedido_id:
            return None
        return next((t for t in self._tarefas.values()
                     if t.sessao_id == sessao_id and t.pedido_id == pedido_id), None)

    def inspecionar(self, tid: str) -> dict[str, Any]:
        """Dados executados, restrições declaradas e dependências, sem resumo inventado."""
        with self._trava:
            t = self._tarefas[tid]
            dados = self._como_dict(t)
            dados["dependencias"] = [{"id": dep, "estado": self._tarefas[dep].estado
                                       if dep in self._tarefas else "inexistente"} for dep in t.depende_de]
            dados["pendencias"] = [e.descricao for e in t.pendentes()]
            dados["aprovacao_pendente"] = t.estado == "aguardando_autorizacao"
            dados["restricoes_fonte"] = "declaradas; texto livre não equivale a validação automática"
            return dados

    def definir_requisitos(self, tid: str, *, conclusao_quando: str | None = None,
                           restricoes: Iterable[str] | None = None, recursos: Iterable[str] | None = None,
                           depende_de: Iterable[str] | None = None) -> Tarefa:
        """Atualização explícita e versionada; dependências inexistentes/cíclicas são recusadas."""
        with self._trava:
            t = self._tarefas[tid]
            if t.estado in ("cancelada", "concluida", "em_execucao"):
                raise ValueError("pause a tarefa aberta antes de alterar requisitos")
            deps = list(dict.fromkeys(depende_de)) if depende_de is not None else t.depende_de
            def alcança(origem, alvo, vistos):
                if origem == alvo:
                    return True
                if origem in vistos or origem not in self._tarefas:
                    return False
                return any(alcança(d, alvo, vistos | {origem}) for d in self._tarefas[origem].depende_de)
            if any(d not in self._tarefas or alcança(d, tid, set()) for d in deps):
                raise ValueError("dependência inexistente ou cíclica")
            antes = copy.deepcopy(t.__dict__)
            if conclusao_quando is not None:
                t.conclusao_quando = conclusao_quando.strip()
            if restricoes is not None:
                t.restricoes = list(dict.fromkeys(r.strip() for r in restricoes if r.strip()))
            if recursos is not None:
                t.recursos = list(dict.fromkeys(r.strip() for r in recursos if r.strip()))
            t.depende_de, t.mexida_em, t.versao = deps, _agora(), t.versao + 1
            # Novos requisitos não herdam autorização sobre o conteúdo anterior.
            t.aprovacoes = []
            try:
                self.salvar()
            except OSError:
                t.__dict__.update(antes)
                raise
            return t

    def registrar_plano_modelo(self, tid: str, chamadas: list[dict[str, Any]]) -> dict[str, int]:
        """Guarda o lote inteiro antes da primeira execução, com dependências sequenciais."""
        with self._trava:
            t = self._tarefas[tid]
            if t.origem != "modelo" or t.estado in ("cancelada", "concluida", "pausada"):
                raise ValueError("tarefa não aceita novas etapas do modelo")
            antes = copy.deepcopy(t.__dict__)
            indices = {}
            for c in chamadas:
                idx = next((i for i, e in enumerate(t.etapas) if e.assinatura == c["assinatura"]), None)
                if idx is None:
                    if len(t.etapas) >= t.limite_acoes:
                        t.__dict__.update(antes)
                        raise ValueError("limite de cinco ações persistentes atingido")
                    idx = len(t.etapas)
                    recursos = [f"ferramenta:{c['ferramenta']}"] + list(c.get("recursos", []))
                    t.etapas.append(Etapa(descricao=c["descricao"], ferramenta=c["ferramenta"],
                                         argumentos=copy.deepcopy(c["argumentos"]), assinatura=c["assinatura"],
                                         chamada_id=c["chamada_id"], depende_de=[idx - 1] if idx else [],
                                         recursos=recursos))
                    t.recursos = list(dict.fromkeys(t.recursos + recursos))
                indices[c["chamada_id"]] = idx
            t.mexida_em = _agora()
            try:
                self.salvar()
            except OSError:
                t.__dict__.update(antes)
                raise
            return indices

    def registrar_tentativa_modelo(self, tid: str, chamada_id: str, *, erro: str = "") -> bool:
        with self._trava:
            t = self._tarefas[tid]
            if t.chamadas_usadas >= t.limite_acoes or t.estado in ("cancelada", "concluida", "pausada"):
                return False
            antes = copy.deepcopy(t.__dict__)
            t.chamadas_usadas += 1
            t.eventos_execucao.append({"chamada_id": chamada_id, "erro_validacao": erro,
                                      "em": _agora(), "sessao_id": t.sessao_id,
                                      "pedido_id": t.pedido_id, "tarefa_id": tid, "projeto": t.projeto})
            try:
                self.salvar()
            except OSError:
                t.__dict__.update(antes)
                raise
            return True

    def ativa(self) -> Tarefa | None:
        t = self._tarefas.get(self._ativa or "")
        return t if t and t.aberta else None

    def focar(self, tid: str) -> Tarefa | None:
        with self._trava:
            t = self._tarefas.get(tid)
            if t is None:
                return None
            self._ativa = tid
            if t.projeto:
                self._projeto = t.projeto
        self.salvar()
        return t

    @property
    def projeto(self) -> str:
        return self._projeto

    def abrir_projeto(self, nome: str) -> str:
        """Troca de projeto SEM perder o anterior: cada tarefa guarda o seu."""
        with self._trava:
            self._projeto = nome.strip()
            atual = self._tarefas.get(self._ativa or "")
            if atual is not None and _norm(atual.projeto) != _norm(self._projeto):
                self._ativa = None        # nao misturar parametros de projetos diferentes
        self.salvar()
        return self._projeto

    def abertas(self, projeto: str | None = None) -> list[Tarefa]:
        alvo = _norm(projeto) if projeto else None
        saida = [t for t in self._tarefas.values()
                 if t.aberta and (alvo is None or _norm(t.projeto) == alvo)]
        return sorted(saida, key=lambda t: t.mexida_em, reverse=True)

    def todas(self) -> list[Tarefa]:
        return sorted(self._tarefas.values(), key=lambda t: t.mexida_em, reverse=True)

    def projetos(self) -> list[str]:
        vistos: dict[str, str] = {}
        for t in sorted(self._tarefas.values(), key=lambda t: t.mexida_em, reverse=True):
            if t.projeto and _norm(t.projeto) not in vistos:
                vistos[_norm(t.projeto)] = t.projeto
        return list(vistos.values())

    def achar(self, texto: str, *, so_abertas: bool = False) -> Tarefa | None:
        """Acha pelo nome falado: "a caixa", "o projeto da luminária"."""
        alvo = _norm(texto)
        if not alvo:
            return None
        candidatas = self.abertas() if so_abertas else self.todas()
        palavras = [p for p in alvo.split() if len(p) > 2]
        melhor, nota_melhor = None, 0
        for t in candidatas:
            texto_t = _norm(f"{t.objetivo} {t.projeto}")
            if alvo in texto_t:
                return t
            nota = sum(1 for p in palavras if p in texto_t)
            if nota > nota_melhor:
                melhor, nota_melhor = t, nota
        return melhor if nota_melhor else None

    def ultima_mexida(self, *, so_abertas: bool = True) -> Tarefa | None:
        """Para "continue de ontem": a última em que trabalhamos."""
        lista = self.abertas() if so_abertas else self.todas()
        return lista[0] if lista else None

    # ---- mexer ----------------------------------------------------------
    def mudar_estado(self, tid: str, estado: str, motivo: str = "") -> Tarefa | None:
        if estado not in ESTADOS:
            raise ValueError(f"estado desconhecido: {estado}")
        with self._trava:
            t = self._tarefas.get(tid)
            if t is None:
                return None
            if t.estado == "cancelada" and estado != "cancelada":
                raise ValueError("tarefa cancelada não pode ser reaberta; crie um novo pedido")
            t.estado, t.motivo, t.mexida_em = estado, motivo, _agora()
            if estado in FECHADOS and self._ativa == tid:
                self._ativa = None
        self.salvar()
        return t

    def acrescentar_etapas(self, tid: str, descricoes: Iterable[str]) -> Tarefa | None:
        with self._trava:
            t = self._tarefas.get(tid)
            if t is None:
                return None
            existentes = {_norm(e.descricao) for e in t.etapas}
            for d in descricoes:
                if _norm(d) not in existentes:          # nao duplica etapa ja listada
                    t.etapas.append(Etapa(descricao=d))
                    existentes.add(_norm(d))
            t.mexida_em = _agora()
        self.salvar()
        return t

    def depender(self, tid: str, etapa: str, de: str) -> Etapa | None:
        """"exportar só depois de furar": dependência entre etapas (F41).

        Guarda o ÍNDICE da etapa anterior, que é o formato usado pelo executor
        de planos; aqui só traduzo o nome falado para esse índice.
        """
        with self._trava:
            t = self._tarefas.get(tid)
            if t is None:
                return None
            alvo, antes = _norm(etapa), _norm(de)
            if alvo == antes:
                raise ValueError("uma etapa não pode depender de si mesma")
            e = next((x for x in t.etapas if _norm(x.descricao) == alvo), None)
            if e is None:
                e = Etapa(descricao=etapa)
                t.etapas.append(e)
            anterior = next((x for x in t.etapas if _norm(x.descricao) == antes), None)
            if anterior is None:
                anterior = Etapa(descricao=de)
                t.etapas.insert(t.etapas.index(e), anterior)
            i = t.etapas.index(anterior)
            if i not in e.depende_de:
                e.depende_de.append(i)
            t.mexida_em = _agora()
        self.salvar()
        return e

    def concluir_etapa(self, tid: str, descricao: str, resultado: str | None = None) -> Etapa | None:
        """Marca a etapa como feita. Se já estava feita, NÃO refaz nem duplica."""
        with self._trava:
            t = self._tarefas.get(tid)
            if t is None or t.estado in ("cancelada", "concluida"):
                return None
            alvo = _norm(descricao)
            etapa = next((e for e in t.etapas if _norm(e.descricao) == alvo), None)
            if etapa is None:
                etapa = Etapa(descricao=descricao)
                t.etapas.append(etapa)
            if etapa.pronta:
                return etapa                        # idempotente: retomar não repete
            etapa.estado, etapa.resultado, etapa.em = "concluida", resultado, _agora()
            if resultado:
                t.resultados.append(resultado)
            t.mexida_em = _agora()
            if t.estado == "planejada":
                t.estado = "em_execucao"
            if not t.pendentes() and t.etapas and t.estado != "pausada":
                # tudo feito, mas quem disse que está certo? só o Senhor ou uma verificação
                t.estado = "executada_sem_verificacao"
        self.salvar()
        return etapa

    def falhar_etapa(self, tid: str, descricao: str, motivo: str) -> Etapa | None:
        with self._trava:
            t = self._tarefas.get(tid)
            if t is None or t.estado in ("cancelada", "concluida"):
                return None
            alvo = _norm(descricao)
            etapa = next((e for e in t.etapas if _norm(e.descricao) == alvo), None)
            if etapa is not None and etapa.pronta:
                return etapa
            if etapa is None:
                etapa = Etapa(descricao=descricao)
                t.etapas.append(etapa)
            etapa.estado, etapa.resultado, etapa.em = "falha", motivo, _agora()
            t.estado, t.motivo, t.mexida_em = "parcialmente_concluida" if t.prontas() else "falha", motivo, _agora()
        self.salvar()
        return etapa

    def registrar_resultado(self, tid: str, texto: str) -> Tarefa | None:
        with self._trava:
            t = self._tarefas.get(tid)
            if t is None or t.estado in ("cancelada", "concluida"):
                return None
            t.resultados.append(texto)
            t.mexida_em = _agora()
            if t.estado == "planejada":
                t.estado = "em_execucao"        # houve trabalho: nao esta mais so planejada
        self.salvar()
        return t

    def aprovar(self, tid: str, operacao: str, parametros: str = "") -> Tarefa | None:
        """Aprovação vale para ESTA operação e ESTES parâmetros (§18)."""
        with self._trava:
            t = self._tarefas.get(tid)
            if t is None:
                return None
            t.aprovacoes.append({"operacao": operacao, "parametros": parametros, "em": _agora()})
            if t.estado == "aguardando_autorizacao":
                t.estado = "em_execucao"
            t.mexida_em = _agora()
        self.salvar()
        return t

    def tem_aprovacao(self, tid: str, operacao: str, parametros: str = "") -> bool:
        t = self._tarefas.get(tid)
        if t is None:
            return False
        return t.estado != "cancelada" and any(a["operacao"] == operacao and a.get("parametros", "") == parametros
                   for a in t.aprovacoes)

    def nova_versao(self, tid: str, resultado: str) -> Tarefa | None:
        with self._trava:
            t = self._tarefas.get(tid)
            if t is None:
                return None
            t.versao += 1
            t.resultados.append(resultado)
            t.mexida_em = _agora()
        self.salvar()
        return t

    def iniciar_etapa(self, tid: str, indice: int) -> str | None:
        """Reserva persistida antes da ferramenta; uma única chamada por etapa.

        Resultado incerto (incluindo queda durante a chamada) exige conferência,
        e não é uma autorização de retry. Não promete exactly-once externo.
        """
        with self._trava:
            t = self._tarefas.get(tid)
            if t is None or t.estado in ("cancelada", "concluida", "pausada", "aguardando_autorizacao"):
                return None
            if not 0 <= indice < len(t.etapas):
                raise IndexError("etapa inexistente")
            if any(self.obter(dep) is None or self.obter(dep).estado != "concluida" for dep in t.depende_de):
                t.estado, t.motivo = "aguardando_informacao", "Há tarefas dependentes ainda não concluídas."
                self.salvar()
                return None
            e = t.etapas[indice]
            if any(not isinstance(dep, int) or dep < 0 or dep >= indice or not t.etapas[dep].pronta
                   for dep in e.depende_de):
                t.estado, t.motivo = "aguardando_informacao", "Há etapas dependentes ainda não concluídas."
                self.salvar()
                return None
            if e.estado != "planejada" or any(not p.pronta for p in t.etapas[:indice]):
                return None
            e.estado, e.acao_id, e.em = "em_execucao", uuid.uuid4().hex, _agora()
            for evento in reversed(t.eventos_execucao):
                if evento["chamada_id"] == e.chamada_id and "acao_id" not in evento:
                    evento["acao_id"] = e.acao_id
                    break
            e.tentativas += 1
            t.estado, t.mexida_em = "em_execucao", _agora()
            self.salvar()  # falhar aqui impede chamar a ferramenta
            return e.acao_id

    def finalizar_execucao(self, tid: str, indice: int, acao_id: str, resultado: str,
                           *, erro: bool = False, incerto: bool = False) -> bool:
        """Registra o retorno na tarefa original, inclusive após cancelar.

        False indica retorno que não deve ser anunciado nem alimentar outro pedido.
        """
        with self._trava:
            t = self._tarefas.get(tid)
            if t is None or not 0 <= indice < len(t.etapas):
                return False
            e = t.etapas[indice]
            if e.acao_id != acao_id or e.estado != "em_execucao":
                return False
            e.estado = "resultado_incerto" if incerto else "falha" if erro else "concluida"
            e.resultado, e.em = resultado, _agora()
            t.resultados.append(resultado)
            t.mexida_em = _agora()
            ativo = t.estado not in ("cancelada", "pausada")
            if ativo:
                if incerto:
                    t.estado, t.motivo = "aguardando_informacao", resultado
                elif erro:
                    t.estado, t.motivo = "parcialmente_concluida" if t.prontas() else "falha", resultado
                elif not t.pendentes():
                    t.estado = "executada_sem_verificacao"
            self.salvar()
            return ativo

    def conferir_etapa(self, tid: str, indice: int, *, executada: bool, evidencia: str) -> Etapa:
        """Conferência explícita permite continuar após interrupção de efeito incerto."""
        if not evidencia.strip():
            raise ValueError("registre a evidência da conferência")
        with self._trava:
            t = self._tarefas[tid]
            if t.estado == "cancelada":
                raise ValueError("tarefa cancelada")
            e = t.etapas[indice]
            if e.estado not in ("resultado_incerto", "falha"):
                raise ValueError("a etapa não aguarda conferência")
            e.estado = "concluida" if executada else "planejada"
            e.resultado, e.em = evidencia, _agora()
            t.resultados.append("Conferência da etapa: " + evidencia)
            t.estado = "pausada" if t.pendentes() else "executada_sem_verificacao"
            t.motivo, t.mexida_em = evidencia, _agora()
            self.salvar()
            return e

    def registrar_experimento(self, tid: str, nome: str, *, resultado: str,
                              condicoes: str = "", unidades: str = "", falha: str = "",
                              fonte: str = "usuario", versao_peca: int | None = None) -> dict[str, Any]:
        """Caderno de ensaio: relato/medição não conclui nem valida o projeto."""
        if not nome.strip() or not resultado.strip():
            raise ValueError("informe nome e resultado observado do experimento")
        with self._trava:
            t = self._tarefas[tid]
            registro = {"id": uuid.uuid4().hex, "nome": nome.strip(), "resultado": resultado,
                        "condicoes": condicoes, "unidades": unidades, "falha": falha,
                        "fonte": fonte, "versao_peca": versao_peca, "em": _agora(),
                        "validacao": "relato_usuario" if fonte == "usuario" else "resultado_ferramenta"}
            t.experimentos.append(registro)
            t.mexida_em = _agora()
            self.salvar()
            return registro

    def esquecer(self, tid: str) -> bool:
        with self._trava:
            saiu = self._tarefas.pop(tid, None) is not None
            if self._ativa == tid:
                self._ativa = None
        if saiu:
            self.salvar()
        return saiu


# ---- como o Jarvis fala disso -------------------------------------------
def _lista(itens: list[str]) -> str:
    if not itens:
        return ""
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def resumo_falado(t: Tarefa, tratamento: str = "Senhor") -> str:
    """Uma a três frases: onde está, o que ficou pronto e o que falta."""
    objetivo = t.objetivo[:1].upper() + t.objetivo[1:]      # capitalize() estragava "Arduino"
    partes = [f"{objetivo}: {por_extenso(t.estado)}"]
    if t.projeto and _norm(t.projeto) != _norm(t.objetivo):
        partes[0] = f"{t.projeto} — {partes[0]}"        # sem repetir o nome do projeto
    prontas, pendentes = t.prontas(), t.pendentes()
    if prontas:
        partes.append(f"Já fiz: {_lista([e.descricao for e in prontas[:3]])}")
    if pendentes:
        partes.append(f"Falta: {_lista([e.descricao for e in pendentes[:3]])}")
    travadas = t.bloqueadas()
    if travadas:
        e, faltam = travadas[0]
        partes.append(f"{e.descricao} depende de {_lista(faltam)}")
    if t.experimentos:
        ultimo = t.experimentos[-1]
        cond = ultimo.get("condicoes") or ""
        partes.append(f"Último ensaio: {ultimo.get('nome')} — {ultimo.get('resultado')}"
                      + (f" ({cond})" if cond else ""))
    elif t.etapas and t.estado == "executada_sem_verificacao":
        partes.append("Todas as etapas rodaram, mas nada foi conferido ainda")
    if t.resultados:
        partes.append(f"Último resultado: {t.resultados[-1]}")
    if t.motivo:
        partes.append(f"Motivo: {t.motivo}")
    if t.conclusao_quando and t.aberta:
        partes.append(f"Termina quando {t.conclusao_quando}")
    return ". ".join(partes).replace("..", ".") + "."


def resumo_da_lista(tarefas: list[Tarefa], tratamento: str = "Senhor") -> str:
    if not tarefas:
        return f"Não há nada em andamento, {tratamento}."
    if len(tarefas) == 1:
        return resumo_falado(tarefas[0], tratamento)
    nomes = [f"{t.objetivo} ({por_extenso(t.estado)})" for t in tarefas[:4]]
    return f"Tenho {len(tarefas)} em andamento, {tratamento}: {_lista(nomes)}."
