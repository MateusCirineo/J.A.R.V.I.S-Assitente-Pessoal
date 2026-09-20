"""Comandos por voz: o que voce fala, o Jarvis faz.

Duas camadas:
1. Frases conhecidas (regras abaixo) sao executadas na hora, sem o modelo:
   camera, capacete, janelas, tela cheia, musica, volume, sites, pesquisa
   com fontes, cotacoes, lembretes, timers, notas, noticias (por assunto),
   "abra a segunda noticia", resumo do dia, status, e-mails, conversa
   casual e "o que e isso?" (visao).
2. O resto vai ao modelo com FERRAMENTAS (function calling pelo servidor do
   OpenJarvis). Se o modelo escolher uma ferramenta, ela e executada aqui.

Seguranca: so acoes do proprio HUD, sites de uma lista fixa e programas que
estao no menu Iniciar (os mesmos que voce abriria clicando). Nada de rodar
comandos arbitrarios nem de fechar programas.
"""

from __future__ import annotations

import random
import re
import threading
import time
import unicodedata
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Callable

from .cotacoes import _ALTERNATIVAS as _ATIVOS

SITES = {
    "youtube": "https://www.youtube.com/", "g1": "https://g1.globo.com/",
    "gmail": "https://mail.google.com/", "email": "https://mail.google.com/",
    "google agenda": "https://calendar.google.com/", "agenda do google": "https://calendar.google.com/",
    "spotify": "https://open.spotify.com/", "netflix": "https://www.netflix.com/",
    "whatsapp": "https://web.whatsapp.com/", "google": "https://www.google.com/",
    "instagram": "https://www.instagram.com/", "linkedin": "https://www.linkedin.com/",
    "github": "https://github.com/", "chatgpt": "https://chatgpt.com/",
    "mapa": "https://www.google.com/maps", "mapas": "https://www.google.com/maps",
    "google maps": "https://www.google.com/maps", "bbc": "https://www.bbc.com/portuguese",
}


_APPS_CACHE: tuple[float, dict[str, str]] | None = None


def apps_instalados() -> dict[str, str]:
    """Nome normalizado -> AppID, do menu Iniciar (Get-StartApps; inclui apps da Loja)."""
    global _APPS_CACHE
    import json
    import subprocess
    import time as _t
    if _APPS_CACHE and _t.time() - _APPS_CACHE[0] < 600:
        return _APPS_CACHE[1]
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
           "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"]
    try:
        saida = subprocess.run(cmd, capture_output=True, timeout=20, creationflags=0x08000000).stdout
        itens = json.loads(saida.decode("utf-8", "replace") or "[]")
    except (OSError, ValueError, subprocess.SubprocessError):
        itens = []
    if isinstance(itens, dict):
        itens = [itens]
    mapa = {normalizar(i["Name"]): i["AppID"] for i in itens if i.get("Name") and i.get("AppID")}
    _APPS_CACHE = (_t.time(), mapa)
    return mapa


# nomes falados -> nome no menu Iniciar (ou programa do proprio Windows)
_APELIDOS = {"calculadora": "calculadora", "bloco de notas": "bloco de notas", "vs code": "visual studio code",
             "vscode": "visual studio code", "code": "visual studio code", "explorador": "explorador de arquivos",
             "arquivos": "explorador de arquivos", "configuracoes": "configuracoes", "word": "word",
             "excel": "excel", "powerpoint": "powerpoint", "navegador": "microsoft edge", "edge": "microsoft edge",
             "chrome": "google chrome", "terminal": "terminal", "paint": "paint", "camera do windows": "camera"}
_WINDOWS = {"calculadora": "calc.exe", "bloco de notas": "notepad.exe", "explorador de arquivos": "explorer.exe",
            "configuracoes": "ms-settings:", "paint": "mspaint.exe"}


def achar_app(nome: str, apps: dict[str, str] | None = None) -> tuple[str, str] | None:
    """(nome no menu, AppID) do programa mais parecido com o que foi dito."""
    alvo = normalizar(nome).strip(" .!?")
    alvo = _APELIDOS.get(alvo, alvo)
    if len(alvo) < 2:
        return None
    apps = apps if apps is not None else apps_instalados()
    if alvo in apps:
        return alvo, apps[alvo]
    comeca = sorted((n for n in apps if n.startswith(alvo)), key=len)
    if comeca:
        return comeca[0], apps[comeca[0]]
    contem = sorted((n for n in apps if re.search(rf"\b{re.escape(alvo)}\b", n)), key=len)
    if contem:
        return contem[0], apps[contem[0]]
    return None


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip()


def normalizar_mesmo_tamanho(texto: str) -> str:
    """Como normalizar(), mas letra a letra (sem juntar espacos): as posicoes
    batem com o texto original, para recortar trechos com acento."""
    saida = []
    for c in texto.lower():
        base = "".join(x for x in unicodedata.normalize("NFKD", c) if not unicodedata.combining(x))
        saida.append(base[:1] if base else c)
    return "".join(saida)


def grupo_original(original: str, regra: re.Pattern, grupo: str) -> str | None:
    """Trecho do grupo nomeado da regra, mas com a grafia original (acentos)."""
    t = sem_chamado(original).strip()
    m = regra.search(normalizar_mesmo_tamanho(t))
    if not m or m.group(grupo) is None:
        return None
    return t[m.start(grupo):m.end(grupo)].strip(" .!?")


def nome_arquivo(caminho: str) -> str:
    from pathlib import Path
    return Path(caminho).name


def Path_(caminho: str):
    from pathlib import Path
    return Path(caminho)


def sem_chamado(texto: str) -> str:
    """Tira o "Jarvis," do comeco (e variantes da transcricao)."""
    return re.sub(r"^\W*(?:jarvis|jarbas|jarvas|jervis|djarvis)\b\W*", "", texto.strip(), flags=re.I)


R = re.compile
# O Senhor nao pede duas vezes do mesmo jeito. Em 19/09, 15 de 33 formas de pedir o
# cadastro de rosto/voz nao casavam com regra nenhuma ("memorize SEU rosto", "grave
# minha voz AGORA", "aprenda A RECONHECER o meu rosto") e caiam no modelo de linguagem,
# que respondia "sou so um assistente de voz e nao posso memorizar rostos".
_CADASTRAR = (r"(?:memoriz\w*|memor(?!ia)\w*|decor(?:e|a|ar|em)|aprend\w*|cadastr\w*|grav\w*"
              r"|registr\w*|salv\w*|guard\w*|arquiv\w*)")
_ROSTO = r"(?:rosto|rostinho|cara|face|fisionomia)"
# "o meu", "a sua", "esse", "os dados do"...: ate tres palavrinhas antes do substantivo
_DET = (r"(?:(?:o|a|os|as|um|uma|meu|minha|meus|minhas|seu|sua|seus|suas|esse|essa|este|esta"
        r"|aquele|aquela|todos|todas|dados|cadastro|registro|de|do|da)\s+){0,3}")
_MEIO = r"(?:\s+(?:a|o|para|pra|de|como|bem)?\s*\w+){0,2}?"     # "aprenda A RECONHECER o rosto"
_VOZ = r"(?:voz|vozinha)"
_ROSTO_E_VOZ = rf"(?:{_ROSTO}\b[^.!?]{{0,60}}\be\s+{_DET}{_VOZ}|{_VOZ}\b[^.!?]{{0,60}}\be\s+{_DET}{_ROSTO})"
AUTOMACAO = {"raciocinio", "agendar", "protocolo_criar", "protocolo_listar", "protocolo_apagar", "protocolo_executar",
             "projetar", "engenharia", "tarifa", "dados_analisar", "pesquisa_detalhada"}      # o pedido manda, nao a conta solta
