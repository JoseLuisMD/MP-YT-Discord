"""Utilidades de texto compartidas."""
import html
import re
import unicodedata


def normalizar(texto):
    """Minúsculas y sin tildes, para comparar textos."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def limpiar_html(texto):
    """Quita etiquetas HTML, decodifica entidades y compacta los espacios."""
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return re.sub(r"\s+", " ", html.unescape(texto)).strip()


def recortar(texto, maximo):
    """Recorta en una palabra completa y añade «…» si el texto no cabe."""
    if len(texto) <= maximo:
        return texto
    return texto[: maximo - 1].rsplit(" ", 1)[0] + "…"


def extraer_hashtags(descripcion):
    """Hashtags de un texto, sin repetidos y sin los que son solo números."""
    vistos, lista = set(), []
    for h in re.findall(r"#\w+", descripcion or ""):
        if h[1:].isdigit() or h.lower() in vistos:
            continue
        vistos.add(h.lower())
        lista.append(h)
    return lista
