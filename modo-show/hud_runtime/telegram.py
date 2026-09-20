"""Ponte com o celular do Senhor pelo Telegram (o "comunicador" do Jarvis).

- O bot e do proprio Senhor (criado no @BotFather); o token fica no cofre
  hud-segredos.json e nunca volta para as telas.
- Pareamento: o Painel mostra um codigo de 6 digitos; o Senhor manda
  "/parear 123456" ao bot. So esse chat fica autorizado; os outros sao ignorados.
- Mensagens do chat autorizado viram comandos digitados (a resposta volta pelo
  Telegram, sem falar no PC). Comandos proibidos continuam proibidos.
- Avisos (vigia, lembretes, monitores) vao para o celular se "avisos_no_celular".
- Nenhuma foto da camera e enviada. TLS sempre verificado (api.telegram.org).
"""

from __future__ import annotations

import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

API = "https://api.telegram.org"


class PonteTelegram(threading.Thread):
    def __init__(self, atender: Callable[[str], str | None], ler: Callable[[str], str | None],
                 gravar: Callable[[str, str | None], None], registrar: Callable[..., None]) -> None:
        super().__init__(daemon=True, name="telegram")
        self._atender, self._ler, self._gravar, self._registrar = atender, ler, gravar, registrar
        self._parar = threading.Event()
        self.codigo = f"{secrets.randbelow(900000) + 100000}"
        self.bot: str | None = None
        self.erro: str | None = None
        self._offset = 0

    # ---- API -----------------------------------------------------------------------------
    def _chamar(self, token: str, metodo: str, dados: dict[str, Any] | None = None, timeout: float = 35) -> Any:
        corpo = json.dumps(dados or {}).encode()
        req = urllib.request.Request(f"{API}/bot{token}/{metodo}", data=corpo,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
        if not d.get("ok"):
            raise ValueError(d.get("description") or "o Telegram recusou")
        return d["result"]

    def testar(self, token: str) -> str:
        """Confere o token (getMe) e devolve o @ do bot."""
        eu = self._chamar(token, "getMe", timeout=10)
        return eu.get("username") or "bot"

    @property
    def token(self) -> str | None:
        return self._ler("telegram_token")

    @property
    def chat(self) -> int | None:
        c = self._ler("telegram_chat")
        return int(c) if c and str(c).lstrip("-").isdigit() else None

    def publico(self) -> dict[str, Any]:
        pareado = self.chat is not None
        return {"configurado": bool(self.token), "bot": self.bot, "pareado": pareado,
                "codigo": None if pareado else self.codigo, "erro": self.erro}

    def definir_token(self, token: str) -> str:
        token = token.strip()
        if not token or ":" not in token or len(token) > 100:
            raise ValueError("isso não parece um token do BotFather (formato 123456:ABC...)")
        try:
            self.bot = self.testar(token)
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise ValueError(f"o Telegram não aceitou o token: {str(e)[:80]}") from None
        self._gravar("telegram_token", token)
        self._gravar("telegram_chat", None)                 # bot novo: parear de novo
        self.codigo = f"{secrets.randbelow(900000) + 100000}"
        self.erro = None
        self._registrar("telegram", f"bot @{self.bot} configurado; aguardando pareamento")
        return self.bot

    def desparear(self) -> None:
        self._gravar("telegram_chat", None)
        self.codigo = f"{secrets.randbelow(900000) + 100000}"

    def enviar(self, texto: str) -> bool:
        """Mensagem para o celular do Senhor (so com o chat pareado)."""
        token, chat = self.token, self.chat
        if not token or chat is None:
            return False
        try:
            self._chamar(token, "sendMessage", {"chat_id": chat, "text": texto[:3900]}, timeout=10)
            return True
        except (urllib.error.URLError, OSError, ValueError) as e:
            self.erro = str(e)[:120]
            return False

    # ---- laco ---------------------------------------------------------------------------------
    def encerrar(self) -> None:
        self._parar.set()

    def tratar(self, msg: dict[str, Any], token: str) -> None:
        chat = (msg.get("chat") or {}).get("id")
        texto = (msg.get("text") or "").strip()
        if chat is None or not texto:
            return
        responder = lambda t: self._chamar(token, "sendMessage", {"chat_id": chat, "text": t[:3900]}, timeout=10)  # noqa: E731
        if texto.startswith(("/parear", "/start")):
            partes = texto.split()
            if self.chat is None and len(partes) > 1 and secrets.compare_digest(partes[1], self.codigo):
                self._gravar("telegram_chat", str(chat))
                self._registrar("telegram", "celular pareado")
                responder("Pareado, Senhor. Pode me mandar comandos por aqui, e os avisos chegam neste chat.")
            elif self.chat == chat:
                responder("Este chat já está pareado.")
            else:
                responder("Para parear, mande /parear seguido do código que aparece no Painel do Jarvis.")
            return
        if chat != self.chat:
            return                                             # estranhos: silencio
        try:
            resposta = self._atender(texto)
        except Exception as e:  # noqa: BLE001 - o celular recebe o erro em vez de silencio
            resposta = f"Não consegui: {str(e)[:120]}"
        responder((resposta or "Feito.") + self._aviso_de_canal(texto))

    def _aviso_de_canal(self, pedido: str) -> str:
        """Por aqui só vai TEXTO. Se ele pediu áudio ou tela, eu digo onde saiu (F37)."""
        import re
        n = pedido.lower()
        if re.search(r"\b(?:fale|fala|leia em voz|em voz alta|audio|áudio|toque|escutar|ouvir)\b", n):
            capacidade = "audio"
        elif re.search(r"\b(?:mostre|mostra|na tela|gráfico|grafico|modelo 3d|mesa)\b", n):
            capacidade = "apresentacao"
        else:
            return ""
        canais = getattr(self, "canais", None)
        if canais is None:
            from .canais import Canais
            canais = self.canais = Canais()
        if canais.pode("telegram", capacidade):
            return ""
        canais.autenticar("telegram", self.chat is not None)
        return "\n\n" + canais.porque_nao("telegram", capacidade)

    def run(self) -> None:
        while not self._parar.is_set():
            token = self.token
            if not token:
                self._parar.wait(5)
                continue
            try:
                atualizacoes = self._chamar(token, "getUpdates", {"offset": self._offset, "timeout": 25,
                                                                   "allowed_updates": ["message"]})
                self.erro = None
            except (urllib.error.URLError, OSError, ValueError) as e:
                self.erro = str(e)[:120]
                self._parar.wait(15)
                continue
            for u in atualizacoes:
                self._offset = max(self._offset, u.get("update_id", 0) + 1)
                if u.get("message"):
                    try:
                        self.tratar(u["message"], token)
                    except (urllib.error.URLError, OSError, ValueError) as e:
                        self.erro = str(e)[:120]


def link_whatsapp(numero: str, texto: str) -> str | None:
    """wa.me com a mensagem pronta (o Senhor aperta enviar). Numero brasileiro sem DDI ganha 55."""
    digitos = "".join(c for c in numero if c.isdigit())
    if len(digitos) < 10 or len(digitos) > 13:
        return None
    if len(digitos) <= 11:
        digitos = "55" + digitos
    return f"https://wa.me/{digitos}?text={urllib.parse.quote(texto.strip())}"
