"""Falas proativas: o Jarvis toma a palavra sozinho, como no filme.

"Senhor, sua reuniao comeca em 10 minutos." / "Bem-vindo de volta, Senhor."
Espera a vez: nunca fala por cima de voce nem de outra resposta. No horario
de silencio (preferencia) so fala o que voce mesmo pediu (lembretes, timers).

Tres modos (preferencia "modo_proativo"), por categoria de fala:
- sob_demanda: so o que voce pediu (lembretes, timers, seus monitores);
- assistido (padrao): + compromissos, boas-vindas/resumo do dia, avisos criticos;
- proativo: + observacoes (e-mail novo, alguem na sala).
"""

from __future__ import annotations

import queue
import itertools
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable


PERMITIDAS = {
    "sob_demanda": {"pedido"},
    "assistido": {"pedido", "agenda", "presenca", "aviso"},
    "proativo": {"pedido", "agenda", "presenca", "aviso", "observacao"},
}


def modo_de(prefs: dict[str, Any]) -> str:
    if prefs.get("falas_proativas") is False:          # chave antiga, desligada = so o que foi pedido
        return "sob_demanda"
    m = prefs.get("modo_proativo")
    return m if m in PERMITIDAS else "assistido"


def em_silencio(agora: datetime, inicio: int, fim: int) -> bool:
    """Horario de silencio [inicio, fim) em horas; atravessa a meia-noite."""
    if inicio == fim:
        return False
    h = agora.hour
    return inicio <= h < fim if inicio < fim else (h >= inicio or h < fim)


@dataclass
class Aviso:
    texto: str
    pedido: bool
    categoria: str
    vence: float
    chave: str
    geracao: int
    prioridade: str


class Anunciador(threading.Thread):
    def __init__(self, falar: Callable[[str], Any], ocupado: Callable[[], bool],
                 prefs: Any, registrar: Callable[[str], None] | None = None,
                 mostrar: Callable[[str], None] | None = None) -> None:
        super().__init__(name="anunciador", daemon=True)
        self._falar = falar
        self._ocupado = ocupado
        self._prefs = prefs
        self._registrar = registrar or (lambda t: None)
        self._mostrar = mostrar or (lambda t: None)
        self._fila: queue.PriorityQueue[tuple[int, int, Aviso]] = queue.PriorityQueue(maxsize=20)
        self._encerrar = threading.Event()
        self._trava = threading.RLock()
        self._ordem = itertools.count()
        self._geracao = 0
        self._pendentes: set[str] = set()
        self._recentes: dict[str, float] = {}
        self._ultima_espontanea = float("-inf")
        self._retirado: Aviso | None = None

    @staticmethod
    def _somente_painel(aviso: Aviso, p: dict) -> bool:
        if p.get("voz_muda") or p.get("avisos_canal") == "painel":
            return True
        return not aviso.pedido and (bool(p.get("modo_foco")) or em_silencio(
            datetime.now(), int(p.get("silencio_inicio", 22)), int(p.get("silencio_fim", 7))))

    def anunciar(self, texto: str, pedido_pelo_usuario: bool = False, validade_s: float = 300,
                 categoria: str | None = None, chave: str | None = None,
                 prioridade: str = "normal") -> bool:
        """Enfileira uma fala. `pedido_pelo_usuario` (lembrete, timer, monitor) fura o silencio."""
        p = self._prefs.ler()
        categoria = "pedido" if pedido_pelo_usuario else (categoria or "observacao")
        if categoria not in PERMITIDAS[modo_de(p)]:
            return False
        if not isinstance(texto, str) or not texto.strip() or validade_s <= 0:
            return False
        # Dois timers distintos podem ter o mesmo texto. Deduplique pedidos
        # explicitos apenas quando o produtor fornece a chave da ocorrencia.
        identidade = chave or (f"pedido-{next(self._ordem)}" if pedido_pelo_usuario else ' '.join(texto.casefold().split()))
        chave = f"{categoria}:{identidade}"
        agora = time.time()
        with self._trava:
            janela = float(p.get("avisos_deduplicacao_s", 300))
            self._recentes = {c: em for c, em in self._recentes.items() if agora - em < janela}
            if chave in self._pendentes or chave in self._recentes:
                return False
            aviso = Aviso(texto, pedido_pelo_usuario, categoria, agora + validade_s,
                          chave, self._geracao, prioridade)
            try:
                ordem = 0 if pedido_pelo_usuario else {"alta": 1, "normal": 2, "baixa": 3}.get(prioridade, 2)
                self._fila.put_nowait((ordem, next(self._ordem), aviso))
                self._pendentes.add(chave)
                return True
            except queue.Full:
                return False

    def limpar(self) -> int:
        """Descarta as falas na fila ("pare"). Devolve quantas."""
        with self._trava:
            self._geracao += 1
            n = int(self._retirado is not None)
            self._retirado = None
            self._pendentes.clear()
            while True:
                try:
                    self._fila.get_nowait()
                    n += 1
                except queue.Empty:
                    return n

    def encerrar(self) -> None:
        self._encerrar.set()
        self.limpar()

    def processar_proximo(self, espera: float = 0.0) -> bool:
        """Uma entrega real. Se a politica mudar durante a espera, revalida antes de falar."""
        try:
            _, _, aviso = self._fila.get(timeout=espera)
        except queue.Empty:
            return False
        with self._trava:
            self._retirado = aviso
        try:
            while self._ocupado() and time.time() < aviso.vence and not self._encerrar.is_set():
                if aviso.geracao != self._geracao:
                    return False
                if self._somente_painel(aviso, self._prefs.ler()):
                    break
                self._encerrar.wait(0.1)
            with self._trava:
                if aviso.geracao != self._geracao or time.time() >= aviso.vence or self._encerrar.is_set():
                    return False
                p = self._prefs.ler()
                if aviso.categoria not in PERMITIDAS[modo_de(p)]:
                    return False
                somente_painel = self._somente_painel(aviso, p)
                if not aviso.pedido and aviso.prioridade != "alta":
                    somente_painel |= time.time() - self._ultima_espontanea < float(p.get("avisos_intervalo_s", 30))
                self._recentes[aviso.chave] = time.time()
                if not somente_painel and not aviso.pedido:
                    self._ultima_espontanea = time.time()
            self._registrar(aviso.texto)
            if somente_painel:
                self._mostrar(aviso.texto)
            elif aviso.geracao == self._geracao and not self._encerrar.is_set():
                self._falar(aviso.texto)
            return True
        except Exception:  # noqa: BLE001 - uma saida com falha nao para outros avisos
            return False
        finally:
            with self._trava:
                if self._retirado is aviso:
                    self._retirado = None
                if aviso.geracao == self._geracao:
                    self._pendentes.discard(aviso.chave)

    def run(self) -> None:
        while not self._encerrar.is_set():
            self.processar_proximo(espera=0.5)
