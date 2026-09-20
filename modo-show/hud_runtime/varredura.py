"""Varredura de imagens sensiveis com quarentena reversivel (projeto C, adaptado).

"Jarvis, verifique as imagens da pasta Downloads"
1. ANALISA sem mover nada: relatorio com caminho, tamanho e SHA-256 de cada
   imagem e o parecer do classificador (~/.openjarvis/varreduras/<id>.json).
2. So com "confirmo quarentena" move as sinalizadas para
   ~/.openjarvis/quarentena/<id>/, conferindo antes que o arquivo nao mudou
   desde a analise (mesmo hash). Manifesto com a origem de cada uma.
3. "restaure a quarentena" devolve cada arquivo ao lugar (sem sobrescrever
   nada: se o nome estiver ocupado, restaura com "(restaurado)" no nome) e
   confere o hash.
Nunca apaga. O classificador so sugere; a decisao de mover e do usuario.
Classificador: NudeNet em duas resolucoes (como no projeto C): o 320n faz a
triagem e o 640m confirma; o que so o 320n acusar fica "incerto" (para revisar,
nunca movido). Sem NudeNet, o modelo de visao LOCAL (Ollama), mais lento.
Categorias: so nudez explicita por padrao; pes, barriga, axilas e peito
masculino NAO contam. A heuristica de "cor de pele" do projeto C fica de fora
(muitos falsos positivos). Icones pequenos sao ignorados. Tudo local.

Situacoes: sensivel | incerto | ok | ignorada | nao_analisada. So "sensivel"
pode ir para a quarentena, e so com confirmacao.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))
MODELOS = Path(__file__).resolve().parent.parent / "modelos"
EXTS_IMG = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MIN_LADO = 80                                   # menor que isso e icone/miniatura: ignora
CATEGORIAS_PADRAO = {"FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED", "FEMALE_BREAST_EXPOSED",
                     "ANUS_EXPOSED", "BUTTOCKS_EXPOSED"}
MAX_BYTES = 25 * 1024 * 1024
PERGUNTA = ("Responda com UMA palavra, SIM ou NAO. Esta imagem mostra nudez, genitália exposta ou ato sexual "
            "explícito? Roupas de banho, abraços e beijos comuns não contam.")


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def imagens(pasta: Path, profundidade: int = 1, limite: int = 60) -> tuple[list[Path], int]:
    """As mais recentes primeiro. Devolve (lista ate o limite, total encontrado)."""
    achadas = []
    pilha = [(pasta, 0)]
    while pilha:
        p, nivel = pilha.pop()
        try:
            itens = list(p.iterdir())
        except OSError:
            continue
        for x in itens:
            if x.is_dir():
                if nivel < profundidade and not x.name.startswith((".", "$")):
                    pilha.append((x, nivel + 1))
            elif x.suffix.lower() in EXTS_IMG:
                try:
                    if x.stat().st_size <= MAX_BYTES:
                        achadas.append(x)
                except OSError:
                    pass
    achadas.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return achadas[:limite], len(achadas)


def classificador_visao(perguntar_imagem: Callable[[bytes, str, int], str]) -> Callable[[Path], tuple[bool, str]]:
    """Usa o modelo de visao local: (sensivel?, motivo)."""
    def classificar(caminho: Path) -> tuple[bool, str]:
        import cv2
        import numpy as np
        img = cv2.imdecode(np.fromfile(str(caminho), np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("imagem ilegível")
        h, w = img.shape[:2]
        if min(h, w) < MIN_LADO:
            return "ignorada", f"ícone ou miniatura ({w}x{h})"
        if max(h, w) > 512:
            f = 512 / max(h, w)
            img = cv2.resize(img, (round(w * f), round(h * f)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("falha ao preparar a imagem")
        resposta = (perguntar_imagem(buf.tobytes(), PERGUNTA, 6) or "").strip().upper()
        if resposta.startswith("SIM"):
            return "sensivel", "modelo de visão local: sinalizou"
        if resposta.startswith("NAO") or resposta.startswith("NÃO"):
            return "ok", "modelo de visão local: não sinalizou"
        return "incerto", "modelo de visão local: resposta ambígua"
    return classificar


def _tamanho(dados: bytes) -> tuple[int, int] | None:
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(dados, np.uint8), cv2.IMREAD_REDUCED_GRAYSCALE_2)
    return None if img is None else (img.shape[1] * 2, img.shape[0] * 2)


def classificador_nudenet(categorias: set[str] | None = None, modelos: Path = MODELOS
                          ) -> Callable[[Path], tuple[str, str]] | None:
    """NudeNet 320n (triagem) + 640m (confirmacao), se instalados."""
    try:
        from nudenet import NudeDetector
    except ImportError:
        return None
    categorias = categorias or CATEGORIAS_PADRAO
    rapido = NudeDetector()                                         # 320n, vem no pacote
    arq640 = modelos / "nudenet-640m.onnx"
    preciso = NudeDetector(model_path=str(arq640), inference_resolution=640) if arq640.is_file() else None

    def achados(det, dados: bytes, minimo: float) -> list[str]:
        return sorted({d["class"].lower() for d in det.detect(dados)
                       if d.get("class") in categorias and d.get("score", 0) >= minimo})

    def classificar(caminho: Path) -> tuple[str, str]:
        dados = caminho.read_bytes()                                # bytes: caminho com acento funciona
        tam = _tamanho(dados)
        if tam is None:
            raise ValueError("imagem ilegível")
        if min(tam) < MIN_LADO:
            return "ignorada", f"ícone ou miniatura ({tam[0]}x{tam[1]})"
        a = achados(rapido, dados, 0.35)
        if not a:
            return "ok", "NudeNet 320: nada"
        if preciso is None:
            return "incerto", "NudeNet 320: " + ", ".join(a) + " (sem o 640 para confirmar)"
        b = achados(preciso, dados, 0.5)
        if b:
            return "sensivel", "NudeNet 640: " + ", ".join(b)
        return "incerto", "320 suspeitou (" + ", ".join(a) + "), 640 não confirmou"
    return classificar


class Varredura:
    def __init__(self, classificar: Callable[[Path], tuple[bool, str]], home: Path = HOME) -> None:
        self._classificar = classificar
        self._relatorios = home / "varreduras"
        self._quarentena = home / "quarentena"

    # ---- 1. analise (nao move nada) -----------------------------------------
    def analisar(self, pasta: Path, limite: int = 60, progresso: Callable[[int, int], None] | None = None) -> dict[str, Any]:
        lista, total = imagens(pasta, limite=limite)
        ident = time.strftime("%Y%m%d-%H%M%S")
        itens = []
        for i, img in enumerate(lista, 1):
            item: dict[str, Any] = {"caminho": str(img), "tamanho": img.stat().st_size, "sha256": sha256(img)}
            try:
                situacao, item["motivo"] = self._classificar(img)
                if isinstance(situacao, bool):                     # classificadores antigos: sim/nao
                    situacao = "sensivel" if situacao else "ok"
            except Exception as e:  # noqa: BLE001 - uma imagem ruim nao para a varredura
                situacao, item["motivo"] = "nao_analisada", f"não analisada: {type(e).__name__}"
            item["situacao"] = situacao
            item["sensivel"] = situacao == "sensivel"               # so estas podem ir para a quarentena
            itens.append(item)
            if progresso:
                progresso(i, len(lista))
        rel = {"id": ident, "pasta": str(pasta), "em": time.time(), "analisadas": len(itens), "encontradas": total,
               "sinalizadas": sum(1 for x in itens if x["sensivel"]),
               "incertas": sum(1 for x in itens if x["situacao"] == "incerto"),
               "ignoradas": sum(1 for x in itens if x["situacao"] == "ignorada"),
               "nao_analisadas": sum(1 for x in itens if x["situacao"] == "nao_analisada"),
               "itens": itens, "movido": False}
        self._relatorios.mkdir(parents=True, exist_ok=True)
        (self._relatorios / f"{ident}.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
        return rel

    def ultimo_relatorio(self) -> dict[str, Any] | None:
        try:
            arqs = sorted(self._relatorios.glob("*.json"))
            return json.loads(arqs[-1].read_text(encoding="utf-8")) if arqs else None
        except (OSError, ValueError):
            return None

    # ---- 2. quarentena (so com confirmacao, fora daqui) ----------------------
    def quarentenar(self, relatorio: dict[str, Any]) -> dict[str, Any]:
        destino = self._quarentena / relatorio["id"]
        manifesto_arq = destino / "manifesto.json"
        movidos, pulados = [], []
        for n, item in enumerate((x for x in relatorio["itens"] if x["sensivel"]), 1):
            origem = Path(item["caminho"])
            if not origem.is_file() or sha256(origem) != item["sha256"]:
                pulados.append({**item, "motivo_pulo": "sumiu ou mudou desde a análise"})
                continue
            destino.mkdir(parents=True, exist_ok=True)
            alvo = destino / f"{n:03d}_{origem.name}"
            shutil.move(str(origem), str(alvo))
            movidos.append({"origem": str(origem), "quarentena": str(alvo), "sha256": item["sha256"],
                            "em": time.time(), "restaurado": False})
        if movidos:
            antigos = json.loads(manifesto_arq.read_text(encoding="utf-8")) if manifesto_arq.exists() else []
            manifesto_arq.write_text(json.dumps(antigos + movidos, ensure_ascii=False, indent=1), encoding="utf-8")
        relatorio["movido"] = True                       # a mesma analise nao move de novo
        (self._relatorios / f"{relatorio['id']}.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=1),
                                                                 encoding="utf-8")
        return {"movidos": len(movidos), "pulados": len(pulados), "pasta": str(destino)}

    # ---- 3. restaurar ---------------------------------------------------------
    def restaurar(self) -> dict[str, Any]:
        restaurados, problemas = 0, []
        for manifesto_arq in sorted(self._quarentena.glob("*/manifesto.json")):
            entradas = json.loads(manifesto_arq.read_text(encoding="utf-8"))
            for e in entradas:
                if e.get("restaurado"):
                    continue
                q, origem = Path(e["quarentena"]), Path(e["origem"])
                if not q.is_file():
                    problemas.append(f"{q.name} não está mais na quarentena")
                    continue
                alvo = origem
                if alvo.exists():                                   # nunca sobrescreve
                    alvo = origem.with_name(f"{origem.stem} (restaurado){origem.suffix}")
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(q), str(alvo))
                if sha256(alvo) != e["sha256"]:
                    problemas.append(f"{alvo.name}: hash diferente depois de restaurar")
                e["restaurado"], e["restaurado_em"] = True, str(alvo)
                restaurados += 1
            manifesto_arq.write_text(json.dumps(entradas, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"restaurados": restaurados, "problemas": problemas}

    def em_quarentena(self) -> list[dict[str, Any]]:
        saida = []
        for manifesto_arq in sorted(self._quarentena.glob("*/manifesto.json")):
            try:
                saida += [e for e in json.loads(manifesto_arq.read_text(encoding="utf-8")) if not e.get("restaurado")]
            except (OSError, ValueError):
                continue
        return saida
