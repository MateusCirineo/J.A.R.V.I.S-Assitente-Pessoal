"""Avisos do HUD tambem como notificacao do Windows (toast).

Um programa sem pacote (como este runtime) so consegue mostrar toast se tiver
um AppUserModelID registrado. O registro fica so na conta do usuario
(HKCU\\Software\\Classes\\AppUserModelId\\OpenJarvis.JarvisHUD), com nome e icone
do Jarvis: nao pede administrador nem permissao nova. O modo "Nao perturbe" do
Windows continua valendo. Desligavel em Preferencias (notificacoes_windows).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

AUMID = "OpenJarvis.JarvisHUD"
CHAVE = rf"Software\Classes\AppUserModelId\{AUMID}"
TITULOS = {"erro": "Jarvis · alerta", "aviso": "Jarvis · aviso", "info": "Jarvis"}


def registrar_app(icone: Path | None = None) -> None:
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CHAVE) as k:
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "Jarvis")
        if icone and icone.exists():
            winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, str(icone))


def desregistrar_app() -> None:
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CHAVE)
    except OSError:
        pass


def xml_toast(texto: str, nivel: str = "info") -> str:
    return ("<toast><visual><binding template=\"ToastGeneric\">"
            f"<text>{escape(TITULOS.get(nivel, 'Jarvis'))}</text><text>{escape(texto[:250])}</text>"
            "</binding></visual></toast>")


def vai_para_o_windows(item: dict[str, Any]) -> bool:
    """So o que pede atencao: avisos, alertas, compromisso e download concluido."""
    return (item.get("nivel") in ("aviso", "erro") or item.get("tipo") in ("agenda", "email", "lembrete")
            or str(item.get("texto", "")).startswith("Download concluído"))


class AvisosWindows:
    def __init__(self, icone: Path | None = None) -> None:
        self._notificador = None
        self._erro: str | None = None
        self._trava = threading.Lock()
        try:
            registrar_app(icone)
            from winrt.windows.ui.notifications import ToastNotificationManager
            self._notificador = ToastNotificationManager.create_toast_notifier_with_id(AUMID)
        except Exception as e:  # noqa: BLE001 - sem toast, o HUD continua avisando na tela
            self._erro = str(e)[:140]

    @property
    def disponivel(self) -> bool:
        return self._notificador is not None

    @property
    def erro(self) -> str | None:
        return self._erro

    def mostrar(self, texto: str, nivel: str = "info") -> bool:
        if not self._notificador:
            return False
        from winrt.windows.data.xml.dom import XmlDocument
        from winrt.windows.ui.notifications import ToastNotification
        with self._trava:
            try:
                doc = XmlDocument()
                doc.load_xml(xml_toast(texto, nivel))
                self._notificador.show(ToastNotification(doc))
                return True
            except Exception as e:  # noqa: BLE001
                self._erro = str(e)[:140]
                return False
