import json
import random
from datetime import datetime, timezone

import pytest

from noticias import proceso
from noticias.config import EMOJIS_FUENTE
from noticias.fuentes import FUENTES
from noticias.modelos import Noticia
from noticias.resumen import Resumen

AHORA = datetime(2026, 10, 11, 20, 0, tzinfo=timezone.utc)   # los feeds reales se guardaron la tarde de ese día

# Noticias de los feeds reales que usan las pruebas
NINTENDO_3DJ = "https://www.3djuegos.com/juegos/the-legend-of-zelda-ocarina-of-time/noticias/"   # «mario» y «zelda», 19:15
MARIO_GA = "https://www.generationamiga.com/2026/10/11/super-mario-odyssey-pc-port-could-arrive-in-november-2026/"
STARFIELD_3DJ = "https://www.3djuegos.com/juegos/starfield/noticias/"
AMIGA_GA = "https://www.generationamiga.com/2026/10/11/hyper-runner"


class Red:
    def __init__(self, resultado=True):
        self.publicaciones, self.resultado = [], resultado

    def publicar(self, p):
        self.publicaciones.append(p)
        return self.resultado


def escribir_palabras(ruta, niveles):
    datos = {f"nivel_{i}": {p: 0 for p in n} for i, n in enumerate(niveles, start=1)}
    ruta.write_text(json.dumps(datos), encoding="utf-8")


def leer_palabras(ruta):
    return json.loads(ruta.read_text(encoding="utf-8"))


@pytest.fixture
def entorno(monkeypatch, cargar, tmp_path):
    fixtures = {"vandal": "vandal.xml", "3djuegos": "3djuegos.xml", "generationamiga": "generationamiga.xml"}
    fuentes = [f for f in FUENTES if f.nombre in ("Vandal", "3DJuegos", "GenerationAmiga")]

    cache = {}

    def parse(url):   # los feeds reales son grandes: se leen una sola vez
        nombre = next(v for k, v in fixtures.items() if k in url)
        if nombre not in cache:
            cache[nombre] = cargar(nombre)
        return cache[nombre]

    estado = {"resumir": lambda titulo, texto, otro_idioma=False: Resumen(f"Resumen de {titulo[:20]}", ["#uno", "#dos"])}
    monkeypatch.setattr(proceso, "resumir", lambda *a, **k: estado["resumir"](*a, **k))
    monkeypatch.setattr(proceso, "imagen_og", lambda enlace: "https://og/imagen.jpg")
    ruta = tmp_path / "noticias_publicadas.json"
    estado["palabras"] = tmp_path / "palabras_clave.json"
    estado["web"] = tmp_path / "noticias_web.json"
    estado["recientes"] = tmp_path / "noticias_recientes.json"
    escribir_palabras(estado["palabras"], [["mario", "sonic", "zelda"], ["capcom"], ["indie"]])

    def correr(red=None, rng=None, historial=None, ahora=AHORA, cola_x=None):
        if historial is not None:
            ruta.write_text(json.dumps(historial), encoding="utf-8")
        red = red or Red()
        proceso.ejecutar(fuentes=fuentes, ruta=str(ruta), ruta_palabras=str(estado["palabras"]),
                         ruta_web=str(estado["web"]), ruta_recientes=str(estado["recientes"]), parse=parse,
                         publicadores=[red], ahora=ahora, rng=rng or random.Random(1), cola_x=cola_x)
        return red, json.loads(ruta.read_text(encoding="utf-8"))

    return correr, estado


def test_publica_la_noticia_que_coincide_con_una_palabra_clave(entorno):
    correr, _ = entorno
    red, historial = correr()
    assert len(red.publicaciones) == 1
    p = red.publicaciones[0]
    # La de Nintendo de 3DJuegos acierta «mario» y «zelda»: gana a las que solo aciertan una
    assert p.enlace.startswith(NINTENDO_3DJ)
    resumen, firma = p.texto.split("\n\n")
    emoji, fuente = firma.split(" ")
    assert emoji in EMOJIS_FUENTE and fuente == "3DJuegos"
    assert p.hashtags == ["#uno", "#dos"]
    assert historial == [p.enlace]


