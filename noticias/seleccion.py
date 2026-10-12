"""Qué noticia se publica: primero las que coinciden con las palabras clave del nivel 1; si no hay, del 2;
luego del 3; y si no hay ninguna, una al azar. Antes se descartan las que ya se han publicado desde otra web."""
import random
import re
import time

from common.texto import normalizar

from .config import MAX_EDAD_HORAS, MIN_PALABRAS_COMUNES, MIN_PROPORCION_COMUN


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


# Palabras que no ayudan a saber de qué trata un título (sin tildes, como las deja `normalizar`)
PALABRAS_VACIAS = set("""
a al algo ante antes asi aun aunque bajo cada como con contra cual cuando de del desde donde dos durante e el ella
ellos en entre era es esa ese eso esta este esto estos estas fue ha han hace hasta hay la las le les lo los mas me mi
muy nada ni no nos o otra otro otros para pero poco por porque que quien se ser si sin sobre son su sus tambien tan te
tiene tienen todo todos tras tu un una uno unos unas ya y yo
the of and to in on for with is are was it its at by from as an or be has have new now can could after more this that
nuevo nueva nuevos nuevas juego juegos videojuego videojuegos anuncia anunciado anunciada llegara tendra sera trailer
""".split())


def palabras_significativas(titulo):
    """Palabras del título sin tildes ni mayúsculas, sin las vacías ni las de menos de 3 letras (salvo números)."""
    return {p for p in re.findall(r"\w+", normalizar(titulo))
            if p not in PALABRAS_VACIAS and (len(p) > 2 or p.isdigit())}


def es_repetida(titulo, titulos_publicados, min_comunes=MIN_PALABRAS_COMUNES, min_proporcion=MIN_PROPORCION_COMUN):
    """True si el título parece la misma noticia que alguno de los publicados (aunque sea de otra web)."""
    palabras = palabras_significativas(titulo)
    for publicado in titulos_publicados:
        otras = palabras_significativas(publicado)
        comunes = len(palabras & otras)
        if comunes >= min_comunes and comunes >= min_proporcion * min(len(palabras), len(otras)):
            return True
    return False
