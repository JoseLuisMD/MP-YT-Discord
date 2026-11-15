"""Qué versión tiene una release y si cuenta como estable.

Los ports ponen las versiones de mil maneras («v1.3.2», «v 1.0.0», «1.3», «v2», «knack2-Version-0.18.3»…), así que
se busca el primer número con punto del tag (o del nombre de la release, si el tag no tiene) o un tag que sea solo
un número, y se descartan las pruebas, las betas, los launchers y las versiones por fecha.
"""
import re

# Un número de versión con al menos un punto, que no vaya pegado a una letra o a otro número («knack2» no cuenta)
VERSION = re.compile(r"(?<![A-Za-z0-9.])[vV]?\s?(\d+)\.(\d+)(?:\.(\d+))?")
# Un tag que es solo un número («v2», «1»). Solo cuenta en el tag, no en el nombre («Build 365» no es la versión 365)
VERSION_SUELTA = re.compile(r"\s*[vV]?\s?(\d+)\s*")
# Si el tag o el nombre llevan alguna de estas palabras, la release no es estable
NO_ESTABLE = re.compile(
    r"alpha|beta|(?<![a-z])rc(?![a-z])|preview|(?<![a-z])pre(?![a-z])|(?<![a-z])test|nightly|(?<![a-z])dev(?![a-z])"
    r"|snapshot|canary|experimental|unstable|unverified",
    re.IGNORECASE,
)
# Releases que no son del juego en sí
NO_ES_EL_JUEGO = re.compile(r"launcher|installer|instalador|updater|toolkit|server", re.IGNORECASE)
AÑO_MINIMO = 1900   # «2026.11.11» es una fecha, no la versión 2026


def _numeros(texto, suelta=False):
    """Los números de la versión tal como están escritos («1.3» → ("1", "3")), o None si no tiene."""
    texto = texto or ""
    m = VERSION.search(texto)
    if m:
        return tuple(n for n in m.groups() if n is not None)
    m = VERSION_SUELTA.fullmatch(texto) if suelta else None
    return (m.group(1),) if m else None


def version(texto, suelta=False):
    """La versión de un tag o nombre como tupla (mayor, menor, parche), o None si no tiene o es una fecha.
    Con `suelta`, un texto que sea solo un número («v2») también cuenta como versión."""
    numeros = _numeros(texto, suelta)
    if not numeros:
        return None
    v = tuple(int(n) for n in numeros) + (0,) * (3 - len(numeros))
    return None if v[0] >= AÑO_MINIMO else v


def descartada(release):
    """True si la release no es estable a propósito: borrador, prerelease, beta, prueba, launcher…"""
    if release.get("draft") or release.get("prerelease"):
        return True
    tag, nombre = release.get("tag_name") or "", release.get("name") or ""
    return bool(NO_ESTABLE.search(f"{tag} {nombre}") or NO_ES_EL_JUEGO.search(tag))


def version_estable(release):
    """La versión de una release de la API de GitHub si es estable, o None si no lo es (descartada o sin versión
    reconocible)."""
    if descartada(release):
        return None
    tag, nombre = release.get("tag_name") or "", release.get("name") or ""
    return version(tag, suelta=True) or version(nombre)


def texto_original(release):
    """El número de versión de una release como lo escribe su tag, sin la «v» ni lo que venga detrás («v1.3» →
    «1.3», «1.5.1_tag» → «1.5.1», «v2» → «2»), o el de su nombre si el tag no tiene. None si ninguno tiene."""
    tag, nombre = release.get("tag_name") or "", release.get("name") or ""
    for texto, suelta in ((tag, True), (nombre, False)):
        if version(texto, suelta):
            return ".".join(_numeros(texto, suelta))
    return None
