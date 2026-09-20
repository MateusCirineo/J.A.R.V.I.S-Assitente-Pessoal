"""Download pequeno e seguro para feeds e APIs publicas.

- TLS sempre verificado: nenhum caminho desliga a verificacao de certificado.
- Descompacta gzip mesmo sem ter pedido (o G1 manda assim).
- Segue 308 (o urllib do Python 3.10 so segue 301/302/303/307).
- Limite de tamanho; so https/http de saida, nada de file:// ou ftp://.
"""

from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.request
from typing import Any

AGENTE = "Mozilla/5.0 (JarvisHUD; uso pessoal)"


class _Segue308(urllib.request.HTTPRedirectHandler):
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_301(req, fp, 301, msg, headers)


_ABRIR = urllib.request.build_opener(_Segue308).open


def baixar(url: str, limite: int = 3_000_000, timeout: float = 12, aceitar: str = "*/*") -> bytes:
    if not url.startswith(("https://", "http://")):
        raise ValueError("só http(s)")
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": aceitar,
                                               "Accept-Encoding": "gzip"})
    with _ABRIR(req, timeout=timeout) as r:
        dados = r.read(limite)
        gz = (r.headers.get("Content-Encoding") or "").lower() == "gzip"
    if gz or dados[:2] == b"\x1f\x8b":
        dados = gzip.decompress(dados)
    return dados


def baixar_json(url: str, timeout: float = 10) -> Any:
    return json.loads(baixar(url, 2_000_000, timeout, "application/json"))


ERROS_REDE = (urllib.error.URLError, OSError, ValueError, EOFError)
