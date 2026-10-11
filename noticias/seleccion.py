"""Qué noticia se publica: primero las que coinciden con las palabras clave del nivel 1; si no hay, del 2;
luego del 3; y si no hay ninguna, una al azar."""
import random
import re
import time

from common.texto import normalizar

from .config import MAX_EDAD_HORAS


def compilar_patrones(palabras):
    """Cada palabra clave se busca entera (sin tildes ni mayúsculas): «sonic» no coincide con «supersonic»."""
    return [(k, re.compile(rf"(?<!\w){re.escape(normalizar(k))}(?!\w)")) for k in palabras]


def compilar_niveles(niveles):
    """Una lista de patrones por cada nivel de palabras clave."""
    return [compilar_patrones(palabras) for palabras in niveles]


def coincidencias(texto, patrones):
    t = normalizar(texto)
    return [k for k, patron in patrones if patron.search(t)]


def clasificar(texto, niveles):
    """(nivel, coincidencias) del primer nivel con alguna coincidencia, o (None, []) si no hay ninguna."""
    for nivel, patrones in enumerate(niveles, start=1):
        encontradas = coincidencias(texto, patrones)
        if encontradas:
            return nivel, encontradas
    return None, []


def es_reciente(fecha, ahora=None, max_edad_horas=MAX_EDAD_HORAS):
    """`fecha` y `ahora` son marcas de tiempo UTC. Sin fecha se acepta."""
    ahora = time.time() if ahora is None else ahora
    return fecha is None or ahora - fecha <= max_edad_horas * 3600


def elegir(candidatas, max_por_ejecucion, rng=random):
    """Las del nivel de palabras clave más prioritario; dentro del nivel, las que más palabras aciertan
    (y las más recientes). Si ninguna coincide en ningún nivel, al azar."""
    con_match = sorted(
        (c for c in candidatas if c.nivel is not None),
        key=lambda c: (c.nivel, -len(c.coincide), -(c.fecha or 0)),
    )
    if con_match:
        return con_match[:max_por_ejecucion]
    return rng.sample(candidatas, min(max_por_ejecucion, len(candidatas)))
