"""Testes do runtime do HUD.  Rodar:  .venv\\Scripts\\python -m unittest discover modo-show\\testes"""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AQUI))

from hud_runtime import audio, estado, palmas, ponte, preferencias, servidor_http, telemetria  # noqa: E402
from hud_runtime.voz import limpar_resposta  # noqa: E402

# fala de verdade gravada pelo Kokoro: fica na instalacao, nao na pasta isolada
# dos testes (o conftest desvia OPENJARVIS_HOME para um temporario de proposito)
WAV_FALA = Path.home() / ".openjarvis" / "teste-voz-pt.wav"


# ---------------------------------------------------------------------------

class TestPreferencias(unittest.TestCase):
    def test_campos_invalidos_ignorados_e_faixas_limitadas(self):
        p = preferencias.validar({"tema": "neon", "brilho": 7, "volume": -1,
                                  "nome_usuario": "  Mateus  ", "desconhecido": 1,
                                  "saudacao": "sim", "abrir": {"chat": False, "x": True}})
        self.assertEqual(p["tema"], "hud")               # enum invalido -> padrao
        self.assertEqual(p["brilho"], 1.0)               # limitado ao teto
        self.assertEqual(p["volume"], 0.0)               # limitado ao piso
        self.assertEqual(p["nome_usuario"], "Mateus")
        self.assertTrue(p["saudacao"])                   # string nao vira bool
        self.assertFalse(p["abrir"]["chat"])
        self.assertNotIn("x", p["abrir"])
        self.assertNotIn("desconhecido", p)

    def test_persistencia_atomica_e_arquivo_corrompido(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "p.json"
            pr = preferencias.Preferencias(arq)
            pr.aplicar({"perfil_grafico": "economico"})
            self.assertEqual(preferencias.Preferencias(arq).ler()["perfil_grafico"], "economico")
            arq.write_text("{quebrado", encoding="utf-8")
            self.assertEqual(preferencias.Preferencias(arq).ler(), preferencias.PADRAO)


# ---------------------------------------------------------------------------

def _palma(pico=0.7, dur=0.12, taxa=16000, seed=0):
    rng = np.random.default_rng(seed)
    n = int(dur * taxa)
    env = np.exp(-np.arange(n) / (0.012 * taxa))
    return (rng.standard_normal(n) * env * pico / 3).clip(-1, 1).astype(np.float32)


def _alimentar(det, sinal):
    disparos = 0
    for i in range(0, len(sinal) - palmas.BLOCO + 1, palmas.BLOCO):
        disparos += det.processar(sinal[i:i + palmas.BLOCO])
    return disparos


def _fundo(seg, nivel=0.004, seed=1):
    return (np.random.default_rng(seed).standard_normal(int(seg * 16000)) * nivel).astype(np.float32)


class TestPalmas(unittest.TestCase):
    def _cena(self, intervalo, fundo=0.004):
        s = _fundo(3.0, fundo)
        a, b = int(1.0 * 16000), int((1.0 + intervalo) * 16000)
        p = _palma()
        s[a:a + p.size] += p
        s[b:b + p.size] += _palma(seed=3)
        return s

    def test_duas_palmas_disparam(self):
        self.assertEqual(_alimentar(palmas.DetectorPalmas(), self._cena(0.4)), 1)

    def test_uma_palma_nao_dispara(self):
        s = _fundo(3.0)
        p = _palma()
        s[16000:16000 + p.size] += p
        self.assertEqual(_alimentar(palmas.DetectorPalmas(), s), 0)

    def test_palmas_muito_separadas_nao_disparam(self):
        self.assertEqual(_alimentar(palmas.DetectorPalmas(), self._cena(1.8)), 0)

    def test_ambiente_barulhento_ainda_detecta(self):
        self.assertEqual(_alimentar(palmas.DetectorPalmas(), self._cena(0.45, fundo=0.03)), 1)

    def test_som_sustentado_nao_dispara(self):
        t = np.arange(int(3 * 16000)) / 16000
        tom = (0.6 * np.sin(2 * np.pi * 440 * t) * ((t % 1.0) < 0.5)).astype(np.float32)
        self.assertEqual(_alimentar(palmas.DetectorPalmas(), tom), 0)

    @unittest.skipUnless(WAV_FALA.exists(), "wav de fala do Kokoro ausente")
    def test_fala_real_nao_dispara(self):
        import soundfile as sf
        fala, taxa = sf.read(WAV_FALA, dtype="float32")
        x = np.interp(np.arange(0, len(fala), taxa / 16000), np.arange(len(fala)), fala)
        sinal = np.concatenate([_fundo(1.0), x.astype(np.float32), _fundo(1.0)])
        self.assertEqual(_alimentar(palmas.DetectorPalmas(), sinal), 0)


# ---------------------------------------------------------------------------

class _EstadoFalso:
    def __init__(self):
        self.atualizacoes, self.logs = [], []

    def atualizar(self, canal, **v):
        self.atualizacoes.append((canal, v))

    def registrar(self, *a, **k):
        self.logs.append(a)


class TestPonte(unittest.TestCase):
    # par de eventos exatamente como observado no servidor desta instalacao
    PAR = [
        {"type": "inference_start", "data": {"model": "qwen3.5:0.8b", "engine": "multi"}},
        {"type": "inference_start", "data": {"model": "qwen3.5:0.8b", "message_count": 2}},
        {"type": "inference_end", "data": {"model": "qwen3.5:0.8b", "latency": 13.15,
                                           "usage": {"prompt_tokens": 552, "completion_tokens": 2},
                                           "ttft": 4.9, "throughput_tok_per_sec": 0.15,
                                           "energy_joules": 0.0, "power_watts": 0.0}},
        {"type": "inference_end", "data": {"model": "qwen3.5:0.8b", "content": "Ok",
                                           "usage": {"completion_tokens": 2}}},
    ]

    def test_par_duplo_conta_uma_inferencia_e_volta_a_zero(self):
        e = _EstadoFalso()
        p = ponte.Ponte(e)
        profundidades = []
        for ev in self.PAR:
            p.processar(ev)
            profundidades.append(p._profundidade)
        self.assertEqual(profundidades, [1, 2, 1, 0])
        ultimas = [v["ultima"] for c, v in e.atualizacoes if "ultima" in v]
        self.assertEqual(len(ultimas), 1)                 # metrica de um so evento
        m = ultimas[0]
        self.assertEqual(m["latencia_s"], 13.15)
        self.assertIsNone(m["energia_j"])                 # 0.0 sem medidor = nao medido
        self.assertIsNone(m["potencia_w"])
        self.assertNotIn("content", json.dumps(e.atualizacoes))   # texto nunca repassado

    def test_fim_sem_inicio_nao_fica_negativo(self):
        p = ponte.Ponte(_EstadoFalso())
        p.processar({"type": "inference_end", "data": {}})
        self.assertEqual(p._profundidade, 0)


# ---------------------------------------------------------------------------

class TestEstadoEAudio(unittest.TestCase):
    def test_atualizacao_difunde_canal_e_incrementa_versao(self):
        e = estado.Estado()
        q = e.inscrever()
        v0 = e.instantaneo()["versao"]
        e.atualizar("microfone", estado="ouvindo")
        linha = q.get(timeout=1)
        self.assertIn("event: canal", linha)
        self.assertEqual(e.instantaneo()["versao"], v0 + 1)
        self.assertEqual(e.ler("microfone")["estado"], "ouvindo")

    def test_nivel_e_limitado_por_taxa(self):
        e = estado.Estado()
        q = e.inscrever()
        for _ in range(50):
            e.nivel("entrada", 0.1, None, taxa_hz=20)
        self.assertEqual(q.qsize(), 1)

    def test_bandas_de_um_seno_de_1khz(self):
        t = np.arange(2048) / 16000
        b = audio.bandas(np.sin(2 * np.pi * 1000 * t).astype(np.float32), 16000)
        limites = np.geomspace(80, 8000, audio.N_BANDAS + 1)
        esperada = int(np.searchsorted(limites, 1000)) - 1
        self.assertEqual(int(np.argmax(b)), esperada)
        self.assertEqual(audio.bandas(np.zeros(2048, np.float32), 16000), [0.0] * audio.N_BANDAS)

    def test_limiar_pela_mediana_ignora_um_estouro(self):
        ruido, limiar = audio.calcular_limiar([300] * 30 + [20000])
        self.assertEqual(ruido, 300)
        self.assertEqual(limiar, 780)

    def test_filtro_descarta_transcricao_sem_fala(self):
        f = audio.filtrar_transcricao
        self.assertEqual(f("..."), "")                     # o caso real observado
        self.assertEqual(f(" ?! "), "")
        self.assertEqual(f("Legendas pela comunidade Amara.org"), "")
        self.assertEqual(f("Quanto é dois mais dois?"), "Quanto é dois mais dois?")
        self.assertEqual(f("Obrigado"), "Obrigado")         # fala plausivel: mantida

    def test_so_responde_quando_chamado_pelo_nome(self):
        from hud_runtime.voz import chamou_jarvis
        for dirigida in ("Jarvis, que horas são?", "Ô Jarbas, liga a luz", "djarvis tudo bem",
                         "Jarves quanto é dois mais dois", "JARVIS!"):
            self.assertTrue(chamou_jarvis(dirigida), dirigida)
        for casa in ("Vai vim comer, amor!", "Quanto é dois mais dois?", "Janta tá pronta",
                     "cadê as chaves", "o jardim tá bonito"):
            self.assertFalse(chamou_jarvis(casa), casa)

    def test_limpar_resposta(self):
        self.assertEqual(limpar_resposta("<think>x</think> **Ola**, tudo _bem_?"), "Ola, tudo bem?")
        self.assertEqual(limpar_resposta("<think>sem fim"), "")


class TestTelemetria(unittest.TestCase):
    def test_cpu_precisa_de_duas_amostras(self):
        c = telemetria._Cpu()
        self.assertEqual(c.medir()["status"], "aguardando")
        time.sleep(0.2)
        m = c.medir()
        self.assertIn(m["status"], ("medido", "aguardando"))
        if m["status"] == "medido":
            self.assertTrue(0 <= m["uso_pct"] <= 100)

    def test_memoria_e_disco_medidos(self):
        m = telemetria.memoria()
        self.assertEqual(m["status"], "medido")
        self.assertGreater(m["total_gb"], m["livre_gb"])
        self.assertEqual(telemetria.disco()["status"], "medido")


# ---------------------------------------------------------------------------

class _RtFalso:
    token = "tok-teste"

    def __init__(self):
        self.encerrando = threading.Event()
        self.estado = estado.Estado()
        self.prefs = preferencias.Preferencias(Path(tempfile.mkdtemp()) / "p.json")
        self.acoes = []

    def acao(self, rota, corpo):
        self.acoes.append((rota, corpo))
        if rota != "/api/microfone":
            raise KeyError(rota)
        return {"ok": True}

    def dados_classicos(self):
        return "window.DADOS = {};"

    def prefs_publicas(self):
        return {**self.prefs.ler(), "agenda_configurada": False}


def _porta_livre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class TestHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rt = _RtFalso()
        cls.porta = _porta_livre()
        cls.srv = servidor_http.criar(cls.rt, cls.porta)
        servidor_http.rodar(cls.srv)
        cls.base = f"http://127.0.0.1:{cls.porta}"

    @classmethod
    def tearDownClass(cls):
        cls.rt.encerrando.set()
        cls.srv.shutdown()

    def _req(self, caminho, metodo="GET", corpo=None, cab=None):
        req = urllib.request.Request(self.base + caminho, method=metodo,
                                     data=json.dumps(corpo).encode() if corpo is not None else None,
                                     headers=cab or {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def test_host_estranho_e_recusado(self):
        self.assertEqual(self._req("/api/estado", cab={"Host": "evil.example:80"})[0], 403)

    def test_post_sem_token_recusado(self):
        self.assertEqual(self._req("/api/microfone", "POST", {"ativo": True})[0], 403)

    def test_post_de_outra_origem_recusado(self):
        cab = {"X-Jarvis-Token": "tok-teste", "Origin": "http://evil.example"}
        self.assertEqual(self._req("/api/microfone", "POST", {"ativo": True}, cab)[0], 403)

    def test_post_valido_chega_na_acao(self):
        cab = {"X-Jarvis-Token": "tok-teste", "Origin": self.base,
               "Content-Type": "application/json"}
        codigo, _, corpo = self._req("/api/microfone", "POST", {"ativo": False}, cab)
        self.assertEqual(codigo, 200)
        self.assertIn(("/api/microfone", {"ativo": False}), self.rt.acoes)

    def test_nenhuma_origem_recebe_cors(self):
        for origem in ("http://127.0.0.1:8000", "http://evil.example"):
            _, cab, _ = self._req("/api/estado", cab={"Origin": origem})
            self.assertNotIn("Access-Control-Allow-Origin", cab)

    def test_traversal_bloqueado(self):
        self.assertEqual(self._req("/hud/../jarvis_runtime.py")[0], 404)
        self.assertEqual(self._req("/hud/..%5cjarvis_runtime.py")[0], 404)

    def test_tela_tem_csp_e_token_injetado(self):
        codigo, cab, corpo = self._req("/jarvis")
        self.assertEqual(codigo, 200)
        self.assertIn("script-src 'self'", cab.get("Content-Security-Policy", ""))
        self.assertIn(b"tok-teste", corpo)
        self.assertNotIn(b"{{TOKEN}}", corpo)

    def test_segundo_runtime_nao_ocupa_a_mesma_porta(self):
        # no Windows, SO_REUSEADDR deixava dois processos na mesma porta
        with self.assertRaises(OSError):
            servidor_http.criar(self.rt, self.porta)

    def test_camera_exige_token_e_camera_ligada(self):
        self.assertEqual(self._req("/api/camera.mjpg")[0], 403)
        self.assertEqual(self._req("/api/camera.mjpg?token=errado")[0], 403)
        self.assertEqual(self._req("/api/camera.mjpg?token=tok-teste")[0], 403)
        self.assertEqual(self._req("/api/camera.mjpg", cab={"Cookie": "jarvis_hud_session=tok-teste"})[0], 409)

    def test_contexto_privado_exige_sessao(self):
        for rota in ("/api/estado", "/api/telemetria", "/api/preferencias", "/api/eventos", "/classico/dados.js"):
            with self.subTest(rota=rota):
                self.assertEqual(self._req(rota)[0], 403)
        self.assertEqual(self._req("/api/saude")[0], 200)

    def test_tela_autoriza_leitura_sem_token_na_url(self):
        _, cab, _ = self._req("/jarvis")
        cookie = cab["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertEqual(self._req("/api/estado", cab={"Cookie": cookie.split(";", 1)[0]})[0], 200)
        self.assertEqual(self._req("/api/estado", cab={"Cookie": cookie.split(";", 1)[0], "Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self._req("/api/estado", cab={"X-Jarvis-Token": "tok-teste"})[0], 200)

    def test_sse_entrega_retrato_inicial(self):
        req = urllib.request.Request(self.base + "/api/eventos", headers={"Cookie": "jarvis_hud_session=tok-teste"})
        with urllib.request.urlopen(req, timeout=5) as r:
            recebido = b""
            while b"event: preferencias" not in recebido:
                recebido += r.read1(4096)
        self.assertIn(b"event: estado", recebido)
        self.assertIn(b"event: telemetria", recebido)


if __name__ == "__main__":
    unittest.main()
