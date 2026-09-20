"""Automacao estilo filme: protocolos com nome, comandos com horario marcado,
diagnostico "prepare a armadura" e consumo por programa."""

import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.append(str(RAIZ / "_libs"))

from hud_runtime import comandos as cmd  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402
from hud_runtime.protocolos import PROIBIDOS, Protocolos, separar_passos, validar_passos  # noqa: E402
from hud_runtime.secretario import Secretario  # noqa: E402


class TestPassos(unittest.TestCase):
    def test_separa_por_virgula_depois_e_verbo(self):
        self.assertEqual(separar_passos("abra o VS Code, abra o Gmail e me dê as notícias de tecnologia"),
                         ["abra o VS Code", "abra o Gmail", "me dê as notícias de tecnologia"])
        self.assertEqual(separar_passos("toque Legião Urbana depois volume 30"), ["toque Legião Urbana", "volume 30"])
        self.assertEqual(separar_passos("adicione leite e pão à lista de compras"),
                         ["adicione leite e pão à lista de compras"])                # "e" entre itens fica

    def test_so_comandos_conhecidos_e_permitidos(self):
        ok, erro = validar_passos(["abra o VS Code"], cmd.interpretar)
        self.assertIsNone(erro)
        _, erro = validar_passos(["escreva um poema sobre o mar"], cmd.interpretar)
        self.assertIn("Não sei executar sozinho", erro)
        _, erro = validar_passos(["apague toda a memória"], cmd.interpretar)
        self.assertIn("por segurança", erro)
        for perigoso in ("memoria_limpar_confirmado", "quarentena_mover", "rotina_descanso", "lista_limpar", "programa"):
            self.assertIn(perigoso, PROIBIDOS)


class TestComandos(unittest.TestCase):
    def setUp(self):
        from hud_runtime.projetos import Projetos
        prefs = validar({"nome_usuario": "Senhor"})
        pasta = Path(tempfile.mkdtemp())
        self.sec = Secretario(ao_mudar=lambda d: None, pasta=pasta)      # nunca o arquivo real do Senhor
        self.rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: prefs), secretario=self.sec,
                                  estado=SimpleNamespace(atualizar=mock.Mock(), ler=lambda c: {"estado": "ouvindo"}),
                                  protocolos=Protocolos(pasta / "p.json"),
                                  projetos=Projetos(pasta / "projetos.json"),
                                  camera=SimpleNamespace(ativa=False))
        self.c = cmd.Comandos(self.rt, lambda x: None)
        self.abertos = []
        self.c._abrir_url = self.abertos.append

    def dizer(self, frase):
        nome, args = self.c.interpretar(frase)
        return self.c.executar(nome, args, frase)

    def test_protocolo_criar_executar_listar_apagar(self):
        r = self.dizer("crie o protocolo manhã: quanto é 2 mais 2, jogue uma moeda e depois que horas são em Tóquio")
        self.assertTrue(r.startswith("Protocolo manha criado com 3 passos"), r)
        self.assertEqual(self.dizer("quais são meus protocolos?"), "Seus protocolos: manha.")
        with mock.patch("hud_runtime.utilidades.hora_em", return_value="Em Tóquio são 9 e 10."):
            r = self.dizer("Jarvis, execute o protocolo manhã")
        self.assertIn("executada, mas ainda não conferida", r)
        self.assertIn("Dá 4. Deu ", r)
        self.assertIn("Em Tóquio são 9 e 10.", r)
        self.assertEqual(self.rt.projetos.ativa().estado, "executada_sem_verificacao")
        self.assertEqual(self.dizer("apague o protocolo manhã"), "Protocolo manha apagado.")
        self.assertIn("Não achei o protocolo manha", self.dizer("protocolo manhã"))

    def test_protocolo_recusa_passo_perigoso(self):
        r = self.dizer("crie o protocolo limpeza: apague toda a memória e abra o Gmail")
        self.assertIn("por segurança", r)
        self.assertEqual(self.rt.protocolos.nomes(), [])

    def test_protocolo_dentro_de_protocolo_nao_trava(self):
        self.rt.protocolos.salvar("eco", ["execute o protocolo eco"])
        r = self.dizer("execute o protocolo eco")
        self.assertIn("não pode rodar sozinho", r)

    def test_horario_marcado_executa_comando(self):
        r = self.dizer("todo dia às 7h me dê o resumo do dia")
        self.assertEqual(r, "Combinado, Senhor. Todos os dias às 7h eu executo: me dê o resumo do dia.")
        item = self.sec.pendentes()[-1]
        self.assertEqual((item["tipo"], item["comando"], item["repetir"]), ("rotina", "me dê o resumo do dia", "diario"))
        self.assertEqual(datetime.fromtimestamp(item["quando"]).hour, 7)

    def test_horario_com_texto_comum_vira_lembrete(self):
        r = self.dizer("todo dia às 7h tomar remédio")
        self.assertEqual(r, "Certo. Vou lembrar todos os dias às 7h: tomar remédio.")
        self.assertEqual(self.sec.pendentes()[-1]["tipo"], "lembrete")

    def test_horario_nao_agenda_coisa_perigosa(self):
        self.dizer("às 23h apague toda a memória")
        self.assertNotIn("comando", self.sec.pendentes()[-1])                   # vira lembrete, nunca executa

    def test_armadura_com_medidas_reais(self):
        from hud_runtime.estado import Estado
        tel = {"em": time.time(), "sistema": {"bateria": {"status": "medido", "percentual": 80, "na_tomada": True},
                           "cpu": {"status": "medido", "uso_pct": 22}, "memoria": {"status": "medido", "uso_pct": 94},
                           "disco": {"status": "medido", "livre_gb": 120}},
               "servidor": {"status": "ok"}, "ollama": {"status": "ok"}, "clima": {"status": "medido"}}
        self.rt.estado = Estado()
        self.rt.estado.definir_telemetria(tel)
        r = self.dizer("Jarvis, prepare a Mark 42")
        self.assertIn("Diagnóstico das evidências", r)
        rel = self.rt.estado.ler("conversa")["diagnostico"]
        itens = {i["id"]: i for i in rel["componentes"]}
        self.assertEqual((itens["bateria"]["valor"], itens["bateria"]["estado"]), (80, "disponivel"))
        self.assertEqual((itens["memoria"]["valor"], itens["memoria"]["estado"]), (94, "atencao"))
        self.assertEqual(itens["camera"]["estado"], "em_espera")
        self.assertNotIn("todos os sistemas prontos", r.lower())

    def test_consumo(self):
        def proc(nome, cpu, rss):
            return SimpleNamespace(info={"name": nome}, cpu_percent=mock.Mock(side_effect=[0.0, cpu]),
                                   memory_info=lambda: SimpleNamespace(rss=rss))
        procs = [proc("ollama.exe", 240.0, 6.1e9), proc("msedge.exe", 30.0, 9e8), proc("msedge.exe", 18.0, 9e8),
                 proc("System Idle Process", 900.0, 0)]
        with mock.patch("psutil.process_iter", return_value=procs), mock.patch("psutil.cpu_count", return_value=12), \
                mock.patch("time.sleep"), mock.patch.object(self.c, "_contexto"):
            r = self.dizer("o que está consumindo mais energia?")
        self.assertEqual(r, "No processador, que é o que mais puxa a bateria: Ollama, 20 por cento; Edge, 4 por cento. "
                            "Na memória: Ollama, 6,1 gigas; Edge, 1,8 gigas.")


if __name__ == "__main__":
    unittest.main()
