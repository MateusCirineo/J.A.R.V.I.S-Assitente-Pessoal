"""Same-origin bridge to the paired HUD; its secret never reaches the chat."""
from __future__ import annotations

import ipaddress
import json
import re
import time
import uuid
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from openjarvis.core.paths import get_config_dir

_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


def local_client(request: Request) -> None:
    try:
        peer = ipaddress.ip_address(request.client.host)
        host = urlsplit(str(request.url)).hostname
        if not peer.is_loopback or host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError
    except (ValueError, AttributeError):
        raise HTTPException(403, "O controle do Jarvis está restrito ao cliente local.") from None
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Origem não autorizada para controlar o Jarvis.")


def identity(request: Request) -> tuple[str, str]:
    session = request.headers.get("x-jarvis-session", "")
    operation = request.headers.get("x-jarvis-request", "")
    if not _ID.fullmatch(session) or not _ID.fullmatch(operation):
        raise HTTPException(400, "Identificadores de conversa e pedido são obrigatórios.")
    return session, operation


async def call_runtime(path: str, payload: dict) -> dict | None:
    descriptor = get_config_dir() / "hud-runtime.json"
    if not descriptor.exists():
        return None  # OpenJarvis installations without modo-show keep working.
    try:
        data = json.loads(descriptor.read_text(encoding="utf-8"))
        port, token = data["porta"], data["token"]
        if type(port) is not int or not 1024 <= port <= 65535 or not isinstance(token, str) or not token:
            raise ValueError
    except (KeyError, OSError, ValueError, TypeError):
        raise HTTPException(503, "Registro do runtime inválido; reinicie o Jarvis.") from None
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=360) as client:
            response = await client.post(f"http://127.0.0.1:{port}{path}", json=payload,
                                         headers={"X-Jarvis-Token": token})
        if response.status_code != 200:
            raise HTTPException(503, "O runtime não aceitou o pedido; nenhuma repetição automática foi feita.")
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Não foi possível confirmar a resposta do runtime. Confira o painel antes de repetir uma ação.") from None


async def dispatch_chat(body, request: Request):
    if request.headers.get("x-openjarvis-runtime") != "1":
        return None
    local_client(request)
    session, operation = identity(request)
    if body.tools or not body.messages or body.messages[-1].role != "user":
        raise HTTPException(400, "O runtime recebe somente um pedido direto do usuário.")
    text = body.messages[-1].content
    if not isinstance(text, str) or not text.strip() or len(text) > 8000:
        raise HTTPException(400, "Pedido vazio ou maior que 8000 caracteres.")
    result = await call_runtime("/api/chat", {
        "texto": text, "sessao_id": session, "pedido_id": operation, "falar": False,
    })
    if result is None:
        return None
    content = result.get("resposta") or "Pedido interrompido. Consulte no painel as ações já executadas."
    modelos = result.get("modelos") or []
    common = {"id": "chatcmpl-" + uuid.uuid4().hex, "created": int(time.time()),
              "model": modelos[-1] if modelos else "jarvis-runtime",
              "runtime": {**{k: v for k, v in result.items() if k != "resposta"},
                          "modelo_solicitado": body.model}}
    if not body.stream:
        return {**common, "object": "chat.completion", "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}

    async def events():
        for delta, finish in [({"role": "assistant", "content": content}, None), ({}, "stop")]:
            chunk = {**common, "object": "chat.completion.chunk", "choices": [
                {"index": 0, "delta": delta, "finish_reason": finish}]}
            yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")
