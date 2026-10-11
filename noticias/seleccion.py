"""Qué noticia se publica: primero las que coinciden con las palabras clave; si no hay, una al azar."""
import random
import re
import time

from common.texto import normalizar

from .config import MAX_EDAD_HORAS


def compilar_patrones(palabras):
    """Cada palabra clave se busca entera (sin tildes ni mayúsculas): «sonic» no coincide con «supersonic»."""
    return [(k, re.compile(rf"(?<!\w){re.escape(normalizar(k))}(?!\w)")) for k in palabras]


def coincidencias(texto, patrones):
    t = normalizar(texto)
    return [k for k, patron in patrones if patron.search(t)]


def es_reciente(fecha, ahora=None, max_edad_horas=MAX_EDAD_HORAS):
    """`fecha` y `ahora` son marcas de tiempo UTC. Sin fecha se acepta."""
    ahora = time.time() if ahora is None else ahora
    return fecha is None or ahora - fecha <= max_edad_horas * 3600


def elegir(candidatas, max_por_ejecucion, rng=random):
    """Las que más palabras clave aciertan (y más recientes); si no hay ninguna, al azar."""
    con_match = sorted(
        (c for c in candidatas if c.coincide),
        key=lambda c: (-len(c.coincide), -(c.fecha or 0)),
    )
    if con_match:
        return con_match[:max_por_ejecucion]
    return rng.sample(candidatas, min(max_por_ejecucion, len(candidatas)))
