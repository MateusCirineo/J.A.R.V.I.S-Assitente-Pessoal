"""Ponte: WebSocket /v1/agents/events do servidor -> estado do runtime.

Contrato observado na instalacao (nao suposto):
  - cada pedido gera DOIS inference_start e DOIS inference_end (duas camadas
    do motor). Por isso a atividade e contada por profundidade, nao por evento.
  - so um dos inference_end traz latency/ttft/throughput; o outro traz o texto
    da resposta. O texto nunca e repassado as telas.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

from . import SERVIDOR_OPENJARVIS
from .estado import Estado

URL_WS = SERVIDOR_OPENJARVIS.replace("http://", "ws://") + "/v1/agents/events"
LIMITE_SEM_EVENTO_S = 600      # zera contagem presa (servidor reiniciado no meio)


def extrair_metricas(dados: dict) -> dict | None:
    """Metricas do INFERENCE_END que as tem. None para o outro evento do par."""
    if "latency" not in dados:
        return None
    uso = dados.get("usage") or {}

    def pos(v):
        # energia/potencia chegam 0.0 quando nao ha medidor (iGPU Intel aqui):
        # 0 nesse campo significa "nao medido", nao "consumo zero".
        return v if isinstance(v, (int, float)) and v > 0 else None

    return {
        "modelo": dados.get("model"),
        "latencia_s": round(float(dados["latency"]), 2),
        "ttft_s": round(float(dados["ttft"]), 2) if dados.get("ttft") is not None else None,
        "tokens_saida": uso.get("completion_tokens"),
        "tokens_entrada": uso.get("prompt_tokens"),
        "vazao_tok_s": (round(float(dados["throughput_tok_per_sec"]), 2)
                        if dados.get("throughput_tok_per_sec") is not None else None),
        "energia_j": pos(dados.get("energy_joules")),
        "potencia_w": pos(dados.get("power_watts")),
        "fonte": "evento INFERENCE_END do servidor",
        "em": time.time(),
    }


class Ponte(threading.Thread):
    def __init__(self, estado: Estado, medidor=None) -> None:
        super().__init__(name="ponte-eventos", daemon=True)
        self._estado = estado
        # medidor() -> joules acumulados da CPU (leitor de sensores) ou None
        self._medidor = medidor or (lambda: None)
        self._energia_ini: tuple[float, float] | None = None
        self._profundidade = 0
        self._ultimo_evento = 0.0
        self._conectada = False
        self._encerrar = threading.Event()

    @property
    def conectada(self) -> bool:
        return self._conectada

    def encerrar(self) -> None:
        self._encerrar.set()

    def run(self) -> None:
        asyncio.run(self._laco())

    def processar(self, evento: dict) -> None:
        tipo, dados = evento.get("type"), evento.get("data") or {}
        self._ultimo_evento = time.time()
        if tipo == "inference_start":
            self._profundidade += 1
            campos = {"ativas_servidor": self._profundidade}
            if self._profundidade == 1:
                campos.update(modelo=dados.get("model"), desde=time.time())
                j = self._medidor()
                self._energia_ini = (time.time(), j) if j is not None else None
            self._estado.atualizar("inferencia", **campos)
        elif tipo == "inference_end":
            self._profundidade = max(0, self._profundidade - 1)
            campos: dict = {"ativas_servidor": self._profundidade}
            metricas = extrair_metricas(dados)
            if metricas:
                campos["ultima"] = metricas
                self._estado.registrar(
                    "inferencia",
                    f"{metricas['modelo']}: {metricas['latencia_s']}s, "
                    f"{metricas['tokens_saida']} tokens")
            if self._profundidade == 0 and self._energia_ini:
                # energia do pacote da CPU durante a resposta (inclui o consumo de base)
                t0, j0 = self._energia_ini
                j1 = self._medidor()
                self._energia_ini = None
                if j1 is not None and j1 >= j0:
                    campos["energia_ultima"] = {"joules": round(j1 - j0, 1),
                                                "wh": round((j1 - j0) / 3600, 4),
                                                "segundos": round(time.time() - t0, 1),
                                                "fonte": "CPU Package (RAPL), medido", "em": time.time()}
            self._estado.atualizar("inferencia", **campos)

    async def _laco(self) -> None:
        import websockets

        espera = 1.0
        while not self._encerrar.is_set():
            try:
                async with websockets.connect(URL_WS, open_timeout=5,
                                              ping_interval=20) as ws:
                    self._conectada = True
                    espera = 1.0
                    self._estado.atualizar("conexao", eventos={
                        "estado": "conectado", "detalhe": URL_WS, "em": time.time()})
                    while not self._encerrar.is_set():
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            self._vigiar()
                            continue
                        try:
                            self.processar(json.loads(msg))
                        except (ValueError, TypeError):
                            continue
            except Exception as e:  # noqa: BLE001 - reconecta sempre
                if self._conectada or espera == 1.0:
                    self._estado.atualizar("conexao", eventos={
                        "estado": "desconectado", "detalhe": str(e)[:120],
                        "em": time.time()})
                self._conectada = False
                if self._profundidade:
                    self._profundidade = 0
                    self._estado.atualizar("inferencia", ativas_servidor=0)
            await asyncio.sleep(espera)
            espera = min(espera * 2, 15.0)

    def _vigiar(self) -> None:
        if self._profundidade and time.time() - self._ultimo_evento > LIMITE_SEM_EVENTO_S:
            self._profundidade = 0
            self._estado.atualizar("inferencia", ativas_servidor=0)
            self._estado.registrar("inferencia", "contagem zerada: sem INFERENCE_END", "aviso")
