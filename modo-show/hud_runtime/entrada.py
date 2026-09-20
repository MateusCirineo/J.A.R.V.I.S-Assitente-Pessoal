"""Pedidos com identidade, continuidade de sessão e recibos persistentes.

Uma reconexão consulta o recibo; não repete a escrita. Após queda, um pedido
iniciado fica incerto até conferência, nunca é anunciado como concluído.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
import threading
import time
from pathlib import Path

ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
REFERENCIAS = {"_ultimo": None, "ultima_lista": [], "ultima_lista_em": 0,
              "_pendente": None, "_limpeza_memoria_ate": 0, "_previa_peca": None,
              "_ultima_evidencia": None}


class Entrada:
    def __init__(self, rt, arquivo: Path):
        self.rt = rt
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(arquivo), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS pedidos (sessao TEXT, id TEXT, hash TEXT, estado TEXT, resposta TEXT, em REAL, PRIMARY KEY(sessao,id))")
        if "metadados" not in {row[1] for row in self.db.execute("PRAGMA table_info(pedidos)")}:
            self.db.execute("ALTER TABLE pedidos ADD COLUMN metadados TEXT")
        self.db.execute("CREATE TABLE IF NOT EXISTS sessoes (id TEXT PRIMARY KEY, historico TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS cancelamentos (sessao TEXT, id TEXT, em REAL, PRIMARY KEY(sessao,id))")
        self.db.execute("UPDATE pedidos SET estado='incerto' WHERE estado='em_execucao'")
        self.db.commit()
        self.trava = threading.RLock()
        self.ativo = None
        self.cancelados = set()
        self.referencias = {}

    def cancelar(self, sessao: str, pedido: str) -> dict:
        if not ID.fullmatch(sessao) or not ID.fullmatch(pedido):
            raise ValueError("identificadores inválidos")
        with self.trava:
            chave = (sessao, pedido)
            self.cancelados.add(chave)
            try:
                self.db.execute("INSERT OR IGNORE INTO cancelamentos VALUES (?,?,?)", (*chave, time.time()))
                self.db.commit()
            except sqlite3.Error:
                self.db.rollback()
                if self.ativo == chave:
                    self.rt.conversa.interromper()
                return {"ok": False, "estado": "cancelamento_sem_recibo",
                        "detalhe": "Interrupção solicitada, mas não consegui persistir o cancelamento."}
            if len(self.cancelados) > 256:
                self.cancelados = {chave}
            if self.ativo == chave:
                self.rt.conversa.interromper()
                return {"ok": True, "estado": "cancelamento_solicitado"}
            return {"ok": True, "estado": "sem_execucao_ativa"}

    def atender(self, corpo: dict) -> dict:
        sessao, pedido = corpo.get("sessao_id", ""), corpo.get("pedido_id", "")
        texto = corpo.get("texto", "")
        if not isinstance(sessao, str) or not isinstance(pedido, str) or not ID.fullmatch(sessao) or not ID.fullmatch(pedido):
            raise ValueError("identificadores de sessão e pedido inválidos")
        if not isinstance(texto, str) or not texto.strip() or len(texto) > 8000:
            raise ValueError("texto vazio ou maior que 8000 caracteres")
        chave = (sessao, pedido)
        digest = hashlib.sha256(texto.encode()).hexdigest()
        with self.trava:
            anterior = self.db.execute("SELECT hash,estado,resposta,metadados FROM pedidos WHERE sessao=? AND id=?", chave).fetchone()
            if anterior:
                if anterior[0] != digest:
                    raise ValueError("o mesmo pedido não pode mudar de conteúdo")
                metadados = json.loads(anterior[3]) if anterior[3] else {}
                return {"ok": anterior[1] == "respondida", "pedido_id": pedido, "estado": anterior[1], "repetido": True,
                        "modelos": metadados.get("modelos", []),
                        "resposta": anterior[2] or "Esse pedido já começou. Confira seu estado no painel antes de repetir; não o executei novamente."}
            if chave in self.cancelados or self.db.execute("SELECT 1 FROM cancelamentos WHERE sessao=? AND id=?", chave).fetchone():
                return {"ok": True, "estado": "cancelada", "resposta": "Pedido cancelado antes de executar."}
            # Voice, HUD and chat acquire exactly the same execution gate.
            if not self.rt.conversa._pedido_lock.acquire(blocking=False):
                return {"ok": False, "estado": "ocupado", "resposta": "Estou atendendo outro pedido. Aguarde ou interrompa a atividade atual; este pedido não foi executado."}
            try:
                self.db.execute("INSERT INTO pedidos (sessao,id,hash,estado,resposta,em) VALUES (?,?,?,?,?,?)", (*chave, digest, "em_execucao", None, time.time()))
                self.db.commit()  # durable claim before any side effect
            except sqlite3.Error:
                self.db.rollback()
                self.rt.conversa._pedido_lock.release()
                raise
            self.rt.conversa._cancelado.clear()
            self.ativo = chave
        conversa, comandos = self.rt.conversa, self.rt.comandos
        historico_anterior = conversa._historico
        modelos_anteriores = getattr(conversa, "_modelos_pedido", [])
        conversa._modelos_pedido = []
        modelos = []
        refs_anteriores = {k: copy.deepcopy(getattr(comandos, k, v)) for k, v in REFERENCIAS.items()}
        estado, resposta = "respondida", None
        try:
            with self.trava:
                row = self.db.execute("SELECT historico FROM sessoes WHERE id=?", (sessao,)).fetchone()
            conversa._historico = json.loads(row[0]) if row else []
            for k, v in self.referencias.get(sessao, REFERENCIAS).items():
                setattr(comandos, k, copy.deepcopy(v))
            self.rt.estado.atualizar("pedido", sessao_id=sessao, pedido_id=pedido, estado="em_execucao", em=time.time())
            if chave not in self.cancelados:
                atender = getattr(conversa, "_atender_serial", conversa.atender)
                resposta = atender(texto, falar=bool(corpo.get("falar", False)))
            if chave in self.cancelados or conversa._cancelado.is_set():
                estado = "cancelada"
                resposta = "Pedido interrompido. Ações já executadas continuam registradas no painel."
            # Deterministic commands must also be part of this session's history.
            if resposta and not (conversa._historico and conversa._historico[-1].get("content") == resposta):
                conversa._historico.extend([{"role": "user", "content": texto}, {"role": "assistant", "content": resposta}])
        except Exception as exc:
            estado = "incerto"
            resposta = "O pedido falhou. Confira os resultados no painel antes de repetir uma ação."
            self.rt.estado.registrar("pedido", f"{pedido}: {type(exc).__name__}", "erro")
        finally:
            with self.trava:
                try:
                    modelos = list(dict.fromkeys(conversa._modelos_pedido))
                    self.referencias[sessao] = {k: copy.deepcopy(getattr(comandos, k, v)) for k, v in REFERENCIAS.items()}
                    self.db.execute("INSERT OR REPLACE INTO sessoes VALUES (?,?)", (sessao, json.dumps(conversa._historico[-12:], ensure_ascii=False)))
                    self.db.execute("UPDATE pedidos SET estado=?,resposta=?,em=?,metadados=? WHERE sessao=? AND id=?", (estado, resposta, time.time(), json.dumps({"modelos": modelos}), *chave))
                    self.db.commit()
                except sqlite3.Error:
                    self.db.rollback()
                    estado = "incerto"
                    resposta = "Não consegui salvar o recibo. Confira o efeito da operação antes de repetir."
                finally:
                    conversa._historico = historico_anterior
                    conversa._modelos_pedido = modelos_anteriores
                    for k, v in refs_anteriores.items():
                        setattr(comandos, k, v)
                    self.ativo = None
                    conversa._pedido_lock.release()
            self.rt.estado.atualizar("pedido", sessao_id=sessao, pedido_id=pedido, estado=estado, em=time.time())
        return {"ok": estado == "respondida", "estado": estado, "pedido_id": pedido, "resposta": resposta, "modelos": modelos}