def test_las_palabras_del_nivel_1_mandan_sobre_las_del_2(entorno):
    correr, estado = entorno
    # La de Starfield es más antigua y acierta menos palabras, pero es la única del nivel 1
    escribir_palabras(estado["palabras"], [["starfield"], ["mario", "zelda"], []])
    red, _ = correr()
    assert red.publicaciones[0].enlace.startswith(STARFIELD_3DJ)


def test_si_no_hay_coincidencias_en_1_ni_2_se_usa_el_3(entorno):
    correr, estado = entorno
    escribir_palabras(estado["palabras"], [["palabra que no sale"], [], ["amiga"]])
    red, _ = correr()
    assert red.publicaciones[0].enlace.startswith(AMIGA_GA)


def test_se_cuentan_las_palabras_que_hacen_publicar_una_noticia(entorno):
    correr, estado = entorno
    correr()   # 3DJuegos, por «mario» y «zelda»
    correr()   # GenerationAmiga, por «mario» (más reciente que la de Zelda de Vandal)
    palabras = leer_palabras(estado["palabras"])
    assert palabras["nivel_1"] == {"mario": 2, "sonic": 0, "zelda": 1}
    assert palabras["nivel_2"] == {"capcom": 0} and palabras["nivel_3"] == {"indie": 0}


def test_si_no_se_publica_no_se_cuenta(entorno):
    correr, estado = entorno
    correr(Red(resultado=False))
    assert leer_palabras(estado["palabras"])["nivel_1"]["mario"] == 0


def test_una_noticia_aleatoria_no_suma_a_ninguna_palabra(entorno):
    correr, estado = entorno
    escribir_palabras(estado["palabras"], [["xyzzy"], ["plugh"], ["qwerty"]])
    correr()
    assert leer_palabras(estado["palabras"]) == {"nivel_1": {"xyzzy": 0}, "nivel_2": {"plugh": 0}, "nivel_3": {"qwerty": 0}}


def test_el_emoji_de_la_web_cambia_entre_publicaciones(entorno):
    correr, _ = entorno
    emojis = set()
    for semilla in range(20):
        red, _ = correr(rng=random.Random(semilla), historial=[])
        emojis.add(red.publicaciones[0].texto.split("\n\n")[1].split(" ")[0])
    assert len(emojis) > 1 and emojis <= set(EMOJIS_FUENTE)


def test_la_segunda_ejecucion_publica_la_siguiente_y_no_repite(entorno):
    correr, _ = entorno
    _, h1 = correr()
    red, h2 = correr()
    assert red.publicaciones[0].enlace == MARIO_GA
    assert h2 == h1 + [red.publicaciones[0].enlace]


def test_sin_coincidencias_publica_una_al_azar_de_las_que_quedan(entorno):
    correr, estado = entorno
    escribir_palabras(estado["palabras"], [["xyzzy"], [], []])
    ya = [MARIO_GA]
    red, historial = correr(historial=ya)
    assert len(red.publicaciones) == 1 and len(historial) == 2
    assert red.publicaciones[0].enlace not in ya


def test_las_secciones_excluidas_de_3djuegos_nunca_se_publican(entorno):
    correr, estado = entorno
    escribir_palabras(estado["palabras"], [["xyzzy"], [], []])   # al azar, para recorrer todas
    publicadas = []
    for _ in range(31):
        red, _historial = correr()
        publicadas += [p.enlace for p in red.publicaciones]
    assert not any(x for x in publicadas if "/tv-series/" in x or "/manga-anime/" in x or "trivia" in x)
    assert len(publicadas) == 31 and len(set(publicadas)) == 31   # 15 Vandal + 6 3DJuegos + 10 GenerationAmiga
    red, _ = correr()
    assert red.publicaciones == []   # ya no queda ninguna


def test_noticia_en_otro_idioma_sin_resumen_no_se_publica_ni_se_guarda(entorno):
    correr, estado = entorno
    escribir_palabras(estado["palabras"], [["amiga"], [], []])   # elige una de GenerationAmiga (inglés)
    estado["resumir"] = lambda titulo, texto, otro_idioma=False: None if otro_idioma else Resumen("Resumen", [])
    red, historial = correr()
    assert red.publicaciones == [] and historial == []


