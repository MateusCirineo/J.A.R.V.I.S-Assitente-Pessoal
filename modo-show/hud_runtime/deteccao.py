"""Visao em tempo real: detector de objetos local (YOLOX-S int8 do OpenCV Zoo,
Apache-2.0, 9 MB, 80 tipos do COCO). Roda aqui, no quadro mais recente da camera,
~4 vezes por segundo nesta CPU (~180 ms por quadro), so enquanto a camera esta
ligada. Nada sai da maquina e nada e gravado.

Da a resposta NA HORA ("o que voce esta vendo?", "onde esta meu celular?",
"quantas pessoas tem aqui?") e as caixas ao vivo no HUD; o modelo de visao
(gemma4/qwen) continua fazendo a analise detalhada (marca, modelo, titulo).
Pessoas sao so "pessoa": nada de quem e.

O motor NOVO do OpenCV 5 devolve confianca zero neste modelo int8 (medido):
usa-se o motor classico, que da o mesmo resultado do onnxruntime em ~1/8 do tempo.
"""

from __future__ import annotations

import threading
import time
import unicodedata
from collections import Counter, deque
from pathlib import Path
from typing import Any, Callable

MODELO = Path(__file__).resolve().parent.parent / "modelos" / "object_detection_yolox_2022nov_int8.onnx"
LADO = 640                      # o modelo foi exportado com entrada fixa 640x640

# COCO (ordem do modelo) -> (singular, plural, genero)
CLASSES = [
    ("pessoa", "pessoas", "f"), ("bicicleta", "bicicletas", "f"), ("carro", "carros", "m"), ("moto", "motos", "f"),
    ("avião", "aviões", "m"), ("ônibus", "ônibus", "m"), ("trem", "trens", "m"), ("caminhão", "caminhões", "m"),
    ("barco", "barcos", "m"), ("semáforo", "semáforos", "m"), ("hidrante", "hidrantes", "m"),
    ("placa de pare", "placas de pare", "f"), ("parquímetro", "parquímetros", "m"), ("banco", "bancos", "m"),
    ("pássaro", "pássaros", "m"), ("gato", "gatos", "m"), ("cachorro", "cachorros", "m"), ("cavalo", "cavalos", "m"),
    ("ovelha", "ovelhas", "f"), ("vaca", "vacas", "f"), ("elefante", "elefantes", "m"), ("urso", "ursos", "m"),
    ("zebra", "zebras", "f"), ("girafa", "girafas", "f"), ("mochila", "mochilas", "f"),
    ("guarda-chuva", "guarda-chuvas", "m"), ("bolsa", "bolsas", "f"), ("gravata", "gravatas", "f"),
    ("mala", "malas", "f"), ("frisbee", "frisbees", "m"), ("esqui", "esquis", "m"), ("snowboard", "snowboards", "m"),
    ("bola", "bolas", "f"), ("pipa", "pipas", "f"), ("taco de beisebol", "tacos de beisebol", "m"),
    ("luva de beisebol", "luvas de beisebol", "f"), ("skate", "skates", "m"),
    ("prancha de surfe", "pranchas de surfe", "f"), ("raquete", "raquetes", "f"), ("garrafa", "garrafas", "f"),
    ("taça", "taças", "f"), ("copo", "copos", "m"), ("garfo", "garfos", "m"), ("faca", "facas", "f"),
    ("colher", "colheres", "f"), ("tigela", "tigelas", "f"), ("banana", "bananas", "f"), ("maçã", "maçãs", "f"),
    ("sanduíche", "sanduíches", "m"), ("laranja", "laranjas", "f"), ("brócolis", "brócolis", "m"),
    ("cenoura", "cenouras", "f"), ("cachorro-quente", "cachorros-quentes", "m"), ("pizza", "pizzas", "f"),
    ("rosquinha", "rosquinhas", "f"), ("bolo", "bolos", "m"), ("cadeira", "cadeiras", "f"), ("sofá", "sofás", "m"),
    ("planta", "plantas", "f"), ("cama", "camas", "f"), ("mesa", "mesas", "f"),
    ("vaso sanitário", "vasos sanitários", "m"), ("tela", "telas", "f"), ("notebook", "notebooks", "m"),
    ("mouse", "mouses", "m"), ("controle remoto", "controles remotos", "m"), ("teclado", "teclados", "m"),
    ("celular", "celulares", "m"), ("micro-ondas", "micro-ondas", "m"), ("forno", "fornos", "m"),
    ("torradeira", "torradeiras", "f"), ("pia", "pias", "f"), ("geladeira", "geladeiras", "f"),
    ("livro", "livros", "m"), ("relógio", "relógios", "m"), ("vaso", "vasos", "m"), ("tesoura", "tesouras", "f"),
    ("urso de pelúcia", "ursos de pelúcia", "m"), ("secador de cabelo", "secadores de cabelo", "m"),
    ("escova de dentes", "escovas de dentes", "f"),
]
# como o Senhor chama -> nome da classe
SINONIMOS = {
    "telefone": "celular", "smartphone": "celular", "iphone": "celular", "fone": "celular",
    "laptop": "notebook", "computador": "notebook", "pc": "notebook",
    "tv": "tela", "televisao": "tela", "televisor": "tela", "monitor": "tela",
    "caneca": "copo", "xicara": "copo", "controle": "controle remoto", "vaso de planta": "planta",
    "cao": "cachorro", "cachorrinho": "cachorro", "gatinho": "gato", "passarinho": "passaro", "ave": "passaro",
    "gente": "pessoa", "pessoas": "pessoa", "alguem": "pessoa", "homem": "pessoa", "mulher": "pessoa",
    "crianca": "pessoa", "cadeiras": "cadeira", "livros": "livro", "garrafas": "garrafa", "copos": "copo",
}


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


