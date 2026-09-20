"""Varredura de imagens (F3): analisa sem mover, quarentena so confirmada,
confere hash, restaura sem sobrescrever e nunca apaga."""

import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hud_runtime import comandos as cmd, documentos, varredura  # noqa: E402


def falso(caminho):
    """Classificador de teste: sinaliza arquivos com 'sens' no nome."""
    return ("sens" in caminho.name, "teste")


def _pasta():
    base = Path(tempfile.mkdtemp())
    fotos = base / "Fotos"
    fotos.mkdir()
    for nome in ("praia.jpg", "sens_1.png", "sens_2.jpg", "notas.txt"):
        (fotos / nome).write_bytes(nome.encode() * 10)
    return base, fotos


def contar(base):
    return sum(1 for p in base.rglob("*") if p.is_file() and p.suffix in (".jpg", ".png"))


class TestVarredura(unittest.TestCase):
    def test_ciclo_completo_sem_apagar(self):
        base, fotos = _pasta()
        vr = varredura.Varredura(falso, home=base / "home")
        total = contar(base)
        rel = vr.analisar(fotos)
        self.assertEqual((rel["analisadas"], rel["sinalizadas"]), (3, 2))       # .txt nao e imagem
        self.assertTrue(all(len(x["sha256"]) == 64 for x in rel["itens"]))
        self.assertTrue((fotos / "sens_1.png").exists())                         # analise nao move nada
        (fotos / "sens_2.jpg").write_bytes(b"mudou depois da analise")
        r = vr.quarentenar(rel)
        self.assertEqual((r["movidos"], r["pulados"]), (1, 1))                   # o que mudou fica
        self.assertFalse((fotos / "sens_1.png").exists())
        self.assertTrue((fotos / "sens_2.jpg").exists())
        self.assertEqual(contar(base), total)                                    # nada apagado
        self.assertTrue(vr.ultimo_relatorio()["movido"])
        (fotos / "sens_1.png").write_bytes(b"outro arquivo com o mesmo nome")
        r = vr.restaurar()
        self.assertEqual((r["restaurados"], r["problemas"]), (1, []))
        self.assertEqual((fotos / "sens_1 (restaurado).png").read_bytes(), b"sens_1.png" * 10)   # nao sobrescreveu
        self.assertEqual((fotos / "sens_1.png").read_bytes(), b"outro arquivo com o mesmo nome")
        self.assertEqual(vr.em_quarentena(), [])
        self.assertEqual(vr.restaurar()["restaurados"], 0)

    def test_imagem_ruim_nao_para_a_varredura(self):
        base, fotos = _pasta()

        def explode(c):
            if c.name == "praia.jpg":
                raise ValueError("ilegível")
            return falso(c)
        rel = varredura.Varredura(explode, home=base / "home").analisar(fotos)
        self.assertEqual(rel["analisadas"], 3)
        self.assertIn("não analisada", next(x for x in rel["itens"] if x["caminho"].endswith("praia.jpg"))["motivo"])


class TestComandosVarredura(unittest.TestCase):
    def test_por_voz(self):
        base, fotos = _pasta()
        pronto = threading.Event()
        falas = []
        anunciador = SimpleNamespace(anunciar=lambda t, **kw: (falas.append(t), pronto.set()))
        rt = SimpleNamespace(prefs=SimpleNamespace(ler=lambda: {"nome_usuario": "Senhor"}), anunciador=anunciador,
                             estado=SimpleNamespace(atualizar=mock.Mock()),
                             varredura=varredura.Varredura(falso, home=base / "home"))
        c = cmd.Comandos(rt, lambda x: None)

        def dizer(frase):
            nome, args = c.interpretar(frase)
            return c.executar(nome, args, frase)
        self.assertIn("Não há imagens sinalizadas", dizer("confirmo quarentena"))
        with mock.patch.object(documentos, "pasta_conhecida", lambda n: fotos):
            fala = dizer("Jarvis, verifique as imagens da pasta Downloads")
        self.assertIn("Não vou mover nada sem sua confirmação", fala)
        self.assertTrue(pronto.wait(10))
        self.assertIn("2 parecem sensíveis. Nada foi movido", falas[0])
        self.assertTrue((fotos / "sens_1.png").exists())
        self.assertIn("Para confirmar", dizer("mova para a quarentena"))
        self.assertTrue((fotos / "sens_1.png").exists())                         # pedir nao move; so confirmar
        self.assertEqual(dizer("Jarvis, confirmo quarentena"), "2 imagens na quarentena. Para desfazer, diga: restaure a quarentena.")
        self.assertIn("Há 2 imagens na quarentena", dizer("o que tem na quarentena?"))
        self.assertEqual(dizer("restaure a quarentena"), "2 imagens devolvidas ao lugar de origem.")
        self.assertTrue((fotos / "sens_1.png").exists())


if __name__ == "__main__":
    unittest.main()