def test_se_pasa_a_resumir_si_la_fuente_esta_en_otro_idioma(entorno):
    correr, estado = entorno
    escribir_palabras(estado["palabras"], [["amiga"], [], []])
    recibido = {}

    def resumir(titulo, texto, otro_idioma=False):
        recibido["otro_idioma"] = otro_idioma
        return Resumen("Resumen", [])
    estado["resumir"] = resumir
    correr()
    assert recibido["otro_idioma"] is True


def test_usa_la_imagen_del_feed_y_si_no_hay_la_de_la_pagina(entorno):
    correr, estado = entorno
    mk, _ = correr()                                    # 3DJuegos: imagen en el feed
    assert mk.publicaciones[0].url_imagen == "https://i.blogs.es/a2a426/qwrtr/1024_2000.jpeg"
    ga, _ = correr()                                    # GenerationAmiga: sin imagen en el feed
    assert ga.publicaciones[0].url_imagen == "https://og/imagen.jpg"


def test_solo_las_fuentes_marcadas_adjuntan_la_imagen_en_threads(entorno):
    correr, _ = entorno
    mk, _ = correr()                                    # 3DJuegos: adjuntamos la imagen nosotros
    assert mk.publicaciones[0].imagen_en_threads is True
    ga, _ = correr()                                    # GenerationAmiga: Threads ya muestra su tarjeta
    assert ga.publicaciones[0].imagen_en_threads is False


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
    red, historial = correr(ahora=datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc))
    assert red.publicaciones == [] and historial == []


def test_la_noticia_publicada_se_guarda_para_la_web(entorno):
    correr, estado = entorno
    correr()
    web = json.loads(estado["web"].read_text(encoding="utf-8"))
    assert web == [{
        "titulo": web[0]["titulo"],
        "resumen": f"Resumen de {web[0]['titulo'][:20]}",
        "enlace": web[0]["enlace"],
        "imagen": "https://i.blogs.es/a2a426/qwrtr/1024_2000.jpeg",
        "fuente": "3DJuegos",
        "idioma": "es",
        "fecha": "2026-10-11T20:00:00+00:00",
    }]


def test_en_la_web_la_mas_nueva_va_primero_y_se_recorta(entorno, monkeypatch):
    correr, estado = entorno
    monkeypatch.setattr(proceso, "MAX_WEB", 2)
    for _ in range(3):
        correr()
    _, historial = correr()
    web = json.loads(estado["web"].read_text(encoding="utf-8"))
    assert [n["enlace"] for n in web] == historial[-1:-3:-1]


def test_si_ninguna_red_publica_no_se_guarda_para_la_web(entorno):
    correr, estado = entorno
    correr(Red(resultado=False))
    assert json.loads(estado["web"].read_text(encoding="utf-8")) == []


# ---------------- Cola de X ----------------
def test_la_noticia_publicada_se_apunta_en_la_cola_de_x(entorno):
    correr, _ = entorno
    cola = Red()
    red, _ = correr(cola_x=cola)
    assert cola.publicaciones == red.publicaciones


def test_si_ninguna_red_publica_no_se_apunta_para_x_aunque_la_cola_funcione(entorno):
    correr, estado = entorno
    cola = Red()
    _, historial = correr(Red(resultado=False), cola_x=cola)
    assert cola.publicaciones == [] and historial == []


def test_la_cola_de_x_no_cuenta_como_publicacion(entorno):
    correr, _ = entorno
    _, historial = correr(Red(resultado=False), cola_x=Red(resultado=True))
    assert historial == []


# ---------------- Noticias repetidas ----------------
def escribir_recientes(ruta, recientes):
    ruta.write_text(json.dumps(recientes), encoding="utf-8")


