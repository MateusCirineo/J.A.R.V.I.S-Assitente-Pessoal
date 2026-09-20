"""Fonte unica de estado do runtime, com difusao para as telas via SSE.

Cada canal e independente. Gerar uma resposta e tocar outra ao mesmo tempo
e possivel, entao "inferencia" e "reproducao" nunca compartilham variavel.

Niveis de audio (dezenas por segundo) nao entram no estado versionado: vao
direto aos inscritos como eventos "nivel", para nao reenviar tudo a cada
amostra.
"""

from __future__ import annotations

import copy
import json
import queue
import secrets
import threading
import time
from collections import deque
from typing import Any

ETAPAS_BOOT = [
    ("servidor", "Servidor OpenJarvis"),
    ("ollama", "Motor Ollama"),
    ("modelo_chat", "Modelo do chat"),
    ("modelo_voz", "Modelo da voz"),
    ("microfone", "Microfone"),
    ("saida_audio", "Saída de áudio"),
    ("sintese", "Síntese de voz"),
    ("transcricao", "Transcrição"),
    ("eventos", "Eventos do servidor"),
    ("memoria", "Memória"),
]


def _estado_inicial() -> dict[str, Any]:
    return {
        "pedido": {"sessao_id": None, "pedido_id": None, "estado": "inativo", "em": None},
        "previa": {"estado": "inativo", "arquivo": None, "em": None},
        "conexao": {
            "servidor": {"estado": "desconhecido", "detalhe": None, "em": None},
            "ollama": {"estado": "desconhecido", "detalhe": None, "em": None},
            "eventos": {"estado": "desconectado", "detalhe": None, "em": None},
        },
        "microfone": {
            # desativado | calibrando | ouvindo | captando | pausado | erro
            "estado": "desativado",
            "dispositivo": None,
            "ruido_rms": None,
            "limiar_rms": None,
            "detalhe": None,
        },
        "inferencia": {
            # ativas_servidor conta pela profundidade de eventos: cada pedido
            # gera dois INFERENCE_START e dois INFERENCE_END (duas camadas).
            "ativas_servidor": 0,
            "voz_em_andamento": False,
            "modelo": None,
            "desde": None,
            "ultima": None,
        },
        "reproducao": {
            # parado | preparando | falando | erro
            "estado": "parado",
            "volume": 1.0,
            "dispositivo": None,
            "detalhe": None,
            "inicio": None,
        },
        "boot": {
            "etapas": [
                {"id": i, "rotulo": r, "estado": "pendente", "detalhe": None}
                for i, r in ETAPAS_BOOT
            ],
            "concluido": False,
            # online | limitado: so vira "online" se TODAS as etapas passarem
            "resultado": None,
        },
        "conversa": {"ultima_fala": None, "ultima_resposta": None, "em": None},
        "modelos": {"chat": None, "voz": None},
        "camera": {"ativa": False, "presente": False, "desde": None, "fps": None,
                   "detector": None, "detalhe": None},
        "tarefas": {"itens": []},
        "notificacoes": {"itens": [], "nao_lidas": 0},
        # analise visual ("o que e isso?"): olhando | analisando | pronto | erro
        "visao": {"estado": None, "pergunta": None, "resposta": None, "miniatura": None,
                  "em": None, "duracao_s": None, "olhar": None},
        "secretario": {"lembretes": [], "notas": []},
        # cartao de contexto: noticias listadas, fontes de uma pesquisa, cotacoes
        "contexto": {"tipo": None, "titulo": None, "itens": [], "em": None},
        "monitores": {"itens": []},
        # percepcao do ambiente: objetos vistos na regiao (fracoes do quadro), cena e quando
        "percepcao": {"objetos": [], "cena": None, "em": None, "regiao": None, "duracao_s": None},
        "vigia": {"ativo": False, "armado_em": None, "ultimo_alerta": None},
        # o que estamos fazendo agora: a tela mostra a MESMA tarefa de que a voz fala
        "projeto": {"projeto": None, "tarefa": None, "abertas": 0, "em": None},
        "peca": {"nome": None, "tipo": None, "versao": 0, "parametros": [], "volume_cm3": None,
                 "arquivo": None, "historico": [], "em": None},
        # a cena observada: o que esta em vista, o que sumiu e o que NAO foi olhado
        "cena": {"em": None, "camera_ligada": False, "regua_calibrada": False, "itens": [],
                 "observadas": [], "sem_observacao": [], "fonte": None},
        # o que esta selecionado agora, e por qual entrada (mouse, voz, gesto...)
        "selecao": {"alvo": None, "entradas": {}, "em": None},
        "gestos": {"ativo": False, "fase": "desativado", "calibrado": False,
                   "ponteiro": None, "acao": None, "cliente": None, "em": None},
        "apresentacao": {"id": None, "destino": "holograma", "estado": "vazia", "arquivo": None},
        # identificacao fina: cada atributo com o estado da evidencia (§8)
        "identificacao": {"categoria": None, "qualidade": None, "atributos": [], "candidatos": [],
                          "evidencias": [], "proximo_passo": None, "em": None},
        "anuncio": {"texto": None, "em": None},
    }


