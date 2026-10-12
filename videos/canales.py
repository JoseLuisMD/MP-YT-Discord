"""Canales de YouTube que se vigilan. Se definen en proyectos.py; aquí se despliegan canal a canal.

Cada canal acaba con estas claves (las del proyecto, cambiadas por las suyas si las tiene):
  mensaje, mensajeMiembros, webhooks, incluirShorts, bluesky, threads, web y proyecto (nombre del proyecto)
"""
from proyectos import PROYECTOS

ARCHIVO = "vistos.json"

# Bluesky y Threads: el aviso empieza con uno de estos emojis (al azar) y el mensaje del canal
EMOJIS_AVISO = ["🚨", "🔔", "📢", "📣", "❗", "‼️", "🔴", "⏰", "🆕", "⚡"]
MAX_VISTOS = 100  # IDs recordados por feed (el feed de YouTube solo trae los 15 últimos)

# Claves que el proyecto pasa a sus canales, con su valor si el proyecto no las pone
POR_DEFECTO = {"webhooks": [], "incluirShorts": True, "bluesky": False, "threads": False, "web": None}


def canales_de(proyectos):
    """{id del canal: configuración} con lo que cada canal hereda de su proyecto."""
    canales = {}
    for nombre, proyecto in proyectos.items():
        base = {clave: proyecto.get(clave, valor) for clave, valor in POR_DEFECTO.items()}
        for canal, propio in proyecto.get("canales", {}).items():
            if canal in canales:
                raise ValueError(f"El canal {canal} está en dos proyectos: {canales[canal]['proyecto']} y {nombre}")
            canales[canal] = {**base, **propio, "proyecto": nombre}
    return canales


CANALES = canales_de(PROYECTOS)
