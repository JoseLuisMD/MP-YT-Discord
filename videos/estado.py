"""Estado de los vídeos ya vistos (vistos.json).

Formato nuevo:   "CANAL": {"normal": [ids...], "miembros": [ids...]}   (en orden de llegada, el más nuevo al final)
Formato antiguo: "CANAL": [ids...]   (se sigue entendiendo)

Por feed se guardan como mucho los `max_vistos` últimos IDs. Los que siguen apareciendo en el feed
se mueven al final en cada ejecución, así que nunca se descarta uno que YouTube aún devuelve.
"""
from common.estado import cargar_json, guardar_json


def estado_vacio():
    return {
        "normal": [],
        "miembros": [],
        "normal_inicializado": False,
        "miembros_inicializado": False,
    }


def cargar_estado(ruta):
    datos = cargar_json(ruta, {})
    estado = {}
    for canal, contenido in datos.items():
        if isinstance(contenido, list):
            estado[canal] = {
                "normal": list(dict.fromkeys(contenido)),
                "miembros": [],
                "normal_inicializado": True,
                "miembros_inicializado": False,
            }
        elif isinstance(contenido, dict):
            estado[canal] = {
                "normal": list(dict.fromkeys(contenido.get("normal", []))),
                "miembros": list(dict.fromkeys(contenido.get("miembros", []))),
                "normal_inicializado": "normal" in contenido,
                "miembros_inicializado": "miembros" in contenido,
            }
    return estado


def marcar_visto(vistos, video_id):
    """Pone el ID al final de la lista (el más reciente). Devuelve True si no estaba."""
    nuevo = video_id not in vistos
    if not nuevo:
        vistos.remove(video_id)
    vistos.append(video_id)
    return nuevo


def guardar_estado(ruta, estado, canales, max_vistos):
    a_guardar = {}
    for canal, datos in estado.items():
        cfg = canales.get(canal, {})
        contenido = {"normal": datos["normal"][-max_vistos:]}
        if cfg.get("mensajeMiembros"):
            contenido["miembros"] = datos["miembros"][-max_vistos:]
        a_guardar[canal] = contenido
    guardar_json(ruta, a_guardar)
