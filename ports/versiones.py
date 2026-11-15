"""Qué versión tiene una release y si cuenta como estable.

Los ports ponen las versiones de mil maneras («v1.3.2», «v 1.0.0», «1.3», «knack2-Version-0.18.3»…), así que se
busca el primer número con punto del tag (o del nombre de la release, si el tag no tiene) y se descartan las
pruebas, las betas, los launchers y las versiones por fecha.
"""
import re

# Un número de versión con al menos un punto, que no vaya pegado a una letra o a otro número («knack2» no cuenta)
VERSION = re.compile(r"(?<![A-Za-z0-9.])[vV]?\s?(\d+)\.(\d+)(?:\.(\d+))?")
# Si el tag o el nombre llevan alguna de estas palabras, la release no es estable
NO_ESTABLE = re.compile(
    r"alpha|beta|(?<![a-z])rc(?![a-z])|preview|(?<![a-z])pre(?![a-z])|(?<![a-z])test|nightly|(?<![a-z])dev(?![a-z])"
    r"|snapshot|canary|experimental|unstable|unverified",
    re.IGNORECASE,
)
# Releases que no son del juego en sí
NO_ES_EL_JUEGO = re.compile(r"launcher|installer|instalador|updater|toolkit|server", re.IGNORECASE)
AÑO_MINIMO = 1900   # «2026.11.11» es una fecha, no la versión 2026


def version(texto):
    """La versión de un tag o nombre como tupla (mayor, menor, parche), o None si no tiene o es una fecha."""
    m = VERSION.search(texto or "")
    if not m:
        return None
    v = tuple(int(n) for n in m.groups(default="0"))
    return None if v[0] >= AÑO_MINIMO else v


def version_estable(release):
    """La versión de una release de la API de GitHub si es estable, o None si no lo es (borrador, prerelease,
    beta, prueba, launcher o sin versión reconocible)."""
    if release.get("draft") or release.get("prerelease"):
        return None
    tag, nombre = release.get("tag_name") or "", release.get("name") or ""
    textos = f"{tag} {nombre}"
    if NO_ESTABLE.search(textos) or NO_ES_EL_JUEGO.search(tag):
        return None
    return version(tag) or version(nombre)


def texto_version(v):
    """(1, 3, 0) → «1.3.0»."""
    return ".".join(str(n) for n in v)
