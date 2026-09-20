"""Exemplos revisados e avaliação local, sem treinamento ou coleta de conversas.

Somente os campos enviados explicitamente entram na coleção opt-in. Avaliação
usa casos separados e resultados conferidos; não executa candidatos nem os
promove, altera políticas ou transforma uma nota em superioridade geral.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import unicodedata
import uuid
from pathlib import Path


def pasta_dados() -> Path:
    return Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))


def texto_revisado(texto: str, campo: str, limite: int = 4000) -> str:
    if not isinstance(texto, str) or not texto.strip() or len(texto) > limite:
        raise ValueError(f"{campo} deve ser texto entre 1 e {limite} caracteres")
    # Não conservar nem fragmentos de uma linha que contenha credencial.
    from .memoria import parece_segredo
    linhas = []
    for linha in texto.splitlines():
        if (parece_segredo(linha) or re.search(
                r"(?i)\b(?:bearer\s+\S+|sk-[a-z0-9_-]{12,}|gh[pousr]_[a-z0-9]{12,})|https?://[^/\s]+:[^/\s]+@", linha)):
            linhas.append("[SEGREDO REMOVIDO]")
        else:
            linhas.append(linha.strip())
    resultado = "\n".join(linhas).strip()
    if not resultado.replace("[SEGREDO REMOVIDO]", "").strip():
        raise ValueError(f"{campo} contém apenas informação secreta; forneça uma descrição sem credenciais")
    return resultado


def referencias(fontes) -> list[dict]:
    if not isinstance(fontes, (list, tuple)) or len(fontes) > 20:
        raise ValueError("informe até vinte referências explícitas")
    saida = []
    for f in fontes:
        if not isinstance(f, dict) or set(f) - {"tipo", "id", "versao"}:
            raise ValueError("referência deve conter tipo, id e versão opcional; não o documento inteiro")
        if f.get("tipo") not in {"documento", "episodio", "correcao", "fato", "resultado", "usuario"}:
            raise ValueError("tipo de referência desconhecido")
        ident = texto_revisado(f.get("id"), "identificador da fonte", 300)
        versao = f.get("versao", "")
        if not isinstance(versao, str) or len(versao) > 128:
            raise ValueError("versão da fonte inválida")
        saida.append({"tipo": f["tipo"], "id": ident, "versao": versao})
    return saida


class RegistroLocal:
    """Pequeno armazenamento transacional; leituras não ficam em cache entre instâncias."""

    def __init__(self, arquivo: Path | str):
        self.arquivo = Path(arquivo)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self._trava = threading.RLock()
        self.db = sqlite3.connect(str(self.arquivo), check_same_thread=False)
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute("CREATE TABLE IF NOT EXISTS registros (id TEXT PRIMARY KEY, tipo TEXT, dados TEXT)")
        self.db.commit()

    def _guardar(self, tipo: str, dado: dict) -> dict:
        with self._trava, self.db:
            self.db.execute("INSERT OR REPLACE INTO registros VALUES (?,?,?)",
                            (dado["id"], tipo, json.dumps(dado, ensure_ascii=False)))
        return json.loads(json.dumps(dado))

    def _listar(self, tipo: str) -> list[dict]:
        with self._trava:
            return [json.loads(r[0]) for r in self.db.execute(
                "SELECT dados FROM registros WHERE tipo=? ORDER BY rowid DESC", (tipo,))]

    def _excluir(self, ids: list[str]) -> int:
        with self._trava, self.db:
            return sum(self.db.execute("DELETE FROM registros WHERE id=?", (i,)).rowcount for i in ids)

    def fechar(self):
        self.db.close()


class Aprendizado(RegistroLocal):
    def __init__(self, arquivo: Path | str | None = None):
        super().__init__(arquivo or pasta_dados() / "hud-aprendizado.sqlite")

    def optar(self, ativo: bool) -> dict:
        if type(ativo) is not bool:
            raise ValueError("a opção de coleta precisa ser explícita")
        self._guardar("configuracao", {"id": "coleta", "ativa": ativo, "em": time.time()})
        return self.estado()

    def estado(self) -> dict:
        configuracao = self._listar("configuracao")
        exemplos = self.listar()
        return {"coleta_ativa": bool(configuracao and configuracao[0]["ativa"]),
                "adaptacao": sum(e["destino"] == "adaptacao" for e in exemplos),
                "avaliacao": sum(e["destino"] == "avaliacao" for e in exemplos),
                "treinamento": False, "coleta_automatica": False}

    def registrar(self, pedido: str, contexto: str, acao: str, resultado: str,
                  correcao: str, *, verificado: bool, aprovado: bool, sucesso: bool,
                  destino: str = "adaptacao", fontes=()) -> dict:
        if not self.estado()["coleta_ativa"]:
            raise ValueError("a coleta está desativada; ative-a explicitamente antes de guardar exemplos")
        if not all(v is True for v in (verificado, aprovado, sucesso)):
            raise ValueError("exemplo positivo exige resultado verificado, sucesso e correção aprovada")
        if destino not in {"adaptacao", "avaliacao"}:
            raise ValueError("destino deve ser adaptação ou avaliação")
        dado = {k: texto_revisado(v, k) for k, v in dict(
            pedido=pedido, contexto=contexto, acao=acao, resultado=resultado, correcao=correcao).items()}
        # Mesmo pedido/contexto não pode contaminar o conjunto reservado,
        # mesmo que ação ou resposta tenham sido editadas.
        chave = unicodedata.normalize("NFKD", dado["pedido"] + "\n" + dado["contexto"]).casefold()
        chave = "".join(c for c in chave if not unicodedata.combining(c))
        chave = re.sub(r"\s+", " ", chave)
        digest = hashlib.sha256(chave.encode()).hexdigest()
        with self._trava:
            for anterior in self.listar():
                if anterior["chave"] == digest:
                    raise ValueError("esse pedido/contexto já pertence a uma coleção; não duplique nem mova casos reservados")
            dado.update(id="e" + uuid.uuid4().hex[:16], chave=digest, destino=destino,
                        fontes=referencias(fontes), em=time.time(), verificado=True,
                        aprovado=True, sucesso=True)
            return self._guardar("exemplo", dado)

    def listar(self, destino: str | None = None) -> list[dict]:
        return [e for e in self._listar("exemplo") if destino is None or e["destino"] == destino]

    def esquecer(self, ident: str) -> bool:
        if not ident or not any(e["id"] == ident for e in self.listar()):
            return False
        # Relatórios derivados não conservam o caso removido nem suas notas.
        relatorios = [r["id"] for r in self._listar("comparacao") if ident in r["casos"]]
        return bool(self._excluir([ident, *relatorios]))

    def esquecer_fonte(self, tipo: str, ident: str) -> int:
        ids = [e["id"] for e in self.listar() if any(
            f["tipo"] == tipo and f["id"] == ident for f in e["fontes"])]
        for eid in ids:
            self.esquecer(eid)
        return len(ids)

    def comparar(self, referencia: str, candidato: str, resultados_referencia: dict,
                 resultados_candidato: dict, *, politica_referencia: str,
                 politica_candidato: str, reversao: str) -> dict:
        referencia = texto_revisado(referencia, "versão de referência", 300)
        candidato = texto_revisado(candidato, "versão candidata", 300)
        reversao = texto_revisado(reversao, "como restaurar a referência", 1000)
        if not isinstance(politica_referencia, str) or not politica_referencia or politica_referencia != politica_candidato:
            raise ValueError("a comparação não pode autorizar mudanças de política ou permissão")
        politica_referencia = texto_revisado(politica_referencia, "identificador da política", 300)
        if not isinstance(resultados_referencia, dict) or not isinstance(resultados_candidato, dict):
            raise ValueError("informe os resultados por identificador de caso")
        casos = set(resultados_referencia)
        if not casos or casos != set(resultados_candidato):
            raise ValueError("referência e candidato precisam dos mesmos casos verificados")
        reservados = {e["id"] for e in self.listar("avaliacao")}
        if not casos <= reservados:
            raise ValueError("a avaliação aceita apenas casos do conjunto reservado")

        def medir(resultados):
            certos, repeticoes, alertas = 0, 0, 0
            conferidos = {}
            for ident, resultado in resultados.items():
                if (not isinstance(resultado, dict) or set(resultado) - {
                        "correto", "verificado", "evidencia", "repeticoes", "alertas_inuteis"}
                        or resultado.get("verificado") is not True
                        or type(resultado.get("correto")) is not bool):
                    raise ValueError("cada resultado exige correto booleano, verificação e evidência")
                evidencia = texto_revisado(resultado.get("evidencia"), "evidência do resultado", 1000)
                valores = [resultado.get(k, 0) for k in ("repeticoes", "alertas_inuteis")]
                if any(type(v) is not int or not 0 <= v <= 1000 for v in valores):
                    raise ValueError("repetições e alertas devem ser contagens entre zero e mil")
                certos += resultado["correto"]
                repeticoes += valores[0]
                alertas += valores[1]
                conferidos[ident] = {"correto": resultado["correto"], "verificado": True,
                                    "evidencia": evidencia, "repeticoes": valores[0], "alertas_inuteis": valores[1]}
            return ({"corretos": certos, "total": len(casos), "repeticoes": repeticoes, "alertas_inuteis": alertas}, conferidos)

        (antes, evidencias_antes), (depois, evidencias_depois) = medir(resultados_referencia), medir(resultados_candidato)
        melhora = (depois["corretos"] >= antes["corretos"]
                   and depois["repeticoes"] <= antes["repeticoes"]
                   and depois["alertas_inuteis"] <= antes["alertas_inuteis"] and antes != depois)
        return self._guardar("comparacao", {"id": "a" + uuid.uuid4().hex[:16], "em": time.time(),
            "referencia": referencia, "candidato": candidato, "casos": sorted(casos),
            "antes": antes, "depois": depois, "melhora_nos_casos": melhora,
            "evidencias_antes": evidencias_antes, "evidencias_depois": evidencias_depois,
            "politica": politica_referencia, "reversao": reversao, "promovido": False,
            "limite": "Resultados submetidos e conferidos; não demonstra superioridade geral nem executa reversão."})

    def avaliacoes(self) -> list[dict]:
        return self._listar("comparacao")


def apagar_derivados(pasta: Path, tipo: str, ident: str) -> None:
    arquivo = Path(pasta) / "hud-aprendizado.sqlite"
    if arquivo.is_file():
        colecao = Aprendizado(arquivo)
        try:
            colecao.esquecer_fonte(tipo, ident)
        finally:
            colecao.fechar()
