"""Avisa de los vídeos nuevos de los canales de YouTube en Discord, Bluesky y Threads."""
import random

import feedparser

from common.publicadores import Bluesky, Discord, Publicacion, Threads
from common.texto import extraer_hashtags

from .canales import ARCHIVO, CANALES, EMOJIS_AVISO, MAX_VISTOS
from .estado import cargar_estado, estado_vacio, guardar_estado, marcar_visto

FEED_CANAL = "https://www.youtube.com/feeds/videos.xml?channel_id={canal}"
FEED_MIEMBROS = "https://www.youtube.com/feeds/videos.xml?playlist_id=UUMF{sufijo}"
# Portada vertical de un Short. YouTube solo sirve la portada personalizada en horizontal
# (maxresdefault: la portada 9:16 centrada con un fondo difuminado a los lados; oardefault es un
# fotograma automático), así que se recorta el centro 9:16 con el proxy de imágenes weserv.
PORTADA_SHORT = (
    "https://images.weserv.nl/?url=i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
    "&w=405&h=720&fit=cover&a=center&output=jpg"
)


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
        if es_short:
            # La tarjeta de YouTube recorta la portada en horizontal: se adjunta la portada vertical
            # con el enlace en el texto (si Threads no la acepta, se publica con la tarjeta)
            portada = PORTADA_SHORT.format(video_id=v.get("yt_videoid"))
            threads.publicar(Publicacion(texto=texto, enlace=v.link, url_imagen=portada, imagen_en_threads=True))
        else:
            threads.publicar(Publicacion(texto=texto, enlace=v.link))


def procesar_feed(canal, cfg, estado, bluesky, threads, miembros=False, parse=None, rng=random):
    """Avisa de los vídeos nuevos del feed. Devuelve True si ha avisado de alguno."""
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
        return False

    vistos = estado[canal][clave]
    # Cada feed tiene su propia primera ejecución: la primera vez solo se registra, sin avisar.
    inicializado = estado[canal][f"{clave}_inicializado"]
    avisados = 0

    for v in reversed(feed.entries):
        video_id = v.get("yt_videoid")
        if not video_id or not marcar_visto(vistos, video_id):
            continue
        if not inicializado:
            continue
        _avisar(v, mensaje, cfg, miembros, bluesky, threads, rng)
        avisados += 1

    estado[canal][f"{clave}_inicializado"] = True
    return avisados > 0


def ejecutar(canales=None, ruta_estado=ARCHIVO, parse=None, bluesky=None, threads=None, max_vistos=MAX_VISTOS, rng=random):
    canales = CANALES if canales is None else canales
    bluesky = bluesky or Bluesky()
    threads = threads or Threads()

    estado = cargar_estado(ruta_estado)
    webs = set()   # webs con vídeos nuevos que hay que reconstruir
    for canal, cfg in canales.items():
        if canal not in estado:
            estado[canal] = estado_vacio()
        if procesar_feed(canal, cfg, estado, bluesky, threads, miembros=False, parse=parse, rng=rng) and cfg.get("web"):
            webs.add(cfg["web"])   # los vídeos de miembros no salen en la web: no cuentan
        if cfg.get("mensajeMiembros"):
            procesar_feed(canal, cfg, estado, bluesky, threads, miembros=True, parse=parse, rng=rng)
    guardar_estado(ruta_estado, estado, canales, max_vistos)
    return sorted(webs)
