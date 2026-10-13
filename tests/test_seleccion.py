import random

from noticias.modelos import Noticia
from noticias.seleccion import (clasificar, coincidencias, compilar_niveles, compilar_patrones, elegir, es_analisis, puntos,
                                es_reciente, es_repetida, palabras_significativas)

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


def test_las_palabras_del_titulo_valen_el_doble():
    # Caso real: una noticia de GTA 5 que nombra Pokémon y Final Fantasy de pasada en el texto
    de_pasada = noticia("Modding GTA 5", fecha=100, coincide=["gta", "pokemon", "final fantasy"])   # 2+1+1 = 4
    en_titulo = noticia("Pokémon y Final Fantasy, juntos", fecha=50, coincide=["pokemon", "final fantasy"])  # 2+2 = 4
    titulo_y_texto = noticia("Nuevo Sonic", fecha=10, coincide=["sonic", "resident evil", "capcom"])  # 2+1+1 = 4
    assert [puntos(n) for n in (de_pasada, en_titulo, titulo_y_texto)] == [4, 4, 4]
    solo_texto = noticia("Un análisis", fecha=200, coincide=["sonic", "resident evil", "capcom"])   # 1+1+1 = 3
    assert puntos(solo_texto) == 3
    assert elegir([solo_texto, en_titulo], 1) == [en_titulo]   # menos palabras, pero en el título


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


# ---------------- Noticias repetidas ----------------
def test_palabras_significativas_sin_vacias_ni_tildes():
    assert palabras_significativas("Anunciado el nuevo Pokémon para Switch 2") == {"pokemon", "switch", "2"}


def test_la_misma_noticia_de_otra_web_es_repetida():
    # Títulos reales de Vandal y Eurogamer del 11 de octubre de 2026
    vandal = "Bad Bunny, Lana del Rey y otros famosos cantantes presentarán las emisoras de GTA 6: 'Es increíblemente especial'"
    eurogamer = "Bad Bunny, Lana del Rey y Robyn presentarán radios en Grand Theft Auto 6"
    assert es_repetida(vandal, [eurogamer]) and es_repetida(eurogamer, [vandal])


def test_noticias_distintas_del_mismo_juego_no_son_repetidas():
    publicadas = [
        "Final Fantasy VII Revelation tendrá una versión espectacular en Nintendo Switch 2, superior incluso al port de Rebirth",
        "Rockstar tranquiliza: GTA 6 no te obligará a usar sus mecánicas de rol de pareja entre Jason y Lucía",
        "Precio oficial del remake de Zelda Ocarina of Time en físico y digital en Nintendo Store",
    ]
    assert not es_repetida("Tropico 7 también tendrá una versión para Nintendo Switch 2", publicadas)
    assert not es_repetida("Habrá redes sociales en GTA 6, pero ni Jason ni Lucía publicarán en ellas por una lógica razón", publicadas)
    assert not es_repetida("Las reservas de Zelda Ocarina of Time Remake en GAME suben de nivel con un póster a doble cara", publicadas)


def test_sin_publicadas_no_hay_repetidas():
    assert not es_repetida("Cualquier cosa", [])


def test_los_analisis_se_reconocen_por_el_titulo_o_el_enlace():
    # Enlaces reales de 3DJuegos y Hobby Consolas
    assert es_analisis("Me esperaba un buen juego, pero no uno de los mejores de su género",
                       "https://www.3djuegos.com/juegos/castlevania-belmonts-curse/analisis/me-esperaba-buen-juego")
    assert es_analisis("Análisis de Valor Mortis, un napoleónico soulslike en primera persona")
    assert es_analisis("Un título cualquiera", "https://www.hobbyconsolas.com/videojuegos/analisis-valor-mortis-un-napoleonico_7045474_0.html")
    assert es_analisis("Pragmata review: Capcom's best new IP in years")
    assert not es_analisis("GAME publica los juegos más vendidos en septiembre",
                           "https://www.hobbyconsolas.com/videojuegos/game-publica-los-juegos-mas-vendidos_7048007_0.html")
    assert not es_analisis("Los análisisx no existen")  # la palabra tiene que ir sola