_POR_NOME = {_norm(s): i for i, (s, p, _) in enumerate(CLASSES)} | {_norm(p): i for i, (s, p, _) in enumerate(CLASSES)}


def classe_citada(texto: str) -> int | None:
    """ "meu celular" / "o controle" / "pessoas" -> indice da classe (ou None)."""
    n = _norm(texto)
    for artigo in ("o ", "a ", "os ", "as ", "meu ", "minha ", "meus ", "minhas ", "um ", "uma "):
        if n.startswith(artigo):
            n = n[len(artigo):]
    n = SINONIMOS.get(n, n)
    if n in _POR_NOME:
        return _POR_NOME[n]
    for chave, i in sorted(_POR_NOME.items(), key=lambda kv: -len(kv[0])):    # "celular preto" -> celular
        if n.startswith(chave + " ") or n.endswith(" " + chave):
            return i
    return None


NAO_OBJETOS = {"mesa", "cadeira", "sofa", "cama", "pia"}       # moveis: sao o lugar, nao o objeto


def classe_na_frase(texto: str) -> int | None:
    """Primeiro objeto citado numa frase ("quanto mede o meu celular?") -> classe.
    Moveis ("na mesa") nao contam: sao onde o objeto esta."""
    palavras = _norm(texto).replace("?", " ").replace(",", " ").split()
    for n in (3, 2, 1):
        for i in range(len(palavras) - n + 1):
            trecho = " ".join(palavras[i:i + n])
            trecho = SINONIMOS.get(trecho, trecho)
            if trecho in _POR_NOME and trecho not in NAO_OBJETOS:
                return _POR_NOME[trecho]
    return None


def quantidade(n: int, classe: int) -> str:
    s, p, g = CLASSES[classe]
    if n == 1:
        return f"{'uma' if g == 'f' else 'um'} {s}"
    if n == 2:
        return f"{'duas' if g == 'f' else 'dois'} {p}"
    return f"{n} {p}"


def juntar(partes: list[str]) -> str:
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]


def resumo(objetos: list[dict[str, Any]], maximo: int = 6) -> str:
    """Lista falada: "uma pessoa, um celular e dois copos" (pessoas primeiro, depois os mais vistos)."""
    cont: dict[int, int] = {}
    for o in objetos:
        cont[o["classe"]] = cont.get(o["classe"], 0) + 1
    ordem = sorted(cont, key=lambda c: (c != 0, -cont[c]))
    return juntar([quantidade(cont[c], c) for c in ordem[:maximo]]) if ordem else ""


