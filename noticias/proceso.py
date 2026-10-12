"""Publica cada hora una noticia de videojuegos por cada proyecto que tiene noticias (ver proyectos.py)."""
import random
from datetime import datetime, timezone

import feedparser

from common.estado import cargar_json, guardar_json
from common.publicadores import Bluesky, ColaX, Discord, Publicacion, Threads
from proyectos import PROYECTOS

from .config import EMOJIS_FUENTE, MAX_HISTORIAL, MAX_POR_EJECUCION, MAX_WEB, TEMA_THREADS, USER_AGENT
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


def publicar_noticia(n, resumen, hashtags, publicadores, rng=random, cola_x=None):
    """Publica en todos los destinos. True si al menos uno ha funcionado.

    Si se ha publicado, la apunta también en `cola_x` (para publicarla a mano en X). La cola no cuenta
    como publicación: si todas las redes fallan, la noticia no se apunta y se reintentará más adelante."""
    texto = f"{resumen}\n\n{rng.choice(EMOJIS_FUENTE)} {n.fuente}"
    n.url_imagen = n.url_imagen or imagen_og(n.enlace)   # se guarda en la noticia para la web
    publicacion = Publicacion(
        texto=texto,
        enlace=n.enlace,
        titulo_tarjeta=n.titulo,
        url_imagen=n.url_imagen,
        hashtags=hashtags,
        imagen_en_threads=n.imagen_en_threads,
    )
    resultados = [p.publicar(publicacion) for p in publicadores]
    if any(resultados) and cola_x:
        cola_x.publicar(publicacion)
    return any(resultados)


def entrada_web(n, resumen, ahora=None):
    """Datos de una noticia publicada tal como los muestra la web (noticias_web.json)."""
    ahora = ahora or datetime.now(timezone.utc)
    return {
        "titulo": n.titulo,
        "resumen": resumen,
        "enlace": n.enlace,
        "imagen": n.url_imagen,
        "fuente": n.fuente,
        "fecha": ahora.astimezone(timezone.utc).isoformat(timespec="seconds"),
    }


def ejecutar(fuentes, ruta, ruta_palabras, publicadores, ruta_web=None, parse=None, ahora=None, rng=random, cola_x=None):
    """Publica una noticia de `fuentes` en los `publicadores` (y la apunta en `cola_x`, si la hay).
    Devuelve True si ha publicado alguna."""
    feedparser.USER_AGENT = USER_AGENT
    palabras = cargar_palabras(ruta_palabras)
    niveles = compilar_niveles(palabras)

    publicadas = cargar_json(ruta, [])
    web = cargar_json(ruta_web, []) if ruta_web else []   # la más nueva primero
    publicada = False
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
            if publicar_noticia(c, resumen, hashtags, publicadores, rng, cola_x):
                publicada = True
                publicadas.append(c.enlace)
                web.insert(0, entrada_web(c, resumen, ahora))
                if c.nivel:
                    contar(palabras, c.nivel, c.coincide)

    guardar_json(ruta, publicadas[-MAX_HISTORIAL:])
    if ruta_web:
        guardar_json(ruta_web, web[:MAX_WEB])
    guardar_palabras(ruta_palabras, palabras)
    return publicada


def fuentes_de(nombres, fuentes=FUENTES):
    """Las `Fuente` con esos nombres (error si alguno no existe, para que no pase desapercibida una errata)."""
    por_nombre = {f.nombre: f for f in fuentes}
    desconocidas = [n for n in nombres if n not in por_nombre]
    if desconocidas:
        raise ValueError(f"Webs de noticias que no están en noticias/fuentes.py: {desconocidas}")
    return [por_nombre[n] for n in nombres]


def publicadores_de(proyecto, noticias):
    publicadores = [Discord(noticias["discord"])] if noticias.get("discord") else []
    if proyecto.get("bluesky"):
        publicadores.append(Bluesky())
    if proyecto.get("threads"):
        publicadores.append(Threads(tema=TEMA_THREADS))
    return publicadores


def ejecutar_proyectos(proyectos=None, **opciones):
    """Publica las noticias de cada proyecto que las tiene. Devuelve los repos de las webs que hay que reconstruir."""
    proyectos = PROYECTOS if proyectos is None else proyectos
    webs = []
    for nombre, proyecto in proyectos.items():
        noticias = proyecto.get("noticias")
        if not noticias:
            continue
        print(f"--- Noticias de {nombre}")
        publicada = ejecutar(
            fuentes=fuentes_de(noticias["fuentes"]),
            ruta=noticias["historial"],
            ruta_palabras=noticias["palabras"],
            ruta_web=noticias.get("web"),
            publicadores=publicadores_de(proyecto, noticias),
            cola_x=ColaX("noticia", nombre) if proyecto.get("x") else None,
            **opciones,
        )
        if publicada and noticias.get("web") and proyecto.get("web"):
            webs.append(proyecto["web"])
    return webs
