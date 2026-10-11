"""Avisa de los vídeos nuevos de los canales de YouTube en Discord, Bluesky y Threads."""
import random

import feedparser

from common.publicadores import Bluesky, Discord, Publicacion, Threads
from common.texto import extraer_hashtags

from .canales import ARCHIVO, CANALES, EMOJIS_AVISO, MAX_VISTOS
from .estado import cargar_estado, estado_vacio, guardar_estado, marcar_visto

FEED_CANAL = "https://www.youtube.com/feeds/videos.xml?channel_id={canal}"
FEED_MIEMBROS = "https://www.youtube.com/feeds/videos.xml?playlist_id=UUMF{sufijo}"


def _miniatura(v):
    return v.get("media_thumbnail", [{}])[0].get("url")


def _avisar(v, mensaje, cfg, miembros, bluesky, threads, rng=random):
    # Discord (los canales con incluirShorts=False no avisan de Shorts)
    es_short = "shorts" in v.link.lower()
    if cfg["incluirShorts"] or not es_short:
        for webhook in cfg["webhooks"]:
            Discord(webhook).publicar(Publicacion(texto=mensaje, enlace=v.link))
    # Los vídeos exclusivos para miembros se avisan únicamente por Discord
    if miembros:
        return
    # Bluesky y Threads: emoji de aviso + mensaje del canal, y debajo el título
    texto = f"{rng.choice(EMOJIS_AVISO)} {mensaje}\n\n{v.title}"
    if cfg["bluesky"]:
        bluesky.publicar(Publicacion(
            texto=texto,
            enlace=v.link,
            url_imagen=_miniatura(v),
            hashtags=extraer_hashtags(v.get("summary", "")),
        ))
    if cfg.get("threads"):
        threads.publicar(Publicacion(texto=texto, enlace=v.link))


def procesar_feed(canal, cfg, estado, bluesky, threads, miembros=False, parse=None, rng=random):
    parse = parse or feedparser.parse
    if miembros:
        url_feed = FEED_MIEMBROS.format(sufijo=canal[2:])
        clave = "miembros"
        mensaje = cfg["mensajeMiembros"]
    else:
        url_feed = FEED_CANAL.format(canal=canal)
        clave = "normal"
        mensaje = cfg["mensaje"]

    print(f"Consultando feed {'de miembros' if miembros else 'normal'}: {canal}")
    feed = parse(url_feed)

    # No modificar el estado si el feed no devuelve entradas.
    if not feed.entries:
        print(f"Feed vacío o sin entradas: {url_feed}")
        return

    vistos = estado[canal][clave]
    # Cada feed tiene su propia primera ejecución: la primera vez solo se registra, sin avisar.
    inicializado = estado[canal][f"{clave}_inicializado"]

    for v in reversed(feed.entries):
        video_id = v.get("yt_videoid")
        if not video_id or not marcar_visto(vistos, video_id):
            continue
        if not inicializado:
            continue
        _avisar(v, mensaje, cfg, miembros, bluesky, threads, rng)

    estado[canal][f"{clave}_inicializado"] = True


def ejecutar(canales=None, ruta_estado=ARCHIVO, parse=None, bluesky=None, threads=None, max_vistos=MAX_VISTOS, rng=random):
    canales = CANALES if canales is None else canales
    bluesky = bluesky or Bluesky()
    threads = threads or Threads()

    estado = cargar_estado(ruta_estado)
    for canal, cfg in canales.items():
        if canal not in estado:
            estado[canal] = estado_vacio()
        procesar_feed(canal, cfg, estado, bluesky, threads, miembros=False, parse=parse, rng=rng)
        if cfg.get("mensajeMiembros"):
            procesar_feed(canal, cfg, estado, bluesky, threads, miembros=True, parse=parse, rng=rng)
    guardar_estado(ruta_estado, estado, canales, max_vistos)