def test_no_se_publica_la_misma_noticia_desde_otra_web(entorno):
    correr, estado = entorno
    # Ya se publicó desde otra web la de Nintendo que elegiría (la de 3DJuegos)
    correr()
    titulo = json.loads(estado["web"].read_text(encoding="utf-8"))[0]["titulo"]
    escribir_recientes(estado["recientes"], [{"titulo": titulo, "fecha": "2026-10-11T19:00:00+00:00"}])
    red, historial = correr(historial=[])   # sin el enlace en el historial: solo la frena el título
    assert not red.publicaciones[0].enlace.startswith(NINTENDO_3DJ)
    # La descartada queda como vista: en las próximas ejecuciones ni se compara ni se anota en el registro
    assert any(e.startswith(NINTENDO_3DJ) for e in historial)


def test_la_descartada_por_titulo_no_se_vuelve_a_anotar(entorno, capsys):
    correr, estado = entorno
    correr()
    titulo = json.loads(estado["web"].read_text(encoding="utf-8"))[0]["titulo"]
    escribir_recientes(estado["recientes"], [{"titulo": titulo, "fecha": "2026-10-11T19:00:00+00:00"}])
    correr(historial=[])
    assert "Descartada por repetida (título)" in capsys.readouterr().out
    correr()   # mismo historial que dejó la ejecución anterior
    assert "Descartada por repetida (título)" not in capsys.readouterr().out


def test_las_publicadas_se_apuntan_en_recientes(entorno):
    correr, estado = entorno
    red, _ = correr()
    recientes = json.loads(estado["recientes"].read_text(encoding="utf-8"))
    p = red.publicaciones[0]
    assert recientes == [{"titulo": p.titulo_tarjeta, "resumen": p.texto.split("\n\n")[0], "enlace": p.enlace,
                          "fecha": "2026-10-11T20:00:00+00:00"}]


def test_las_recientes_antiguas_se_olvidan(entorno):
    correr, estado = entorno
    escribir_recientes(estado["recientes"], [
        {"titulo": "Vieja", "fecha": "2026-10-09T19:00:00+00:00"},    # hace más de 48 h
        {"titulo": "Reciente", "fecha": "2026-10-10T21:00:00+00:00"},
    ])
    correr()
    titulos = [r["titulo"] for r in json.loads(estado["recientes"].read_text(encoding="utf-8"))]
    assert titulos[0] == "Reciente" and "Vieja" not in titulos and len(titulos) == 2


def test_si_ninguna_red_publica_no_se_apunta_en_recientes(entorno):
    correr, estado = entorno
    correr(Red(resultado=False))
    assert json.loads(estado["recientes"].read_text(encoding="utf-8")) == []


# ---------------- Noticias repetidas por el resumen de Gemini ----------------
# Noticias reales de octubre de 2026 (título, resumen de Gemini y enlace)
GAME_VANDAL = Noticia(
    "Vandal", "Los más vendidos en GAME España: se confirma que EA Sports FC 27 fue el título más vendido en septiembre",
    "https://vandal.elespanol.com/noticia/2026286013/los-mas-vendidos-en-espana-game-confirma-que-ea-sports-fc-27-fue-el-titulo-mas-vendido-en-septiembre/", "")
GAME_VANDAL_RESUMEN = ("GAME España ha anunciado que EA SPORTS FC 27 fue el juego más vendido en septiembre. "
                       "Marvel: Lobezno y Silent Hill: Townfall completan el podio.")
GAME_HOBBY = {
    "titulo": "GAME publica los juegos más vendidos en sus tiendas durante septiembre de 2026: fútbol, Lobezno y Konami dominan la lista",
    "resumen": "GAME publica los juegos más vendidos en septiembre de 2026. EA Sports FC 27, Marvel: Lobezno y Silent Hill "
               "Townfall lideran el top de ventas.",
    "enlace": "https://www.hobbyconsolas.com/videojuegos/game-publica-los-juegos-mas-vendidos-sus-tiendas-durante-septiembre-2026-futbol-lobezno-konami-dominan-lista_7048007_0.html",
    "fecha": "2026-10-11T19:00:00+00:00",
}
HORII_3DJ = Noticia(
    "3DJuegos", "El creador de Dragon Quest ha hecho un juego en lo que tardas en ver un capítulo de Los Simpson, y ya sabes qué significa",
    "https://www.3djuegos.com/juegos/dragon-quest-xii/noticias/creador-dragon-quest-ha-hecho-juego-que-tardas-ver-capitulo-simpson-sabes-que-significa", "")
