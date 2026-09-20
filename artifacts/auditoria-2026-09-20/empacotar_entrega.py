"""Manifesto e cópia do código auditado; exclui dados pessoais e bibliotecas."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
paths = set()
with zipfile.ZipFile(OUT / "codigo-inicial.zip") as initial:
    baseline = {name: hashlib.sha256(initial.read(name)).hexdigest() for name in initial.namelist()}
    paths.update(ROOT / name for name in baseline if (ROOT / name).is_file())
for directory in ("modo-show/hud_runtime", "modo-show/testes", "modo-show/hud", "frontend/src", "src/openjarvis/server/static"):
    paths.update(p for p in (ROOT / directory).rglob("*") if p.is_file()
                 and "__pycache__" not in p.parts
                 and p.suffix.lower() in {".py", ".js", ".mjs", ".html", ".css", ".tsx", ".ts", ".json", ".svg", ".woff2", ".ico", ".png"})
paths.update((ROOT / "modo-show").glob("*.html"))
for relative in ("modo-show/jarvis_runtime.py", "modo-show/GESTOS_S7.md", "modo-show/requirements-s7.txt",
                 "src/openjarvis/server/runtime_bridge.py", "tests/server/test_runtime_bridge.py",
                 "docs/JARVIS_AUDITORIA_2026-09-20.md", "docs/JARVIS_COMANDOS_E_VALIDACAO.md"):
    paths.add(ROOT / relative)
rows = []
with zipfile.ZipFile(OUT / "codigo-entregue.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append({"arquivo": relative, "sha256": digest,
                     "comparacao_checkpoint": "novo" if relative not in baseline else "alterado" if baseline[relative] != digest else "preservado"})
        bundle.write(path, relative)
report = {"aviso": "Comparação com checkpoint do início da revisão, não com árvore Git limpa. Inclui alterações preexistentes. Não atribui autoria.",
          "bibliotecas_e_modelos": "Não incluídos; requisitos/versão/hash de S7 em modo-show/GESTOS_S7.md. Dados pessoais fora do pacote.",
          "quantidade": len(rows), "arquivos": rows}
(OUT / "manifesto-arquivos.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"arquivos": len(rows), "zip_bytes": (OUT / "codigo-entregue.zip").stat().st_size,
                  "zip_sha256": hashlib.sha256((OUT / "codigo-entregue.zip").read_bytes()).hexdigest()}))
