"""Runtime do Jarvis: estado real + telas HUD + conversa por voz.

Uso:
    jarvis_runtime.py                     abre as janelas das preferencias
    jarvis_runtime.py --janelas jarvis    so a tela Jarvis
    jarvis_runtime.py --sem-janelas       so o servico (telas via navegador)
    jarvis_runtime.py --porta 8765

Se ja houver um runtime rodando, apenas traz as janelas pedidas para frente.
Estado da instancia: ~/.openjarvis/hud-runtime.json (pid, porta, token).
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path(os.environ.setdefault("OPENJARVIS_HOME", str(Path.home() / ".openjarvis")))
CACHE_HF = Path.home() / ".cache" / "huggingface" / "hub"

def _voz_configurada() -> str:
    try:
        import tomlkit
        c = tomlkit.parse((HOME / "config.toml").read_text(encoding="utf-8")).unwrap()
        return c.get("speech", {}).get("voice_id") or "pf_dora"
    except Exception:  # noqa: BLE001
        return "pf_dora"


# Tudo o que a voz precisa ja esta no cache: nao consulta a internet a cada
# abertura (a promessa e funcionar offline, e a consulta atrasava a sintese).
# Se a voz configurada NAO estiver em cache (ex.: trocada depois), deixa o
# download acontecer em vez de falhar por causa do modo offline.
_voz_em_cache = any((CACHE_HF / "models--hexgrad--Kokoro-82M" / "snapshots").glob(
    f"*/voices/{_voz_configurada()}.pt"))
if _voz_em_cache and (CACHE_HF / "models--Systran--faster-whisper-base").exists():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Bibliotecas do HUD (psutil, opencv, pycaw, winrt, icalendar) ficam em _libs,
# fora do venv: um `uv sync` apagaria pacotes extras do venv. Vao no FIM do
# path para o venv ter precedencia (numpy, dateutil etc. continuam os dele).
sys.path.append(str(Path(__file__).resolve().parent / "_libs"))

# O winrt (midia do Windows) traz uma msvcp140.dll antiga. Se ela carregar
# antes do torch/ctranslate2, os dois falham com WinError 1114 e a voz morre
# (sintese e transcricao). Carrega-los aqui, primeiro, fixa a versao certa.
import ctranslate2  # noqa: E402,F401
import torch  # noqa: E402,F401

from hud_runtime import PORTA_PADRAO, boot, janelas, midia, servidor_http, sistema  # noqa: E402
from hud_runtime.agenda import Agenda, gravar_segredo, ler_segredo  # noqa: E402
from hud_runtime.anunciador import Anunciador  # noqa: E402
from hud_runtime.atalhos import Atalhos  # noqa: E402
from hud_runtime.vozes import PROVEDORES, Vozes  # noqa: E402
from hud_runtime.comandos import Comandos  # noqa: E402
from hud_runtime.noticias import Noticias  # noqa: E402
from hud_runtime.cotacoes import Cotacoes  # noqa: E402
from hud_runtime.memoria import Memoria  # noqa: E402
from hud_runtime.pesquisa import Pesquisa  # noqa: E402
from hud_runtime.rotinas import definir_inicio_com_windows, inicio_com_windows  # noqa: E402
from hud_runtime.monitores import Monitores  # noqa: E402
from hud_runtime import openjarvis_info  # noqa: E402
from hud_runtime.olhar import ObservadorObjeto  # noqa: E402
from hud_runtime.percepcao import Percepcao  # noqa: E402
from hud_runtime.rede import baixar  # noqa: E402
from hud_runtime.secretario import Secretario  # noqa: E402
from hud_runtime.visao import Visao  # noqa: E402
from hud_runtime.avisos_windows import AvisosWindows, vai_para_o_windows  # noqa: E402
from hud_runtime.audio import Microfone, Reprodutor, Sintese, Transcricao  # noqa: E402
from hud_runtime.camera import Camera  # noqa: E402
from hud_runtime.clima import Clima, buscar_cidades  # noqa: E402
from hud_runtime.estado import Estado  # noqa: E402
from hud_runtime.google_agenda import ErroGoogle, GoogleAgenda  # noqa: E402
from hud_runtime.notificacoes import Notificacoes, Vigia  # noqa: E402
from hud_runtime.ponte import Ponte  # noqa: E402
from hud_runtime.preferencias import Preferencias  # noqa: E402
from hud_runtime.tarefas import Tarefas  # noqa: E402
from hud_runtime.telemetria import Amostrador  # noqa: E402
from hud_runtime.voz import Conversa  # noqa: E402

ARQ_INSTANCIA = HOME / "hud-runtime.json"
JANELAS_VALIDAS = ("jarvis", "painel", "chat", "holograma")


class Runtime:
    def __init__(self, porta: int) -> None:
        import hashlib
        base_codigo = Path(__file__).resolve().parent
        arquivos_codigo = [Path(__file__), *sorted((base_codigo / "hud_runtime").glob("*.py")),
                           *sorted(base_codigo.glob("tela*.html")),
                           *sorted(p for p in (base_codigo / "hud").rglob("*")
                                   if p.suffix.lower() in (".html", ".js", ".css"))]
        self.versao_codigo = hashlib.sha256(b"".join(p.read_bytes() for p in arquivos_codigo)).hexdigest()[:16]
        self.porta = porta
        self.token = secrets.token_urlsafe(24)
        self.encerrando = threading.Event()
        self.estado = Estado()
        self.prefs = Preferencias()
        self.reprodutor = Reprodutor(self.estado)
        self.reprodutor.volume(self.prefs.ler()["volume"])
        self.sintese = Sintese()
        self.transcricao = Transcricao(motor=lambda: self.prefs.ler().get("stt_motor", "whisper"),
                                       tamanho=lambda: self.prefs.ler().get("stt_modelo", "small"))
        self.ponte = Ponte(self.estado, medidor=lambda: (sistema.sensores() or {}).get("energia_pacote_j"))
        self.clima = Clima()
        self.google = GoogleAgenda(porta)
        self.agenda = Agenda(self.google)
        self.avisos_windows = AvisosWindows(HOME / "icon.ico")
        self.notificacoes = Notificacoes(self.estado, ao_notificar=self._aviso_windows)
        self.tarefas = Tarefas(ao_mudar=lambda itens: self.estado.atualizar("tarefas", itens=itens))
        self.estado.atualizar("tarefas", itens=self.tarefas.listar())
        self.camera = Camera(self.estado, ao_presenca=self._presenca, ao_quadro=self._rostos_no_quadro,
                             ao_imagem=self._olhar_quadro)
        self.olhar = ObservadorObjeto(self._objeto_na_regiao)
        self.percepcao = None                                  # criada junto com a visao, mais abaixo
        self._ultimo_quadro = None                             # so na memoria: a percepcao olha o mais recente
        self._tempo_real_cache = (0.0, False)
        from hud_runtime.identidade import Cadastro, Falantes, Rostos
        self.identidades = Cadastro()                           # so numeros, so de quem foi cadastrado
        self.rostos_id = Rostos(self.identidades)
        self.falantes = Falantes(self.identidades)
        self.pessoas: tuple[float, list] = (0.0, [])            # ultimo reconhecimento de rostos
        from hud_runtime.canais import Canais
        # cada canal declara o que faz: o Jarvis nao promete audio pelo Telegram (F37)
        self.canais = Canais()
        from hud_runtime.selecao import Selecionador
        # uma autoridade so de selecao: o que o mouse marca na mesa e o mesmo
        # "isso" que a voz altera (§10)
        self.selecao = Selecionador(publicar=lambda c: self.estado.atualizar("selecao", **c))
        from hud_runtime.gestos import Gestos
        self.gestos = Gestos(self.selecao, lambda c: self.estado.atualizar("gestos", **c),
                             camera_ativa=lambda: self.camera.ativa)
        self._identificando = threading.Event()
        self._id_em = 0.0
        self.holograma_modelo = None                            # Path do modelo 3D que a mesa mostra
        from hud_runtime.apresentacao import Apresentacao
        self.apresentacao = Apresentacao(lambda **c: self.estado.atualizar("apresentacao", **c))
        self.holograma_grafico = None                           # ultimo grafico mandado a mesa
        self.ultimo_projeto = None                              # ultima peca projetada (para "abra no Cura")
        self._olhar_prefs = (0.0, False, "centro")
        self._olhando = threading.Event()
        self.microfone = Microfone(self.estado, ocupado=lambda: self.conversa.ocupada(),
                                   ouvir_interrupcao=lambda: self.prefs.ler().get("interromper_por_voz", True))
        self.conversa = Conversa(self.estado, self.prefs, self.microfone, self.transcricao,
                                 self.sintese, self.reprodutor,
                                 ponte_conectada=lambda: self.ponte.conectada,
                                 clima=self.clima, tarefas=self.tarefas)
        self.noticias = Noticias()
        self.amostrador = Amostrador(self.estado, prefs=self.prefs, clima=self.clima,
                                     agenda=self.agenda, vigia=Vigia(self.notificacoes), extras={
                                         "noticias": (300, lambda: self.noticias.obter(self.prefs.ler().get("noticias_fontes"))),
                                         "email": (120, self.google.emails),
                                         "openjarvis": (300, openjarvis_info.resumo),
                                     })
        # secretario do filme: lembretes/timers/notas, visao, comandos por voz, falas proativas
        self.secretario = Secretario(ao_mudar=lambda d: self.estado.atualizar("secretario", **d),
                                     ao_vencer=self._lembrete_venceu)
        self.visao = Visao(self.estado, self.camera, self.prefs)
        self.percepcao = Percepcao(self.visao.perguntar_imagem, self.estado)
        from hud_runtime.deteccao import Detector, VisaoContinua
        from hud_runtime.deteccao import Vigia as VigiaCamera          # (Vigia = o das notificacoes)
        self.visao_continua = VisaoContinua(                   # caixas ao vivo, so com a camera ligada
            Detector(), quadro=lambda: self._ultimo_quadro,
            ativo=lambda: self.camera.ativa and self._tempo_real(),
            publicar=self._deteccoes, ocupado=lambda: self.conversa.ocupada())
        self.vigia = VigiaCamera()
        self.comandos = Comandos(self, publicar_pagina=lambda c: self.estado.publicar("comando", c))
        self.conversa.comandos = self.comandos
        from hud_runtime.entrada import Entrada
        self.entrada = Entrada(self, HOME / "hud-pedidos.sqlite")
        self.memoria = Memoria()
        self.conversa.memoria = self.memoria
        self.cotacoes = Cotacoes()
        self.pesquisa = Pesquisa(self.noticias)
        self.vozes = Vozes(self.sintese, self.prefs,
                           registrar=lambda t, n: self.estado.registrar("voz", t, n))
        self.conversa.vozes = self.vozes
        self.anunciador = Anunciador(falar=self._falar_anuncio, ocupado=self._alguem_falando,
                                     prefs=self.prefs,
                                     registrar=lambda t: self.estado.registrar("anuncio", t),
                                     mostrar=lambda t: self.estado.atualizar("anuncio", texto=t, em=time.time()))
        self.conversa.anunciador = self.anunciador
        self.conversa.visao_contexto = self._visao_para_conversa
        self.conversa.falantes = self.falantes
        self.monitores = Monitores(self._monitor_avisou, noticias=self.noticias, cotacoes=self.cotacoes,
                                   baixar=baixar, ao_mudar=lambda itens: self.estado.atualizar("monitores", itens=itens))
        from hud_runtime.telegram import PonteTelegram
        self.telegram = PonteTelegram(self._atender_remoto, ler_segredo, gravar_segredo,
                                      lambda o, t, n="info": self.estado.registrar(o, t, n))
        self.atalhos = Atalhos({"falar": self._atalho_falar, "parar": self.conversa.interromper},
                               registrar=lambda t, n: self.estado.registrar("atalho", t, n))
        self._saiu_em: float | None = None
        self._varias_desde: float | None = None
        self._aviso_pessoas_em = 0.0
        self._http = None

    # ---- falas proativas --------------------------------------------------

    def _atalho_falar(self) -> None:
        if not self.microfone.ativo and self.transcricao.pronta:
            self.microfone.ativar()
        self.conversa.escutar_agora()

    def _alguem_falando(self) -> bool:
        return bool(self.entrada.ativo) or self.conversa.ocupada() or (self.estado.ler("microfone") or {}).get("estado") == "captando"

    def _falar_anuncio(self, texto: str) -> None:
        # Nao fica esperando uma conversa com um aviso que pode perder validade:
        # se um novo pedido conquistou a vez, o resultado vai so para o painel.
        if not self.conversa._pedido_lock.acquire(blocking=False):
            self.estado.atualizar("anuncio", texto=texto, em=time.time())
            return
        try:
            self.estado.atualizar("anuncio", texto=texto, em=time.time())
            self.estado.atualizar("conversa", ultima_resposta=texto, em=time.time())
            self.conversa.falar(texto)
        finally:
            self.conversa._pedido_lock.release()

    def _trat(self) -> str:
        return self.prefs.ler().get("nome_usuario") or "Senhor"

    def _lembrete_venceu(self, item: dict) -> None:
        t = self._trat()
        if item.get("tipo") == "rotina" and item.get("comando"):
            threading.Thread(target=self._rodar_rotina, args=(item,), name="rotina", daemon=True).start()
            return
        if item.get("tipo") == "timer":
            fala = f"{t}, o tempo acabou."
        elif item.get("tipo") == "alarme":
            fala = f"{t}, seu alarme."
        else:
            fala = f"{t}, lembrete: {item['texto']}." + (" Desculpe o atraso." if item.get("atrasado") else "")
        self._no_celular(fala)
        self.notificacoes.notificar(fala, "aviso", "lembrete")
        self.anunciador.anunciar(fala, pedido_pelo_usuario=True,
                                 chave=f"lembrete-{item.get('id')}-{item.get('vencido_em', item.get('quando'))}")

    def _rodar_rotina(self, item: dict) -> None:
        """Rotina agendada ("todo dia às 7h me dê o resumo do dia"): executa e fala o resultado.
        Confere de novo, na hora, se o comando continua permitido."""
        from hud_runtime.protocolos import PROIBIDOS
        comando = item["comando"]
        try:
            achado = self.comandos.interpretar(comando)
            if achado is None or achado[0] in PROIBIDOS:
                fala = f"{self._trat()}, não executei a rotina \"{comando}\": não é um comando permitido."
            else:
                fala = self.comandos.executar(achado[0], achado[1], comando) or f"Rotina \"{comando}\" executada."
        except Exception as e:  # noqa: BLE001 - rotina com problema nao derruba o runtime
            fala = f"{self._trat()}, a rotina \"{comando}\" falhou: {str(e)[:80]}."
        self.estado.registrar("rotina", f"rotina agendada: {comando}", "info")
        self.anunciador.anunciar(fala, pedido_pelo_usuario=True, validade_s=900)

    # ---- olhar automatico (objeto mostrado na regiao definida) -----------------
    def _olhar_quadro(self, img, rostos) -> None:
        self._ultimo_quadro = img                              # so na memoria (o proximo quadro substitui)
        self.gestos.oferecer(img)                              # opt-in; nunca abre outra câmera
        self._talvez_identificar(img, rostos)
        agora = time.monotonic()
        if agora - self._olhar_prefs[0] > 1.0:                 # le as preferencias no maximo 1x/s
            p = self.prefs.ler()
            self._olhar_prefs = (agora, bool(p.get("visao_automatica")), p.get("visao_regiao", "centro"))
        _, ligado, regiao = self._olhar_prefs
        if not ligado:
            if self.olhar.fase != "aprendendo":
                self.olhar.reiniciar()
                self.estado.atualizar("visao", olhar=None)
            return
        self.olhar.definir_regiao(regiao)
        antes = self.olhar.fase
        fase = self.olhar.processar(img, rostos)
        if fase != antes:
            self.estado.atualizar("visao", olhar=fase)

    # ---- visao em tempo real e modo vigia -----------------------------------------------
    def _tempo_real(self) -> bool:
        agora = time.monotonic()
        if agora - self._tempo_real_cache[0] > 1.0:            # le as preferencias no maximo 1x/s
            ligado = bool(self.prefs.ler().get("visao_tempo_real", True))
            self._tempo_real_cache = (agora, ligado and self.visao_continua.detector.disponivel)
        return self._tempo_real_cache[1]

    # ---- quem e quem (so cadastrados) -------------------------------------------------------
    def _talvez_identificar(self, img, rostos) -> None:
        """Com rostos na camera e alguem cadastrado: reconhece ~1x/s num fio (nao trava a camera)."""
        agora = time.time()
        if (not rostos or agora - self._id_em < 1.2 or self._identificando.is_set()
                or not self.rostos_id.disponivel or not self.identidades.ler()["rostos"]):
            if not rostos and self.pessoas[1] and agora - self.pessoas[0] > 2:
                self.pessoas = (agora, [])
                self.estado.publicar("identidades", {"pessoas": []})
            return
        if not self.prefs.ler().get("reconhecer_pessoas", True):
            return
        self._id_em = agora
        self._identificando.set()

        def rodar():
            try:
                pessoas = self.rostos_id.identificar(img)
                self.pessoas = (time.time(), pessoas)
                trat = self._trat()
                self.estado.publicar("identidades", {"pessoas": [
                    dict(p, rotulo=(trat if p["nome"] == "dono" else p["nome"]) if p["nome"] else "desconhecido")
                    for p in pessoas]})
            except Exception as e:  # noqa: BLE001 - reconhecer nunca derruba a camera
                self.estado.registrar("identidade", f"falha ao reconhecer: {e}", "aviso")
            finally:
                self._identificando.clear()
        threading.Thread(target=rodar, name="identificar", daemon=True).start()

    def so_conhecidos_na_camera(self) -> bool:
        """Rostos vistos ha pouco e TODOS cadastrados (o vigia nao dispara para o Senhor)."""
        em, pessoas = self.pessoas
        return bool(pessoas) and time.time() - em < 3 and all(p["nome"] for p in pessoas)

    def _visao_para_conversa(self):
        """(jpeg do quadro mais recente, o que o detector ve agora) -- so com a camera ligada.
        A imagem vai apenas ao modelo local, e so quando a pergunta e sobre o que se ve."""
        img = self._ultimo_quadro
        if not self.camera.ativa or img is None:
            return None, None
        import cv2
        from hud_runtime.deteccao import resumo
        h, w = img.shape[:2]
        escala = 768 / max(h, w)
        if escala < 1:
            img = cv2.resize(img, (int(w * escala), int(h * escala)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        objs = self.visao_continua.estaveis()
        vendo = resumo(objs) if objs else None
        em, pessoas = self.pessoas                             # so nomes CADASTRADOS, reconhecidos pelo rosto
        nomes = [self._trat() if p["nome"] == "dono" else p["nome"] for p in pessoas if p["nome"]]
        if nomes and time.time() - em < 5:
            vendo = (vendo + "; " if vendo else "") + "reconhecidos pelo rosto: " + ", ".join(nomes)
        return (buf.tobytes() if ok else None), vendo

    def _deteccoes(self, objs, ms) -> None:
        self.estado.publicar("deteccoes", {"objetos": objs, "ms": round(ms), "vigia": self.vigia.armado})
        self._conferir_vigia(objs)

    def vigia_ligar(self, espera_s: float = 20.0) -> str | None:
        """Arma o modo vigia (a camera liga porque o Senhor pediu). Devolve erro ou None."""
        if not self.visao_continua.detector.disponivel:
            return "O detector de objetos não está instalado, então não consigo vigiar."
        if not self.camera.ativa:
            self.camera.ativar()
        self.vigia.espera_s = espera_s
        self.vigia.ligar()
        self.estado.atualizar("vigia", ativo=True, armado_em=self.vigia.armado_em)
        self.estado.registrar("vigia", f"modo vigia armado (vale em {espera_s:.0f} s)", "info")
        return None

    def vigia_desligar(self) -> bool:
        era = self.vigia.desligar()
        if era:
            self.estado.atualizar("vigia", ativo=False, armado_em=None)
            self.estado.registrar("vigia", "modo vigia desativado", "info")
        return era

    def _conferir_vigia(self, objs) -> None:
        """Vigia armado + pessoa por 1,5 s: alerta (no maximo 1 por minuto). Nao identifica ninguem."""
        if self.vigia.armado and self.so_conhecidos_na_camera():
            self.vigia.ignorar_agora()                         # e o Senhor (ou alguem cadastrado)
            return
        if self.vigia.conferir(objs):
            agora = time.time()
            desconhecido = any(not p["nome"] for p in self.pessoas[1]) and time.time() - self.pessoas[0] < 3
            fala = (f"{self._trat()}, alerta do modo vigia: há uma pessoa "
                    f"{'desconhecida ' if desconhecido else ''}na frente da câmera.")
            self.estado.atualizar("vigia", ultimo_alerta=agora)
            self.estado.registrar("vigia", "pessoa detectada na câmera", "aviso")
            self.notificacoes.notificar(fala, "aviso", "vigia")
            self._no_celular(fala)
            self.anunciador.anunciar(fala, pedido_pelo_usuario=True, validade_s=60)

    def _previa_na_regiao(self) -> str | None:
        """O que o detector ja ve na regiao (tirando pessoas): "um celular"."""
        from hud_runtime.deteccao import no_retangulo, quantidade
        from hud_runtime.olhar import REGIOES
        caixa = REGIOES.get(self.olhar.regiao, REGIOES["centro"])
        objs = [o for o in (self.visao_continua.recentes(1.5) or [])
                if o["classe"] != 0 and o["conf"] >= 0.5 and no_retangulo(o, caixa)]
        if not objs:
            return None
        o = max(objs, key=lambda o: o["w"] * o["h"] * o["conf"])
        return quantidade(1, o["classe"])

    def _objeto_na_regiao(self, recorte) -> None:
        if self._olhando.is_set() or self.conversa.ocupada():
            return                                             # ja analisando ou falando: nao empilha
        self._olhando.set()

        def rodar():
            try:
                previa = self._previa_na_regiao()              # resposta na hora; o modelo detalha depois
                if previa:
                    self.anunciador.anunciar(f"Parece {previa}. Vou ver os detalhes.",
                                             pedido_pelo_usuario=True, validade_s=10)
                resposta = self.visao.analisar_recorte(recorte, self.olhar.regiao)
                if resposta:
                    self.estado.atualizar("contexto", tipo="visao", titulo="Análise visual",
                                          itens=[{"titulo": resposta, "fonte": f"câmera · região {self.olhar.regiao}"}],
                                          em=time.time())
                    self.anunciador.anunciar(resposta, pedido_pelo_usuario=True, validade_s=60)
            finally:
                self._olhando.clear()
        threading.Thread(target=rodar, name="olhar", daemon=True).start()

    def olhar_agora(self, esperar: bool = True):
        """Uma olhada da percepcao na regiao (camera precisa estar ligada)."""
        from hud_runtime.olhar import REGIOES
        if not self.percepcao:
            return None
        if not self.camera.ativa:
            self.camera.ativar()                               # pediu para olhar: liga a camera
        fim = time.time() + 8
        while (self._ultimo_quadro is None or not self.camera.ativa) and time.time() < fim:
            time.sleep(0.2)
        if self._ultimo_quadro is None:
            return None
        self.olhar.definir_regiao(self.prefs.ler().get("visao_regiao", "centro"))
        img = self._ultimo_quadro
        h, w = img.shape[:2]
        x, y, cw, ch = self.olhar.caixa(w, h)
        return self.percepcao.observar(img[y:y + ch, x:x + cw].copy(), self.olhar.regiao, REGIOES[self.olhar.regiao])

    def _percepcao_periodica(self) -> None:
        """A cada ~5 min, com camera e olhar automatico ligados, e SO se ninguem esta conversando."""
        while not self.encerrando.wait(20):
            try:
                p = self.prefs.ler()
                if not (p.get("visao_automatica") and self.camera.ativa and self.percepcao):
                    continue
                falou_em = (self.estado.ler("conversa") or {}).get("em") or 0
                if self.conversa.ocupada() or self._olhando.is_set() or time.time() - falou_em < 60:
                    continue
                if self.percepcao.atual and time.time() - self.percepcao.atual["em"] < 300:
                    continue
                self.olhar_agora()
            except Exception as e:  # noqa: BLE001 - a percepcao nunca derruba o runtime
                self.estado.registrar("percepcao", f"falha ao olhar: {e}", "aviso")

    def _atender_remoto(self, texto: str) -> str | None:
        """Mensagem do celular pareado: vira comando digitado (sem falar no PC). Proibidos continuam proibidos."""
        from hud_runtime.protocolos import PROIBIDOS
        achado = self.comandos.interpretar(texto)
        if achado and achado[0] in PROIBIDOS:
            return "Por segurança, isso eu só faço com o Senhor no computador."
        self.estado.registrar("telegram", f"comando do celular: {texto[:80]}")
        return self.conversa.atender(texto, falar=False)

    def _no_celular(self, fala: str) -> None:
        if self.prefs.ler().get("avisos_no_celular", True):
            threading.Thread(target=self.telegram.enviar, args=(fala,), daemon=True).start()

    def _monitor_avisou(self, texto: str) -> None:
        fala = f"{self._trat()}, {texto}"
        self._no_celular(fala)
        self.notificacoes.notificar(fala, "info", "monitor")
        self.anunciador.anunciar(fala, pedido_pelo_usuario=True, validade_s=600)

    def _resumo_ja_dado_hoje(self, marcar: bool = False) -> bool:
        arq = HOME / "hud-resumo.json"
        hoje = time.strftime("%Y-%m-%d")
        try:
            ultimo = json.loads(arq.read_text(encoding="utf-8")).get("dia")
        except (OSError, ValueError):
            ultimo = None
        if marcar:
            arq.write_text(json.dumps({"dia": hoje}), encoding="utf-8")
        return ultimo == hoje

    def _presenca(self, presente: bool) -> None:
        """Voce apareceu na camera: resumo do dia (1x por dia) ou boas-vindas."""
        agora = time.time()
        if not presente:
            self._saiu_em = agora
            return
        p = self.prefs.ler()
        fora_s = agora - self._saiu_em if self._saiu_em else None
        self._saiu_em = None
        if p.get("resumo_diario", True) and 5 <= time.localtime().tm_hour < 23 and not self._resumo_ja_dado_hoje():
            self._resumo_ja_dado_hoje(marcar=True)
            self.anunciador.anunciar(self.comandos.briefing(), validade_s=120, categoria="presenca")
        elif p.get("boas_vindas", True) and fora_s is not None and fora_s >= 600:
            self.anunciador.anunciar(f"Bem-vindo de volta, {self._trat()}.", validade_s=30, categoria="presenca")

    def _rostos_no_quadro(self, n: int) -> None:
        """Mais alguem na frente da camera por 3 s: avisa (no maximo a cada 15 min)."""
        agora = time.time()
        if n < 2:
            self._varias_desde = None
            return
        self._varias_desde = self._varias_desde or agora
        if agora - self._varias_desde >= 3 and agora - self._aviso_pessoas_em > 900:
            self._aviso_pessoas_em = agora
            self.anunciador.anunciar(f"{self._trat()}, há mais alguém na sala.", validade_s=20, categoria="observacao")

    def _aviso_windows(self, item: dict) -> None:
        if self.prefs.ler().get("notificacoes_windows") and vai_para_o_windows(item):
            threading.Thread(target=self.avisos_windows.mostrar, args=(item["texto"], item["nivel"]),
                             name="toast", daemon=True).start()
        # o Jarvis tambem fala o que importa (compromisso, e-mail novo, bateria critica)
        anunciador = getattr(self, "anunciador", None)
        if anunciador and item.get("tipo") in ("agenda", "email") or (anunciador and item.get("nivel") == "erro"
                                                                      and item.get("tipo") == "energia"):
            texto = item["texto"]
            if item.get("tipo") == "email":
                texto = texto.split(":", 1)[0]                 # so "Novo e-mail de Fulano"
            categoria = {"agenda": "agenda", "email": "observacao"}.get(item.get("tipo"), "aviso")
            anunciador.anunciar(f"{self._trat()}, {texto[0].lower()}{texto[1:]}", validade_s=120, categoria=categoria,
                                 prioridade="alta" if item.get("nivel") == "erro" else "normal")

    def prefs_publicas(self) -> dict:
        """Preferencias para as telas. O endereco da agenda (segredo) nunca sai daqui."""
        return {**self.prefs.ler(), "agenda_configurada": self.agenda.configurada(),
                "agenda_ics": bool(ler_segredo("agenda_ics")), "agenda_google": self.google.publico(),
                "vozes_catalogo": self.vozes.catalogo(), "voz_ultimo": self.vozes.ultimo,
                "inicio_com_windows": inicio_com_windows(),
                "casa": self._casa_publica(), "telegram": self.telegram.publico(),
                "atalhos": self.atalhos.ativos}

    def _casa_publica(self) -> dict:
        from hud_runtime.casa import Casa
        d = Casa().ler()
        return {"ha": bool(ler_segredo("ha_url") and ler_segredo("ha_token")), "ha_url": ler_segredo("ha_url"),
                "descoberto_em": d.get("descoberto_em"),
                "aparelhos": [{"nome": a.get("apelido") or a["nome"], "tipo": a["tipo"], "ip": a.get("ip")}
                              for a in d.get("aparelhos", [])][:30]}

    def _publicar_prefs(self) -> dict:
        p = self.prefs_publicas()
        self.estado.publicar("preferencias", p)
        return p

    # ---- acoes (POST) ----------------------------------------------------

    def acao(self, rota: str, corpo: dict) -> dict:
        from hud_runtime.registros import ROTAS, executar as executar_registro
        if rota in ROTAS:
            if not self.conversa._pedido_lock.acquire(blocking=False):
                raise ValueError("há um pedido em execução; aguarde ou interrompa antes de editar registros")
            try:
                return executar_registro(self.comandos, rota, corpo)
            finally:
                self.conversa._pedido_lock.release()
        if rota == "/api/microfone":
            ativo = corpo.get("ativo")
            if not isinstance(ativo, bool):
                raise ValueError("'ativo' deve ser true ou false")
            if ativo and not self.transcricao.pronta:
                raise ValueError("transcricao ainda nao carregou")
            (self.microfone.ativar if ativo else self.microfone.desativar)()
            self.estado.registrar("controle", f"microfone {'ligado' if ativo else 'desligado'}")
            return {"ok": True, "ativo": ativo}
        if rota == "/api/audio/parar":
            parou = self.reprodutor.parar()
            return {"ok": True, "interrompido": parou,
                    "observacao": "so a reproducao foi interrompida; a geracao nao e cancelada"}
        if rota == "/api/audio/volume":
            v = corpo.get("volume")
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ValueError("'volume' deve ser numero entre 0 e 1")
            self.reprodutor.volume(v)
            self.prefs.aplicar({"volume": v})
            return {"ok": True, "volume": self.prefs.ler()["volume"]}
        if rota == "/api/preferencias":
            novas = self.prefs.aplicar(corpo)
            self.reprodutor.volume(novas["volume"])
            self.estado.atualizar("modelos", voz=novas["modelo_voz"])
            if "pastas_monitoradas" in corpo:
                self.amostrador.lento.forcar("pastas")
            return self._publicar_prefs()
        if rota == "/api/tarefas":
            op = corpo.get("acao")
            if op == "adicionar":
                return {"ok": True, "tarefa": self.tarefas.adicionar(str(corpo.get("texto", "")))}
            if op == "alternar":
                self.tarefas.alternar(str(corpo.get("id", "")))
            elif op == "remover":
                self.tarefas.remover(str(corpo.get("id", "")))
            elif op == "limpar_feitas":
                return {"ok": True, "removidas": self.tarefas.limpar_feitas()}
            else:
                raise ValueError("acao deve ser adicionar, alternar, remover ou limpar_feitas")
            return {"ok": True}
        if rota == "/api/notificacoes":
            op = corpo.get("acao")
            if op == "lidas":
                self.notificacoes.marcar_lidas()
            elif op == "limpar":
                self.notificacoes.limpar()
            else:
                raise ValueError("acao deve ser lidas ou limpar")
            return {"ok": True}
        if rota == "/api/midia":
            return {"ok": midia.controlar(str(corpo.get("acao", "")))}
        if rota == "/api/volume-sistema":
            v, mudo = corpo.get("volume"), corpo.get("mudo")
            if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool)):
                raise ValueError("'volume' deve ser numero entre 0 e 1")
            if mudo is not None and not isinstance(mudo, bool):
                raise ValueError("'mudo' deve ser true ou false")
            return midia.definir_volume(v, mudo)
        if rota == "/api/clima/buscar":
            nome = str(corpo.get("nome", "")).strip()
            if len(nome) < 2:
                raise ValueError("digite o nome da cidade")
            return {"ok": True, "cidades": buscar_cidades(nome)}
        if rota == "/api/clima/local":
            self.prefs.aplicar({"local_clima": corpo.get("local")})
            self.amostrador.lento.forcar("clima")
            return self._publicar_prefs()
        if rota == "/api/clima/extras":
            return self._climas_extras(corpo)
        if rota == "/api/voz/credenciais":
            prov = corpo.get("provedor")
            if prov not in PROVEDORES:
                raise ValueError("provedor desconhecido")
            self.vozes.definir_credenciais(prov, {k: v for k, v in corpo.items() if k != "provedor"})
            return self._publicar_prefs()
        if rota == "/api/voz/remover":
            prov = corpo.get("provedor")
            if prov not in PROVEDORES:
                raise ValueError("provedor desconhecido")
            self.vozes.remover_credenciais(prov)
            return self._publicar_prefs()
        if rota == "/api/voz/previa":
            prov = corpo.get("provedor") or None
            if prov is not None and prov not in PROVEDORES:
                raise ValueError("provedor desconhecido")
            voz = str(corpo.get("voz") or "")[:120] or None

            def previa():
                frase = f"Olá, {self._trat()}. Esta é uma prévia da minha voz."
                try:
                    audio, taxa = self.vozes.gerar(frase, prov, voz)
                    self.reprodutor.tocar(audio, taxa)
                finally:
                    self._publicar_prefs()           # mostra provedor usado / erro
            threading.Thread(target=previa, name="previa-voz", daemon=True).start()
            return {"ok": True}
        if rota == "/api/openjarvis/persona":
            # A9: cria SOUL.md/USER.md que faltarem, so quando o usuario clica (nunca sobrescreve)
            r = openjarvis_info.criar_persona(self.prefs.ler())
            self.amostrador.lento.forcar("openjarvis")
            return r
        if rota == "/api/rotinas/inicio":
            # R4: so o usuario liga/desliga (botao no Painel); cria/remove um atalho na pasta Inicializar
            if not isinstance(corpo.get("ligar"), bool):
                raise ValueError("ligar deve ser true ou false")
            definir_inicio_com_windows(corpo["ligar"], HOME / "bin" / "jarvis-tudo.cmd")
            return self._publicar_prefs()
        if rota == "/api/falar":
            self._atalho_falar()
            return {"ok": True}
        if rota == "/api/parar":
            self.conversa.interromper()
            return {"ok": True}
        if rota == "/api/chat/cancelar":
            return self.entrada.cancelar(str(corpo.get("sessao_id") or ""), str(corpo.get("pedido_id") or ""))
        if rota == "/api/chat":
            return self.entrada.atender(corpo)
        if rota == "/api/comando":
            # comando digitado (ou de teste): mesmo caminho da voz, sem o microfone
            texto = str(corpo.get("texto") or "").strip()[:300]
            if not texto:
                raise ValueError("'texto' vazio")
            from hud_runtime.voz import normalizar_parada
            if normalizar_parada(texto):
                self.conversa.interromper()
                return {"ok": True, "resposta": "Interrompido."}
            if corpo.get("pedido_id") and corpo.get("sessao_id"):
                if corpo.get("falar", True):
                    threading.Thread(target=self.entrada.atender, args=(dict(corpo, texto=texto),),
                                     name="pedido-hud", daemon=True).start()
                    return {"ok": True, "observacao": "executando", "pedido_id": corpo["pedido_id"]}
                return self.entrada.atender(dict(corpo, texto=texto))
            if corpo.get("falar", True):
                threading.Thread(target=self.conversa.atender, args=(texto,), name="comando", daemon=True).start()
                return {"ok": True, "observacao": "executando"}
            return {"ok": True, "resposta": self.conversa.atender(texto, falar=False)}
        if rota == "/api/visao":
            def olhar():
                resposta = self.visao.analisar(str(corpo.get("pergunta") or "") or None)
                self.estado.atualizar("conversa", ultima_resposta=resposta, em=time.time())
                self.conversa.falar(resposta)
            threading.Thread(target=olhar, name="visao", daemon=True).start()
            return {"ok": True}
        if rota == "/api/secretario":
            op = corpo.get("acao")
            if op == "lembrar":
                item = self.secretario.lembrar_por_frase(str(corpo.get("frase") or ""))
                if not item:
                    raise ValueError("não achei um horário (ex.: às 15h, em 10 minutos, amanhã às 9)")
                return {"ok": True, "item": item}
            if op == "cancelar":
                i = corpo.get("id")
                return {"ok": True, "cancelados": self.secretario.cancelar(i if isinstance(i, int) else None)}
            if op == "anotar":
                texto = str(corpo.get("texto") or "").strip()
                if not texto:
                    raise ValueError("nota vazia")
                return {"ok": True, "item": self.secretario.anotar(texto)}
            if op == "apagar_nota" and isinstance(corpo.get("id"), int):
                return {"ok": True, "apagada": self.secretario.apagar_nota(corpo["id"])}
            raise ValueError("'acao' deve ser lembrar, cancelar, anotar ou apagar_nota")
        if rota == "/api/agenda/google/cliente":
            self.google.definir_cliente(str(corpo.get("id") or ""), str(corpo.get("chave") or ""))
            return self._publicar_prefs()
        if rota == "/api/agenda/google/conectar":
            url = self.google.url_login()
            os.startfile(url)            # navegador padrao, onde voce ja entra no Google
            return {"ok": True, "observacao": "abri o login do Google no seu navegador"}
        if rota == "/api/agenda/google/desconectar":
            self.google.desconectar(str(corpo.get("email") or ""))
            self.agenda.esquecer_cache()
            self.amostrador.lento.forcar("agenda")
            return self._publicar_prefs()
        if rota == "/api/agenda":
            self.agenda.definir(str(corpo.get("ics") or "") or None)
            self.amostrador.lento.forcar("agenda")
            return self._publicar_prefs()
        if rota == "/api/servidor/religar":
            def religar():
                self.estado.registrar("servidor", "religando o servidor OpenJarvis...")
                aviso = boot.limpar_registro_orfao()
                if aviso:
                    self.estado.registrar("servidor", aviso, "aviso")
                ok = boot._no_ar(f"{boot.SERVIDOR_OPENJARVIS}/health") or boot.subir_servidor()
                self.estado.registrar("servidor", "servidor no ar" if ok else "servidor não subiu (ver serve.log)",
                                      "info" if ok else "erro")
            threading.Thread(target=religar, name="religar-servidor", daemon=True).start()
            return {"ok": True, "observacao": "religando; leva uns 10 s"}
        if rota == "/api/apresentacao/confirmar":
            confirmado = self.apresentacao.confirmar(str(corpo.get("id") or ""),
                                                     str(corpo.get("destino") or ""))
            return {"ok": confirmado, "confirmado": confirmado, "apresentacao": self.apresentacao.atual()}
        if rota == "/api/gestos":
            if corpo.get("acao") == "ativar":
                self.gestos.validar_ativacao(str(corpo.get("cliente") or ""))
                self.camera.ativar()                           # pedido explícito de gesto no HUD
            return self.gestos.comando(corpo)
        if rota == "/api/selecao":
            # a tela (mouse/teclado) marca o alvo; a voz le o MESMO registro
            alvo = corpo.get("alvo", {})
            if alvo is None:
                alvo = {}
            if not isinstance(alvo, dict):
                raise ValueError("alvo deve ser um objeto")
            if not alvo:
                self.selecao.limpar()
                return {"ok": True, "alvo": None}
            try:
                por = str(alvo.get("por") or "mouse")
                if por not in ("mouse", "teclado"):
                    raise ValueError("seleção da tela deve vir de mouse ou teclado")
                extra = alvo.get("extra", {})
                if not isinstance(extra, dict) or any(k not in ("caixa", "fonte", "categoria") for k in extra):
                    raise ValueError("dados extras da seleção inválidos")
                a = self.selecao.selecionar(str(alvo.get("tipo") or "objeto"), str(alvo.get("id") or ""),
                                            str(alvo.get("rotulo") or ""), por=por, **extra)
            except (ValueError, RuntimeError) as e:
                raise ValueError(str(e)) from e
            return {"ok": True, "alvo": {"tipo": a.tipo, "id": a.id, "rotulo": a.rotulo, "por": a.por}}
        if rota == "/api/camera":
            ativa = corpo.get("ativa")
            if not isinstance(ativa, bool):
                raise ValueError("'ativa' deve ser true ou false")
            if not ativa:
                self.gestos.desativar("câmera desligada pelo usuário")
            (self.camera.ativar if ativa else self.camera.desativar)()
            return {"ok": True, "ativa": ativa}
        if rota == "/api/janela":
            nome = corpo.get("nome")
            if nome not in JANELAS_VALIDAS:
                raise ValueError(f"'nome' deve ser um de {JANELAS_VALIDAS}")
            return {"ok": True, "resultado": janelas.abrir(nome, self.porta)}
        if rota == "/api/casa/descobrir":
            from hud_runtime.casa import Casa
            aparelhos = Casa().descobrir()
            self._publicar_prefs()
            return {"ok": True, "total": len(aparelhos)}
        if rota == "/api/casa/ha":
            from hud_runtime.casa import ERROS, HomeAssistant
            url, token = str(corpo.get("url") or "").strip(), str(corpo.get("token") or "").strip()
            if not url and not token:                           # remover
                gravar_segredo("ha_url", None)
                gravar_segredo("ha_token", None)
                self._publicar_prefs()
                return {"ok": True, "removido": True}
            if not url.startswith(("http://", "https://")) or len(token) < 20:
                raise ValueError("preencha o endereço (http://IP:8123) e o token de acesso longo")
            try:
                n = len(HomeAssistant(url, token).estados())
            except (*ERROS, KeyError) as e:
                raise ValueError(f"o Home Assistant não respondeu: {str(e)[:80]}") from None
            gravar_segredo("ha_url", url.rstrip("/"))
            gravar_segredo("ha_token", token)
            self._publicar_prefs()
            return {"ok": True, "entidades": n}
        if rota == "/api/telegram/token":
            bot = self.telegram.definir_token(str(corpo.get("token") or ""))
            self._publicar_prefs()
            return {"ok": True, "bot": bot}
        if rota == "/api/telegram/desparear":
            self.telegram.desparear()
            self._publicar_prefs()
            return {"ok": True}
        if rota == "/api/desligar":
            threading.Timer(0.3, self.encerrar).start()
            return {"ok": True}
        raise KeyError(rota)

    def dados_classicos(self) -> str:
        """dados.js no formato da tela classica, a partir da telemetria atual."""
        t = self.estado.telemetria or {}
        mem = t.get("sistema", {}).get("memoria", {})
        dsk = t.get("sistema", {}).get("disco", {})
        oll = t.get("ollama", {})
        cfg = t.get("config", {})
        inst = oll.get("instalados", [])
        dados = {
            "ram_total": mem.get("total_gb"), "ram_livre": mem.get("livre_gb"),
            "disco_total": dsk.get("total_gb"), "disco_livre": dsk.get("livre_gb"),
            "modelos": [{"nome": m["nome"], "tamanho": f"{m['tamanho_gb']:.1f} GB"} for m in inst],
            "modelos_gb": round(sum(m["tamanho_gb"] for m in inst), 2),
            "voz": cfg.get("voz"), "tts": (cfg.get("tts") or "").capitalize() or None,
            "servicos": [{"nome": "Ollama (127.0.0.1:11434)", "ok": oll.get("status") == "ok"}],
            "gerado": time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(t.get("em", time.time()))),
        }
        return "window.DADOS = " + json.dumps(dados, ensure_ascii=False) + ";"

    def _climas_extras(self, corpo: dict) -> dict:
        p = self.prefs.ler()
        extras, principal = list(p.get("climas_extras") or []), p.get("local_clima")
        op = corpo.get("acao")
        if op == "adicionar":
            novo = corpo.get("local")
            if not isinstance(novo, dict):
                raise ValueError("'local' deve ser uma cidade da busca")
            if len(extras) >= 3:
                raise ValueError("já são 3 cidades extras; remova uma antes")
            extras.append(novo)
        elif op in ("remover", "principal"):
            i = corpo.get("indice")
            if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(extras):
                raise ValueError("'indice' invalido")
            escolhida = extras.pop(i)
            if op == "principal":              # troca de lugar com a principal
                if principal:
                    extras.insert(i, principal)
                self.prefs.aplicar({"local_clima": escolhida})
        else:
            raise ValueError("'acao' deve ser adicionar, remover ou principal")
        self.prefs.aplicar({"climas_extras": extras})
        self.amostrador.lento.forcar("clima")
        return self._publicar_prefs()

    # ---- ciclo de vida ---------------------------------------------------

    def iniciar(self, abrir: list[str]) -> None:
        self._http = servidor_http.criar(self, self.porta)
        servidor_http.rodar(self._http)
        ARQ_INSTANCIA.write_text(json.dumps({"pid": os.getpid(), "porta": self.porta,
                                             "token": self.token, "inicio": time.time()}),
                                 encoding="utf-8")
        for fio in (self.ponte, self.amostrador, self.microfone, self.conversa, self.camera,
                    self.secretario, self.anunciador, self.atalhos, self.monitores, self.visao_continua,
                    self.telegram):
            fio.start()
        for nome in abrir:           # telas antes do boot: a animacao acompanha as etapas
            janelas.abrir(nome, self.porta)
        threading.Thread(target=boot.executar, args=(self,), name="boot", daemon=True).start()
        threading.Thread(target=self._percepcao_periodica, name="percepcao", daemon=True).start()
        print(f"  runtime no ar: http://127.0.0.1:{self.porta}/jarvis")
        print("  feche esta janela (ou use Desligar no HUD) para encerrar.")

    def encerrar(self) -> None:
        if self.encerrando.is_set():
            return
        self.encerrando.set()
        self.visao_continua.parar()
        self.telegram.encerrar()
        self.microfone.encerrar()
        self.camera.encerrar()
        self.gestos.encerrar()
        self.conversa.encerrar()
        self.secretario.encerrar()
        self.anunciador.encerrar()
        self.atalhos.encerrar()
        self.monitores.encerrar()
        self.ponte.encerrar()
        self.amostrador.parar()
        self.reprodutor.parar()
        if self._http:
            threading.Thread(target=self._http.shutdown, daemon=True).start()
        try:
            dados = json.loads(ARQ_INSTANCIA.read_text(encoding="utf-8"))
            if dados.get("pid") == os.getpid():
                ARQ_INSTANCIA.unlink()
        except (OSError, ValueError):
            pass


def instancia_ativa() -> dict | None:
    try:
        dados = json.loads(ARQ_INSTANCIA.read_text(encoding="utf-8"))
        with urllib.request.urlopen(f"http://127.0.0.1:{dados['porta']}/api/saude",
                                    timeout=2) as r:
            if json.load(r).get("servico") == "jarvis-hud":
                return dados
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        pass
    return None


def pedir_janela(inst: dict, nome: str) -> None:
    req = urllib.request.Request(
        f"http://127.0.0.1:{inst['porta']}/api/janela",
        data=json.dumps({"nome": nome}).encode(),
        headers={"Content-Type": "application/json", "X-Jarvis-Token": inst["token"]})
    urllib.request.urlopen(req, timeout=5).read()


def _mic_por_env() -> None:
    import sounddevice as sd
    alvo = os.environ.get("JARVIS_MIC", "").strip()
    if not alvo:
        return
    if alvo.isdigit():
        sd.default.device = (int(alvo), sd.default.device[1])
        return
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and alvo.lower() in d["name"].lower():
            sd.default.device = (i, sd.default.device[1])
            return


def main() -> int:
    args = sys.argv[1:]
    if "-h" in args or "--help" in args or "--ajuda" in args:
        print(__doc__)
        return 0
    porta = int(args[args.index("--porta") + 1]) if "--porta" in args else PORTA_PADRAO
    prefs = Preferencias().ler()
    if "--sem-janelas" in args:
        abrir: list[str] = []
    elif "--janelas" in args:
        abrir = [j for j in args[args.index("--janelas") + 1].split(",") if j in JANELAS_VALIDAS]
    else:
        abrir = [j for j in JANELAS_VALIDAS if prefs["abrir"].get(j)]

    existente = instancia_ativa()
    if existente:
        for nome in abrir or ["jarvis"]:
            pedir_janela(existente, nome)
        print("  runtime ja estava rodando; janelas trazidas para frente.")
        return 0

    _mic_por_env()
    rt = Runtime(porta)
    try:
        rt.iniciar(abrir)
    except OSError:
        # Porta ocupada = outro runtime venceu a corrida (duplo clique, palma +
        # icone). Ele e o dono: so traz as janelas dele para frente.
        for _ in range(12):
            existente = instancia_ativa()
            if existente:
                for nome in abrir or ["jarvis"]:
                    pedir_janela(existente, nome)
                print("  outro runtime ja esta rodando; janelas trazidas para frente.")
                return 0
            time.sleep(0.5)
        print(f"  a porta {porta} esta ocupada por outro programa.")
        return 1
    try:
        while not rt.encerrando.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        rt.encerrar()
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
