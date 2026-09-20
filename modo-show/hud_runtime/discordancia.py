"""Discordar com fundamento -- e com uma saída (F05).

"Não dá" sozinho não ajuda ninguém. O que o prompt mestre (§4) pede é o que um
colaborador técnico faz: apontar o conflito, dizer de onde ele vem e oferecer a
alternativa que cabe.

Três regras aqui:

1. **Só discordo do que eu consigo conferir.** Espessura contra a menor dimensão,
   peça contra a mesa da impressora, horário contra a agenda, tarefa contra um
   serviço desligado. Nada de risco inventado.
2. **Toda discordância traz o número.** "A parede não cabe" vira "a parede não
   cabe: o máximo aqui é 14 milímetros".
3. **Quem decide é o Senhor.** Eu digo o conflito e a alternativa; não recuso o
   que é decisão dele nem faço a troca por conta própria.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable

# limites reais desta oficina (os mesmos de pecas.py)
MESA_MM = 300.0
PAREDE_MINIMA_MM = 0.8
FOLGA_AGENDA_S = 30 * 60           # compromisso a menos de 30 min conta como conflito


@dataclass
class Conflito:
    motivo: str                    # o que está errado, em português
    alternativa: str = ""          # o que dá para fazer, com número
    fonte: str = ""                # de onde tirei o limite
    grave: bool = True             # grave impede; não grave é só um alerta

    def falado(self) -> str:
        frase = self.motivo
        if self.alternativa:
            frase += f"; {self.alternativa}"
        if self.fonte:
            frase += f" ({self.fonte})"
        return frase


def _num(x: float) -> str:
    return f"{x:.10g}".replace(".", ",")


def conflitos_de_peca(tipo: str, p: dict[str, float]) -> list[Conflito]:
    """O que impede essa peça de existir, com o valor que caberia."""
    saida: list[Conflito] = []
    for chave, valor in p.items():
        if valor <= 0 and not (chave == "parede" and valor == 0):
            saida.append(Conflito(f"{chave} não pode ser {_num(valor)}",
                                  "use um valor maior que zero", "geometria"))
        elif valor > MESA_MM and chave != "dentes":
            saida.append(Conflito(
                f"{chave} de {_num(valor)} mm não cabe na mesa",
                f"o máximo é {_num(MESA_MM)} mm; acima disso a peça sai em partes",
                "mesa de 300 mm", grave=False))
    if tipo == "caixa":
        parede = p.get("parede") or 0
        menor = min(p.get("c", 0), p.get("l", 0), p.get("a", 0))
        if parede and parede * 2 >= menor:
            cabe = max(0.0, (menor - 0.2) / 2)
            saida.append(Conflito(
                f"a parede de {_num(parede)} mm não cabe: a menor dimensão tem {_num(menor)} mm",
                f"o máximo aqui é {_num(round(cabe, 1))} mm de parede",
                "duas paredes + o vão interno"))
        elif parede and parede < PAREDE_MINIMA_MM:
            saida.append(Conflito(
                f"parede de {_num(parede)} mm é fina para um bico de 0,4",
                f"com {_num(PAREDE_MINIMA_MM)} mm saem dois perímetros e a peça aguenta",
                "bico de 0,4 mm", grave=False))
    if tipo == "tubo" and p.get("interno", 0) >= p.get("externo", 0):
        saida.append(Conflito(
            f"o furo de {_num(p.get('interno', 0))} mm é maior que o tubo de {_num(p.get('externo', 0))} mm",
            f"deixe o furo abaixo de {_num(p.get('externo', 0) - 1.6)} mm para sobrar parede",
            "geometria"))
    if tipo == "engrenagem":
        if p.get("dentes", 0) < 6:
            saida.append(Conflito(
                f"{int(p.get('dentes', 0))} dentes não formam uma engrenagem",
                "a partir de 6 dentes o perfil fecha; 12 a 20 rodam melhor", "perfil evolvente"))
        if p.get("furo", 0) >= p.get("externo", 0) * 0.8:
            saida.append(Conflito(
                "o furo está grande demais para o diâmetro",
                f"abaixo de {_num(round(p.get('externo', 0) * 0.5, 1))} mm sobra dente", "geometria"))
    return saida


def conflito_de_horario(quando: float, eventos: Iterable[dict[str, Any]],
                        folga_s: float = FOLGA_AGENDA_S) -> Conflito | None:
    """Um lembrete em cima de um compromisso da agenda de verdade."""
    for e in eventos or []:
        inicio = e.get("inicio")
        if not inicio:
            continue
        if abs(float(inicio) - quando) <= folga_s:
            hora = time.strftime("%H:%M", time.localtime(float(inicio)))
            titulo = str(e.get("titulo") or "um compromisso")[:60]
            return Conflito(
                f"nesse horário o senhor tem {titulo}, às {hora}",
                "posso marcar depois, se preferir", "sua agenda")
    return None


def conflito_de_recurso(necessario: str, estado: dict[str, Any]) -> Conflito | None:
    """A tarefa depende de algo que está desligado ou ausente AGORA (F30)."""
    mapa = {
        "camera": ("camera", "ativa", "a câmera está desligada", "diga: ligue a câmera"),
        "servidor": ("conexao", "servidor", "o servidor do OpenJarvis não está respondendo",
                     "use o botão Religar no cartão Serviços do Painel"),
        "microfone": ("microfone", "estado", "o microfone está desativado",
                      "ligue o microfone no Painel"),
    }
    if necessario not in mapa:
        return None
    canal, chave, motivo, saida = mapa[necessario]
    valor = (estado.get(canal) or {}).get(chave)
    if necessario == "camera" and not valor:
        return Conflito(motivo, saida, "estado da câmera")
    if necessario == "microfone" and valor in (None, "desativado", "erro"):
        return Conflito(motivo, saida, "estado do microfone")
    if necessario == "servidor":
        est = (valor or {}).get("estado") if isinstance(valor, dict) else valor
        if est in ("erro", "desconectado"):
            return Conflito(motivo, saida, "estado do servidor")
    return None


def falar(conflitos: list[Conflito], pedido: str = "", tratamento: str = "Senhor") -> str:
    """Uma frase de colaborador: o conflito, o motivo e o caminho."""
    if not conflitos:
        return ""
    graves = [c for c in conflitos if c.grave]
    if graves:
        abertura = f"Não dá assim, {tratamento}" if not pedido else f"Assim não dá, {tratamento}"
        return abertura + ": " + "; ".join(c.falado() for c in graves) + "."
    return ("Dá para fazer, mas fique sabendo: "
            + "; ".join(c.falado() for c in conflitos) + f", {tratamento}.")
