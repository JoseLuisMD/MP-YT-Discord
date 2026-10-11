from pathlib import Path

import feedparser
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def cargar():
    """Lee un feed guardado en tests/fixtures y devuelve el resultado de feedparser."""
    def _cargar(nombre):
        return feedparser.parse(str(FIXTURES / nombre))
    return _cargar


@pytest.fixture
def entradas(cargar):
    return lambda nombre: cargar(nombre).entries


class Respuesta:
    """Respuesta HTTP simulada para las pruebas."""

    def __init__(self, status=200, datos=None, texto="", cabeceras=None, contenido=b"x"):
        import requests
        self.status_code = status
        self._datos = datos or {}
        self.text = texto
        self.headers = cabeceras or {}
        self.content = contenido
        self._requests = requests

    def raise_for_status(self):
        if self.status_code >= 400:
            raise self._requests.HTTPError(str(self.status_code), response=self)

    def json(self):
        return self._datos
