"""Visao: "Jarvis, o que e isso?" -> um quadro da camera vai ao modelo de visao
LOCAL (o mesmo modelo da voz, escolhido em Preferencias; hoje gemma4:e4b, no Ollama desta maquina), que diz o que e e, se
der para ver, a marca e o modelo.

O servidor do OpenJarvis nao aceita imagens em /v1/chat/completions; por isso
esta chamada vai direto ao Ollama local. Nada sai da maquina e o quadro nao e
gravado: fica so uma miniatura na memoria, para a tela mostrar o que foi analisado.
"""

from __future__ import annotations

import base64
import json
import re
import time
import uuid
import urllib.error
import urllib.request
from typing import Any

from . import OLLAMA
from .modelos_ia import escolher

INSTRUCAO = (
    "Você é J.A.R.V.I.S. olhando pela câmera do computador. Identifique o objeto principal "
    "que a pessoa está mostrando para a câmera (em geral na mão ou no centro da imagem). "
    "Diga o que é e, se der para ver, a marca e o modelo (ex.: celular Samsung Galaxy S23); "
    "se for um livro, o título e o autor; use o texto legível do rótulo ou da capa. "
    "Se não tiver certeza da marca ou do modelo, diga isso em vez de inventar. Se não houver "
    "objeto em destaque, descreva brevemente a cena. Responda em português do Brasil, em no "
    "máximo duas frases curtas, sem listas, markdown ou aspas."
)


