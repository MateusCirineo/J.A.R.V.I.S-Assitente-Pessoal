"""Agenda e e-mail do Google pela API oficial, com login OAuth so de leitura.

Por que nao o conector do OpenJarvis: ele pede Gmail (inclusive apagar),
Drive, Contatos e escrita na Agenda de uma vez so. Aqui o pedido e o minimo:
`calendar.readonly` e `gmail.metadata` (remetente e assunto dos e-mails, sem o
corpo; nao apaga, nao envia, nao marca como lido) + o e-mail da conta.

- A credencial (ID e chave do cliente, tipo "App para computador") e criada
  pelo proprio usuario no Google Cloud; o login acontece no navegador dele.
- PKCE + `state` de uso unico: o codigo so vale para este runtime.
- Tokens em ~/.openjarvis/hud-segredos.json; nunca vao para as telas nem para
  o log. As telas so veem os e-mails ligados.
- Mais de uma conta (pessoal e trabalho); as agendas marcadas como visiveis em
  cada conta entram juntas.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any

from .agenda import gravar_segredo, ler_segredo

AUTORIZAR = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
REVOGAR = "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com/calendar/v3"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
ESCOPOS = ("openid email https://www.googleapis.com/auth/calendar.readonly "
           "https://www.googleapis.com/auth/gmail.metadata")
VALIDADE_PEDIDO_S = 10 * 60


class ErroGoogle(ValueError):
    """Mensagem ja segura para mostrar (sem token, sem chave)."""


def validar_cliente(client_id: str, client_secret: str) -> tuple[str, str]:
    cid, sec = client_id.strip(), client_secret.strip()
    if not cid.endswith(".apps.googleusercontent.com"):
        raise ValueError("o ID do cliente termina em .apps.googleusercontent.com")
    if len(sec) < 10 or any(c.isspace() for c in sec):
        raise ValueError("a chave secreta do cliente parece incompleta")
    return cid, sec


def _desafio(verificador: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()


def _email_do_id_token(id_token: str | None) -> str | None:
    # veio direto do Google por HTTPS, entao basta ler o conteudo do JWT
    try:
        corpo = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(corpo + "=" * (-len(corpo) % 4))).get("email")
    except (AttributeError, IndexError, ValueError):
        return None


def _post(url: str, dados: dict[str, str], tempo: float = 15) -> dict[str, Any]:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(dados).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=tempo) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            erro = json.load(e).get("error")
        except ValueError:
            erro = None
        raise ErroGoogle(f"Google recusou ({erro or e.code})") from None
    except (urllib.error.URLError, OSError) as e:
        raise ErroGoogle(f"sem conexão com o Google ({type(e).__name__})") from None


def _get(url: str, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise ErroGoogle(f"API do Google respondeu {e.code}") from None
    except (urllib.error.URLError, OSError) as e:
        raise ErroGoogle(f"sem conexão com o Google ({type(e).__name__})") from None


def _quando(v: dict[str, Any]) -> tuple[float, bool]:
    if "dateTime" in v:
        return datetime.fromisoformat(v["dateTime"].replace("Z", "+00:00")).timestamp(), False
    d = datetime.fromisoformat(v["date"])                    # dia inteiro: meia-noite local
    return d.astimezone().timestamp(), True


def converter_evento(ev: dict[str, Any], agenda: str | None = None) -> dict[str, Any] | None:
    if ev.get("status") == "cancelled" or "start" not in ev:
        return None
    ini, dia_todo = _quando(ev["start"])
    fim = _quando(ev["end"])[0] if ev.get("end") else ini
    return {"titulo": ev.get("summary") or "(sem título)", "local": ev.get("location"),
            "inicio": ini, "fim": fim, "dia_inteiro": dia_todo, "agenda": agenda}


class GoogleAgenda:
    def __init__(self, porta: int) -> None:
        self._porta = porta
        self._pedidos: dict[str, tuple[float, str]] = {}     # state -> (quando, verificador)
        self._acessos: dict[str, tuple[float, str]] = {}     # email -> (expira, access_token)
        self._trava = threading.Lock()

    @property
    def redirecionamento(self) -> str:
        return f"http://127.0.0.1:{self._porta}/oauth/google"

    # ---- configuracao ----------------------------------------------------
    def cliente(self) -> dict[str, str] | None:
        c = ler_segredo("google_cliente")
        return c if isinstance(c, dict) and c.get("id") and c.get("chave") else None

    def definir_cliente(self, client_id: str, client_secret: str) -> None:
        cid, sec = validar_cliente(client_id, client_secret)
        gravar_segredo("google_cliente", {"id": cid, "chave": sec})

    def contas(self) -> list[dict[str, Any]]:
        c = ler_segredo("google_contas")
        return c if isinstance(c, list) else []

    def publico(self) -> dict[str, Any]:
        """O que as telas podem saber: se ha credencial e quais e-mails estao ligados."""
        return {"cliente": self.cliente() is not None,
                "contas": [{"email": c.get("email"), "reconectar": bool(c.get("reconectar"))}
                           for c in self.contas()]}

    # ---- login -----------------------------------------------------------
    def url_login(self) -> str:
        cli = self.cliente()
        if not cli:
            raise ValueError("cole antes o ID e a chave do cliente OAuth")
        estado, verificador = secrets.token_urlsafe(24), secrets.token_urlsafe(64)
        agora = time.time()
        with self._trava:
            self._pedidos = {k: v for k, v in self._pedidos.items() if agora - v[0] < VALIDADE_PEDIDO_S}
            self._pedidos[estado] = (agora, verificador)
        return AUTORIZAR + "?" + urllib.parse.urlencode({
            "client_id": cli["id"], "redirect_uri": self.redirecionamento, "response_type": "code",
            "scope": ESCOPOS, "access_type": "offline", "prompt": "consent select_account",
            "state": estado, "code_challenge": _desafio(verificador), "code_challenge_method": "S256",
        })

    def concluir_login(self, codigo: str, estado: str) -> str:
        """Troca o codigo pelos tokens. Devolve o e-mail da conta ligada."""
        with self._trava:
            pedido = self._pedidos.pop(estado, None)
        if not pedido or time.time() - pedido[0] > VALIDADE_PEDIDO_S:
            raise ErroGoogle("pedido de login desconhecido ou vencido; clique em Conectar de novo")
        cli = self.cliente()
        if not cli:
            raise ErroGoogle("credencial do cliente removida durante o login")
        r = _post(TOKEN, {"client_id": cli["id"], "client_secret": cli["chave"], "code": codigo,
                          "code_verifier": pedido[1], "redirect_uri": self.redirecionamento,
                          "grant_type": "authorization_code"})
        email = _email_do_id_token(r.get("id_token")) or "conta Google"
        if not r.get("refresh_token"):
            raise ErroGoogle("o Google não devolveu acesso contínuo; tente Conectar de novo")
        contas = [c for c in self.contas() if c.get("email") != email]
        contas.append({"email": email, "refresh": r["refresh_token"], "ligada_em": time.time()})
        gravar_segredo("google_contas", contas)
        with self._trava:
            self._acessos[email] = (time.time() + int(r.get("expires_in", 3600)) - 60, r["access_token"])
        return email

    def desconectar(self, email: str) -> None:
        contas = self.contas()
        alvo = next((c for c in contas if c.get("email") == email), None)
        if not alvo:
            raise ValueError("conta não encontrada")
        try:                                            # revoga no Google; se falhar, remove mesmo assim
            _post(REVOGAR, {"token": alvo["refresh"]}, tempo=8)
        except ErroGoogle:
            pass
        gravar_segredo("google_contas", [c for c in contas if c.get("email") != email] or None)
        with self._trava:
            self._acessos.pop(email, None)

    # ---- leitura ---------------------------------------------------------
    def _acesso(self, conta: dict[str, Any]) -> str:
        email = conta.get("email")
        with self._trava:
            guardado = self._acessos.get(email)
        if guardado and guardado[0] > time.time():
            return guardado[1]
        cli = self.cliente()
        if not cli:
            raise ErroGoogle("credencial do cliente ausente")
        try:
            r = _post(TOKEN, {"client_id": cli["id"], "client_secret": cli["chave"],
                              "refresh_token": conta["refresh"], "grant_type": "refresh_token"})
        except ErroGoogle as e:
            if "invalid_grant" in str(e):               # revogado ou expirado: precisa logar de novo
                contas = self.contas()
                for c in contas:
                    if c.get("email") == email:
                        c["reconectar"] = True
                gravar_segredo("google_contas", contas)
                raise ErroGoogle("acesso vencido; clique em Conectar de novo") from None
            raise
        with self._trava:
            self._acessos[email] = (time.time() + int(r.get("expires_in", 3600)) - 60, r["access_token"])
        return r["access_token"]

    def emails(self, recentes: int = 5) -> dict[str, Any]:
        """Nao lidos da caixa de entrada: quantos e de quem (so metadados)."""
        if not self.contas():
            return {"status": "nao_configurado", "motivo": "conecte sua conta Google no cartão Agenda"}
        contas, avisos = [], []
        for conta in self.contas():
            email = conta.get("email", "conta")
            if conta.get("reconectar"):
                avisos.append(f"{email}: precisa conectar de novo")
                continue
            try:
                token = self._acesso(conta)
                lista = _get(f"{GMAIL}/messages?labelIds=INBOX&labelIds=UNREAD&maxResults=25", token)
                ids = [m["id"] for m in lista.get("messages", [])]
                achados = []
                for i in ids[:recentes]:
                    m = _get(f"{GMAIL}/messages/{i}?format=metadata&metadataHeaders=From&metadataHeaders=Subject", token)
                    h = {x["name"].lower(): x["value"] for x in (m.get("payload") or {}).get("headers", [])}
                    achados.append({"id": i, "de": nome_remetente(h.get("from", "")),
                                    "assunto": (h.get("subject") or "(sem assunto)")[:160],
                                    "em": int(m.get("internalDate") or 0) / 1000})
                contas.append({"email": email, "nao_lidos": max(len(ids), lista.get("resultSizeEstimate") or 0),
                               "recentes": achados})
            except ErroGoogle as e:
                avisos.append(f"{email}: " + ("sem permissão de e-mail; conecte a conta de novo e ative a "
                                              "Gmail API no projeto" if "403" in str(e) else str(e)))
        if not contas:
            return {"status": "erro", "detalhe": "; ".join(avisos)[:300], "avisos": avisos}
        return {"status": "medido", "em": time.time(), "contas": contas, "avisos": avisos,
                "nao_lidos": sum(c["nao_lidos"] for c in contas)}

    def eventos(self, inicio: datetime, fim: datetime) -> tuple[list[dict[str, Any]], list[str]]:
        """Eventos de todas as contas ligadas + avisos por conta (sem segredos)."""
        saida: list[dict[str, Any]] = []
        avisos: list[str] = []
        for conta in self.contas():
            email = conta.get("email", "conta")
            if conta.get("reconectar"):
                avisos.append(f"{email}: precisa conectar de novo")
                continue
            try:
                token = self._acesso(conta)
                agendas = _get(f"{API}/users/me/calendarList", token, {"minAccessRole": "reader"})
                for ag in agendas.get("items", []):
                    if not ag.get("selected"):           # so as agendas visiveis no Google Agenda
                        continue
                    evs = _get(f"{API}/calendars/{urllib.parse.quote(ag['id'], safe='')}/events", token, {
                        "timeMin": inicio.isoformat(), "timeMax": fim.isoformat(),
                        "singleEvents": "true", "orderBy": "startTime", "maxResults": 50})
                    nome = ag.get("summaryOverride") or ag.get("summary")
                    saida += [e for e in (converter_evento(x, nome) for x in evs.get("items", [])) if e]
            except ErroGoogle as e:
                avisos.append(f"{email}: {e}")
        return saida, avisos


def nome_remetente(de: str) -> str:
    from email.utils import parseaddr
    nome, endereco = parseaddr(de or "")
    return (nome or endereco or "remetente desconhecido").strip()[:80]


def iniciar_periodo(dias: int = 3) -> tuple[datetime, datetime]:
    agora = datetime.now().astimezone()
    inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    return inicio, inicio + timedelta(days=dias)
