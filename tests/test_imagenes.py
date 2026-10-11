import requests

from noticias import imagenes
from noticias.imagenes import imagen_generica, imagen_og, imagen_vandal
from tests.conftest import Respuesta


def test_vandal_usa_la_imagen_marcada_como_imagen1(entradas):
    e = entradas("vandal.xml")
    assert imagen_vandal(e[0]) == "https://media.vandal.net/m/10-2026/6/20261061351987_1.jpg"
    # En esta noticia la primera <img> es la miniatura de un vídeo; la principal está al final
    assert imagen_vandal(e[1]) == "https://media.vandal.net/m/18/180853/crimson-desert-202412168462772_1.jpg"
    # Aquí la primera <img> es una imagen del cuerpo del texto
    assert imagen_vandal(e[2]) == "https://media.vandal.net/m/10-2026/8/20261089415622_1.jpg"


def test_el_extractor_generico_no_basta_para_vandal(entradas):
    """Documenta por qué Vandal tiene su propio extractor."""
    e = entradas("vandal.xml")
    assert imagen_generica(e[1]) == "https://videos.vandalimg.com/t320x180/1009876.jpg"


def test_3djuegos_la_imagen_es_la_primera_img(entradas):
    e = entradas("3djuegos.xml")
    assert imagen_generica(e[1]) == "https://i.blogs.es/d2d792/discord/1024_2000.jpeg"
    assert all(imagen_generica(x).startswith("https://i.blogs.es/") for x in e)


def test_generationamiga_no_trae_imagen_en_el_feed(entradas):
    assert [imagen_generica(e) for e in entradas("generationamiga.xml")] == [None, None, None]


def test_media_thumbnail_de_youtube(entradas):
    e = entradas("youtube_canal.xml")[0]
    assert imagen_generica(e) == "https://i1.ytimg.com/vi/XX6h-So_bSA/hqdefault.jpg"


def test_enclosure_de_imagen_y_se_ignoran_otros_tipos():
    import feedparser
    xml = """<rss version="2.0"><channel><item><title>A</title>
    <enclosure url="https://x/audio.mp3" type="audio/mpeg" length="1"/>
    <enclosure url="https://x/foto.jpg" type="image/jpeg" length="1"/></item></channel></rss>"""
    assert imagen_generica(feedparser.parse(xml).entries[0]) == "https://x/foto.jpg"


def test_se_ignoran_pixeles_y_gifs():
    html = '<img src="https://x/pixel.gif"><img src="https://x/a.gif"><img src="https://x/real.jpg">'
    assert imagen_generica({"summary": html}) == "https://x/real.jpg"


def _paginas(monkeypatch, paginas):
    def falso(url, **kw):
        if url not in paginas:
            return Respuesta(404)
        return Respuesta(200, texto=paginas[url])
    monkeypatch.setattr(requests, "get", falso)


def test_og_image_en_sus_variantes(monkeypatch):
    _paginas(monkeypatch, {
        "https://w/1": '<meta property="og:image" content="https://w/img.jpg?a=1&amp;b=2">',
        "https://w/2": '<meta content="/fotos/a.jpg" property="og:image">',
        "https://w/3": '<meta name="twitter:image" content="https://w/tw.png">',
        "https://w/4": "<title>sin imagen</title>",
    })
    assert imagen_og("https://w/1") == "https://w/img.jpg?a=1&b=2"
    assert imagen_og("https://w/2") == "https://w/fotos/a.jpg"
    assert imagen_og("https://w/3") == "https://w/tw.png"
    assert imagen_og("https://w/4") is None


def test_og_image_si_la_pagina_falla_devuelve_none(monkeypatch):
    _paginas(monkeypatch, {})
    assert imagen_og("https://w/no-existe") is None