def reduzir(jpeg: bytes, largura: int, qualidade: int = 85) -> bytes:
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("quadro da câmera inválido")
    h, w = img.shape[:2]
    if w > largura:
        img = cv2.resize(img, (largura, round(h * largura / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, qualidade])
    if not ok:
        raise ValueError("falha ao comprimir o quadro")
    return buf.tobytes()


INSTRUCAO_AUTO = (
    "Você é J.A.R.V.I.S. e esta é a região da câmera que o usuário definiu. Se houver um OBJETO sendo "
    "mostrado ou colocado ali, diga o que é, em uma frase curta: se for livro, título e autor; se for "
    "produto, marca e modelo; use o texto legível do rótulo ou da capa. Se não tiver certeza da marca ou "
    "do modelo, diga isso em vez de inventar. Se não houver objeto em destaque (só a pessoa, o quarto, a "
    "mesa vazia ou uma mão vazia), responda apenas NADA. Português do Brasil, sem listas nem markdown."
)

# identificacao fina (§8): o modelo devolve as PISTAS separadas, nao um veredito.
# Quem decide o que e "confirmado" e o que e "provavel" e identificacao.py, aqui no PC.
INSTRUCAO_IDENT = (
    "Você é J.A.R.V.I.S. olhando o objeto que a pessoa mostra para a câmera. Responda EXATAMENTE "
    "nestas quatro linhas, sem markdown e sem comentários:\n"
    "CATEGORIA: o que é, em até três palavras\n"
    "TEXTO: o texto que você consegue LER no objeto, copiado letra por letra; se não der para ler, escreva: nada\n"
    "LOGO: a marca do logotipo, se aparecer inteiro; se não aparecer ou estiver cortado, escreva: nada\n"
    "DESCRICAO: uma frase curta com cor, formato e tamanho aparente\n"
    "Regra: nunca complete uma palavra cortada ou borrada. Escreva só o que dá para ler de verdade. "
    "Se estiver ilegível, escreva: nada."
)
_LINHA = re.compile(r"^\s*(CATEGORIA|TEXTO|LOGO|DESCRICAO|DESCRIÇÃO)\s*:\s*(.*)$", re.I | re.M)
_VAZIO = re.compile(r"^(?:nada|nenhum[ao]?|ilegivel|ilegível|n/?a|-|—)?$", re.I)


def separar_pistas(bruto: str) -> dict[str, str]:
    """Lê as quatro linhas do modelo. O que vier fora do formato é descartado."""
    achados: dict[str, str] = {}
    for nome, valor in _LINHA.findall(bruto or ""):
        chave = "descricao" if nome.lower().startswith("descri") else nome.lower()
        valor = valor.strip().strip('"').strip()
        achados[chave] = "" if _VAZIO.match(valor) else valor
    return achados


INSTRUCAO_TELA = (
    "Você é J.A.R.V.I.S. olhando a janela em que o usuário está trabalhando. Diga em poucas frases o que "
    "aparece (programa, conteúdo principal). Se houver uma mensagem de erro, leia o erro, explique a causa "
    "provável e o que fazer para resolver. Não leia em voz alta senhas, números de cartão ou dados pessoais "
    "que apareçam. Responda em português do Brasil, em até quatro frases, sem listas nem markdown."
)


class Visao:
    def __init__(self, estado: Any, camera: Any, prefs: Any) -> None:
        self._estado = estado
        self._camera = camera
        self._prefs = prefs

    def _quadro(self) -> bytes:
        """Liga a camera se preciso (voce pediu para ele olhar) e pega um quadro."""
        if not self._camera.ativa:
            self._camera.ativar()
        seq, jpeg = getattr(self._camera, "seq", 0), None
        limite = time.monotonic() + 8
        while time.monotonic() < limite:
            anterior = seq
            seq, candidato = self._camera.proximo_jpeg(seq, 1.0)
            if not self._camera.ativa:
                raise RuntimeError("a câmera foi desligada durante o pedido")
            if candidato and seq != anterior:
                jpeg = candidato
                break
        if not jpeg:
            raise RuntimeError("a câmera não entregou imagem")
        time.sleep(0.6)                        # exposicao automatica estabiliza
        novo_seq, novo = self._camera.proximo_jpeg(seq, 1.0)
        if not self._camera.ativa:
            raise RuntimeError("a câmera foi desligada durante o pedido")
        return novo if novo and novo_seq != seq else jpeg

    def perguntar_imagem(self, imagem_jpeg: bytes, texto: str, num_predict: int = 120,
                         formato: dict | None = None) -> str:
        """Uma imagem + instrucao -> resposta do modelo de visao local (Ollama).
        `formato`: esquema JSON (saida estruturada), para a percepcao."""
        pedido = {
            "model": escolher(self._prefs.ler())[0], "stream": False, "think": False,
            "keep_alive": "10m", "options": {"num_predict": num_predict, "temperature": 0.2 if not formato else 0.1},
            "messages": [{"role": "user", "content": texto,
                          "images": [base64.b64encode(imagem_jpeg).decode()]}],
        }
        if formato:
            pedido["format"] = formato
        corpo = json.dumps(pedido).encode()
        req = urllib.request.Request(f"{OLLAMA}/api/chat", data=corpo,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            dados = json.load(r)
        conteudo = (dados.get("message") or {}).get("content", "")
        if formato:
            return conteudo                                 # JSON cru: quem pediu interpreta
        from .voz import limpar_resposta
        return limpar_resposta(conteudo)

    def analisar_tela(self, pergunta: str | None = None) -> str:
        """ "olhe minha tela": so a janela de trabalho, sob pedido, sem gravar."""
        from . import tela
        t0 = time.time()
        achada = tela.janela_de_trabalho()
        if not achada:
            return "Não encontrei uma janela aberta para olhar, Senhor."
        hwnd, titulo = achada
        if tela.sensivel(titulo):
            return "Por segurança, não analiso janelas de senha ou de banco, Senhor."
        self._estado.atualizar("visao", estado="olhando", pergunta=f"tela: {titulo[:80]}", resposta=None,
                               miniatura=None, captura_id=None, fonte="janela", escopo=titulo[:120],
                               capturado_em=None, em=time.time(), duracao_s=None)
        try:
            img = tela.capturar(hwnd)
            self._estado.atualizar("visao", estado="analisando", capturado_em=time.time(),
                                   miniatura="data:image/jpeg;base64," + base64.b64encode(tela.jpeg(img, 320, 70)).decode())
            texto = INSTRUCAO_TELA + f"\nTítulo da janela: {titulo[:120]}" + (f"\nPedido: {pergunta}" if pergunta else "")
            resposta = self.perguntar_imagem(tela.jpeg(img, 1280), texto, 220) \
                or "Não consegui entender o que está na janela, Senhor."
        except (urllib.error.URLError, OSError, ValueError, RuntimeError) as e:
            self._estado.atualizar("visao", estado="erro", resposta=str(e)[:160], em=time.time())
            self._estado.registrar("visao", f"falha ao olhar a tela: {e}", "erro")
            return f"Não consegui olhar a janela: {e}."
        dur = round(time.time() - t0, 1)
        self._estado.atualizar("visao", estado="pronto", resposta=resposta, em=time.time(), duracao_s=dur)
        self._estado.registrar("visao", f"tela ({titulo[:40]}) em {dur}s: {resposta[:100]}")
        return resposta

    def analisar_recorte(self, img_bgr: Any, regiao: str = "") -> str | None:
        """Olhar automatico: o recorte da regiao definida -> o que e (ou None se nao ha objeto)."""
        import cv2
        t0 = time.time()
        h, w = img_bgr.shape[:2]
        if w > 384:
            img_bgr = cv2.resize(img_bgr, (384, max(1, round(h * 384 / w))), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return None
        jpg = buf.tobytes()
        self._estado.atualizar("visao", estado="analisando", pergunta=f"olhar automático · {regiao}", resposta=None,
                               miniatura="data:image/jpeg;base64," + base64.b64encode(jpg).decode(),
                               captura_id=None, fonte="camera", escopo=regiao or "recorte automático",
                               capturado_em=t0, em=time.time(), duracao_s=None)
        try:
            resposta = self.perguntar_imagem(jpg, INSTRUCAO_AUTO, 90)
        except (urllib.error.URLError, OSError, ValueError) as e:
            self._estado.atualizar("visao", estado="erro", resposta=str(e)[:160], em=time.time())
            return None
        dur = round(time.time() - t0, 1)
        if not resposta or resposta.strip(" .").upper().startswith("NADA"):
            self._estado.atualizar("visao", estado=None, resposta=None, em=time.time(), duracao_s=dur)
            self._estado.registrar("visao", f"olhar automático: nada em destaque ({dur}s)")
            return None
        self._estado.atualizar("visao", estado="pronto", resposta=resposta, em=time.time(), duracao_s=dur)
        self._estado.registrar("visao", f"olhar automático em {dur}s: {resposta[:100]}")
        return resposta

    def identificar(self, pergunta: str | None = None, caixa: tuple[float, float, float, float] | None = None,
                    categoria: str | None = None, inventario: Any = None) -> tuple[str, dict[str, Any]]:
        """A sequência do §8: avaliar a imagem, classificar, extrair pistas,
        consultar o inventário, comparar e responder separando o que é evidência
        do que é palpite. Devolve (frase falada, cartão para o HUD)."""
        import cv2
        import numpy as np

        from .identificacao import (
            PROVAVEL,
            Identificacao,
            avaliar_regiao,
            pistas_de_texto,
        )
        t0 = time.time()
        self._estado.atualizar("visao", estado="olhando", pergunta=pergunta, resposta=None,
                               miniatura=None, captura_id=None, fonte="camera", escopo="região selecionada",
                               capturado_em=None, em=time.time(), duracao_s=None)
        quadro = self._quadro()
        capturado_em = time.time()
        img = cv2.imdecode(np.frombuffer(quadro, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("quadro da câmera inválido")

        # 2. AVALIAR: a regiao da para identificar? Isso e medido aqui, sem modelo.
        qualidade = avaliar_regiao(img, caixa)
        ident = Identificacao(categoria, qualidade)
        ident.evidencia(f"quadro da câmera de {time.strftime('%H:%M:%S', time.localtime(capturado_em))}")
        mini = "data:image/jpeg;base64," + base64.b64encode(reduzir(quadro, 320, 70)).decode()
        captura_id = uuid.uuid4().hex
        self._estado.atualizar("visao", estado="analisando", miniatura=mini, captura_id=captura_id,
                               capturado_em=capturado_em)

        if qualidade.boa:
            # 3 e 4. CLASSIFICAR e EXTRAIR PISTAS com o modelo de visao local
            texto = INSTRUCAO_IDENT + (f"\nPergunta da pessoa: {pergunta}" if pergunta else "")
            alvo_jpeg = quadro
            if caixa is not None:
                x, y, w, h = caixa
                altura, largura = img.shape[:2]
                recorte = img[max(0, int(y * altura)):min(altura, int((y + h) * altura)),
                              max(0, int(x * largura)):min(largura, int((x + w) * largura))]
                ok, buf = cv2.imencode(".jpg", recorte)
                if not ok:
                    raise ValueError("não consegui preparar a região selecionada")
                alvo_jpeg = buf.tobytes()
            bruto = self.perguntar_imagem(reduzir(alvo_jpeg, 1024), texto, 150)
            pistas = separar_pistas(bruto)
            if not ident.categoria and pistas.get("categoria"):
                ident.categoria = pistas["categoria"]
            if pistas.get("descricao"):
                ident.evidencia(f"o que aparece: {pistas['descricao']}")
            lido = pistas_de_texto(pistas.get("texto", ""))
            if lido["legivel"]:
                ident.evidencia(f"texto lido no objeto: {lido['legivel']}")
            if lido["parcial"]:
                ident.evidencia(f"texto cortado, não completei: {lido['parcial']}")
            # logotipo inteiro e PISTA de marca, nao confirmacao
            if pistas.get("logo"):
                ident.anotar("marca", pistas["logo"], PROVAVEL, "logotipo visível")
            # 5. CONSULTAR o inventario do Senhor com o que foi LIDO
            if inventario is not None and lido["legivel"]:
                ident.comparar_inventario(lido["legivel"], inventario)

        frase = ident.frase(self._prefs.ler().get("nome_usuario") or "Senhor")
        cartao = ident.cartao()
        cartao.update(fonte="camera", capturado_em=capturado_em,
                      regiao=list(caixa) if caixa is not None else [0, 0, 1, 1],
                      pergunta=pergunta, captura_id=captura_id,
                      evidencia_disponivel="miniatura em memória enquanto visao.captura_id coincidir; sem gravação",
                      metodo="qualidade de imagem + leitura por modelo visual local + comparação textual")
        dur = round(time.time() - t0, 1)
        try:
            self._estado.atualizar("identificacao", **cartao)
        except (KeyError, AttributeError):
            pass
        self._estado.atualizar("visao", estado="pronto", resposta=frase, em=time.time(), duracao_s=dur)
        self._estado.registrar("visao", f"identificação em {dur}s: {frase[:110]}")
        return frase, cartao

    def analisar(self, pergunta: str | None = None) -> str:
        t0 = time.time()
        self._estado.atualizar("visao", estado="olhando", pergunta=pergunta, resposta=None,
                               miniatura=None, captura_id=None, fonte="camera", escopo="quadro inteiro",
                               capturado_em=None, em=time.time(), duracao_s=None)
        try:
            quadro = self._quadro()
            mini = "data:image/jpeg;base64," + base64.b64encode(reduzir(quadro, 320, 70)).decode()
            self._estado.atualizar("visao", estado="analisando", miniatura=mini, capturado_em=time.time())
            texto = INSTRUCAO + (f"\nPergunta da pessoa: {pergunta}" if pergunta else "")
            corpo = json.dumps({
                "model": escolher(self._prefs.ler())[0], "stream": False, "think": False,
                "keep_alive": "10m", "options": {"num_predict": 120, "temperature": 0.2},
                "messages": [{"role": "user", "content": texto,
                              "images": [base64.b64encode(reduzir(quadro, 560)).decode()]}],
            }).encode()
            req = urllib.request.Request(f"{OLLAMA}/api/chat", data=corpo,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                dados = json.load(r)
            from .voz import limpar_resposta
            resposta = limpar_resposta((dados.get("message") or {}).get("content", "")) \
                or "Não consegui identificar o que é, Senhor."
        except (urllib.error.URLError, OSError, ValueError, RuntimeError) as e:
            self._estado.atualizar("visao", estado="erro", resposta=str(e)[:160], em=time.time())
            self._estado.registrar("visao", f"falha na análise: {e}", "erro")
            return "Não consegui analisar a imagem agora, Senhor."
        dur = round(time.time() - t0, 1)
        self._estado.atualizar("visao", estado="pronto", resposta=resposta, em=time.time(), duracao_s=dur)
        self._estado.registrar("visao", f"análise em {dur}s: {resposta[:100]}")
        return resposta
