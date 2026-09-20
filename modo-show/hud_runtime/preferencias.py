"""Preferencias persistentes do HUD, validadas campo a campo.

Ficam em ~/.openjarvis/hud-preferencias.json, fora do repositorio.
Campo invalido ou desconhecido e ignorado e o padrao prevalece: um arquivo
editado a mao nunca impede o runtime de subir.
"""

from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any

ARQUIVO = Path(os.environ.get("OPENJARVIS_HOME", Path.home() / ".openjarvis")) / "hud-preferencias.json"

PADRAO: dict[str, Any] = {
    "tema": "hud",                    # hud | classico
    "estilo_nucleo": "reator",        # reator (como no filme) | abstrato | olhos | orbe (particulas, projeto C)
    "cor_tema": "ciano",              # ciano (filme) | dourado (alternativa do projeto C)
    "perfil_grafico": "equilibrado",  # economico | equilibrado | cinematografico
    "brilho": 0.8,                    # 0.2 .. 1.0
    "movimento": "normal",            # normal | reduzido
    "boot_animado": True,
    "sons_interface": False,
    "saudacao": True,
    "nome_usuario": "Mateus",
    "escuta_automatica": True,
    "exigir_nome": True,              # so responde falas com "Jarvis"
    "janela_conversa_s": 30,          # depois de responder, escuta sem precisar do nome
    "manter_modelo_voz": True,        # modelo da voz carregado enquanto o microfone esta ligado
    "voz_rapida": True,               # voz sem o laco do agente (sem ferramentas), bem mais rapida
    "voz_tts": "pm_alex",             # voz do Kokoro: pm_alex (masculina, como no filme) | pm_santa | pf_dora
    "voz_provedor": "kokoro",         # kokoro | sapi | piper | edge | azure | google | elevenlabs | fish
    "voz_remota": "",                 # voz/modelo do provedor escolhido (ex.: pt-BR-AntonioNeural, id da fish.audio)
    "voz_muda": False,                # modo texto: responde so na tela
    "interromper_por_voz": True,      # "pare"/"silencio" durante a resposta
    "ferramentas_voz": True,          # o modelo pode executar acoes (camera, lembretes, musica...)
    "falas_proativas": True,          # (antiga) False = modo sob_demanda
    "modo_proativo": "assistido",     # sob_demanda | assistido | proativo (ver anunciador.py)
    "silencio_inicio": 22,            # horario de silencio das falas proativas (hora)
    "silencio_fim": 7,
    "modo_foco": False,              # avisos espontaneos ficam no painel enquanto trabalha
    "avisos_canal": "voz",           # voz | painel; pedidos explicitos preservam lembretes
    "avisos_intervalo_s": 30,         # intervalo entre falas espontaneas comuns
    "avisos_deduplicacao_s": 300,     # mesma ocorrencia nao e repetida por reconexao
    "boas_vindas": True,              # "Bem-vindo de volta" ao voltar para a frente da camera
    "resumo_diario": True,            # resumo do dia na primeira vez que ele te ve no dia
    "noticias_fontes": ["g1", "bbc"],
    "modelo_voz": "qwen3.5:4b",
    "modelo_reserva": "qwen3.5:4b",   # usado quando o principal nao cabe na memoria ou falha (vazio = sem reserva)
    "espera_modelo_s": 120,           # sem a primeira palavra nesse tempo, troca para a reserva
    "stt_motor": "whisper",           # whisper (mais preciso) | vosk (projeto B: offline e leve)
    "stt_modelo": "small",            # small (entende melhor, ~3 s) | base (mais rapido, erra mais)
    "volume": 1.0,                    # 0.0 .. 1.0
    "abrir": {"jarvis": True, "painel": True, "chat": True},
    "camera_ao_iniciar": False,       # a camera so liga quando voce pede
    "reconhecer_pessoas": True,       # rostos/vozes CADASTRADOS por comando (autorizado pelo Senhor em 19/09)
    "so_o_dono": False,               # com a voz do Senhor cadastrada: so ela da comandos
    "avisos_no_celular": True,        # com o Telegram pareado: vigia, lembretes e monitores vao ao celular
    "tarifa_kwh": 0.0,                # R$/kWh para o consumo em reais (0 = nao informada)
    "estilo_conversa": "natural",     # natural (como o Copilot do video) | breve (1-2 frases)
    "fala_em_fluxo": True,            # fala cada frase enquanto o modelo ainda escreve
    "visao_na_conversa": "auto",      # auto (imagem quando a pergunta e visual) | sempre | nunca
    "visao_tempo_real": True,         # com a camera ligada: caixas ao vivo nos objetos (detector local)
    "visao_automatica": False,        # com a camera ligada: objeto mostrado na regiao -> ele diz o que e
    "visao_regiao": "centro",         # centro | mesa (metade de baixo) | inteira
    "notificacoes_windows": True,     # avisos tambem como notificacao do Windows
    "capacete": "automatico",         # visao do capacete: automatico (ao ver um rosto) | sempre | desligado
    "capacete_imagem": True,          # mostra a imagem da camera por tras do HUD (False = rosto holografico)
    "espelhar_camera": True,          # imagem como num espelho
    "local_clima": None,              # {"nome","regiao","pais","lat","lon"}
    "climas_extras": [],              # ate 3 cidades a mais, no mesmo formato
    "pastas_monitoradas": None,       # None = Area de Trabalho + Documentos
    "widgets_painel": {"projeto": True, "casa": True, "celular": True, "vozcat": True, "rotinas": True, "openjarvis": True, "secretario": True, "email": True, "noticias": True,
                       "modelos": True, "inferencia": True, "servicos": True,
                       "voz": True, "eventos": True, "clima": True, "agenda": True,
                       "tarefas": True, "notificacoes": True, "midia": True, "rede": True,
                       "apps": True, "downloads": True, "pastas": True, "dispositivos": True,
                       "custos": True, "historico": True, "automacoes": True},
    "widgets_jarvis": {"relogio": True, "clima": True, "energia": True, "midia": True,
                       "camera": True, "onda": True},
    # rotinas do projeto B, adaptadas: frases exatas; fechar so os apps da rotina, com WM_CLOSE
    "rotina_chegada": {"frases": ["cheguei", "estou em casa", "voltei", "papai chegou"], "apps": [], "sites": [],
                       "som": "", "resumo": True, "volume": None},
    "rotina_descanso": {"frases": ["vou descansar", "hora de descansar", "vou dormir", "encerrar o dia"],
                        "fechar_apps": True, "parar_musica": True, "desligar_camera": True, "acao_final": "nada"},
}

