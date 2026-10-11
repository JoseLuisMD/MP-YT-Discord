"""Utilidades de texto compartidas."""
import html
import re
import unicodedata
from html.parser import HTMLParser


def normalizar(texto):
    """Minúsculas y sin tildes, para comparar textos."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def limpiar_html(texto):
    """Quita etiquetas HTML, decodifica entidades y compacta los espacios."""
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return re.sub(r"\s+", " ", html.unescape(texto)).strip()


class _QuitarBloques(HTMLParser):
    """Copia el HTML saltándose <script>, <style> y los elementos cuya clase esté en `clases` (con todo su interior)."""
    VACIAS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self, clases):
        super().__init__(convert_charrefs=False)
        self.clases, self.salida, self.saltando = set(clases), [], []   # pila de etiquetas abiertas dentro del bloque

    def _quitar(self, tag, attrs):
        return tag in ("script", "style") or bool(self.clases & set((dict(attrs).get("class") or "").split()))

    def handle_starttag(self, tag, attrs):
        if self.saltando:
            if tag not in self.VACIAS:
                self.saltando.append(tag)
        elif self._quitar(tag, attrs) and tag not in self.VACIAS:
            self.saltando.append(tag)
        else:
            self.salida.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        if not self.saltando:
            self.salida.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.saltando:
            if tag in self.saltando:   # cierra hasta su apertura (tolera HTML mal cerrado)
                while self.saltando.pop() != tag:
                    pass
        else:
            self.salida.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.saltando:
            self.salida.append(data)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")


def quitar_bloques(texto, clases=()):
    """Quita del HTML los scripts, estilos y bloques con alguna de esas clases (p. ej. enlaces a otras noticias)."""
    parser = _QuitarBloques(clases)
    parser.feed(texto or "")
    parser.close()
    return "".join(parser.salida)


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
