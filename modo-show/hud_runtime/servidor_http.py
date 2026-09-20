"""HTTP local do runtime: telas, estado (SSE) e controles.

Escopo e protecoes:
  - escuta so em 127.0.0.1
  - cabecalho Host precisa ser 127.0.0.1:<porta> ou localhost:<porta>
    (bloqueia DNS rebinding)
  - acoes (POST) exigem X-Jarvis-Token e Origin da propria pagina; o token
    fica numa meta tag das telas servidas aqui. Outra origem nao le as telas
    (sem CORS) e o cabecalho customizado forca um preflight que nao e aceito.
  - nenhuma rota libera CORS. O chat do OpenJarvis so abre estas telas; nao
    consulta a API (e a CSP dele, default-src 'self', impediria de qualquer
    forma -- e continua intacta).
  - CSP estrita nas telas do HUD.
"""

from __future__ import annotations

import json
import queue
import socket
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import janelas

PASTA = Path(__file__).resolve().parent.parent
HUD = PASTA / "hud"
CSP_HUD =("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
           "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
           "form-action 'none'")
CSP_CLASSICO = ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "frame-ancestors 'none'")
TIPOS = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
         ".woff2": "font/woff2", ".ico": "image/x-icon", ".png": "image/png"}
MAX_CORPO = 16 * 1024


