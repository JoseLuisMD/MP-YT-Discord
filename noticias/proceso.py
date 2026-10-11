"""Publica cada hora una noticia de videojuegos en Discord, Bluesky y Threads."""
import random

import feedparser

from common.estado import cargar_json, guardar_json
from common.publicadores import Bluesky, Discord, Publicacion, Threads

from .config import (ARCHIVO, ARCHIVO_PALABRAS, EMOJIS_FUENTE, MAX_HISTORIAL, MAX_POR_EJECUCION,
                     TEMA_THREADS, USER_AGENT, WEBHOOK_NOTICIAS)
from .fuentes import FUENTES
from .imagenes import imagen_og
from .palabras import cargar_palabras, contar, guardar_palabras
from .resumen import resumir
from .seleccion import clasificar, compilar_niveles, elegir, es_reciente


def recoger_candidatas(fuentes, ya_publicadas, parse=None, ahora=None):
    """Noticias recientes y no publicadas de todas las fuentes (sin repetir enlaces)."""
    marca = ahora.timestamp() if ahora else None
    candidatas, enlaces_vistos = [], set()
    for fuente in fuentes:
        for n in fuente.noticias(parse=parse, ahora=ahora):
            if n.enlace in ya_publicadas or n.enlace in enlaces_vistos or not es_reciente(n.fecha, marca):
                continue
            enlaces_vistos.add(n.enlace)
            candidatas.append(n)
    return candidatas


def publicar_noticia(n, resumen, hashtags, publicadores, rng=random):
    """Publica en todos los destinos. True si al menos uno ha funcionado."""
    texto = f"{resumen}\n\n{rng.choice(EMOJIS_FUENTE)} {n.fuente}"
    publicacion = Publicacion(
        texto=texto,
        enlace=n.enlace,
        titulo_tarjeta=n.titulo,
        url_imagen=n.url_imagen or imagen_og(n.enlace),
        hashtags=hashtags,
        imagen_en_threads=n.imagen_en_threads,
    )
    resultados = [p.publicar(publicacion) for p in publicadores]
    return any(resultados)


def ejecutar(fuentes=None, ruta=ARCHIVO, ruta_palabras=ARCHIVO_PALABRAS, parse=None, publicadores=None, ahora=None, rng=random):
    feedparser.USER_AGENT = USER_AGENT
    fuentes = FUENTES if fuentes is None else fuentes
    if publicadores is None:
        publicadores = [Discord(WEBHOOK_NOTICIAS), Bluesky(), Threads(tema=TEMA_THREADS)]
    palabras = cargar_palabras(ruta_palabras)
    niveles = compilar_niveles(palabras)

    publicadas = cargar_json(ruta, [])
    candidatas = recoger_candidatas(fuentes, set(publicadas), parse=parse, ahora=ahora)
    print(f"Noticias candidatas: {len(candidatas)}")

    if candidatas:
        for c in candidatas:
            c.nivel, c.coincide = clasificar(c.titulo + " " + c.texto, niveles)
        for c in elegir(candidatas, MAX_POR_EJECUCION, rng):
            motivo = f"nivel {c.nivel}, coincide con {c.coincide}" if c.nivel else "aleatoria (sin coincidencias)"
            print(f"Elegida [{c.fuente}] {c.titulo} -> {motivo}")
            resultado = resumir(c.titulo, c.texto, otro_idioma=c.idioma != "es")
            if resultado is None:
                continue
            resumen, hashtags = resultado
            if publicar_noticia(c, resumen, hashtags, publicadores, rng):
                publicadas.append(c.enlace)
                if c.nivel:
                    contar(palabras, c.nivel, c.coincide)

    guardar_json(ruta, publicadas[-MAX_HISTORIAL:])
    guardar_palabras(ruta_palabras, palabras)
