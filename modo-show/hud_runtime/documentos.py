"""Resumir um documento local sob pedido (txt, md, pdf, docx, csv...).

"Jarvis, resuma o último PDF baixado" / "resuma o documento aberto" /
"resuma o relatório de vendas" / "resuma C:\\...\\contrato.pdf".
So o arquivo pedido e lido (nada de varrer pastas pessoais por conta
propria); o texto vai ao modelo LOCAL pelo servidor do OpenJarvis. Documento
longo: resume o comeco e diz que foi so o comeco.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Callable

EXTS_TEXTO = {".txt", ".md", ".csv", ".log", ".json", ".py", ".js", ".ts", ".html", ".xml", ".ini", ".toml",
              ".yaml", ".yml", ".c", ".h", ".java", ".sql"}
EXTS = EXTS_TEXTO | {".pdf", ".docx"}
LIMITE_CHARS = 6000
SISTEMA = ("Você resume documentos em português do Brasil para ouvir em voz alta. Em até cinco frases curtas, "
           "diga do que se trata e os pontos principais (datas, valores e conclusões que estiverem no texto). "
           "Não invente nada que não esteja no texto. Sem listas nem markdown.")

_GUIDS = {"downloads": "{374DE290-123F-4565-9164-39C4925E467B}", "documentos": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
          "area de trabalho": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "imagens": "{33E28130-4E1E-4676-835A-98395C3BC3BB}"}


def pasta_conhecida(nome: str) -> Path:
    try:
        import ctypes
        import uuid

        class GUID(ctypes.Structure):
            _fields_ = [("d1", ctypes.c_ulong), ("d2", ctypes.c_ushort), ("d3", ctypes.c_ushort), ("d4", ctypes.c_ubyte * 8)]
        g = uuid.UUID(_GUIDS[nome])
        guid = GUID(g.fields[0], g.fields[1], g.fields[2], (ctypes.c_ubyte * 8)(*g.bytes[8:]))
        p = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(p)) == 0:
            caminho = Path(p.value)
            ctypes.windll.ole32.CoTaskMemFree(p)
            return caminho
    except (OSError, AttributeError, ValueError, KeyError):
        pass
    return Path.home() / {"downloads": "Downloads", "documentos": "Documents", "area de trabalho": "Desktop",
                          "imagens": "Pictures"}[nome]


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def extrair_texto(caminho: Path, limite: int = LIMITE_CHARS) -> tuple[str, dict[str, Any]]:
    ext = caminho.suffix.lower()
    info: dict[str, Any] = {"paginas": None, "cortado": False}
    if ext == ".pdf":
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            leitor = PdfReader(str(caminho))
        except PyPdfError as e:
            raise ValueError(f"o PDF está danificado ou ilegível ({type(e).__name__})") from e
        if leitor.is_encrypted:
            raise ValueError("o PDF está protegido por senha")
        info["paginas"] = len(leitor.pages)
        partes, total = [], 0
        info["limites_paginas"] = []
        for i, pg in enumerate(leitor.pages):
            t = pg.extract_text() or ""
            t = re.sub(r"[ \t]+", " ", t)
            t = re.sub(r"\n{3,}", "\n\n", t).strip()
            inicio = total + (1 if i else 0)
            partes.append(t)
            total = inicio + len(t)
            info["limites_paginas"].append((i + 1, inicio, total))
            if total > limite:
                info["cortado"] = i + 1 < len(leitor.pages) or total > limite
                info["lidas"] = i + 1
                break
        texto = "\n".join(partes)
        if not texto.strip():
            raise ValueError("o PDF não tem texto (parece ser só imagem escaneada)")
    elif ext == ".docx":
        import docx
        d = docx.Document(str(caminho))
        texto = "\n".join(p.text for p in d.paragraphs if p.text.strip())
    elif ext in EXTS_TEXTO:
        bruto = caminho.read_bytes()[: limite * 4]
        for cod in ("utf-8-sig", "cp1252"):
            try:
                texto = bruto.decode(cod)
                break
            except UnicodeDecodeError:
                continue
        else:
            texto = bruto.decode("utf-8", "replace")
    else:
        raise ValueError(f"não sei ler arquivos {ext or 'sem extensão'}")
    if ext != ".pdf":
        texto = re.sub(r"[ \t]+", " ", texto)
        texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    if len(texto) > limite:
        texto, info["cortado"] = texto[:limite], True
    return texto, info


def _procurar(pastas: list[Path], aceitar: Callable[[Path], bool], profundidade: int = 3,
              limite_arquivos: int = 6000) -> list[Path]:
    achados, vistos = [], 0
    for base in pastas:
        if not base.is_dir():
            continue
        pilha = [(base, 0)]
        while pilha and vistos < limite_arquivos:
            pasta, nivel = pilha.pop()
            try:
                itens = list(pasta.iterdir())
            except OSError:
                continue
            for p in itens:
                vistos += 1
                if p.is_dir():
                    if nivel < profundidade and not p.name.startswith((".", "$")) and p.name != "node_modules":
                        pilha.append((p, nivel + 1))
                elif aceitar(p):
                    achados.append(p)
    return sorted(achados, key=lambda p: p.stat().st_mtime, reverse=True)


def achar(frase: str, titulo_janela: str | None = None, exts: set[str] = EXTS) -> Path | None:
    """Qual arquivo o usuario quer: caminho dito, ultimo baixado, o aberto na tela ou pelo nome."""
    m = re.search(r"[A-Za-z]:\\[^\"<>|?*\n]+?\.(\w{2,5})\b", frase)
    if m and Path(m.group(0)).is_file():
        return Path(m.group(0))
    n = _norm(frase)
    pastas = [pasta_conhecida("downloads"), pasta_conhecida("documentos"), pasta_conhecida("area de trabalho")]
    # "Documentos" desta maquina aponta para o OneDrive; a pasta local tambem
    # existe e o Senhor usa as duas. Procuro nas duas, sem repetir.
    for extra in (Path.home() / "Documents", Path.home() / "Desktop", Path.home() / "Downloads"):
        if extra.is_dir() and not any(extra == p for p in pastas):
            pastas.append(extra)
    tipo = {"pdf": {".pdf"}, "word": {".docx"}, "docx": {".docx"}, "planilha": {".csv"}, "texto": {".txt", ".md"}}
    filtro = next((v for k, v in tipo.items() if re.search(rf"\b{k}\b", n)), exts)
    if re.search(r"\bultim\w* (?:\w+ )?(?:baixad\w*|download)|\b(?:baixei|download) por ultimo\b", n):
        achados = _procurar([pastas[0]], lambda p: p.suffix.lower() in filtro, profundidade=0)
        return achados[0] if achados else None
    if titulo_janela and re.search(r"\b(?:aberto|aberta|dessa janela|desta janela|na tela|que estou vendo|atual)\b", n):
        mt = re.search(r"([^\\/:*?\"<>|]+?\.(?:" + "|".join(e[1:] for e in exts) + r"))\b", titulo_janela, re.I)
        if mt:
            nome = mt.group(1).strip().lower()
            achados = _procurar(pastas, lambda p: p.name.lower() == nome)
            if achados:
                return achados[0]
    palavras = [p for p in re.findall(r"[a-z0-9]{3,}", re.sub(
        r"\b(?:resum\w*|document\w*|arquivo|pdf|word|docx|texto|planilha|jarvis|sobre|chamad\w*|para|mim|por|favor"
        r"|leia|ler|analis\w*|explique|o que diz|dizer)\b", " ", n))]
    if not palavras:
        return None
    achados = _procurar(pastas, lambda p: p.suffix.lower() in filtro and all(w in _norm(p.stem) for w in palavras))
    return achados[0] if achados else None


def resumir(caminho: Path, gerar: Callable[[list[dict[str, Any]]], str]) -> dict[str, Any]:
    texto, info = extrair_texto(caminho)
    aviso = " (é só o começo de um documento maior)" if info.get("cortado") else ""
    resumo = gerar([{"role": "system", "content": SISTEMA},
                    {"role": "user", "content": f"Documento '{caminho.name}'{aviso}:\n\n{texto}"}])
    return {"arquivo": str(caminho), "nome": caminho.name, "paginas": info.get("paginas"),
            "cortado": bool(info.get("cortado")), "resumo": resumo}


def fala(r: dict[str, Any]) -> str:
    pag = f", {r['paginas']} página{'s' if r['paginas'] != 1 else ''}" if r.get("paginas") else ""
    corte = " Resumi só o começo, porque é longo." if r["cortado"] else ""
    return f"{r['nome']}{pag}. {r['resumo']}{corte}"
