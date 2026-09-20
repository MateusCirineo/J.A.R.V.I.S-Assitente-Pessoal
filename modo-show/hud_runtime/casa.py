"""Casa inteligente pela rede LOCAL (nada vai para a internet).

Descoberta: SSDP/UPnP (TVs, caixas de som, roteadores, DLNA) e mDNS
(Chromecast, Hue, Home Assistant, Shelly, impressoras, AirPlay).

Controle, so com protocolos abertos e locais:
- UPnP MediaRenderer (TV/caixa de som DLNA): volume, mudo, tocar, pausar, parar.
- Home Assistant: luzes, tomadas, ventiladores, cortinas, fechaduras, midia, pelo
  endereco e token que o Senhor cola no Painel (token no cofre hud-segredos.json).
- Shelly (gen1/gen2) e Tasmota: tomadas e reles Wi-Fi, liga/desliga por HTTP.

Fechadura/portao: destrancar ou abrir pede "confirmo". TLS sempre verificado
(Home Assistant com certificado proprio: use o endereco http da rede local).
"""

from __future__ import annotations

import json
import os
import re
import socket
import struct
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
REGISTRO = HOME / "hud-casa.json"
ERROS = (urllib.error.URLError, OSError, ValueError, ET.ParseError)
SERVICOS_MDNS = ["_googlecast._tcp.local", "_hue._tcp.local", "_home-assistant._tcp.local", "_shelly._tcp.local",
                 "_http._tcp.local", "_airplay._tcp.local", "_spotify-connect._tcp.local", "_ipp._tcp.local",
                 "_hap._tcp.local", "_esphomelib._tcp.local"]
TIPOS_MDNS = {"_googlecast": "Chromecast/Google", "_hue": "Philips Hue", "_home-assistant": "Home Assistant",
              "_shelly": "Shelly", "_airplay": "AirPlay", "_spotify-connect": "Spotify Connect", "_ipp": "impressora",
              "_hap": "HomeKit", "_esphomelib": "ESPHome"}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).replace("_", " ").split())


def _http(url: str, dados: bytes | None = None, cabecalhos: dict[str, str] | None = None, metodo: str | None = None,
          timeout: float = 3.0) -> bytes:
    req = urllib.request.Request(url, data=dados, headers=cabecalhos or {}, method=metodo)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(2_000_000)


# ---- descoberta ------------------------------------------------------------------------------
def descobrir_ssdp(tempo: float = 2.5) -> list[dict[str, Any]]:
    msg = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 2\r\n"
           "ST: ssdp:all\r\n\r\n").encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    s.settimeout(0.3)
    locais: dict[str, str] = {}
    try:
        for _ in range(2):
            s.sendto(msg, ("239.255.255.250", 1900))
        fim = time.time() + tempo
        while time.time() < fim:
            try:
                dados, (ip, _) = s.recvfrom(4096)
            except socket.timeout:
                continue
            cab = {k.strip().lower(): v.strip() for k, _, v in
                   (l.partition(":") for l in dados.decode("utf-8", "replace").split("\r\n")[1:]) if k}
            if cab.get("location"):
                locais.setdefault(cab["location"], ip)
    finally:
        s.close()
    aparelhos, vistos = [], set()
    for local, ip in list(locais.items())[:40]:
        try:
            d = descrever_upnp(local)
        except ERROS:
            continue
        if d and d["id"] not in vistos:
            vistos.add(d["id"])
            aparelhos.append(d)
    return aparelhos


def descrever_upnp(local: str) -> dict[str, Any] | None:
    raiz = ET.fromstring(_http(local, timeout=2.5))
    ns = {"d": "urn:schemas-upnp-org:device-1-0"}
    dev = raiz.find("d:device", ns)
    if dev is None:
        return None
    texto = lambda e, k: (e.findtext(f"d:{k}", default="", namespaces=ns) or "").strip()   # noqa: E731
    servicos = {}
    for sv in raiz.iter("{urn:schemas-upnp-org:device-1-0}service"):
        tipo, ctrl = texto(sv, "serviceType"), texto(sv, "controlURL")
        for nome in ("AVTransport", "RenderingControl"):
            if f":{nome}:" in tipo:
                servicos[nome] = {"tipo": tipo, "url": urllib.parse.urljoin(local, ctrl)}
    tipo_dev = texto(dev, "deviceType")
    return {"id": texto(dev, "UDN") or local, "nome": texto(dev, "friendlyName") or "aparelho UPnP",
            "fabricante": texto(dev, "manufacturer"), "modelo": texto(dev, "modelName"),
            "tipo": "midia" if "MediaRenderer" in tipo_dev or "RenderingControl" in servicos else "upnp",
            "protocolo": "upnp", "ip": urllib.parse.urlparse(local).hostname, "servicos": servicos}


