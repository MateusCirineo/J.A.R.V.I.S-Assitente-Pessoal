"""O que está selecionado AGORA -- uma autoridade só, para todas as entradas.

"Aumente isso" só faz sentido se o Jarvis e a tela concordarem sobre o que é
"isso". Antes cada tela guardava a sua ideia: o mouse marcava uma peça na mesa
holográfica e a voz não sabia de nada.

Aqui fica o registro único: o que está selecionado, quem selecionou (mouse,
teclado, voz ou gesto) e quando. Quem seleciona muda; o alvo é o mesmo (§10, T18).

Gesto só fica disponível quando o controlador S7 real estiver ativo e calibrado.
A função global entradas() descreve a base sem controlador ligado.

Gesto no ar e toque na superfície são coisas diferentes. Nenhuma das duas é
chamada pelo nome da outra em lugar nenhum deste arquivo.
"""

from __future__ import annotations

import threading
import time
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

# de onde pode vir uma seleção
ENTRADAS = ("mouse", "teclado", "voz", "gesto", "toque")
# o que dá para selecionar
TIPOS = ("peca", "componente", "objeto", "noticia", "documento", "trecho", "regiao", "tarefa")

MOTIVO_GESTO = ("rastreamento MediaPipe desativado ou sem calibração nesta sessão; "
                "use o mouse, o teclado ou a voz")
MOTIVO_TOQUE = "sem tela sensível ao toque nesta máquina"

# uma seleção velha não vale como "isso": depois disto, o Jarvis pergunta
VALIDADE_S = 300.0


@dataclass
class Alvo:
    tipo: str
    id: str
    rotulo: str = ""
    por: str = "voz"                 # qual entrada selecionou
    em: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)

    def valido(self, agora: float | None = None, validade: float = VALIDADE_S) -> bool:
        return (agora or time.time()) - self.em <= validade

    def falado(self) -> str:
        nome = self.rotulo or self.id
        return f"{nome}" if not self.tipo else f"{nome} ({self.tipo})"


def entradas() -> dict[str, str]:
    """Estado REAL de cada forma de selecionar. Nada aqui é decorativo."""
    return {
        "mouse": "disponivel",
        "teclado": "disponivel",
        "voz": "disponivel",
        "gesto": f"indisponivel: {MOTIVO_GESTO}",
        "toque": f"indisponivel: {MOTIVO_TOQUE}",
    }


def disponivel(entrada: str) -> bool:
    return entradas().get(entrada, "indisponivel").startswith("disponivel")


class Selecionador:
    """Guarda o alvo corrente e avisa quem quiser saber (a tela, por exemplo)."""

    def __init__(self, publicar: Callable[[dict[str, Any]], None] | None = None) -> None:
        self._trava = threading.RLock()
        self._alvo: Alvo | None = None
        self._historico: list[Alvo] = []
        self._publicar = publicar
        self.gesto_disponivel: Callable[[], bool] = lambda: False

    def selecionar(self, tipo: str, id: str, rotulo: str = "", por: str = "voz",
                   **extra: Any) -> Alvo:
        if tipo not in TIPOS or not str(id).strip() or len(str(id)) > 160:
            raise ValueError("tipo ou identificador de seleção inválido")
        if "caixa" in extra:
            caixa = extra["caixa"]
            if isinstance(caixa, dict):
                caixa = [caixa.get(k) for k in ("x", "y", "w", "h")]
            if not isinstance(caixa, (tuple, list)) or len(caixa) != 4 or not all(
                    isinstance(v, (int, float)) and not isinstance(v, bool)
                    and math.isfinite(v) and 0 <= v <= 1 for v in caixa):
                raise ValueError("caixa de seleção inválida")
            if caixa[2] <= 0 or caixa[3] <= 0 or caixa[0] + caixa[2] > 1 or caixa[1] + caixa[3] > 1:
                raise ValueError("caixa de seleção fora da imagem")
            extra["caixa"] = list(caixa)
        if "fonte" in extra and extra["fonte"] not in ("camera", "tela", "mesa"):
            raise ValueError("fonte de seleção inválida")
        if por not in ENTRADAS:
            raise ValueError(f"entrada desconhecida: {por}")
        if not (self.gesto_disponivel() if por == "gesto" else disponivel(por)):
            raise RuntimeError(entradas()[por])          # gesto sem rastreador: erro honesto
        alvo = Alvo(tipo=tipo, id=str(id), rotulo=rotulo, por=por, extra=dict(extra))
        with self._trava:
            self._alvo = alvo
            self._historico.append(alvo)
            del self._historico[:-20]
        self._avisar()
        return alvo

    def limpar(self) -> None:
        with self._trava:
            self._alvo = None
        self._avisar()

    def atual(self, validade: float = VALIDADE_S) -> Alvo | None:
        with self._trava:
            alvo = self._alvo
        return alvo if alvo is not None and alvo.valido(validade=validade) else None

    def ultimo_do_tipo(self, tipo: str) -> Alvo | None:
        with self._trava:
            for a in reversed(self._historico):
                if a.tipo == tipo:
                    return a
        return None

    def historico(self) -> list[Alvo]:
        with self._trava:
            return list(self._historico)

    def cartao(self) -> dict[str, Any]:
        alvo = self.atual()
        capacidades = entradas()
        if self.gesto_disponivel():
            capacidades["gesto"] = "disponivel: gesto no ar, sessão calibrada"
        return {"alvo": asdict(alvo) if alvo else None,
                "entradas": capacidades,
                "em": time.time()}

    def _avisar(self) -> None:
        if self._publicar is not None:
            try:
                self._publicar(self.cartao())
            except Exception:  # noqa: BLE001 - avisar a tela nunca derruba a selecao
                pass


def falar_selecao(alvo: Alvo | None, tratamento: str = "Senhor") -> str:
    if alvo is None:
        return f"Nada selecionado agora, {tratamento}."
    origem = {"mouse": "pelo mouse", "teclado": "pelo teclado", "voz": "por voz",
              "gesto": "por gesto", "toque": "por toque"}.get(alvo.por, alvo.por)
    return f"Selecionado {origem}: {alvo.falado()}, {tratamento}."
