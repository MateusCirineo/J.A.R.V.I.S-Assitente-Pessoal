"""Monitores criados por voz (P2) e os tres modos de proatividade (P1)."""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime import comandos as cmd, monitores  # noqa: E402
from hud_runtime.anunciador import Anunciador, modo_de  # noqa: E402
from hud_runtime.preferencias import validar  # noqa: E402


class _Noticias:
    def __init__(self):
        self.itens = [{"titulo": "Nvidia antiga", "fonte": "G1", "link": "https://a/1"}]

    def buscar(self, q, limite=10):
        return {"status": "medido", "itens": list(self.itens)}


class _Cotacoes:
    def __init__(self, valor):
        self.valor = valor

    def consultar(self, ativos):
        return {"status": "medido", "itens": [{"tipo": "moeda", "nome": "dólar", "venda": self.valor}]}


def _mon(**kw):
    avisos = []
    m = monitores.Monitores(avisos.append, arquivo=Path(tempfile.mkdtemp()) / "mon.json", **kw)
    return m, avisos


class TestNumero(unittest.TestCase):
    def test_numero_falado(self):
        for txt, v in (("5,50", 5.5), ("400 mil", 400000), ("1.200", 1200), ("5.50", 5.5), ("7", 7), ("x", None)):
            self.assertEqual(monitores.numero_falado(txt), v, txt)


class TestMonitores(unittest.TestCase):
    def test_noticia_linha_de_base_e_novidade(self):
        n = _Noticias()
        m, avisos = _mon(noticias=n)
        m.criar("noticia", "Nvidia")
        self.assertEqual(m.verificar(forcar=True), [])                    # linha de base: nada anunciado
        n.itens.insert(0, {"titulo": "Nvidia lança chip novo", "fonte": "Tecnoblog", "link": "https://b/2"})
        self.assertEqual(m.verificar(forcar=True), ["saiu notícia sobre Nvidia: Nvidia lança chip novo, Tecnoblog."])
        self.assertEqual(m.verificar(forcar=True), [])                    # a mesma nao repete
        self.assertEqual(len(avisos), 1)

    def test_intervalo_respeitado(self):
        m, _ = _mon(noticias=_Noticias())
        m.criar("noticia", "Nvidia")
        m.verificar(agora=1000.0)
        with mock.patch.object(m, "_checar") as c:
            m.verificar(agora=1000.0 + 60)                              # antes de 30 min: nao consulta
            c.assert_not_called()

    def test_cotacao_dispara_uma_vez(self):
        cot = _Cotacoes(5.40)
        m, _ = _mon(cotacoes=cot)
        m.criar("cotacao", "USD", classe="moeda", codigo="USD", limite=5.5, direcao="acima", nome="dólar")
        self.assertEqual(m.verificar(forcar=True), [])
        cot.valor = 5.61
        aviso = m.verificar(forcar=True)[0]
        self.assertIn("o dólar passou de 5 reais e 50 centavos: está em 5 reais e 61 centavos", aviso)
        self.assertFalse(m.listar()[0]["ativo"])
        self.assertEqual(m.verificar(forcar=True), [])

    def test_site_ignora_anuncio_rotativo(self):
        base = "<html><body>" + " ".join(f"<p>Parágrafo {i} com texto fixo da página.</p>" for i in range(60))
        paginas = iter([base + "<div>anúncio A</div></body></html>", base + "<div>anúncio B</div></body></html>",
                        "<html><body><h1>Página totalmente nova</h1><p>Outro conteúdo.</p></body></html>"])
        m, _ = _mon(baixar=lambda u: next(paginas).encode())
        with self.assertRaises(ValueError):
            m.criar("site", "http://inseguro.com")
        m.criar("site", "https://exemplo.com.br/precos")
        self.assertEqual(m.verificar(forcar=True), [])
        self.assertEqual(m.verificar(forcar=True), [])                    # so o anuncio mudou
        self.assertEqual(m.verificar(forcar=True), ["o site exemplo.com.br/precos mudou."])

    def test_pasta_arquivo_novo_e_pausa(self):
        pasta = Path(tempfile.mkdtemp())
        (pasta / "velho.pdf").write_text("x")
        m, _ = _mon()
        item = m.criar("pasta", str(pasta))
        m.verificar(forcar=True)
        (pasta / "boleto.pdf").write_text("x")
        (pasta / "baixando.crdownload").write_text("x")                  # download em andamento: ignora
        self.assertEqual(m.verificar(forcar=True), [f"arquivo novo em {pasta.name}: boleto.pdf."])
        self.assertEqual(m.mudar([item["id"]], False), 1)
        (pasta / "outro.pdf").write_text("x")
        self.assertEqual(m.verificar(forcar=True), [])                    # pausado
        m.mudar([item["id"]], None)
        self.assertEqual(m.listar(), [])


