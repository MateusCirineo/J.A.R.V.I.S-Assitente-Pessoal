"""F38: apresentação do artefato corrente, confirmada pela tela após renderizar.

Um acknowledgement não valida geometria de engenharia nem cria outro trabalho.
 IDs atrasados e destinos diferentes nunca confirmam uma apresentação nova.
"""
from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path


class Apresentacao:
    def __init__(self, publicar=lambda **kw: None):
        self._publicar = publicar
        self._trava = threading.RLock()
        self._atual = {"id": None, "destino": "holograma", "estado": "vazia", "arquivo": None}

    def preparar(self, arquivo: Path) -> str:
        arquivo = Path(arquivo)
        if not arquivo.is_file() or arquivo.suffix.lower() not in ('.stl', '.obj'):
            raise ValueError("modelo inexistente ou formato não suportado")
        with self._trava:
            ident = uuid.uuid4().hex
            self._atual = {"id": ident, "destino": "holograma", "estado": "solicitada",
                           "arquivo": str(arquivo), "nome": arquivo.name, "solicitada_em": time.time(),
                           "confirmada_em": None, "validacao_engenharia": False}
            self._publicar(**self._atual)
            return ident

    def atual(self):
        with self._trava:
            return dict(self._atual)

    def confirmar(self, ident: str, destino: str) -> bool:
        with self._trava:
            if not ident or ident != self._atual['id'] or destino != self._atual['destino']:
                return False
            if self._atual['estado'] != 'carregada':
                self._atual.update(estado='carregada', confirmada_em=time.time())
                self._publicar(**self._atual)
            return True
