from datetime import datetime, timezone

from noticias.fuentes import FUENTES, Fuente
from common.texto import normalizar
from noticias.imagenes import imagen_vandal


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def fuente(nombre):
    return next(f for f in FUENTES if f.nombre == nombre)


def test_url_sin_plantilla_se_queda_igual():
    assert Fuente("X", "https://x/feed").urls() == ["https://x/feed"]


def test_url_con_fecha_usa_el_mes_actual():
    f = Fuente("X", "https://x/{aaaa}/{mm}/feed/")
    assert f.urls(utc(2026, 10, 10, 11, 0)) == ["https://x/2026/10/feed/"]


def test_a_primeros_de_mes_tambien_se_consulta_el_anterior():
    f = Fuente("X", "https://x/{aaaa}/{mm}/feed/")
    assert f.urls(utc(2026, 11, 1, 0, 30)) == ["https://x/2026/10/feed/", "https://x/2026/11/feed/"]
    assert f.urls(utc(2026, 11, 2, 12, 0)) == ["https://x/2026/11/feed/"]


def test_cambio_de_anio():
    f = Fuente("X", "https://x/{aaaa}/{mm}/feed/")
    assert f.urls(utc(2027, 1, 1, 8, 0)) == ["https://x/2026/12/feed/", "https://x/2027/01/feed/"]


def test_3djuegos_descarta_las_secciones_que_no_son_de_videojuegos(cargar):
    noticias = fuente("3DJuegos").noticias(parse=lambda url: cargar("3djuegos.xml"))
    assert len(noticias) == 14   # de 27: fuera series, anime y trivia
    assert not any(r in n.enlace for n in noticias for r in ("/tv-series/", "/manga-anime/", "/3djuegos-trivia/"))
    n = noticias[0]
    assert n.fuente == "3DJuegos" and n.idioma == "es"
    assert n.enlace.startswith("https://www.3djuegos.com/juegos/the-legend-of-zelda-ocarina-of-time/noticias/")
    assert n.url_imagen == "https://i.blogs.es/a2a426/qwrtr/1024_2000.jpeg"
    assert n.fecha == utc(2026, 10, 11, 19, 15, 24).timestamp()   # 21:15:24 en horario de España
    assert "<" not in n.texto and n.texto                           # sin HTML


def test_3djuegos_sin_recuadros_ni_lineas_en_3djuegos(cargar):
    # Misma plantilla que VidaExtra (Webedia): recuadros «desvío» y líneas «En 3DJuegos | ...»
    for n in fuente("3DJuegos").noticias(parse=lambda url: cargar("3djuegos.xml")):
        assert "En 3DJuegos |" not in n.texto


def test_vandal_extrae_la_imagen_principal(cargar):
    f = fuente("Vandal")
    assert f.extraer_imagen is imagen_vandal
    noticias = f.noticias(parse=lambda url: cargar("vandal.xml"))
    assert len(noticias) == 30
    assert noticias[1].url_imagen == "https://media.vandal.net/m/10-2026/11/2026101118273559_1.jpg"
    assert all(n.url_imagen.startswith("https://media.vandal.net/") for n in noticias)


def test_generationamiga_esta_en_ingles_y_su_texto_queda_limpio(cargar):
    f = fuente("GenerationAmiga")
    assert f.idioma == "en"
    noticias = f.noticias(parse=lambda url: cargar("generationamiga.xml"), ahora=utc(2026, 10, 11, 20, 0))
    assert len(noticias) == 10
    assert noticias[0].titulo == "After more than a decade, Forza Horizon 2 is no longer stuck on Xbox"
    assert "Forza Horizon 2" in noticias[0].texto and "&#8230;" not in noticias[0].texto
    assert noticias[0].url_imagen is None


def test_feed_vacio_devuelve_lista_vacia_y_lo_anota(capsys):
    class Vacio:
        entries = []
    assert Fuente("Web", "https://w/feed").noticias(parse=lambda url: Vacio()) == []
    assert "Sin entradas en Web" in capsys.readouterr().out


