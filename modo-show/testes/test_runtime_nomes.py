"""O runtime inteiro nao sobe nos testes (carrega voz, camera, modelos). Esta
checagem estatica pega o erro que ja derrubou a inicializacao uma vez: um
`from x import Nome` DENTRO de uma funcao torna `Nome` local na funcao inteira,
e um uso anterior do `Nome` global vira UnboundLocalError."""

import ast
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def nomes_globais(arvore: ast.Module) -> set[str]:
    nomes = set()
    for no in arvore.body:
        if isinstance(no, (ast.Import, ast.ImportFrom)):
            nomes |= {a.asname or a.name.split(".")[0] for a in no.names}
        elif isinstance(no, (ast.FunctionDef, ast.ClassDef)):
            nomes.add(no.name)
        elif isinstance(no, ast.Assign):
            nomes |= {t.id for t in no.targets if isinstance(t, ast.Name)}
    return nomes


class TestNomesDoRuntime(unittest.TestCase):
    def test_import_local_nao_esconde_nome_global(self):
        for arq in [RAIZ / "jarvis_runtime.py", *sorted((RAIZ / "hud_runtime").glob("*.py"))]:
            arvore = ast.parse(arq.read_text(encoding="utf-8"))
            globais = nomes_globais(arvore)
            for f in ast.walk(arvore):
                if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                locais = {a.asname or a.name.split(".")[0] for no in ast.walk(f)
                          if isinstance(no, (ast.Import, ast.ImportFrom)) for a in no.names}
                for nome in sorted(locais & globais):
                    usos = [n.lineno for n in ast.walk(f) if isinstance(n, ast.Name) and n.id == nome
                            and isinstance(n.ctx, ast.Load)]
                    imps = [no.lineno for no in ast.walk(f) if isinstance(no, (ast.Import, ast.ImportFrom))
                            and any((a.asname or a.name.split(".")[0]) == nome for a in no.names)]
                    antes = [u for u in usos if u < min(imps)]
                    self.assertFalse(antes, f"{arq.name}:{f.name}: '{nome}' usado na linha {antes} antes do import "
                                            f"local da linha {min(imps)} (UnboundLocalError)")


class TestArquivosLimpos(unittest.TestCase):
    def test_sem_caractere_de_controle_perdido(self):
        """Patches via heredoc ja transformaram "\\b" num backspace invisivel (regex que nunca casa)."""
        for arq in [RAIZ / "jarvis_runtime.py", *(RAIZ / "hud_runtime").glob("*.py"), *(RAIZ / "hud").glob("*.js"),
                    *(RAIZ / "hud").glob("*.html"), *(RAIZ / "testes").glob("*.py")]:
            texto = arq.read_text(encoding="utf-8")
            ruins = [i + 1 for i, linha in enumerate(texto.split("\n")) if any(ord(c) < 32 and c not in "\t\r" for c in linha)]
            self.assertFalse(ruins, f"{arq.name}: caractere de controle nas linhas {ruins}")


if __name__ == "__main__":
    unittest.main()
