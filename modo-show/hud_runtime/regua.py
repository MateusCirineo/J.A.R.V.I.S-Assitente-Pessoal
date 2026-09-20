"""Regua virtual: mede objetos na mesa pela camera (o video de referencia fazia
isso "no olho" pelo modelo; aqui e medido).

Calibracao (uma vez, com a camera parada): uma folha A4 (ou carta, ou um cartao
de credito) deitada na mesa, de frente para a camera. Os 4 cantos dela dao a
perspectiva da mesa (homografia imagem -> centimetros). Depois, "quanto mede
isso?" pega o objeto (caixa do detector ou o maior contorno na regiao), acha o
retangulo girado que o contem e converte os cantos para centimetros.

Vale para objetos baixos, deitados na mesa: a altura do objeto engana a
perspectiva (a resposta diz "cerca de"). Se a camera mexer, recalibrar.
Guardado em ~/.openjarvis/hud-regua.json (so numeros, nenhuma imagem).
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
REFERENCIAS = {"a4": ("uma folha A4", 29.7, 21.0), "carta": ("uma folha carta", 27.94, 21.59),
               "cartao": ("um cartão de crédito", 8.56, 5.398)}
VALIDADE_CALIBRACAO_S = 24 * 3600  # exige confirmação do plano após um dia


def ordenar_cantos(pts) -> Any:
    """4 pontos -> [cima-esq, cima-dir, baixo-dir, baixo-esq]."""
    import numpy as np
    p = np.asarray(pts, np.float32).reshape(4, 2)
    s, d = p.sum(1), np.diff(p, axis=1).ravel()
    return np.array([p[s.argmin()], p[d.argmin()], p[s.argmax()], p[d.argmax()]], np.float32)


def achar_referencia(img_bgr, proporcao: float, area_min: float = 0.01) -> Any | None:
    """Maior quadrilatero convexo com a proporcao da referencia (folha clara ou borda nitida)."""
    import cv2
    import numpy as np
    cinza = cv2.GaussianBlur(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    total = cinza.shape[0] * cinza.shape[1]
    _, claro = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bordas = cv2.dilate(cv2.Canny(cinza, 40, 120), np.ones((3, 3), np.uint8))
    melhor = None
    for mascara in (cv2.morphologyEx(claro, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)), bordas):
        contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in sorted(contornos, key=cv2.contourArea, reverse=True)[:8]:
            area = cv2.contourArea(c)
            if area < area_min * total or area > 0.95 * total:
                continue
            ap = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
            if len(ap) != 4 or not cv2.isContourConvex(ap):
                continue
            (_, _), (a, b), _ = cv2.minAreaRect(ap)
            if min(a, b) <= 0:
                continue
            if not 0.7 * proporcao <= max(a, b) / min(a, b) <= 2.3 * proporcao:  # a perspectiva deforma MUITO
                continue
            if melhor is None or area > melhor[0]:
                melhor = (area, ordenar_cantos(ap))
        if melhor:
            return melhor[1]
    return None


class Regua:
    def __init__(self, arquivo: Path = HOME / "hud-regua.json") -> None:
        self._arquivo = arquivo
        self._dados = self._ler()

    def _ler(self) -> dict[str, Any] | None:
        try:
            import numpy as np
            d = json.loads(self._arquivo.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                return None
            h = np.asarray(d.get("h"), dtype=float)
            if h.shape != (3, 3) or not np.isfinite(h).all() or abs(np.linalg.det(h)) < 1e-12:
                return None
            return d if d.get("largura", 0) > 0 and d.get("altura", 0) > 0 else None
        except (OSError, ValueError, TypeError):
            return None

    @property
    def calibrada(self) -> bool:
        return self._dados is not None and 0 <= time.time() - self._dados.get("em", 0) <= VALIDADE_CALIBRACAO_S

    def invalidar(self) -> None:
        """Usar quando a câmera/posição/plano mudar; mantém arquivo para auditoria."""
        if self._dados is not None:
            self._dados["em"] = 0

    def calibrar(self, img_bgr, referencia: str = "a4") -> dict[str, Any] | None:
        """Acha a referencia e guarda a perspectiva. None = nao achou."""
        import cv2
        import numpy as np
        nome, longo, curto = REFERENCIAS.get(referencia, REFERENCIAS["a4"])
        cantos = achar_referencia(img_bgr, longo / curto)
        if cantos is None:
            return None
        topo = np.linalg.norm(cantos[1] - cantos[0])
        lado = np.linalg.norm(cantos[3] - cantos[0])
        lx, ly = (longo, curto) if topo >= lado else (curto, longo)          # lado maior da imagem = lado maior do papel
        destino = np.array([[0, 0], [lx, 0], [lx, ly], [0, ly]], np.float32)
        h = cv2.getPerspectiveTransform(cantos, destino)
        altura, largura = img_bgr.shape[:2]
        self._dados = {"h": h.tolist(), "referencia": referencia, "largura": largura, "altura": altura,
                       "cantos": (cantos / [largura, altura]).tolist(), "em": time.time()}
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._arquivo.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._dados), encoding="utf-8")
        os.replace(tmp, self._arquivo)
        return self._dados

    def para_cm(self, pontos_px, tamanho: tuple[int, int]) -> Any:
        """Pontos em pixels do quadro atual -> centimetros no plano da mesa."""
        import cv2
        import numpy as np
        d = self._dados
        if not self.calibrada:
            raise ValueError("calibração ausente ou antiga; recalibre a régua")
        p = np.asarray(pontos_px, np.float32).reshape(-1, 1, 2)
        largura, altura = tamanho
        if (largura, altura) != (d["largura"], d["altura"]):                  # outra resolucao: reescala
            p = p * np.array([d["largura"] / largura, d["altura"] / altura], np.float32)
        return cv2.perspectiveTransform(p, np.array(d["h"], np.float64)).reshape(-1, 2)

    def contorno_do_objeto(self, img_bgr, caixa: tuple[float, float, float, float] | None) -> Any | None:
        """Contorno (pontos em px) do objeto na caixa (fracoes) ou na imagem toda.
        Separa pela COR diferente da mesa em volta (mediana da borda do recorte) e pelas bordas."""
        import cv2
        import numpy as np
        altura, largura = img_bgr.shape[:2]
        x0, y0, x1, y1 = 0, 0, largura, altura
        if caixa:
            x, y, w, h = caixa
            folga = 0.04
            x0, y0 = max(0, int((x - folga) * largura)), max(0, int((y - folga) * altura))
            x1, y1 = min(largura, int((x + w + folga) * largura)), min(altura, int((y + h + folga) * altura))
        recorte = img_bgr[y0:y1, x0:x1]
        if recorte.size == 0 or min(recorte.shape[:2]) < 8:
            return None
        borda = np.concatenate([recorte[0], recorte[-1], recorte[:, 0], recorte[:, -1]]).astype(np.int16)
        fundo = np.median(borda, axis=0)
        diferente = (np.abs(recorte.astype(np.int16) - fundo).max(axis=2) > 28).astype(np.uint8) * 255
        cinza = cv2.GaussianBlur(cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        mascara = cv2.bitwise_or(diferente, cv2.Canny(cinza, 40, 120))
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        minimo = (0.02 if caixa else 0.002) * recorte.shape[0] * recorte.shape[1]   # imagem toda: objetos pequenos
        contornos = [c for c in contornos if cv2.contourArea(c) > minimo]
        if contornos:
            return max(contornos, key=cv2.contourArea).reshape(-1, 2).astype(np.float32) + np.array([x0, y0], np.float32)
        if caixa:                                                               # sem nada nitido: a caixa inteira
            return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float32)
        return None

    def para_px(self, pontos_cm, tamanho: tuple[int, int]) -> Any:
        """Centimetros no plano da mesa -> pixels do quadro atual (para desenhar a medida)."""
        import cv2
        import numpy as np
        d = self._dados
        p = cv2.perspectiveTransform(np.asarray(pontos_cm, np.float32).reshape(-1, 1, 2),
                                     np.linalg.inv(np.array(d["h"], np.float64))).reshape(-1, 2)
        largura, altura = tamanho
        return p * np.array([largura / d["largura"], altura / d["altura"]], np.float32)

    def medir(self, img_bgr, caixa: tuple[float, float, float, float] | None = None) -> dict[str, Any] | None:
        """{comprimento, largura (cm), cantos (fracoes do quadro)} ou None. O retangulo e
        ajustado JA no plano da mesa (em cm), onde a perspectiva nao deforma."""
        import cv2
        import numpy as np
        if not self.calibrada:
            return None
        altura, largura = img_bgr.shape[:2]
        proporcao = self._dados["largura"] / self._dados["altura"]
        if abs((largura / altura) / proporcao - 1) > 0.01:
            self.invalidar()
            return None
        contorno = self.contorno_do_objeto(img_bgr, caixa)
        if contorno is None:
            return None
        altura, largura = img_bgr.shape[:2]
        em_cm = self.para_cm(contorno, (largura, altura)).astype(np.float32)
        retangulo = cv2.minAreaRect(em_cm)
        a, b = retangulo[1]
        cantos = self.para_px(cv2.boxPoints(retangulo), (largura, altura))
        return {"comprimento": round(float(max(a, b)), 1), "largura": round(float(min(a, b)), 1),
                "cantos": (ordenar_cantos(cantos) / [largura, altura]).round(4).tolist(),
                "fonte": "câmera + homografia calibrada", "unidade": "cm", "em": time.time(),
                "calibrada_em": self._dados["em"], "metodo": "retângulo do contorno projetado no plano",
                "limites": "Somente o plano calibrado; câmera imóvel. Altura e espessura não medidas.",
                "incerteza": "não quantificada; resultado aproximado, não dimensão de catálogo"}


def cm_falado(v: float) -> str:
    if v >= 100:
        return f"{v / 100:.2f}".replace(".", ",") + " metro" + ("s" if v >= 200 else "")
    inteiro = math.isclose(v, round(v), abs_tol=0.05)
    return (f"{round(v)}" if inteiro else f"{v:.1f}".replace(".", ",")) + " centímetros"


def medida_falada(m: dict[str, Any], nome: str | None = None) -> str:
    alvo = f"{nome[0].upper() + nome[1:]} mede" if nome else "Mede"
    return (f"{alvo} cerca de {cm_falado(m['comprimento']).replace(' centímetros', '')} por "
            f"{cm_falado(m['largura'])}.")
