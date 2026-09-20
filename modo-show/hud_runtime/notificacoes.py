"""Notificacoes do HUD, geradas a partir de mudancas reais na telemetria.

Nada e inventado: cada aviso vem de uma comparacao entre duas amostras
(bateria, memoria, disco, servicos, downloads, aprovacoes, agenda).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Callable

from .estado import Estado


class Notificacoes:
    def __init__(self, estado: Estado,
                 ao_notificar: Callable[[dict[str, Any]], None] | None = None) -> None:
        self._estado = estado
        self._ao_notificar = ao_notificar      # ex.: repassar ao Windows
        self._itens: deque[dict[str, Any]] = deque(maxlen=40)
        self._chaves: dict[str, float] = {}
        self._nao_lidas = 0
        self._trava = threading.Lock()

    def _publicar(self) -> None:
        self._estado.atualizar("notificacoes", itens=list(self._itens), nao_lidas=self._nao_lidas)

    def notificar(self, texto: str, nivel: str = "info", tipo: str = "sistema",
                  chave: str | None = None, janela_s: float = 600) -> bool:
        agora = time.time()
        with self._trava:
            if chave and agora - self._chaves.get(chave, 0) < janela_s:
                return False
            if chave:
                self._chaves[chave] = agora
            item = {"em": agora, "texto": texto, "nivel": nivel, "tipo": tipo}
            self._itens.appendleft(item)
            self._nao_lidas += 1
            self._publicar()
        self._estado.registrar("notificacao", texto, nivel)
        if self._ao_notificar:
            try:
                self._ao_notificar(item)
            except Exception:  # noqa: BLE001 - o aviso na tela ja foi dado
                pass
        return True

    def marcar_lidas(self) -> None:
        with self._trava:
            self._nao_lidas = 0
            self._publicar()

    def limpar(self) -> None:
        with self._trava:
            self._itens.clear()
            self._nao_lidas = 0
            self._publicar()


class Vigia:
    """Compara cada amostra de telemetria com a anterior e gera avisos."""

    def __init__(self, notif: Notificacoes) -> None:
        self._n = notif
        self._ant: dict[str, Any] = {}

    def observar(self, t: dict[str, Any]) -> None:
        n = self._n
        s = t.get("sistema", {})

        b = s.get("bateria", {})
        if b.get("status") == "medido":
            if not b["na_tomada"] and b["percentual"] <= 10:
                n.notificar(f"Bateria crítica: {b['percentual']:.0f}%. Conecte o carregador.",
                            "erro", "energia", "bateria_critica", 900)
            elif not b["na_tomada"] and b["percentual"] <= 20:
                n.notificar(f"Bateria baixa: {b['percentual']:.0f}%.", "aviso", "energia",
                            "bateria_baixa", 1800)
            antes = self._ant.get("na_tomada")
            if antes is not None and antes != b["na_tomada"]:
                n.notificar("Carregador conectado." if b["na_tomada"] else "Carregador desconectado.",
                            "info", "energia")
            self._ant["na_tomada"] = b["na_tomada"]

        m = s.get("memoria", {})
        if m.get("status") == "medido" and m["uso_pct"] >= 92:
            n.notificar(f"Memória quase cheia: {m['uso_pct']:.0f}% em uso "
                        f"({m['livre_gb']:.1f} GB livres).", "aviso", "sistema", "ram_alta", 900)
        d = s.get("disco", {})
        if d.get("status") == "medido" and d["livre_gb"] < 10:
            n.notificar(f"Disco {d['unidade']} com só {d['livre_gb']:.0f} GB livres.", "aviso",
                        "sistema", "disco_baixo", 3600)

        for chave, rotulo in (("servidor", "Servidor OpenJarvis"), ("ollama", "Ollama")):
            atual = t.get(chave, {}).get("status")
            antes = self._ant.get(chave)
            if antes and atual and antes != atual:
                if atual == "ok":
                    n.notificar(f"{rotulo} voltou.", "info", "servico")
                else:
                    n.notificar(f"{rotulo} parou de responder.", "erro", "servico")
            if atual:
                self._ant[chave] = atual

        dl = t.get("arquivos", {}).get("downloads", {})
        if dl.get("status") == "medido":
            andamento = {i["nome"] for i in dl["em_andamento"]}
            antes = self._ant.get("downloads")
            if antes is not None:
                recentes = {i["nome"] for i in dl["recentes"]}
                for parcial in antes - andamento:
                    final = parcial.rsplit(".", 1)[0]
                    if final in recentes:
                        n.notificar(f"Download concluído: {final}", "info", "arquivos")
                for novo in andamento - antes:
                    n.notificar(f"Download em andamento: {novo.rsplit('.', 1)[0]}", "info", "arquivos")
            self._ant["downloads"] = andamento

        ap = t.get("servidor_extra", {}).get("aprovacoes")
        if isinstance(ap, int):
            if ap > self._ant.get("aprovacoes", 0):
                n.notificar(f"{ap} ação(ões) aguardando sua aprovação no Chat.", "aviso", "openjarvis")
            self._ant["aprovacoes"] = ap

        em = t.get("email", {})
        if em.get("status") == "medido":
            recentes = {r["id"]: r for c in em.get("contas", []) for r in c.get("recentes", [])}
            antes = self._ant.get("emails")
            if antes is not None:                  # a primeira leitura so registra
                for i, r in recentes.items():
                    if i not in antes:
                        n.notificar(f"Novo e-mail de {r['de']}: {r['assunto']}", "info", "email",
                                    f"email-{i}", 86400)
            self._ant["emails"] = set(recentes) | (antes or set())

        ag = t.get("agenda", {})
        if ag.get("status") == "medido":
            agora = time.time()
            for ev in ag.get("eventos", []):
                falta = ev["inicio"] - agora
                if not ev["dia_inteiro"] and 0 < falta <= 600:
                    n.notificar(f"Em {max(1, round(falta / 60))} min: {ev['titulo']}", "aviso", "agenda",
                                f"agenda-{ev['titulo']}-{ev['inicio']}", 3600)
