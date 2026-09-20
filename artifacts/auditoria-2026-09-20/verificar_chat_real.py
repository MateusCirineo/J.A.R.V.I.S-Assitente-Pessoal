"""Smoke HTTP local, sem câmera, fala, contas ou escrita fora dos recibos do chat."""
import argparse
import http.client
import json
import time
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent


def request(port, path, body=None, headers=None, timeout=360):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("POST" if body is not None else "GET", path,
                     json.dumps(body) if body is not None else None, headers or {})
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()


def chat(text, session, operation):
    headers = {"Content-Type": "application/json", "Origin": "http://127.0.0.1:8000",
               "X-OpenJarvis-Runtime": "1", "X-Jarvis-Session": session,
               "X-Jarvis-Request": operation}
    body = {"model": "gemma4:e4b", "messages": [{"role": "user", "content": text}], "stream": False}
    status, result = request(8000, "/v1/chat/completions", body, headers)
    return status, result, headers, body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--composto", action="store_true")
    args = parser.parse_args()
    session = "auditoria-real-" + uuid.uuid4().hex
    report = {"via": "HTTP real chat 8000 -> runtime 8765; sem navegador",
              "runtime": request(8765, "/api/saude")[1], "servidor": request(8000, "/health")[1]}
    text = ("calcule 17 vezes 19 e depois calcule 25 por cento de 480" if args.composto
            else "Como memorizar meu rosto e minha voz?")
    started = time.monotonic()
    status, result, headers, body = chat(text, session, uuid.uuid4().hex)
    report.update(entrada=text, http=status, primeira=result, duracao_s=round(time.monotonic()-started, 3))
    report["http_repeticao"], report["repeticao"] = request(8000, "/v1/chat/completions", body, headers, 20)
    answer = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    report["sucesso"] = (status == 200 and result.get("runtime", {}).get("estado") == "respondida"
                         and report["repeticao"].get("runtime", {}).get("repetido") is True)
    if args.composto:
        report["sucesso"] &= "323" in answer and "120" in answer and "Nenhuma ferramenta" not in answer
    else:
        report["sucesso"] &= "três frases" in answer and result.get("model") == "jarvis-runtime"
        report["origem_alheia_http"] = request(8000, "/v1/chat/completions", body,
                                               dict(headers, Origin="https://example.invalid"), 10)[0]
        report["runtime_sem_token_http"] = request(8765, "/api/chat",
                                                   {"texto": "calcule 1 mais 1", "sessao_id": session, "pedido_id": "auth"},
                                                   {"Content-Type": "application/json"}, 10)[0]
        cancelled_headers = dict(headers, **{"X-Jarvis-Request": uuid.uuid4().hex})
        report["cancelar_http"], report["cancelar"] = request(8000, "/v1/runtime/cancel", {}, cancelled_headers, 10)
        report["cancelado_http"], report["cancelado"] = request(8000, "/v1/chat/completions", body, cancelled_headers, 10)
        report["sucesso"] &= (report["origem_alheia_http"] == 403 and report["runtime_sem_token_http"] == 403
                              and report["cancelado"].get("runtime", {}).get("estado") == "cancelada")
    target = OUT / ("chat-runtime-real.json" if args.composto else "chat-cadastro-ajuda-real.json")
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)
    return 0 if report["sucesso"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
