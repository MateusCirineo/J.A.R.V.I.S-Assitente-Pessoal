"""Quando o Senhor corrige, fica corrigido -- sem treinar nada.

§17 do prompt mestre separa quatro coisas que costumam ser confundidas: guardar
uma preferência, indexar um manual, ajustar um prompt e treinar pesos. Aqui é a
primeira: o Senhor diz "quando eu falar X, faça Y" e isso passa a valer.

Como funciona, em uma linha: vira uma REGRA de apelido, guardada em JSON,
conferida contra os comandos que já existem, inspecionável e apagável.

O que este arquivo **não** faz, de propósito:

- não treina modelo nem mexe em pesos (isso é outro projeto, §17-B);
- não cria comando novo: o destino tem de ser um comando que já existe, senão a
  correção é recusada -- é o que impede um apelido de virar permissão nova;
- não guarda nada sem o Senhor mandar, e tudo aparece em "quais correções você
  guardou?".
"""

from __future__ import annotations

import json
import os
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
ARQ = HOME / "hud-correcoes.json"

TIPOS = ("apelido", "pronuncia", "fato")


def _sem_chamado(texto: str) -> str:
    """Tira o "Jarvis," do comeco, como o resto do sistema faz."""
    import re
    return re.sub(r"^\W*(?:jarvis|jarbas|jarvas|jervis)\b\W*", "", (texto or "").strip(), flags=re.I)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split()).strip(" .,!?")


@dataclass
class Correcao:
    id: str
    tipo: str                      # apelido | pronuncia | fato
    quando_eu_disser: str          # a frase do Senhor
    faca: str                      # a frase que já funciona (ou o texto certo)
    comando: str = ""              # comando ao qual "faca" resolve (conferido na hora de guardar)
    origem: str = "voz"
    em: float = field(default_factory=time.time)
    usos: int = 0