class TestComandosMonitor(unittest.TestCase):
    def _c(self, **kw):
        mon, avisos = _mon(**kw)
        rt = SimpleNamespace(monitores=mon, prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}),
                             estado=SimpleNamespace(atualizar=mock.Mock()))
        return cmd.Comandos(rt, lambda x: None), mon

    def dizer(self, c, frase):
        nome, args = c.interpretar(frase)
        return c.executar(nome, args, frase)

    def test_por_voz(self):
        c, mon = self._c(noticias=_Noticias(), cotacoes=_Cotacoes(5.0))
        self.assertIn("Aviso quando sair notícia sobre Nvidia", self.dizer(c, "Jarvis, me avise quando sair notícia sobre a Nvidia"))
        self.assertIn("passar de 5 reais e 50 centavos", self.dizer(c, "me avise quando o dólar passar de 5,50"))
        self.assertIn("cair abaixo de 400 mil reais", self.dizer(c, "me avise quando o bitcoin cair abaixo de 400 mil"))
        fala = self.dizer(c, "quais são meus monitores")
        self.assertIn("notícias sobre Nvidia", fala)
        self.assertEqual(self.dizer(c, "pause o monitor da Nvidia"), "Monitor pausado: notícias sobre Nvidia.")
        self.assertIn("(pausado)", self.dizer(c, "quais são meus monitores"))
        self.assertIn("Monitor removido: dólar acima", self.dizer(c, "remova o monitor do dólar"))
        self.assertIn("site x.com", c.monitorar("monitor_site", {"u": "http://x.com"}, ""))     # dito sem https:
        self.assertEqual(mon.listar()[-1]["alvo"], "https://x.com")                              # sempre vira https


class TestModos(unittest.TestCase):
    def _anunciador(self, **prefs):
        p = validar({"silencio_inicio": 0, "silencio_fim": 0, **prefs})
        return Anunciador(falar=lambda t: None, ocupado=lambda: False, prefs=SimpleNamespace(ler=lambda: p))

    def test_categorias_por_modo(self):
        casos = {"sob_demanda": {"pedido"}, "assistido": {"pedido", "agenda", "presenca", "aviso"},
                 "proativo": {"pedido", "agenda", "presenca", "aviso", "observacao"}}
        for modo, aceitas in casos.items():
            a = self._anunciador(modo_proativo=modo)
            for cat in ("agenda", "presenca", "aviso", "observacao"):
                self.assertEqual(a.anunciar("x", categoria=cat), cat in aceitas, (modo, cat))
                a.limpar()
            self.assertTrue(a.anunciar("lembrete", pedido_pelo_usuario=True))
            a.limpar()

    def test_chave_antiga(self):
        self.assertEqual(modo_de({"falas_proativas": False, "modo_proativo": "proativo"}), "sob_demanda")
        p = validar({"falas_proativas": False})
        self.assertEqual(modo_de(p), "sob_demanda")
        p = validar({"modo_proativo": "proativo"}, p)                    # escolher um modo reativa as falas
        self.assertEqual(modo_de(p), "proativo")

    def test_por_voz(self):
        prefs = SimpleNamespace(d=validar({}), ler=None, aplicar=None)
        prefs.ler = lambda: prefs.d
        prefs.aplicar = lambda m: prefs.d.update(validar(m, prefs.d))
        rt = SimpleNamespace(prefs=prefs, _publicar_prefs=lambda: None)
        c = cmd.Comandos(rt, lambda x: None)
        nome, args = c.interpretar("Jarvis, só fale quando eu chamar")
        self.assertIn("Só falo quando o senhor chamar", c.executar(nome, args, "só fale quando eu chamar"))
        self.assertEqual(prefs.d["modo_proativo"], "sob_demanda")


if __name__ == "__main__":
    unittest.main()