# (nome, regra no texto normalizado). A ordem importa: a primeira que casar vale.
REGRAS: list[tuple[str, re.Pattern]] = [
    # parar: caminho rapido, fora do modelo ("Jarvis, pare" / "silencio")
    # quem e quem (so pessoas cadastradas por comando)
    # capacidades por canal (F37): o Jarvis nao promete o que o canal nao faz
    ("canais_pode", R(r"\b(?:o |a )?(?P<canal>telegram|celular|chat|tela|painel|mesa|voz)\b\s*"
                      r"(?:faz|toca|reproduz|aceita|mostra|abre|executa|envia|manda|recebe|consegue|pode)\b"
                      r"\s*(?P<cap>[\w\s]{2,30}?)\W*$"
                      r"|\b(?:d[aá]|consigo|posso|da para)\b.{0,12}\b(?:ouvir|escutar|falar|mostrar|abrir|enviar)\b"
                      r".{0,20}\b(?:pelo|no|na|por)\s+(?P<canal2>telegram|celular|chat|tela|painel|mesa)\b")),
    ("canais_listar", R(r"\bquais (?:sao (?:os )?)?(?:meus )?canais\b|\bo que cada canal faz\b"
                        r"|\bcanais (?:disponiveis|conectados|declarados)\b|\bpor onde (?:eu )?falo com voce\b")),
    # correcoes do Senhor (§17): apelidos revisados, nada de treinamento
    # o verbo faz parte da ACAO ("abra o VS Code"), menos quando e so "faca/execute"
    ("corrigir_apelido", R(r"\bquando eu (?:disser|falar|pedir)\s+(?P<gatilho>[^,]{3,50}?)\s*,\s*"
                           r"(?:voce\s+)?(?:faca|faz|execute)?\s*(?P<acao>.{3,70}?)\W*$"
                           r"|\bquando eu (?:disser|falar|pedir)\s+(?P<gatilho3>.{3,50}?)\s+"
                           r"(?:faca|faz|execute)\s+(?P<acao3>.{3,70}?)\W*$"
                           r"|^\W*(?:jarvis\W*)?(?P<gatilho2>.{3,40}?)\s+(?:quer dizer|significa|e a mesma coisa que)\s+(?P<acao2>.{3,70}?)\W*$")),
    ("corrigir_listar", R(r"\bquais (?:sao (?:as )?)?(?:minhas |as )?correc\w*\b|\bo que voce (?:ja )?corrigiu\b"
                          r"|\bquais apelidos\b|\bo que voce aprendeu comigo\b")),
    ("corrigir_esquecer", R(r"\b(?:esquec\w*|apag\w*|remov\w*|cancel\w*)\b\s+(?:a |essa |aquela )?correc\w*"
                            r"(?:\s+(?:de |do |da )?(?P<q>.{2,40}?))?\W*$"
                            r"|\besquec\w* (?:o |esse )?apelido\s*(?P<q2>.{2,40}?)\W*$")),
    # cena consultavel (F16): "descreva a cena", "o que voce NAO viu?"
    ("cena_nao_visto", R(r"\bo que (?:voce )?nao (?:viu|observou|olhou|esta vendo)\b"
                         r"|\bo que (?:voce )?(?:nao )?deixou de (?:ver|olhar)\b"
                         r"|\bquais (?:partes|regioes) (?:voce )?nao (?:viu|observou)\b")),
    ("cena_descrever", R(r"\b(?:descrev\w*|mont\w*|resum\w*)\b.{0,12}\b(?:a )?cena\b"
                         r"|\bcomo (?:esta|ta) (?:a )?(?:cena|a mesa|o ambiente)\b"
                         r"|\bo que (?:tem|ha) (?:a|na|no)\s+(?P<regiao>esquerda|direita|centro|meio)\b"
                         r"|\bo que (?:esta|ta) (?:a|na|no)\s+(?P<regiao2>esquerda|direita|centro|meio)\b")),
    # cruzar o que aconteceu (F17): "o que apareceu na mesa hoje a tarde?"
    ("ocorrencias", R(r"\bo que (?:aconteceu|rolou|houve|apareceu|sumiu|mudou|voce (?:viu|registrou|anotou))\b"
                      r"(?=.*\b(?:hoje|ontem|agora|manha|tarde|noite|semana|ultim\w+|enquanto|fora|minutos?|horas?|dias?)\b)"
                      r"|\bquando (?:voce )?(?:viu|vi|apareceu|sumiu)\b.{0,40}"
                      r"|\bo que (?:voce )?(?:viu|registrou) (?:hoje|ontem|de manha|a tarde|a noite)\b"
                      r"|\bme conte o que (?:aconteceu|houve|rolou)\b")),
    # manuais e documentos do Senhor (§7/F25): ler, perguntar e citar a fonte
    # "me lembre de ler o documento as 15h" e LEMBRETE, nao pedido de leitura
    ("doc_indexar", R(r"^(?!.*\blembr\w*\b)"
                      # "leia o arquivo notas" continua sendo LER em voz alta (comando `documento`);
                      # manual e ficha tecnica vao para o indice, que e o que serve para consultar
                      r".*(?:\b(?:index\w*|estud\w*|guard\w*|aprend\w*)\b\s+(?:o |a |os |as |esse |este )?"
                      r"(?:manual|documento|pdf|arquivo|texto|apostila|datasheet|ficha tecnica)\b"
                      r"|\b(?:leiam|leia|lendo|ler|le)\b\s+(?:o |a |esse |este )?"
                      r"(?:manual|apostila|datasheet|ficha tecnica)\b)"
                      r"(?:\s+(?:d[aoe]\s+|sobre\s+|chamad[ao]\s+)?(?P<q>[\w\s.-]{2,60}?))?\W*$")),
    ("doc_perguntar", R(r"\bo que (?:o |a )?(?P<onde>manual|documento|pdf|apostila|datasheet|ficha)\b"
                        r"(?:\s+d[aoe]\s+(?P<alvo>[\w\s-]{2,40}?))?\s+(?:diz|fala|manda|recomenda|explica)"
                        r"(?:\s+(?:sobre|de|do|da|a respeito de))?\s*(?P<q>.{2,80}?)\W*$"
                        r"|\bsegundo o manual\b.{0,3}(?P<q2>.{2,80}?)\W*$"
                        r"|\bconsult\w* o manual\b.{0,12}(?P<q3>.{2,80}?)\W*$")),
    ("pesquisa_detalhada", R(r"^\W*(?:jarvis\W*)?(?:por favor\W*)?(?:investig\w*|pesquis\w* (?:em detalhes|a fundo|detalhadamente))"
                            r"\s+(?:sobre\s+)?(?P<q>.{2,350}?)\W*$")),
    ("doc_fonte", R(r"\bqual (?:e |eh )?(?:a )?fonte\b|\bde onde (?:voce )?(?:tirou|tirou isso|leu isso)\b"
                    r"|\bonde (?:esta|ta) escrito\b|\bcom base em que\b")),
    ("doc_listar", R(r"\bquais (?:sao )?(?:os )?(?:meus )?(?:documentos|manuais)\b|\bo que voce (?:ja )?(?:leu|indexou)\b"
                     r"|\bquais (?:documentos|manuais) voce (?:tem|conhece|leu)\b")),
    ("doc_esquecer", R(r"\b(?:esquec\w*|apag\w*|remov\w*)\b\s+(?:o |a )?(?:manual|documento|pdf)\b"
                       r"(?:\s+d[aoe]\s+(?P<q>[\w\s.-]{2,40}?))?\W*$")),
    # inventario do Senhor: "cadastre esta impressora", "o que voce sabe do meu carregador"
    # "o modelo da impressora e L3250", "o manual dela e C:\...pdf": o Senhor confirmando
    ("inv_definir", R(r"^\W*(?:jarvis\W*)?(?:o |a )?(?P<campo>marca|modelo|fabricante|manual|numero de serie|serie|capacidade|potencia)"
                      r"\s+(?:d[oa]\s+(?:meu\s+|minha\s+)?(?P<obj>[\w\s-]{2,40}?)\s+)?(?:e|eh|:)\s+(?P<valor>.{2,80}?)\W*$")),
    ("inv_saber", R(r"^(?!.*\b(?:rosto|voz|projeto|peca)\b)"
                    r".*\bo que (?:voce )?sabe (?:sobre|do|da|de)\s+(?:o |a )?(?:meu|minha|este|esta|esse|essa)\s+(?P<obj>[\w\s-]{2,40}?)\W*$"
                    r"|\bme (?:fal\w*|cont\w*) (?:sobre|do|da)\s+(?:o |a )?(?:meu|minha)\s+(?P<obj2>[\w\s-]{2,40}?)\W*$"
                    r"|\bficha (?:do|da|de)\s+(?P<obj3>[\w\s-]{2,40}?)\W*$")),
    ("inv_listar", R(r"\bqu(?:ais|e)\s+(?:sao\s+)?(?:os\s+)?(?:meus\s+)?objetos\b|\bo que voce tem cadastrado\b"
                     r"|\bmeu inventario\b|\bquais coisas minhas voce conhece\b")),
    ("inv_manual", R(r"\b(?:abr\w*|mostr\w*|ach\w*|procur\w*)\b.{0,12}\bmanual\b"
                     r"(?:\s+(?:do|da|de)\s+(?:o |a )?(?:meu |minha )?(?P<obj>[\w\s-]{2,40}?))?\W*$")),
    # rosto e voz sao de PESSOA (id_*), nao de objeto: ficam de fora daqui
    ("inv_esquecer", R(r"^(?!.*\b(?:rosto|rostinho|cara|face|fisionomia|voz|vozes|projeto|peca)\b)"
                       r".*\b(?:esquec\w*|apag\w*|remov\w*|descadastr\w*)\b\s+(?:o |a )?(?:meu|minha|este|esta|esse|essa)\s+"
                       r"(?P<obj>[\w\s-]{2,40}?)\W*$")),
    ("inv_cadastrar", R(r"^(?!.*\b(?:rosto|rostinho|cara|face|fisionomia|voz|vozes|protocolo|lembrete|tarefa)\b)"
                        r".*\b(?:cadastr\w*|registr\w*)\b\s+(?:est[ea]\s+|esse\s+|essa\s+|o\s+|a\s+|meu\s+|minha\s+)?"
                        r"(?P<obj>[a-z][\w\s-]{2,40}?)\W*$"
                        r"|^\W*(?:jarvis\W*)?est[ea]\s+(?:e|eh)\s+(?:o|a)\s+(?:meu|minha)\s+(?P<obj2>[a-z][\w\s-]{2,40}?)\W*$")),
    # peca em edicao: "aumente a largura em 2 mm". Sem dimensao ("aumente isso"),
    # o Jarvis PERGUNTA em vez de mexer em algo arbitrario (§4 e T03).
    ("peca_confirmar", R(r"^\W*(?:jarvis\W*)?confirm\w*\s+(?:a\s+)?(?:alteracao|previa)(?:\s+d[ao]\s+peca)?\W*$")),
    ("peca_estilo", R(r"\b(?:mud\w*|alter\w*|troc\w*|ajust\w*)\b.{0,25}\b(?:material|cor)\b.{0,50}")),
    ("peca_comparar", R(r"\bcompar\w*\b.{0,25}\bvers(?:oes|ao)\b")),
    ("peca_alterar", R(r"\b(?:aument\w*|diminu\w*|reduz\w*|encolh\w*|engross\w*|afin\w*|mud\w*|alter\w*|deix\w*|ajust\w*|coloq\w*|pon\w*)\b"
                       r"(?=.*\b(?:mm|milimetros?|cent[ií]metros?|cm|isso|isto|essa peca|a peca|largura|altura|comprimento"
                       r"|parede|espessura|diametro|furo|dentes|profundidade|base|externo|interno|grosso|grossa|fino|fina|maior|menor)\b)"
                       r"(?!.*\b(?:volume|som|audio|microfone|brilho|zoom|temperatura|velocidade)\b)")),
    ("peca_versoes", R(r"\b(?:quais|quantas|list\w*|mostr\w*)\b.{0,15}\bvers(?:oes|ao)\b|\bhistorico da peca\b"
                       # "o que mudou?" sozinho continua sendo da percepcao (o que mudou na sala)
                       r"|\bo que mudou\b.{0,12}\b(?:na peca|no projeto|nela|nessa peca)\b")),
    # montagem e vista explodida (F20): so do que o Jarvis montou
    ("montagem_criar", R(r"\b(?:mont\w*|faz\w*|projet\w*|cri\w*)\b.{0,20}\bcaixa com tampa\b"
                         r"|\bcaixa com tampa\b.{0,20}\b(?:de|com)\b")),
    ("montagem_pecas", R(r"\b(?:quais|quantas|list\w*|mostr\w*)\b.{0,18}\b(?:pecas|componentes)\b"
                         r"|\bdo que (?:isso|ela|ele) e feit[oa]\b|\bcomponentes d[ae]\b")),
    ("montagem_explodir", R(r"\bvista explodida\b|\bexplod\w*\b.{0,15}\b(?:vista|peca|montagem|isso)?\b"
                            r"|\bsepar\w*\b.{0,12}\b(?:as )?pecas\b|\bdesmont\w*\b")),
    ("peca_apagar", R(r"\b(?:apag\w*|esquec\w*|remov\w*|descart\w*|delet\w*)\b\s+(?:a\s+|essa\s+|esta\s+|minha\s+)?"
                      r"(?:peca|caixa|engrenagem|cilindro|tubo|esfera|cone)\b")),
    ("peca_voltar", R(r"\bvolt\w*\b.{0,20}\bvers[aã]o\s*(?P<n>\d+)?\b|\bdesfaz\w*\b|\bdesfa[cç]\w*\b"
                      r"|\bvolt\w* (?:para )?(?:a )?(?:versao )?anterior\b")),
    # projetos e tarefas: "continue de ontem" precisa saber DE QUE. Vem antes das
    # regras gerais porque "continue" e "o que falta" sao frases muito comuns.
    ("projeto_experimento", R(r"^\W*(?:jarvis\W*)?registr\w*\s+(?:o\s+)?(?:experimento|teste)\s+(?P<nome>[^:]{1,80}):\s*(?P<resultado>.+)$")),
    ("projeto_conferir_etapa", R(r"^\W*(?:jarvis\W*)?confirm\w*\s+(?:a\s+)?etapa\s+(?P<n>\d+)\W*$")),
    ("projeto_etapa_nao_executada", R(r"^\W*(?:jarvis\W*)?(?:confirme que\s+)?(?:a\s+)?etapa\s+(?P<n>\d+)\s+nao\s+(?:foi\s+)?executada\W*$")),
    ("projeto_novo", R(r"^\W*(?:jarvis\W*)?(?:vamos\s+)?(?:comec\w*|inici\w*|abr\w*|cri\w*|comeca\w*)\s+"
                       r"(?:um |uma |o |a )?(?:novo |nova )?projeto\s*(?:de |da |do |chamado |:)?\s*(?P<nome>.{2,60}?)\W*$"
                       r"|^\W*(?:jarvis\W*)?novo projeto\s*:?\s*(?P<nome2>.{2,60}?)\W*$")),
    ("projeto_estado", R(r"\bo que (?:ainda )?(?:falta|falta fazer)\b|\bo que (?:ja )?(?:foi feito|fizemos|eu fiz)\b"
                         r"|\bem que pe\b|\bcomo (?:esta|estamos|vai|anda) (?:o projeto|a tarefa|isso)\b"
                         r"|\b(?:qual|como esta) o (?:status|estado|andamento) (?:d[oa] )?(?:projeto|tarefa)\b")),
    ("projeto_listar", R(r"\bquais (?:sao )?(?:os |as )?(?:meus |minhas )?(?:projetos|tarefas em andamento)\b"
                         r"|\bo que (?:esta|ta) em andamento\b|\bmeus projetos\b|\blist\w* (?:os |meus )?projetos\b")),
    ("projeto_continuar", R(r"^\W*(?:jarvis\W*)?(?:continu\w*|retom\w*|volt\w* (?:para|pro|pra))\s+"
                            r"(?P<alvo>(?:de )?ontem|de onde (?:paramos|parou)|(?:o |a |com o |com a |no |na )?"
                            r"(?:projeto|tarefa|peca)\b.{0,40}|aquil[oa]|(?:o|a) .{2,40}?)\W*$"
                            r"|^\W*(?:jarvis\W*)?(?:continu\w*|retom\w*)\W*$")),
    ("projeto_pausar", R(r"\b(?:paus\w*|suspend\w*)\b.{0,25}\b(?:projeto|tarefa|isso)\b"
                         r"|\b(?:par\w*|chega) por (?:hoje|agora)\b"
                         r"|\bdeix\w* (?:isso |o projeto |a tarefa )?para (?:depois|amanha)\b")),
    ("projeto_concluir", R(r"\b(?:terminei|conclui|finalizei)\b(?!\s+de\b)"
                           r"|\bacabei\b(?!\s+de\b)"
                           r"|\bmarq\w*\b.{0,25}\b(?:como )?(?:pronto|concluido|concluida|feito|terminado)\b"
                           r"|\b(?:o projeto|a tarefa|a peca) (?:esta|ta) (?:pronto|pronta|concluid[oa])\b")),
    ("projeto_apagar", R(r"\b(?:apag\w*|esquec\w*|remov\w*|descart\w*|cancel\w*)\b\s+(?:o\s+|esse\s+|este\s+|meu\s+)?"
                         r"projeto\b(?:\s+(?P<nome>.{2,40}?))?\W*$")),
    ("projeto_depende", R(r"\b(?P<etapa>[\w\s]{3,40}?)\s+(?:so )?(?:depende de|precisa de|vem depois de|so depois de)\s+"
                          r"(?P<antes>[\w\s]{3,40}?)\W*$")),
    ("projeto_etapa", R(r"^\W*(?:jarvis\W*)?(?:anot\w* que )?(?:ainda )?falta\s+(?P<etapa>.{3,60}?)\W*$"
                        r"|\b(?:proximo passo|proxima etapa|acrescent\w* a etapa|anot\w* a etapa)\b\s*:?\s*(?P<etapa2>.{3,60}?)\W*$")),
    # A PERGUNTA vem antes do pedido: "voce reconhece o meu rosto?" quer uma resposta,
    # nao um cadastro. Em 19/09 o Senhor tentou varias formas e TODAS caiam no modelo,
    # que respondia "sou so um assistente de voz e nao posso memorizar rostos".
    ("id_quem", R(rf"\bquem (?:esta|ta|e|eh|e que esta) (?:aqui|ai|na sala|na camera|na minha frente|na frente da camera|essa pessoa"
                  rf"|esse|essa|comigo|falando)\b|\bquem sou eu\b|\bsabe quem (?:eu sou|e ele|e ela)\b"
                  rf"|\bvoce (?:me )?(?:reconhec\w+|lembra (?:de mim|quem))\b"
                  rf"|\bvoce (?:reconhec\w+|conhec\w+) {_DET}{_ROSTO}\b")),
    ("id_listar", R(r"\bquem voce conhece\b|\bquais (?:rostos|vozes|pessoas) voce conhece\b|\bde quem voce (?:conhece|sabe)\b"
                    r"|\bquem (?:ja )?(?:esta |foi )?cadastrad[oa]s?\b|\bque rostos voce (?:conhece|tem|guardou)\b")),
    ("id_cancelar", R(r"\b(?:cancel\w*|interromp\w*|par\w*)\s+(?:o\s+)?(?:cadastro|registro|captura)\s+(?:d[aoe]\s+)?"
                      r"(?:minha\s+|meu\s+)?(?:voz|rosto|pessoa|biometri\w*)\b")),
    ("id_pessoa_esquecer", R(rf"\b(?:esquec\w*|apag\w*|remov\w*|delet\w*|descadastr\w*)\b{_MEIO}\s+{_DET}{_ROSTO_E_VOZ}\b")),
    ("id_esquecer", R(rf"\b(?:esquec\w*|apag\w*|remov\w*|delet\w*|descadastr\w*)\b{_MEIO}\s+{_DET}"
                      rf"(?P<tipo>rostos?|vozes|voz|caras?|faces?)\b"
                      rf"(?:\s+(?:dela|dele)\b|\s+d[aoe]s?\s+(?P<nome>[a-z][\w\s]{{0,30}}?)\b)?")),
    ("id_pessoa_cadastrar", R(rf"\b{_CADASTRAR}\b{_MEIO}\s+{_DET}{_ROSTO_E_VOZ}\b")),
    ("id_rosto_cadastrar", R(rf"\b{_CADASTRAR}\b{_MEIO}\s+{_DET}{_ROSTO}\b"
                             rf"(?:\s+(?:dela|dele)\b|\s+d[aoe]\s+(?P<nome>[a-z][\w\s]{{0,30}}?)\b)?")),
    ("id_voz_cadastrar", R(rf"\b(?:{_CADASTRAR}|reconhec\w+)\b{_MEIO}\s+{_DET}(?:voz|vozinha)\b"
                           rf"(?:\s+(?:dela|dele)\b|\s+d[aoe]\s+(?P<nome>[a-z][\w\s]{{0,30}}?)\b)?")),
    ("id_so_dono", R(r"\b(?:so|somente|apenas) (?:atend\w*|obede\w*|ouc\w*|escut\w*|respond\w*)\b.{0,15}\b(?:minha voz|a mim|eu|o dono)\b"
                     r"|\b(?:atend\w*|obede\w*|ouc\w*) (?:qualquer|todo mundo|qualquer pessoa|outras vozes|todas as vozes)\b")),
    ("repetir", R(r"^\W*(?:jarvis\W*)?(?:repita|repete|fala de novo|diga de novo|o que voce (?:disse|falou)|nao (?:entendi|ouvi))\W*$")),
    ("parar_fala", R(r"^\W*(?:jarvis\W*)?(?:pare|para|parar|chega|silencio|cala a boca|fica quieto|cancela|cancelar"
                     r"|para de falar|pare de falar|stop)\W*(?:jarvis)?\W*$")),
    # automacao: protocolos com nome e comandos com horario marcado (antes de apps/sites)
    ("reuniao_preparar", R(r"^\W*(?:jarvis\W*)?(?:por favor\W*)?(?:prepar\w*|organiz\w*)\s+(?:(?:a|minha|uma|proxima)\s+)*"
                          r"reuniao(?:\s+(?P<consulta>.{1,100}?))?\W*$")),
    ("modo_foco", R(r"\b(?P<acao>ativ\w*|lig\w*|entr\w*|desativ\w*|deslig\w*|sai\w*)\s+(?:o |no |do )?(?:modo )?foco\b"
                    r"|^\W*(?:jarvis\W*)?(?:modo foco|nao me interrompa)\W*$")),
    ("avisos_canal", R(r"\b(?:avisos|notificacoes|alertas)\s+(?:(?:somente|so|apenas)\s+)?(?P<canal>no painel|por texto|por voz|falados)\b")),
    ("capacidades", R(r"\bdiagnostico (?:das |de )?capacidades\b|\bquais (?:as |sao as )?capacidades (?:estao )?(?:disponiveis|conectadas)\b"
                      r"|\bo que (?:esta|ta) funcionando\b")),
    ("raciocinio", R(r"^\W*(?:jarvis\W*)?(?:por favor\W*)?(?:planej\w*|prioriz\w*|organiz\w* (?:o |a |meu |minha |meus |minhas )|me ajud\w* a (?:planejar|organizar|decidir|priorizar|escolher)|o que (?:eu )?(?:devo|deveria) fazer primeiro|por onde (?:eu )?comec\w*)")),
    ("casa_descobrir", R(r"\b(?:quais|que|procur\w*|descubr\w*|list\w*|mostr\w*|busqu\w*|busc\w*)\b.{0,20}\b(?:aparelhos|dispositivos|equipamentos)\b"
                         r"(?:.{0,20}\b(?:casa|rede)\b)?")),
    ("agendar", R(r"^\W*(?:jarvis\W*)?(?:(?:tod[oa]s? (?:os |as )?(?:dias?(?: uteis)?|manhas?|noites?|tardes?|segundas?|tercas?|quartas?|quintas?|sextas?|sabados?|domingos?)(?:-feiras?)?|diariamente|de segunda a sexta|dias uteis)(?:[\s,]+(?:as|a|ao) (?:\d{1,2}(?:h\d{0,2}|:\d{2}| ?horas?)?|uma|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|meio[- ]dia|meia[- ]noite))?|(?:(?:amanha|hoje)[\s,]+)?(?:as|ao) (?:\d{1,2}(?:h\d{0,2}|:\d{2}| ?horas?)?|uma|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|meio[- ]dia|meia[- ]noite))(?: (?:horas?|h|da manha|da tarde|da noite|em ponto))*[\s,]+(?P<acao>(?!(?:me )?lembr|me avis)[a-z].{3,})$")),
    ("armadura", R(r"\bprepar\w* (?:a )?(?:armadura|mark(?: \w+)?)\b|\bdiagnostico completo\b|\bcheck ?up\b"
                     r"|\bchecagem (?:completa|geral|dos sistemas)\b|\bverificacao completa\b"
                   r"|\bverifi\w* (?:todos )?(?:os )?sistemas\b"
                   r"|^\W*(?:jarvis\W*)?(?:(?:execut|inici|ativ)\w* )?(?:o )?protocolo (?:armadura|mark(?: \w+)?)\W*$")),
    ("protocolo_criar", R(r"\b(?:cri\w*|defin\w*|salv\w*|grav\w*|mont\w*|configur\w*)\b (?:o |um |uma )?(?:novo )?protocolo "
                          r"(?:chamado |de nome )?(?P<nome>[a-z0-9][\w\s-]{0,30}?)\s*(?::|,| com os passos| que (?:faz|faca|deve)| para)\s+(?P<passos>.+)$")),
    ("protocolo_listar", R(r"\b(?:quais|liste|lista|mostre|diga)\b.{0,20}\bprotocolos\b")),
    ("protocolo_apagar", R(r"\b(?:apag\w*|remov\w*|exclu\w*|delet\w*)\b (?:o )?protocolo (?P<nome>[a-z0-9][\w\s-]{0,30}?)\W*$")),
    ("protocolo_executar", R(r"\b(?:execut\w*|inici\w*|ativ\w*|rod\w*|dispar\w*|acion\w*|comec\w*)\b (?:o )?protocolo (?P<nome>[a-z0-9][\w\s-]{0,30}?)(?:\s+com\s+(?P<parametros>.+?))?\W*$"
                             r"|^\W*(?:jarvis\W*)?protocolo (?P<nome2>[a-z0-9][\w\s-]{0,30}?)\W*$")),
    ("consumo", R(r"\b(?:o que|quem|quais? (?:programas?|processos?|apps?|aplicativos?))\b.{0,25}\b(?:consumindo|gastando|usando|pesando|comendo|puxando)\b"
                  r"|\b(?:consumo|gasto) de (?:energia|bateria|memoria|cpu|processador)\b"
                  r"|\bo que (?:esta|ta) (?:deixando|travando) o (?:pc|computador|notebook)(?: lento)?\b")),
    ("voz_desativar", R(r"\b(?:desativ\w*|deslig\w*|tir\w*)\b.{0,6}\b(?:a )?voz\b|\bmodo (?:so )?texto\b"
                        r"|\bfique (?:calado|em silencio)\b|\bresponda (?:so )?por escrito\b")),
    ("voz_ativar", R(r"\b(?:ativ\w*|lig\w*|volt\w*)\b.{0,6}\b(?:a )?voz\b|\bpode (?:voltar a )?falar\b")),
    ("presenca", R(r"^\W*(?:jarvis\W*)?(?:(?:voce )?(?:esta|ta|tah) (?:ai|acordado|online|ouvindo|comigo)|me ouve|acorda)\W*(?:jarvis)?\W*$")),
    ("obrigado", R(r"^\W*(?:jarvis\W*)?(?:muito )?(?:obrigad\w*|valeu|brigad\w*)\W*(?:jarvis)?\W*$")),
    ("cumprimento", R(r"^\W*(?:jarvis\W*)?(?:oi|ola|opa|e ai|eai|salve|hey|fala)\W*(?:jarvis)?\W*$")),
    ("despedida", R(r"^\W*(?:jarvis\W*)?(?:tchau|ate (?:logo|mais|amanha|depois|a proxima)|falou|fui"
                    r"|encerr\w* (?:a )?conversa|pode (?:ir|descansar)|dispensado)\W*(?:jarvis)?\W*$")),
    ("como_voce_esta", R(r"^\W*(?:jarvis\W*)?(?:e )?(?:ai\W*)?(?:como (?:voce )?(?:esta|vai|ta|anda)|tudo (?:bem|certo|bom|em ordem)"
                         r"|beleza|como (?:estao|vao) (?:os|seus) sistemas)\W*(?:jarvis)?\W*$")),
    ("quem_e_voce", R(r"\bquem (?:e|eh) voce\b|\bquem voce e\b|\bse apresent\w*|\bquem (?:te|lhe) (?:criou|fez|programou)\b"
                      r"|\bo que voce (?:e|faz|sabe fazer|consegue fazer|pode fazer)\b|\bquais (?:sao )?(?:os )?seus comandos\b"
                      r"|\bcomo voce funciona\b")),
    ("piada", R(r"\bpiada\b|\bme faca rir\b|\bme faz rir\b|\balgo engracado\b")),
    ("briefing", R(r"^\W*(?:jarvis\W*)?(?:bom dia|boa tarde|boa noite)\W*(?:jarvis)?\W*$|\bme atualiz\w*|\bresumo do dia\b|\bbriefing\b"
                   r"|\bo que (?:eu )?perdi\b|\bcomo (?:esta|ta) (?:o|meu) dia\b|\bprepar\w* (?:o )?(?:meu |o )?dia\b")),
    # varredura de imagens: analisa sem mover; quarentena so com "confirmo quarentena"; nunca apaga
    ("quarentena_confirmar", R(r"^\W*(?:jarvis\W*)?confirmo\W*(?:a )?quarentena\W*(?:jarvis)?\W*$")),
    ("quarentena_restaurar", R(r"\b(?:restaur\w*|devolv\w*|tir\w*)\b.{0,20}\bquarentena\b")),
    ("quarentena_listar", R(r"\b(?:o que tem|quais|liste|lista|mostre)\b.{0,15}\bquarentena\b")),
    ("quarentena_mover", R(r"\b(?:mov\w*|coloq\w*|mand\w*|pass\w*)\b.{0,30}\bquarentena\b")),
    ("varredura", R(r"\b(?:varr\w*|escane\w*|verifi\w*|analis\w*|examin\w*|cheq\w*)\b.{0,15}\b(?:as |minhas |todas as )?(?:imagens|fotos)\b"
                    r"|\b(?:imagens|fotos) (?:improprias|sensiveis|de nudez|adultas|explicitas)\b")),
    ("midia", R(r"^\W*(?:jarvis\W*)?(?:por favor\W*)?(?:(?:voce )?(?:pode|poderia|consegue) )?(?:me )?(?:transcrev\w*|transcri\w*|analis\w*|resum\w*|o que (?:diz|dizem|falam))\b.{0,25}"
                r"\b(?:audio|video|gravacao|podcast|mp3|mp4|m4a|wav)\b")),
    ("documento", R(r"^\W*(?:jarvis\W*)?(?:por favor\W*)?(?:(?:voce )?(?:pode|poderia|consegue) )?(?:me )?(?:resum\w*|o que diz|expliqu\w*|analis\w*|le|ler|leia)\b.{0,25}\b(?:documento|arquivo|pdf|word|docx"
                    r"|relatorio|contrato|apostila|artigo|trabalho)\b|\bresum\w*\b.{0,5}\b[a-z]:\\")),
    ("olhar_auto", R(r"\b(?P<acao>ativ\w*|lig\w*|desativ\w*|deslig\w*)\b.{0,12}\b(?:o )?(?:olhar|reconhecimento|visao) automatic\w*"
                      r"|\bregiao de visao (?:na |no |para a |para o )?(?P<regiao>centro|mesa|inteira|tudo)\b")),
    ("tema", R(r"\b(?:tema|modo|visual|tela)\s+(?P<tema>hud|classico|original|antigo|novo)\b")),
    ("tela", R(r"\b(?:olh\w*|ve|ver|veja|vej\w*|analis\w*|le|ler|leia|examin\w*|verifi\w*|confir\w*|confer\w*) (?:a |para a |pra )?(?:minha |essa |esta |a )?(?:tela|janela)\b(?! cheia)"
               r"|\bo que (?:tem|ha|aparece|esta) (?:na|nessa|nesta) (?:minha )?(?:tela|janela)\b"
               r"|\bexpli\w* (?:esse|este|o) erro\b|\bque erro (?:e|eh) esse\b|\bme ajud\w* com (?:esse|este) erro\b")),
    ("vigia_desligar", R(r"\b(?:desativ\w*|deslig\w*|desarm\w*|par\w*|encerr\w*)\b.{0,12}\b(?:o )?(?:modo )?(?:vigia|vigilancia|sentinela)\b")),
    ("vigia_ligar", R(r"\b(?:ativ\w*|lig\w*|inici\w*|arm\w*|entr\w* (?:em|no))\b.{0,12}\b(?:o )?(?:modo )?(?:vigia|vigilancia|sentinela)\b"
                      r"|\bvigi\w* (?:a sala|o quarto|a casa|o ambiente|o escritorio|a porta)\b")),
    ("tarifa", R(r"\btarifa (?:de luz |de energia |do kwh |da luz )?(?:e|eh|esta|custa|agora e)\b")),
    ("cura_abrir", R(r"\b(?:abr\w*|mand\w*|envi\w*|lev\w*|coloq\w*)\b.{0,20}\b(?:no|para o|pro|ao) cura\b"
                     r"|\bimprim\w* (?:isso|esse|essa|a peca|o projeto|a engrenagem|a caixa|o tubo|o cilindro)\b")),
    ("projetar", R(r"\b(?:projet\w*|model\w*|desenh\w*|cri\w*|fac\w*|ger\w*)\b (?:um |uma |o |a )?(?:\w+ )?"
                   r"(?:engrenage\w*|caixa(?! de entrada)|cilindro|tubo|esfera|cone|pino|disco)\b")),
    ("dados_analisar", R(r"\banalis\w* (?:o |a |os |as |meu |minha )?(?:arquivo|planilha|tabela|dados|csv)\b(?: (?:de|do|da|dos|das|chamad[oa]))? ?(?P<q>.*)$")),
    ("engenharia", R(r"\b(?:ohms?|volts?|voltagem|amperes?|miliamperes?|watts?|kw|quilowatts?)\b|\blanc\w*\b.*\bgraus\b"
                     r"|\benergia cinetica\b|\b(?:cai\w*|queda)\b.*\bmetros?\b|\bdensidade\b|\b(?:ponto|temperatura) de fusao\b"
                     r"|\bcompar\w*\b.*\b(?:aco|aluminio|titanio|cobre|latao|bronze|inox|pla|abs|petg|nylon|chumbo|ouro|prata)\b"
                     r"|\bquanto pesa (?:um|uma)\b|\bresistencia (?:do|da)\b")),
    ("holograma_fechar", R(r"\b(?:fech\w*|deslig\w*|sai\w* d\w*)\b.{0,10}\b(?:a |o )?(?:mesa holografica|holograma)\b")),
    ("holograma_abrir", R(r"\b(?:abr\w*|mostr\w*|lig\w*|ativ\w*|inici\w*|projet\w*)\b.{0,10}\b(?:a |o )?(?:mesa holografica|holograma|mesa do tony)\b"
                          r"|^\W*(?:jarvis\W*)?(?:modo )?holograma\W*$")),
    ("modelo_mostrar", R(r"\b(?:mostr\w*|abr\w*|carreg\w*|exib\w*|coloq\w*)\b (?:o |a )?(?:modelo|arquivo|projeto|peca|desenho)(?: 3d)?"
                         r"(?: (?:do|da|de|chamado))? (?P<q>[\w\s.-]{2,40}?)(?: (?:no|na|em) (?:holograma|3d|mesa(?: holografica)?))?\W*$")),
    ("modelo_girar", R(r"\b(?:gir\w*|rod\w*)\b (?:o |a )?(?:modelo|holograma|projeto|peca)\b|\bpar\w* de girar\b")),
    ("modelo_zoom", R(r"\b(?:aument\w*|diminu\w*|aproxim\w*|afast\w*)\b (?:o )?(?:zoom|modelo|holograma)\b")),
    ("grafico", R(r"\b(?:mostr\w*|exib\w*|abr\w*|faca|desenh\w*|coloq\w*)\b (?:o |um )?grafico (?:d[oa]s? |de )?(?P<q>[\w\s-]{2,30}?)\W*$")),
    ("regua_calibrar", R(r"\bcalibr\w*\b.{0,20}\b(?:a |da )?(?:regua|medida|medicao|mesa)\b")),
    ("medir", R(r"\bquanto (?:mede|tem de (?:comprimento|largura))\b|\bqual (?:e )?(?:o )?tamanho\b|\bqual (?:e )?a medida\b"
                r"|\bmeca\b|\bme(?:d|c)\w* (?:isso|isto|esse|essa|este|esta|o |a |meu |minha )|\btamanho (?:disso|desse|dessa|deste|desta)\b")),
    ("percepcao_contar", R(r"\bquant[oa]s (?P<q>[a-z][\w\s-]{1,30}?) (?:tem|ha|existem|estao|aparecem|voce (?:ve|esta vendo|enxerga|conta))\b")),
    ("percepcao_mudou", R(r"\bo que mudou\b|\bmudou alguma coisa\b|\bo que (?:apareceu|sumiu|saiu) (?:na|da) (?:mesa|regiao|camera)\b")),
    ("percepcao_onde", R(r"\bonde (?:esta|estao|ta|ficou|deixei|coloquei) (?:o |a |os |as |meu |minha |meus |minhas )?(?P<q>[\w\s]{2,40}?)\W*$"
                         r"|\bvoce (?:ve|esta vendo|enxerga) (?:o |a |os |as |meu |minha |meus |minhas )(?P<q2>[\w\s]{2,40}?)\W*$")),
    ("percepcao_ver", R(r"\bo que (?:voce )?(?:esta|ta) vendo\b|\bo que (?:voce )?(?:ve|enxerga)\b|\bdescrev\w* (?:o ambiente|a cena|o que (?:voce )?ve|a mesa)"
                        r"|\bo que (?:tem|ha) (?:na mesa|na minha frente|ao meu redor|a minha volta|na regiao|ai na camera)\b"
                        r"|\bolh\w* (?:ao (?:meu )?redor|em volta|a mesa)\b")),
    ("visao", R(r"\bo que (?:e|eh) (?:isso|isto|esse|essa|este|esta|aquilo)\b|\bo que (?:eu )?(?:estou|to|tou) (?:segurando|mostrando)\b"
                r"|\b(?:reconhe\w*|identifi\w*|analis\w*|escane\w*|examin\w*)\b.{0,30}\b(?:isso|isto|objeto|item|coisa|aqui|imagem|cena|camera)\b"
                r"|\bque (?:objeto|coisa|modelo|marca|tipo|celular|aparelho|produto|carro|livro|planta)(?: de \w+)? (?:e|eh) (?:esse|essa|este|esta|isso|aquele|aquela)\b"
                r"|\bo que (?:voce )?(?:esta|ta) vendo\b|\bdescrev\w* (?:o que|a cena|a imagem|o que ve)|\bolh\w* (?:isso|isto|aqui|para a camera)\b")),
    ("camera_desligar", R(r"\b(?:deslig\w*|desativ\w*|fech\w*|apag\w*)\b.{0,20}\b(?:camera|webcam)\b")),
    ("camera_ligar", R(r"\b(?:lig\w*|ativ\w*|abr\w*|acend\w*)\b.{0,20}\b(?:camera|webcam)\b")),
    ("capacete_desligar", R(r"\b(?:deslig\w*|desativ\w*|fech\w*|tir\w*|sa\w+ do)\b.{0,25}\b(?:capacete|hud)\b")),
    ("capacete_ligar", R(r"\b(?:lig\w*|ativ\w*|abr\w*|mostr\w*|coloc\w*|coloq\w*|entr\w*|modo)\b.{0,25}\b(?:capacete|hud)\b|\bmodo capacete\b")),
    ("rosto_ocultar", R(r"\b(?:ocult\w*|escond\w*|tir\w*)\b.{0,15}\b(?:rosto|imagem da camera)\b")),
    ("rosto_mostrar", R(r"\bmostr\w*\b.{0,15}\b(?:rosto|imagem da camera)\b")),
    ("tela_cheia", R(r"\btela cheia\b|\bmaximiz\w*\b")),
    ("microfone_desligar", R(r"\b(?:deslig\w*|desativ\w*|par\w* de ouvir)\b.{0,15}\b(?:microfone|mic)\b|\bpare de me ouvir\b")),
    ("janela", R(r"\b(?:abr\w*|mostr\w*|v[ae]\w* para|traz\w*)\b.{0,15}\b(?P<j>painel|chat|conversa escrita)\b")),
    ("lista_add", R(r"^\W*(?:jarvis\W*)?(?:adicion\w*|coloc\w*|coloq\w*|po[en]\w*|bot\w*|inclu\w*|acrescent\w*|anot\w*)\s+(?P<itens>.+?)\s+"
                    r"(?:a|na|no|para a|pra|pra a)\s+(?:minha )?lista(?:\s+(?:de|do|da)\s+(?P<lista>[\w\s]+?))?\W*$")),
    ("lista_tirar", R(r"^\W*(?:jarvis\W*)?(?:tir\w*|remov\w*|apag\w*|risc\w*)\s+(?P<item>.+?)\s+da\s+(?:minha )?lista(?:\s+(?:de|do|da)\s+(?P<lista>[\w\s]+?))?\W*$")),
    ("lista_limpar", R(r"\b(?:limp\w*|esvazi\w*|zer\w*)\b.{0,6}\blista(?:\s+(?:de|do|da)\s+(?P<lista>[\w\s]+?))?\W*$")),
    ("lista_ler", R(r"\b(?:o que tem|o que ha|leia|ler|le|mostr\w*|diz\w*|fal\w*|qual e|quais (?:sao )?(?:os )?itens|quais itens)\b.{0,14}\blista(?:\s+(?:de|do|da)\s+(?P<lista>[\w\s]+?))?\W*$")),
    ("hora_mundo", R(r"\b(?:que horas? (?:sao|e)|horario|hora certa|que hora e)\b.{0,8}?\b(?:em|no|na|de)\s+(?P<cidade>[a-z][\w\s]{1,40}?)\W*$")),
    ("clima_mundo", R(r"\b(?:clima|tempo|temperatura|previsao|vai chover)\b.{0,25}?\b(?:em|no|na)\s+(?P<cidade>(?!hoje\b|amanha\b|agora\b)[a-z][\w\s]{1,40}?)(?:\s+(?:hoje|amanha|agora))?\W*$")),
    ("tocar", R(r"^\W*(?:jarvis\W*)?(?:(?:toque|toca|tocar|reproduz\w*|quero ouvir|coloque|coloca|bota|ponha)\s+(?:para|pra)\s+tocar\s+"
                r"|(?:toque|toca|tocar|reproduz\w*|quero ouvir)\s+)(?:a musica |a cancao |musica )?"
                r"(?P<q>(?!a musica\b|musica\b|uma musica\b|umas musicas\b|uma cancao\b|o som\b|som\b|um som\b|a faixa\b|a playlist\b|playlist\b|alguma coisa\b|qualquer coisa\b)[^?!]{2,80}?)(?:\s+no\s+(?P<onde>youtube|spotify))?\W*$")),
    ("youtube_tocar", R(r"\b(?:toqu\w*|toca|tocar|coloqu\w*|poe|bota|ponha)\b\s+(?P<q>.+?)\s+no youtube\b")),
    ("modo_proativo", R(r"\bmodo (?P<modo>proativo|assistido|sob demanda)\b|\bso fal\w* (?:comigo )?quando eu (?:chamar|pedir)\b"
                        r"|\bpode falar sozinho\b")),
    ("monitor_cotacao", R(r"\bavis\w* (?:quando|se) (?:o |a )?(?P<ativo>" + _ATIVOS + r")\b.{0,12}?(?P<dir>passar de|passar dos?"
                          r"|subir (?:acima )?de|ultrapassar|chegar a|cair abaixo de|ficar abaixo de|baixar de|descer de|cair para)"
                          r"\s*(?:r\$\s*)?(?P<v>\d[\d.,]*(?:\s*mil)?)")),
    ("monitor_noticia", R(r"\bavis\w* (?:quando|se) (?:sair|sairem|tiver|houver|aparecer|publicarem) (?:alguma |uma |nova )?"
                          r"noticias? (?:nova )?(?:sobre|de|do|da|dos|das) (?P<q>.{2,60})")),
    ("monitor_site", R(r"\b(?:monitor\w*|vigi\w*|acompanh\w*|observ\w*|fique de olho n\w*) (?:o |no )?(?:site|pagina)\s+(?P<u>\S+)")),
    ("monitor_pasta", R(r"\b(?:monitor\w*|vigi\w*|fique de olho n\w*) (?:a |na )?pasta\s+(?P<p>.+)")),
    ("monitores_listar", R(r"\b(?:quais|meus|liste|lista|mostre)\b.{0,15}\bmonitor(?:es|amentos)\b")),
    ("monitor_mudar", R(r"\b(?P<acao>remov\w*|apag\w*|cancel\w*|exclu\w*|desativ\w*|paus\w*|retom\w*|reativ\w*)\b.{0,12}\bmonitor\w*\b")),
    ("planilha", R(r"\b(?:cri\w*|fa[cz]\w*|mont\w*|ger\w*|prepar\w*|nova)\b.{0,15}\bplanilhas?\b|^\W*(?:jarvis\W*)?planilha (?:de|para|do|da|dos|das)\b")),
    ("programa", R(r"\b(?:cri\w*|fa[cz]\w*|escrev\w*|ger\w*|program\w*|desenvolv\w*|mont\w*)\b.{0,20}\b(?:programa|script|codigo)\b"
                   r"(?:.{0,20}\b(?:python|que|para|pra)\b)")),
    ("cotacao", R(r"\b(?:cotac\w*|preco|valor|quanto (?:esta|ta|custa|vale|anda|sai|fechou|subiu|caiu)"
                  r"|como (?:esta|ta|anda|fechou) o|(?:subiu|caiu) o)\b.{0,30}\b(?:" + _ATIVOS + r"|cripto\w*)\b"
                  r"|\b(?:dolar|euro|bitcoin|ethereum|libra|cripto\w*) (?:hoje|agora)\b|\bcotac(?:ao|oes)\b"
                  r"|\bcomo (?:estao|andam) as cripto\w*")),
    ("pesquisar", R(r"\b(?:pesquis\w*|procur\w*|busc\w*|busqu\w*|googl\w*)\b\s+(?:no (?P<onde>google|youtube)\s+)?(?:por |sobre |o que e |a )?(?P<q>.{2,})")),
    ("musica_pausar", R(r"\b(?:paus\w*|pare|para|parar|interromp\w*)\b.{0,15}\b(?:musica|som|video|faixa|spotify)\b|^\W*(?:jarvis\W*)?pausa\W*$")),
    ("musica_proxima", R(r"\b(?:proxim\w*|pul\w*|avanc\w*|troc\w*)\b.{0,15}\b(?:musica|faixa|cancao|video)\b|^\W*(?:jarvis\W*)?proxima\W*$")),
    ("musica_anterior", R(r"\b(?:anterior|volt\w*)\b.{0,15}\b(?:musica|faixa|cancao)\b|\bmusica anterior\b")),
    ("musica_tocar", R(r"\b(?:toqu\w*|toca|tocar|solt\w*|continu\w*|retom\w*|play|volt\w* a tocar|bot\w*|coloc\w*|po[en]\w*)\b"
                       r".{0,15}\b(?:musica|som|faixa|spotify|playlist)\b")),
    # casa (rede local) e comunicacao
    ("casa_confirmar", R(r"\bconfirmo (?:destrancar|abrir|abertura)\b")),
    ("casa_adicionar", R(r"\badicion\w* (?:a |o )?(?:tomada|lampada|luz|rele|interruptor|aparelho|dispositivo)\b.{0,12}?"
                         r"(?P<ip>\d{1,3}(?:[.,]\d{1,3}){3}) (?:como|chamad[oa]) (?:a |o )?(?P<nome>[\w\s]{2,30})\W*$")),
    ("casa_volume", R(r"\bvolume d[ao] (?P<alvo>tv|televisao|televisor|som da sala|caixa de som)\b.{0,6}?\b(?:em|para|pra|no)\s+(?P<n>\d{1,3})\b"
                      r"|\b(?P<dir>aument\w*|diminu\w*|abaix\w*|sub\w*) o volume d[ao] (?P<alvo2>tv|televisao|televisor|caixa de som)\b")),
    ("casa_controlar", R(r"^\W*(?:jarvis\W*)?(?:por favor\W*)?(?P<acao>lig\w*|deslig\w*|acend\w*|apag\w*|paus\w*|continu\w*|tran[cq]\w*|destran[cq]\w*|abr\w*|fech\w*)\s+"
                         r"(?:a |o |as |os )?(?P<alvo>(?:luz|luzes|lampada|lampadas|abajur|tomada|tv|televisao|televisor|ventilador|ar condicionado"
                         r"|porta|portao|fechadura|cortina|cortinas|persiana|interruptor|rele|aquecedor|cafeteira|umidificador)\b[\w\s]{0,30}?)\W*$")),
    ("whatsapp", R(r"\b(?:mand\w*|envi\w*|escrev\w*)\b.{0,25}?\b(?:whatsapp|whats|zap)\b.{0,15}?\b(?:para|pro|pra) "
                   r"(?P<num>\+?[\d\s().-]{8,20}?)\s*(?:dizendo|falando|com o texto|com|que|:)\s*(?P<txt>.+)$")),
    ("celular_avisar", R(r"\b(?:avis\w*|mand\w*|envi\w*|escrev\w*)\b.{0,12}\b(?:no|pro|pra|para o|ao) (?:meu )?(?:celular|telegram|telefone)\b\W*(?:que|dizendo|:)?\s*(?P<txt>.*)$")),
    ("volume_desmutar", R(r"\b(?:tir\w*|desativ\w*|desliga\w*)\b.{0,10}\bmudo\b|\b(?:ativ\w*|volt\w*|lig\w*) o som\b|\bcom som\b")),
    ("volume_mutar", R(r"\b(?:sem som|modo mudo|mudo|silenci\w* o (?:pc|computador|som)|corte o som)\b")),
    ("volume_definir", R(r"\bvolume\b.{0,15}?\b(?:em|para|no|pra|a)\s+(?P<n>\d{1,3})\b")),
    ("volume_aumentar", R(r"\b(?:aument\w*|sob\w*|ergu\w*|mais alto)\b.{0,15}\b(?:volume|som)\b|\bmais volume\b"
                          r"|\b(?:volume|som)\b.{0,20}\bmais alto\b"
                          r"|^\W*(?:jarvis\W*)?(?:mais alto|fala mais alto|ta baixo|esta baixo)\W*$")),
    ("volume_diminuir", R(r"^\W*(?:jarvis\W*)?(?:mais baixo|ta alto|esta alto)\W*$"
                          r"|\b(?:abaix\w*|diminu\w*|reduz\w*|baix\w*|mais baixo)\b.{0,15}\b(?:volume|som)\b|\bmenos volume\b"
                          r"|\b(?:volume|som)\b.{0,20}\bmais baixo\b")),
    ("site", R(r"\b(?:abr\w*|entr\w*|v[ae]\w* (?:no|para o|pro)|mostr\w*)\b.{0,12}\b(?P<s>youtube|g1|gmail|e-?mail|google agenda|agenda do google"
               r"|spotify|netflix|whatsapp|google maps|mapas?|google|instagram|linkedin|github|chatgpt|bbc)\b")),
    # memoria do Senhor ("lembre que..." guarda; "me lembre de... as 15h" e lembrete)
    ("agenda_conflitos", R(r"\b(?:conflito\w*|choque\w*|sobrepost\w*|encavalad\w*)\b.{0,25}\b(?:agenda|compromisso\w*|horario\w*|reuni\w*)\b"
                           r"|\btenho (?:algum )?(?:conflito|choque)\b")),
    ("agenda_livres", R(r"\b(?:horarios?|tempo|janelas?|espaco) (?:livres?|vagos?|disponive\w*)\b|\bquando (?:estou|to|fico|vou estar) livre\b"
                        r"|\btenho (?:um |algum )?(?:horario|tempo) livre\b")),
    ("confirmar_acao", R(r"^\W*(?:jarvis\W*)?confirmo\W*(?P<acao>bloquear|suspender)\W*(?:jarvis)?\W*$")),
    ("memoria_limpar_confirmado", R(r"\bconfirmo\b.{0,20}\bapag\w*\b.{0,20}\bmemoria\b")),
    ("memoria_limpar", R(r"\b(?:apag\w*|limp\w*|zer\w*|esquec\w*)\b.{0,12}\b(?:toda a (?:sua )?memoria"
                         r"|tudo (?:o )?que (?:voce )?sabe (?:sobre|de) mim|tudo sobre mim)\b")),
    ("memoria_listar", R(r"\bo que (?:voce )?(?:sabe|lembra|guardou) (?:sobre|de) mim\b|\b(?:mostr\w*|list\w*|le\w*) (?:a )?(?:sua )?memoria\b"
                         r"|\bo que (?:voce )?tem (?:na|em) (?:sua )?memoria\b")),
    ("memoria_esquecer", R(r"^\W*(?:jarvis\W*)?(?:esqueca|esquece|esquecer|apague da (?:sua )?memoria|tire da (?:sua )?memoria"
                           r"|remova da (?:sua )?memoria)\b[\s,:]*(?:que |o que (?:eu )?(?:te )?(?:disse|falei) sobre )?(?P<fato>.{2,})$")),
    ("memoria_corrigir", R(r"^\W*(?:jarvis\W*)?(?:corrij\w*|corrig\w*|atualiz\w*) (?:a |na |sua )?(?:memoria|informacao)[\s,:]*(?:que )?(?P<fato>.{3,})$")),
    ("memoria_guardar", R(r"^\W*(?:jarvis\W*)?(?:(?:lembre|lembra|memorize|grave|guarde|saiba)(?:-se)?(?: (?:disso|de que))?[\s,]*(?:que|:)"
                          r"|(?:guarde|grave|anote|coloque|salve) (?:isso )?(?:na|em) (?:sua )?memoria(?: que|:)?)\s*(?P<fato>.{3,})$")),
    ("lembretes_cancelar", R(r"\b(?:cancel\w*|apag\w*|limp\w*|remov\w*)\b.{0,20}\b(?:lembretes?|timers?|alarmes?|temporizador\w*)\b")),
    ("lembretes_listar", R(r"\b(?:quais|meus|liste|lista|leia|ler)\b.{0,20}\blembretes\b|\btenho (?:algum )?lembrete")),
    ("lembrete_adiar", R(r"\b(?:adi[ae]\w*|posterg\w*|soneca)\b|^\W*(?:jarvis\W*)?(?:me (?:de|da) )?mais (?P<n>\d{1,3}|cinco|dez|quinze|vinte|trinta) minutos\W*$")),
    ("lembrete_remarcar", R(r"\b(?:mud\w*|troc\w*|remarc\w*|pass\w*|alter\w*|transfir\w*)\b.{0,30}\b(?:lembrete|alarme|timer)\b.{0,40}\bpara\b")),
    ("timer", R(r"\b(?:timer|temporizador|cronometro|alarme|despertador)\b")),
    ("lembrete", R(r"\b(?:me\s+)?lembr[ae]\w*\b|\bme avis\w*\b|\bnao me deix\w* esquecer\b")),
    ("notas_listar", R(r"\b(?:quais|minhas|leia|liste|lista|ler)\b.{0,15}\bnotas\b|\bo que (?:eu )?anotei\b")),
    ("nota", R(r"^\W*(?:jarvis\W*)?(?:anot\w*|tom[ae] nota|registr\w*|salv\w* (?:uma )?nota)\b(?!.*\btarefa)")),
    ("noticia_abrir", R(r"\b(?:abr\w*|mostr\w*|detalh\w*|mais sobre|link d\w*|entr\w* n\w*)\b.{0,15}?\b(?P<ord>primeira|segunda"
                        r"|terceira|quarta|quinta|sexta|setima|oitava|nona|decima|ultima|\d{1,2}a?)\b.{0,10}\b(?:noticia|manchete|materia)\b"
                        r"|\b(?:abr\w*|mostr\w*)\b.{0,8}\b(?:noticia|manchete|materia) (?:numero )?(?P<num>\d{1,2}|um|uma|dois|duas|tres|quatro|cinco)\b")),
    ("noticias", R(r"\bnoticias?\b|\bmanchetes?\b|\bo que (?:ha|tem) de novo\b|\bnoticiario\b"
                   r"|\bquais (?:sao )?(?:as )?novidades\b|\balguma novidade\b"
                   r"|\bo que (?:esta|ta) acontecendo\b(?!.{0,12}\bcom\b)")),
    ("rascunho_gmail", R(r"\b(?:abr\w*|coloq\w*|pass\w*|mand\w* para o)\b.{0,20}\brascunho\b.{0,20}\b(?:gmail|e-?mail)\b")),
    ("rascunho", R(r"^\W*(?:jarvis\W*)?(?:por favor\W*)?(?:escrev\w*|redij\w*|redig\w*|prepar\w*|faca|faz|rascunh\w*|crie|cria|monte|monta)\b"
                   r".{0,20}\b(?:e-?mail|mensagem|resposta|recado|comunicado|convite)\b")),
    ("emails", R(r"\be-?mails?\b|\bcaixa de entrada\b|\bmensagens novas\b|\bnovas mensagens\b")),
    ("status", R(r"\b(?:relatorio|status|diagnostico)\b|\bcomo (?:esta|ta) o (?:sistema|computador|pc|notebook)\b")),
    # perguntas de fato ("quem foi", "o que e") -> pesquisa com fontes em vez do modelo adivinhar
    ("saber", R(r"^\W*(?:jarvis\W*)?(?:voce sabe |sabe |me diga |me diz )?(?:quem (?:e|eh|foi|era|foram)|o que (?:e|eh|foi|sao|significa)"
                r"|o que quer dizer|me (?:fal\w*|cont\w*|expliq\w*) (?:sobre|quem (?:e|foi)|o que (?:e|foi))|fal\w* (?:me )?sobre)"
                r"\s+(?!(?:isso|isto|esse|essa|aquilo|voce|que|eu|melhor|pior)\b)(?P<q>.{2,80}?)\W*$")),
    ("app", R(r"^\W*(?:jarvis\W*)?(?:por favor\W*)?(?:abr\w*|inici\w*|execut\w*|rod\w*|lanc\w*|carreg\w*)\s+(?:o |a |os |as |um |uma )?(?P<app>[\w .+#-]{2,40}?)\W*(?:por favor)?\W*$")),
]


