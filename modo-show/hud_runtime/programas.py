"""Gerar um programa em Python a pedido, SEM executar.

"Jarvis, crie um programa em Python que renomeia as fotos pela data."
O modelo local escreve; aqui o codigo e:
1. extraido da resposta (```python ...```),
2. validado so pela sintaxe (ast.parse: nada roda),
3. inspecionado por chamadas sensiveis (apagar arquivos, rodar comandos,
   rede, eval/exec) -> avisos no cabecalho e na fala,
4. salvo em Documentos\\Jarvis\\Programas\\ (sem sobrescrever),
5. aberto no VS Code (ou no Bloco de Notas). Nunca com os.startfile: no
   Windows isso EXECUTARIA o .py.

Codigo gerado e nao confiavel: quem decide rodar e o usuario.
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

SISTEMA = ("Você é um programador Python cuidadoso. Escreva UM arquivo Python 3 completo e comentado em português "
           "que faça o que o usuário pediu. Use só a biblioteca padrão, a menos que o pedido exija outra (e então "
           "diga no comentário do topo como instalar). Não apague arquivos sem pedir confirmação no próprio programa. "
           "Coloque o código principal em uma função main() com if __name__ == '__main__'. "
           "Responda só com o código, dentro de um bloco ```python.")

# chamadas que merecem aviso (nao bloqueiam: o usuario revisa)
_SENSIVEIS = {
    "apaga arquivos": {"os.remove", "os.unlink", "os.rmdir", "shutil.rmtree", "Path.unlink", "unlink", "rmtree", "rmdir"},
    "roda comandos do sistema": {"os.system", "subprocess.run", "subprocess.call", "subprocess.Popen",
                                 "subprocess.check_output", "subprocess.check_call", "os.popen", "Popen"},
    "acessa a internet": {"urllib.request.urlopen", "urlopen", "requests.get", "requests.post", "socket.socket",
                          "httpx.get", "httpx.post"},
    "executa texto como código": {"eval", "exec", "compile", "__import__"},
    "move ou renomeia arquivos": {"os.rename", "os.replace", "shutil.move", "Path.rename", "rename"},
}


def extrair_codigo(texto: str) -> str:
    blocos = re.findall(r"```(?:python|py)?\s*\n(.*?)```", texto, re.S)
    if blocos:
        return max(blocos, key=len).strip("\n")
    return re.sub(r"^```\w*|```$", "", texto.strip()).strip("\n")


def _nome_chamada(n: ast.AST) -> str:
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        base = _nome_chamada(n.value)
        return f"{base}.{n.attr}" if base else n.attr
    return ""


def validar(codigo: str) -> tuple[str | None, list[str]]:
    """(erro de sintaxe ou None, avisos). So analisa: nada e executado."""
    try:
        arvore = ast.parse(codigo)
    except SyntaxError as e:
        return f"erro de sintaxe na linha {e.lineno}: {e.msg}", []
    chamadas = set()
    for n in ast.walk(arvore):
        if isinstance(n, ast.Call):
            nome = _nome_chamada(n.func)
            chamadas.add(nome)
            chamadas.add(nome.rsplit(".", 1)[-1])
    avisos = [rot for rot, nomes in _SENSIVEIS.items() if chamadas & nomes]
    return None, avisos


def slug(pedido: str) -> str:
    t = unicodedata.normalize("NFKD", pedido.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"^.*?\b(?:que|para|pra)\b\s*", "", t) or t
    palavras = [p for p in re.findall(r"[a-z0-9]+", t) if p not in {"o", "a", "os", "as", "de", "do", "da", "e", "um", "uma"}]
    return "_".join(palavras[:5]) or "programa"


def abrir_para_revisar(arquivo: Path) -> str:
    """VS Code se houver; senao Bloco de Notas. Nunca o interpretador."""
    code = shutil.which("code")
    exe = Path(code).parent.parent / "Code.exe" if code else None
    if exe and exe.is_file():
        subprocess.Popen([str(exe), str(arquivo)], creationflags=0x08000000)
        return "VS Code"
    subprocess.Popen(["notepad.exe", str(arquivo)])
    return "Bloco de Notas"


class Programas:
    def __init__(self, gerar: Callable[[list[dict[str, Any]]], str], pasta: Path | None = None,
                 abrir: Callable[[Path], str] = abrir_para_revisar) -> None:
        self._gerar = gerar
        self._pasta = pasta
        self._abrir = abrir

    def criar(self, pedido: str) -> dict[str, Any]:
        from .modelo import limpar
        from .planilhas import caminho_livre, pasta_documentos
        msgs = [{"role": "system", "content": SISTEMA}, {"role": "user", "content": pedido}]
        codigo = extrair_codigo(limpar(self._gerar(msgs)))
        erro, avisos = validar(codigo)
        if erro:                                   # uma segunda chance, com o erro
            msgs += [{"role": "assistant", "content": f"```python\n{codigo}\n```"},
                     {"role": "user", "content": f"Esse código tem {erro}. Corrija e mande o arquivo inteiro."}]
            codigo = extrair_codigo(limpar(self._gerar(msgs)))
            erro, avisos = validar(codigo)
        cabecalho = [f"# Gerado pelo Jarvis (modelo local) em {datetime.now():%d/%m/%Y %H:%M}.",
                     f"# Pedido: {pedido[:150]}",
                     "# NÃO foi executado. Revise antes de rodar."]
        if avisos:
            cabecalho.append("# Atenção, este código " + "; ".join(avisos) + ".")
        if erro:
            cabecalho.append(f"# ATENÇÃO: {erro}.")
        pasta = self._pasta or (pasta_documentos() / "Jarvis" / "Programas")
        arquivo = caminho_livre(pasta, slug(pedido), ".py")
        arquivo.write_text("\n".join(cabecalho) + "\n\n" + codigo + "\n", encoding="utf-8")
        onde = self._abrir(arquivo)
        return {"arquivo": str(arquivo), "erro": erro, "avisos": avisos, "linhas": codigo.count("\n") + 1,
                "aberto_em": onde}


def fala(r: dict[str, Any]) -> str:
    base = f"Programa salvo em Documentos, Jarvis, Programas, com {r['linhas']} linhas, e aberto no {r['aberto_em']}."
    if r["erro"]:
        base += f" Mas ele tem {r['erro']}."
    if r["avisos"]:
        base += " Atenção: ele " + " e ".join(r["avisos"]) + "."
    return base + " Não executei nada; revise antes de rodar."
