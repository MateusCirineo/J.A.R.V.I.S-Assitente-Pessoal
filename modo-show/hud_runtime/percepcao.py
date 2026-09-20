"""Percepcao do ambiente: o Jarvis sabe o que ha na regiao que ele pode ver.

Como no video de referencia ("entender com clareza qualquer objeto e o mundo
ao seu redor... limitado a regiao que eu defini"): uma foto da REGIAO vai ao
modelo de visao LOCAL, que devolve os objetos (nome, detalhe legivel como
marca/titulo, posicao) e uma frase sobre a cena. Com isso:
  "o que você está vendo?"   -> lista na hora (se o retrato e recente)
  "onde está meu celular?"   -> posicao na regiao (esquerda, centro, direita...)
  "o que mudou?"             -> compara com o retrato anterior
e a tela desenha uma etiqueta sobre cada objeto.

Pessoas: so "pessoa" (nunca quem e). Nada e gravado; so o ultimo e o
penultimo retrato ficam na memoria. Sai o formato por esquema JSON (o modelo
as vezes devolve JSON malformado sem isso).
"""

from __future__ import annotations

import json
import math
from collections import Counter
import re
import threading
import time
import unicodedata
from typing import Any, Callable

ESQUEMA = {
    "type": "object",
    "properties": {
        "objetos": {"type": "array", "items": {"type": "object", "properties": {
            "nome": {"type": "string"}, "detalhe": {"type": "string"},
            "caixa": {"type": "array", "items": {"type": "integer"}}}, "required": ["nome", "caixa"]}},
        "cena": {"type": "string"},
    },
    "required": ["objetos", "cena"],
}
INSTRUCAO = (
    "Você é a percepção visual do J.A.R.V.I.S. Liste até 8 objetos visíveis nesta imagem. nome: curto, em "
    "português. detalhe: o que der para ler ou reconhecer (marca, modelo, título e autor de livro, cor); vazio "
    "se não souber, sem inventar. caixa: [x1, y1, x2, y2] de 0 a 1000 (canto superior esquerdo = 0,0). "
    "Uma pessoa é só \"pessoa\": nunca diga quem é. cena: uma frase curta sobre o ambiente."
)
VALIDADE_S = 180


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def posicao(o: dict[str, Any]) -> str:
    """Centro da caixa (fracoes da regiao) -> "a esquerda, em cima"."""
    cx, cy = o["x"] + o["w"] / 2, o["y"] + o["h"] / 2
    horiz = "à esquerda" if cx < 0.36 else "à direita" if cx > 0.64 else "no centro"
    vert = "em cima" if cy < 0.36 else "embaixo" if cy > 0.64 else ""
    return f"{horiz}{', ' + vert if vert else ''}"


def ler_resposta(bruto: str) -> dict[str, Any]:
    """JSON do modelo -> objetos com caixa em fracoes (0-1) da regiao, sanitizados."""
    try:
        d = json.loads(bruto)
    except ValueError:
        m = re.search(r"\{.*\}", bruto or "", re.S)
        try:
            d = json.loads(m.group(0)) if m else {}
        except ValueError:
            d = {}
    if not isinstance(d, dict):
        d = {}
    objetos = []
    lista = d.get("objetos")
    for o in (lista if isinstance(lista, list) else [])[:8]:
        if not isinstance(o, dict):
            continue
        nome = str(o.get("nome") or "").strip()[:40]
        cx = o.get("caixa") or []
        if not nome or not isinstance(cx, list) or len(cx) != 4 or not all(
                isinstance(v, (int, float)) and math.isfinite(v) for v in cx):
            continue
        x1, y1, x2, y2 = (max(0.0, min(1000.0, float(v))) / 1000 for v in cx)
        if x2 - x1 < 0.01 or y2 - y1 < 0.01:
            continue
        if _norm(nome) in ("rosto", "homem", "mulher", "menino", "menina"):
            nome = "pessoa"                                   # nunca quem e
        objetos.append({"nome": nome, "detalhe": str(o.get("detalhe") or "").strip()[:80],
                        "x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1,
                        "estado_evidencia": "descrição do modelo visual; não verificada"})
    return {"objetos": objetos, "cena": str(d.get("cena") or "").strip()[:200]}