def _nome_dns(q: str) -> bytes:
    return b"".join(bytes([len(p)]) + p.encode() for p in q.split(".")) + b"\0"


def _ler_nome(pacote: bytes, pos: int) -> tuple[str, int]:
    partes, pulou, fim = [], False, pos
    for _ in range(50):
        n = pacote[pos]
        if n == 0:
            pos += 1
            break
        if n & 0xC0 == 0xC0:
            if not pulou:
                fim = pos + 2
            pos, pulou = ((n & 0x3F) << 8) | pacote[pos + 1], True
            continue
        partes.append(pacote[pos + 1:pos + 1 + n].decode("utf-8", "replace"))
        pos += 1 + n
    return ".".join(partes), (fim if pulou else pos)


def ler_resposta_mdns(pacote: bytes) -> list[tuple[str, int, Any]]:
    """Registros (nome, tipo, dado) de todas as secoes. PTR=12 SRV=33 A=1 TXT=16."""
    _, _, qd, an, ns_, ar = struct.unpack("!6H", pacote[:12])
    pos = 12
    for _ in range(qd):
        _, pos = _ler_nome(pacote, pos)
        pos += 4
    saida = []
    for _ in range(an + ns_ + ar):
        nome, pos = _ler_nome(pacote, pos)
        tipo, _, _, tam = struct.unpack("!HHIH", pacote[pos:pos + 10])
        pos += 10
        dado: Any = pacote[pos:pos + tam]
        if tipo == 12:
            dado = _ler_nome(pacote, pos)[0]
        elif tipo == 33:
            porta = struct.unpack("!H", pacote[pos + 4:pos + 6])[0]
            dado = (_ler_nome(pacote, pos + 6)[0], porta)
        elif tipo == 1 and tam == 4:
            dado = socket.inet_ntoa(pacote[pos:pos + 4])
        elif tipo == 16:
            txt, i = {}, 0
            while i < tam:
                n = pacote[pos + i]
                k, _, v = pacote[pos + i + 1:pos + i + 1 + n].decode("utf-8", "replace").partition("=")
                txt[k] = v
                i += 1 + n
            dado = txt
        saida.append((nome, tipo, dado))
        pos += tam
    return saida


def descobrir_mdns(tempo: float = 2.5) -> list[dict[str, Any]]:
    """Pergunta "quem oferece estes servicos?" (resposta unicast, sem ocupar a porta 5353)."""
    pergunta = struct.pack("!6H", 0, 0, len(SERVICOS_MDNS), 0, 0, 0) + b"".join(
        _nome_dns(s) + struct.pack("!HH", 12, 1) for s in SERVICOS_MDNS)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.settimeout(0.3)
    registros: list[tuple[str, int, Any]] = []
    try:
        s.sendto(pergunta, ("224.0.0.251", 5353))
        fim = time.time() + tempo
        while time.time() < fim:
            try:
                dados, _ = s.recvfrom(9000)
                registros += ler_resposta_mdns(dados)
            except socket.timeout:
                continue
            except (struct.error, IndexError):
                continue
    finally:
        s.close()
    srv = {n: d for n, t, d in registros if t == 33}
    ips = {n: d for n, t, d in registros if t == 1}
    txts = {n: d for n, t, d in registros if t == 16}
    aparelhos, vistos = [], set()
    for servico, tipo, instancia in registros:
        if tipo != 12 or instancia in vistos:
            continue
        vistos.add(instancia)
        chave = servico.split(".")[0]
        alvo, porta = srv.get(instancia, (None, None))
        ip = ips.get(alvo) if alvo else None
        txt = txts.get(instancia, {})
        nome = txt.get("fn") or instancia.split("._")[0]
        tipo_ap = TIPOS_MDNS.get(chave, "web")
        n = _norm(nome)
        if chave == "_http" and not re.search(r"shelly|tasmota", n):
            continue                                        # _http de tudo (roteador, NAS): so reles interessam
        if "shelly" in n:
            tipo_ap = "Shelly"
        elif "tasmota" in n:
            tipo_ap = "Tasmota"
        aparelhos.append({"id": instancia, "nome": nome, "tipo": tipo_ap, "protocolo": "mdns", "ip": ip, "porta": porta})
    return aparelhos


