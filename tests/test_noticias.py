import json
import random
from datetime import datetime, timezone

import pytest

from noticias import proceso
from noticias.config import EMOJIS_FUENTE
from noticias.fuentes import FUENTES

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

    estado = {"resumir": lambda titulo, texto, otro_idioma=False: (f"Resumen de {titulo[:20]}", ["#uno", "#dos"])}
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
    estado["resumir"] = lambda titulo, texto, otro_idioma=False: None if otro_idioma else ("Resumen", [])
    red, historial = correr()
    assert red.publicaciones == [] and historial == []


def test_se_pasa_a_resumir_si_la_fuente_esta_en_otro_idioma(entorno):
    correr, estado = entorno
    escribir_palabras(estado["palabras"], [["amiga"], [], []])
    recibido = {}

    def resumir(titulo, texto, otro_idioma=False):
        recibido["otro_idioma"] = otro_idioma
        return "Resumen", []
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
    red, _ = correr(historial=[])   # sin el enlace en el historial: solo la frena el título
    assert not red.publicaciones[0].enlace.startswith(NINTENDO_3DJ)


def test_las_publicadas_se_apuntan_en_recientes(entorno):
    correr, estado = entorno
    red, _ = correr()
    recientes = json.loads(estado["recientes"].read_text(encoding="utf-8"))
    assert recientes == [{"titulo": red.publicaciones[0].titulo_tarjeta, "fecha": "2026-10-11T20:00:00+00:00"}]


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