class Percepcao:
    def __init__(self, perguntar: Callable[..., str], estado: Any = None) -> None:
        self._perguntar = perguntar                # Visao.perguntar_imagem
        self._estado = estado
        self.atual: dict[str, Any] | None = None
        self.anterior: dict[str, Any] | None = None
        self._trava = threading.Lock()

    def recente(self) -> bool:
        return bool(self.atual) and time.time() - self.atual["em"] < VALIDADE_S

    def observar(self, img_bgr: Any, regiao: str = "", caixa_regiao: tuple[float, float, float, float] = (0, 0, 1, 1)
                 ) -> dict[str, Any] | None:
        """Uma olhada na regiao. Devolve o retrato (ou None se ja ha uma olhada em andamento)."""
        import cv2
        if not self._trava.acquire(blocking=False):
            return None
        try:
            t0 = time.time()
            h, w = img_bgr.shape[:2]
            if w > 448:
                img_bgr = cv2.resize(img_bgr, (448, max(1, round(h * 448 / w))), interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                return None
            bruto = self._perguntar(buf.tobytes(), INSTRUCAO, 400, formato=ESQUEMA)
            r = ler_resposta(bruto)
            r.update(em=t0, analisado_em=time.time(), fonte="camera",
                     duracao_s=round(time.time() - t0, 1), regiao=regiao, caixa_regiao=list(caixa_regiao),
                     evidencia_disponivel="descrição em memória; imagem não armazenada")
            self.anterior, self.atual = self.atual, r
            if self._estado is not None:
                rx, ry, rw, rh = caixa_regiao                   # para a tela: fracoes do QUADRO inteiro
                self._estado.atualizar("percepcao", em=r["em"], cena=r["cena"], regiao=regiao,
                                       duracao_s=r["duracao_s"],
                                       objetos=[{**o, "x": rx + o["x"] * rw, "y": ry + o["y"] * rh,
                                                 "w": o["w"] * rw, "h": o["h"] * rh} for o in r["objetos"]])
            return r
        finally:
            self._trava.release()

    # ---- respostas ------------------------------------------------------------------
    def descrever(self, r: dict[str, Any] | None = None) -> str:
        r = r or self.atual
        if not r:
            return "Ainda não olhei a região. Ligue a câmera."
        itens = [o["nome"] + (f", {o['detalhe']}" if o["detalhe"] else "") for o in r["objetos"]]
        antiga = time.time() - r["em"] >= VALIDADE_S
        partes = [("Vi: " if antiga else "Vejo: ") + "; ".join(itens) + "." if itens
                  else "Não identifiquei objetos em destaque naquela imagem."]
        if r["cena"]:
            cena = r["cena"].strip().rstrip(".")
            partes.append(cena[:1].upper() + cena[1:] + ".")
        partes.append(f"Observação de {time.strftime('%H:%M:%S', time.localtime(r['em']))}.")
        if antiga:
            partes.append("É a última observação; não posso afirmar que a cena continua assim.")
        return " ".join(partes)

    def onde_esta(self, coisa: str) -> str:
        if not self.atual:
            return "Ainda não olhei a região. Ligue a câmera e o olhar automático."
        alvo = {p for p in re.findall(r"\w{3,}", _norm(coisa)) if p not in {"meu", "minha", "meus", "minhas", "esta", "estao"}}
        achados = [o for o in self.atual["objetos"]
                   if alvo & set(re.findall(r"\w{3,}", _norm(o["nome"] + " " + o["detalhe"])))]
        idade = round((time.time() - self.atual["em"]) / 60)
        quando = "agora há pouco" if idade < 2 else f"há {idade} minutos"
        if not achados:
            return f"Não vi {coisa} na região quando olhei {quando}."
        if len(achados) > 1:
            return (f"Vi {len(achados)} candidatos {quando}: "
                    + "; ".join(f"{o['nome']} {posicao(o)}" for o in achados)
                    + ". Qual deles você quer localizar?")
        o = achados[0]
        return (f"Vi {o['nome']}{' (' + o['detalhe'] + ')' if o['detalhe'] else ''} {posicao(o)} da região, {quando}."
                + (" Não sei se ainda está lá." if not self.recente() else ""))

    def mudou(self) -> str:
        if not (self.atual and self.anterior):
            return "Ainda não tenho duas olhadas para comparar."
        if (self.anterior.get("regiao"), self.anterior.get("caixa_regiao")) != (
                self.atual.get("regiao"), self.atual.get("caixa_regiao")):
            return "As observações são de regiões diferentes; não posso comparar a mudança da mesma cena."
        antes = Counter(_norm(o["nome"]) for o in self.anterior["objetos"])
        agora = Counter(_norm(o["nome"]) for o in self.atual["objetos"])
        novos = [f"{q} {n}" if q > 1 else n for n, q in (agora - antes).items()]
        sairam = [f"{q} {n}" if q > 1 else n for n, q in (antes - agora).items()]
        if not novos and not sairam:
            return ("As categorias e quantidades descritas são as mesmas nas duas observações. "
                    "Isso não comprova que sejam as mesmas unidades nem que nada tenha se movido.")
        partes = []
        if novos:
            partes.append("Apareceu " + ", ".join(novos))
        if sairam:
            partes.append("saiu " + ", ".join(sairam))
        return "; ".join(partes).capitalize() + "."