class Estado:
    def __init__(self) -> None:
        # muda a cada execucao do runtime: a tela detecta o reinicio e se
        # recarrega para pegar o token novo
        self.sessao = secrets.token_hex(4)
        self._trava = threading.RLock()
        self._dados = _estado_inicial()
        self._versao = 0
        self._eventos: deque[dict] = deque(maxlen=60)
        self._inscritos: list[queue.Queue] = []
        self._ultimo_nivel: dict[str, float] = {}
        self.telemetria: dict[str, Any] = {}

    # -- leitura --------------------------------------------------------------

    def instantaneo(self) -> dict[str, Any]:
        with self._trava:
            d = copy.deepcopy(self._dados)
            d["versao"] = self._versao
            d["sessao"] = self.sessao
            d["eventos"] = list(self._eventos)
            return d

    def ler(self, canal: str) -> Any:
        with self._trava:
            return copy.deepcopy(self._dados[canal])

    # -- escrita --------------------------------------------------------------

    def atualizar(self, canal: str, **valores: Any) -> None:
        """Mescla valores num canal e difunde o canal inteiro."""
        with self._trava:
            alvo = self._dados[canal]
            for k, v in valores.items():
                if isinstance(v, dict) and isinstance(alvo.get(k), dict):
                    alvo[k].update(v)
                else:
                    alvo[k] = v
            self._versao += 1
            carga = {"canal": canal, "valor": copy.deepcopy(alvo), "versao": self._versao}
        self._difundir("canal", carga)

    def etapa_boot(self, etapa: str, estado: str, detalhe: str | None = None) -> None:
        with self._trava:
            for e in self._dados["boot"]["etapas"]:
                if e["id"] == etapa:
                    e["estado"] = estado
                    e["detalhe"] = detalhe
            self._versao += 1
            carga = {"canal": "boot", "valor": copy.deepcopy(self._dados["boot"]),
                     "versao": self._versao}
        self._difundir("canal", carga)

    def registrar(self, tipo: str, texto: str, nivel: str = "info") -> None:
        ev = {"em": time.time(), "tipo": tipo, "texto": texto, "nivel": nivel}
        with self._trava:
            self._eventos.append(ev)
        self._difundir("log", ev)

    def definir_telemetria(self, amostra: dict[str, Any]) -> None:
        with self._trava:
            self.telemetria = amostra
        self._difundir("telemetria", amostra)

    def publicar(self, evento: str, dados: Any) -> None:
        self._difundir(evento, dados)

    def nivel(self, fonte: str, rms: float, bandas: list[float] | None,
              taxa_hz: float = 20.0, onda: list[float] | None = None) -> None:
        """Nivel real de audio (entrada ou saida), limitado a taxa_hz.
        `onda` e a forma de onda do bloco, reduzida a poucos pontos."""
        agora = time.monotonic()
        if agora - self._ultimo_nivel.get(fonte, 0.0) < 1.0 / taxa_hz:
            return
        self._ultimo_nivel[fonte] = agora
        self._difundir("nivel", {"fonte": fonte, "rms": round(rms, 4),
                                 "bandas": bandas, "onda": onda})

    # -- inscricao SSE --------------------------------------------------------

    def inscrever(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=400)
        with self._trava:
            self._inscritos.append(q)
        return q

    def cancelar(self, q: queue.Queue) -> None:
        with self._trava:
            if q in self._inscritos:
                self._inscritos.remove(q)

    def _difundir(self, evento: str, dados: Any) -> None:
        linha = f"event: {evento}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"
        with self._trava:
            inscritos = list(self._inscritos)
        for q in inscritos:
            try:
                q.put_nowait(linha)
            except queue.Full:
                # cliente lento: descarta niveis antigos, nunca bloqueia o audio
                if evento != "nivel":
                    try:
                        q.get_nowait()
                        q.put_nowait(linha)
                    except (queue.Empty, queue.Full):
                        pass
