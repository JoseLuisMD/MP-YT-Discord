import json
import random
from datetime import datetime, timezone

import pytest

from noticias import proceso
from noticias.fuentes import FUENTES

AHORA = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)   # los fixtures son de la mañana de ese día


class Red:
    def __init__(self, resultado=True):
        self.publicaciones, self.resultado = [], resultado

    def publicar(self, p):
        self.publicaciones.append(p)
        return self.resultado


@pytest.fixture
def entorno(monkeypatch, cargar, tmp_path):
    fixtures = {"vandal": "vandal.xml", "3djuegos": "3djuegos.xml", "generationamiga": "generationamiga.xml"}
    fuentes = [f for f in FUENTES if f.nombre in ("Vandal", "3DJuegos", "GenerationAmiga")]

    def parse(url):
        return cargar(next(v for k, v in fixtures.items() if k in url))

    estado = {"resumir": lambda titulo, texto, otro_idioma=False: (f"Resumen de {titulo[:20]}", ["#uno", "#dos"])}
    monkeypatch.setattr(proceso, "resumir", lambda *a, **k: estado["resumir"](*a, **k))
    monkeypatch.setattr(proceso, "imagen_og", lambda enlace: "https://og/imagen.jpg")
    ruta = tmp_path / "noticias_publicadas.json"

    def correr(red=None, rng=None, historial=None, ahora=AHORA):
        if historial is not None:
            ruta.write_text(json.dumps(historial), encoding="utf-8")
        red = red or Red()
        proceso.ejecutar(fuentes=fuentes, ruta=str(ruta), parse=parse, publicadores=[red], ahora=ahora,
                         rng=rng or random.Random(1))
        return red, json.loads(ruta.read_text(encoding="utf-8"))

    return correr, estado


def test_publica_la_noticia_que_coincide_con_una_palabra_clave(entorno):
    correr, _ = entorno
    red, historial = correr()
    assert len(red.publicaciones) == 1
    p = red.publicaciones[0]
    # Coinciden «Sonic Mania» (GenerationAmiga) y «Mario Kart» (3DJuegos); gana la más reciente
    assert p.enlace == "https://www.generationamiga.com/2026/10/10/sonic-mania-saturn/"
    assert p.texto.endswith("\n\n📰 GenerationAmiga")
    assert p.hashtags == ["#uno", "#dos"]
    assert historial == [p.enlace]


def test_la_segunda_ejecucion_publica_la_siguiente_y_no_repite(entorno):
    correr, _ = entorno
    _, h1 = correr()
    red, h2 = correr()
    assert red.publicaciones[0].enlace == "https://www.3djuegos.com/juegos/noticias/mario-kart-parche"
    assert h2 == h1 + [red.publicaciones[0].enlace]


def test_sin_coincidencias_publica_una_al_azar_de_las_que_quedan(entorno):
    correr, _ = entorno
    red, historial = correr(historial=[
        "https://www.generationamiga.com/2026/10/10/sonic-mania-saturn/",
        "https://www.3djuegos.com/juegos/noticias/mario-kart-parche",
    ])
    assert len(red.publicaciones) == 1 and len(historial) == 3
    assert red.publicaciones[0].enlace not in historial[:2]


def test_las_secciones_excluidas_de_3djuegos_nunca_se_publican(entorno):
    correr, _ = entorno
    publicadas = []
    for _ in range(10):
        red, _historial = correr()
        publicadas += [p.enlace for p in red.publicaciones]
    assert not any(x for x in publicadas if "/tv-series/" in x or "/manga-anime/" in x or "trivia" in x)
    assert len(publicadas) == 8 and len(set(publicadas)) == 8   # 3 Vandal + 2 3DJuegos + 3 GenerationAmiga


def test_noticia_en_otro_idioma_sin_resumen_no_se_publica_ni_se_guarda(entorno):
    correr, estado = entorno
    estado["resumir"] = lambda titulo, texto, otro_idioma=False: None if otro_idioma else ("Resumen", [])
    red, historial = correr()
    assert red.publicaciones == [] and historial == []


def test_se_pasa_a_resumir_si_la_fuente_esta_en_otro_idioma(entorno):
    correr, estado = entorno
    recibido = {}

    def resumir(titulo, texto, otro_idioma=False):
        recibido["otro_idioma"] = otro_idioma
        return "Resumen", []
    estado["resumir"] = resumir
    correr()   # la elegida es de GenerationAmiga (inglés)
    assert recibido["otro_idioma"] is True


def test_usa_la_imagen_del_feed_y_si_no_hay_la_de_la_pagina(entorno):
    correr, _ = entorno
    ga, _ = correr()                                    # GenerationAmiga: sin imagen en el feed
    assert ga.publicaciones[0].url_imagen == "https://og/imagen.jpg"
    mk, _ = correr()                                    # 3DJuegos: imagen en el feed
    assert mk.publicaciones[0].url_imagen == "https://i.blogs.es/aa11bb/mario/1024_2000.jpeg"


def test_solo_las_fuentes_marcadas_adjuntan_la_imagen_en_threads(entorno):
    correr, _ = entorno
    ga, _ = correr()                                    # GenerationAmiga: Threads ya muestra su tarjeta
    assert ga.publicaciones[0].imagen_en_threads is False
    mk, _ = correr()                                    # 3DJuegos: adjuntamos la imagen nosotros
    assert mk.publicaciones[0].imagen_en_threads is True


def test_si_ninguna_red_publica_la_noticia_no_se_guarda(entorno):
    correr, _ = entorno
    red, historial = correr(Red(resultado=False))
    assert len(red.publicaciones) == 1 and historial == []


def test_el_historial_se_recorta(entorno, monkeypatch):
    correr, _ = entorno
    monkeypatch.setattr(proceso, "MAX_HISTORIAL", 3)
    _, historial = correr(historial=[f"https://x/{i}" for i in range(10)])
    assert len(historial) == 3 and historial[:2] == ["https://x/8", "https://x/9"]


def test_noticias_de_hace_mas_de_24_horas_no_son_candidatas(entorno):
    correr, _ = entorno
    red, historial = correr(ahora=datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc))
    assert red.publicaciones == [] and historial == []