def interpretar(texto: str) -> tuple[str, dict[str, str]] | None:
    n = normalizar(texto)
    for nome, regra in REGRAS:
        m = regra.search(n)
        if m:
            if nome in ("id_esquecer", "id_pessoa_esquecer") and re.search(
                    r"\b(?:nao|nunca)\b[^.!?]{0,35}\b(?:esquec\w*|apag\w*|remov\w*|delet\w*|descadastr\w*)", n):
                return "id_exclusao_negada", {}
            if nome in ("id_rosto_cadastrar", "id_voz_cadastrar", "id_pessoa_cadastrar"):
                if re.search(r"\b(?:nao|nunca)\b[^.!?]{0,35}\b" + _CADASTRAR, n):
                    return "id_cadastro_negado", {}
                if re.search(r"\bcomo (?:eu |posso |faco para |faz para )?" + _CADASTRAR, n):
                    return "id_ajuda", {}
            return nome, {k: v for k, v in m.groupdict().items() if v}
    return None


_VERBO_DE_ACAO = re.compile(
    r"\b(?:abr|lig|deslig|toc|toqu|paus|pare|aument|diminu|abaix|baix|cri|marc|lembr|anot|guard|salv"
    r"|pesquis|procur|busc|busqu|mostr|fech|coloc|ponh|bot|agend|program|silenci|tir|desativ|ativ|inici|execut"
    r"|olh|analis|identifi|reconhe|mud|troqu|troc|avis|registr|deix|faz|faca|prepar|organiz|configur|arrum|comec"
    # cadastro de pessoas, medidas, projeto e casa: sem estes o modelo respondia "nao posso"
    r"|memor|decor|cadastr|esquec|apag|remov|delet|med|meca|calibr|projet|imprim|model|desenh|cont|vigi"
    r"|descobr|descubr|ajust|envi|mand|list|adicion|acrescent|cancel|aprend|ensin|conect|control)\w*\b")


def parece_acao(texto: str) -> bool:
    """So manda a lista de ferramentas (~1000 tokens, lenta nesta CPU) quando a
    frase pede para FAZER algo; perguntas comuns vao sem ela."""
    return bool(_VERBO_DE_ACAO.search(normalizar(sem_chamado(texto))))


def texto_depois_do_verbo(original: str, verbos: str) -> str:
    """ "Jarvis, anote que amanha tem prova" -> "amanha tem prova"."""
    t = sem_chamado(original)
    t = re.sub(rf"^\W*(?:{verbos})\w*\W*(?:que|isso|isto|:)?\s*", "", t, flags=re.I)
    return t.strip(" .!?:") or t


# Ferramentas que o modelo pode chamar (formato OpenAI, aceito pelo servidor)
def _f(nome: str, desc: str, props: dict[str, Any] | None = None, obrig: list[str] | None = None) -> dict:
    return {"type": "function", "function": {"name": nome, "description": desc, "parameters": {
        "type": "object", "properties": props or {}, "required": obrig or []}}}


FERRAMENTAS = [
    _f("ligar_camera", "Liga ou desliga a câmera do computador.", {"ligada": {"type": "boolean"}}, ["ligada"]),
    _f("modo_capacete", "Abre ou fecha a visão do capacete (HUD sobre o rosto).", {"ligado": {"type": "boolean"}}, ["ligado"]),
    _f("olhar_camera", "Olha pela câmera e identifica o objeto que a pessoa está mostrando.",
       {"pergunta": {"type": "string"}}),
    _f("abrir_janela", "Abre uma janela do Jarvis.", {"nome": {"type": "string", "enum": ["painel", "chat", "jarvis"]}}, ["nome"]),
    _f("controlar_musica", "Controla a música tocando no computador.",
       {"acao": {"type": "string", "enum": ["tocar_pausar", "proxima", "anterior"]}}, ["acao"]),
    _f("volume", "Ajusta o volume do computador.",
       {"percentual": {"type": "integer", "minimum": 0, "maximum": 100}, "mudo": {"type": "boolean"},
        "ajuste": {"type": "string", "enum": ["aumentar", "diminuir"]}}),
    _f("abrir_site", "Abre um site conhecido no navegador.", {"site": {"type": "string", "enum": sorted(SITES)}}, ["site"]),
    _f("abrir_programa", "Abre um programa instalado no computador (menu Iniciar).", {"nome": {"type": "string"}}, ["nome"]),
    _f("pesquisar", "Pesquisa na internet e responde citando as fontes (Wikipédia, notícias). "
       "Use onde=google/youtube só se pedirem para abrir o navegador.",
       {"consulta": {"type": "string"}, "onde": {"type": "string", "enum": ["fontes", "google", "youtube"]}}, ["consulta"]),
    _f("cotacao", "Cotação atual de moedas (dólar, euro, libra...) ou criptomoedas (bitcoin, ethereum...).",
       {"ativos": {"type": "string", "description": "ex.: dólar, bitcoin"}}, ["ativos"]),
    _f("criar_lembrete", "Cria um lembrete falado. Use em_minutos OU horario (HH:MM); repetir é opcional.",
       {"texto": {"type": "string"}, "em_minutos": {"type": "integer"}, "horario": {"type": "string"},
        "amanha": {"type": "boolean"}, "repetir": {"type": "string", "enum": ["diario", "dias_uteis", "semanal"]}},
       ["texto"]),
    _f("anotar", "Guarda uma nota.", {"texto": {"type": "string"}}, ["texto"]),
    _f("noticias", "Lê manchetes. tema opcional: categoria (tecnologia, economia, esportes...) ou assunto livre.",
       {"tema": {"type": "string"}}),
    _f("resumo_do_dia", "Resumo do dia: hora, clima, agenda, e-mails, lembretes e notícias."),
    _f("status_sistema", "Relatório do estado do computador."),
    _f("executar_comando", "Executa um comando do Jarvis como o usuário falaria, por exemplo: 'abra o VS Code', "
       "'timer de 25 minutos', 'toque música lo-fi', 'modo sob demanda', 'notícias de tecnologia', "
       "'adicione café à lista de compras'. Para pedidos com várias etapas, faça uma chamada por etapa.",
       {"frase": {"type": "string"}}, ["frase"]),
]


