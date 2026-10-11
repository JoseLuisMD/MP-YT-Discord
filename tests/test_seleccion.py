import random

from noticias.modelos import Noticia
from noticias.seleccion import coincidencias, compilar_patrones, elegir, es_reciente

PATRONES = compilar_patrones(["sonic", "resident evil", "final fantasy"])


def noticia(titulo, fecha=0, coincide=()):
    return Noticia(fuente="F", titulo=titulo, enlace=f"https://x/{titulo}", texto="", fecha=fecha, coincide=list(coincide))


def test_coincidencias_sin_distinguir_mayusculas_ni_tildes():
    assert coincidencias("Nuevo RESIDENT EVIL anunciado", PATRONES) == ["resident evil"]
    assert coincidencias("Sónic y Final Fantasy", PATRONES) == ["sonic", "final fantasy"]


def test_la_palabra_clave_debe_ir_entera():
    assert coincidencias("Un avión supersonic", PATRONES) == []
    assert coincidencias("Sonic's new game", PATRONES) == ["sonic"]


def test_gana_la_que_mas_palabras_clave_acierta():
    a = noticia("a", fecha=100, coincide=["sonic"])
    b = noticia("b", fecha=50, coincide=["sonic", "resident evil"])
    assert elegir([a, b, noticia("c")], 1) == [b]


def test_con_las_mismas_palabras_gana_la_mas_reciente():
    vieja = noticia("vieja", fecha=10, coincide=["sonic"])
    nueva = noticia("nueva", fecha=20, coincide=["sonic"])
    assert elegir([vieja, nueva], 1) == [nueva]


def test_sin_coincidencias_se_elige_al_azar_de_forma_reproducible():
    candidatas = [noticia(str(i)) for i in range(10)]
    uno = elegir(candidatas, 1, random.Random(5))
    otro = elegir(candidatas, 1, random.Random(5))
    assert uno == otro and uno[0] in candidatas


def test_no_se_piden_mas_de_las_que_hay():
    assert len(elegir([noticia("a"), noticia("b")], 5, random.Random(1))) == 2


def test_es_reciente():
    ahora = 1_000_000
    assert es_reciente(ahora - 3600, ahora)
    assert not es_reciente(ahora - 25 * 3600, ahora)
    assert es_reciente(None, ahora)   # sin fecha, se acepta
