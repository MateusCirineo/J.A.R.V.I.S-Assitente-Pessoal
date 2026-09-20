"""Cotacoes (Q5/Q6), conversa casual (Q7), noticias por categoria/tema (N1),
"abra a segunda noticia" (N2), pesquisa com fontes (N3) e TLS (N4)."""

import gzip
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime import comandos as cmd, cotacoes, noticias, pesquisa, rede  # noqa: E402

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Primeira manchete longa o bastante para contar - Folha de S.Paulo</title><link>https://a.example/1</link>
<pubDate>Fri, 18 Sep 2026 12:00:00 GMT</pubDate></item>
<item><title>Segunda manchete longa o bastante para contar - G1</title><link>http://b.example/2</link>
<pubDate>Fri, 18 Sep 2026 11:00:00 GMT</pubDate></item>
</channel></rss>"""


class _Prefs:
    def __init__(self, d=None):
        self.d = d or {"nome_usuario": "Senhor"}

    def ler(self):
        return dict(self.d)


class _Estado:
    def __init__(self, mic="ouvindo", srv="ok"):
        self.canais = {"microfone": {"estado": mic}}
        self.srv = srv
        self.telemetria = {}
        self.contexto = None

    def ler(self, canal):
        return self.canais.get(canal)

    def instantaneo(self):
        return {"conexao": {"servidor": {"estado": self.srv}}}

    def atualizar(self, canal, **kw):
        if canal == "contexto":
            self.contexto = kw


def _rt(**extra):
    rt = SimpleNamespace(prefs=_Prefs(), estado=_Estado(), conversa=SimpleNamespace(encerrar_conversa=mock.Mock()))
    for k, v in extra.items():
        setattr(rt, k, v)
    return rt


class TestCotacoes(unittest.TestCase):
    def test_valores_falados(self):
        self.assertEqual(cotacoes.reais_falados(5.1463), "5 reais e 15 centavos")
        self.assertEqual(cotacoes.reais_falados(1.0), "1 real")
        self.assertEqual(cotacoes.reais_falados(0.42), "42 centavos")
        self.assertEqual(cotacoes.reais_falados(416322), "416 mil 322 reais")
        self.assertEqual(cotacoes.reais_falados(13000), "13 mil reais")
        self.assertEqual(cotacoes.reais_falados(2_500_000), "2 milhões 500 mil de reais")
        self.assertEqual(cotacoes.pct_falado(0.4176), "alta de 0,4 por cento")
        self.assertEqual(cotacoes.pct_falado(-5.0), "queda de 5 por cento")
        self.assertEqual(cotacoes.pct_falado(0.01), "estável")

    def test_ativos(self):
        self.assertEqual(cotacoes.ativos_citados("quanto está o dólar e o Bitcoin? e o dólar de novo"),
                         [("moeda", "USD"), ("cripto", "bitcoin")])
        self.assertEqual(cotacoes.ativos_citados("preço do ether"), [("cripto", "ethereum")])
        self.assertEqual(cotacoes.ativos_citados("dólar canadense"), [("moeda", "CAD")])

    def test_consulta_com_fonte_e_horario(self):
        def falso(url, timeout=10):
            if "awesomeapi" in url:
                return {"USDBRL": {"bid": "5.1459", "ask": "5.1463", "pctChange": "0.4176", "timestamp": "1789757739"}}
            return {"bitcoin": {"brl": 416322, "usd": 80899, "brl_24h_change": 5.68, "last_updated_at": 1789758160}}
        c = cotacoes.Cotacoes()
        with mock.patch.object(cotacoes, "baixar_json", falso):
            r = c.consultar([("moeda", "USD"), ("cripto", "bitcoin")])
        fala = cotacoes.cotacao_falada(r)
        self.assertIn("O dólar está em 5 reais e 15 centavos na venda", fala)
        self.assertIn("416 mil 322 reais", fala)
        self.assertIn("Fonte: AwesomeAPI", fala)
        self.assertIn("CoinGecko", fala)
        card = cotacoes.cartao(r)
        self.assertEqual(card["itens"][1]["titulo"], "bitcoin: R$ 416.322")

    def test_fonte_fora_do_ar(self):
        def cai(url, timeout=10):
            raise OSError("sem rede")
        with mock.patch.object(cotacoes, "baixar_json", cai):
            r = cotacoes.Cotacoes().consultar([("moeda", "USD")])
        self.assertEqual(r["status"], "erro")
        self.assertIn("não respondeu", cotacoes.cotacao_falada(r))


class TestNoticias(unittest.TestCase):
    def test_categoria_so_para_palavras_genericas(self):
        self.assertEqual(noticias.detectar_categoria("tecnologia"), "tecnologia")
        self.assertEqual(noticias.detectar_categoria("de esporte"), "esportes")
        self.assertEqual(noticias.detectar_categoria("economia de hoje"), "economia")
        self.assertEqual(noticias.detectar_categoria("do dia"), "geral")
        self.assertIsNone(noticias.detectar_categoria("o Corinthians"))
        self.assertIsNone(noticias.detectar_categoria("inteligência artificial na medicina"))

    def test_catalogo_coerente(self):
        for cat, chaves in noticias.CATEGORIAS.items():
            self.assertTrue(chaves, cat)
            for c in chaves:
                self.assertIn(c, noticias.FONTES)
                self.assertTrue(noticias.FONTES[c][1].startswith("https://"), c)

    def test_busca_por_tema_separa_veiculo(self):
        n = noticias.Noticias()
        with mock.patch.object(noticias, "baixar", return_value=RSS) as b:
            r = n.buscar("Corinthians")
        self.assertIn("q=Corinthians", b.call_args[0][0])
        self.assertEqual(r["itens"][0]["fonte"], "Folha de S.Paulo")
        self.assertEqual(r["itens"][0]["titulo"], "Primeira manchete longa o bastante para contar")

    def test_categoria_tolera_fonte_fora(self):
        n = noticias.Noticias()

        def baixar(url, limite=0):
            if "g1.globo" in url:
                raise OSError("fora")
            return RSS
        with mock.patch.object(noticias, "baixar", baixar):
            r = n.por_categoria("tecnologia")
        self.assertEqual(r["status"], "medido")
        self.assertTrue(any("G1 Tecnologia" in f for f in r["falhas"]))

    def test_numeradas(self):
        dados = {"status": "medido", "itens": [{"fonte": "G1", "titulo": "Um."}, {"fonte": "BBC", "titulo": "Dois"}]}
        self.assertEqual(noticias.manchetes_faladas(dados, 2, numerar=True, titulo="Manchetes"),
                         "Manchetes. Primeira, G1: Um. Segunda, BBC: Dois. Li apenas as manchetes.")


class TestRede(unittest.TestCase):
    def test_gzip_sem_pedir(self):
        corpo = gzip.compress(b"<rss/>")

        class Resp(io.BytesIO):
            headers = {"Content-Encoding": ""}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        with mock.patch.object(rede, "_ABRIR", lambda req, timeout: Resp(corpo)):
            self.assertEqual(rede.baixar("https://x.example/feed"), b"<rss/>")
        with self.assertRaises(ValueError):
            rede.baixar("file:///c:/segredo.txt")

    def test_nunca_desliga_tls(self):
        raiz = Path(__file__).resolve().parent.parent / "hud_runtime"
        for arq in raiz.glob("*.py"):
            s = arq.read_text(encoding="utf-8")
            self.assertNotIn("CERT_NONE", s, arq.name)
            self.assertNotIn("check_hostname = False", s, arq.name)
            self.assertNotIn("_create_unverified_context", s, arq.name)


class TestPesquisa(unittest.TestCase):
    def test_wikipedia_com_fonte(self):
        def falso(url, timeout=10):
            if "list=search" in url:
                return {"query": {"search": [{"title": "Alan Turing"}]}}
            return {"type": "standard", "title": "Alan Turing",
                    "extract": "Alan Turing foi um matemático britânico. Foi pioneiro da computação. Morreu em 1954.",
                    "content_urls": {"desktop": {"page": "https://pt.wikipedia.org/wiki/Alan_Turing"}}}
        p = pesquisa.Pesquisa()
        with mock.patch.object(pesquisa, "baixar_json", falso):
            r = p.responder("sobre Alan Turing")
        self.assertEqual(r["consulta"], "Alan Turing")
        self.assertTrue(r["fala"].startswith("Segundo a Wikipédia: Alan Turing foi um matemático britânico."))
        self.assertNotIn("1954", r["fala"])                      # so as duas primeiras frases
        self.assertEqual(r["fontes"][0]["link"], "https://pt.wikipedia.org/wiki/Alan_Turing")

    def test_sem_fontes_nao_inventa(self):
        p = pesquisa.Pesquisa(noticias=SimpleNamespace(buscar=lambda q, limite=3: {"status": "medido", "itens": []}))
        with mock.patch.object(pesquisa, "baixar_json", lambda url, timeout=10: {}):
            r = p.responder("xyzzy qwerty")
        self.assertEqual(r["status"], "sem_fontes")
        self.assertIn("Não encontrei fontes", r["fala"])


class TestRotas(unittest.TestCase):
    CASOS = {
        "Jarvis, quanto está o dólar?": "cotacao", "cotação do bitcoin": "cotacao",
        "como estão as criptomoedas": "cotacao", "qual o valor do euro": "cotacao",
        "Jarvis, o que é bitcoin?": "saber", "Jarvis, quem foi Alan Turing?": "saber",
        "me fale sobre a Torre Eiffel": "saber", "o que é isso?": "visao",
        "Jarvis, notícias de tecnologia": "noticias", "abra a segunda notícia": "noticia_abrir",
        "Jarvis, abre a notícia 3": "noticia_abrir", "busque receitas de bolo": "pesquisar",
        "pesquise no google receita de bolo": "pesquisar", "quem é você?": "quem_e_voce",
        "Jarvis, o que você sabe fazer?": "quem_e_voce", "conte uma piada": "piada",
        "tchau Jarvis": "despedida", "oi Jarvis": "cumprimento", "Jarvis, como você está?": "como_voce_esta",
    }

    def test_rotas(self):
        for frase, esperado in self.CASOS.items():
            achado = cmd.interpretar(frase)
            self.assertEqual(achado[0] if achado else None, esperado, frase)
        for frase in ("o que é melhor, python ou java?", "quem foi que ligou?"):
            self.assertIsNone(cmd.interpretar(frase), frase)      # vao para o modelo


class TestComandos(unittest.TestCase):
    def test_noticias_por_categoria_e_abrir_a_segunda(self):
        itens = [{"titulo": "Manchete A", "fonte": "G1 Tecnologia", "link": "https://a/1", "em": 1},
                 {"titulo": "Manchete B", "fonte": "Tecnoblog", "link": "http://b/2", "em": 2}]
        svc = SimpleNamespace(por_categoria=mock.Mock(return_value={"status": "medido", "itens": itens}),
                              buscar=mock.Mock(), obter=mock.Mock())
        rt = _rt(noticias=svc)
        c = cmd.Comandos(rt, lambda x: None)
        fala = c.executar("noticias", {}, "Jarvis, notícias de tecnologia por favor")
        svc.por_categoria.assert_called_once_with("tecnologia")
        self.assertTrue(fala.startswith("Manchetes de tecnologia. Primeira, G1 Tecnologia: Manchete A."))
        self.assertEqual(rt.estado.contexto["tipo"], "noticias")
        with mock.patch.object(c, "_abrir_url") as abrir:
            fala = c.executar("noticia_abrir", {"ord": "segunda"}, "abra a segunda notícia")
        abrir.assert_called_once_with("https://b/2")              # http vira https
        self.assertIn("Tecnoblog", fala)
        self.assertIn("Só tenho 2", c.executar("noticia_abrir", {"ord": "quinta"}, ""))

    def test_noticias_tema_livre(self):
        svc = SimpleNamespace(buscar=mock.Mock(return_value={"status": "medido", "itens": []}))
        c = cmd.Comandos(_rt(noticias=svc), lambda x: None)
        self.assertEqual(c.executar("noticias", {}, "notícias sobre o Corinthians hoje"),
                         "Não encontrei notícias recentes sobre o Corinthians.")
        svc.buscar.assert_called_once_with("o Corinthians")

    def test_pesquisa_sem_fonte_abre_navegador(self):
        svc = SimpleNamespace(responder=lambda q: {"status": "sem_fontes", "consulta": q,
                                                   "fala": f"Não encontrei fontes confiáveis sobre {q}.", "fontes": []})
        c = cmd.Comandos(_rt(pesquisa=svc), lambda x: None)
        with mock.patch.object(c, "_abrir_url") as abrir:
            fala = c.executar("pesquisar", {"q": "xyzzy"}, "pesquise xyzzy")
        self.assertIn("google.com/search", abrir.call_args[0][0])
        self.assertIn("Abri a busca no navegador", fala)

    def test_casual(self):
        rt = _rt()
        c = cmd.Comandos(rt, lambda x: None)
        self.assertEqual(c.executar("como_voce_esta", {}, "tudo bem?"), "Operacional e à disposição, Senhor.")
        rt.estado.telemetria = {"sistema": {"memoria": {"status": "medido", "uso_pct": 95}}}
        rt.estado.canais["microfone"]["estado"] = "bloqueado"
        fala = c.executar("como_voce_esta", {}, "tudo bem?")
        self.assertIn("95 por cento", fala)
        self.assertIn("bloqueando o microfone", fala)
        self.assertNotIn("Operacional e", fala)
        c.executar("despedida", {}, "tchau")
        rt.conversa.encerrar_conversa.assert_called_once()
        piadas = {c.executar("piada", {}, "piada") for _ in range(len(cmd.Comandos.PIADAS))}
        self.assertEqual(len(piadas), len(cmd.Comandos.PIADAS))   # nao repete antes de contar todas
        self.assertIn("Posso dar o resumo do dia", c.executar("quem_e_voce", {}, "o que você sabe fazer?"))


if __name__ == "__main__":
    unittest.main()
