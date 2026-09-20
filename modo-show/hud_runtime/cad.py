"""Projeto parametrico -> arquivo STL (para ver na mesa holografica e imprimir no Cura).

Pecas: caixa (macica ou aberta com parede), cilindro, tubo, esfera, cone e
engrenagem de dentes retos com perfil EVOLVENTE de verdade (angulo de pressao
20 graus, modulo pelo diametro externo), com furo central opcional.

Tudo em milimetros. O volume vem da propria malha (soma de tetraedros) e a
massa usa a densidade do material (PLA por padrao, a da impressao 3D).
"""

from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Iterable

Tri = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


def _quad(a, b, c, d) -> list[Tri]:
    return [(a, b, c), (a, c, d)]


def extrudar_estrela(contorno: list[tuple[float, float]], furo: float, altura: float) -> list[Tri]:
    """Perfil "estrelado" a partir do centro (cada angulo tem um raio: engrenagem,
    circulo) extrudado em Z, com furo redondo opcional. Faces viradas para fora."""
    n = len(contorno)
    tris: list[Tri] = []
    angs = [math.atan2(y, x) for x, y in contorno]
    dentro = [(furo * math.cos(a), furo * math.sin(a)) for a in angs] if furo > 0 else None
    for i in range(n):
        j = (i + 1) % n
        (x1, y1), (x2, y2) = contorno[i], contorno[j]
        tris += _quad((x1, y1, 0), (x2, y2, 0), (x2, y2, altura), (x1, y1, altura))       # parede de fora
        if dentro:
            (u1, v1), (u2, v2) = dentro[i], dentro[j]
            tris += _quad((u1, v1, altura), (x1, y1, altura), (x2, y2, altura), (u2, v2, altura))   # tampa
            tris += _quad((u2, v2, 0), (x2, y2, 0), (x1, y1, 0), (u1, v1, 0))                         # fundo
            tris += _quad((u2, v2, 0), (u1, v1, 0), (u1, v1, altura), (u2, v2, altura))               # parede do furo
        else:
            tris.append(((0, 0, altura), (x1, y1, altura), (x2, y2, altura)))
            tris.append(((0, 0, 0), (x2, y2, 0), (x1, y1, 0)))
    return tris


def circulo(r: float, n: int = 96) -> list[tuple[float, float]]:
    return [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def cilindro(diametro: float, altura: float) -> list[Tri]:
    return extrudar_estrela(circulo(diametro / 2), 0, altura)


def tubo(externo: float, interno: float, altura: float) -> list[Tri]:
    if not 0 < interno < externo:
        raise ValueError("o diâmetro interno precisa ser menor que o externo")
    return extrudar_estrela(circulo(externo / 2), interno / 2, altura)


def caixa(c: float, l: float, a: float, parede: float | None = None) -> list[Tri]:
    """Macica, ou aberta em cima com paredes (e fundo) da espessura dada."""
    def bloco(x0, y0, z0, x1, y1, z1) -> list[Tri]:
        p = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        return [t for f in faces for t in _quad(*(p[i] for i in f))]
    if not parede:
        return bloco(0, 0, 0, c, l, a)
    if parede * 2 >= min(c, l) or parede >= a:
        raise ValueError("a parede é grossa demais para essa caixa")
    e = parede                                    # fundo + 4 paredes (blocos que se tocam: bom para fatiar)
    return (bloco(0, 0, 0, c, l, e) + bloco(0, 0, e, c, e, a) + bloco(0, l - e, e, c, l, a)
            + bloco(0, e, e, e, l - e, a) + bloco(c - e, e, e, c, l - e, a))


def esfera(diametro: float, n: int = 48) -> list[Tri]:
    r, tris = diametro / 2, []
    def p(i, j):
        t, f = math.pi * i / n, 2 * math.pi * j / n
        return (r * math.sin(t) * math.cos(f), r * math.sin(t) * math.sin(f), r * math.cos(t))
    for i in range(n):
        for j in range(n):
            a, b, c, d = p(i, j), p(i + 1, j), p(i + 1, j + 1), p(i, j + 1)
            if i == 0:
                tris.append((a, b, c))
            elif i == n - 1:
                tris.append((a, b, d))
            else:
                tris += _quad(a, b, c, d)
    return tris


def cone(diametro: float, altura: float, n: int = 96) -> list[Tri]:
    base = circulo(diametro / 2, n)
    tris = []
    for i in range(n):
        (x1, y1), (x2, y2) = base[i], base[(i + 1) % n]
        tris.append(((x1, y1, 0), (x2, y2, 0), (0, 0, altura)))
        tris.append(((0, 0, 0), (x2, y2, 0), (x1, y1, 0)))
    return tris


def perfil_engrenagem(dentes: int, externo: float, pressao: float = 20.0, pontos: int = 10) -> list[tuple[float, float]]:
    """Contorno de engrenagem reta com flancos em evolvente. externo = diametro de cabeca."""
    if dentes < 6:
        raise ValueError("uma engrenagem precisa de pelo menos 6 dentes")
    m = externo / (dentes + 2)                                # modulo
    rp, rb = m * dentes / 2, m * dentes / 2 * math.cos(math.radians(pressao))
    ra, rf = rp + m, max(rp - 1.25 * m, 0.5 * rp)
    inv = lambda a: math.tan(a) - a                           # noqa: E731
    meia = math.pi / (2 * dentes) + inv(math.radians(pressao))   # meia espessura angular na base
    def flanco(sinal: float) -> list[tuple[float, float]]:
        pts = []
        r0 = max(rb, rf)
        for k in range(pontos + 1):
            r = r0 + (ra - r0) * k / pontos
            alfa = math.acos(min(1.0, rb / r))
            pts.append((r, sinal * (meia - inv(alfa))))
        return pts
    contorno = []
    passo = 2 * math.pi / dentes
    for d in range(dentes):
        c = d * passo
        dir_ = flanco(-1)                                     # sobe pelo flanco de um lado...
        esq = flanco(1)[::-1]                                  # ...e desce pelo outro
        if rf < rb:
            contorno.append((rf, c - meia - 0.02))
        contorno += [(r, c + a) for r, a in dir_]
        contorno += [(r, c + a) for r, a in esq]
        if rf < rb:
            contorno.append((rf, c + meia + 0.02))
        contorno.append((rf, c + passo / 2))                  # fundo do vao
    return [(r * math.cos(a), r * math.sin(a)) for r, a in contorno]


def engrenagem(dentes: int, externo: float, espessura: float, furo: float = 0.0) -> list[Tri]:
    if furo and furo >= externo * 0.6:
        raise ValueError("o furo é grande demais para essa engrenagem")
    return extrudar_estrela(perfil_engrenagem(dentes, externo), furo / 2, espessura)


def volume_mm3(tris: Iterable[Tri]) -> float:
    v = 0.0
    for (a, b, c) in tris:
        v += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    return abs(v)


def salvar_stl(tris: list[Tri], caminho: Path, nome: str = "jarvis") -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "wb") as f:
        f.write(nome.encode("ascii", "replace")[:80].ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
            vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            f.write(struct.pack("<12fH", nx / ln, ny / ln, nz / ln, *a, *b, *c, 0))
    return caminho


def pasta_projetos() -> Path:
    return Path.home() / "Documents" / "Jarvis" / "Projetos"
