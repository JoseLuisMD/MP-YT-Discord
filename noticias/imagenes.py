"""Cómo encontrar la imagen de una noticia. Cada web la pone en un sitio distinto del feed.

Un extractor recibe una entrada de feedparser y devuelve la URL de la imagen o None.
Para una web con un formato especial, se escribe su extractor aquí y se asigna a su `Fuente`.
"""
import html
import re
from urllib.parse import urljoin

import requests

USER_AGENT = "Mozilla/5.0 (compatible; MundosPixeladosBot/1.0)"


def _html_de(e):
    texto = e.get("summary", "")
    if e.get("content"):
        texto += " " + e["content"][0].get("value", "")
    return texto


def imagen_generica(e):
    """Campos estándar del feed (media:thumbnail, media:content, enclosure) y, si no, la primera <img>."""
    for campo in ("media_thumbnail", "media_content"):
        for m in e.get(campo) or []:
            if m.get("url"):
                return m["url"]
    for enc in e.get("enclosures") or []:
        if "image" in (enc.get("type") or "") and enc.get("href"):
            return enc["href"]
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)', _html_de(e)):
        if src.startswith("http") and not re.search(r"pixel|1x1|spacer|\.gif", src, re.I):
            return html.unescape(src)
    return None


def imagen_vandal(e):
    """Vandal solo pone imágenes dentro del HTML y marca la principal con el enlace «#imagen1»."""
    m = re.search(r'#imagen1["\'][^>]*>\s*<img[^>]+src=["\']([^"\']+)', _html_de(e))
    if m:
        return html.unescape(m.group(1))
    return imagen_generica(e)


def imagen_og(enlace):
    """Último recurso: la imagen que la propia web declara para compartir (og:image)."""
    try:
        r = requests.get(enlace, headers={"User-Agent": USER_AGENT}, timeout=15)
        r.raise_for_status()
        cabecera = r.text[:200_000]
        for patron in (
            r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)',
        ):
            m = re.search(patron, cabecera, re.I)
            if m:
                return urljoin(enlace, html.unescape(m.group(1)))
    except Exception as ex:
        print(f"No se pudo leer la imagen de la página ({enlace}): {ex}")
    return None