HORII_3DJ_RESUMEN = ("Yuji Horii, creador de Dragon Quest, ha desarrollado en solo treinta minutos el juego Interrogation Room Komiya "
                     "utilizando inteligencia artificial.")
HORII_HOBBY = {
    "titulo": "Yuji Horii, el creador de Dragon Quest, lanza un juego gratis hecho con IA centrado en un interrogatorio, y la lluvia de críticas no se ha hecho esperar",
    "resumen": "Yuji Horii, creador de Dragon Quest, ha lanzado gratis en navegador un juego de interrogatorios creado con "
               "inteligencia artificial que ha recibido duras críticas.",
    "enlace": "https://www.hobbyconsolas.com/videojuegos/yuji-horii-creador-dragon-quest-lanza-un-juego-gratis-hecho-con-ia-centrado-un-interrogatorio-lluvia-criticas-no-se-ha-hecho-esperar_7047756_0.html",
    "fecha": "2026-10-11T19:00:00+00:00",
}
CASTLEVANIA_3DJ = Noticia(
    "3DJuegos", "Me esperaba un buen juego, pero no uno de los mejores de su género. Análisis de Castlevania: Belmont's Curse",
    "https://www.3djuegos.com/juegos/castlevania-belmonts-curse/analisis/me-esperaba-buen-juego-no-uno-mejores-su-genero-analisis-castlevania-belmont-s-curse", "")
CASTLEVANIA_3DJ_RESUMEN = ("El análisis de Castlevania: Belmont's Curse destaca el excelente trabajo de Evil Empire, calificándolo "
                           "como uno de los mejores y más logrados juegos de la saga y del género.")
CASTLEVANIA_HOBBY = {
    "titulo": "Análisis de Castlevania: Belmont's Curse, un regreso al castillo de Dracula por la puerta grande que unifica la saga en todas sus vertientes y formatos",
    "resumen": "Castlevania: Belmont's Curse marca el triunfal regreso de la saga de Konami, desarrollado por Evil Empire para "
               "unificar la franquicia y competir en la era moderna de los metroidvania.",
    "enlace": "https://www.hobbyconsolas.com/videojuegos/analisis-castlevania-belmont-s-curse-un-regreso-castillo-dracula-por-puerta-grande-que-unifica-saga-todas-sus-vertientes-formatos_7045323_0.html",
    "fecha": "2026-10-11T19:00:00+00:00",
}
NARUTO_RASENGAN = {
    "titulo": "Naruto prepara grandes novedades hasta 2029 y deja pistas de un nuevo videojuego con Project Rasengan",
    "resumen": "Bandai Namco presenta Project Rasengan, una iniciativa que ampliará el universo de Naruto y Boruto hasta 2029 "
               "con nuevos contenidos y pistas sobre posibles videojuegos.",
    "enlace": "https://vandal.elespanol.com/noticia/2026285005/naruto-prepara-grandes-novedades-hasta-2029-y-deja-pistas-de-un-nuevo-videojuego-con-project-rasengan/",
    "fecha": "2026-10-11T19:00:00+00:00",
}


def test_la_misma_noticia_de_otra_web_es_repetida_por_el_resumen_aunque_no_por_el_titulo():
    assert proceso.descartar_repetidas([GAME_VANDAL], [GAME_HOBBY]) == [GAME_VANDAL]   # el título no basta
    assert proceso.repetida_por_resumen(GAME_VANDAL, GAME_VANDAL_RESUMEN, [GAME_HOBBY])
    assert proceso.repetida_por_resumen(HORII_3DJ, HORII_3DJ_RESUMEN, [HORII_HOBBY])


def test_dos_analisis_del_mismo_juego_no_son_repetidos():
    assert not proceso.repetida_por_resumen(CASTLEVANIA_3DJ, CASTLEVANIA_3DJ_RESUMEN, [CASTLEVANIA_HOBBY])


