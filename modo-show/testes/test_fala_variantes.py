"""O Senhor nao fala igual duas vezes: o mesmo pedido, de varios jeitos.

Em 19/09 "Jarvis, memore o meu rosto" nao casou com regra nenhuma, foi parar no
modelo e foi RECUSADO. Aqui cada jeito de pedir tem de chegar ao comando certo,
e as frases parecidas que NAO sao comando tem de continuar indo para a conversa.
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.comandos import Comandos, interpretar  # noqa: E402
from hud_runtime.fala_variantes import corrigir, separar_pedidos  # noqa: E402


class RT:
    prefs = type("P", (), {"ler": staticmethod(lambda: {})})()


def comandos():
    return Comandos(RT(), lambda pagina: None)


# (frase dita, comando esperado). O Senhor tentou VARIAS formas em 19/09 e TODAS caiam
# no modelo, que respondia "sou so um assistente de voz e nao posso memorizar rostos".
JEITOS = [
    # --- rosto: o caso do print e todos os jeitos que ele tentou -----------
    ("Jarvis, memore o meu rosto", "id_rosto_cadastrar"),
    ("Jarvis, memorize seu rosto", "id_rosto_cadastrar"),
    ("Jarvis, memorize o seu rosto", "id_rosto_cadastrar"),
    ("jarvis memoriza seu rosto", "id_rosto_cadastrar"),
    ("jarvis memora meu rosto", "id_rosto_cadastrar"),
    ("Jarvis, memorizar o meu rosto", "id_rosto_cadastrar"),
    ("Jarvis, memorize meu rosto", "id_rosto_cadastrar"),
    ("Jarvis, memorize o rosto", "id_rosto_cadastrar"),
    ("Jarvis, memorize esse rosto", "id_rosto_cadastrar"),
    ("Jarvis, memorize este rosto", "id_rosto_cadastrar"),
    ("Jarvis, memorize meu rosto por favor", "id_rosto_cadastrar"),
    ("Jarvis, memorize o meu rosto agora", "id_rosto_cadastrar"),
    ("Jarvis, quero que você memorize o meu rosto", "id_rosto_cadastrar"),
    ("Jarvis, decore o meu rosto", "id_rosto_cadastrar"),
    ("Jarvis, cadastra o meu rosto", "id_rosto_cadastrar"),
    ("Jarvis, cadastre o meu rosto no sistema", "id_rosto_cadastrar"),
    ("Jarvis, registre o meu rosto", "id_rosto_cadastrar"),
    ("Jarvis, grave o meu rosto", "id_rosto_cadastrar"),
    ("Jarvis, salve o meu rosto", "id_rosto_cadastrar"),
    ("Jarvis, guarde o meu rosto na memória", "id_rosto_cadastrar"),
    ("Jarvis, guarde o rosto da Maria", "id_rosto_cadastrar"),
    ("Jarvis, memorize a minha cara", "id_rosto_cadastrar"),
    ("Jarvis, grave a minha face", "id_rosto_cadastrar"),
    ("Jarvis, aprende o meu rosto", "id_rosto_cadastrar"),
    ("Jarvis, aprenda a reconhecer o meu rosto", "id_rosto_cadastrar"),
    # --- voz ---------------------------------------------------------------
    ("Jarvis, memore a minha voz", "id_voz_cadastrar"),
    ("Jarvis, memorize sua voz", "id_voz_cadastrar"),
    ("Jarvis, memorize a sua voz", "id_voz_cadastrar"),
    ("Jarvis, memoriza minha voz", "id_voz_cadastrar"),
    ("Jarvis, cadastrar a minha voz", "id_voz_cadastrar"),
    ("Jarvis, grave minha voz agora", "id_voz_cadastrar"),
    ("Jarvis, guarde a minha voz", "id_voz_cadastrar"),
    ("Jarvis, aprenda a minha voz", "id_voz_cadastrar"),
    ("Jarvis, grave a voz do Pedro", "id_voz_cadastrar"),
    # --- quem e quem (pergunta, nao cadastro) ------------------------------
    ("Jarvis, quem está aqui?", "id_quem"),
    ("Jarvis, quem que tá aqui?", "id_quem"),
    ("Jarvis, você me reconhece?", "id_quem"),
    ("Jarvis, você reconhece o meu rosto?", "id_quem"),
    ("Jarvis, quem você conhece?", "id_listar"),
    ("Jarvis, quem está cadastrado?", "id_listar"),
    # --- esquecer ----------------------------------------------------------
    ("Jarvis, esqueça o rosto da Maria", "id_esquecer"),
    ("Jarvis, apague a minha voz", "id_esquecer"),
    ("Jarvis, apague meus dados de rosto", "id_esquecer"),
    ("Jarvis, apagar todos os rostos", "id_esquecer"),
]

# frases parecidas que NAO sao comando de cadastro: seguem o caminho de sempre
NAO_SAO = [
    "Jarvis, o que você tem na memória sobre mim?",
    "Jarvis, me fale sobre memória RAM",
    "Jarvis, quantas memórias você guardou?",
    "Jarvis, você lembra do que eu disse ontem?",
    "Jarvis, grave um vídeo da tela",
    "Jarvis, salve esse arquivo",
    "Jarvis, memorize que eu odeio cebola",
]


class JeitosDePedir(unittest.TestCase):
    def setUp(self):
        self.cmd = comandos()

    def test_cada_jeito_chega_ao_comando(self):
        for frase, esperado in JEITOS:
            with self.subTest(frase=frase):
                achado = self.cmd.interpretar(frase)
                self.assertIsNotNone(achado, f"nao entendeu: {frase}")
                self.assertEqual(achado[0], esperado)

    def test_frases_parecidas_nao_viram_cadastro(self):
        for frase in NAO_SAO:
            with self.subTest(frase=frase):
                achado = self.cmd.interpretar(frase)
                self.assertTrue(achado is None or not achado[0].startswith("id_"), f"{frase} -> {achado}")

    def test_regras_diretas_continuam_valendo(self):
        self.assertEqual(interpretar("jarvis memorize meu rosto")[0], "id_rosto_cadastrar")

    def test_o_nome_da_pessoa_sobrevive_ao_jeito_de_pedir(self):
        for frase in ("Jarvis, memore o rosto da Maria", "Jarvis, memorize o rosto da Maria agora",
                      "Jarvis, cadastra o rosto da Maria por favor"):
            with self.subTest(frase=frase):
                nome, args = self.cmd.interpretar(frase)
                self.assertEqual(nome, "id_rosto_cadastrar")
                self.assertEqual(args.get("nome", "").strip(), "maria")

    def test_a_frase_corrigida_e_a_que_vale(self):
        # quando a correção é que salvou a frase, é ela que chega ao executar()
        achado = self.cmd.interpretar("Jarvis, abrir o bloco de notas")
        self.assertEqual(achado[0], "app")


class Correcao(unittest.TestCase):
    def test_nao_mexe_em_memoria(self):
        self.assertNotIn("memorize", corrigir("o que voce tem na memoria"))
        self.assertNotIn("memorize", corrigir("minhas memorias de infancia"))

    def test_infinitivo_vira_imperativo(self):
        self.assertEqual(comandos().interpretar("Jarvis, abrir o bloco de notas")[0], "app")

    def test_ligar_para_alguem_nao_e_ligar_aparelho(self):
        self.assertIn("ligar para", corrigir("me lembre de ligar para a Maria"))


class DuasFalasGrudadas(unittest.TestCase):
    def test_separa_no_segundo_chamado(self):
        # caso real: virou um lembrete com o texto "que horas sao? jarvis, me lembre de ligar"
        partes = separar_pedidos("Jarvis, que horas são? Jarvis, me lembre de ligar para a Maria")
        self.assertEqual(len(partes), 2)
        self.assertTrue(partes[0].lower().startswith("jarvis, que horas"))
        self.assertTrue(partes[1].lower().startswith("me lembre"))

    def test_uma_fala_so_continua_inteira(self):
        frase = "Jarvis, me lembre de ligar para o Pedro amanhã"
        self.assertEqual(separar_pedidos(frase), [frase])

    def test_cada_parte_vira_seu_comando(self):
        partes = separar_pedidos("Jarvis, ligue a câmera. Jarvis, memore o meu rosto")
        cmd = comandos()
        self.assertEqual([cmd.interpretar(p)[0] for p in partes], ["camera_ligar", "id_rosto_cadastrar"])

    def test_lembrete_nao_engole_a_pergunta_anterior(self):
        # o bug real: o lembrete foi salvo como "que horas sao? jarvis, me lembre de ligar"
        partes = separar_pedidos("Jarvis, que horas são? Jarvis, me lembre de ligar para a Maria")
        achado = comandos().interpretar(partes[1])
        self.assertIsNotNone(achado)
        self.assertNotIn("horas", str(achado[1]).lower())


if __name__ == "__main__":
    unittest.main()
