"""O mesmo pedido, de vários jeitos, em TODAS as famílias de comando (F01).

O `test_fala_variantes.py` cobre cadastro de rosto e voz. Aqui está o resto:
lembretes, listas, mídia, volume, câmera, notícias, engenharia, projeto, peça,
documento, inventário e canais -- mais o clima e as tarefas, que são respondidos
antes do modelo, em `voz._INTENCOES`.

Duas camadas, porque o Jarvis de verdade usa as duas:

1. `comandos.interpretar` (regras determinísticas);
2. `voz._INTENCOES` (respostas locais que nem chegam ao modelo).

E uma lista de frases que **não podem** virar comando: é ela que impede a
regra de ficar gulosa e engolir conversa.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))
os.environ.setdefault("OPENJARVIS_HOME", tempfile.mkdtemp())

from hud_runtime import voz  # noqa: E402
from hud_runtime.comandos import interpretar  # noqa: E402

# (comando esperado, formas de pedir)
FAMILIAS: dict[str, list[str]] = {
    "lembrete": [
        "me lembre de ligar para a Maria às 15h",
        "lembra de tirar o bolo em 20 minutos",
        "me avisa às 8 da manhã de tomar o remédio",
        "bota um lembrete de reunião às 14h",
    ],
    "lista_add": [
        "adicione leite à lista de compras",
        "põe arroz na lista",
        "coloca sabão em pó na lista de compras",
        "acrescente café na lista",
        "bota ovos na lista de compras",
    ],
    "lista_ler": [
        "o que tem na lista de compras?",
        "me diz a lista de compras",
        "leia a minha lista",
        "quais itens tem na lista?",
    ],
    "musica_tocar": ["toque uma música", "bota um som", "coloca música", "toca a playlist"],
    "volume_aumentar": ["aumente o volume", "aumenta o som", "mais alto", "sobe o volume"],
    "volume_diminuir": ["abaixe o volume", "diminui o som", "mais baixo"],
    "camera_ligar": ["ligue a câmera", "liga a webcam", "abre a câmera", "ativa a câmera"],
    "camera_desligar": ["desligue a câmera", "desliga a webcam", "fecha a câmera"],
    "noticias": [
        "me dê as notícias",
        "quais são as novidades?",
        "o que está acontecendo no mundo?",
        "manchetes de hoje",
        "notícias de tecnologia",
    ],
    "visao": ["o que é isso?", "que objeto é esse?", "o que eu estou segurando?"],
    "app": ["abra o bloco de notas", "inicia o vs code", "roda a calculadora"],
    "projetar": [
        "projete uma caixa de 80 por 50 por 30",
        "faça uma engrenagem de 20 dentes com 40 mm",
        "desenhe um cilindro de 20 por 40",
    ],
    "projeto_novo": ["comece o projeto caixa do Arduino", "novo projeto luminária",
                     "vamos começar um projeto de suporte"],
    "projeto_estado": ["o que falta?", "em que pé estamos?", "como está o projeto?"],
    "projeto_continuar": ["continue de ontem", "retome o projeto caixa", "continue"],
    "peca_versoes": ["quais versões?", "liste as versões", "mostre as versões da peça"],
    "doc_indexar": ["leia o manual da impressora", "indexe o documento tal", "estude o manual"],
    "doc_fonte": ["qual é a fonte?", "de onde você tirou isso?", "onde está escrito?"],
    "inv_listar": ["quais são os meus objetos?", "meu inventário", "o que você tem cadastrado?"],
    "canais_listar": ["quais canais você tem?", "por onde eu falo com você?"],
    "corrigir_listar": ["quais são as minhas correções?", "quais apelidos?"],
    "ocorrencias": ["o que aconteceu enquanto eu estava fora?", "o que apareceu hoje?"],
    "montagem_explodir": ["mostre a vista explodida", "separe as peças", "desmonte isso"],
    "parar_fala": ["pare", "chega", "silêncio", "cala a boca"],
    "armadura": ["prepare a armadura", "checagem completa dos sistemas"],
}

# respondidas antes do modelo, em voz._INTENCOES
INTENCOES_LOCAIS: dict[str, list[str]] = {
    "clima": ["como está o tempo?", "vai chover hoje?", "qual a previsão?", "está frio lá fora?"],
    "horas": ["que horas são?", "me diz a hora certa"],
    "listar": ["quais são minhas tarefas?", "leia minhas tarefas"],
    "bateria": ["quanto de bateria tem?", "como está a bateria?"],
}

# conversa que NAO pode virar comando
NAO_SAO_COMANDO = [
    "o que você acha da minha ideia?",
    "me conte uma curiosidade sobre Marte",
    "o que está acontecendo com o meu pedido na loja?",
    "eu gosto de café forte",
    "explique o que é uma engrenagem planetária",
    "você está bem hoje?",
]


class FamiliasDeComando(unittest.TestCase):
    def test_cada_familia_entende_varios_jeitos(self):
        for esperado, frases in FAMILIAS.items():
            for frase in frases:
                with self.subTest(comando=esperado, frase=frase):
                    achado = interpretar("Jarvis, " + frase)
                    self.assertIsNotNone(achado, f"nenhuma regra entendeu: {frase}")
                    self.assertEqual(achado[0], esperado, frase)

    def test_intencoes_locais_respondem_antes_do_modelo(self):
        for esperado, frases in INTENCOES_LOCAIS.items():
            for frase in frases:
                with self.subTest(intencao=esperado, frase=frase):
                    achados = [n for n, r in voz._INTENCOES if r.search(voz._norm_visual(frase))]
                    self.assertIn(esperado, achados, frase)

    def test_conversa_continua_sendo_conversa(self):
        for frase in NAO_SAO_COMANDO:
            with self.subTest(frase=frase):
                achado = interpretar("Jarvis, " + frase)
                nome = achado[0] if achado else None
                # pode cair em "saber"/"memoria_guardar" (que levam ao modelo),
                # mas nunca numa acao do computador
                self.assertNotIn(nome, {"app", "musica_tocar", "camera_ligar", "volume_aumentar",
                                        "projetar", "montagem_explodir", "parar_fala", "lista_add"},
                                 frase)


class SemAmbiguidadePerigosa(unittest.TestCase):
    """Frases parecidas que precisam ir para famílias diferentes."""

    def test_pares_que_nao_podem_se_confundir(self):
        pares = [
            ("aumente o volume", "volume_aumentar"),
            ("aumente a largura em 2 milímetros", "peca_alterar"),
            ("o que mudou?", "percepcao_mudou"),
            ("o que mudou na peça?", "peca_versoes"),
            ("esqueça o meu rosto", "id_esquecer"),
            ("esqueça a minha impressora", "inv_esquecer"),
            ("leia o manual da impressora", "doc_indexar"),
            ("leia a minha lista", "lista_ler"),
            ("abra a segunda notícia", "noticia_abrir"),
            ("abra o bloco de notas", "app"),
        ]
        for frase, esperado in pares:
            with self.subTest(frase=frase):
                achado = interpretar("Jarvis, " + frase)
                self.assertIsNotNone(achado, frase)
                self.assertEqual(achado[0], esperado, frase)


if __name__ == "__main__":
    unittest.main()
