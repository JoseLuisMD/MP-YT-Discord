"""Publica cada hora una noticia de videojuegos en Discord, Bluesky y Threads."""
import random

import feedparser

from common.estado import cargar_json, guardar_json
from common.publicadores import Bluesky, Discord, Publicacion, Threads

from .config import (ARCHIVO, MAX_HISTORIAL, MAX_POR_EJECUCION, PALABRAS_CLAVE,
                     TEMA_THREADS, USER_AGENT, WEBHOOK_NOTICIAS)
from .fuentes import FUENTES
from .imagenes import imagen_og
from .resumen import resumir
from .seleccion import coincidencias, compilar_patrones, elegir, es_reciente


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


def publicar_noticia(n, resumen, hashtags, publicadores):
    """Publica en todos los destinos. True si al menos uno ha funcionado."""
    texto = f"{resumen}\n\n📰 {n.fuente}"
    publicacion = Publicacion(
        texto=texto,
        enlace=n.enlace,
        titulo_tarjeta=n.titulo,
        url_imagen=n.url_imagen or imagen_og(n.enlace),
        hashtags=hashtags,
    )
    resultados = [p.publicar(publicacion) for p in publicadores]
    return any(resultados)


def ejecutar(fuentes=None, ruta=ARCHIVO, parse=None, publicadores=None, ahora=None, rng=random):
    feedparser.USER_AGENT = USER_AGENT
    fuentes = FUENTES if fuentes is None else fuentes
    if publicadores is None:
        publicadores = [Discord(WEBHOOK_NOTICIAS), Bluesky(), Threads(tema=TEMA_THREADS)]
    patrones = compilar_patrones(PALABRAS_CLAVE)

    publicadas = cargar_json(ruta, [])
    candidatas = recoger_candidatas(fuentes, set(publicadas), parse=parse, ahora=ahora)
    print(f"Noticias candidatas: {len(candidatas)}")

    if candidatas:
        for c in candidatas:
            c.coincide = coincidencias(c.titulo + " " + c.texto, patrones)
        for c in elegir(candidatas, MAX_POR_EJECUCION, rng):
            motivo = f"coincide con {c.coincide}" if c.coincide else "aleatoria (sin coincidencias)"
            print(f"Elegida [{c.fuente}] {c.titulo} -> {motivo}")
            resultado = resumir(c.titulo, c.texto, otro_idioma=c.idioma != "es")
            if resultado is None:
                continue
            resumen, hashtags = resultado
            if publicar_noticia(c, resumen, hashtags, publicadores):
                publicadas.append(c.enlace)

    guardar_json(ruta, publicadas[-MAX_HISTORIAL:])