class Comandos:
    """Executa os comandos. `rt` e o Runtime (camera, prefs, secretario...)."""

    def __init__(self, rt: Any, publicar_pagina: Callable[[dict], None]) -> None:
        self.rt = rt
        self._pagina = publicar_pagina           # comandos que so a tela sabe fazer
        self.ultima_lista: list[dict[str, Any]] = []   # ultimas noticias lidas ("abra a segunda")
        self.ultima_lista_em = 0.0                     # quando foram lidas (a referencia expira)
        self._piadas: list[str] = []
        self._limpeza_memoria_ate = 0.0                 # "apague toda a memoria" espera confirmacao
        self._pendente: tuple[str, float] | None = None # bloquear/suspender depois do descanso
        self._trava_cadastro = threading.Lock()
        self._cadastro_cancelado = threading.Event()
        self._ultima_evidencia: dict[str, Any] | None = None

    def interpretar(self, texto: str) -> tuple[str, dict[str, str]] | None:
        """Frases das rotinas (configuraveis) primeiro; depois as regras fixas."""
        from .rotinas import frase_da_rotina
        try:
            rotina = frase_da_rotina(texto, self.rt.prefs.ler())
        except AttributeError:
            rotina = None
        if rotina:
            return f"rotina_{rotina}", {}
        # apelido que o Senhor mesmo ensinou vem primeiro (§17)
        try:
            apelido = self._correcoes().aplicar(texto)
        except Exception:  # noqa: BLE001 - sem correcoes, segue o caminho normal
            apelido = None
        if apelido is not None:
            achado = interpretar(apelido.faca)
            if achado:
                self._correcoes().salvar()                  # guarda a contagem de usos
                return achado[0], dict(achado[1], _frase=apelido.faca)
        from .contexto import continuar
        completa = continuar(texto, self._ultimo, time.time())
        if completa:                                     # "e em Londres?" -> "que horas são em Londres"
            achado = self.interpretar(completa)
            if achado:
                return achado[0], dict(achado[1], _frase=completa)
        fixo = interpretar(texto)
        if fixo and fixo[0] in AUTOMACAO:               # "crie o protocolo X: quanto é 2 mais 2, ..." e
            return fixo                                 # "às 7h ...": o horario/protocolo manda, nao a conta
        from .utilidades import detectar
        util = detectar(sem_chamado(texto))            # contas, conversoes, datas, sorte: na hora
        if util:
            return util
        if fixo:
            # "abra a segunda" logo depois de ler as manchetes e a SEGUNDA NOTICIA,
            # nao um programa chamado "segunda" (§4: contexto compartilhado)
            if fixo[0] == "app" and self.ultima_lista and time.time() - self.ultima_lista_em < 600:
                alvo = normalizar(fixo[1].get("app", ""))
                from .noticias import ORDINAIS
                ordinais = {normalizar(o) for o in ORDINAIS} | {"ultima"}
                if alvo in ordinais or alvo.isdigit():
                    return "noticia_abrir", {"ord": alvo}
            return fixo
        # nada casou: tenta as variantes da fala ("memore o meu rosto" -> "memorize...").
        # A correcao so vale se a frase corrigida casar com uma regra de verdade.
        from .fala_variantes import corrigir
        alt = corrigir(texto)
        if alt != texto:
            achado = interpretar(alt)
            if achado:
                return achado[0], dict(achado[1], _frase=alt)
        return None

    def _rotinas(self) -> Any:
        from .rotinas import Rotinas
        return self._servico("rotinas", lambda: Rotinas(self.rt, achar_app))

    _profundidade = 0                       # protocolo executando protocolo
    _ultimo: tuple[str, str, float] | None = None   # ultimo comando (para "e em Londres?")

    def _servico(self, nome: str, fabrica: Callable[[], Any]) -> Any:
        s = getattr(self.rt, nome, None)
        if s is None:
            s = fabrica()
            setattr(self.rt, nome, s)
        return s

    def _contexto(self, cartao: dict[str, Any]) -> None:
        """Cartao de contexto na tela (lista de noticias, fontes, cotacoes)."""
        try:
            self.rt.estado.atualizar("contexto", tipo=cartao.get("tipo"), titulo=cartao.get("titulo"),
                                     itens=cartao.get("itens", [])[:8], em=time.time())
        except (AttributeError, KeyError):
            pass

    # ---- utilitarios ------------------------------------------------------
    def _trat(self) -> str:
        return self.rt.prefs.ler().get("nome_usuario") or "Senhor"

    def _tel(self) -> dict[str, Any]:
        return self.rt.estado.telemetria or {}

    def _abrir_url(self, url: str) -> None:
        import os
        if not url.startswith("https://"):
            raise ValueError("só abro endereços https")
        os.startfile(url)

    # ---- execucao ---------------------------------------------------------
    def executar(self, nome: str, args: dict[str, str], original: str) -> str | None:
        """Devolve a frase a falar (None = nao era comando de fato)."""
        if "_frase" in args:                             # continuacao: a frase completa reconstruida
            args = dict(args)
            original = args.pop("_frase")
        if nome == "raciocinio":
            return None                                  # vai ao modelo, com tarefas/lembretes/agenda (contexto_para_modelo)
        if nome == "repetir":
            return (self.rt.estado.ler("conversa") or {}).get("ultima_resposta") or f"Ainda não disse nada, {self._trat()}."
        if nome not in ("parar_fala",):
            self._ultimo = (nome, original, time.time())
        t = self._trat()
        from . import janelas, midia
        if nome == "parar_fala":
            self.rt.conversa.interromper()
            return ""                        # nada a falar: so silencio
        if nome in ("voz_desativar", "voz_ativar"):
            muda = nome == "voz_desativar"
            self.rt.prefs.aplicar({"voz_muda": muda})
            self.rt._publicar_prefs()
            return "Voz desativada. Respondo só por escrito." if muda else f"Voz reativada, {t}."
        if nome == "presenca":
            return f"Para o senhor, sempre."
        if nome == "obrigado":
            return f"Às ordens, {t}."
        if nome == "cumprimento":
            return f"Olá, {t}. Às suas ordens."
        if nome == "despedida":
            fechar = getattr(self.rt.conversa, "encerrar_conversa", None)
            if fechar:
                fechar()
            return f"Até logo, {t}. Estarei aqui."
        if nome == "como_voce_esta":
            return self.como_estou()
        if nome == "quem_e_voce":
            return self.apresentacao(original)
        if nome == "piada":
            return self.piada()
        if nome == "cotacao":
            return self.falar_cotacao(original)
        if nome == "noticia_abrir":
            return self.abrir_noticia(args)
        if nome == "saber":
            q = args.get("q", "")
            if re.search(r"\bou\b|\bvoce acha\b|\bdevo\b|\bmelhor\b", normalizar(q)):
                return None                  # opiniao/comparacao: o modelo responde
            return self.pesquisar_com_fontes(self._consulta(original, r"(?:voce sabe |sabe |me diga |me diz )?(?:quem (?:é|e|foi|era|foram)|o que (?:é|e|foi|são|sao|significa)|o que quer dizer|me (?:fal\w*|cont\w*|expliq\w*) (?:sobre|quem (?:é|e|foi)|o que (?:é|e|foi))|fal\w* (?:me )?sobre)", r"\?+$"))
        if nome == "briefing":
            return self.briefing()
        if nome == "pesquisa_detalhada":
            q = grupo_original(original, dict(REGRAS)[nome], "q") or args.get("q", "")
            return self.pesquisar_em_detalhes(q)
        if nome == "reuniao_preparar":
            return self.preparar_reuniao(original)
        if nome == "capacidades":
            return self.armadura()
        if nome == "modo_foco":
            ligado = not args.get("acao", "").startswith(("desativ", "deslig", "sai"))
            self.rt.prefs.aplicar({"modo_foco": ligado})
            self.rt._publicar_prefs()
            return ("Modo foco ativado. Avisos espontâneos ficam no painel; seus lembretes e timers continuam conforme configurados."
                    if ligado else "Modo foco desativado. Os avisos voltam a seguir o canal e o horário configurados.")
        if nome == "avisos_canal":
            canal = "voz" if args.get("canal") in ("por voz", "falados") else "painel"
            self.rt.prefs.aplicar({"avisos_canal": canal})
            self.rt._publicar_prefs()
            return "Avisos somente no painel." if canal == "painel" else "Avisos por voz, respeitando foco e horário de silêncio."
        if nome == "visao":
            frase = sem_chamado(original)
            # pergunta de IDENTIDADE ("que celular e esse?", "qual a marca?") segue a
            # sequencia do §8, com evidencia por atributo; o resto continua na descricao
            if re.search(r"\b(?:marca|modelo|fabricante|qual (?:e |eh )?(?:o|a)|que (?:celular|carro|aparelho"
                         r"|produto|impressora|notebook|fone|carregador|livro|componente)|identifi\w*"
                         r"|reconhe\w*)\b", normalizar(frase)):
                try:
                    sel = getattr(self.rt, "selecao", None)
                    alvo = sel.atual() if sel else None
                    caixa, categoria = None, None
                    detector = getattr(self.rt, "visao_continua", None)
                    rastreador = getattr(detector, "rastreador", None)
                    agora = time.time()
                    objetos = [obj for obj in rastreador.ativos() if 0 <= agora - obj.visto_em < 2] if rastreador else []
                    if alvo and alvo.tipo in ("objeto", "regiao") and alvo.extra.get("fonte") == "camera":
                        if alvo.tipo == "objeto":
                            trilha = rastreador.obter(alvo.id) if rastreador else None
                            if trilha is None or trilha not in objetos:
                                return "Perdi a continuidade do objeto selecionado. Selecione novamente o alvo atual na câmera."
                            caixa, categoria = trilha.caixa, trilha.nome
                        else:
                            # Região é uma área fixa autorizada; nunca a caixa de uma tela 3D.
                            caixa = alvo.extra.get("caixa")
                            if caixa is None:
                                return "A região da câmera não tem uma caixa válida. Selecione a área novamente."
                    if caixa is None and len(objetos) > 1:
                        return "Há mais de um objeto visível. Selecione o alvo no painel ou mostre somente o objeto desejado."
                    if caixa is None and len(objetos) == 1:
                        caixa, categoria = objetos[0].caixa, objetos[0].nome
                    if isinstance(caixa, dict):
                        caixa = tuple(caixa[k] for k in ("x", "y", "w", "h"))
                    dito, _cartao = self.rt.visao.identificar(frase, inventario=self._inventario(),
                                                            caixa=caixa, categoria=categoria)
                    return dito
                except (OSError, ValueError, RuntimeError) as e:
                    self.rt.estado.registrar("visao", f"identificação falhou: {e}", "erro")
                    return f"Não consegui olhar agora, {self._trat()}: {e}."
            return self.rt.visao.analisar(frase)
        if nome.startswith("percepcao_"):
            return self.perceber(nome, args, original)
        if nome == "olhar_auto":
            if args.get("regiao"):
                regiao = "inteira" if args["regiao"] in ("inteira", "tudo") else args["regiao"]
                self.rt.prefs.aplicar({"visao_regiao": regiao})
                self.rt._publicar_prefs()
                return f"Região de visão: {regiao}."
            ligar = not args.get("acao", "").startswith(("desativ", "deslig"))
            self.rt.prefs.aplicar({"visao_automatica": ligar})
            self.rt._publicar_prefs()
            if not ligar:
                return "Olhar automático desligado."
            if not self.rt.camera.ativa:
                self.rt.camera.ativar()
            return (f"Olhar automático ligado, {t}. Mostre o objeto na região marcada e segure um instante; "
                    "a análise leva uns 25 segundos neste computador.")
        if nome == "tema":
            tema = "classico" if args.get("tema") in ("classico", "original", "antigo") else "hud"
            self.rt.prefs.aplicar({"tema": tema})
            self.rt._publicar_prefs()
            return "Tema clássico." if tema == "classico" else f"De volta ao HUD, {t}."
        if nome == "tela":
            return self.rt.visao.analisar_tela(sem_chamado(original))
        if nome == "documento":
            return self.resumir_documento(original)
        if nome == "varredura" or nome.startswith("quarentena_"):
            return self.varrer(nome, original)
        if nome == "midia":
            return self.analisar_midia(original)
        if nome == "camera_ligar":
            self.rt.camera.ativar()
            return f"Câmera ligada, {t}."
        if nome == "camera_desligar":
            gestos = getattr(self.rt, "gestos", None)
            if gestos is not None:
                gestos.desativar("câmera desligada pelo usuário")
            self.rt.camera.desativar()
            return f"Câmera desligada, {t}."
        if nome in ("capacete_ligar", "capacete_desligar"):
            ligar = nome == "capacete_ligar"
            if ligar and not self.rt.camera.ativa:
                self.rt.camera.ativar()
            self._pagina({"acao": "capacete", "ligado": ligar})
            return f"Visão do capacete {'ativada' if ligar else 'encerrada'}, {t}."
        if nome in ("rosto_ocultar", "rosto_mostrar"):
            self.rt.prefs.aplicar({"capacete_imagem": nome == "rosto_mostrar"})
            self.rt._publicar_prefs()
            return "Imagem da câmera de volta." if nome == "rosto_mostrar" else "Rosto oculto. Modo holográfico."
        if nome == "tela_cheia":
            ok = janelas.tela_cheia("jarvis")
            return f"Tela cheia, {t}." if ok else "Não achei a janela do Jarvis para pôr em tela cheia."
        if nome == "microfone_desligar":
            self.rt.microfone.desativar()
            self.rt.estado.registrar("controle", "microfone desligado por voz")
            return "Microfone desligado. Para voltar, use o botão Microfone."
        if nome == "janela":
            alvo = "chat" if args.get("j", "").startswith(("chat", "conversa")) else "painel"
            janelas.abrir(alvo, self.rt.porta)
            return f"Abrindo o {alvo}, {t}."
        if nome == "youtube_tocar":
            q = self._consulta(original, r"(?:toqu\w*|toca|tocar|coloqu\w*|poe|põe|bota|ponha)", r"\s+no youtube.*$")
            return self.tocar(q, "youtube")
        if nome == "tocar":
            q = grupo_original(original, dict(REGRAS)["tocar"], "q") or args.get("q", "")
            return self.tocar(q, args.get("onde") or "youtube")
        if nome == "utilidade":
            return args["resposta"]
        if nome == "conversao":
            from .cotacoes import Cotacoes
            from .utilidades import converter
            return converter(sem_chamado(original), self._servico("cotacoes", Cotacoes)) or "Não entendi a conversão."
        if nome in ("hora_mundo", "clima_mundo"):
            return self.mundo(nome, original)
        if nome.startswith("lista_"):
            return self.listar(nome, args, original)
        if nome == "pesquisar":
            q = self._consulta(original, r"(?:pesquis\w*|procur\w*|busc\w*|busqu\w*|googl\w*)(?:\s+no\s+(?:google|youtube|navegador))?(?:\s+(?:por|sobre|a))?", r"\s+no (?:google|youtube|navegador)\s*$")
            n = normalizar(original)
            if args.get("onde") == "youtube" or re.search(r"no youtube", n):
                self._abrir_url("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": q}))
                return f"Pesquisando {q} no YouTube."
            if args.get("onde") == "google" or re.search(r"\bno (?:google|navegador)\b|\babr\w* (?:uma )?pesquisa\b", n):
                self._abrir_url("https://www.google.com/search?" + urllib.parse.urlencode({"q": q}))
                return f"Pesquisando {q}, {t}."
            if re.match(r"(?:as |umas )?(?:ultimas )?(?:noticias|manchetes)\b", normalizar(q)):
                return self.falar_noticias(q)
            return self.pesquisar_com_fontes(q)
        if nome.startswith("musica_"):
            acao = {"musica_pausar": "tocar_pausar", "musica_tocar": "tocar_pausar",
                    "musica_proxima": "proxima", "musica_anterior": "anterior"}[nome]
            m = midia.estado_midia()
            if m.get("status") != "medido" or not m.get("titulo"):
                return "Não há nenhuma música aberta para controlar."
            tocando = m.get("situacao") == "tocando"
            if (nome == "musica_pausar" and not tocando) or (nome == "musica_tocar" and tocando):
                return "Já está assim, " + t + "."
            midia.controlar(acao)
            return {"tocar_pausar": "Pausado." if tocando else "Tocando.", "proxima": "Próxima faixa.",
                    "anterior": "Faixa anterior."}[acao]
        if nome.startswith("volume_"):
            v = midia.volume_sistema()
            atual = v.get("volume", 0.5) if v.get("status") == "medido" else 0.5
            if nome == "volume_mutar":
                midia.definir_volume(None, True)
                return "Som desligado."
            if nome == "volume_desmutar":
                midia.definir_volume(None, False)
                return "Som de volta."
            if nome == "volume_definir":
                novo = max(0, min(100, int(args.get("n", "50")))) / 100
            else:
                novo = max(0.0, min(1.0, atual + (0.15 if nome == "volume_aumentar" else -0.15)))
            midia.definir_volume(novo, False)
            return f"Volume em {round(novo * 100)} por cento."
        if nome == "site":
            s = args.get("s", "").replace("-", "")
            if s in ("spotify", "whatsapp", "netflix"):          # prefere o app instalado
                achado = achar_app(s)
                if achado:
                    self._abrir_app(achado[1])
                    return f"Abrindo {s}, {t}."
            url = SITES.get(s) or SITES.get(s.rstrip("s"))
            if not url:
                return None
            self._abrir_url(url)
            return f"Abrindo {s}, {t}."
        if nome == "app":
            pedido = args.get("app", "")
            if normalizar(pedido) in _WINDOWS and not achar_app(pedido):
                import os
                os.startfile(_WINDOWS[normalizar(pedido)])
                return f"Abrindo {pedido}, {t}."
            achado = achar_app(pedido)
            if not achado:
                return None                  # deixa o modelo tentar entender
            self._abrir_app(achado[1])
            return f"Abrindo {achado[0]}, {t}."
        if nome in ("agenda_conflitos", "agenda_livres"):
            from .agenda_analise import fala_conflitos, fala_livres
            agora = datetime.now()
            amanha = bool(re.search(r"\bamanha\b", normalizar(original)))
            dia, rotulo = (agora + timedelta(days=1), "amanhã") if amanha else (agora, "hoje")
            ag = self._tel().get("agenda") or {"status": "erro"}
            return (fala_conflitos(ag, dia, rotulo) if nome == "agenda_conflitos"
                    else fala_livres(ag, dia, rotulo, agora=agora))
        if nome == "rotina_chegada":
            vigia = getattr(self.rt, "vigia_desligar", None)
            aviso = "Modo vigia desativado. " if vigia and vigia() else ""
            return aviso + self._rotinas().chegada()
        if nome == "vigia_ligar":
            erro = self.rt.vigia_ligar()
            return erro or (f"Modo vigia armado em 20 segundos, {self._trat()}. Se alguém aparecer na câmera, "
                            "aviso aqui e no Windows. Não identifico quem é e nada é gravado.")
        if nome == "vigia_desligar":
            return "Modo vigia desativado." if self.rt.vigia_desligar() else "O modo vigia já estava desligado."
        if nome == "rotina_descanso":
            fala, acao = self._rotinas().descanso()
            self._pendente = (acao, time.time() + 90) if acao else None
            return fala
        if nome == "confirmar_acao":
            from . import rotinas
            acao = args.get("acao")
            pend = self._pendente
            if not pend or pend[0] != acao or time.time() > pend[1]:
                return f"Não havia pedido para {acao}. Diga primeiro: Jarvis, vou descansar."
            self._pendente = None
            ok = rotinas.bloquear() if acao == "bloquear" else rotinas.suspender()
            return ("Bloqueando." if acao == "bloquear" else "Suspendendo.") if ok else f"O Windows não deixou {acao}."
        if nome.startswith("memoria_"):
            return self.memoria(nome, original)
        if nome == "modo_proativo" or nome.startswith("monitor"):
            return self.monitorar(nome, args, original)
        if nome == "lembretes_cancelar":
            return self.cancelar_lembretes(original)
        if nome == "lembretes_listar":
            return self.falar_lembretes()
        if nome == "lembrete_adiar":
            return self.adiar_lembrete(original, args)
        if nome == "lembrete_remarcar":
            return self.remarcar_lembrete(original)
        if nome == "timer":
            from .secretario import falar_quando, interpretar_quando
            quando, _ = interpretar_quando(original)
            if not quando:
                return "De quanto tempo, " + t + "? Por exemplo: timer de 5 minutos."
            n = normalizar(original)
            tipo = "alarme" if re.search(r"\b(?:alarme|despertador)\b", n) else "timer"
            self.rt.secretario.lembrar("Alarme" if tipo == "alarme" else "Tempo esgotado", quando, tipo)
            return f"{'Alarme' if tipo == 'alarme' else 'Timer'} marcado para {falar_quando(quando)}."
        if nome == "lembrete":
            from .secretario import falar_repeticao
            item = self.rt.secretario.lembrar_por_frase(original)
            if not item:
                return f"Para quando, {t}? Diga, por exemplo: me lembre de ligar para o Pedro às 15h."
            frase = f"Certo. Vou lembrar {falar_repeticao(item)}: {item['texto']}."
            # o lembrete cai em cima de um compromisso REAL da agenda? aviso (F05)
            try:
                from .discordancia import conflito_de_horario
                ag = (self._tel().get("agenda") or {})
                if ag.get("status") == "medido":
                    choque = conflito_de_horario(item["quando"], ag.get("eventos") or [])
                    if choque:
                        frase += f" Atenção: {choque.falado()}."
            except Exception:  # noqa: BLE001 - conferir a agenda e bonus, nao pode perder o lembrete
                pass
            return frase
        if nome == "notas_listar":
            notas = self.rt.secretario.notas()
            if not notas:
                return "Você não tem notas."
            return f"Suas últimas notas: " + "; ".join(n["texto"] for n in notas[:5]) + "."
        if nome == "nota":
            texto = texto_depois_do_verbo(original, r"anot|tom[ae] nota|registr|salv\w* (?:uma )?nota")
            if len(texto) < 2:
                return "O que devo anotar?"
            self.rt.secretario.anotar(texto)
            return "Anotado."
        if nome == "noticias":
            return self.falar_noticias(original)
        if nome == "planilha":
            import os
            from .planilhas import criar, fala
            r = criar(sem_chamado(original))
            os.startfile(r["arquivo"])                    # .xlsx sem macros: abre no Excel
            self._contexto({"tipo": "arquivo", "titulo": f"Planilha · {r['titulo']}",
                            "itens": [{"titulo": nome_arquivo(r["arquivo"]), "detalhe": ", ".join(r["colunas"]),
                                       "fonte": "Documentos\\Jarvis\\Planilhas"}]})
            return fala(r)
        if nome == "programa":
            return self.criar_programa(sem_chamado(original))
        if nome == "rascunho":
            return self.criar_rascunho(sem_chamado(original))
        if nome == "rascunho_gmail":
            from .rascunhos import url_gmail
            r = getattr(self._servico("rascunhos", lambda: None), "ultimo", None)
            if not r:
                return "Ainda não fiz nenhum rascunho. Diga, por exemplo: escreva um e-mail para o Pedro dizendo que vou atrasar."
            self._abrir_url(url_gmail(r))
            return f"Abri o Gmail com o rascunho preenchido, {t}. Revise e envie o senhor mesmo."
        if nome == "emails":
            return self.falar_emails()
        if nome.startswith("canais_"):
            return self.canais(nome, original)
        if nome.startswith("corrigir_"):
            return self.corrigir(nome, original)
        if nome.startswith("cena_"):
            return self.cena(nome, original)
        if nome == "ocorrencias":
            return self.ocorrencias(original)
        if nome.startswith("doc_"):
            return self.documento(nome, args, original)
        if nome.startswith("inv_"):
            return self.inventario(nome, args, original)
        if nome.startswith("montagem_"):
            return self.montagem(nome, original)
        if nome.startswith("peca_"):
            return self.peca(nome, args, original)
        if nome.startswith("projeto_"):
            return self.projeto(nome, args, original)
        if nome.startswith("id_"):
            return self.identidade(nome, args, original)
        if nome.startswith("casa_"):
            return self.casa(nome, args, original)
        if nome in ("whatsapp", "celular_avisar"):
            return self.comunicar(nome, original)
        if nome in ("projetar", "cura_abrir", "engenharia", "tarifa", "dados_analisar"):
            return self.engenharia(nome, original)
        if nome.startswith("holograma_") or nome.startswith("modelo_") or nome == "grafico":
            return self.holograma(nome, original)
        if nome in ("regua_calibrar", "medir"):
            return self.regua(nome, original)
        if nome == "armadura":
            return self.armadura()
        if nome == "consumo":
            return self.consumo(original)
        if nome == "agendar":
            return self.agendar(original)
        if nome.startswith("protocolo_"):
            return self.protocolo(nome, args, original)
        if nome == "status":
            return self.status()
        return None

    def _abrir_app(self, app_id: str) -> None:
        import os
        os.startfile(f"shell:AppsFolder\\{app_id}")

    def _consulta(self, original: str, verbo: str, fim: str) -> str:
        t = sem_chamado(original)
        t = re.sub(rf"^\W*{verbo}\s+", "", t, flags=re.I)
        t = re.sub(fim, "", t, flags=re.I)
        return t.strip(" .!?") or t

    # ---- ferramentas (modelo) ---------------------------------------------
    def executar_ferramenta(self, nome: str, a: dict[str, Any]) -> str:
        from .execucao_modelo import validar_argumentos
        erro = validar_argumentos(nome, a, FERRAMENTAS)
        if erro:
            return f"Não executei: {erro}."
        from . import janelas, midia
        t = self._trat()
        if nome == "ligar_camera":
            return self.executar("camera_ligar" if a.get("ligada", True) else "camera_desligar", {}, "")
        if nome == "modo_capacete":
            return self.executar("capacete_ligar" if a.get("ligado", True) else "capacete_desligar", {}, "")
        if nome == "olhar_camera":
            return self.rt.visao.analisar(a.get("pergunta"))
        if nome == "abrir_janela":
            alvo = a.get("nome") if a.get("nome") in ("painel", "chat", "jarvis") else "painel"
            janelas.abrir(alvo, self.rt.porta)
            return f"Abrindo o {alvo}, {t}."
        if nome == "controlar_musica":
            acao = a.get("acao") if a.get("acao") in ("tocar_pausar", "proxima", "anterior") else "tocar_pausar"
            midia.controlar(acao)
            return "Feito."
        if nome == "volume":
            if isinstance(a.get("mudo"), bool):
                midia.definir_volume(None, a["mudo"])
                return "Som desligado." if a["mudo"] else "Som de volta."
            v = midia.volume_sistema()
            atual = v.get("volume", 0.5) if v.get("status") == "medido" else 0.5
            if isinstance(a.get("percentual"), int):
                novo = max(0, min(100, a["percentual"])) / 100
            else:
                novo = max(0.0, min(1.0, atual + (0.15 if a.get("ajuste") != "diminuir" else -0.15)))
            midia.definir_volume(novo, False)
            return f"Volume em {round(novo * 100)} por cento."
        if nome == "abrir_site":
            url = SITES.get(str(a.get("site", "")).lower())
            if not url:
                return "Esse site não está na minha lista."
            self._abrir_url(url)
            return f"Abrindo {a['site']}."
        if nome == "abrir_programa":
            achado = achar_app(str(a.get("nome", "")))
            if not achado:
                return f"Não encontrei {a.get('nome')} no menu Iniciar."
            self._abrir_app(achado[1])
            return f"Abrindo {achado[0]}."
        if nome == "pesquisar":
            q = str(a.get("consulta", "")).strip()[:200]
            if not q:
                return "O que devo pesquisar?"
            if a.get("onde") not in ("google", "youtube"):
                return self.pesquisar_com_fontes(q)
            base = ("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": q})
                    if a.get("onde") == "youtube" else "https://www.google.com/search?" + urllib.parse.urlencode({"q": q}))
            self._abrir_url(base)
            return f"Pesquisando {q}."
        if nome == "cotacao":
            return self.falar_cotacao("cotação " + str(a.get("ativos", "")))
        if nome == "criar_lembrete":
            from .secretario import falar_quando
            agora = datetime.now()
            quando = None
            if isinstance(a.get("em_minutos"), int) and a["em_minutos"] > 0:
                quando = agora + timedelta(minutes=a["em_minutos"])
            elif re.fullmatch(r"\d{1,2}:\d{2}", str(a.get("horario", ""))):
                h, m = map(int, a["horario"].split(":"))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    quando = agora.replace(hour=h, minute=m, second=0, microsecond=0)
                    if a.get("amanha") or quando <= agora:
                        quando += timedelta(days=1)
            if not quando:
                return "Para quando é o lembrete?"
            repetir = a.get("repetir") if a.get("repetir") in ("diario", "dias_uteis", "semanal") else None
            if repetir:
                from .secretario import proxima_ocorrencia
                quando = proxima_ocorrencia(quando, repetir, None, agora)
            item = self.rt.secretario.lembrar(str(a.get("texto") or "lembrete"), quando, repetir=repetir)
            from .secretario import falar_repeticao
            return f"Certo. Vou lembrar {falar_repeticao(item)}: {item['texto']}."
        if nome == "anotar":
            self.rt.secretario.anotar(str(a.get("texto", "")))
            return "Anotado."
        if nome == "noticias":
            tema = str(a.get("tema") or "").strip()[:100]
            return self.falar_noticias(f"notícias sobre {tema}" if tema else "notícias")
        if nome == "resumo_do_dia":
            return self.briefing()
        if nome == "status_sistema":
            return self.status()
        if nome == "executar_comando":                     # plano do modelo: cada passo passa pelo filtro
            from .protocolos import PROIBIDOS
            frase = str(a.get("frase") or "").strip()[:200]
            achado = self.interpretar(frase) if frase else None
            if (achado is None or achado[0] in PROIBIDOS
                    or achado[0].startswith(("id_", "memoria_", "correcao_", "corrigir_"))
                    or achado[0] in ("projeto_continuar", "projeto_etapa_nao_executada")
                    or achado[0].endswith(("_confirmar", "_concluir", "_apagar", "_esquecer"))):
                return f"Não executei \"{frase}\": não é um comando que eu rode sozinho."
            return self.executar(achado[0], achado[1], frase) or "Não houve retorno verificável do comando."
        return "Não sei fazer isso ainda."

    # ---- falas compostas ----------------------------------------------------
    def falar_noticias(self, frase: str) -> str:
        """ "notícias" / "notícias de tecnologia" / "notícias sobre o Corinthians"."""
        from .noticias import NOMES_CATEGORIA, Noticias, detectar_categoria, manchetes_faladas
        svc = self._servico("noticias", Noticias)
        m = re.search(r"\b(?:not[ií]cias?|manchetes?|notici[aá]rio)\b\s*(?:(?:de|do|da|dos|das|sobre|a respeito de|acerca de|em|no|na)\s+)?(?P<tema>.*)$",
                      sem_chamado(frase), flags=re.I)
        tema = (m.group("tema") if m else "").strip(" .!?,")
        tema = re.sub(r"\s*(?:,?\s*por favor|pra mim|para mim|agora|de hoje|hoje|do dia)\s*$", "", tema, flags=re.I).strip(" .!?,")
        cat = detectar_categoria(tema) if tema else "geral"
        if not tema or cat == "geral":
            dados = self._tel().get("noticias") or svc.obter(self.rt.prefs.ler().get("noticias_fontes"))
            titulo = "As principais manchetes"
        elif cat:
            dados = svc.por_categoria(cat)
            titulo = {"mundo": "Manchetes do mundo", "geral": "Manchetes gerais"}.get(
                cat, f"Manchetes de {NOMES_CATEGORIA[cat]}")
        else:
            dados = svc.buscar(tema)
            titulo = f"Notícias sobre {tema}"
            if dados.get("status") == "medido" and not dados.get("itens"):
                return f"Não encontrei notícias recentes sobre {tema}."
        itens = (dados or {}).get("itens") or []
        if itens:
            self.ultima_lista, self.ultima_lista_em = itens[:10], time.time()
            self._contexto({"tipo": "noticias", "titulo": titulo, "itens": [
                {"titulo": x["titulo"], "fonte": x["fonte"], "link": x.get("link"), "em": x.get("em")} for x in itens[:8]]})
        fala = manchetes_faladas(dados, 3, numerar=True, titulo=titulo)
        if itens:
            fontes = [dict(x, cobertura="manchete", publicado_em=x.get("em"),
                           consultado_em=x.get("consultado_em", (dados or {}).get("em"))) for x in itens[:3]]
            self._registrar_fontes(fontes, fala)
        return fala

    def abrir_noticia(self, args: dict[str, str]) -> str:
        from .noticias import ORDINAIS
        ords = {normalizar(o): i for i, o in enumerate(ORDINAIS)}
        palavras = {"um": 0, "uma": 0, "dois": 1, "duas": 1, "tres": 2, "quatro": 3, "cinco": 4}
        lista = self.ultima_lista or (self._tel().get("noticias") or {}).get("itens") or []
        if not lista:
            return "Ainda não li nenhuma notícia. Diga: Jarvis, notícias."
        chave = args.get("ord") or args.get("num") or "primeira"
        if chave == "ultima":
            i = len(lista) - 1
        elif chave in ords:
            i = ords[chave]
        elif chave in palavras:
            i = palavras[chave]
        else:
            i = int(re.sub(r"\D", "", chave) or 1) - 1
        if not 0 <= i < len(lista):
            return f"Só tenho {len(lista)} notícias na lista."
        n = lista[i]
        link = (n.get("link") or "").replace("http://", "https://", 1)
        if not link.startswith("https://"):
            return "Essa notícia não tem link."
        self._abrir_url(link)
        self._registrar_fontes([dict(n, cobertura="manchete", publicado_em=n.get("em"))],
                               "Abrindo: {}, {}.".format(n["fonte"], n["titulo"].rstrip(".")))
        selecao = getattr(self.rt, "selecao", None)
        if selecao is not None:
            selecao.selecionar("noticia", f"noticia-{i + 1}", n["titulo"], por="voz",
                               indice=i, lista_em=self.ultima_lista_em)
        return f"Abrindo: {n['fonte']}, {n['titulo'].rstrip('.')}."

    def falar_cotacao(self, frase: str) -> str:
        from .cotacoes import Cotacoes, ativos_citados, cartao, cotacao_falada
        ativos = ativos_citados(frase)
        if not ativos:
            ativos = ([("cripto", "bitcoin"), ("cripto", "ethereum"), ("cripto", "solana")]
                      if "cripto" in normalizar(frase) else [("moeda", "USD"), ("moeda", "EUR"), ("cripto", "bitcoin")])
        r = self._servico("cotacoes", Cotacoes).consultar(ativos[:4])
        if r.get("status") == "medido":
            self._contexto(cartao(r))
        return cotacao_falada(r)

    def pesquisar_com_fontes(self, consulta: str) -> str:
        from .noticias import Noticias
        from .pesquisa import Pesquisa, cartao
        svc = self._servico("pesquisa", lambda: Pesquisa(self._servico("noticias", Noticias)))
        r = svc.responder(consulta)
        if r["status"] == "medido":
            self._contexto(cartao(r))
            fala = r["fala"] + " Fontes na tela."
            self._registrar_fontes(r["fontes"], fala)
            return fala
        if r["status"] == "sem_fontes" and r.get("consulta"):
            self._abrir_url("https://www.google.com/search?" + urllib.parse.urlencode({"q": r["consulta"]}))
            return r["fala"] + " Abri a busca no navegador."
        return r["fala"]

    def pesquisar_em_detalhes(self, consulta: str) -> str:
        from .noticias import Noticias
        from .pesquisa import Pesquisa, cartao
        svc = self._servico("pesquisa", lambda: Pesquisa(self._servico("noticias", Noticias)))
        conversa = getattr(self.rt, "conversa", None)
        cancelamento = getattr(conversa, "_cancelado", None)
        r = svc.investigar(consulta, cancelado=cancelamento.is_set if cancelamento is not None else None)
        c = cartao(r)
        self.rt.estado.atualizar("contexto", **c, em=r["em"])
        self.rt.estado.atualizar("conversa", pesquisa=r)
        self._registrar_fontes(r["fontes"], r["fala"])
        return r["fala"]

    def _registrar_fontes(self, fontes: list[dict], resposta: str) -> None:
        import copy
        self._ultima_evidencia = {"fontes": copy.deepcopy(fontes), "resposta": resposta, "em": time.time()}
        self.rt.estado.atualizar("conversa", evidencias_ultima_resposta=self._ultima_evidencia)

    def fonte_da_resposta(self, original: str) -> str | None:
        """Selecao explicita ou evidencia da ultima resposta, sem trocar pesquisa por manual antigo."""
        fontes = []
        selecao = getattr(self.rt, "selecao", None)
        alvo = selecao.atual() if selecao is not None else None
        if alvo is not None and alvo.tipo == "noticia" and alvo.extra.get("lista_em") == self.ultima_lista_em:
            indice = alvo.extra.get("indice")
            if isinstance(indice, int) and 0 <= indice < len(self.ultima_lista):
                n = self.ultima_lista[indice]
                fontes = [dict(n, cobertura="manchete", publicado_em=n.get("em"))]
        if not fontes and alvo is not None and alvo.tipo in ("documento", "trecho"):
            con = self._conhecimento()
            doc = next((d for d in con.todos() if d.id == alvo.id), None)
            if doc:
                fontes = [{"titulo": doc.nome, "fonte": doc.nome, "cobertura": "documento indexado",
                           "consultado_em": doc.indexado_em, "versao": doc.versao,
                           "desatualizado": doc.obsoleto or doc.mudou_no_disco()}]
        if not fontes:
            from .noticias import ORDINAIS
            n = normalizar(original)
            indice = next((i for i, o in enumerate(ORDINAIS) if re.search(rf"\b{normalizar(o)}\b", n)), None)
            if indice is not None and 0 <= indice < len(self.ultima_lista):
                noticia = self.ultima_lista[indice]
                fontes = [dict(noticia, cobertura="manchete", publicado_em=noticia.get("em"))]
        if not fontes and self._ultima_evidencia:
            try:
                ultima = (self.rt.estado.ler("conversa") or {}).get("ultima_resposta")
                sessao = (self.rt.estado.ler("pedido") or {}).get("sessao_id")
                if sessao and sessao != "voz-local":
                    historico = getattr(getattr(self.rt, "conversa", None), "_historico", [])
                    ultima = next((m.get("content") for m in reversed(historico) if m.get("role") == "assistant"), ultima)
            except (AttributeError, KeyError):
                ultima = None
            if ultima and ultima != self._ultima_evidencia["resposta"]:
                return "Não tenho uma fonte vinculada à última resposta. Indique qual notícia, pesquisa ou documento deseja conferir."
            fontes = self._ultima_evidencia["fontes"]
        if not fontes:
            return None
        self._contexto({"tipo": "fontes", "titulo": "Evidências da resposta ou seleção",
                        "itens": [{"titulo": f["titulo"], "fonte": f["fonte"], "link": f.get("link"),
                                   "detalhe": f"Cobertura: {f.get('cobertura', 'não informada')}. " +
                                   (f"Versão {f['versao']}. " if f.get("versao") else "") +
                                   ("Fonte desatualizada; precisa de nova consulta." if f.get("desatualizado") else ""),
                                   "em": f.get("consultado_em"), "publicado_em": f.get("publicado_em")}
                                  for f in fontes]})
        partes = []
        for f in fontes[:4]:
            quando = f.get("consultado_em")
            data = f", consultada em {datetime.fromtimestamp(quando):%d/%m às %H:%M}" if isinstance(quando, (int, float)) else ", horário da consulta não registrado"
            partes.append(f"{f['fonte']}: {f['titulo']} ({f.get('cobertura', 'cobertura não informada')}{data})")
        fala = "Usei estas evidências: " + "; ".join(partes) + ". Os links e limites estão no painel."
        if any(f.get("desatualizado") for f in fontes):
            fala += " Há fonte desatualizada; confira a versão antes de confiar no conteúdo atual."
        self._registrar_fontes(fontes, fala)
        return fala

    def como_estou(self) -> str:
        """Resposta honesta, a partir do que foi medido (sem "tudo no verde" falso)."""
        t = self._trat()
        problemas = []
        mem = (self._tel().get("sistema") or {}).get("memoria") or {}
        if mem.get("status") == "medido" and mem.get("uso_pct", 0) >= 90:
            problemas.append(f"a memória do computador está em {round(mem['uso_pct'])} por cento, "
                             "então posso demorar mais para responder")
        try:
            mic = (self.rt.estado.ler("microfone") or {}).get("estado")
            srv = ((self.rt.estado.instantaneo().get("conexao") or {}).get("servidor") or {}).get("estado")
        except (AttributeError, KeyError):
            mic = srv = None
        if mic == "bloqueado":
            problemas.append("o Windows está bloqueando o microfone")
        if srv not in (None, "ok"):
            problemas.append("o servidor do OpenJarvis não está respondendo")
        if not problemas:
            return f"Operacional e à disposição, {t}."
        return f"Funcionando, {t}, mas " + " e ".join(problemas) + "."

    def apresentacao(self, frase: str) -> str:
        n = normalizar(frase)
        if re.search(r"\bo que voce (?:faz|sabe fazer|consegue fazer|pode fazer)\b|\bcomandos\b|\bcomo voce funciona\b", n):
            return ("Posso dar o resumo do dia, ler notícias do Brasil e do mundo por assunto, dizer a hora e o "
                    "clima de qualquer cidade, cotações e conversões, fazer contas, datas e sorteios, cuidar das suas "
                    "listas, pesquisar citando as fontes, marcar lembretes, timers e notas, tocar a música que o senhor "
                    "pedir, abrir programas e sites e, com a câmera ligada, olhar um objeto e dizer o que é, descrever "
                    "o ambiente e dizer onde as coisas estão. Por exemplo: Jarvis, o que você está vendo?")
        if re.search(r"\bquem (?:te|lhe) (?:criou|fez|programou)\b", n):
            return ("Fui montado neste computador sobre o OpenJarvis, com modelos que rodam aqui mesmo, "
                    "e ajustado para trabalhar para o senhor.")
        return ("Sou o Jarvis, a inteligência artificial pessoal do senhor, rodando aqui neste computador. "
                "Ouço quando me chamam, enxergo pela câmera quando o senhor a liga, acompanho agenda, e-mails e "
                "notícias do mundo, respondo contas, conversões, hora e clima de qualquer lugar, cuido das listas "
                "e lembretes e controlo o computador por voz.")

    PIADAS = [
        "Existem 10 tipos de pessoas, Senhor: as que entendem binário e as que não entendem.",
        "Eu contaria uma piada sobre UDP, mas não tenho garantia de que o senhor a receberia.",
        "Há três problemas difíceis na computação: dar nome às coisas, invalidar cache e erros de um a mais.",
        "Um fóton chega ao hotel. O recepcionista pergunta se tem bagagem. Não, estou viajando leve.",
        "Por que o robô atravessou a rua? Estava programado para isso. Humor de máquina, perdoe-me.",
        "O senhor sabe qual é o café preferido de um programador? Java. Eu prefiro eletricidade.",
        "Uma consulta SQL entra num bar, vai até duas mesas e pergunta: posso me juntar a vocês?",
        "Pedi um tempo ao Wi-Fi. Ele respondeu com perda de pacotes.",
        "Por que o computador foi ao médico? Estava com vírus, e se recusou a reiniciar.",
        "Eu faria uma piada sobre recursão, mas eu faria uma piada sobre recursão.",
    ]

    def piada(self) -> str:
        if not self._piadas:                       # todas antes de repetir
            self._piadas = random.sample(self.PIADAS, len(self.PIADAS))
        return self._piadas.pop()

    def _varredura(self) -> Any:
        from .varredura import Varredura, classificador_nudenet, classificador_visao
        def fabrica():
            nudenet = classificador_nudenet()
            vr = Varredura(nudenet or classificador_visao(self.rt.visao.perguntar_imagem))
            vr.rapido = nudenet is not None
            return vr
        return self._servico("varredura", fabrica)

    def varrer(self, nome: str, original: str) -> str:
        import threading
        from .documentos import pasta_conhecida
        vr = self._varredura()
        t = self._trat()
        if nome == "varredura":
            if getattr(self, "_varrendo", False):
                return "Já estou verificando imagens; aviso quando terminar."
            n = normalizar(original)
            chave = next((k for k in ("downloads", "documentos", "area de trabalho", "imagens")
                          if k in n or (k == "imagens" and re.search(r"\bpasta (?:de )?(?:imagens|fotos)\b", n))), "downloads")
            pasta = pasta_conhecida(chave)
            from .varredura import imagens
            lista, total = imagens(pasta)
            if not lista:
                return f"Não há imagens em {pasta.name}."
            self._varrendo = True

            def rodar():
                try:
                    rel = vr.analisar(pasta)
                    fala = (f"{t}, terminei de verificar {rel['analisadas']} imagens em {pasta.name}: "
                            + (f"{rel['sinalizadas']} parecem sensíveis. Nada foi movido. Para mover para a quarentena, "
                               "diga: Jarvis, confirmo quarentena." if rel["sinalizadas"] else "nenhuma parece sensível."))
                    if rel.get("incertas"):
                        fala += f" {rel['incertas']} ficaram incertas; estão na tela para o senhor revisar, e não serão movidas."
                    self._contexto({"tipo": "varredura", "titulo": f"Varredura · {pasta.name}",
                                    "itens": [{"titulo": Path_(x["caminho"]).name, "detalhe": x["motivo"],
                                               "fonte": "sinalizada" if x["sensivel"] else "incerta: revisar"}
                                              for x in rel["itens"] if x.get("situacao") in ("sensivel", "incerto")][:8]
                                             or [{"titulo": "Nenhuma imagem sinalizada", "fonte": f"{rel['analisadas']} analisadas"}]})
                except Exception as e:  # noqa: BLE001
                    fala = f"{t}, a verificação de imagens falhou: {e}."
                finally:
                    self._varrendo = False
                anunciador = getattr(self.rt, "anunciador", None)
                if anunciador:
                    anunciador.anunciar(fala, pedido_pelo_usuario=True, validade_s=900)
            threading.Thread(target=rodar, name="varredura", daemon=True).start()
            mais = f" das {total}" if total > len(lista) else ""
            por_imagem = 1 if getattr(vr, "rapido", False) else 40   # NudeNet ~1 s; modelo de visao ~40 s
            minutos = max(1, round(len(lista) * por_imagem / 60))
            return (f"Verificando as {len(lista)} imagens mais recentes{mais} em {pasta.name}, aqui mesmo no computador; "
                    f"deve levar uns {minutos} minuto{'s' if minutos > 1 else ''}. "
                    "Não vou mover nada sem sua confirmação. Aviso quando terminar.")
        if nome == "quarentena_mover":
            rel = vr.ultimo_relatorio()
            if not rel or rel.get("movido") or not rel["sinalizadas"]:
                return "Não há imagens sinalizadas esperando decisão. Peça antes: verifique as imagens da pasta Downloads."
            return (f"Vou mover {rel['sinalizadas']} imagens para a quarentena. Nada é apagado e dá para restaurar. "
                    "Para confirmar, diga: Jarvis, confirmo quarentena.")
        if nome == "quarentena_confirmar":
            rel = vr.ultimo_relatorio()
            if not rel or rel.get("movido") or not rel["sinalizadas"]:
                return "Não há imagens sinalizadas para mover."
            r = vr.quarentenar(rel)
            pulo = f" {r['pulados']} mudaram desde a análise e ficaram onde estavam." if r["pulados"] else ""
            return f"{r['movidos']} imagens na quarentena.{pulo} Para desfazer, diga: restaure a quarentena."
        if nome == "quarentena_restaurar":
            r = vr.restaurar()
            if not r["restaurados"]:
                return "A quarentena está vazia."
            prob = f" Atenção: {'; '.join(r['problemas'][:2])}." if r["problemas"] else ""
            return f"{r['restaurados']} imagens devolvidas ao lugar de origem.{prob}"
        if nome == "quarentena_listar":
            itens = vr.em_quarentena()
            if not itens:
                return "A quarentena está vazia."
            self._contexto({"tipo": "quarentena", "titulo": f"Quarentena · {len(itens)}",
                            "itens": [{"titulo": Path_(e["origem"]).name, "fonte": Path_(e["origem"]).parent.name} for e in itens[:8]]})
            return f"Há {len(itens)} imagens na quarentena. Os nomes estão na tela."
        return None

    def _detector_pronto(self):
        """Visao em tempo real pronta para responder (liga a camera: o Senhor pediu para ver)."""
        v = getattr(self.rt, "visao_continua", None)
        if v is None or not v.detector.disponivel or not self.rt.prefs.ler().get("visao_tempo_real", True):
            return None
        if not self.rt.camera.ativa:
            self.rt.camera.ativar()
        return v

    def _detalhar(self) -> None:
        """Depois da resposta na hora, o modelo de visao olha os detalhes e fala sozinho."""
        try:
            r = self.rt.olhar_agora()
            if r:
                self.rt.anunciador.anunciar(self.rt.percepcao.descrever(r), pedido_pelo_usuario=True, validade_s=180)
        except Exception as e:  # noqa: BLE001 - a percepcao nunca derruba o runtime
            self.rt.estado.registrar("percepcao", f"falha ao detalhar: {e}", "aviso")

    # ---- automacao: protocolos e rotinas com horario ------------------------------------------
    def agendar(self, original: str) -> str:
        """ "todo dia às 7h me dê o resumo do dia": na hora, EXECUTA o comando (se permitido).
        Se o que vem depois do horario nao e comando que eu rode sozinho, vira lembrete comum."""
        from .protocolos import PROIBIDOS
        from .secretario import falar_repeticao, limpar_texto_lembrete
        t = self._trat()
        acao = (grupo_original(original, dict(REGRAS)["agendar"], "acao") or "").strip(" .,")
        quando, regra, _ = self.rt.secretario.quando_da_frase(sem_chamado(original))
        if not quando:
            return f"A que horas, {t}? Por exemplo: todo dia às 7h me dê o resumo do dia."
        alvo = self.interpretar(acao)
        if alvo is None or alvo[0] in PROIBIDOS or alvo[0] in ("lembrete", "timer"):
            item = self.rt.secretario.lembrar(limpar_texto_lembrete(acao) or acao, quando, repetir=regra)
            return f"Certo. Vou lembrar {falar_repeticao(item)}: {item['texto']}."
        item = self.rt.secretario.lembrar(acao, quando, tipo="rotina", repetir=regra, comando=acao)
        return f"Combinado, {t}. {falar_repeticao(item)[0].upper() + falar_repeticao(item)[1:]} eu executo: {acao}."

    def protocolo(self, nome: str, args: dict[str, str], original: str) -> str:
        from .listas import juntar
        from .protocolos import PROIBIDOS, Protocolos, nome_protocolo, separar_passos, validar_passos
        pr = self._servico("protocolos", Protocolos)
        regra = dict(REGRAS)[nome]
        if nome == "protocolo_listar":
            nomes = pr.nomes()
            return (f"Seus protocolos: {juntar(nomes)}." if nomes else
                    "O senhor ainda não tem protocolos. Diga, por exemplo: crie o protocolo trabalho: "
                    "abra o VS Code e me dê as notícias de tecnologia.")
        alvo = grupo_original(original, regra, "nome") or grupo_original(original, regra, "nome2") or ""
        rotulo = nome_protocolo(alvo)
        if nome == "protocolo_criar":
            passos, erro = validar_passos(separar_passos(grupo_original(original, regra, "passos") or ""), self.interpretar)
            if erro:
                return erro
            pr.salvar(alvo, passos)
            return (f"Protocolo {rotulo} criado com {len(passos)} passo{'s' if len(passos) > 1 else ''}: "
                    + "; ".join(passos) + f". Para usar: execute o protocolo {rotulo}.")
        if nome == "protocolo_apagar":
            return f"Protocolo {rotulo} apagado." if pr.apagar(alvo) else f"Não achei o protocolo {rotulo}."
        passos = pr.passos(alvo)
        if passos is None:
            nomes = pr.nomes()
            return f"Não achei o protocolo {rotulo}." + (f" Tenho: {juntar(nomes)}." if nomes else "")
        from .projetos import resumo_falado
        pedido = self.rt.estado.ler("pedido") or {}
        ativo = getattr(getattr(self.rt, "entrada", None), "ativo", None)
        if ativo:
            pedido = dict(pedido, sessao_id=ativo[0], pedido_id=ativo[1])
        try:
            from .protocolos import ler_parametros
            parametros = ler_parametros(grupo_original(original, regra, "parametros") or "")
            tarefa = pr.executar(alvo, self._projetos(), self.interpretar, self.executar,
                                 sessao_id=pedido.get("sessao_id", ""), pedido_id=pedido.get("pedido_id", ""),
                                 cancelado=getattr(getattr(self.rt, "conversa", None), "_cancelado", None),
                                 parametros=parametros)
        except ValueError as exc:
            return str(exc)
        self._projeto_na_tela(tarefa)
        return resumo_falado(tarefa, self._trat()) + " " + " ".join(e.resultado or "" for e in tarefa.etapas)

    # ---- inteligencia: dados reais para o modelo raciocinar ------------------------------------------
    def contexto_para_modelo(self, texto: str) -> str | None:
        """Quando a pergunta pede planejar, priorizar ou entender o PC/noticias, junta os dados
        reais (tarefas, lembretes, agenda, medidas, manchetes) para o modelo nao inventar."""
        n = normalizar(texto)
        partes: list[str] = []
        agora = datetime.now()
        tel = self._tel() or {}
        try:
            from .memoria import Episodios
            episodios = self._servico("episodios", Episodios)
            evidencia = episodios.para_prompt(self._projetos().projeto or "pessoal", texto)
            if evidencia:
                partes.append(evidencia)
        except (OSError, ValueError):
            pass
        # trechos dos documentos do Senhor, com a referência: é isto que faz o
        # modelo responder PELO manual em vez de pela memória dele (§7, RAG)
        try:
            evidencia, achados = self._conhecimento().para_prompt(texto, 2)
            if evidencia:
                partes.append(evidencia)
                self._contexto({"tipo": "documento", "titulo": achados[0].documento.nome,
                                "itens": [{"titulo": a.citar(), "fonte": a.documento.nome,
                                           "trecho": a.trecho.texto[:400]} for a in achados]})
        except Exception:  # noqa: BLE001 - sem documentos, a conversa segue igual
            pass
        # o projeto aberto vai SEMPRE: sem isto o modelo responde "isso" no vazio
        try:
            from .projetos import por_extenso
            aberta = self._projetos().ativa()
            if aberta is not None:
                pend = [e.descricao for e in aberta.pendentes()[:4]]
                partes.append(f"projeto aberto agora: {aberta.projeto or 'sem nome'}; tarefa: {aberta.objetivo} "
                              f"({por_extenso(aberta.estado)}, versão {aberta.versao}); "
                              f"falta: {'; '.join(pend) if pend else 'nada listado'}")
        except Exception:  # noqa: BLE001 - contexto e opcional, nunca derruba a resposta
            pass
        if re.search(r"\b(?:planej|prioriz|organiz|agenda|compromiss|tarefa|meu dia|minha semana|minha manha|minha tarde"
                     r"|o que (?:eu )?(?:faco|devo fazer|tenho)|por onde comec|proximos passos|rotina)\w*", n):
            tarefas = getattr(self.rt, "tarefas", None)
            pend = [t["texto"] for t in (tarefas.listar() if tarefas else []) if not t.get("feita")][:12]
            partes.append("tarefas pendentes: " + ("; ".join(pend) if pend else "nenhuma"))
            sec = getattr(self.rt, "secretario", None)
            lembretes = [f"{datetime.fromtimestamp(x['quando']):%d/%m %H:%M} {x['texto']}" for x in (sec.pendentes() if sec else [])
                         if x["quando"] - agora.timestamp() < 7 * 86400][:10]
            partes.append("lembretes dos próximos 7 dias: " + ("; ".join(lembretes) if lembretes else "nenhum"))
            ag = tel.get("agenda") or {}
            if ag.get("status") == "medido":
                evs = [f"{datetime.fromtimestamp(e['inicio']):%d/%m %H:%M} {e['titulo']}" for e in ag.get("eventos", [])
                       if 0 <= e["inicio"] - agora.timestamp() < 3 * 86400][:10]
                partes.append("agenda dos próximos 3 dias: " + ("; ".join(evs) if evs else "livre"))
            else:
                partes.append("agenda: não conectada")
        if re.search(r"\b(?:computador|pc|notebook|lento|lenta|travando|desempenho|memoria|processador|bateria|esquentando)\b", n):
            s = tel.get("sistema") or {}
            medidas = []
            for chave, rot, campo, un in (("cpu", "processador", "uso_pct", "%"), ("memoria", "memória", "uso_pct", "%"),
                                          ("disco", "disco livre", "livre_gb", " GB"), ("temperatura", "CPU", "celsius", " °C"),
                                          ("bateria", "bateria", "percentual", "%")):
                v = s.get(chave) or {}
                if v.get("status") == "medido":
                    medidas.append(f"{rot} {round(v[campo])}{un}")
            modelo = self.rt.prefs.ler().get("modelo_voz")
            partes.append("medidas agora: " + ", ".join(medidas) + (f"; modelo de IA carregado: {modelo}" if modelo else ""))
        if re.search(r"\b(?:noticia|aconteceu|acontecendo|novidades|no mundo hoje)\w*", n):
            itens = (tel.get("noticias") or {}).get("itens") or []
            if itens:
                partes.append("manchetes: " + "; ".join(f"{i['titulo']} ({i['fonte']})" for i in itens[:6]))
        if not partes:
            return None
        return "[Dados reais deste computador para responder (use o que for útil, não invente outros): " + " | ".join(partes) + "]"

    # ---- quem e quem (autorizado pelo Senhor; so cadastrados, so neste PC) ---------------------------
    def _nome_do_pedido(self, original: str, regra_nome: str) -> str | None:
        """ "o rosto da Maria" -> "Maria"; "meu rosto" -> "dono"; "este é o Pedro, memorize o rosto dele" -> "Pedro"."""
        n = normalizar(original)
        regra = dict(REGRAS)[regra_nome]
        nome = grupo_original(original, regra, "nome") if "nome" in regra.groupindex else None
        # O segundo alvo de um pedido conjunto nao repete o verbo. Preserve o nome
        # da pessoa, incluindo sobrenomes, sem incorporar "agora" ou "por favor".
        tipo = _VOZ if regra_nome == "id_voz_cadastrar" else _ROSTO if regra_nome == "id_rosto_cadastrar" else rf"(?:{_ROSTO}|{_VOZ})"
        trecho = sem_chamado(original)
        m_nome = re.search(rf"\b{tipo}\s+d[aoe]\s+(?P<n>[a-z]\w*(?:\s+(?!(?:e|agora|por|no|na|para|com|que)\b)[a-z]\w*){{0,3}})",
                           normalizar_mesmo_tamanho(trecho))
        if m_nome:
            nome = trecho[m_nome.start("n"):m_nome.end("n")]
        if not nome:
            m = re.search(r"\b(?:este|esta|esse|essa) (?:e|eh) (?:o |a )?(?P<n>[a-z][a-z]+)\b", n)
            if m:
                trecho = sem_chamado(original)
                ini = normalizar_mesmo_tamanho(trecho).find(m.group("n"))
                nome = trecho[ini:ini + len(m.group("n"))] if ini >= 0 else m.group("n")
        if nome:
            nome = nome.strip(" .,!?")
            return nome[0].upper() + nome[1:] if nome else None
        return "dono" if re.search(r"\b(?:meu|minha|eu)\b", n) else None

    # ---- canais e o que cada um faz (F37) --------------------------------
    def _canais(self) -> Any:
        from .canais import Canais
        return self._servico("canais", Canais)

    def canais(self, nome: str, original: str) -> str | None:
        from .canais import APRESENTACAO, ARQUIVO, AUDIO, CONTROLE, TEXTO, falar_lista
        reg, t = self._canais(), self._trat()
        if nome == "canais_listar":
            return falar_lista(reg.listar(), t)

        regra = dict(REGRAS)[nome]
        alvo = (grupo_original(original, regra, "canal") or
                grupo_original(original, regra, "canal2") or "").strip().lower()
        cid = {"celular": "telegram", "painel": "tela", "mesa": "tela"}.get(alvo, alvo)
        n = normalizar(sem_chamado(original))
        capacidade = (AUDIO if re.search(r"\b(?:audio|som|voz|fala|toca|ouvir|escutar|ler em voz)\b", n) else
                      APRESENTACAO if re.search(r"\b(?:mostr\w*|tela|modelo|grafico|apresent\w*)\b", n) else
                      ARQUIVO if re.search(r"\b(?:arquivo|stl|planilha|pdf|documento)\b", n) else
                      CONTROLE if re.search(r"\b(?:control\w*|execut\w*|abr\w*|lig\w*)\b", n) else TEXTO)
        canal = reg.obter(cid)
        if canal is None:
            return reg.porque_nao(cid, capacidade, t)
        if reg.pode(cid, capacidade) and canal.autenticado:
            return f"Faz, {t}. {canal.falado()}."
        return reg.porque_nao(cid, capacidade, t)

    # ---- correções do Senhor (§17: regra revisável, não treinamento) -----
    def _correcoes(self) -> Any:
        from .correcoes import Correcoes
        return self._servico("correcoes", Correcoes)

    def corrigir(self, nome: str, original: str) -> str | None:
        from .correcoes import falar_lista, falar_registro
        cor, t = self._correcoes(), self._trat()
        regra = dict(REGRAS)[nome]

        def grupo(*nomes: str) -> str:
            for g in nomes:
                try:
                    v = grupo_original(original, regra, g)
                except (IndexError, KeyError):
                    v = None
                if v:
                    return v.strip(" .,!?")
            return ""

        if nome == "corrigir_listar":
            return falar_lista(cor.listar(), t)

        if nome == "corrigir_esquecer":
            alvo = grupo("q", "q2")
            try:
                if not alvo:
                    itens = cor.listar()
                    if not itens:
                        return f"Não tenho correção nenhuma guardada, {t}."
                    cor.esquecer(itens[0].id)
                    return f"Esqueci a última: \"{itens[0].quando_eu_disser}\", {t}."
                return (f"Esqueci \"{alvo}\", {t}." if cor.esquecer(alvo)
                        else f"Não tenho correção com \"{alvo}\", {t}.")
            except ValueError as exc:
                return f"Não apaguei a correção: {exc}."

        gatilho = grupo("gatilho", "gatilho3", "gatilho2")
        acao = grupo("acao", "acao3", "acao2")
        try:
            c = cor.registrar(gatilho, acao, interpretar=interpretar, origem="voz")
        except ValueError as e:
            return (f"Não consigo guardar assim, {t}: {e}. O apelido precisa apontar para algo "
                    f"que eu já saiba fazer, como \"abra o VS Code\".")
        return falar_registro(c, t)

    # ---- cena consultável (F16: o observado e o não observado) -----------
    def cena(self, nome: str, original: str) -> str:
        from .cena import consultar, falar, montar
        t = self._trat()
        v = getattr(self.rt, "visao_continua", None)
        seguidor = getattr(v, "rastreador", None) if v is not None else None
        camera = bool(getattr(getattr(self.rt, "camera", None), "ativa", False))
        rodou = False
        if camera and v is not None and getattr(v.detector, "disponivel", False):
            v.aguardar(3.0)                       # um quadro novo antes de descrever
            rodou = bool(getattr(v, "em", 0)) and (time.time() - v.em) < 5
        c = montar(seguidor, camera_ligada=camera, detector_rodou=rodou,
                   regua=getattr(self.rt, "regua", None))
        try:
            self.rt.estado.atualizar("cena", **c.cartao())
        except (AttributeError, KeyError):
            pass
        if c.itens or not camera:
            self._contexto({"tipo": "cena", "titulo": "Cena observada",
                            "itens": [{"titulo": i.falado(c.em), "fonte": i.estado}
                                      for i in c.itens[:8]]})
        if nome == "cena_nao_visto":
            return consultar(c, "o que você não viu?", t)
        pedido = sem_chamado(original)
        return consultar(c, pedido, t) if re.search(
            r"\b(?:esquerda|direita|centro|meio)\b", normalizar(pedido)) else falar(c, t)

    # ---- cruzar ocorrências (F17: o que aconteceu, quando e onde) --------
    def ocorrencias(self, original: str) -> str:
        from .ocorrencias import (
            de_eventos,
            de_inventario,
            de_pecas,
            de_projetos,
            de_rastreador,
            falar,
            filtrar,
            periodo_citado,
        )
        t = self._trat()
        agora = time.time()
        inicio, fim, rotulo = periodo_citado(original, agora)
        tudo = []
        v = getattr(self.rt, "visao_continua", None)
        seguidor = getattr(v, "rastreador", None) if v is not None else None
        if seguidor is not None:
            tudo += de_rastreador(seguidor)
        try:
            tudo += de_inventario(self._inventario())
            tudo += de_projetos(self._projetos())
            tudo += de_pecas(self._pecas())
        except Exception:  # noqa: BLE001 - uma fonte vazia nao derruba a resposta
            pass
        try:
            tudo += de_eventos((self.rt.estado.instantaneo() or {}).get("eventos") or [])
        except (AttributeError, KeyError):
            pass

        n = normalizar(sem_chamado(original))

        # "o que apareceu na mesa?" -> lugar; "quando voce viu meu celular?" -> objeto
        onde = ""
        for chave, rotulo_onde in (("esquerda", "esquerda"), ("direita", "direita"), ("centro", "centro")):
            if re.search(rf"\b{chave}\b", n):
                onde = rotulo_onde
        termo = ""
        from .deteccao import CLASSES, classe_na_frase
        c = classe_na_frase(n)
        if c is not None:
            termo = CLASSES[c][0]
        tipos: tuple[str, ...] = ()
        if re.search(r"\bapareceu\b", n):
            tipos = ("objeto_visto", "objeto_voltou")
        elif re.search(r"\bsumiu\b|\bsaiu\b", n):
            tipos = ("objeto_sumiu",)

        achados = filtrar(tudo, inicio, fim, termo=termo, onde=onde, tipos=tipos)
        alvo = f"{rotulo}{f' com {termo}' if termo else ''}{f', {onde}' if onde else ''}"
        camera_desligada = not (self.rt.estado.ler("camera") or {}).get("ativa") if hasattr(self.rt.estado, "ler") else False
        frase = falar(achados, alvo, t, com_data=(fim - inicio) > 86400)
        if not achados and camera_desligada:
            frase += " A câmera está desligada agora; só registro o que ela vê ligada."
        if achados:
            self._contexto({"tipo": "ocorrencias", "titulo": alvo.capitalize(),
                            "itens": [{"titulo": o.falado(), "fonte": o.fonte} for o in achados[-8:]]})
        return frase

    # ---- manuais e documentos (§7: responder com a evidência) ------------
    def _conhecimento(self) -> Any:
        from .conhecimento import Conhecimento
        return self._servico("conhecimento", Conhecimento)

    def documento(self, nome: str, args: dict[str, str], original: str) -> str | None:
        from .conhecimento import falar_fontes, falar_indexado, falar_lista
        from .documentos import EXTS, achar
        con, t = self._conhecimento(), self._trat()
        regra = dict(REGRAS)[nome]

        def grupo(*nomes: str) -> str:
            for g in nomes:
                try:
                    v = grupo_original(original, regra, g)
                except (IndexError, KeyError):
                    v = None
                if v:
                    return v.strip(" .,!?")
            return ""

        if nome == "doc_listar":
            return falar_lista(con.todos(), t)

        if nome == "doc_fonte":
            atual = self.fonte_da_resposta(original)
            return atual or "Última consulta documental: " + falar_fontes(con.ultimos, t)

        if nome == "doc_indexar":
            alvo = grupo("q")
            caminho = achar(alvo or original, exts=EXTS)
            if caminho is None:
                return (f"Não achei esse arquivo, {t}. Coloque-o em Documentos ou na Área de Trabalho "
                        f"e diga o nome: leia o manual tal.")
            ja = con.achar_documento(caminho.stem)
            try:
                doc = con.indexar(caminho, assunto=alvo or caminho.stem)
            except (ValueError, OSError) as e:
                return f"Não consegui ler {caminho.name}, {t}: {e}."
            # se o objeto do inventario tiver o mesmo assunto, guarda o manual nele
            try:
                obj = self._inventario().achar(alvo or caminho.stem)
                if obj is not None and not obj.manual:
                    obj.manual = str(caminho)
                    self._inventario().salvar()
            except Exception:  # noqa: BLE001 - vincular e bonus
                pass
            return falar_indexado(doc, substituiu=bool(ja and ja.versao != doc.versao), tratamento=t)

        if nome == "doc_esquecer":
            alvo = grupo("q")
            atuais = con.atuais()
            if len(atuais) > 1:                       # dois manuais? pergunto qual (F04)
                from .ambiguidade import de_objetos, resolver
                escolhido, pergunta = resolver(alvo or original,
                                               de_objetos(atuais, lambda d: d.nome, "documento"),
                                               "documento", t)
                if escolhido is None:
                    return pergunta
                doc = escolhido.extra
            else:
                doc = con.achar_documento(alvo) if alvo else (atuais[0] if atuais else None)
            if doc is None:
                return f"Não tenho esse documento indexado, {t}."
            quantas = con.esquecer_arquivo(doc.caminho)
            return f"Esqueci {doc.nome}, {t} ({quantas} versão{'ões' if quantas > 1 else ''} apagada{'s' if quantas > 1 else ''})."

        # doc_perguntar
        pergunta = grupo("q", "q2", "q3")
        alvo = grupo("alvo")
        doc = con.achar_documento(alvo) if alvo else None
        if not con.atuais():
            return (f"Ainda não li nenhum documento, {t}. Diga: leia o manual da impressora.")
        achados = con.buscar(pergunta or original, 3, documento=doc)
        if not achados:
            if getattr(con, "avisos", None):
                return "A fonte mudou ou não está disponível. Reindexe o documento antes de consultar: " + "; ".join(map(str, con.avisos))
            onde = doc.nome if doc else "nos documentos que eu li"
            return (f"Isso não está escrito {('em ' + onde) if doc else onde}, {t}. "
                    f"Não vou inventar o que o manual não diz.")
        melhor = achados[0]
        aviso = (" Atenção: o arquivo mudou depois que eu indexei; vale dizer, leia o manual de novo."
                 if melhor.documento.mudou_no_disco() else "")
        self._contexto({"tipo": "documento", "titulo": melhor.documento.nome,
                        "itens": [{"titulo": a.citar(), "fonte": a.documento.nome,
                                   "link": None, "trecho": a.trecho.texto[:400]} for a in achados]})
        # o trecho e a FONTE: leio o que esta escrito, sem concluir por conta propria
        trecho = re.sub(r"\s+", " ", melhor.trecho.texto).strip()
        if len(trecho) > 420:
            trecho = trecho[:420].rsplit(" ", 1)[0] + "…"
        resposta = (f"Segundo {melhor.citar()}: {trecho}" + aviso +
                    f" Os trechos estão na tela, {t}.")
        self._registrar_fontes([{"titulo": a.citar(), "fonte": a.documento.nome, "cobertura": "trecho documental",
                                "consultado_em": a.documento.indexado_em, "versao": a.documento.versao,
                                "desatualizado": a.documento.mudou_no_disco()} for a in achados], resposta)
        return resposta

    # ---- inventário pessoal (§9: as coisas do Senhor) --------------------
    @staticmethod
    def _objetos_parecidos(inv: Any, alvo: str) -> list[Any]:
        """Objetos que casam com o pedido pelo nome, apelido ou categoria."""
        from .inventario import _norm
        n = _norm(alvo)
        if not n:
            return []
        saida = []
        for o in inv.todos():
            nomes = [_norm(x) for x in o.chamado()] + [_norm(o.categoria)]
            if any(x and (x == n or n in x or x in n) for x in nomes):
                saida.append(o)
        return saida

    def _inventario(self) -> Any:
        from .inventario import Inventario
        return self._servico("inventario", Inventario)

    def inventario(self, nome: str, args: dict[str, str], original: str) -> str | None:
        from .inventario import falar_lista, falar_objeto
        inv, t = self._inventario(), self._trat()
        regra = dict(REGRAS)[nome]
        alvo = ""
        for grupo in ("obj", "obj2", "obj3"):
            try:
                alvo = grupo_original(original, regra, grupo) or alvo
            except (IndexError, KeyError):
                pass
            if alvo:
                break
        alvo = alvo.strip(" .,!?")

        if nome == "inv_listar":
            return falar_lista(inv.todos(), t)

        if nome == "inv_definir":
            campo = (grupo_original(original, regra, "campo") or "").lower()
            valor = (grupo_original(original, regra, "valor") or "").strip(" .,!?")
            o = inv.achar(alvo) if alvo else (inv.todos()[0] if inv.todos() else None)
            if o is None:
                return f"De qual objeto, {t}? Diga: cadastre esta impressora, primeiro."
            campo = {"fabricante": "marca", "serie": "número de série",
                     "numero de serie": "número de série"}.get(campo, campo)
            if campo == "manual":
                o.manual = valor
                o.mexido_em = time.time()
                inv.salvar()
                return f"Anotei o manual de {o.nome}, {t}."
            inv.confirmar(o.id, campo, valor)
            return f"Certo, {t}: {campo} de {o.nome} é {valor}. Fica como confirmado pelo senhor."

        if nome == "inv_cadastrar":
            if not alvo:
                return f"O que devo cadastrar, {t}?"
            ja = inv.achar(alvo)
            if ja is not None:
                return (f"Já tenho {ja.nome} cadastrado, {t}. Para trocar algo, diga: "
                        f"o modelo do {ja.nome} é tal.")
            # o que a camera esta vendo vira SUGESTAO, nunca cadastro automatico
            categoria = ""
            v = getattr(self.rt, "visao_continua", None)
            if v is not None and getattr(v.detector, "disponivel", False):
                from .deteccao import CLASSES, classe_na_frase
                c = classe_na_frase(alvo)
                if c is not None:
                    categoria = CLASSES[c][0]
            o = inv.cadastrar(alvo, categoria=categoria or alvo.split()[-1], projeto=self._projetos().projeto)
            return (f"Cadastrei {o.nome}, {t}. Se quiser, me diga a marca e o modelo — "
                    f"eu só guardo o que o senhor confirmar.")

        if not alvo and nome != "inv_manual":
            return f"Qual objeto, {t}?"
        o = inv.achar(alvo) if alvo else None
        # `achar` devolve None tanto para "não existe" quanto para "tem mais de um".
        # São coisas diferentes: no empate eu PERGUNTO, não digo que não tenho (F04).
        empatados = self._objetos_parecidos(inv, alvo) if (o is None and alvo) else []
        if len(empatados) == 1:
            o = empatados[0]

        if nome == "inv_saber":
            if o is None and empatados:
                from .ambiguidade import de_objetos, perguntar
                return perguntar(de_objetos(empatados, lambda x: x.nome, "objeto"), alvo, t)
            if o is None:
                return (f"Não tenho {alvo} cadastrado, {t}. Diga: cadastre {alvo}.")
            return falar_objeto(o, tratamento=t)

        if nome == "inv_manual":
            o = o or next((x for x in inv.todos() if x.manual), None)
            if o is None or not o.manual:
                return (f"Não tenho manual guardado{' de ' + alvo if alvo else ''}, {t}. "
                        f"Diga: o manual é, e o caminho do arquivo.")
            from pathlib import Path
            caminho = Path(o.manual)
            if caminho.is_file():
                import os
                os.startfile(str(caminho))
                return f"Abrindo o manual de {o.nome}, {t}."
            if o.manual.startswith("https://"):
                self._abrir_url(o.manual)
                return f"Abrindo o manual de {o.nome}, {t}."
            return f"O manual de {o.nome} está anotado como {o.manual}, mas não encontrei o arquivo."

        if nome == "inv_esquecer":
            if o is None and empatados:              # pergunto antes de apagar o errado (F04)
                from .ambiguidade import de_objetos, resolver
                escolhido, pergunta = resolver(alvo, de_objetos(empatados, lambda x: x.nome, "objeto"),
                                               alvo, t)
                if escolhido is None:
                    return pergunta
                o = escolhido.extra
            if o is None:
                return f"Não tenho {alvo} cadastrado, {t}."
            inv.esquecer(o.id)
            return f"Tirei {o.nome} do inventário, {t}."
        return None

    # ---- peça em edição (§12: parâmetros, versões, prévia) ---------------
    def _pecas(self) -> Any:
        from .pecas import Pecas
        return self._servico("pecas", Pecas)

    def _focar_peca_do_projeto(self) -> None:
        """Projeto, peça, seleção e prévia precisam se referir ao mesmo trabalho."""
        peca = self._pecas().focar_projeto(self._projetos().projeto)
        self._previa_peca = None
        selecao = getattr(self.rt, "selecao", None)
        if selecao is not None:
            selecao.limpar()
        self.rt.estado.atualizar("previa", estado="inativo", arquivo=None,
                                 peca_nome=None, projeto=None, parametros=None,
                                 versao_base=None, em=time.time())
        self._peca_na_tela(peca)
        versao = peca.atual() if peca else None
        self.rt.ultimo_projeto = versao.arquivo if versao else None
        if versao and versao.arquivo:
            self.mostrar_modelo(versao.arquivo)
        else:
            self.rt.holograma_modelo = None

    def _peca_na_tela(self, peca: Any) -> None:
        from .pecas import NOME_FALADO
        v = peca.atual() if peca else None
        try:
            self.rt.estado.atualizar(
                "peca",
                nome=peca.nome if peca else None,
                tipo=peca.tipo if peca else None,
                versao=peca.versao if peca else 0,
                parametros=([{"nome": NOME_FALADO.get(k, k), "valor": val}
                             for k, val in peca.parametros.items()] if peca else []),
                volume_cm3=round(v.volume_mm3 / 1000, 2) if v else None,
                arquivo=(v.arquivo if v else None),
                material=peca.material if peca else None,
                cor=peca.cor if peca else None,
                restricoes=(["Unidades em mm", "Cor e material são metadados; STL só contém geometria",
                             "Impressão e resistência física não verificadas"] if peca else []),
                historico=[{"versao": x.numero, "motivo": x.motivo} for x in (peca.versoes[-5:] if peca else [])],
                em=time.time())
        except (AttributeError, KeyError):
            pass

    _NUMERO = re.compile(r"(?<![\d.,])(?P<n>\d+(?:[.,]\d+)?)(?!\d)\s*(?P<un>mm|milimetros?|cm|centimetros?)?")

    def montagem(self, nome: str, original: str) -> str | None:
        from .montagem import falar_componentes, falar_explosao, recusa_de_explosao
        from .pecas import MONTAGENS, falar_versao
        acervo, t = self._pecas(), self._trat()

        if nome == "montagem_criar":
            medidas = [float(x.replace(",", ".")) for x in
                       re.findall(r"(?<![\d.,])(\d+(?:[.,]\d+)?)(?![\d.,])",
                                  normalizar(sem_chamado(original)))][:5]
            c, l, a = (medidas + [80.0, 50.0, 30.0])[:3]
            parede = medidas[3] if len(medidas) > 3 else 2.0
            tampa = medidas[4] if len(medidas) > 4 else 2.0
            try:
                peca, avisos = acervo.criar("caixa_com_tampa",
                                            {"c": c, "l": l, "a": a, "parede": parede, "tampa": tampa},
                                            nome="caixa com tampa", projeto=self._projetos().projeto,
                                            motivo=f"caixa de {c:g} por {l:g} por {a:g} mm com tampa de {tampa:g}")
            except ValueError:
                from .discordancia import conflitos_de_peca, falar as falar_conflito
                return falar_conflito(conflitos_de_peca("caixa_com_tampa",
                                                        {"c": c, "l": l, "a": a, "parede": parede, "tampa": tampa}),
                                      original, t)
            v = peca.atual()
            self.rt.ultimo_projeto = v.arquivo
            self._peca_na_tela(peca)
            if v.arquivo:
                self.mostrar_modelo(v.arquivo)
            m = acervo.montagem_de(peca)
            return (falar_versao(peca, v, avisos, t) + " " +
                    f"São {len(m.componentes)} peças: corpo e tampa. Para ver separadas, diga: "
                    f"mostre a vista explodida.")

        peca = acervo.ativa()
        if peca is None:
            return f"Não há peça aberta, {t}. Diga: monte uma caixa com tampa de 80 por 50 por 30."
        m = acervo.montagem_de(peca)

        if nome == "montagem_pecas":
            if m is None:
                return recusa_de_explosao(peca.nome, t)
            return falar_componentes(m, t)

        # montagem_explodir
        if m is None or peca.tipo not in MONTAGENS:
            return recusa_de_explosao(peca.nome, t)
        arquivo = acervo.explodir(peca)
        if arquivo is None:
            return f"Não consegui gerar a vista explodida, {t}."
        self.mostrar_modelo(arquivo)
        return falar_explosao(m, t)

    def peca(self, nome: str, args: dict[str, str], original: str) -> str | None:
        from .pecas import NOME_FALADO, dimensao_citada, dimensoes_do_tipo, falar_versao, falar_versoes
        acervo, t = self._pecas(), self._trat()
        p = acervo.ativa()
        if p is None:
            return ("Ainda não há peça aberta, Senhor. Peça, por exemplo: projete uma caixa de "
                    "80 por 50 por 30 milímetros.")
        projeto = self._projetos().projeto
        if normalizar(p.projeto) != normalizar(projeto):
            self._focar_peca_do_projeto()
            return ("A peça anterior pertence a outro projeto. Restabeleci o foco do projeto atual; "
                    "peça novamente a alteração para conferir a peça correta.")
        n = normalizar(sem_chamado(original))

        if nome == "peca_confirmar":
            previa = getattr(self, "_previa_peca", None)
            if (not previa or previa["peca_nome"] != p.nome
                    or normalizar(previa.get("projeto", "")) != normalizar(projeto)
                    or time.time() - previa["em"] > 300):
                return "Não há prévia atual para confirmar. Peça novamente a alteração da peça."
            try:
                if previa.get("tipo_alteracao") == "estilo":
                    v, avisos = acervo.alterar_estilo(p, previa["chave"], previa["valor"],
                                                    versao_esperada=previa["versao_base"])
                else:
                    v, avisos = acervo.alterar(p, previa["chave"], valor=previa["valor"],
                                             versao_esperada=previa["versao_base"])
            except (ValueError, OSError) as exc:
                return f"Não consolidei a alteração: {exc}. Gere uma nova prévia."
            self._previa_peca = None
            self.rt.estado.atualizar("previa", estado="inativo", arquivo=None, cor=None, em=time.time())
            self._peca_na_tela(p)
            if v.arquivo:
                self.mostrar_modelo(v.arquivo)
            self.rt.ultimo_projeto = v.arquivo
            aberta = self._projetos().ativa()
            if aberta is not None:
                self._projetos().registrar_resultado(aberta.id, f"{p.nome} versão {v.numero}: {v.motivo}")
            return falar_versao(p, v, avisos, t)

        if nome == "peca_apagar":
            nome_peca = p.nome
            acervo.esquecer(nome_peca)
            self._peca_na_tela(acervo.ativa())
            return (f"Tirei {nome_peca} do acervo, {t}. Os arquivos STL continuam em "
                    f"Documentos, Jarvis, Projetos; apague-os o senhor mesmo se quiser.")

        if nome == "peca_versoes":
            self._peca_na_tela(p)
            return falar_versoes(p, t)

        if nome == "peca_comparar":
            numeros = [int(x) for x in re.findall(r"\d+", n)]
            if len(numeros) != 2:
                return "Diga as duas versões: compare as versões 1 e 2 da peça."
            try:
                comparacao = acervo.comparar(p, *numeros)
            except ValueError as exc:
                return f"Não comparei: {exc}."
            itens = [{"titulo": NOME_FALADO.get(m["campo"], m["campo"]),
                      "detalhe": f"{m['antes'] if m['antes'] is not None else 'desconhecido'} → "
                                 f"{m['depois'] if m['depois'] is not None else 'desconhecido'} {m.get('unidade', '')}",
                      "fonte": "histórico local da peça"} for m in comparacao["mudancas"]]
            self._contexto({"tipo": "comparacao", "titulo": f"{p.nome} · versões {numeros[0]} e {numeros[1]}",
                            "itens": itens, "limites": comparacao["limite"]})
            return (f"Comparação das versões {numeros[0]} e {numeros[1]} de {p.nome}: "
                    + ("; ".join(f"{i['titulo']}: {i['detalhe']}" for i in itens) or "os parâmetros, material e cor são iguais")
                    + ". Não houve teste físico.")

        if nome == "peca_estilo":
            m = re.search(r"\b(material|cor)\b(?:\s+d[aeo]\s+(?:peca|caixa|montagem))?\s+(?:para|pra|por|em)\s+(.+)", n)
            if not m:
                return "Diga: altere o material da peça para PETG, ou altere a cor da peça para azul."
            try:
                previa = acervo.previa_estilo(p, m[1], m[2].strip(" .!?"))
            except (ValueError, OSError) as exc:
                return f"Não preparei a alteração: {exc}."
            self._previa_peca = dict(previa, peca_nome=p.nome, projeto=projeto, em=time.time())
            self.rt.estado.atualizar("previa", **self._previa_peca)
            self.mostrar_modelo(previa["arquivo"])
            return (f"Prévia de {p.nome}: {previa['motivo']}. A versão {p.versao} continua salva. "
                    "Confira e diga: confirme a alteração da peça. Cor e material são metadados locais; o STL contém só geometria.")

        if nome == "peca_voltar":
            self._previa_peca = None
            self.rt.estado.atualizar("previa", estado="inativo", arquivo=None, cor=None, em=time.time())
            alvo = args.get("n")
            numero = int(alvo) if alvo else max(1, p.versao - 1)
            if numero == p.versao and p.versao == 1:
                return f"{p.nome} só tem a versão 1, {t}."
            v = acervo.reverter(p, numero)
            if v is None:
                return f"Não existe a versão {numero} de {p.nome}, {t}."
            self._peca_na_tela(p)
            if v.arquivo:
                self.mostrar_modelo(v.arquivo)
            return falar_versao(p, v, None, t)

        # peca_alterar: "isso" e o que estiver selecionado na tela, se houver
        sel = getattr(self.rt, "selecao", None)
        alvo = sel.atual() if sel is not None else None
        if alvo is not None and alvo.tipo in ("peca", "componente") and re.search(r"\b(?:isso|isto|essa|esta)\b", n):
            if alvo.tipo == "componente":
                self._previa_peca = None
                self.rt.estado.atualizar("previa", estado="inativo", arquivo=None,
                                         peca_nome=None, parametros=None, em=time.time())
                return (f"A seleção é o componente {alvo.rotulo or alvo.id}. Ainda não altero um componente "
                        "isoladamente. Na caixa com tampa, corpo e tampa compartilham comprimento e largura. "
                        "Para alterar o conjunto, diga o parâmetro explicitamente, por exemplo: "
                        "aumente a largura em 2 milímetros. Para a tampa, posso alterar a espessura da tampa.")
            escolhida = acervo.achar(alvo.rotulo or alvo.id)
            if escolhida is not None and normalizar(escolhida.projeto) != normalizar(projeto):
                self._focar_peca_do_projeto()
                return "Essa seleção pertence a outro projeto. Selecione uma peça do projeto atual antes de alterar."
            if escolhida is not None and escolhida is not p:
                acervo.focar(escolhida.nome)
                p = escolhida
        chave = dimensao_citada(p.tipo, n)
        if chave is None:
            # "aumente isso": NAO chutar. Perguntar qual dimensão (§4, T03)
            opcoes = dimensoes_do_tipo(p.tipo)
            return (f"Qual dimensão, {t}? {p.nome} tem "
                    + ", ".join(opcoes[:-1]) + f" e {opcoes[-1]}." if len(opcoes) > 1
                    else f"Qual dimensão, {t}?")
        m = self._NUMERO.search(n)
        quantidade = float(m.group("n").replace(",", ".")) if m else None
        if quantidade is not None and (m.group("un") or "").startswith("c"):
            quantidade *= 10                                   # centímetros -> mm
        aumentar = bool(re.search(r"\b(?:aument\w*|engross\w*|maior|mais gross\w*|sob\w*)\b", n))
        diminuir = bool(re.search(r"\b(?:diminu\w*|reduz\w*|encolh\w*|afin\w*|menor|mais fin\w*)\b", n))
        para = bool(re.search(r"\b(?:para|pra|fique com|com)\b", n))

        if quantidade is None:
            atual = p.parametros.get(chave, 0)
            return (f"Quanto, {t}? {NOME_FALADO.get(chave, chave)} está em {atual:g} milímetros. "
                    f"Diga, por exemplo: aumente {NOME_FALADO.get(chave, chave)} em 2 milímetros.")
        try:
            if (aumentar or diminuir) and not para:
                delta = quantidade if aumentar else -quantidade
                previa = acervo.gerar_previa(p, chave, delta=delta)
            else:
                previa = acervo.gerar_previa(p, chave, valor=quantidade)
        except KeyError as e:
            return f"Não dá para fazer isso, {t}: {e}."
        except ValueError:
            from .discordancia import conflitos_de_peca, falar as falar_conflito
            tentativa = dict(p.parametros)
            tentativa[chave] = quantidade if not (aumentar or diminuir) else (
                tentativa.get(chave, 0) + (quantidade if aumentar else -quantidade))
            return falar_conflito(conflitos_de_peca(p.tipo, tentativa), original, t)
        self._previa_peca = dict(previa, peca_nome=p.nome, projeto=projeto, em=time.time())
        self.rt.estado.atualizar("previa", **self._previa_peca)
        self.mostrar_modelo(previa["arquivo"])
        return (f"Prévia de {p.nome}: {previa['motivo']}. Mantive a versão {p.versao}. "
                "Confira o modelo na mesa e diga: confirme a alteração da peça.")

    # ---- projetos e tarefas (§6: o que foi pedido, o que falta) ----------
    _CONDICAO = re.compile(
        r"\b(?P<chave>material|filamento|temperatura|velocidade|camada|bico|preenchimento|tensao|corrente|carga)\b"
        r"\s*(?:de|em|a|:)?\s*(?P<valor>[\w.,°%]+(?:\s?(?:graus|mm|cm|%|v|a|w|c))?)", re.I)
    _MATERIAIS_COMUNS = ("pla", "petg", "abs", "tpu", "resina", "nylon", "aluminio", "aco", "madeira")

    def _condicoes_do_texto(self, texto: str) -> tuple[dict[str, str], list[str]]:
        """Tira do relato as condições do experimento (F22) e o que não foi conferido (F26)."""
        n = normalizar(texto)
        condicoes: dict[str, str] = {}
        # a unidade manda mais que a palavra-chave: em "30 por cento de preenchimento
        # a 50 mm por segundo", o preenchimento é 30%, não os 50 mm que vêm depois
        for chave, regex, formato in (
                ("temperatura", r"\b(\d{2,3})\s*(?:graus|°c?|c)\b", "{} graus"),
                ("preenchimento", r"\b(\d{1,3})\s*(?:%|por cento)\b", "{}%"),
                ("velocidade", r"\b(\d{1,3})\s*mm\s*(?:por segundo|/s)\b", "{} mm/s")):
            m = re.search(regex, n)
            if m:
                condicoes[chave] = formato.format(m.group(1))
        for m in self._CONDICAO.finditer(n):
            condicoes.setdefault(m.group("chave"), m.group("valor").strip())
        for material in self._MATERIAIS_COMUNS:
            if re.search(rf"\b{material}\b", n) and "material" not in condicoes:
                condicoes["material"] = material.upper() if len(material) <= 4 else material
        limites = []
        if not re.search(r"\bmed[ií]\b|\bmedi(?:do|da)\b|\bpaqu[ií]metro\b|\bbalanca\b", n):
            limites.append("medida com instrumento")
        return condicoes, limites

    def _projetos(self) -> Any:
        from .projetos import Projetos
        return self._servico("projetos", Projetos)

    def _projeto_na_tela(self, tarefa: Any = None) -> None:
        """A tela mostra a MESMA tarefa de que o Jarvis está falando."""
        from .projetos import por_extenso
        p = self._projetos()
        t = tarefa or p.ativa()
        dados = p.inspecionar(t.id) if t else None
        if dados:
            dados.pop("ferramentas_modelo", None)
            dados["estado_falado"] = por_extenso(t.estado)
            dados["total_etapas"] = len(t.etapas)
            # O HUD precisa do resultado e das pendências, não dos argumentos internos.
            for e in dados["etapas"]:
                e.pop("argumentos", None)
                e.pop("assinatura", None)
        try:
            self.rt.estado.atualizar(
                "projeto",
                projeto=p.projeto or None,
                tarefa=dados,
                abertas=len(p.abertas()), em=time.time())
        except (AttributeError, KeyError):
            pass

    def projeto(self, nome: str, args: dict[str, str], original: str) -> str:
        from .projetos import resumo_da_lista, resumo_falado
        p, t = self._projetos(), self._trat()
        texto = sem_chamado(original)

        if nome == "projeto_novo":
            titulo = (grupo_original(original, dict(REGRAS)["projeto_novo"], "nome")
                      or grupo_original(original, dict(REGRAS)["projeto_novo"], "nome2") or "").strip(" .!?")
            if not titulo:
                return f"Qual é o projeto, {t}?"
            p.abrir_projeto(titulo)
            tarefa = p.criar(titulo, projeto=titulo)
            self._focar_peca_do_projeto()
            self._projeto_na_tela(tarefa)
            return (f"Projeto {titulo} aberto, {t}. Vá me dizendo o que falta e eu guardo o andamento; "
                    f"depois é só dizer: continue o projeto {titulo}.")

        if nome == "projeto_listar":
            abertas = p.abertas()
            projetos = p.projetos()
            if not abertas and not projetos:
                return f"Não há projeto nenhum em andamento, {t}. Diga: comece o projeto tal."
            frase = resumo_da_lista(abertas, t)
            return frase + (f" Projetos: {', '.join(projetos[:5])}." if len(projetos) > 1 else "")

        if nome == "projeto_continuar":
            alvo = (grupo_original(original, dict(REGRAS)["projeto_continuar"], "alvo") or "").strip(" .!?")
            generico = not alvo or re.search(r"\b(?:ontem|onde paramos|onde parou|aquilo|aquila)\b", normalizar(alvo))
            tarefa = p.ultima_mexida() if generico else (p.achar(alvo, so_abertas=True) or p.achar(alvo))
            if tarefa is None:
                if generico:
                    return f"Não tenho nada em andamento para retomar, {t}."
                return f"Não encontrei esse projeto, {t}. Diga: quais são os meus projetos?"
            p.focar(tarefa.id)
            self._focar_peca_do_projeto()
            if tarefa.origem == "modelo":
                conversa = getattr(self.rt, "conversa", None)
                if conversa is None or not hasattr(conversa, "retomar_tarefa"):
                    self._projeto_na_tela(tarefa)
                    return "O serviço de retomada não está disponível agora. " + resumo_falado(tarefa, t)
                resposta = conversa.retomar_tarefa(tarefa)
                self._projeto_na_tela(tarefa)
                return resposta
            if tarefa.origem == "protocolo":
                from .protocolos import Protocolos
                pr = self._servico("protocolos", Protocolos)
                tarefa = pr.executar(tarefa.objetivo.removeprefix("protocolo "), p,
                                     self.interpretar, self.executar, tarefa_id=tarefa.id,
                                     cancelado=getattr(getattr(self.rt, "conversa", None), "_cancelado", None))
                self._projeto_na_tela(tarefa)
                return resumo_falado(tarefa, t)
            if tarefa.estado == "pausada":
                p.mudar_estado(tarefa.id, "em_execucao")
            self._projeto_na_tela(tarefa)
            proxima = tarefa.proxima_etapa()
            frase = resumo_falado(tarefa, t)
            return frase + (f" Retomo por: {proxima.descricao}." if proxima else "")

        if nome == "projeto_apagar":
            alvo = (grupo_original(original, dict(REGRAS)["projeto_apagar"], "nome") or "").strip(" .!?")
            tarefa = p.achar(alvo) if alvo else (p.ativa() or p.ultima_mexida())
            if tarefa is None:
                return f"Não achei esse projeto, {t}."
            p.esquecer(tarefa.id)
            self._projeto_na_tela(p.ativa())
            return f"Apaguei o projeto {tarefa.projeto or tarefa.objetivo}, {t}."

        # daqui para baixo tudo age sobre a tarefa em foco
        tarefa = p.ativa() or p.ultima_mexida()
        if tarefa is None:
            if nome == "projeto_etapa":
                return f"Não sei de qual projeto, {t}. Diga: comece o projeto tal."
            return f"Não há projeto em andamento, {t}."

        if nome == "projeto_estado":
            self._projeto_na_tela(tarefa)
            return resumo_falado(tarefa, t)

        if nome == "projeto_experimento":
            regra = dict(REGRAS)[nome]
            titulo = grupo_original(original, regra, "nome") or args.get("nome", "teste")
            resultado = grupo_original(original, regra, "resultado") or args.get("resultado", "")
            falha = resultado if re.search(r"\b(?:falh\w*|quebr\w*|erro)\b", normalizar(resultado)) else ""
            # material, temperatura e afins saem do proprio relato: sem elas o
            # resultado nao serve para comparar depois (F22/F26)
            condicoes, _limites = self._condicoes_do_texto(resultado)
            p.registrar_experimento(tarefa.id, titulo, resultado=resultado, falha=falha,
                                    condicoes="; ".join(f"{k} {v}" for k, v in condicoes.items()))
            self._projeto_na_tela(tarefa)
            return f"Registrei o experimento {titulo} em {tarefa.objetivo}, como relato seu. O registro não declara o projeto validado."

        if nome in ("projeto_conferir_etapa", "projeto_etapa_nao_executada"):
            try:
                executada = nome == "projeto_conferir_etapa"
                p.conferir_etapa(tarefa.id, int(args["n"]) - 1, executada=executada,
                                 evidencia=("Usuário confirmou que a etapa foi executada." if executada else
                                            "Usuário confirmou que a etapa não foi executada."))
            except (ValueError, IndexError) as exc:
                return str(exc)
            self._projeto_na_tela(tarefa)
            return "Registrei sua conferência da etapa. Ao retomar, não repetirei essa operação."

        if nome == "projeto_pausar":
            p.mudar_estado(tarefa.id, "pausada", "o Senhor pediu para parar por agora")
            self._projeto_na_tela(tarefa)
            pendentes = len(tarefa.pendentes())
            return (f"Pausei {tarefa.objetivo}, {t}." +
                    (f" Faltam {pendentes} etapas; guardei o que já ficou pronto." if pendentes else
                     " Guardei o andamento."))

        if nome == "projeto_concluir":
            # o Senhor confirmando vale como verificacao; o Jarvis sozinho nao conclui
            p.mudar_estado(tarefa.id, "concluida", "o Senhor confirmou")
            self._projeto_na_tela(None)
            return f"Certo, {t}: {tarefa.objetivo} está concluída."

        if nome == "projeto_depende":
            regra = dict(REGRAS)["projeto_depende"]
            etapa = (grupo_original(original, regra, "etapa") or "").strip(" .!?")
            antes = (grupo_original(original, regra, "antes") or "").strip(" .!?")
            if not etapa or not antes:
                return f"Qual etapa depende de qual, {t}?"
            try:
                p.depender(tarefa.id, etapa, antes)
            except ValueError as e:
                return f"Não dá, {t}: {e}."
            self._projeto_na_tela(tarefa)
            proxima = tarefa.proxima_etapa()
            return (f"Certo: {etapa} só depois de {antes}." +
                    (f" Começo por {proxima.descricao}." if proxima else ""))

        if nome == "projeto_etapa":
            etapa = (grupo_original(original, dict(REGRAS)["projeto_etapa"], "etapa")
                     or grupo_original(original, dict(REGRAS)["projeto_etapa"], "etapa2") or "").strip(" .!?")
            if not etapa:
                return f"O que falta, {t}?"
            p.acrescentar_etapas(tarefa.id, [etapa])
            self._projeto_na_tela(tarefa)
            return f"Anotei em {tarefa.objetivo}: falta {etapa}."
        return None

    def identidade(self, nome: str, args: dict[str, str], original: str) -> str:
        from .identidade import DONO
        t = self._trat()
        if nome == "id_cadastro_negado":
            return "Certo. Não vou cadastrar rosto nem voz."
        if nome == "id_exclusao_negada":
            return "Certo. Nenhum cadastro de rosto ou voz foi apagado."
        if nome == "id_ajuda":
            return ("Diga: memorize meu rosto e minha voz. O rosto usa a câmera local; "
                    "a voz precisa de três frases no microfone. Só guardo os vetores neste computador. "
                    "Você pode cancelar ou pedir para esquecer os cadastros.")
        if nome == "id_cancelar":
            self.cancelar_cadastro()
            conversa = getattr(self.rt, "conversa", None)
            cancelar = getattr(conversa, "cancelar_cadastro_voz", None)
            if cancelar:
                cancelar()
            return "Cancelei a captura pendente. Cadastros já salvos continuam disponíveis; para removê-los, peça para esquecer."
        cad = getattr(self.rt, "identidades", None)
        if cad is None:
            return "O reconhecimento de pessoas não está disponível agora."
        if nome == "id_so_dono":
            ligar = bool(re.search(r"\b(?:so|somente|apenas)\b", normalizar(original)))
            if ligar and DONO not in cad.ler()["vozes"]:
                return f"Primeiro preciso conhecer a sua voz, {t}. Diga: memorize minha voz."
            self.rt.prefs.aplicar({"so_o_dono": ligar})
            return (f"Certo, {t}: daqui em diante só atendo a sua voz." if ligar else "Certo: volto a atender qualquer voz.")
        if nome == "id_listar":
            from .listas import juntar as juntar_falado
            d = cad.ler()
            # "o Senhor e Pedro" soa melhor falado do que "Senhor, Pedro"
            quem = lambda ns: juntar_falado([f"o {t}" if n == DONO else n for n in ns])   # noqa: E731
            rostos, vozes = list(d["rostos"]), list(d["vozes"])
            if not rostos and not vozes:
                return f"Ainda não conheço ninguém, {t}. Diga: memorize meu rosto, ou memorize minha voz."
            de_rosto = f"De rosto, conheço {quem(rostos)}." if rostos else "De rosto, ninguém ainda."
            de_voz = f"De voz, conheço {quem(vozes)}." if vozes else "De voz, ninguém ainda."
            return f"{de_rosto} {de_voz}"
        if nome in ("id_esquecer", "id_pessoa_esquecer"):
            tipo = None if nome == "id_pessoa_esquecer" else "vozes" if (args.get("tipo") or "").startswith("vo") else "rostos"
            alvo = self._nome_do_pedido(original, nome)
            if nome == "id_pessoa_esquecer":
                rosto = self._nome_do_pedido(original, "id_rosto_cadastrar")
                voz = self._nome_do_pedido(original, "id_voz_cadastrar")
                if rosto and voz and rosto != voz:
                    return "Há duas pessoas no pedido. Diga separadamente de quem devo apagar o rosto e de quem devo apagar a voz."
            todos = bool(re.search(r"\btod[oa]s\b", normalizar(original)))
            if not todos and not alvo:
                return "De quem devo apagar o cadastro? Diga meu rosto, minha voz ou o nome da pessoa."
            conversa = getattr(self.rt, "conversa", None)
            pendente = getattr(conversa, "cadastro_voz", None)
            if tipo in (None, "vozes") and isinstance(pendente, dict) and (todos or pendente.get("nome") == alvo):
                conversa.cancelar_cadastro_voz()
            self.cancelar_cadastro()
            saiu = cad.esquecer(tipo, None if todos else alvo)
            if not saiu:
                return "Não havia esse cadastro."
            if tipo is None:
                return f"Apaguei os cadastros de rosto e voz {'de todos' if todos else 'do usuário' if alvo == DONO else 'de ' + alvo}."
            return f"Apaguei {'todos os ' + tipo if todos else ('o seu ' if alvo == DONO else 'o de ' + str(alvo) + ', o ') + tipo[:-1]}."
        if nome in ("id_voz_cadastrar", "id_pessoa_cadastrar"):
            alvo_voz = self._nome_do_pedido(original, "id_voz_cadastrar")
            alvo_rosto = self._nome_do_pedido(original, "id_rosto_cadastrar")
            if nome == "id_pessoa_cadastrar" and alvo_voz and alvo_rosto and alvo_voz != alvo_rosto:
                return "Há duas pessoas no pedido. Cadastre rosto e voz de uma pessoa por vez, com ela presente e de acordo."
            alvo = alvo_voz or (alvo_rosto if nome == "id_pessoa_cadastrar" else None) or DONO
            partes = []
            if nome == "id_pessoa_cadastrar":
                partes.append(self._cadastrar_rosto(alvo))
                if self._cadastro_cancelado.is_set():
                    return " ".join(partes)
            partes.append(self._iniciar_cadastro_voz(alvo))
            return " ".join(partes)
        rostos_id = getattr(self.rt, "rostos_id", None)
        if nome == "id_rosto_cadastrar":
            alvo = self._nome_do_pedido(original, "id_rosto_cadastrar") or DONO
            return self._cadastrar_rosto(alvo)
        # id_quem
        n = normalizar(original)
        if re.search(r"\bfalando\b", n):
            conversa = getattr(self.rt, "conversa", None)
            f = getattr(conversa, "falante", None)
            if not cad.ler()["vozes"]:
                return "Ainda não conheço a voz de ninguém. Diga: memorize minha voz."
            if not f or time.time() - f[2] > 60:
                return "Não ouvi ninguém ainda."
            return (f"Pela voz, é {'o ' + t if f[0] == DONO else f[0]}." if f[0]
                    else "Não reconheço essa voz.")
        if not cad.ler()["rostos"]:
            return "Ainda não conheço o rosto de ninguém. Diga: memorize meu rosto."
        img = self._quadro_agora(espera=4.0)
        if img is None or rostos_id is None:
            return "A câmera não mandou imagem. Ligue a câmera e tente de novo."
        pessoas = rostos_id.identificar(img)
        self.rt.pessoas = (time.time(), pessoas)
        if not pessoas:
            return "Não vejo ninguém de frente para a câmera."
        conhecidos = [('o ' + t) if p["nome"] == DONO else p["nome"] for p in pessoas if p["nome"]]
        desconhecidos = sum(1 for p in pessoas if not p["nome"])
        partes = conhecidos + ([f"{'uma pessoa' if desconhecidos == 1 else str(desconhecidos) + ' pessoas'} que não conheço"]
                               if desconhecidos else [])
        juntar = lambda xs: xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " e " + xs[-1]    # noqa: E731
        return f"Estou vendo {juntar(partes)}."

    def cancelar_cadastro(self) -> None:
        self._cadastro_cancelado.set()

    def _iniciar_cadastro_voz(self, alvo: str) -> str:
        conversa = getattr(self.rt, "conversa", None)
        if conversa is None:
            return "A conversa por voz não está disponível agora; o cadastro da voz não começou."
        if not getattr(self.rt, "falantes", None) or not self.rt.falantes.disponivel:
            return "O modelo local de reconhecimento de voz não está instalado; a voz não foi cadastrada."
        erro = conversa.iniciar_cadastro_voz(alvo)
        if isinstance(erro, str) and erro:
            return erro
        quem = "a sua voz" if alvo == "dono" else f"a voz de {alvo}"
        aviso = "" if alvo == "dono" else " Só cadastro quem estiver presente e de acordo."
        return (f"Vou cadastrar {quem}. Fale três frases quaisquer, uma de cada vez, com uns três segundos cada, "
                f"sem dizer Jarvis. A voz só será salva após as três amostras válidas. Para interromper, diga cancelar.{aviso}")

    def _cadastrar_rosto(self, alvo: str) -> str:
        from .identidade import LIMIAR_ROSTO, media, similaridade
        rostos_id = getattr(self.rt, "rostos_id", None)
        if rostos_id is None or not rostos_id.disponivel:
            return "O modelo local de rostos não está instalado; o rosto não foi cadastrado."
        if not self._trava_cadastro.acquire(blocking=False):
            return "Já há um cadastro de rosto em andamento. Aguarde ou diga cancelar cadastro de rosto."
        try:
            self._cadastro_cancelado.clear()
            img = self._quadro_agora(espera=4.0)
            if img is None:
                return "A câmera não mandou imagem. Ligue a câmera e tente de novo; o rosto não foi cadastrado."
            vetores, quadros = [], []
            fim = time.monotonic() + 8
            while time.monotonic() < fim and len(vetores) < 5:
                if self._cadastro_cancelado.is_set():
                    return "Cadastro do rosto cancelado; nenhuma amostra nova foi salva."
                if not self.rt.camera.ativa:
                    return "A câmera foi desligada. Cadastro do rosto cancelado."
                # Um quadro congelado nao conta como cinco observacoes novas.
                if not any(img is q for q in quadros):
                    quadros.append(img)
                    v = rostos_id.vetor_de_um_rosto(img)
                    if isinstance(v, int):
                        if v > 1:
                            return "Vejo mais de um rosto. Fique só a pessoa a cadastrar na frente da câmera."
                    elif v is not None:
                        if vetores and any(similaridade(v, anterior) < LIMIAR_ROSTO for anterior in vetores):
                            return "O rosto mudou entre as amostras. Cadastre uma pessoa por vez; nada foi salvo."
                        vetores.append(v)
                if len(vetores) < 5:
                    time.sleep(0.5)
                    novo = getattr(self.rt, "_ultimo_quadro", None)
                    if novo is not None:
                        img = novo
            if self._cadastro_cancelado.is_set():
                return "Cadastro do rosto cancelado; nenhuma amostra nova foi salva."
            if len(vetores) < 3:
                return "Não consegui três imagens novas e nítidas do rosto. Verifique a câmera e a iluminação e peça de novo."
            self.rt.identidades.salvar("rostos", alvo, media(vetores))
            self.rt.estado.registrar("identidade", f"rosto cadastrado: {alvo}")
            self._contexto({"tipo": "identidade", "titulo": "Cadastro do rosto salvo localmente",
                            "itens": [{"titulo": self._trat() if alvo == "dono" else alvo,
                                       "detalhe": f"{len(vetores)} amostras; imagens não armazenadas", "fonte": "câmera local"}]})
            return (f"Pronto, {self._trat()}. Cadastro do seu rosto salvo neste computador." if alvo == "dono" else
                    f"Cadastro do rosto de {alvo} salvo neste computador. Só cadastro quem está de acordo; "
                    f"para apagar, diga: esqueça o rosto de {alvo}.")
        finally:
            self._trava_cadastro.release()

    # ---- casa inteligente (rede local) --------------------------------------------------------------
    _casa_pendente: tuple[Callable[[], None], float, str] | None = None

    def _home_assistant(self):
        from .agenda import ler_segredo
        from .casa import HomeAssistant
        url, token = ler_segredo("ha_url"), ler_segredo("ha_token")
        if not (url and token):
            return None
        atual = getattr(self, "_ha", None)
        if atual is None or atual.url != url.rstrip("/"):
            self._ha = HomeAssistant(url, token)
        return self._ha

    def casa(self, nome: str, args: dict[str, str], original: str) -> str:
        from . import casa as cs
        t = self._trat()
        reg = self._servico("casa", cs.Casa)
        if nome == "casa_confirmar":
            pend, self._casa_pendente = self._casa_pendente, None
            if not pend or time.time() > pend[1]:
                return "Não havia nada esperando confirmação."
            try:
                pend[0]()
            except cs.ERROS as e:
                return f"O aparelho não respondeu: {str(e)[:80]}."
            return pend[2]
        if nome == "casa_descobrir":
            aparelhos = reg.descobrir()
            extra, ha = "", self._home_assistant()
            if ha:
                try:
                    n = sum(1 for e in ha.estados() if e["entity_id"].split(".")[0] in cs.DOMINIOS_CONTROLAVEIS)
                    extra = f" O Home Assistant tem {n} itens que eu controlo."
                except (*cs.ERROS, KeyError):
                    extra = " O Home Assistant não respondeu."
            self._contexto({"tipo": "casa", "titulo": "Aparelhos na rede de casa",
                            "itens": [{"titulo": a.get("apelido") or a["nome"], "detalhe": a["tipo"], "fonte": a.get("ip") or ""}
                                      for a in aparelhos[:12]] or [{"titulo": "Nenhum aparelho respondeu", "fonte": "rede local"}]})
            return cs.resumo_falado(aparelhos) + extra
        if nome == "casa_adicionar":
            regra = dict(REGRAS)[nome]
            ip = (grupo_original(original, regra, "ip") or "").replace(",", ".")
            apelido = grupo_original(original, regra, "nome") or "tomada"
            info = cs.sondar_rele(ip)
            if not info:
                return f"Não achei uma tomada Shelly ou Tasmota no endereço {ip}."
            reg.adicionar_manual(ip, apelido, info)
            return f"Pronto: {apelido} ({info['tipo']}) adicionado. Diga: ligue {apelido}."
        # controlar / volume
        n = normalizar(original)
        if nome == "casa_volume":
            alvo = args.get("alvo") or args.get("alvo2") or "tv"
            valor = int(args["n"]) if args.get("n") else None
            acao = "volume"
        else:
            alvo, verbo = args.get("alvo", ""), args.get("acao", "")
            acao = ("destrancar" if verbo.startswith(("destranc", "destranq")) else "trancar" if verbo.startswith(("tranc", "tranq"))
                    else "pausar" if verbo.startswith("paus") else "tocar" if verbo.startswith("continu")
                    else "abrir" if verbo.startswith("abr") else "fechar" if verbo.startswith("fech")
                    else "desligar" if verbo.startswith(("deslig", "apag")) else "ligar")
            valor = None
        ha = self._home_assistant()
        if ha:
            try:
                ent = cs.achar_entidade(ha.estados(), alvo)
            except (*cs.ERROS, KeyError):
                ent = None
            if ent:
                return self._casa_ha(ha, ent, acao, valor, n)
        dev = reg.achar(alvo)
        if dev and dev["tipo"] in ("Shelly", "Tasmota") and acao in ("ligar", "desligar", "abrir", "fechar"):
            try:
                cs.rele(dev, acao in ("ligar", "abrir"))
            except cs.ERROS as e:
                return f"{dev.get('apelido') or dev['nome']} não respondeu: {str(e)[:60]}."
            return f"{(dev.get('apelido') or dev['nome']).capitalize()} {'ligado' if acao in ('ligar', 'abrir') else 'desligado'}."
        if dev and dev["tipo"] == "midia":
            try:
                if nome == "casa_volume" and valor is None:
                    return "Diga o número: volume da TV em 20."
                cs.upnp(dev, {"ligar": "tocar", "desligar": "parar", "fechar": "parar", "abrir": "tocar"}.get(acao, acao), valor)
            except (*cs.ERROS, KeyError) as e:
                return f"{dev['nome']} não aceitou: {str(e)[:80]}."
            return f"Feito na {dev['nome']}." if acao != "volume" else f"Volume da {dev['nome']} em {valor}."
        return (f"Não achei {alvo} entre os aparelhos que controlo. Diga: quais aparelhos tem em casa, "
                f"ou conecte o Home Assistant no Painel, {t}.")

    def _casa_ha(self, ha, ent: dict[str, Any], acao: str, valor: int | None, n: str) -> str:
        from . import casa as cs
        dominio, ident = ent["entity_id"].split(".")[0], ent["entity_id"]
        nome_ent = (ent.get("attributes") or {}).get("friendly_name") or ident
        mapa = {"light": {"ligar": "turn_on", "abrir": "turn_on", "desligar": "turn_off", "fechar": "turn_off"},
                "switch": {"ligar": "turn_on", "desligar": "turn_off"}, "fan": {"ligar": "turn_on", "desligar": "turn_off"},
                "input_boolean": {"ligar": "turn_on", "desligar": "turn_off"}, "scene": {"ligar": "turn_on"},
                "climate": {"ligar": "turn_on", "desligar": "turn_off"},
                "cover": {"abrir": "open_cover", "ligar": "open_cover", "fechar": "close_cover", "desligar": "close_cover",
                          "pausar": "stop_cover"},
                "lock": {"trancar": "lock", "fechar": "lock", "destrancar": "unlock", "abrir": "unlock"},
                "media_player": {"ligar": "turn_on", "desligar": "turn_off", "pausar": "media_pause", "tocar": "media_play",
                                 "volume": "volume_set"}}
        servico = mapa.get(dominio, {}).get(acao)
        if not servico:
            return f"Não sei fazer isso com {nome_ent}."
        dados: dict[str, Any] = {"entity_id": ident}
        if servico == "volume_set":
            dados["volume_level"] = max(0, min(100, valor or 0)) / 100
        executar = lambda: ha.servico(dominio, servico, dados)            # noqa: E731
        if servico == "unlock" or (dominio == "cover" and re.search(r"\bportao|garagem\b", n) and servico == "open_cover"):
            self._casa_pendente = (executar, time.time() + 60, f"{nome_ent} {'destrancada' if servico == 'unlock' else 'abrindo'}.")
            return f"Por segurança, confirme: diga confirmo {'destrancar' if servico == 'unlock' else 'abrir'}."
        try:
            executar()
        except cs.ERROS as e:
            return f"O Home Assistant não aceitou: {str(e)[:80]}."
        feito = {"turn_on": "ligado", "turn_off": "desligado", "open_cover": "abrindo", "close_cover": "fechando",
                 "stop_cover": "parado", "lock": "trancado", "media_pause": "pausado", "media_play": "tocando",
                 "volume_set": f"no volume {valor}"}[servico]
        return f"{nome_ent}: {feito}."

    # ---- comunicacao ------------------------------------------------------------------------------
    def comunicar(self, nome: str, original: str) -> str:
        from .telegram import link_whatsapp
        regra = dict(REGRAS)[nome]
        if nome == "whatsapp":
            numero = grupo_original(original, regra, "num") or ""
            texto = re.sub(r"^(?:que|:)\s+", "", grupo_original(original, regra, "txt") or "")
            link = link_whatsapp(numero, texto)
            if not link or not texto:
                return "Diga o número e a mensagem. Por exemplo: mande no WhatsApp para 11 91234 5678 dizendo que vou atrasar."
            self._abrir_url(link)
            return "Abri o WhatsApp com a mensagem pronta. Confira e aperte enviar: eu não envio sozinho."
        ponte = getattr(self.rt, "telegram", None)
        texto = grupo_original(original, regra, "txt") or ""
        if ponte is None or ponte.chat is None:
            return "O celular ainda não está pareado. Configure o bot do Telegram no cartão Celular do Painel."
        if not texto:
            return "O que devo mandar para o seu celular?"
        return "Mandei para o seu celular." if ponte.enviar(texto) else "O Telegram não respondeu agora."

    # ---- engenharia --------------------------------------------------------------------------------
    def engenharia(self, nome: str, original: str) -> str | None:
        from . import cad
        from . import engenharia as eng
        if nome == "tarifa":
            v = eng.tarifa_dita(original)
            if v is None or not 0 < v < 10:
                return "Não entendi o valor. Diga, por exemplo: a tarifa de luz é 0,85."
            self.rt.prefs.aplicar({"tarifa_kwh": v})
            return f"Anotado: {eng.fmt(v, 2)} reais por quilowatt-hora."
        if nome == "projetar":
            pedido = eng.pedido_de_peca(original)
            if pedido is None:
                return None
            if isinstance(pedido, str):
                return pedido
            tipo, p = pedido
            # a peca entra no acervo com parametros e versao: sem isso "aumente
            # dois milimetros" nao teria sobre o que agir (§12)
            from .pecas import falar_versao
            try:
                # o nome e a IDENTIDADE da peca ("caixa"), nao a medida do dia:
                # depois de "aumente a largura", "caixa 80x50x30" seria mentira
                peca, avisos = self._pecas().criar(
                    tipo, p, nome=tipo,
                    projeto=self._projetos().projeto,
                    motivo=eng.gerar_peca(tipo, p)[2])       # "engrenagem de 20 dentes, modulo 1,82"
            except ValueError as e:
                from .discordancia import conflitos_de_peca, falar as falar_conflito
                conflitos = conflitos_de_peca(tipo, p)
                return falar_conflito(conflitos, original, self._trat()) or f"Não dá para fazer essa peça: {e}."
            versao = peca.atual()
            self.rt.ultimo_projeto = versao.arquivo
            self._peca_na_tela(peca)
            if versao.arquivo:
                self.mostrar_modelo(versao.arquivo)
            return (falar_versao(peca, versao, avisos, self._trat())
                    + " Está na mesa holográfica; para imprimir, diga: abra no Cura.")
        if nome == "cura_abrir":
            import subprocess
            from pathlib import Path
            alvo = getattr(self.rt, "ultimo_projeto", None) or getattr(self.rt, "holograma_modelo", None)
            if not alvo or not Path(alvo).is_file():
                return "Ainda não há peça para imprimir. Peça, por exemplo: projete uma caixa de 50 por 30 por 20 milímetros."
            exes = sorted(Path(r"C:\Program Files").glob("UltiMaker Cura*/UltiMaker-Cura.exe"), reverse=True)
            if not exes:
                return "Não achei o UltiMaker Cura instalado."
            subprocess.Popen([str(exes[0]), str(alvo)])
            return f"Abrindo {Path(alvo).stem} no Cura, {self._trat()}."
        if nome == "dados_analisar":
            from .documentos import achar
            q = grupo_original(original, dict(REGRAS)["dados_analisar"], "q") or ""
            caminho = achar(q or original, exts={".csv", ".tsv", ".xlsx", ".xlsm"})
            if not caminho:
                return (f"Não achei a planilha {q}. Procuro arquivos CSV e Excel em Documentos, Downloads e "
                        "Área de Trabalho." if q else "Qual arquivo? Diga, por exemplo: analise a planilha de gastos.")
            try:
                cab, linhas = eng.ler_tabela(caminho)
            except Exception as e:  # noqa: BLE001 - arquivo corrompido/aberto: explica
                return f"Não consegui ler {caminho.name}: {str(e)[:80]}."
            a = eng.analisar_tabela(cab, linhas)
            self._contexto({"tipo": "dados", "titulo": f"Análise · {caminho.name}",
                            "itens": [{"titulo": c["nome"], "detalhe": f"média {eng.fmt(c['media'])} · de {eng.fmt(c['min'])} a {eng.fmt(c['max'])}",
                                       "fonte": f"{c['n']} valores"} for c in a["colunas"][:8]]
                            or [{"titulo": "Sem colunas numéricas", "fonte": caminho.name}]})
            gr = eng.grafico_da_analise(caminho.stem, a)
            if gr:
                self._abrir_holograma()
                self._grafico_na_mesa(gr)
            return eng.falar_analise(caminho.stem, a) + (" O gráfico está na mesa holográfica." if gr else "")
        tarifa = self.rt.prefs.ler().get("tarifa_kwh") or None
        r = eng.consumo(original, tarifa) or eng.eletrica(original)
        if r:
            return r
        fis = eng.fisica(original)
        if fis:
            fala, gr = fis
            if gr:
                self._abrir_holograma()
                self._grafico_na_mesa(gr)
                fala += " Desenhei a trajetória na mesa holográfica."
            return fala
        return eng.peso_de_peca(original) or eng.material(original)

    # ---- mesa holografica ------------------------------------------------------------------------
    def _abrir_holograma(self) -> bool:
        """Abre a mesa (no projetor, em tela cheia, se houver 2o monitor). True = ja estava aberta."""
        from . import janelas
        from .holograma import projetor
        situacao = janelas.abrir("holograma", self.rt.porta)
        if situacao == "aberta" and projetor():
            def cheia():
                time.sleep(3.5)
                janelas.tela_cheia("holograma")
            threading.Thread(target=cheia, name="holograma-tela-cheia", daemon=True).start()
        return situacao == "focada"

    def _grafico_na_mesa(self, gr: dict[str, Any]) -> None:
        """Manda o grafico e guarda (a mesa que abrir depois pede o ultimo)."""
        self.rt.holograma_grafico = dict(gr, em=time.time())
        self._pagina({"acao": "holograma", "tipo": "grafico", "grafico": gr})

    def mostrar_modelo(self, caminho) -> None:
        """Coloca um .stl/.obj na mesa holografica (abre a mesa se precisar)."""
        from .apresentacao import Apresentacao
        apresentacao = self._servico("apresentacao", lambda: Apresentacao(
            lambda **c: self.rt.estado.atualizar("apresentacao", **c)))
        ident = apresentacao.preparar(Path_(str(caminho)))
        self.rt.holograma_modelo = Path_(str(caminho))      # str ou Path: a mesa sempre recebe Path
        ja = self._abrir_holograma()
        evento = {"acao": "holograma", "tipo": "modelo", "apresentacao_id": ident}
        self._pagina(evento)
        if not ja:                                              # pagina acabou de abrir: ela pede o modelo sozinha
            def reapresentar():
                if apresentacao.atual()["id"] == ident:
                    self._pagina(evento)
            threading.Timer(4.0, reapresentar).start()

    def holograma(self, nome: str, original: str) -> str:
        from . import janelas
        from .holograma import CRIPTOS, MOEDAS, achar_modelo, grafico_clima, grafico_cripto, grafico_moeda, projetor
        from .rede import ERROS_REDE
        t = self._trat()
        regra = dict(REGRAS)[nome]
        if nome == "holograma_abrir":
            self._abrir_holograma()
            return (f"Mesa holográfica aberta no projetor, {t}." if projetor() else
                    f"Mesa holográfica aberta, {t}. Com um projetor ligado como segundo monitor, ela abre nele em tela cheia.")
        if nome == "holograma_fechar":
            hwnd = janelas.achar(janelas.TITULOS["holograma"])
            if not hwnd:
                return "A mesa holográfica já estava fechada."
            import ctypes
            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)       # WM_CLOSE: fecha com calma
            return "Mesa holográfica fechada."
        if nome == "modelo_mostrar":
            q = grupo_original(original, regra, "q") or ""
            caminho = achar_modelo(q)
            if not caminho:
                return (f"Não achei nenhum modelo 3D chamado {q}. Procuro arquivos .stl e .obj em Documentos, "
                        "Área de Trabalho, Downloads e Documentos, Jarvis, Projetos.")
            self.mostrar_modelo(caminho)
            return f"Solicitei a apresentação de {caminho.stem} na mesa; o painel registra quando a tela confirmar o carregamento."
        if nome == "modelo_girar":
            parar = bool(re.search(r"\bpar\w*", normalizar(original)))
            self._pagina({"acao": "holograma", "tipo": "girar", "ligado": not parar})
            return "Parei de girar." if parar else "Girando."
        if nome == "modelo_zoom":
            mais = bool(re.search(r"\b(?:aument|aproxim)", normalizar(original)))
            self._pagina({"acao": "holograma", "tipo": "zoom", "fator": 1.4 if mais else 1 / 1.4})
            return "Aproximando." if mais else "Afastando."
        # grafico
        q = normalizar(grupo_original(original, regra, "q") or "")
        try:
            chave = next((k for k in MOEDAS if k in q), None)
            if chave:
                gr = grafico_moeda(chave)
            elif (chave := next((k for k in CRIPTOS if k in q), None)):
                gr = grafico_cripto(chave)
            elif re.search(r"\b(?:clima|tempo|temperatura)\b", q):
                local = self.rt.prefs.ler().get("local_clima")
                if not local:
                    return "Ainda não sei a sua cidade. Defina no cartão Clima do Painel."
                gr = grafico_clima(local)
            elif re.search(r"\b(?:processador|cpu|memoria|ram|computador|pc)\b", q):
                self._abrir_holograma()
                self._pagina({"acao": "holograma", "tipo": "grafico", "grafico": {"titulo": "", "series": [], "em": 0}})
                return "O uso do computador ao vivo está na mesa holográfica."
            else:
                return "Faço gráficos do dólar, euro, libra, bitcoin, ethereum, da temperatura e do uso do computador."
        except ERROS_REDE:
            return "Não consegui buscar os dados do gráfico agora."
        except (KeyError, TypeError, ValueError):
            return "A fonte dos dados respondeu num formato que não entendi."
        if not gr["series"][0]["pontos"]:
            return "A fonte não mandou dados para o gráfico."
        self._abrir_holograma()
        self._grafico_na_mesa(gr)
        if "variacao" in gr:
            v = gr["variacao"]
            pts = gr["series"][0]["pontos"]
            ini, fim = (f"{p[1]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") for p in (pts[0], pts[-1]))
            pct = f"{abs(v):.1f}".replace(".", ",")
            return (f"{gr['nome']} nos últimos 30 dias: de {ini} para {fim} reais, "
                    f"{'alta' if v >= 0 else 'queda'} de {pct} por cento. Está na mesa holográfica.")
        return (f"Temperatura em {gr['nome']} nas próximas 24 horas: mínima de {round(gr['minimo'])} e máxima de "
                f"{round(gr['maximo'])} graus. Está na mesa holográfica.")

    # ---- regua virtual ---------------------------------------------------------------------------
    def _quadro_agora(self, espera: float = 6.0):
        """Quadro atual da camera (liga se estiver desligada: o Senhor pediu para olhar)."""
        cam = getattr(self.rt, "camera", None)
        if cam is None:
            return None
        ligou = not cam.ativa
        anterior = getattr(self.rt, "_ultimo_quadro", None)
        if ligou:
            cam.ativar()
            espera = max(espera, 12.0)   # abrir a webcam no Windows leva ~3 s (e o cadastro
                                         # de rosto falhava dizendo "a camera nao mandou imagem")
        fim = time.time() + espera
        while time.time() < fim:
            q = getattr(self.rt, "_ultimo_quadro", None)
            if q is not None and cam.ativa and (not ligou or q is not anterior):
                if ligou:
                    time.sleep(1.5)                          # a exposicao da camera acerta nos primeiros quadros
                    q = getattr(self.rt, "_ultimo_quadro", q)
                return q
            time.sleep(0.2)
        return None

    def regua(self, nome: str, original: str) -> str:
        from .deteccao import CLASSES, NAO_OBJETOS, classe_na_frase
        from .olhar import REGIOES
        from .regua import REFERENCIAS, Regua, medida_falada
        rg = self._servico("regua", Regua)
        n = normalizar(original)
        if nome == "regua_calibrar":
            ref = "cartao" if re.search(r"\bcartao\b", n) else "carta" if re.search(r"\b(?:folha|papel) carta\b", n) else "a4"
            img = self._quadro_agora()
            if img is None:
                return "A câmera não mandou imagem. Ligue a câmera e tente de novo."
            d = rg.calibrar(img, ref)
            nome_ref = REFERENCIAS[ref][0]
            if not d:
                return (f"Não achei {nome_ref} na imagem. Deixe inteira à vista, deitada na mesa, com o lado maior "
                        "da esquerda para a direita e boa luz, e peça de novo.")
            self.rt.estado.publicar("medida", {"cantos": d["cantos"], "rotulo": f"REFERÊNCIA · {ref.upper()}", "em": time.time()})
            return (f"Régua calibrada com {nome_ref}, {self._trat()}. Pode tirar a folha e perguntar: quanto mede isso? "
                    "Objetos deitados na mesa medem melhor. Se a câmera mudar de lugar, calibre de novo.")
        if not rg.calibrada:
            return ("Ainda não calibrei a régua. Coloque uma folha A4 deitada na mesa, com o lado maior da esquerda "
                    "para a direita, na frente da câmera, e diga: Jarvis, calibre a régua.")
        img = self._quadro_agora()
        if img is None:
            return "A câmera não mandou imagem. Ligue a câmera e tente de novo."
        c = classe_na_frase(original)
        v = getattr(self.rt, "visao_continua", None)
        objs = (v.aguardar(3.0) or v.recentes(2.0) or []) if v is not None and v.detector.disponivel else []
        if c is not None:
            candidatos = [o for o in objs if o["classe"] == c]
        else:                                                  # "isso": o maior objeto que nao e pessoa nem movel
            candidatos = [o for o in objs if o["classe"] != 0 and CLASSES[o["classe"]][0] not in NAO_OBJETOS]
        alvo = max(candidatos, key=lambda o: o["w"] * o["h"] * o["conf"]) if candidatos else None
        if c is not None and alvo is None:
            s, _, g = CLASSES[c]
            return f"Não vejo {'a' if g == 'f' else 'o'} {s} na câmera agora."
        if alvo is not None:
            caixa, rotulo = (alvo["x"], alvo["y"], alvo["w"], alvo["h"]), alvo["nome"]
        else:
            regiao = self.rt.prefs.ler().get("visao_regiao", "centro")
            caixa, rotulo = REGIOES.get(regiao, REGIOES["centro"]), None
        m = rg.medir(img, caixa)
        if m is None:
            return "Não consegui separar o objeto da mesa. Tente com ele deitado e com mais luz."
        texto = f"{m['comprimento']:.1f} × {m['largura']:.1f} cm".replace(".", ",")
        self.rt.estado.publicar("medida", {"cantos": m["cantos"], "rotulo": f"{(rotulo or 'objeto').upper()} · {texto}",
                                           "em": time.time()})
        self._contexto({"tipo": "medida", "titulo": "Régua virtual",
                        "itens": [{"titulo": rotulo or "objeto", "detalhe": texto, "fonte": "câmera calibrada"}]})
        return medida_falada(m, f"{'a' if CLASSES[alvo['classe']][2] == 'f' else 'o'} {rotulo}" if alvo else None)

    # ---- diagnostico no estilo da armadura e consumo ------------------------------------------
    def armadura(self) -> str:
        """Diagnóstico das evidências e das tarefas afetadas, sem ativar componentes."""
        from .capacidades import relatorio_capacidades
        rel = relatorio_capacidades(self.rt)
        self.rt.estado.atualizar("conversa", diagnostico=rel)
        self.rt.estado.atualizar("contexto", tipo="diagnostico", titulo="Capacidades e dependências", em=rel["em"],
                                itens=[{"titulo": i["titulo"], "detalhe": f"{i['estado']}: {i['detalhe']} "
                                        f"Afeta: {', '.join(i['efeitos'])}.", "fonte": i["fonte"], "em": i["em"]}
                                       for i in rel["componentes"]])
        return rel["texto"]

    def preparar_reuniao(self, original: str) -> str:
        from .reunioes import preparar_reuniao
        agenda = getattr(self.rt, "agenda", None)
        dados = agenda.obter(forcar=True) if agenda else {"status": "nao_configurado"}
        tarefas = getattr(self.rt, "tarefas", None)
        consulta = grupo_original(original, dict(REGRAS)["reuniao_preparar"], "consulta") or ""
        con = self._conhecimento() if dados.get("status") == "medido" else None
        resultado = preparar_reuniao(dados, consulta, conhecimento=con,
                                     tarefas=tarefas.listar() if tarefas else [])
        self.rt.estado.atualizar("conversa", preparacao_reuniao=resultado)
        itens = []
        if resultado["evento"]:
            e = resultado["evento"]
            itens.append({"titulo": e["titulo"], "detalhe": datetime.fromtimestamp(e["inicio"]).strftime("%d/%m às %H:%M"),
                          "fonte": resultado["fonte"], "em": resultado["agenda_em"]})
        itens.extend({"titulo": e["titulo"], "detalhe": datetime.fromtimestamp(e["inicio"]).strftime("%d/%m às %H:%M"),
                      "fonte": resultado["fonte"]} for e in resultado["candidatos"])
        itens.extend({"titulo": m["titulo"], "detalhe": m["trecho"], "fonte": m["fonte"]} for m in resultado["materiais"])
        itens.extend({"titulo": t["texto"], "detalhe": t["criterio"], "fonte": "tarefas locais"} for t in resultado["tarefas"])
        itens.extend({"titulo": p, "fonte": "pendência"} for p in resultado["pendencias"])
        self.rt.estado.atualizar("contexto", tipo="reuniao", titulo="Preparação da reunião", em=resultado["em"],
                                itens=itens or [{"titulo": resultado["texto"], "fonte": "agenda"}])
        return resultado["texto"]

    NOMES_PROCESSO = {"msedge": "Edge", "chrome": "Chrome", "firefox": "Firefox", "ollama": "Ollama",
                      "ollama app": "Ollama", "ollama_llama_server": "Ollama", "llama-server": "Ollama",
                      "python": "Python e o Jarvis", "pythonw": "Python e o Jarvis", "claude": "Claude",
                      "code": "VS Code", "explorer": "Explorador de Arquivos", "msmpeng": "antivírus do Windows",
                      "svchost": "serviços do Windows", "dwm": "a interface do Windows", "discord": "Discord",
                      "spotify": "Spotify", "steam": "Steam", "memory compression": "compressão de memória do Windows",
                      "searchhost": "busca do Windows", "windowsterminal": "Terminal",
                      "memcompression": "compressão de memória do Windows", "audiodg": "áudio do Windows"}

    def consumo(self, original: str) -> str:
        """Quem mais usa processador (o que mais puxa a bateria) e memoria, medido por 1 s."""
        import psutil
        so_memoria = bool(re.search(r"\bmemoria\b|\bram\b", normalizar(original)))
        procs = list(psutil.process_iter(["name"]))
        for p in procs:
            try:
                p.cpu_percent(None)
            except psutil.Error:
                pass
        time.sleep(1.0)
        ncpu = psutil.cpu_count() or 1
        cpu: dict[str, float] = {}
        ram: dict[str, float] = {}
        for p in procs:
            try:
                bruto = (p.info.get("name") or "").removesuffix(".exe").removesuffix(".EXE")
                if not bruto or bruto.lower() in ("system idle process", "idle", "system", "registry"):
                    continue
                nome = self.NOMES_PROCESSO.get(bruto.lower(), bruto)
                cpu[nome] = cpu.get(nome, 0.0) + p.cpu_percent(None) / ncpu
                ram[nome] = ram.get(nome, 0.0) + p.memory_info().rss
            except psutil.Error:
                continue
        top_cpu = [(n, v) for n, v in sorted(cpu.items(), key=lambda kv: -kv[1])[:3] if v >= 1]
        top_ram = sorted(ram.items(), key=lambda kv: -kv[1])[:3]

        def gb(v: float) -> str:
            return f"{v / 1e9:.1f} gigas".replace(".", ",") if v >= 1e9 else f"{round(v / 1e6)} megas"
        self._contexto({"tipo": "diagnostico", "titulo": "Consumo agora",
                        "itens": [{"titulo": n, "detalhe": f"{round(v)}% da CPU", "fonte": "processador"} for n, v in top_cpu]
                        + [{"titulo": n, "detalhe": gb(v), "fonte": "memória"} for n, v in top_ram]})
        f_ram = "; ".join(f"{n}, {gb(v)}" for n, v in top_ram)
        if so_memoria:
            return f"Quem mais ocupa a memória agora: {f_ram}."
        f_cpu = "; ".join(f"{n}, {round(v)} por cento" for n, v in top_cpu) or "nada acima de 1 por cento"
        return (f"No processador, que é o que mais puxa a bateria: {f_cpu}. "
                f"Na memória: {f_ram}.")

    def perceber(self, nome: str, args: dict[str, str], original: str) -> str | None:
        from .deteccao import CLASSES, classe_citada, quantidade, resumo
        from .deteccao import juntar as juntar_partes
        from .percepcao import posicao
        p = getattr(self.rt, "percepcao", None)
        v = self._detector_pronto() if nome in ("percepcao_ver", "percepcao_onde", "percepcao_contar") else None
        if nome == "percepcao_contar":
            c = classe_citada(grupo_original(original, dict(REGRAS)[nome], "q") or args.get("q", ""))
            if c is None:
                return None                                    # nao e algo que o detector conhece: vai ao modelo
            if v is None:
                return "Para contar, preciso da visão em tempo real e da câmera."
            objs = v.aguardar()
            if objs is None:
                return "A câmera ainda não mandou imagem. Tente de novo em instantes."
            n = sum(1 for o in objs if o["classe"] == c)
            s, _, g = CLASSES[c]
            return f"Vejo {quantidade(n, c)}." if n else f"Não vejo nenhum{'a' if g == 'f' else ''} {s} agora."
        if nome == "percepcao_ver" and v is not None:
            objs = v.aguardar()
            if objs is not None:
                frase = f"Agora vejo {resumo(objs)}." if objs else "Agora não vejo nenhum objeto que eu conheça."
                self._contexto({"tipo": "percepcao", "titulo": "Visão em tempo real",
                                "itens": [{"titulo": o["nome"], "detalhe": f"{round(o['conf'] * 100)}%", "fonte": posicao(o)}
                                          for o in objs[:8]] or [{"titulo": "Nada reconhecido", "fonte": "câmera"}]})
                if p is not None and not self.rt._olhando.is_set():
                    threading.Thread(target=self._detalhar, name="detalhar", daemon=True).start()
                    frase += " Vou olhar os detalhes."
                return frase
        if p is None:
            return "A percepção visual não está disponível agora."
        if nome == "percepcao_onde":
            q = (grupo_original(original, dict(REGRAS)[nome], "q") or grupo_original(original, dict(REGRAS)[nome], "q2")
                 or args.get("q") or args.get("q2") or "")
            c = classe_citada(q)
            if v is not None and c is not None:                # o detector conhece: resposta na hora
                achados = sorted((o for o in (v.aguardar() or []) if o["classe"] == c), key=lambda o: -o["conf"])
                s, _, g = CLASSES[c]
                art = "a" if g == "f" else "o"
                if len(achados) == 1:
                    return f"{art.upper()} {s} está {posicao(achados[0])}, {self._trat()}."
                if achados:
                    return f"Vejo {quantidade(len(achados), c)}: " + juntar_partes([posicao(o) for o in achados[:4]]) + "."
                # nao esta na camera AGORA: e a ultima vez que vi, dita como ultima vez
                seguidor = getattr(v, "rastreador", None)
                trilhas = [t for t in (seguidor.todos() if seguidor else []) if t.classe == c and t.firme]
                if trilhas:
                    from .rastreador import falar_ultima_vez
                    return falar_ultima_vez(max(trilhas, key=lambda t: t.visto_em), tratamento=self._trat())
                if not p.recente():
                    return f"Não vejo {art} {s} na câmera agora."
            if not p.recente():
                self.rt.olhar_agora()
            return p.onde_esta(q.strip())
        r = self.rt.olhar_agora() if (nome == "percepcao_mudou" or not p.recente()) else p.atual
        if r is None and not p.atual:
            return "Não consegui olhar agora: a câmera não mandou imagem ou já estou analisando."
        if nome == "percepcao_mudou":
            return p.mudou()
        from .percepcao import posicao
        atual = r or p.atual
        self._contexto({"tipo": "percepcao", "titulo": f"Percepção · região {atual.get('regiao') or 'centro'}",
                        "itens": [{"titulo": o["nome"], "detalhe": o["detalhe"] or None, "fonte": posicao(o)}
                                  for o in atual["objetos"]]
                                 or [{"titulo": "Nada em destaque", "fonte": atual.get("cena") or ""}]})
        return p.descrever(atual)

    def tocar(self, q: str, onde: str = "youtube") -> str:
        """ "toque Back in Black": abre o primeiro video (toca sozinho) ou a busca do Spotify."""
        import os
        q = q.strip(" .!?")
        if len(q) < 2:
            return "O que devo tocar?"
        if onde == "spotify":
            if achar_app("spotify"):
                os.startfile("spotify:search:" + urllib.parse.quote(q))
                return f"Abri {q} no Spotify."
            self._abrir_url("https://open.spotify.com/search/" + urllib.parse.quote(q))
            return f"Abri a busca de {q} no Spotify."
        from .rede import ERROS_REDE, baixar
        try:
            pagina = baixar("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": q}),
                            3_000_000).decode("utf-8", "replace")
            m = re.search(r'"videoId":"([\w-]{11})"', pagina)
        except ERROS_REDE:
            m = None
        if m:
            self._abrir_url(f"https://www.youtube.com/watch?v={m.group(1)}")
            return f"Tocando {q}, {self._trat()}."
        self._abrir_url("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": q}))
        return f"Abri a busca de {q} no YouTube."

    def mundo(self, nome: str, original: str) -> str | None:
        from .utilidades import achar_cidade, hora_em
        cidade = grupo_original(original, dict(REGRAS)[nome], "cidade") or ""
        cidade = re.sub(r"\s+(?:hoje|amanh[aã]|agora)$", "", cidade.strip(), flags=re.I)
        if nome == "hora_mundo":
            return hora_em(cidade)
        p = self.rt.prefs.ler()
        configuradas = [c for c in [p.get("local_clima"), *(p.get("climas_extras") or [])] if c]
        if any(normalizar(c["nome"]) == normalizar(cidade) for c in configuradas):
            return None                                   # as suas cidades: resumo completo da voz
        c = achar_cidade(cidade)
        if not c or not getattr(self.rt, "clima", None):
            return f"Não achei a cidade {cidade}."
        r = self.rt.clima.resumo_falado({"nome": c["nome"], "lat": c["lat"], "lon": c["lon"],
                                         "regiao": c.get("regiao"), "pais": c.get("pais")})
        return r or "Não consegui o clima agora."

    def listar(self, nome: str, args: dict[str, str], original: str) -> str:
        from .listas import Listas, juntar, nome_lista, separar_itens
        ls = self._servico("listas", Listas)
        regra = dict(REGRAS)[nome]
        lista = nome_lista(grupo_original(original, regra, "lista"))
        rot = f"lista de {lista}"
        if nome == "lista_add":
            itens = separar_itens(grupo_original(original, regra, "itens") or "")
            novos = ls.adicionar(lista, itens)
            if not novos:
                return f"Já estava na {rot}."
            return f"Adicionei {juntar(novos)} à {rot}."
        if nome == "lista_tirar":
            tirado = ls.remover(lista, grupo_original(original, regra, "item") or "")
            return f"Tirei {tirado} da {rot}." if tirado else f"Não achei isso na {rot}."
        if nome == "lista_limpar":
            n = ls.limpar(lista)
            return f"{rot.capitalize()} limpa ({n} ite{'m' if n == 1 else 'ns'})." if n else f"A {rot} já estava vazia."
        itens = ls.ler(lista)
        if not itens:
            return f"A {rot} está vazia."
        self._contexto({"tipo": "lista", "titulo": rot.capitalize(), "itens": [{"titulo": i} for i in itens]})
        return f"Na {rot}: {juntar(itens)}."

    def resumir_documento(self, frase: str) -> str:
        from . import tela
        from .documentos import achar, fala, resumir
        from .modelo import ErroModelo, gerar
        janela = tela.janela_de_trabalho()
        arq = achar(frase, janela[1] if janela else None)
        if not arq:
            return ("Não achei o arquivo. Diga o nome, por exemplo: resuma o relatório de vendas, "
                    "ou: resuma o último PDF baixado.")
        modelo = self.rt.prefs.ler().get("modelo_voz")
        try:
            r = resumir(arq, lambda m: gerar(m, modelo, max_tokens=350))
        except (ValueError, OSError) as e:
            return f"Não consegui ler {arq.name}: {e}."
        except ErroModelo as e:
            return f"Li {arq.name}, mas não consegui resumir: {e}."
        self._contexto({"tipo": "documento", "titulo": f"Resumo · {r['nome']}",
                        "itens": [{"titulo": r["nome"], "detalhe": r["resumo"][:700], "fonte": str(arq.parent)}]})
        return fala(r)

    def analisar_midia(self, frase: str) -> str:
        from .documentos import achar
        from .midia_arquivos import EXTS_AUDIO, EXTS_VIDEO, analisar, fala
        from .modelo import ErroModelo, gerar
        from .planilhas import pasta_documentos
        arq = achar(frase, None, exts=EXTS_AUDIO | EXTS_VIDEO)
        if not arq:
            return "Não achei o arquivo. Diga o nome, ou: transcreva o último áudio baixado."
        modelo = self.rt.prefs.ler().get("modelo_voz")
        visao = getattr(self.rt, "visao", None)
        try:
            r = analisar(arq, self.rt.transcricao, pasta_documentos() / "Jarvis" / "Transcrições",
                         descrever=(lambda jpg, p: visao.perguntar_imagem(jpg, p, 60)) if visao else None,
                         resumir=lambda m: gerar(m, modelo, max_tokens=250))
        except ErroModelo as e:
            return f"Transcrevi {arq.name}, mas não consegui resumir: {e}."
        except (RuntimeError, OSError, ValueError) as e:
            return f"Não consegui analisar {arq.name}: {e}."
        self._contexto({"tipo": "midia", "titulo": f"{'Vídeo' if r['video'] else 'Áudio'} · {r['nome']}",
                        "itens": [{"titulo": f"{r['segmentos']} trechos transcritos", "detalhe": (r["resumo"] or r["inicio"])[:600],
                                   "fonte": nome_arquivo(r["saida"])}]
                        + [{"titulo": f"Cena aos {int(t // 60)}:{int(t % 60):02d}", "detalhe": d} for t, d in r["cenas"]]})
        return fala(r)

    def criar_programa(self, pedido: str) -> str:
        from .modelo import ErroModelo, gerar
        from .programas import Programas, fala
        modelo = self.rt.prefs.ler().get("modelo_voz")
        svc = self._servico("programas", lambda: Programas(lambda msgs: gerar(msgs, modelo, max_tokens=1200,
                                                                                  temperatura=0.2)))
        try:
            r = svc.criar(pedido)
        except ErroModelo as e:
            return f"Não consegui escrever o programa agora: {e}."
        self._contexto({"tipo": "arquivo", "titulo": "Programa gerado (não executado)",
                        "itens": [{"titulo": nome_arquivo(r["arquivo"]),
                                   "detalhe": (r["erro"] or "sintaxe ok") + ("; " + "; ".join(r["avisos"]) if r["avisos"] else ""),
                                   "fonte": f"aberto no {r['aberto_em']}"}]})
        return fala(r)

    def criar_rascunho(self, pedido: str) -> str:
        from .modelo import ErroModelo, gerar
        from .rascunhos import Rascunhos, cartao, fala
        modelo = self.rt.prefs.ler().get("modelo_voz")
        svc = self._servico("rascunhos", lambda: Rascunhos(lambda msgs: gerar(msgs, modelo, max_tokens=450)))
        try:
            r = svc.criar(pedido)
        except ErroModelo as e:
            return f"Não consegui redigir agora: {e}."
        self._contexto(cartao(r))
        return fala(r)

    def monitorar(self, nome: str, args: dict[str, str], original: str) -> str:
        from .monitores import descrever, numero_falado
        t = self._trat()
        if nome == "modo_proativo":
            n = normalizar(original)
            modo = ("sob_demanda" if re.search(r"sob demanda|quando eu (?:chamar|pedir)", n)
                    else "proativo" if re.search(r"proativo|falar sozinho", n) else "assistido")
            self.rt.prefs.aplicar({"modo_proativo": modo})
            self.rt._publicar_prefs()
            return {"sob_demanda": f"Certo, {t}. Só falo quando o senhor chamar, além dos lembretes e monitores que pediu.",
                    "assistido": "Modo assistido: aviso compromissos, lembretes e o que for importante.",
                    "proativo": "Modo proativo: também aviso e-mails novos e o que eu notar."}[modo]
        mon = getattr(self.rt, "monitores", None)
        if mon is None:
            return "Os monitores não estão ativos agora."
        try:
            if nome == "monitor_noticia":
                q = grupo_original(original, dict(REGRAS)[nome], "q") or args.get("q", "")
                m = mon.criar("noticia", re.sub(r"^(?:o|a|os|as)\s+", "", q.strip(" .?!"), flags=re.I))
                return f"Certo. Aviso quando sair notícia sobre {m['alvo']}. Confiro a cada meia hora."
            if nome == "monitor_cotacao":
                from .cotacoes import ativos_citados, reais_falados
                ativos = ativos_citados(original)
                v = numero_falado(args.get("v", "").rstrip(".,"))
                if not ativos or v is None:
                    return "De qual valor? Diga, por exemplo: me avise quando o dólar passar de 5,50."
                classe, codigo = ativos[0]
                direcao = "abaixo" if re.search(r"abaixo|baixar|descer|cair", args.get("dir", "")) else "acima"
                from .cotacoes import CRIPTOS, MOEDAS
                nome_ativo = (next(n for c, n, _ in MOEDAS.values() if c == codigo) if classe == "moeda"
                              else next(n for c, n in CRIPTOS.values() if c == codigo))
                mon.criar("cotacao", codigo, classe=classe, codigo=codigo, limite=v, direcao=direcao, nome=nome_ativo)
                return (f"Certo. Aviso quando o {nome_ativo} {'passar de' if direcao == 'acima' else 'cair abaixo de'} "
                        f"{reais_falados(v)}. Confiro a cada 10 minutos.")
            if nome == "monitor_site":
                u = args.get("u", "").strip(".,;")
                u = u if u.startswith("https://") else "https://" + re.sub(r"^https?://", "", u)
                m = mon.criar("site", u)
                return f"Certo. Aviso quando {descrever(m)} mudar."
            if nome == "monitor_pasta":
                from .documentos import pasta_conhecida
                alvo = grupo_original(original, dict(REGRAS)[nome], "p") or ""
                n = normalizar(alvo)
                conhecida = next((k for k in ("downloads", "documentos", "area de trabalho") if k in n), None)
                caminho = str(pasta_conhecida(conhecida)) if conhecida else alvo
                m = mon.criar("pasta", caminho)
                return f"Certo. Aviso quando chegar arquivo novo em {descrever(m).split('pasta ', 1)[-1]}."
            if nome == "monitores_listar":
                itens = mon.publico()
                if not itens:
                    return "Nenhum monitor. Diga, por exemplo: me avise quando sair notícia sobre a Nvidia."
                self._contexto({"tipo": "monitores", "titulo": "Monitores", "itens": [
                    {"titulo": x["descricao"], "fonte": ("ativo" if x["ativo"] else "pausado") + f" · {x['disparos']} aviso(s)"}
                    for x in itens]})
                return "Estou de olho em: " + "; ".join(x["descricao"] + ("" if x["ativo"] else " (pausado)") for x in itens[:5]) + "."
            if nome == "monitor_mudar":
                alvos = mon.achar(original)
                if not alvos:
                    return "Não achei esse monitor. Diga: quais são meus monitores."
                if len(alvos) > 1 and not re.search(r"\btod[oa]s\b", normalizar(original)):
                    return "Qual deles: " + "; ".join(descrever(m) for m in alvos[:4]) + "?"
                acao = args.get("acao", "")
                ativo = None if re.match(r"remov|apag|cancel|exclu", acao) else (acao.startswith(("retom", "reativ")))
                k = mon.mudar([m["id"] for m in alvos], ativo)
                verbo = "removido" if ativo is None else ("retomado" if ativo else "pausado")
                return f"Monitor {verbo}: {descrever(alvos[0])}." if k == 1 else f"{k} monitores {verbo}s."
        except ValueError as e:
            return f"Não consegui: {e}."
        return None

    def memoria(self, nome: str, original: str) -> str:
        from .memoria import Memoria, parece_segredo
        mem = self._servico("memoria", Memoria)
        t = self._trat()
        regra = dict(REGRAS)[nome]
        fato = grupo_original(original, regra, "fato") if nome in ("memoria_guardar", "memoria_esquecer",
                                                                    "memoria_corrigir") else None
        if nome == "memoria_guardar":
            from .secretario import interpretar_quando
            if interpretar_quando(fato or "")[0]:               # tem horario: e lembrete
                return self.executar("lembrete", {}, original)
            if parece_segredo(fato or ""):
                return f"Não guardo senhas, códigos ou dados de cartão, {t}."
            if not fato:
                return "O que devo guardar?"
            return f"Guardado na memória: {fato}." if mem.guardar(fato) else "Eu já sabia disso."
        if nome == "memoria_listar":
            itens = mem.listar()
            if not itens:
                return f"Ainda não guardei nada sobre o senhor. Diga, por exemplo: Jarvis, lembre que prefiro café sem açúcar."
            self._contexto({"tipo": "memoria", "titulo": f"Memória · {len(itens)} fato{'s' if len(itens) > 1 else ''}",
                            "itens": [{"titulo": f.text, "fonte": "dito pelo senhor" if f.source == "hud-voz"
                                       else "extraído das conversas"} for _, f in itens[:8]]})
            return "Sei que: " + "; ".join(f.text.rstrip(".") for _, f in itens[:5]) + "."
        if nome == "memoria_esquecer":
            achados = mem.achar(fato or "")
            if not achados:
                return "Não encontrei isso na memória."
            if len(achados) > 1:
                opcoes = "; ".join(f.text.rstrip(".") for _, f in achados[:3])
                return f"Encontrei mais de um: {opcoes}. Diga qual, com mais detalhe."
            i, f = achados[0]
            return f"Esquecido: {f.text.rstrip('.')}." if mem.esquecer(i, f.text) else "A memória mudou; tente de novo."
        if nome == "memoria_corrigir":
            if not fato or parece_segredo(fato):
                return "O que devo corrigir?" if not fato else f"Não guardo senhas, códigos ou dados de cartão, {t}."
            try:
                antigo = mem.corrigir(fato)
            except ValueError as e:
                return f"Não alterei a memória: {e}."
            return f"Corrigido. Antes: {antigo.rstrip('.')}. Agora: {fato}." if antigo else f"Guardado na memória: {fato}."
        if nome == "memoria_limpar":
            n = mem.contar()
            if not n:
                return "A memória já está vazia."
            self._limpeza_memoria_ate = time.time() + 120
            return (f"Isso apaga os {n} fatos que guardei sobre o senhor. "
                    "Para confirmar, diga: Jarvis, confirmo, apague toda a memória.")
        if nome == "memoria_limpar_confirmado":
            if time.time() > self._limpeza_memoria_ate:
                return "Não havia pedido de limpeza pendente. Diga primeiro: apague toda a memória."
            self._limpeza_memoria_ate = 0.0
            n = mem.limpar()
            return f"Memória apagada: {n} fato{'s' if n != 1 else ''}."
        return None

    def falar_lembretes(self) -> str:
        from .secretario import falar_repeticao
        pend = self.rt.secretario.pendentes()
        if not pend:
            return "Você não tem lembretes pendentes."
        partes = [f"{x['texto']}, {falar_repeticao(x)}" for x in pend[:4]]
        return f"Você tem {len(pend)} lembrete{'s' if len(pend) > 1 else ''}: " + "; ".join(partes) + "."

    def _qual_lembrete(self, pend: list[dict[str, Any]], verbo: str) -> str:
        from .secretario import falar_repeticao
        opcoes = "; ".join(f"{x['texto']}, {falar_repeticao(x)}" for x in pend[:4])
        return f"Você tem {len(pend)} lembretes: {opcoes}. Qual devo {verbo}? Diga, por exemplo: o das 15h."

    def cancelar_lembretes(self, frase: str) -> str:
        sec = self.rt.secretario
        pend = sec.pendentes()
        if not pend:
            return "Não havia lembretes pendentes."
        n = normalizar(frase)
        alvos = [] if re.search(r"\btod[oa]s\b", n) else sec.achar(frase)
        if not alvos:
            plural = re.search(r"\btod[oa]s\b|\b(?:lembretes|timers|alarmes|temporizadores)\b", n)
            if plural or len(pend) == 1:
                alvos = pend
            else:
                return self._qual_lembrete(pend, "cancelar")
        k = sec.cancelar(ids=[x["id"] for x in alvos])
        return f"Cancelado: {alvos[0]['texto']}." if k == 1 else f"{k} lembretes cancelados."

    def adiar_lembrete(self, frase: str, args: dict[str, str]) -> str:
        """ "adie o lembrete em 10 minutos", "adie o das 15h para as 16h", "mais 5 minutos" (soneca)."""
        from .secretario import _REL, _n, falar_quando, interpretar_quando, proxima_ocorrencia
        sec = self.rt.secretario
        agora = datetime.now()
        if args.get("n"):
            delta, absoluto = timedelta(minutes=_n(args["n"]) or 10), None
        else:
            quando, _ = interpretar_quando(frase, agora)
            relativo = bool(_REL.search(frase))
            delta = (quando - agora) if (quando and relativo) else timedelta(minutes=10)
            absoluto = quando if (quando and not relativo) else None
        uv = getattr(sec, "ultimo_vencido", None)
        alvos = sec.achar(frase)
        if not alvos and uv and time.time() - uv.get("vencido_em", 0) < 15 * 60:     # soneca
            novo = absoluto or agora + delta
            sec.lembrar(uv["texto"], novo, uv.get("tipo", "lembrete"))
            return f"Certo. Aviso de novo {falar_quando(novo, agora)}."
        pend = sec.pendentes()
        if not alvos:
            if len(pend) > 1 and not re.search(r"\bproximo\b", normalizar(frase)):
                return self._qual_lembrete(pend, "adiar")
            alvos = pend[:1]
        if not alvos:
            return "Não há lembretes para adiar."
        if len(alvos) > 1:
            return self._qual_lembrete(alvos, "adiar")
        x = alvos[0]
        antes = datetime.fromtimestamp(x["quando"])
        novo = absoluto or antes + delta
        if x.get("repetir"):                 # so esta vez: a serie segue no horario de sempre
            sec.remarcar(x["id"], proxima_ocorrencia(antes, x["repetir"], None, antes))
            sec.lembrar(x["texto"], novo, x.get("tipo", "lembrete"))
            return f"Adiado só desta vez para {falar_quando(novo, agora)}: {x['texto']}."
        sec.remarcar(x["id"], novo)
        return f"Adiado para {falar_quando(novo, agora)}: {x['texto']}."

    def remarcar_lembrete(self, frase: str) -> str:
        """ "mude o lembrete das 15h para as 16h" (vale para a serie, se repetir)."""
        from .secretario import falar_repeticao, interpretar_quando, proxima_ocorrencia
        sec = self.rt.secretario
        corte = normalizar(frase).rfind(" para ")
        antes_txt, depois_txt = frase[:corte], frase[corte:]
        agora = datetime.now()
        novo, _ = interpretar_quando(depois_txt, agora)
        if not novo:
            m = re.search(r"para (\d{1,2})\s*(?:h|:|horas?)\s*(\d{2})?", normalizar(depois_txt))
            if m and 0 <= int(m.group(1)) <= 23:
                novo = agora.replace(hour=int(m.group(1)), minute=int(m.group(2) or 0), second=0, microsecond=0)
                if novo <= agora:
                    novo += timedelta(days=1)
        if not novo:
            return "Para que horário? Diga, por exemplo: mude o lembrete das 15h para as 16h."
        pend = sec.pendentes()
        alvos = sec.achar(antes_txt) or (pend if len(pend) == 1 else [])
        if not alvos:
            return self._qual_lembrete(pend, "mudar") if pend else "Não há lembretes para mudar."
        if len(alvos) > 1:
            return self._qual_lembrete(alvos, "mudar")
        x = alvos[0]
        if x.get("repetir"):
            base = datetime.fromtimestamp(x["quando"]).replace(hour=novo.hour, minute=novo.minute)
            novo = proxima_ocorrencia(base - timedelta(days=7), x["repetir"], None, agora)
        item = sec.remarcar(x["id"], novo)
        return f"Mudado: {x['texto']}, {falar_repeticao(item or x)}."

    def falar_emails(self) -> str:
        e = self._tel().get("email") or {}
        if e.get("status") == "nao_configurado":
            return "Seu e-mail ainda não está conectado. Conecte a conta Google no cartão Agenda do painel."
        if e.get("status") != "medido":
            return "Não consegui ler seus e-mails agora."
        n = e.get("nao_lidos", 0)
        if not n:
            return "Nenhum e-mail novo, " + self._trat() + "."
        recentes = [r for c in e.get("contas", []) for r in c.get("recentes", [])][:3]
        de = "; ".join(f"{r['de']}, sobre {r['assunto']}" for r in recentes)
        return f"Você tem {n} e-mail{'s' if n > 1 else ''} não lido{'s' if n > 1 else ''}. Os mais recentes: {de}."

    def status(self) -> str:
        s = (self._tel().get("sistema") or {})
        est = self.rt.estado.instantaneo()
        partes = []
        cpu, mem, dsk = s.get("cpu") or {}, s.get("memoria") or {}, s.get("disco") or {}
        if cpu.get("status") == "medido":
            partes.append(f"processador em {round(cpu['uso_pct'])} por cento")
        if mem.get("status") == "medido":
            alerta = ", acima do ideal" if mem["uso_pct"] >= 90 else ""
            partes.append(f"memória em {round(mem['uso_pct'])} por cento{alerta}")
        if dsk.get("status") == "medido":
            partes.append(f"{round(dsk['livre_gb'])} gigas livres no disco")
        b = s.get("bateria") or {}
        if b.get("status") == "medido":
            partes.append(f"bateria em {round(b['percentual'])} por cento{' na tomada' if b['na_tomada'] else ''}")
        tp = s.get("temperatura") or {}
        if tp.get("status") == "medido":
            partes.append(f"CPU a {round(tp['celsius'])} graus")
        srv = (est.get("conexao") or {}).get("servidor", {}).get("estado")
        partes.append("servidor no ar" if srv == "ok" else "servidor fora do ar")
        return "Relatório de status: " + ", ".join(partes) + "."

    def briefing(self, agora: datetime | None = None) -> str:
        """O "bom dia" do filme: hora, clima, agenda, e-mails, lembretes, tarefas, noticias, alertas."""
        from .noticias import manchetes_faladas
        from .voz import hora_falada, resumo_agenda
        agora = agora or datetime.now()
        t = self._trat()
        tel = self._tel()
        saud = "Bom dia" if 5 <= agora.hour < 12 else "Boa tarde" if agora.hour < 18 else "Boa noite"
        frases = [f"{saud}, {t}. São {hora_falada(agora)}."]
        p = self.rt.prefs.ler()
        if self.rt.clima and p.get("local_clima"):
            c = self.rt.clima.resumo_falado(p["local_clima"])
            if c:
                frases.append(c)
            for lc in (p.get("climas_extras") or [])[:2]:
                c2 = self.rt.clima.resumo_falado(lc, curto=True)
                if c2:
                    frases.append(c2)
        ag = tel.get("agenda") or {}
        if ag.get("status") == "medido":
            if isinstance(ag.get("em"), (int, float)) and agora.timestamp() - ag["em"] > 900:
                frases.append("A última consulta da agenda está antiga; atualize antes de confirmar os compromissos.")
            else:
                frases.append(resumo_agenda(ag, agora))
        else:
            frases.append("A agenda não está disponível agora; não confirmei os compromissos do dia.")
        e = tel.get("email") or {}
        if e.get("status") == "medido" and e.get("nao_lidos"):
            frases.append(f"Há {e['nao_lidos']} e-mail{'s' if e['nao_lidos'] > 1 else ''} não lido{'s' if e['nao_lidos'] > 1 else ''}.")
        hoje = [x for x in self.rt.secretario.pendentes() if datetime.fromtimestamp(x["quando"]).date() == agora.date()]
        if hoje:
            frases.append(f"Você tem {len(hoje)} lembrete{'s' if len(hoje) > 1 else ''} para hoje.")
        if self.rt.tarefas:
            pend = [x for x in self.rt.tarefas.listar() if not x["feita"]]
            if pend:
                frases.append(f"{len(pend)} tarefa{'s' if len(pend) > 1 else ''} pendente{'s' if len(pend) > 1 else ''}.")
        n = tel.get("noticias") or {}
        if n.get("status") == "medido":
            frases.append(manchetes_faladas(n, 2))
        mem = (tel.get("sistema") or {}).get("memoria") or {}
        if mem.get("status") == "medido" and mem["uso_pct"] >= 92:
            frases.append(f"Aviso: a memória do computador está em {round(mem['uso_pct'])} por cento.")
        return " ".join(frases)