class Correcoes:
    """Apelidos e correções revisadas pelo Senhor. Um JSON, local e apagável."""

    def __init__(self, arquivo: Path | str | None = None) -> None:
        self._arq = Path(arquivo) if arquivo else ARQ
        self._trava = threading.RLock()
        self._itens: dict[str, Correcao] = {}
        self._carregar()

    def _carregar(self) -> None:
        try:
            d = json.loads(self._arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for bruto in d.get("correcoes", []):
            try:
                self._itens[bruto["id"]] = Correcao(**bruto)
            except (TypeError, KeyError):
                continue

    def salvar(self) -> None:
        with self._trava:
            dados = {"correcoes": [asdict(c) for c in self._itens.values()], "em": time.time()}
            self._arq.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._arq.with_suffix(".tmp")
            tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self._arq)

    def _persistir(self, anteriores: dict[str, Correcao]) -> None:
        try:
            self.salvar()
        except OSError as exc:
            self._itens = anteriores
            raise ValueError("não consegui salvar a correção no disco; nenhuma mudança foi confirmada") from exc

    # ---- guardar --------------------------------------------------------
    def registrar(self, quando_eu_disser: str, faca: str, *, tipo: str = "apelido",
                  interpretar: Callable[[str], tuple[str, dict] | None] | None = None,
                  origem: str = "voz") -> Correcao:
        """Guarda a correção. Para apelido, `faca` PRECISA resolver num comando real."""
        if tipo not in TIPOS:
            raise ValueError(f"tipo desconhecido: {tipo}")
        gatilho, destino = _norm(quando_eu_disser), faca.strip()
        if len(gatilho) < 3 or len(destino) < 2:
            raise ValueError("preciso da frase e do que fazer")
        from .memoria import parece_segredo
        if parece_segredo(gatilho) or parece_segredo(destino):
            raise ValueError("não guardo credenciais em correções")
        comando = ""
        if tipo == "apelido":
            if interpretar is None:
                raise ValueError("sem como conferir o comando")
            achado = interpretar(destino)
            if not achado:
                raise ValueError(f'"{destino}" não é um comando que eu conheça')
            comando = achado[0]
            if _norm(destino) == gatilho:
                raise ValueError("a frase e o comando são iguais")
        with self._trava:
            anteriores = dict(self._itens)
            cid = f"c{int(time.time() * 1000) % 10_000_000}"
            while cid in self._itens:
                cid += "a"
            c = Correcao(id=cid, tipo=tipo, quando_eu_disser=gatilho, faca=destino,
                         comando=comando, origem=origem)
            # uma frase só tem uma correção: a nova substitui a antiga
            for velho in [x.id for x in self._itens.values()
                          if x.tipo == tipo and x.quando_eu_disser == gatilho]:
                del self._itens[velho]
            self._itens[cid] = c
            self._persistir(anteriores)
            from .memoria import invalidar_fonte
            for velho in anteriores.values():
                if velho.id not in self._itens:
                    invalidar_fonte(self._arq.parent, "correcao", velho.id)
        return c

    # ---- usar -----------------------------------------------------------
    def aplicar(self, frase: str) -> Correcao | None:
        """A frase do Senhor casa com algum apelido? Devolve a correção (sem executar).

        Exige a frase INTEIRA (tirando o "Jarvis"): um apelido "modo oficina" não
        pode sequestrar "esqueça a correção modo oficina".
        """
        alvo = _norm(_sem_chamado(frase))
        if not alvo:
            return None
        with self._trava:
            for c in self._itens.values():
                if c.tipo == "apelido" and alvo == c.quando_eu_disser:
                    c.usos += 1
                    return c
        return None

    def pronuncias(self) -> dict[str, str]:
        """Trocas de pronúncia (o que falar no lugar do que está escrito)."""
        return {c.quando_eu_disser: c.faca for c in self._itens.values() if c.tipo == "pronuncia"}

    def listar(self, tipo: str | None = None) -> list[Correcao]:
        itens = [c for c in self._itens.values() if tipo is None or c.tipo == tipo]
        return sorted(itens, key=lambda c: -c.em)

    def esquecer(self, cid_ou_frase: str) -> bool:
        alvo = _norm(cid_ou_frase)
        if not alvo:
            return False
        with self._trava:
            exatos = [c for c in self._itens.values() if c.id == cid_ou_frase or c.quando_eu_disser == alvo]
            candidatos = exatos or [c for c in self._itens.values() if alvo in c.quando_eu_disser]
            if len(candidatos) > 1:
                raise ValueError("há mais de uma correção correspondente; indique a frase inteira")
            if candidatos:
                c = candidatos[0]
                from .memoria import invalidar_fonte
                invalidar_fonte(self._arq.parent, "correcao", c.id, excluir=True)
                anteriores = dict(self._itens)
                del self._itens[c.id]
                self._persistir(anteriores)
                return True
        return False

    def limpar(self) -> int:
        with self._trava:
            n = len(self._itens)
            from .memoria import invalidar_fonte
            for c in self._itens.values():
                invalidar_fonte(self._arq.parent, "correcao", c.id, excluir=True)
            anteriores = dict(self._itens)
            self._itens.clear()
            self._persistir(anteriores)
        return n


# ---- como o Jarvis fala disso -------------------------------------------
def falar_registro(c: Correcao, tratamento: str = "Senhor") -> str:
    if c.tipo == "apelido":
        return (f"Anotado, {tratamento}: quando o senhor disser \"{c.quando_eu_disser}\", "
                f"eu faço \"{c.faca}\". É uma regra minha, não um modelo treinado: "
                f"dá para ver e apagar quando quiser.")
    if c.tipo == "pronuncia":
        return f"Certo: passo a falar \"{c.faca}\" no lugar de \"{c.quando_eu_disser}\", {tratamento}."
    return f"Corrigido, {tratamento}: {c.faca}."


def falar_lista(itens: list[Correcao], tratamento: str = "Senhor") -> str:
    if not itens:
        return (f"Não guardei nenhuma correção, {tratamento}. Diga, por exemplo: "
                f"quando eu disser modo oficina, abra o VS Code.")
    linhas = [f'"{c.quando_eu_disser}" vira "{c.faca}"'
              + (f" (usei {c.usos} vez{'es' if c.usos > 1 else ''})" if c.usos else "")
              for c in itens[:6]]
    n = len(itens)
    return (f"Tenho {n} correç{'ões' if n > 1 else 'ão'} sua{'s' if n > 1 else ''}, "
            f"{tratamento}: " + "; ".join(linhas) + ".")