def test_se_saltan_las_entradas_sin_enlace_o_sin_titulo():
    from feedparser.util import FeedParserDict

    class Feed:
        entries = [FeedParserDict(title="Sin enlace"), FeedParserDict(link="https://w/1"),
                   FeedParserDict(title="Buena", link="https://w/2#comentarios")]
    noticias = Fuente("Web", "https://w/feed").noticias(parse=lambda url: Feed())
    assert [(n.titulo, n.enlace) for n in noticias] == [("Buena", "https://w/2")]


def test_la_lista_de_fuentes_es_coherente():
    nombres = [f.nombre for f in FUENTES]
    assert len(nombres) == len(set(nombres))
    assert all(f.url.startswith("https://") for f in FUENTES)


def test_vidaextra_los_recuadros_que_enlazan_a_otra_noticia_no_cuentan(cargar):
    # Caso real: la noticia de WandaVision enlaza a un artículo de World of Warcraft en un recuadro «desvío»
    sin_filtro = Fuente("VidaExtra", "https://www.vidaextra.com/feedburner.xml")   # WandaVision es de /series/
    noticias = sin_filtro.noticias(parse=lambda url: cargar("vidaextra.xml"))
    wanda = next(n for n in noticias if "WandaVision" in n.titulo)
    assert "warcraft" not in normalizar(wanda.texto)
    assert "canal oficial de Marvel en YouTube" in wanda.texto        # los enlaces del propio texto se mantienen
    wow = next(n for n in noticias if "World of Warcraft" in n.titulo)
    assert "warcraft" in normalizar(wow.texto)


def test_vidaextra_descarta_cine_y_series(cargar):
    noticias = fuente("VidaExtra").noticias(parse=lambda url: cargar("vidaextra.xml"))
    assert len(noticias) == 14
    assert not any("/cine/" in n.enlace or "/series/" in n.enlace for n in noticias)


def test_hobbyconsolas_usa_la_imagen_del_feed(cargar):
    noticias = fuente("Hobby Consolas").noticias(parse=lambda url: cargar("hobbyconsolas.xml"))
    assert noticias and all(n.url_imagen.startswith("https://imagenes.hobbyconsolas.com/") for n in noticias)


def test_eurogamer_pide_la_imagen_en_jpg_y_no_en_webp(cargar):
    noticias = fuente("Eurogamer.es").noticias(parse=lambda url: cargar("eurogamer.xml"))
    assert noticias[0].url_imagen == "https://assetsio.gnwcdn.com/20261010_193637.jpg?width=690&quality=85&format=jpg"
    assert all(n.url_imagen and "auto=webp" not in n.url_imagen and "format=jpg" in n.url_imagen for n in noticias)


def test_hobbyconsolas_descarta_hobbycine(cargar):
    noticias = fuente("Hobby Consolas").noticias(parse=lambda url: cargar("hobbyconsolas.xml"))
    assert len(noticias) == 37 and not any("/hobbycine/" in n.enlace for n in noticias)


def test_eurogamer_descarta_la_categoria_tecnologia(cargar):
    noticias = fuente("Eurogamer.es").noticias(parse=lambda url: cargar("eurogamer.xml"))
    assert len(noticias) == 86
    assert not any("auriculares" in n.titulo or "WiFi" in n.titulo for n in noticias)


def test_vidaextra_las_lineas_en_vidaextra_del_final_no_cuentan(cargar):
    sin_filtro = Fuente("VidaExtra", "https://www.vidaextra.com/feedburner.xml")
    noticias = sin_filtro.noticias(parse=lambda url: cargar("vidaextra.xml"))
    assert not any("En VidaExtra |" in n.texto for n in noticias)
    wanda = next(n for n in noticias if "WandaVision" in n.titulo)
    assert "Doctor Doom" not in wanda.texto     # estaba solo en un «En VidaExtra | ...» del final
