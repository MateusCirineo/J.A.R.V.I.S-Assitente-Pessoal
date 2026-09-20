"""Ensaio local matemático: HTTP e seleção de ferramentas reais, dados isolados."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
import urllib.request

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "modo-show"))
isolado = tempfile.TemporaryDirectory(prefix="jarvis-matematica-real-")
os.environ["OPENJARVIS_HOME"] = isolado.name
from hud_runtime.comandos import Comandos
from hud_runtime.estado import Estado
from hud_runtime.fala_variantes import pedido_so_calculos
from hud_runtime.voz import Conversa

entrada = sys.argv[1] if len(sys.argv) > 1 else "calcule 17 vezes 19 e depois calcule 25 por cento de 480"
destino = RAIZ / "artifacts/auditoria-2026-09-20" / (sys.argv[2] if len(sys.argv) > 2 else "modelo-ferramentas-real-reserva.json")
if destino.exists():
    raise FileExistsError("Preserve a evidência existente: informe outro nome de saída")
c = Conversa.__new__(Conversa)
c._estado, c._cancelado = Estado(), threading.Event()
rt = SimpleNamespace(estado=c._estado, prefs=SimpleNamespace(ler=lambda: {}))
c.comandos = Comandos(rt, lambda *args: None)
c.comandos.contexto_para_modelo = lambda texto: None
c.clima = c.falante = c.memoria = None
c._historico = []
c._imagem_para = lambda *args: (None, None, None)
c._ponte_conectada = lambda: False
http_real = urllib.request.urlopen
executar_real = c.comandos.executar_ferramenta
trocas, execucoes = [], []

def consultar(request, **kwargs):
    pedido = json.loads(request.data)
    inicio = time.monotonic()
    with http_real(request, **kwargs) as resposta:
        corpo = resposta.read()
    dados = json.loads(corpo)
    trocas.append({"pedido": pedido, "resposta": dados,
                   "duracao_s": round(time.monotonic() - inicio, 3),
                   "via": "HTTP real localhost8000, X-OpenJarvis-Direct=1"})
    print(json.dumps({"troca": len(trocas), "duracao_s": trocas[-1]["duracao_s"],
                      "message": (dados.get("choices") or [{}])[0].get("message")}, ensure_ascii=False), flush=True)
    return io.BytesIO(corpo)

def executar(nome, args):
    # Este ensaio não autoriza nenhum efeito além de matemática local.
    frase = args.get("frase", "")
    if nome != "executar_comando" or not pedido_so_calculos(frase):
        raise ValueError("fora do escopo matemático autorizado para o ensaio")
    retorno = executar_real(nome, args)
    execucoes.append({"nome": nome, "argumentos": args, "resultado": retorno})
    return retorno

c.comandos.executar_ferramenta = executar
inicio = time.monotonic()
try:
    with patch("hud_runtime.voz.urllib.request.urlopen", side_effect=consultar):
        resultado = c._perguntar_com(entrada, {"ferramentas_voz": True, "voz_rapida": True,
                                              "espera_modelo_s": 120}, "qwen3.5:4b", None, False, None)
    evidencia = {"entrada": entrada, "modelo_solicitado": "qwen3.5:4b",
                 "modelos_pedido": c._modelos_pedido, "trocas": trocas, "execucoes": execucoes,
                 "resultado": resultado, "duracao_s": round(time.monotonic() - inicio, 3),
                 "ambiente": "Windows/Python3.10; backend8000/Ollama reais; HOME temporário; sem câmera, microfone, contas ou dados pessoais"}
    destino.write_text(json.dumps(evidencia, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"arquivo": str(destino), "execucoes": execucoes, "resultado": resultado,
                      "duracao_s": evidencia["duracao_s"]}, ensure_ascii=False), flush=True)
finally:
    isolado.cleanup()
