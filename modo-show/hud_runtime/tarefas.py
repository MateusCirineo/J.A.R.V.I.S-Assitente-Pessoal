"""Tarefas locais (~/.openjarvis/hud-tarefas.json). Funcionam sem conta nenhuma."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
ARQUIVO = HOME / "hud-tarefas.json"
MAX_TEXTO = 200


class Tarefas:
    def __init__(self, arquivo: Path = ARQUIVO, ao_mudar=None) -> None:
        self._arquivo = arquivo
        self._trava = threading.Lock()
        self._ao_mudar = ao_mudar
        try:
            self._itens: list[dict[str, Any]] = json.loads(arquivo.read_text(encoding="utf-8"))
            if not isinstance(self._itens, list):
                raise ValueError
        except (OSError, ValueError):
            self._itens = []

    def listar(self) -> list[dict[str, Any]]:
        with self._trava:
            return [dict(t) for t in self._itens]

    def _salvar(self) -> None:
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._itens, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._arquivo)
        if self._ao_mudar:
            self._ao_mudar(self.listar_sem_trava())

    def listar_sem_trava(self) -> list[dict[str, Any]]:
        return [dict(t) for t in self._itens]

    def adicionar(self, texto: str) -> dict[str, Any]:
        texto = " ".join((texto or "").split())[:MAX_TEXTO]
        if not texto:
            raise ValueError("tarefa vazia")
        item = {"id": uuid.uuid4().hex[:10], "texto": texto, "feita": False, "criada": time.time()}
        with self._trava:
            self._itens.append(item)
            self._salvar()
        return item

    def alternar(self, ident: str) -> None:
        with self._trava:
            for t in self._itens:
                if t["id"] == ident:
                    t["feita"] = not t["feita"]
                    t["concluida"] = time.time() if t["feita"] else None
                    self._salvar()
                    return
        raise ValueError("tarefa não encontrada")

    def remover(self, ident: str) -> None:
        with self._trava:
            antes = len(self._itens)
            self._itens = [t for t in self._itens if t["id"] != ident]
            if len(self._itens) == antes:
                raise ValueError("tarefa não encontrada")
            self._salvar()

    def limpar_feitas(self) -> int:
        with self._trava:
            antes = len(self._itens)
            self._itens = [t for t in self._itens if not t["feita"]]
            self._salvar()
            return antes - len(self._itens)

    def concluir_por_texto(self, trecho: str) -> dict[str, Any] | None:
        alvo = trecho.lower().strip(" .!?")
        with self._trava:
            for t in self._itens:
                if not t["feita"] and alvo and alvo in t["texto"].lower():
                    t["feita"] = True
                    t["concluida"] = time.time()
                    self._salvar()
                    return dict(t)
        return None