# ---- controle ------------------------------------------------------------------------------------
def _soap(servico: dict[str, str], acao: str, args: dict[str, Any]) -> bytes:
    corpo = "".join(f"<{k}>{v}</{k}>" for k, v in args.items())
    env = (f'<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
           f's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
           f'<u:{acao} xmlns:u="{servico["tipo"]}">{corpo}</u:{acao}></s:Body></s:Envelope>')
    return _http(servico["url"], env.encode(), {"Content-Type": 'text/xml; charset="utf-8"',
                                                 "SOAPACTION": f'"{servico["tipo"]}#{acao}"'})


def upnp(aparelho: dict[str, Any], acao: str, valor: int | None = None) -> None:
    sv = aparelho.get("servicos") or {}
    if acao in ("volume", "mudo", "som"):
        rc = sv.get("RenderingControl")
        if not rc:
            raise ValueError("esse aparelho não aceita controle de volume")
        if acao == "volume":
            _soap(rc, "SetVolume", {"InstanceID": 0, "Channel": "Master", "DesiredVolume": max(0, min(100, int(valor or 0)))})
        else:
            _soap(rc, "SetMute", {"InstanceID": 0, "Channel": "Master", "DesiredMute": 1 if acao == "mudo" else 0})
        return
    av = sv.get("AVTransport")
    if not av:
        raise ValueError("esse aparelho não aceita tocar/pausar pela rede")
    args = {"InstanceID": 0} | ({"Speed": 1} if acao == "tocar" else {})
    _soap(av, {"tocar": "Play", "pausar": "Pause", "parar": "Stop"}[acao], args)


def rele(aparelho: dict[str, Any], ligar: bool) -> None:
    ip = aparelho["ip"]
    if aparelho["tipo"] == "Tasmota":
        _http(f"http://{ip}/cm?cmnd=Power%20{'On' if ligar else 'Off'}")
    elif aparelho.get("geracao", 1) >= 2:
        _http(f"http://{ip}/rpc/Switch.Set?id=0&on={'true' if ligar else 'false'}")
    else:
        _http(f"http://{ip}/relay/0?turn={'on' if ligar else 'off'}")


def sondar_rele(ip: str) -> dict[str, Any] | None:
    """Um IP digitado pelo Senhor: e Shelly ou Tasmota?"""
    try:
        d = json.loads(_http(f"http://{ip}/shelly", timeout=2))
        return {"tipo": "Shelly", "geracao": int(d.get("gen", 1)), "modelo": d.get("model") or d.get("type", "")}
    except (*ERROS, json.JSONDecodeError):
        pass
    try:
        d = json.loads(_http(f"http://{ip}/cm?cmnd=Status", timeout=2))
        if "Status" in d:
            return {"tipo": "Tasmota", "geracao": 1, "modelo": (d["Status"].get("DeviceName") or "")}
    except (*ERROS, json.JSONDecodeError):
        pass
    return None


