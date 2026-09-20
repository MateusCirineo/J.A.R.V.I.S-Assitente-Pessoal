"""Midia tocando no Windows e volume do sistema.

Midia: Global System Media Transport Controls (WinRT), a mesma API do painel
de midia do Windows -- pega Spotify, navegador, player do Windows, etc.
Volume: Core Audio pelo pycaw.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

_STATUS = {0: "fechado", 1: "abrindo", 2: "parado", 3: "parado", 4: "tocando", 5: "pausado"}


def _app_amigavel(app_id: str) -> str:
    base = app_id.split("!")[-1] if "!" in app_id else app_id
    base = base.removesuffix(".exe")
    return {"msedge": "Edge", "chrome": "Chrome", "firefox": "Firefox"}.get(base.lower(), base)


async def _sessao():
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as Gerenciador,
    )
    return (await Gerenciador.request_async()).get_current_session()


async def _ler() -> dict[str, Any]:
    s = await _sessao()
    if s is None:
        return {"status": "medido", "tocando": False, "titulo": None}
    p = await s.try_get_media_properties_async()
    info = s.get_playback_info()
    linha = s.get_timeline_properties()
    cod = int(info.playback_status)
    return {
        "status": "medido", "fonte": "Windows (GSMTC)",
        "app": _app_amigavel(s.source_app_user_model_id or ""),
        "titulo": p.title or None, "artista": p.artist or None, "album": p.album_title or None,
        "situacao": _STATUS.get(cod, "?"), "tocando": cod == 4,
        "posicao_s": round(linha.position.total_seconds()) if linha else None,
        "duracao_s": round(linha.end_time.total_seconds()) if linha else None,
        "pode_avancar": bool(info.controls.is_next_enabled),
        "pode_voltar": bool(info.controls.is_previous_enabled),
    }


# A API de midia do Windows pode travar sem nunca responder (ja aconteceu com
# uma aba de streaming aberta). Por isso um fio proprio le a cada 2 s, com limite
# por leitura, e quem pergunta so pega o ultimo valor: a telemetria (clima,
# sistema, noticias...) nunca fica esperando por ela.
LIMITE_S = 5.0
VELHO_S = 15.0
_cache: dict[str, Any] = {"valor": {"status": "aguardando"}, "em": 0.0}
_leitor: threading.Thread | None = None
_trava = threading.Lock()


def _ler_uma_vez() -> dict[str, Any]:
    try:
        return asyncio.run(asyncio.wait_for(_ler(), LIMITE_S))
    except asyncio.TimeoutError:
        return {"status": "erro", "detalhe": "o Windows demorou para responder sobre a mídia"}
    except Exception as e:  # noqa: BLE001
        return {"status": "erro", "detalhe": str(e)[:120] or type(e).__name__}


def _laco() -> None:
    while True:
        valor = _ler_uma_vez()
        if not isinstance(valor, dict):
            valor = {"status": "erro", "detalhe": "resposta inesperada do Windows"}
        _cache.update(valor=valor, em=time.time())
        time.sleep(2.0)


def estado_midia() -> dict[str, Any]:
    global _leitor
    with _trava:
        primeira = _leitor is None
        if _leitor is None or not _leitor.is_alive():
            _leitor = threading.Thread(target=_laco, name="midia-windows", daemon=True)
            _leitor.start()
    if primeira:                                            # so a primeira chamada espera um pouco
        fim = time.time() + 2.0
        while _cache["em"] == 0.0 and time.time() < fim:
            time.sleep(0.05)
    if _cache["em"] == 0.0 or time.time() - _cache["em"] > VELHO_S:
        return {"status": "erro", "detalhe": "sem resposta do Windows sobre a mídia"}
    return dict(_cache["valor"])


async def _controlar(acao: str) -> bool:
    s = await _sessao()
    if s is None:
        return False
    metodo = {"tocar_pausar": s.try_toggle_play_pause_async, "proxima": s.try_skip_next_async,
              "anterior": s.try_skip_previous_async}[acao]
    return bool(await metodo())


def controlar(acao: str) -> bool:
    if acao not in ("tocar_pausar", "proxima", "anterior"):
        raise ValueError("acao deve ser tocar_pausar, proxima ou anterior")
    try:
        return asyncio.run(asyncio.wait_for(_controlar(acao), LIMITE_S))
    except asyncio.TimeoutError:
        return False


# ---------------------------------------------------------------------------
# volume do sistema
# ---------------------------------------------------------------------------

def _endpoint():
    import comtypes
    from pycaw.pycaw import AudioUtilities
    comtypes.CoInitialize()          # COM por thread; chamada repetida e inofensiva
    return AudioUtilities.GetSpeakers().EndpointVolume


def volume_sistema() -> dict[str, Any]:
    try:
        ep = _endpoint()
        return {"status": "medido", "fonte": "Core Audio",
                "volume": round(ep.GetMasterVolumeLevelScalar(), 3), "mudo": bool(ep.GetMute())}
    except Exception as e:  # noqa: BLE001
        return {"status": "erro", "detalhe": str(e)[:120]}


def definir_volume(volume: float | None = None, mudo: bool | None = None) -> dict[str, Any]:
    ep = _endpoint()
    if volume is not None:
        ep.SetMasterVolumeLevelScalar(float(min(max(volume, 0.0), 1.0)), None)
    if mudo is not None:
        ep.SetMute(int(bool(mudo)), None)
    return volume_sistema()