def test_noticias_distintas_de_la_misma_saga_no_son_repetidas_por_el_resumen():
    naruto_mobile = Noticia("Vandal", "Naruto Mobile confirma su lanzamiento mundial diez años después de debutar en China",
                            "https://vandal.elespanol.com/noticia/2026285020/naruto-mobile/", "")
    resumen = "Bandai Namco ha anunciado el lanzamiento mundial para iOS y Android de Naruto Mobile, un juego de lucha que debutó en China en 2016."
    assert not proceso.repetida_por_resumen(naruto_mobile, resumen, [NARUTO_RASENGAN])


def test_las_recientes_sin_resumen_no_rompen_la_comparacion():
    antigua = {"titulo": "Una noticia apuntada antes de guardar resúmenes", "fecha": "2026-10-11T19:00:00+00:00"}
    assert not proceso.repetida_por_resumen(GAME_VANDAL, GAME_VANDAL_RESUMEN, [antigua])


REPETIDO = GAME_HOBBY["resumen"]


def test_si_el_resumen_sale_repetido_se_prueba_con_la_siguiente(entorno):
    correr, estado = entorno
    escribir_recientes(estado["recientes"], [GAME_HOBBY])
    resumidas = []

    def resumir(titulo, texto, otro_idioma=False):   # la primera elegida resulta ser la misma noticia que GAME_HOBBY
        resumidas.append(titulo)
        return Resumen(REPETIDO if len(resumidas) == 1 else f"Resumen de {titulo[:20]}", [])

    estado["resumir"] = resumir
    red, historial = correr()
    assert len(resumidas) == 2 and len(red.publicaciones) == 1
    assert red.publicaciones[0].titulo_tarjeta == resumidas[1]
    assert len(historial) == 2   # la repetida queda como vista, para no volver a resumirla


def test_como_mucho_se_resumen_3_noticias_por_ejecucion(entorno):
    correr, estado = entorno
    escribir_recientes(estado["recientes"], [GAME_HOBBY])
    resumidas = []
    estado["resumir"] = lambda titulo, texto, otro_idioma=False: (resumidas.append(titulo), Resumen(REPETIDO, []))[1]
    red, historial = correr()
    assert len(resumidas) == 3 and red.publicaciones == [] and len(historial) == 3


def test_si_gemini_no_resume_no_se_prueba_con_otra(entorno):
    correr, estado = entorno
    llamadas = []
    estado["resumir"] = lambda titulo, texto, otro_idioma=False: llamadas.append(titulo)
    red, historial = correr()
    assert len(llamadas) == 1 and red.publicaciones == [] and historial == []


# ---------------- Noticias de webs en otro idioma ----------------
def test_en_otro_idioma_se_usa_el_titulo_traducido(entorno):
    correr, estado = entorno
    escribir_palabras(estado["palabras"], [["amiga"], [], []])   # elige una de GenerationAmiga (inglés)
    estado["resumir"] = lambda titulo, texto, otro_idioma=False: Resumen("Resumen.", [], "Título en español")
    red, _ = correr()
    assert red.publicaciones[0].titulo_tarjeta == "Título en español"
    entrada = json.loads(estado["web"].read_text(encoding="utf-8"))[0]
    assert entrada["titulo"] == "Título en español" and entrada["idioma"] == "en"
    assert json.loads(estado["recientes"].read_text(encoding="utf-8"))[0]["titulo"] == "Título en español"


def test_en_otro_idioma_sin_titulo_traducido_se_queda_el_original(entorno):
    correr, estado = entorno
    escribir_palabras(estado["palabras"], [["amiga"], [], []])
    estado["resumir"] = lambda titulo, texto, otro_idioma=False: Resumen("Resumen.", [])
    red, _ = correr()
    assert "generationamiga.com" in red.publicaciones[0].enlace
    assert red.publicaciones[0].titulo_tarjeta and red.publicaciones[0].titulo_tarjeta != "Resumen."


def test_en_espanol_se_mantiene_el_titulo_original_aunque_gemini_lo_cambie(entorno):
    correr, estado = entorno
    estado["resumir"] = lambda titulo, texto, otro_idioma=False: Resumen("Resumen.", [], "Otro título")
    red, _ = correr()
    assert red.publicaciones[0].titulo_tarjeta != "Otro título"