_ENUMS = {
    "tema": {"hud", "classico"},
    "estilo_nucleo": {"reator", "abstrato", "olhos", "orbe"},
    "cor_tema": {"ciano", "dourado"},
    "perfil_grafico": {"economico", "equilibrado", "cinematografico"},
    "movimento": {"normal", "reduzido"},
    "capacete": {"automatico", "sempre", "desligado"},
    "voz_tts": {"pm_alex", "pm_santa", "pf_dora"},
    "voz_provedor": {"kokoro", "sapi", "piper", "edge", "azure", "google", "elevenlabs", "fish"},
    "modo_proativo": {"sob_demanda", "assistido", "proativo"},
    "avisos_canal": {"voz", "painel"},
    "visao_regiao": {"centro", "mesa", "inteira"},
    "stt_motor": {"whisper", "vosk"},
    "stt_modelo": {"small", "base"},
    "estilo_conversa": {"natural", "breve"},
    "visao_na_conversa": {"auto", "sempre", "nunca"},
}
_FAIXAS = {"espera_modelo_s": (20, 600), "tarifa_kwh": (0.0, 10.0), "brilho": (0.2, 1.0), "volume": (0.0, 1.0), "janela_conversa_s": (0, 120),
           "avisos_intervalo_s": (0, 3600), "avisos_deduplicacao_s": (0, 86400),
           "silencio_inicio": (0, 23), "silencio_fim": (0, 23)}
_TEXTOS = {"nome_usuario": 40, "modelo_voz": 80, "modelo_reserva": 80, "voz_remota": 120}