class HomeAssistant:
    """Cliente do Home Assistant (REST): estados e servicos."""

    def __init__(self, url: str, token: str) -> None:
        self.url, self._token = url.rstrip("/"), token
        self._cache: tuple[float, list[dict[str, Any]]] = (0.0, [])

    def _cab(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def estados(self) -> list[dict[str, Any]]:
        if time.time() - self._cache[0] < 30:
            return self._cache[1]
        d = json.loads(_http(f"{self.url}/api/states", cabecalhos=self._cab(), timeout=5))
        self._cache = (time.time(), d)
        return d

    def servico(self, dominio: str, servico: str, dados: dict[str, Any]) -> None:
        _http(f"{self.url}/api/services/{dominio}/{servico}", json.dumps(dados).encode(), self._cab(), "POST", 6)
        self._cache = (0.0, [])


DOMINIOS_CONTROLAVEIS = ("light", "switch", "fan", "cover", "lock", "media_player", "climate", "input_boolean", "scene")


def achar_entidade(estados: list[dict[str, Any]], alvo: str) -> dict[str, Any] | None:
    """Entidade do Home Assistant cujo nome mais combina com o que o Senhor disse."""
    palavras = set(_norm(alvo).split()) - {"o", "a", "os", "as", "de", "do", "da"}
    sinon = {"luz": {"luz", "luzes", "lampada", "light"}, "tomada": {"tomada", "plug", "switch"}}
    melhor = None
    for e in estados:
        dominio = e.get("entity_id", "").split(".")[0]
        if dominio not in DOMINIOS_CONTROLAVEIS:
            continue
        nome = _norm((e.get("attributes") or {}).get("friendly_name") or e["entity_id"])
        termos = set(nome.split()) | set(_norm(e["entity_id"].split(".")[1]).split())
        if dominio == "light":
            termos |= sinon["luz"]
        nota = len(palavras & termos) + sum(0.5 for p in palavras for t in termos if p != t and len(p) > 3 and (p in t or t in p))
        if nota and (melhor is None or nota > melhor[0]):
            melhor = (nota, e)
    return melhor[1] if melhor and melhor[0] >= max(1, len(palavras) * 0.5) else None


class Casa:
    def __init__(self, arquivo: Path = REGISTRO) -> None:
        self._arquivo = arquivo
        self._trava = threading.Lock()

    def ler(self) -> dict[str, Any]:
        try:
            d = json.loads(self._arquivo.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {"aparelhos": []}
        except (OSError, ValueError):
            return {"aparelhos": []}

    def _gravar(self, d: dict[str, Any]) -> None:
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self._arquivo)

    def descobrir(self) -> list[dict[str, Any]]:
        achados: list[dict[str, Any]] = []
        fios = [threading.Thread(target=lambda: achados.extend(descobrir_ssdp()), daemon=True),
                threading.Thread(target=lambda: achados.extend(descobrir_mdns()), daemon=True)]
        for f in fios:
            f.start()
        for f in fios:
            f.join(8)
        with self._trava:
            d = self.ler()
            manuais = [a for a in d.get("aparelhos", []) if a.get("manual")]
            apelidos = {a["id"]: a.get("apelido") for a in d.get("aparelhos", []) if a.get("apelido")}
            for a in achados:
                if a["id"] in apelidos:
                    a["apelido"] = apelidos[a["id"]]
            d = {"aparelhos": manuais + achados, "descoberto_em": time.time()}
            self._gravar(d)
        return d["aparelhos"]

    def adicionar_manual(self, ip: str, apelido: str, info: dict[str, Any]) -> dict[str, Any]:
        with self._trava:
            d = self.ler()
            a = {"id": f"manual:{ip}", "nome": apelido, "apelido": apelido, "ip": ip, "manual": True, "protocolo": "http", **info}
            d["aparelhos"] = [x for x in d.get("aparelhos", []) if x["id"] != a["id"]] + [a]
            self._gravar(d)
        return a

    def achar(self, alvo: str, tipos: tuple[str, ...] = ()) -> dict[str, Any] | None:
        n = _norm(alvo)
        aparelhos = [a for a in self.ler().get("aparelhos", []) if not tipos or a["tipo"] in tipos]
        for a in aparelhos:
            if a.get("apelido") and _norm(a["apelido"]) in n:
                return a
        for a in aparelhos:
            if _norm(a["nome"]) and (_norm(a["nome"]) in n or n in _norm(a["nome"])):
                return a
        if re.search(r"\b(?:tv|televisao|televisor|som|caixa de som)\b", n):
            return next((a for a in aparelhos if a["tipo"] == "midia"), None)
        return None


def resumo_falado(aparelhos: list[dict[str, Any]]) -> str:
    if not aparelhos:
        return "Não achei nenhum aparelho respondendo na rede de casa."
    nomes = []
    for a in aparelhos[:10]:
        extra = "" if a["tipo"] in ("upnp", "web") else f" ({a['tipo']})"
        nomes.append((a.get("apelido") or a["nome"]) + extra)
    controlaveis = sum(1 for a in aparelhos if a["tipo"] in ("midia", "Shelly", "Tasmota", "Home Assistant"))
    return (f"Achei {len(aparelhos)} aparelho{'s' if len(aparelhos) > 1 else ''} na rede: " + "; ".join(nomes)
            + f". {controlaveis} deles eu consigo controlar direto." if controlaveis else
            f"Achei {len(aparelhos)} aparelho{'s' if len(aparelhos) > 1 else ''} na rede: " + "; ".join(nomes)
            + ". Nenhum com controle aberto; com o Home Assistant eu controlo mais coisas.")
