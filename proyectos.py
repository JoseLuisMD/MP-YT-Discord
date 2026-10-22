"""Proyectos: cada uno con sus canales de YouTube, dónde avisa, su web y (si las tiene) sus noticias.
Aquí solo hay datos: para añadir un canal o un proyecto, añade una entrada.

Claves de cada proyecto (los canales las heredan):
  webhooks       nombres de los secretos con los webhooks de Discord donde avisar de los vídeos
  incluirShorts  False = no avisar de Shorts en Discord (por defecto True)
  bluesky        True = avisar también en Bluesky (vídeos y noticias)
  threads        True = avisar también en Threads (vídeos y noticias)
  x              True = apuntar los vídeos y noticias en cola_x.json para publicarlos a mano en X
                 desde el panel (repo MP-Backend); los vídeos para miembros no se apuntan
  web            (opcional) repo de GitHub de la web del proyecto: se reconstruye (workflow web.yml)
                 cuando hay un vídeo o una noticia nuevos
  canales        {id del canal: claves del canal}
  noticias       (opcional) noticias de videojuegos del proyecto; sin esta clave, el proyecto no publica noticias
  resenas        (opcional) avisos de las reseñas nuevas de su Conservador de Steam (workflow resenas.yml)

Claves de cada canal:
  mensaje          texto del aviso de un vídeo nuevo
  mensajeMiembros  (opcional) texto del aviso de un vídeo solo para miembros; si no está, no se consultan
  ...y cualquier clave del proyecto, para cambiarla solo en ese canal (p. ej. "incluirShorts": False)

Claves de `noticias`:
  fuentes   nombres de las webs de noticias (las `Fuente` de noticias/fuentes.py)
  discord   secreto con el webhook de Discord donde se publican
  historial archivo con los enlaces ya publicados
  palabras  archivo con las palabras clave (ver noticias/palabras.py)
  web       (opcional) archivo con las últimas noticias para la web
  recientes (opcional) archivo con los títulos y resúmenes publicados hace poco, para no publicar la misma noticia
            desde otra web (ver HORAS_RECIENTES en noticias/config.py); sin esta clave no se comprueba

Claves de `resenas`:
  conservador  ID del Conservador de Steam (el número de store.steampowered.com/curator/<ID>/)
  mensaje      texto del aviso de una reseña nueva
  enlace       (opcional) página del Mentor de Steam, que se enlaza debajo de cada reseña; si no está, la del ID
  titulo       (opcional) título de la tarjeta de Bluesky, que enlaza al Mentor (por defecto «Mentor de Steam»)
  ...y webhooks, bluesky, threads, x o web, para cambiarlas solo en las reseñas (si no, las del proyecto)
"""

PROYECTOS = {
    "mundospixelados": {
        "webhooks": ["DISCORD_WEBHOOK"],
        "bluesky": True,
        "threads": True,
        "x": True,
        "web": "JoseLuisMD/MP-Website",
        "canales": {
            "UCLD3BqL4n2GKmitkEQGCoAQ": {"mensaje": "¡Nuevo vídeo en Mundos Pixelados!"},
            "UCb3jFYgTbBLjDDOlZiD-2kg": {"mensaje": "¡Nuevo short en Mundos Pixelados Shorts!"},
        },
        "noticias": {
            "fuentes": ["Vandal", "3DJuegos", "Hobby Consolas", "VidaExtra", "Eurogamer.es", "GenerationAmiga",
                        "Game Informer", "PC Gamer", "Rock Paper Shotgun"],
            "discord": "DISCORD_WEBHOOK_NOTICIAS",
            "historial": "noticias_publicadas.json",
            "palabras": "palabras_clave.json",
            "web": "noticias_web.json",
            "recientes": "noticias_recientes.json",
        },
        "resenas": {
            "conservador": "46111642",
            "mensaje": "¡Nueva reseña en nuestro Mentor de Steam!",
            "enlace": "https://store.steampowered.com/curator/46111642-Mundos-Pixelados/",
            "titulo": "Mentor de Steam de Mundos Pixelados",
        },
    },
    "vortix": {
        "webhooks": ["DISCORD_WEBHOOK_VRTX"],
        "incluirShorts": False,
        "bluesky": False,
        "threads": False,
        "x": False,
        "canales": {
            "UCYk9AH19xF7dtzM9OY7obmA": {
                "mensaje": "¡Nuevo vídeo en el canal!",
                "mensajeMiembros": "¡Nuevo vídeo para miembros en el canal!",
            },
            "UCngXjqgH_-42BgtegyzI_-A": {"mensaje": "¡Nuevo vídeo en el canal secundario!"},
            "UC4MGzV7ahAN1khnzdjp3rkw": {"mensaje": "¡Nuevo vídeo en el canal de WarCraft 3!"},
        },
    },
}