def _local(valor: Any) -> dict[str, Any] | None:
    if (isinstance(valor, dict) and isinstance(valor.get("nome"), str)
            and all(isinstance(valor.get(k), (int, float)) and not isinstance(valor.get(k), bool)
                    for k in ("lat", "lon"))
            and -90 <= valor["lat"] <= 90 and -180 <= valor["lon"] <= 180):
        return {"nome": valor["nome"][:80], "lat": float(valor["lat"]), "lon": float(valor["lon"]),
                "regiao": str(valor.get("regiao") or "")[:80] or None,
                "pais": str(valor.get("pais") or "")[:80] or None}
    return None


def validar(entrada: dict[str, Any], base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Aplica apenas os campos validos de `entrada` sobre `base`."""
    saida = copy.deepcopy(base if base is not None else PADRAO)
    if not isinstance(entrada, dict):
        return saida
    if entrada.get("modo_proativo") in _ENUMS["modo_proativo"]:
        saida["falas_proativas"] = True           # o modo novo manda; a chave antiga deixa de silenciar
    for chave, valor in entrada.items():
        if chave not in PADRAO:
            continue
        padrao = PADRAO[chave]
        if chave == "local_clima":
            if valor is None:
                saida[chave] = None
            elif _local(valor):
                saida[chave] = _local(valor)
            continue
        if chave == "climas_extras":
            if isinstance(valor, list):
                saida[chave] = [lc for lc in (_local(v) for v in valor) if lc]
            continue
        if chave in ("rotina_chegada", "rotina_descanso"):
            from .rotinas import validar_rotina
            saida[chave] = validar_rotina({**saida[chave], **valor} if isinstance(valor, dict) else None, PADRAO[chave])
            continue
        if chave == "noticias_fontes":
            if isinstance(valor, list):
                from .noticias import FONTES
                saida[chave] = [f for f in valor if f in FONTES][:6] or ["g1"]
            continue
        if chave == "pastas_monitoradas":
            if valor is None:
                saida[chave] = None
            elif isinstance(valor, list):
                saida[chave] = [p.strip()[:260] for p in valor if isinstance(p, str) and p.strip()][:8]
            continue
        if chave in _ENUMS:
            if valor in _ENUMS[chave]:
                saida[chave] = valor
        elif chave in _FAIXAS:
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                lo, hi = _FAIXAS[chave]
                saida[chave] = round(min(max(float(valor), lo), hi), 3)
        elif chave in _TEXTOS:
            if isinstance(valor, str) and valor.strip():
                saida[chave] = valor.strip()[: _TEXTOS[chave]]
        elif isinstance(padrao, bool):
            if isinstance(valor, bool):
                saida[chave] = valor
        elif isinstance(padrao, dict):
            if isinstance(valor, dict):
                for k, v in valor.items():
                    if k in padrao and isinstance(v, bool):
                        saida[chave][k] = v
    # cidades extras sem repetir entre si nem a principal (mesmo lugar = mesma lat/lon)
    principal = saida.get("local_clima")
    vistos = {(round(principal["lat"], 2), round(principal["lon"], 2))} if principal else set()
    extras = []
    for lc in saida.get("climas_extras") or []:
        chave_lugar = (round(lc["lat"], 2), round(lc["lon"], 2))
        if chave_lugar not in vistos:
            vistos.add(chave_lugar)
            extras.append(lc)
    saida["climas_extras"] = extras[:3]
    return saida


class Preferencias:
    def __init__(self, arquivo: Path = ARQUIVO) -> None:
        self._arquivo = arquivo
        self._trava = threading.Lock()
        self._dados = self._carregar()

    def _carregar(self) -> dict[str, Any]:
        try:
            return validar(json.loads(self._arquivo.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return copy.deepcopy(PADRAO)

    def ler(self) -> dict[str, Any]:
        with self._trava:
            return copy.deepcopy(self._dados)

    def aplicar(self, mudancas: dict[str, Any]) -> dict[str, Any]:
        with self._trava:
            self._dados = validar(mudancas, self._dados)
            self._arquivo.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._arquivo.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._dados, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, self._arquivo)     # gravacao atomica
            return copy.deepcopy(self._dados)
