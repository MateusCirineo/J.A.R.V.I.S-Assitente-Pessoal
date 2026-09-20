"""Falar com o Jarvis pelo terminal (mesmo caminho da caixa de comando da tela).

    python modo-show\\jarvis_cmd.py "que horas são"          responde aqui
    python modo-show\\jarvis_cmd.py --falar "notícias"       tambem fala em voz alta
    python modo-show\\jarvis_cmd.py                           modo conversa (Ctrl+C sai)

Precisa do runtime aberto (icone Jarvis ou Modo Show). Usa o token da
instancia em ~/.openjarvis/hud-runtime.json; nada sai do computador.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis"))


def instancia() -> dict:
    try:
        return json.loads((HOME / "hud-runtime.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SystemExit("O Jarvis não está aberto. Abra pelo ícone Jarvis ou pelo Modo Show.") from None


def comando(texto: str, falar: bool = False) -> str:
    inst = instancia()
    req = urllib.request.Request(
        f"http://127.0.0.1:{inst['porta']}/api/comando",
        data=json.dumps({"texto": texto, "falar": falar}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Jarvis-Token": inst["token"]})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.load(r)
    except urllib.error.URLError:
        raise SystemExit("O Jarvis não respondeu. Ele está aberto?") from None
    if falar:
        return "(falando em voz alta)"
    return d.get("resposta") or "(sem resposta)"


def main(args: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    falar = "--falar" in args
    args = [a for a in args if a != "--falar"]
    if args:
        print(comando(" ".join(args), falar))
        return 0
    print("Jarvis pelo terminal. Digite e tecle Enter; Ctrl+C para sair.")
    try:
        while True:
            texto = input("você> ").strip()
            if texto:
                print("jarvis>", comando(texto, falar))
    except (KeyboardInterrupt, EOFError):
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
