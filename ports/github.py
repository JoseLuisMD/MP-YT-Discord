"""Llamadas a la API de GitHub: notificaciones de releases, historial de releases y marcar como hechas.

Usa el token GH_NOTIFICATIONS_TOKEN (classic, solo con el permiso `notifications`), que también sirve para leer
las releases de los repos públicos.
"""
import os

import requests

API = "https://api.github.com"


class GitHub:
    def __init__(self, token=None, sesion=None):
        self.sesion = sesion or requests.Session()
        self.sesion.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {token or os.environ['GH_NOTIFICATIONS_TOKEN']}",
        })

    def _paginas(self, url, params=None):
        """Todos los elementos de una lista paginada de la API."""
        while url:
            r = self.sesion.get(url, params=params, timeout=30)
            r.raise_for_status()
            yield from r.json()
            url, params = r.links.get("next", {}).get("url"), None

    def notificaciones_de_releases(self, desde=None):
        """Las notificaciones de releases de la bandeja (también las leídas y las ya marcadas como hechas),
        actualizadas desde `desde` (ISO 8601) si se indica."""
        params = {"all": "true", "per_page": 50}
        if desde:
            params["since"] = desde
        return [n for n in self._paginas(f"{API}/notifications", params) if n["subject"]["type"] == "Release"]

    def releases(self, repo):
        """Todas las releases publicadas de un repo (owner/nombre), la más nueva primero."""
        return list(self._paginas(f"{API}/repos/{repo}/releases", {"per_page": 100}))

    def marcar_hecha(self, id_hilo):
        """Marca una notificación como hecha («Done»). Devuelve True si ha ido bien."""
        r = self.sesion.delete(f"{API}/notifications/threads/{id_hilo}", timeout=30)
        return r.status_code in (204, 205)