class ServidorExclusivo(ThreadingHTTPServer):
    """A porta e a trava de instancia unica. O HTTPServer padrao liga
    SO_REUSEADDR, que no Windows deixa DOIS processos ocuparem a mesma porta:
    aconteceu aqui (dois runtimes, duas vozes). SO_EXCLUSIVEADDRUSE impede."""

    daemon_threads = True
    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def criar(rt, porta: int) -> ThreadingHTTPServer:
    permitidos_host = {f"127.0.0.1:{porta}", f"localhost:{porta}"}
    permitidos_origem = {f"http://127.0.0.1:{porta}", f"http://localhost:{porta}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "JarvisHUD/1"
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # silencioso: o runtime tem log proprio
            pass

        # ---- utilitarios ------------------------------------------------

        def _host_ok(self) -> bool:
            if self.headers.get("Host", "") in permitidos_host:
                return True
            self._responder(403, {"erro": "host nao permitido"})
            return False

        def _responder(self, codigo: int, corpo: Any, tipo: str = "application/json",
                       extra: dict[str, str] | None = None) -> None:
            dados = (json.dumps(corpo, ensure_ascii=False).encode()
                     if tipo == "application/json" else corpo)
            self.send_response(codigo)
            self.send_header("Content-Type", tipo if tipo != "application/json"
                             else "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(dados)

        def _arquivo(self, caminho: Path, csp: str | None = None,
                     substituir: dict[str, str] | None = None) -> None:
            try:
                dados = caminho.read_bytes()
            except OSError:
                self._responder(404, {"erro": "nao encontrado"})
                return
            if substituir:
                texto = dados.decode("utf-8")
                for k, v in substituir.items():
                    texto = texto.replace(k, v)
                dados = texto.encode("utf-8")
            extra = {"X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"}
            if csp:
                extra["Content-Security-Policy"] = csp
            if substituir and "{{TOKEN}}" in substituir:
                extra["Set-Cookie"] = f"jarvis_hud_session={rt.token}; Path=/; HttpOnly; SameSite=Strict"
            self._responder(200, dados, TIPOS.get(caminho.suffix, "application/octet-stream"),
                            extra)

        def _leitura_autorizada(self) -> bool:
            origem = self.headers.get("Origin")
            if (origem is not None and origem not in permitidos_origem
                    or self.headers.get("Sec-Fetch-Site") == "cross-site"):
                self._responder(403, {"erro": "origem nao permitida"})
                return False
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
                sessao = cookie.get("jarvis_hud_session")
                autorizado = (self.headers.get("X-Jarvis-Token") == rt.token
                              or sessao is not None and sessao.value == rt.token)
            except Exception:
                autorizado = False
            if not autorizado:
                self._responder(403, {"erro": "sessao ausente ou invalida"})
            return autorizado

        def _estatico(self, rel: str) -> None:
            alvo = (HUD / rel).resolve()
            if not alvo.is_relative_to(HUD.resolve()) or not alvo.is_file():
                self._responder(404, {"erro": "nao encontrado"})
                return
            self._arquivo(alvo)

        def _tela(self, nome: str) -> None:
            prefs = rt.prefs.ler()
            if prefs["tema"] == "classico" and nome in ("jarvis", "painel"):
                destino = "/classico/rosto" if nome == "jarvis" else "/classico/painel"
                self.send_response(302)
                self.send_header("Location", destino)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._arquivo(HUD / f"{nome}.html", CSP_HUD,
                          {"{{TOKEN}}": rt.token, "{{PORTA}}": str(porta)})

        def _retorno_google(self) -> None:
            from html import escape
            q = parse_qs(urlparse(self.path).query)
            codigo, estado = (q.get("code") or [""])[0], (q.get("state") or [""])[0]
            erro = (q.get("error") or [""])[0]
            try:
                if erro:
                    raise ValueError("login cancelado" if erro == "access_denied" else f"o Google recusou ({erro})")
                email = rt.google.concluir_login(codigo, estado)
                rt.agenda.esquecer_cache()
                rt.amostrador.lento.forcar("agenda")
                rt._publicar_prefs()
                rt.estado.registrar("agenda", f"conta Google conectada: {email}")
                titulo, msg, cod = "Agenda conectada", f"{email} ligada ao Jarvis (só leitura). Pode fechar esta aba.", 200
            except Exception as e:  # noqa: BLE001 - mensagens ja sem segredos
                titulo, msg, cod = "Não conectou", f"{e}", 400
            pagina = (f"<!doctype html><meta charset=utf-8><title>{escape(titulo)}</title>"
                      f"<body style='font:16px system-ui;background:#03080d;color:#e5f8ff;padding:60px;text-align:center'>"
                      f"<h2 style='color:{'#3de6b0' if cod == 200 else '#ff5964'}'>{escape(titulo)}</h2><p>{escape(msg)}</p>")
            self._responder(cod, pagina.encode(), "text/html; charset=utf-8",
                            {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})

        # ---- GET --------------------------------------------------------

        def do_GET(self):  # noqa: N802
            if not self._host_ok():
                return
            rota = urlparse(self.path).path
            if ((rota.startswith("/api/") and rota != "/api/saude")
                    or rota == "/classico/dados.js") and not self._leitura_autorizada():
                return
            if rota in ("/", "/jarvis"):
                self._tela("jarvis")
            elif rota == "/painel":
                self._tela("painel")
            elif rota == "/holograma":
                self._tela("holograma")
            elif rota == "/api/holograma/grafico":              # o ultimo grafico (a mesa pode ter aberto depois)
                if self.headers.get("X-Jarvis-Token") != rt.token:
                    self._responder(403, {"erro": "token"})
                    return
                self._responder(200, {"grafico": getattr(rt, "holograma_grafico", None)})
            elif rota == "/api/holograma/modelo":               # so o modelo que o runtime escolheu
                if self.headers.get("X-Jarvis-Token") != rt.token:
                    self._responder(403, {"erro": "token"})
                    return
                apresentacao = getattr(rt, "apresentacao", None)
                exibicao = apresentacao.atual() if apresentacao is not None else {}
                caminho = Path(exibicao["arquivo"]) if exibicao.get("arquivo") else getattr(rt, "holograma_modelo", None)
                if not caminho or not caminho.is_file():
                    self._responder(404, {"erro": "sem modelo"})
                    return
                from urllib.parse import quote
                self._responder(200, caminho.read_bytes(), "application/octet-stream",
                                {"X-Modelo-Nome": quote(caminho.name), "Cache-Control": "no-store",
                                 "X-Apresentacao-Id": exibicao.get("id") or ""})
            elif rota.startswith("/hud/"):
                self._estatico(rota[len("/hud/"):])
            elif rota == "/classico/rosto":
                self._arquivo(PASTA / "tela1_rosto.html", CSP_CLASSICO, {"{{TOKEN}}": rt.token})
            elif rota == "/classico/tema":                         # so o nome do tema, sem segredo
                self._responder(200, {"tema": rt.prefs.ler()["tema"]})
            elif rota == "/classico/painel":
                self._arquivo(PASTA / "tela2_painel.html", CSP_CLASSICO, {"{{TOKEN}}": rt.token})
            elif rota == "/classico/dados.js":
                self._responder(200, rt.dados_classicos().encode(), TIPOS[".js"])
            elif rota == "/oauth/google":
                self._retorno_google()
            elif rota == "/api/saude":
                self._responder(200, {"ok": True, "servico": "jarvis-hud",
                                      "versao_codigo": getattr(rt, "versao_codigo", None),
                                      "boot_concluido": rt.estado.ler("boot")["concluido"]})
            elif rota == "/api/estado":
                self._responder(200, rt.estado.instantaneo())
            elif rota == "/api/telemetria":
                self._responder(200, rt.estado.telemetria)
            elif rota == "/api/preferencias":
                self._responder(200, rt.prefs_publicas())
            elif rota == "/api/eventos":
                self._sse()
            elif rota == "/api/camera.mjpg":
                self._mjpeg()
            else:
                self._responder(404, {"erro": "rota desconhecida"})

        def _mjpeg(self) -> None:
            """Preview da camera. Exige o token (uma <img> de outra origem nao
            consegue) e so existe com a camera ligada. Nada e gravado."""
            cam = getattr(rt, "camera", None)
            if cam is None or not cam.ativa:
                self._responder(409, {"erro": "camera desligada"})
                return
            self.close_connection = True
            try:
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=quadro")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                visto = -1
                while not rt.encerrando.is_set() and cam.ativa:
                    visto, jpeg = cam.proximo_jpeg(visto)
                    if jpeg is None:
                        continue
                    self.wfile.write(b"--quadro\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                     + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass

        def _sse(self) -> None:
            q = rt.estado.inscrever()           # inscreve ANTES do retrato: nada se perde
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                inicial = [("estado", rt.estado.instantaneo()),
                           ("telemetria", rt.estado.telemetria),
                           ("preferencias", rt.prefs_publicas())]
                self.wfile.write(b"retry: 2000\n\n")
                for ev, dados in inicial:
                    self.wfile.write(
                        f"event: {ev}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
                while not rt.encerrando.is_set():
                    try:
                        linha = q.get(timeout=15)
                    except queue.Empty:
                        linha = ": ping\n\n"
                    self.wfile.write(linha.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass
            finally:
                rt.estado.cancelar(q)
                self.close_connection = True

        # ---- POST -------------------------------------------------------

        def do_POST(self):  # noqa: N802
            try:
                tamanho = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                tamanho = -1
            if tamanho < 0 or tamanho > MAX_CORPO:
                self.close_connection = True
                self._responder(413, {"erro": "corpo invalido"}, extra={"Connection": "close"})
                return
            # Le o corpo ANTES de qualquer recusa: responder com dados ainda
            # nao lidos no socket faz o Windows resetar a conexao, e o cliente
            # recebe "conexao anulada" em vez do 403.
            bruto = self.rfile.read(tamanho) if tamanho else b""

            if not self._host_ok():
                return
            origem = self.headers.get("Origin")
            if origem is not None and origem not in permitidos_origem:
                self._responder(403, {"erro": "origem nao permitida"})
                return
            if self.headers.get("X-Jarvis-Token") != rt.token:
                self._responder(403, {"erro": "token ausente ou invalido"})
                return
            try:
                corpo = json.loads(bruto or b"{}")
                if not isinstance(corpo, dict):
                    raise ValueError
            except ValueError:
                self._responder(400, {"erro": "JSON invalido"})
                return

            rota = urlparse(self.path).path
            try:
                resposta = rt.acao(rota, corpo)
            except KeyError:
                self._responder(404, {"erro": "acao desconhecida"})
                return
            except ValueError as e:
                self._responder(400, {"erro": str(e)})
                return
            self._responder(200, resposta)

    return ServidorExclusivo(("127.0.0.1", porta), Handler)


def rodar(servidor: ThreadingHTTPServer) -> threading.Thread:
    fio = threading.Thread(target=servidor.serve_forever, name="http", daemon=True)
    fio.start()
    return fio


__all__ = ["criar", "rodar", "janelas"]