class Detector:
    def __init__(self, modelo: Path = MODELO, confianca: float = 0.45, nms: float = 0.5) -> None:
        self._modelo = modelo
        self.confianca, self.nms = confianca, nms
        self._net = None
        self._trava = threading.Lock()
        self.ms: float | None = None

    @property
    def disponivel(self) -> bool:
        return self._modelo.is_file()

    def carregar(self) -> None:
        import cv2
        import numpy as np
        self._net = cv2.dnn.readNetFromONNX(str(self._modelo), engine=cv2.dnn.ENGINE_CLASSIC)
        grades, passos = [], []
        for passo in (8, 16, 32):
            n = LADO // passo
            xv, yv = np.meshgrid(np.arange(n), np.arange(n))
            g = np.stack((xv, yv), 2).reshape(1, -1, 2)
            grades.append(g)
            passos.append(np.full((*g.shape[:2], 1), passo))
        self._grade, self._passo = np.concatenate(grades, 1), np.concatenate(passos, 1)

    def detectar(self, img_bgr) -> list[dict[str, Any]]:
        """Quadro BGR -> [{classe, nome, conf, x, y, w, h}] com a caixa em fracao do quadro."""
        import cv2
        import numpy as np
        with self._trava:
            if self._net is None:
                self.carregar()
            t0 = time.perf_counter()
            h, w = img_bgr.shape[:2]
            r = min(LADO / h, LADO / w)
            nh, nw = int(h * r), int(w * r)
            pad = np.full((LADO, LADO, 3), 114, np.float32)                 # letterbox, como no demo oficial
            pad[:nh, :nw] = cv2.resize(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB), (nw, nh))
            self._net.setInput(pad.transpose(2, 0, 1)[None])
            d = self._net.forward(self._net.getUnconnectedOutLayersNames())[0][0]
            self.ms = (time.perf_counter() - t0) * 1000
        d = d.copy()
        d[:, :2] = (d[:, :2] + self._grade[0]) * self._passo[0]
        d[:, 2:4] = np.exp(d[:, 2:4]) * self._passo[0]
        caixas = np.stack([d[:, 0] - d[:, 2] / 2, d[:, 1] - d[:, 3] / 2, d[:, 2], d[:, 3]], 1)
        notas = d[:, 4:5] * d[:, 5:]
        conf, cls = notas.max(1), notas.argmax(1)
        boas = conf >= self.confianca
        if not boas.any():
            return []
        caixas, conf, cls = caixas[boas], conf[boas], cls[boas]
        manter = cv2.dnn.NMSBoxesBatched(caixas.tolist(), conf.tolist(), cls.tolist(), self.confianca, self.nms)
        saida = []
        for k in np.array(manter).flatten():
            x, y, bw, bh = (float(v) / r for v in caixas[k])
            x0, y0 = max(0.0, x / w), max(0.0, y / h)
            x1, y1 = min(1.0, (x + bw) / w), min(1.0, (y + bh) / h)
            if x1 - x0 < 0.01 or y1 - y0 < 0.01:
                continue
            c = int(cls[k])
            saida.append({"classe": c, "nome": CLASSES[c][0], "conf": round(float(conf[k]), 2),
                          "x": round(x0, 4), "y": round(y0, 4), "w": round(x1 - x0, 4), "h": round(y1 - y0, 4)})
        saida.sort(key=lambda o: -o["conf"])
        return saida[:30]


