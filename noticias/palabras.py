"""Palabras clave por niveles y su contador (palabras_clave.json).

Formato: {"nivel_1": {"palabra": veces, ...}, "nivel_2": {...}, "nivel_3": {...}}
- Para añadir una palabra, ponla en su nivel con contador 0.
- `veces` = cuántas noticias publicadas ha ayudado a elegir. El bot lo actualiza solo.
- Al guardar, las palabras de cada nivel se ordenan alfabéticamente.
"""
from common.estado import cargar_json, guardar_json
from common.texto import normalizar


def cargar_palabras(ruta):
    """Lista de diccionarios {palabra: veces}, del nivel 1 al último."""
    datos = cargar_json(ruta, {})
    if not datos:
        print(f"No hay palabras clave en {ruta}: se elegirán noticias al azar")
    claves = sorted(datos, key=lambda k: int(k.split("_")[-1]))
    return [{p: int(v or 0) for p, v in datos[k].items()} for k in claves]


def contar(niveles, nivel, palabras):
    """Suma 1 a cada palabra del `nivel` (1, 2, 3...) que ha contribuido a publicar una noticia."""
    for p in palabras:
        niveles[nivel - 1][p] = niveles[nivel - 1].get(p, 0) + 1


def guardar_palabras(ruta, niveles):
    if not niveles:
        return  # archivo vacío o con un error de formato: no se sobrescribe para no perder las palabras
    guardar_json(ruta, {f"nivel_{i}": dict(sorted(n.items(), key=lambda kv: normalizar(kv[0])))
                        for i, n in enumerate(niveles, start=1)})
