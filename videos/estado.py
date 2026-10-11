"""Estado de los vídeos ya vistos (vistos.json).

Formato nuevo:   "CANAL": {"normal": [ids...], "miembros": [ids...]}
Formato antiguo: "CANAL": [ids...]   (se sigue entendiendo)
"""
from common.estado import cargar_json, guardar_json


def estado_vacio():
    return {
        "normal": set(),
        "miembros": set(),
        "normal_inicializado": False,
        "miembros_inicializado": False,
    }


def cargar_estado(ruta):
    datos = cargar_json(ruta, {})
    estado = {}
    for canal, contenido in datos.items():
        if isinstance(contenido, list):
            estado[canal] = {
                "normal": set(contenido),
                "miembros": set(),
                "normal_inicializado": True,
                "miembros_inicializado": False,
            }
        elif isinstance(contenido, dict):
            estado[canal] = {
                "normal": set(contenido.get("normal", [])),
                "miembros": set(contenido.get("miembros", [])),
                "normal_inicializado": "normal" in contenido,
                "miembros_inicializado": "miembros" in contenido,
            }
    return estado


def guardar_estado(ruta, estado, canales):
    a_guardar = {}
    for canal, datos in estado.items():
        cfg = canales.get(canal, {})
        contenido = {"normal": sorted(datos["normal"])}
        if cfg.get("mensajeMiembros"):
            contenido["miembros"] = sorted(datos["miembros"])
        a_guardar[canal] = contenido
    guardar_json(ruta, a_guardar)
