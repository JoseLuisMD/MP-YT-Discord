"""Webs de noticias. Para añadir una, añade una `Fuente` a la lista FUENTES.

Lo que cambia de una web a otra son datos (nombre, URL, idioma, secciones que no interesan)
y, en casos especiales, cómo se extrae la imagen: eso se define en `imagenes.py`.
"""
import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

import feedparser

from common.texto import limpiar_html, quitar_bloques, quitar_lineas_de_enlaces

from .config import MAX_EDAD_HORAS
from .imagenes import imagen_eurogamer, imagen_gameinformer, imagen_generica, imagen_vandal
from .modelos import Noticia


def fecha_entrada(e):
    t = e.get("published_parsed") or e.get("updated_parsed")
    return calendar.timegm(t) if t else None


# Bloques del contenido que no son la noticia: «desvio-container» son los recuadros que enlazan a otro
# artículo (VidaExtra, 3DJuegos y el resto de webs de Webedia). No cuentan para las palabras clave ni el resumen.
# Tampoco cuentan las líneas «En VidaExtra | <enlace>» del final (ver common/texto.py).
BLOQUES_EXCLUIDOS = ("desvio-container",)


def texto_generico(e):
    if e.get("content"):
        return e["content"][0].get("value", "")
    return e.get("summary", "")


def texto_pcgamer(e):
    """PC Gamer trae dos bloques de contenido: la ficha del autor y el artículo (dentro de <article>).
    Se usa el subtítulo (summary) más el artículo; algunas noticias no traen artículo y se quedan con el subtítulo."""
    articulo = next((c.get("value", "") for c in e.get("content") or [] if "<article" in c.get("value", "")), "")
    return f"<p>{e.get('summary', '')}</p> {articulo}"


@dataclass(frozen=True)
class Fuente:
    nombre: str
    url: str                      # admite {aaaa} y {mm}: se sustituyen por el año y el mes
    idioma: str = "es"            # si no es "es", el resumen se traduce al castellano
    rutas_excluidas: tuple = ()   # secciones de la web que no son de videojuegos
    categorias_excluidas: tuple = ()  # categorías del feed (<category>) que no son de videojuegos
    extraer_imagen: Callable = imagen_generica
    extraer_texto: Callable = texto_generico  # HTML con el cuerpo de la noticia
    bloques_excluidos: tuple = BLOQUES_EXCLUIDOS  # clases HTML de los bloques que se quitan del contenido
    imagen_en_threads: bool = False  # True si Threads no muestra la imagen de su tarjeta: la adjuntamos nosotros

    def urls(self, ahora=None, max_edad_horas=MAX_EDAD_HORAS):
        """URLs a consultar. Con plantilla de fecha, el mes actual (y el anterior a primeros de mes)."""
        if "{aaaa}" not in self.url:
            return [self.url]
        ahora = ahora or datetime.now(timezone.utc)
        antes = ahora - timedelta(hours=max_edad_horas)
        meses = sorted({(ahora.year, ahora.month), (antes.year, antes.month)})
        return [self.url.format(aaaa=a, mm=f"{m:02d}") for a, m in meses]

    def noticias(self, parse=None, ahora=None):
        """Todas las noticias del feed (sin filtrar por fecha ni por si ya están publicadas)."""
        parse = parse or feedparser.parse
        entradas = []
        for u in self.urls(ahora):
            entradas += parse(u).entries
        if not entradas:
            print(f"Sin entradas en {self.nombre}")
            return []
        resultado = []
        for e in entradas:
            enlace = (e.get("link") or "").split("#")[0]
            titulo = limpiar_html(e.get("title", ""))
            if not enlace or not titulo or any(r in enlace for r in self.rutas_excluidas):
                continue
            if any(t.get("term") in self.categorias_excluidas for t in e.get("tags") or []):
                continue
            resultado.append(Noticia(
                fuente=self.nombre,
                titulo=titulo,
                enlace=enlace,
                texto=limpiar_html(quitar_lineas_de_enlaces(quitar_bloques(self.extraer_texto(e), self.bloques_excluidos))),
                fecha=fecha_entrada(e),
                url_imagen=self.extraer_imagen(e),
                idioma=self.idioma,
                imagen_en_threads=self.imagen_en_threads,
            ))
        return resultado


FUENTES = [
    Fuente("Vandal", "https://vandal.elespanol.com/xml.cgi", extraer_imagen=imagen_vandal, imagen_en_threads=True),
    Fuente(
        "3DJuegos",
        "https://www.3djuegos.com/feedburner.xml",
        rutas_excluidas=("/tv-series/", "/manga-anime/", "/3djuegos-trivia/", "/streamers/"),
        imagen_en_threads=True,
    ),
    Fuente("Hobby Consolas", "https://www.hobbyconsolas.com/rss", rutas_excluidas=("/hobbycine/",), imagen_en_threads=True),
    Fuente("VidaExtra", "https://www.vidaextra.com/feedburner.xml", rutas_excluidas=("/cine/", "/series/")),
    Fuente(
        "Eurogamer.es",
        "https://www.eurogamer.es/feed",
        categorias_excluidas=("Tecnología",),   # artículos de productos (auriculares, wifi...)
        extraer_imagen=imagen_eurogamer,
        imagen_en_threads=True,
    ),
    Fuente("GenerationAmiga", "https://www.generationamiga.com/{aaaa}/{mm}/feed/", idioma="en"),
    Fuente(
        "Game Informer",
        "https://gameinformer.com/news.xml",   # solo noticias; rss.xml mezcla análisis, podcasts y patrocinados
        idioma="en",
        rutas_excluidas=("/digital-issue/",),   # anuncios de la revista
        extraer_imagen=imagen_gameinformer,
    ),
    Fuente(
        "PC Gamer",
        "https://www.pcgamer.com/rss/",
        idioma="en",
        rutas_excluidas=("/hardware/", "/software/"),
        extraer_texto=texto_pcgamer,
        # «product»: recuadros de ofertas y listas de «lo mejor»; «card»: enlaces a otros artículos; «credit»: créditos de las imágenes
        bloques_excluidos=BLOQUES_EXCLUIDOS + ("product", "card", "credit"),
    ),
    Fuente("Rock Paper Shotgun", "https://www.rockpapershotgun.com/feed", idioma="en", extraer_imagen=imagen_eurogamer),
]
