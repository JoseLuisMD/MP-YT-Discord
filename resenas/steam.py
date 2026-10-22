"""Micro-reseñas de un Conservador de Steam.

Steam no tiene una API documentada para esto: se usa el mismo JSON con el que su tienda lista las recomendaciones
de un conservador, que trae el HTML de la lista (igual que la web, en MP-Website/src/lib/datos.js).
"""
import html
import re
from dataclasses import dataclass
from typing import Optional

import requests

URL_CONSERVADOR = "https://store.steampowered.com/curator/{conservador}/"
URL_RESENAS = URL_CONSERVADOR + "ajaxgetfilteredrecommendations/?query=&start=0&count=24&sort=recent&l=spanish"
USER_AGENT = "Mozilla/5.0 (compatible; MundosPixeladosBot/1.0)"
ICONOS = {"recommended": "👍", "not_recommended": "👎", "informational": "ℹ️"}


@dataclass
class Resena:
    appid: str
    juego: str
    veredicto: str            # recommended, not_recommended o informational (la clase «color_...» de Steam)
    veredicto_texto: str      # como lo escribe Steam: «Recomendada», «No recomendada», «Informativa»
    texto: str
    tienda: str               # página del juego en Steam, con la reseña del conservador destacada
    imagen: Optional[str]     # cabecera del juego (460×215)
    video: Optional[str]      # la reseña completa (vídeo de YouTube), si la tiene

    @property
    def icono(self):
        return ICONOS.get(self.veredicto, "ℹ️")


def _texto(fragmento):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragmento or ""))).strip()


def leer_resena(bloque, conservador):
    """Una reseña a partir de su bloque HTML, o None si falta algo imprescindible."""
    tienda = re.search(r'class="store_capsule[^"]*"[^>]*href="https://store\.steampowered\.com/app/(\d+)/([^"/?]*)', bloque)
    imagen = re.search(r'<img src="(https://[^"]+/header_292x136\.jpg)[^"]*" alt="([^"]*)"', bloque)
    tipo = re.search(r"class='color_(\w+)'>([^<]*)<", bloque)
    texto = re.search(r'class="recommendation_desc">(.*?)</div>', bloque, re.S)
    video = re.search(r'class="recommendation_readmore"><a href="(https?://[^"]+)"', bloque)
    if not tienda or not imagen or not texto or not _texto(texto.group(1)):
        return None
    appid, slug = tienda.groups()
    return Resena(
        appid=appid,
        juego=_texto(imagen.group(2)),
        veredicto=tipo.group(1) if tipo else "informational",
        veredicto_texto=_texto(tipo.group(2)) if tipo else "Informativa",
        texto=_texto(texto.group(1)),
        tienda=f"https://store.steampowered.com/app/{appid}/{slug}/?curator_clanid={conservador}",
        imagen=imagen.group(1).replace("header_292x136.jpg", "header.jpg"),
        video=html.unescape(video.group(1)) if video else None,
    )


def cargar_resenas(conservador, get=requests.get):
    """Las últimas reseñas del conservador, de la más nueva a la más antigua. None si Steam falla
    (para no tocar el estado: no es lo mismo que no tener reseñas)."""
    try:
        r = get(URL_RESENAS.format(conservador=conservador),
                headers={"User-Agent": USER_AGENT, "Accept-Language": "es-ES"}, timeout=20)
        r.raise_for_status()
        datos = r.json()
        if datos.get("success") != 1 or not isinstance(datos.get("results_html"), str):
            raise ValueError("respuesta inesperada")
    except (requests.RequestException, ValueError, AttributeError) as e:
        print(f"No se pudieron cargar las reseñas de Steam ({conservador}): {e}")
        return None
    bloques = datos["results_html"].split('class="recommendation"')[1:]
    return [r for r in (leer_resena(b, conservador) for b in bloques) if r]
