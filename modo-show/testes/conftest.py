"""Testes NUNCA escrevem nos dados do Senhor.

Vários módulos guardam estado em ~/.openjarvis (lembretes, listas, identidades,
projetos, peças) e leem esse caminho de `OPENJARVIS_HOME` **no import**. Se um
teste construir um desses serviços sem passar um caminho, ele grava na
instalação de verdade -- foi o que aconteceu duas vezes: três lembretes de teste
no arquivo do Senhor (18/09) e duas peças fantasma no acervo (19/09).

Este arquivo aponta OPENJARVIS_HOME para uma pasta temporária antes de qualquer
módulo do HUD ser importado. Quem precisar do caminho real que peça explicitamente.
"""

import os
import tempfile
from pathlib import Path

_TEMP = Path(tempfile.mkdtemp(prefix="jarvis-testes-"))
os.environ["OPENJARVIS_HOME"] = str(_TEMP)
(_TEMP / "marcador-de-teste.txt").write_text(
    "Pasta de testes do Jarvis. Se isto aparecer em ~/.openjarvis, algo escapou do isolamento.",
    encoding="utf-8")


def pytest_report_header(config):
    return f"dados de teste isolados em {_TEMP}"
