"""Analisar audio e video locais sob pedido.

"Jarvis, transcreva o último áudio baixado" / "analise o vídeo reuniao.mp4".
- Audio: transcricao com marcas de tempo (o mesmo Whisper local da voz),
  salva em Documentos\\Jarvis\\Transcricoes\\<nome>.txt.
- Video: a mesma transcricao + alguns quadros espalhados descritos pelo
  modelo de visao local (Ollama). Nada sai da maquina.
A trava do Whisper e pega segmento a segmento: a escuta do "Jarvis" continua
funcionando entre um trecho e outro.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

EXTS_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".wma"}
EXTS_VIDEO = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".wmv"}
LIMITE_S = 30 * 60                                   # no maximo 30 min por pedido


def tempo(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def transcrever(transcricao: Any, caminho: Path, idioma: str = "pt",
                limite_s: float = LIMITE_S, progresso: dict | None = None) -> tuple[list[tuple[float, float, str]], float]:
    modelo, trava = transcricao._modelo, transcricao._trava
    if modelo is None:
        raise RuntimeError("a transcrição ainda não carregou")
    with trava:
        segs, info = modelo.transcribe(str(caminho), language=idioma, vad_filter=True)
    it, saida = iter(segs), []
    processado, completo = 0.0, False
    while True:
        with trava:                                  # um trecho por vez: a voz nao fica surda
            s = next(it, None)
        if s is None:
            completo = True
            break
        if s.start >= limite_s or s.end > limite_s:
            processado = max(processado, min(float(s.start), limite_s))
            break
        processado = max(processado, float(s.end))
        if s.text.strip():
            saida.append((s.start, s.end, s.text.strip()))
    duracao = float(getattr(info, "duration", 0) or 0)
    if progresso is not None:
        progresso.update(completo=completo, processado_ate_s=duracao if completo and duracao else processado)
    return saida, duracao


def quadros(caminho: Path, n: int = 3) -> list[tuple[float, bytes]]:
    import cv2
    cap = cv2.VideoCapture(str(caminho))
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        saida = []
        for i in range(n):
            alvo = int(total * (i + 1) / (n + 1)) if total else 0
            cap.set(cv2.CAP_PROP_POS_FRAMES, alvo)
            ok, img = cap.read()
            if not ok:
                continue
            h, w = img.shape[:2]
            if w > 640:
                img = cv2.resize(img, (640, round(h * 640 / w)), interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                saida.append((alvo / fps, buf.tobytes()))
        return saida
    finally:
        cap.release()


def cobertura(duracao: float, segs: list[tuple[float, float, str]],
              cenas: list[tuple[float, Any]], limite_s: float = LIMITE_S,
              progresso: dict | None = None) -> dict[str, Any]:
    """O que foi REALMENTE analisado (§10 e T17).

    Ouvir os primeiros 30 minutos e olhar 3 quadros não é "assisti ao vídeo".
    Aqui fica o que entrou: faixa transcrita, silêncios longos e os instantes
    exatos das imagens olhadas.
    """
    fim_ouvido = max((b for _, b, _ in segs), default=0.0)
    if progresso is not None:
        fim_ouvido = float(progresso.get("processado_ate_s", fim_ouvido))
    fim_ouvido = max(0.0, min(fim_ouvido, duracao if duracao else limite_s))
    falado = sum(max(0.0, b - a) for a, b, _ in segs)
    buracos: list[tuple[float, float]] = []
    anterior = 0.0
    for a, b, _ in segs:
        if a - anterior >= 20:                       # 20 s sem fala: vale dizer que ficou em branco
            buracos.append((anterior, a))
        anterior = max(anterior, b)
    if fim_ouvido - anterior >= 20:
        buracos.append((anterior, fim_ouvido))
    return {
        "duracao_s": round(duracao, 1),
        "ouvido_ate_s": round(fim_ouvido, 1),
        "fracao_ouvida": round(fim_ouvido / duracao, 3) if duracao else None,
        "audio_completo": bool(progresso and progresso.get("completo")),
        "fala_s": round(falado, 1),
        "trechos_transcritos": len(segs),
        "sem_fala": [(round(a, 1), round(b, 1)) for a, b in buracos[:6]],
        "quadros_vistos_s": [round(t, 1) for t, _ in cenas],
        "nao_analisado_s": round(max(0.0, duracao - fim_ouvido), 1),
    }


def falar_cobertura(c: dict[str, Any]) -> str:
    """Uma frase que não deixa dúvida sobre o que ficou de fora."""
    partes = []
    if not c["duracao_s"]:
        partes.append(f"duração total desconhecida; transcrição disponível até {tempo(c['ouvido_ate_s'])}")
    elif c["fracao_ouvida"] < 0.995:
        partes.append(f"ouvi até {tempo(c['ouvido_ate_s'])} de {tempo(c['duracao_s'])}; "
                      f"faltaram {tempo(c['nao_analisado_s'])}")
    elif c.get("audio_completo"):
        partes.append(f"ouvi o áudio inteiro ({tempo(c['duracao_s'])})")
    else:
        partes.append(f"transcrição disponível até {tempo(c['ouvido_ate_s'])}; conclusão integral não verificada")
    if c["quadros_vistos_s"]:
        quando = ", ".join(tempo(t) for t in c["quadros_vistos_s"])
        partes.append(f"da imagem, olhei {len(c['quadros_vistos_s'])} quadro"
                      f"{'s' if len(c['quadros_vistos_s']) > 1 else ''}, aos {quando} — não vi o resto")
    elif c["duracao_s"]:
        partes.append("não olhei nenhuma imagem")
    if c["sem_fala"]:
        faixas = "; ".join(f"{tempo(a)} a {tempo(b)}" for a, b in c["sem_fala"][:2])
        partes.append(f"sem fala transcrita em {faixas}")
    return "Cobertura: " + ", ".join(partes) + "."


def analisar(caminho: Path, transcricao: Any, pasta_saida: Path,
             descrever: Callable[[bytes, str], str] | None = None,
             resumir: Callable[[list[dict[str, Any]]], str] | None = None) -> dict[str, Any]:
    from .planilhas import caminho_livre
    video = caminho.suffix.lower() in EXTS_VIDEO
    progresso: dict[str, Any] = {}
    segs, duracao = transcrever(transcricao, caminho, progresso=progresso)
    cenas = []
    falhas_cenas = []
    if video and descrever:
        for t, jpg in quadros(caminho):
            try:
                cenas.append((t, descrever(jpg, "Descreva esta cena de vídeo em uma frase curta, em português.")))
            except Exception as e:  # noqa: BLE001 - uma cena que falha nao derruba a analise
                falhas_cenas.append((t, type(e).__name__))
    cob = cobertura(duracao, segs, cenas, progresso=progresso)
    cob["quadros_falharam_s"] = [t for t, _ in falhas_cenas]
    linhas = [f"Arquivo: {caminho}", f"Duração: {tempo(duracao)}", falar_cobertura(cob), ""]
    if cenas:
        linhas += ["Cenas:"] + [f"[{tempo(t)}] {d}" for t, d in cenas] + [""]
    if falhas_cenas:
        linhas += ["Quadros não analisados por falha:"] + [f"[{tempo(t)}] {e}" for t, e in falhas_cenas] + [""]
    linhas += ["Transcrição:"] + [f"[{tempo(a)}] {txt}" for a, _, txt in segs]
    saida = caminho_livre(pasta_saida, caminho.stem, ".txt")
    saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    texto = " ".join(t for _, _, t in segs)
    resumo = None
    if resumir and len(texto) > 200:
        resumo = resumir([{"role": "system", "content": "Resuma em português, em até quatro frases curtas, o que é "
                                                        "dito nesta transcrição. Não invente nada."},
                          {"role": "user", "content": texto[:6000]}])
    return {"arquivo": str(caminho), "nome": caminho.name, "video": video, "duracao": duracao,
            "segmentos": len(segs), "cenas": cenas, "saida": str(saida), "resumo": resumo,
            "inicio": texto[:200], "cortado": not progresso.get("completo", False),
            "cobertura": cob, "segmentos_tempos": segs, "falhas_cenas": falhas_cenas}


def fala(r: dict[str, Any]) -> str:
    tipo = "Vídeo" if r["video"] else "Áudio"
    partes = [f"{tipo} {r['nome']}, {tempo(r['duracao'])} de duração."]
    if not r["segmentos"]:
        partes.append("Não encontrei fala nele.")
    elif r["resumo"]:
        partes.append(r["resumo"])
    else:
        partes.append(f"Começa com: {r['inicio']}")
    if r["cenas"]:
        partes.append(f"Na imagem, aos {tempo(r['cenas'][0][0])}: {r['cenas'][0][1]}")
    if r.get("cobertura"):
        partes.append(falar_cobertura(r["cobertura"]))      # T17: o que ficou de fora fica dito
    elif r["cortado"]:
        partes.append("Transcrevi só os primeiros 30 minutos.")
    partes.append("A transcrição com os tempos está em Documentos, Jarvis, Transcrições.")
    return " ".join(partes)