class VisaoContinua(threading.Thread):
    """Detecta no quadro mais recente enquanto `ativo()`; publica cada resultado.

    Deixa a CPU respirar: depois de cada deteccao dorme pelo menos o mesmo
    tempo que ela levou (no maximo ~50% de um nucleo logico em media) e fica
    bem mais lenta quando o modelo de linguagem esta gerando."""

    def __init__(self, detector: Detector, quadro: Callable[[], Any], ativo: Callable[[], bool],
                 publicar: Callable[[list[dict[str, Any]], float], None], ocupado: Callable[[], bool] = lambda: False,
                 intervalo: float = 0.25) -> None:
        super().__init__(daemon=True, name="visao-continua")
        self.detector, self._quadro, self._ativo, self._publicar = detector, quadro, ativo, publicar
        self._ocupado, self._intervalo = ocupado, intervalo
        self.ultimos: list[dict[str, Any]] = []
        self.em: float = 0.0
        self._historico: deque[list[dict[str, Any]]] = deque(maxlen=3)
        from .rastreador import Rastreador
        # segue o MESMO objeto entre quadros: sem isto "onde esta meu celular"
        # so sabe responder sobre o quadro de agora
        self.rastreador = Rastreador()
        self._visto = None
        self.erro: str | None = None
        self._parar = threading.Event()

    def parar(self) -> None:
        self._parar.set()

    def recentes(self, validade: float = 2.0) -> list[dict[str, Any]] | None:
        """O que foi visto ha menos de `validade` s (None = nada recente)."""
        return list(self.ultimos) if time.time() - self.em <= validade else None

    def estaveis(self, validade: float = 2.5) -> list[dict[str, Any]] | None:
        """Para FALAR: so o que tem >= 55% e apareceu em 2 dos ultimos 3 quadros
        (ou >= 75%); com um quadro so, >= 60%. Um quadro ruim nao vira fala errada."""
        if time.time() - self.em > validade:
            return None
        atuais = [o for o in self.ultimos if o["conf"] >= 0.55]
        hist = list(self._historico)
        if len(hist) < 2:
            return [o for o in atuais if o["conf"] >= 0.6]
        vistos = Counter(c for quadro in hist for c in {o["classe"] for o in quadro})
        return [o for o in atuais if vistos[o["classe"]] >= 2 or o["conf"] >= 0.75]

    def aguardar(self, limite: float = 4.0) -> list[dict[str, Any]] | None:
        """Espera um resultado NOVO (camera acabou de ligar, por exemplo)."""
        pedido, fim = time.time(), time.time() + limite
        while time.time() < fim:
            if self.em >= pedido and len(self._historico) >= 2:
                break
            time.sleep(0.1)
        return self.estaveis()

    def run(self) -> None:
        while not self._parar.is_set():
            if not self._ativo():
                if self.ultimos or self._historico:
                    self.ultimos, self._visto = [], None
                    self._historico.clear()
                    self.rastreador.atualizar([])       # camera desligou: nada e "agora"
                    self._publicar([], 0.0)
                self._parar.wait(0.5)
                continue
            img = self._quadro()
            if img is None or img is self._visto:
                self._parar.wait(0.05)
                continue
            self._visto = img
            t0 = time.perf_counter()
            try:
                objs = self.detector.detectar(img)
                self.erro = None
            except Exception as e:  # noqa: BLE001 - modelo ausente/corrompido: avisa e desiste
                self.erro = str(e)[:160]
                self._publicar([], 0.0)
                self._parar.wait(10)
                continue
            gasto = time.perf_counter() - t0
            self.ultimos, self.em = objs, time.time()
            self._historico.append(objs)
            try:
                self.rastreador.atualizar(objs)
            except Exception:  # noqa: BLE001 - rastrear e bonus; detectar e o principal
                pass
            self._publicar(objs, gasto * 1000)
            espera = max(self._intervalo, gasto) * (4 if self._ocupado() else 1)
            self._parar.wait(espera)


def no_retangulo(o: dict[str, Any], caixa: tuple[float, float, float, float]) -> bool:
    """O centro do objeto esta dentro da regiao (x, y, w, h em fracao do quadro)?"""
    cx, cy = o["x"] + o["w"] / 2, o["y"] + o["h"] / 2
    x, y, w, h = caixa
    return x <= cx <= x + w and y <= cy <= y + h


class Vigia:
    """Modo vigia: com ele armado, uma PESSOA na camera por `firme_s` gera um alerta
    (no maximo um por `intervalo_s`). Arma depois de `espera_s` (tempo de sair da
    sala). So conta "pessoa": nao identifica quem e nem grava nada."""

    def __init__(self, espera_s: float = 20.0, firme_s: float = 1.5, intervalo_s: float = 60.0,
                 relogio: Callable[[], float] = time.time) -> None:
        self.espera_s, self.firme_s, self.intervalo_s, self._relogio = espera_s, firme_s, intervalo_s, relogio
        self.ativo = False
        self.armado_em = 0.0
        self._desde: float | None = None
        self._avisou = float("-inf")

    def ligar(self) -> None:
        self.ativo, self.armado_em = True, self._relogio() + self.espera_s
        self._desde, self._avisou = None, float("-inf")

    def desligar(self) -> bool:
        era, self.ativo = self.ativo, False
        return era

    def ignorar_agora(self) -> None:
        """So gente cadastrada na frente da camera: nao e intrusao (recomeca a contar)."""
        self._desde = None

    @property
    def armado(self) -> bool:
        return self.ativo and self._relogio() >= self.armado_em

    def conferir(self, objs: list[dict[str, Any]]) -> bool:
        """True = alertar agora."""
        if not self.armado:
            return False
        agora = self._relogio()
        if not any(o["classe"] == 0 and o["conf"] >= 0.6 for o in objs):
            self._desde = None
            return False
        self._desde = self._desde if self._desde is not None else agora
        if agora - self._desde >= self.firme_s and agora - self._avisou >= self.intervalo_s:
            self._avisou = agora
            return True
        return False
