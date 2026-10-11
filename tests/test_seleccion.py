import random

from noticias.modelos import Noticia
from noticias.seleccion import clasificar, coincidencias, compilar_niveles, compilar_patrones, elegir, es_reciente

PATRONES = compilar_patrones(["sonic", "resident evil", "final fantasy"])


NIVELES = compilar_niveles([["sonic", "final fantasy"], ["capcom"], ["indie"]])


def noticia(titulo, fecha=0, coincide=(), nivel=None):
    nivel = nivel or (1 if coincide else None)
    return Noticia(fuente="F", titulo=titulo, enlace=f"https://x/{titulo}", texto="", fecha=fecha, coincide=list(coincide), nivel=nivel)


def test_coincidencias_sin_distinguir_mayusculas_ni_tildes():
    assert coincidencias("Nuevo RESIDENT EVIL anunciado", PATRONES) == ["resident evil"]
    assert coincidencias("Sónic y Final Fantasy", PATRONES) == ["sonic", "final fantasy"]


def test_la_palabra_clave_debe_ir_entera():
    assert coincidencias("Un avión supersonic", PATRONES) == []
    assert coincidencias("Sonic's new game", PATRONES) == ["sonic"]


def test_clasificar_devuelve_el_primer_nivel_con_coincidencias():
    assert clasificar("Capcom anuncia un nuevo Sonic", NIVELES) == (1, ["sonic"])
    assert clasificar("Capcom prepara un indie", NIVELES) == (2, ["capcom"])
    assert clasificar("Un indie precioso", NIVELES) == (3, ["indie"])
    assert clasificar("Nada que ver", NIVELES) == (None, [])


def test_un_nivel_vacio_no_rompe_nada():
    assert clasificar("Un indie", compilar_niveles([["sonic"], [], ["indie"]])) == (3, ["indie"])


def test_el_nivel_1_gana_aunque_otras_acierten_mas_palabras_o_sean_mas_recientes():
    n1 = noticia("n1", fecha=10, coincide=["sonic"], nivel=1)
    n2 = noticia("n2", fecha=99, coincide=["capcom", "konami"], nivel=2)
    assert elegir([n2, n1, noticia("x")], 1) == [n1]


def test_sin_nivel_1_gana_el_2_y_sin_2_el_3():
    n2 = noticia("n2", coincide=["capcom"], nivel=2)
    n3 = noticia("n3", fecha=99, coincide=["indie"], nivel=3)
    assert elegir([n3, n2, noticia("x")], 1) == [n2]
    assert elegir([n3, noticia("x")], 1) == [n3]


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
