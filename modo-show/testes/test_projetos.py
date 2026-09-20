"""Estado de projetos e tarefas (§6 do prompt mestre de 19/09).

O que estes testes garantem, e que era o buraco apontado no diagnóstico:
"continue de ontem" recupera a tarefa certa, retomar NÃO repete o que já foi
feito, e o Jarvis sabe dizer o que falta -- sem depender de um resumo escrito
pelo modelo.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime.projetos import (  # noqa: E402
    ABERTOS,
    ESTADOS,
    FECHADOS,
    Projetos,
    por_extenso,
    resumo_da_lista,
    resumo_falado,
)


def novo() -> Projetos:
    return Projetos(Path(tempfile.mkdtemp()) / "hud-projetos.json")


class CriarERetomar(unittest.TestCase):
    def setUp(self):
        self.p = novo()

    def test_tarefa_nasce_com_objetivo_e_condicao_de_fim(self):
        t = self.p.criar("terminar a caixa do Arduino", projeto="caixa",
                         conclusao_quando="o STL abrir no Cura sem erro",
                         etapas=["desenhar a caixa", "abrir a passagem do cabo", "exportar o STL"])
        self.assertEqual(t.estado, "planejada")
        self.assertEqual(t.conclusao_quando, "o STL abrir no Cura sem erro")
        self.assertEqual(len(t.etapas), 3)
        self.assertIs(self.p.ativa(), t)

    def test_retomar_nao_repete_o_que_ja_foi_feito(self):
        t = self.p.criar("terminar a caixa", etapas=["desenhar", "furar", "exportar"])
        self.p.concluir_etapa(t.id, "desenhar", "caixa 80x50x30 mm")
        self.assertEqual(t.proxima_etapa().descricao, "furar")

        # o Jarvis reinicia: outro objeto, mesmo arquivo
        outro = Projetos(self.p._arq)
        t2 = outro.ultima_mexida()
        self.assertEqual(t2.id, t.id)
        self.assertEqual(t2.proxima_etapa().descricao, "furar")       # nao voltou para "desenhar"
        self.assertEqual([e.descricao for e in t2.prontas()], ["desenhar"])
        self.assertEqual(t2.prontas()[0].resultado, "caixa 80x50x30 mm")

    def test_concluir_a_mesma_etapa_duas_vezes_nao_duplica(self):
        t = self.p.criar("teste", etapas=["passo unico"])
        self.p.concluir_etapa(t.id, "passo unico", "feito")
        self.p.concluir_etapa(t.id, "passo unico", "feito de novo")
        self.assertEqual(len(t.etapas), 1)
        self.assertEqual(t.resultados, ["feito"])                     # o segundo nao entrou

    def test_tudo_feito_nao_vira_concluida_sozinha(self):
        # rodar todas as etapas nao prova que o resultado presta
        t = self.p.criar("gerar peca", etapas=["gerar", "salvar"])
        self.p.concluir_etapa(t.id, "gerar", "ok")
        self.p.concluir_etapa(t.id, "salvar", "peca.stl")
        self.assertEqual(t.estado, "executada_sem_verificacao")
        self.assertIn("ainda não conferida", por_extenso(t.estado))
        self.assertIn("nada foi conferido ainda", resumo_falado(t))
        self.p.mudar_estado(t.id, "concluida")
        self.assertEqual(t.estado, "concluida")

    def test_falha_preserva_o_que_ficou_pronto(self):
        t = self.p.criar("imprimir", etapas=["fatiar", "imprimir"])
        self.p.concluir_etapa(t.id, "fatiar", "gcode pronto")
        self.p.falhar_etapa(t.id, "imprimir", "a impressora não respondeu")
        self.assertEqual(t.estado, "parcialmente_concluida")
        self.assertEqual([e.descricao for e in t.prontas()], ["fatiar"])
        self.assertIn("a impressora não respondeu", resumo_falado(t))


class AcharEFocar(unittest.TestCase):
    def setUp(self):
        self.p = novo()
        self.caixa = self.p.criar("terminar a caixa do Arduino", projeto="caixa")
        self.lamp = self.p.criar("desenhar a luminária da sala", projeto="luminária")

    def test_acha_pelo_nome_falado(self):
        self.assertEqual(self.p.achar("a caixa").id, self.caixa.id)
        self.assertEqual(self.p.achar("projeto da luminária").id, self.lamp.id)
        self.assertIsNone(self.p.achar("foguete"))

    def test_continue_de_ontem_pega_a_ultima_mexida(self):
        # duas tarefas criadas no mesmo milissegundo nao podem empatar:
        # se empatarem, "continue de ontem" retoma a errada
        self.assertEqual(self.p.ultima_mexida().id, self.lamp.id)
        self.p.concluir_etapa(self.caixa.id, "medir", "80 mm")
        self.assertEqual(self.p.ultima_mexida().id, self.caixa.id)

    def test_dez_tarefas_seguidas_mantem_a_ordem(self):
        p = novo()
        ids = [p.criar(f"tarefa {i}").id for i in range(10)]
        self.assertEqual([t.id for t in p.todas()], list(reversed(ids)))

    def test_trocar_de_projeto_nao_mistura_parametros(self):
        self.p.focar(self.caixa.id)
        self.assertEqual(self.p.projeto, "caixa")
        self.p.abrir_projeto("luminária")
        self.assertIsNone(self.p.ativa())          # nao herda a tarefa do outro projeto
        self.assertEqual([t.objetivo for t in self.p.abertas("caixa")],
                         ["terminar a caixa do arduino".replace("arduino", "Arduino")])

    def test_tarefa_fechada_sai_de_foco(self):
        self.p.focar(self.caixa.id)
        self.p.mudar_estado(self.caixa.id, "concluida")
        self.assertIsNone(self.p.ativa())


class Aprovacoes(unittest.TestCase):
    def test_aprovacao_vale_para_a_operacao_e_os_parametros(self):
        p = novo()
        t = p.criar("mandar o recado", conclusao_quando="o Senhor confirmar")
        p.mudar_estado(t.id, "aguardando_autorizacao")
        p.aprovar(t.id, "enviar_telegram", "para Mateus: cheguei")
        self.assertTrue(p.tem_aprovacao(t.id, "enviar_telegram", "para Mateus: cheguei"))
        self.assertFalse(p.tem_aprovacao(t.id, "enviar_telegram", "para Maria: cheguei"))
        self.assertFalse(p.tem_aprovacao(t.id, "enviar_email", "para Mateus: cheguei"))
        self.assertEqual(t.estado, "em_execucao")


class Persistencia(unittest.TestCase):
    def test_arquivo_e_legivel_e_sobrevive_a_versao_antiga(self):
        p = novo()
        t = p.criar("uma tarefa", etapas=["um"])
        d = json.loads(Path(p._arq).read_text(encoding="utf-8"))
        self.assertEqual(d["tarefas"][0]["objetivo"], "uma tarefa")
        # um registro de outra versao do programa nao pode derrubar o Jarvis
        d["tarefas"].append({"id": "velho", "campo_que_nao_existe": 1})
        Path(p._arq).write_text(json.dumps(d), encoding="utf-8")
        p2 = Projetos(p._arq)
        self.assertEqual([x.id for x in p2.todas()], [t.id])

    def test_estados_cobrem_o_que_o_prompt_pede(self):
        for estado in ("planejada", "aguardando_informacao", "aguardando_autorizacao", "em_execucao",
                       "pausada", "parcialmente_concluida", "executada_sem_verificacao", "concluida",
                       "falha", "cancelada"):
            self.assertIn(estado, ESTADOS)
        self.assertEqual(set(ABERTOS) | set(FECHADOS), set(ESTADOS))


class Fala(unittest.TestCase):
    def test_resumo_diz_o_que_falta(self):
        p = novo()
        t = p.criar("terminar a caixa", projeto="caixa", conclusao_quando="o STL abrir no Cura",
                    etapas=["desenhar", "furar", "exportar"])
        p.concluir_etapa(t.id, "desenhar", "80x50 mm")
        frase = resumo_falado(t)
        self.assertIn("Já fiz: desenhar", frase)
        self.assertIn("Falta: furar e exportar", frase)
        self.assertIn("Termina quando o STL abrir no Cura", frase)

    def test_lista_vazia_e_lista_cheia(self):
        p = novo()
        self.assertIn("Não há nada em andamento", resumo_da_lista([], "Senhor"))
        p.criar("primeira")
        p.criar("segunda")
        frase = resumo_da_lista(p.abertas(), "Senhor")
        self.assertIn("2 em andamento", frase)


class PelaVoz(unittest.TestCase):
    """O caminho de verdade: a frase falada até o arquivo em disco."""

    def setUp(self):
        from types import SimpleNamespace
        from hud_runtime.comandos import Comandos
        self.p = novo()                       # arquivo isolado, nada toca os dados do Senhor
        rt = SimpleNamespace(
            prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}),
            estado=SimpleNamespace(atualizar=lambda *a, **k: None, registrar=lambda *a, **k: None,
                                   telemetria={}),
            projetos=self.p)
        self.c = Comandos(rt, lambda pagina: None)

    def dizer(self, frase: str) -> str:
        achado = self.c.interpretar(frase)
        self.assertIsNotNone(achado, f"nenhuma regra entendeu: {frase}")
        return self.c.executar(achado[0], achado[1], frase)

    def test_do_pedido_ao_disco_e_de_volta(self):
        self.assertIn("aberto", self.dizer("Jarvis, comece o projeto caixa do Arduino"))
        self.dizer("Jarvis, falta abrir a passagem do cabo")
        self.dizer("Jarvis, falta exportar o STL")

        falta = self.dizer("Jarvis, o que falta?")
        self.assertIn("abrir a passagem do cabo", falta)
        self.assertIn("exportar o STL", falta)

        self.assertIn("Pausei", self.dizer("Jarvis, pause o projeto"))

        # um dia depois, com o runtime reiniciado: o arquivo e a fonte da verdade
        outro = Projetos(self.p._arq)
        t = outro.ultima_mexida()
        self.assertEqual(t.projeto, "caixa do Arduino")
        self.assertEqual(t.estado, "pausada")
        self.assertEqual([e.descricao for e in t.pendentes()],
                         ["abrir a passagem do cabo", "exportar o STL"])

        voltou = self.dizer("Jarvis, continue de ontem")
        self.assertIn("Retomo por: abrir a passagem do cabo", voltou)

    def test_continuar_sem_nada_em_andamento_diz_a_verdade(self):
        self.assertIn("Não tenho nada em andamento", self.dizer("Jarvis, continue de ontem"))

    def test_concluir_exige_a_palavra_do_senhor(self):
        self.dizer("Jarvis, comece o projeto luminária")
        self.dizer("Jarvis, falta soldar os fios")
        # etapa feita nao conclui a tarefa sozinha
        t = self.p.ativa()
        self.p.concluir_etapa(t.id, "soldar os fios", "soldado")
        self.assertEqual(self.p.obter(t.id).estado, "executada_sem_verificacao")
        self.assertIn("concluída", self.dizer("Jarvis, terminei"))
        self.assertEqual(self.p.obter(t.id).estado, "concluida")

    def test_apagar_o_projeto_pelo_nome(self):
        self.dizer("Jarvis, comece o projeto caixa")
        self.dizer("Jarvis, comece o projeto luminária")
        self.assertIn("Apaguei o projeto caixa", self.dizer("Jarvis, apague o projeto caixa"))
        self.assertEqual([t.projeto for t in self.p.todas()], ["luminária"])

    def test_o_modelo_recebe_o_projeto_aberto(self):
        self.dizer("Jarvis, comece o projeto caixa")
        self.dizer("Jarvis, falta furar a tampa")
        contexto = self.c.contexto_para_modelo("o que você acha disso?")
        self.assertIn("projeto aberto agora: caixa", contexto)
        self.assertIn("furar a tampa", contexto)


if __name__ == "__main__":
    unittest.main()
