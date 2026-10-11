"""Canales de YouTube que se vigilan. Aquí solo hay datos: para añadir un canal, añade una entrada.

Claves de cada canal:
  mensaje          texto del aviso de un vídeo nuevo
  mensajeMiembros  (opcional) texto del aviso de un vídeo solo para miembros; si no está, no se consultan
  webhooks         nombres de los secretos con los webhooks de Discord donde avisar
  incluirShorts    False = no avisar de Shorts en Discord
  bluesky          True = avisar también en Bluesky
  threads          True = avisar también en Threads
"""

ARCHIVO = "vistos.json"
MAX_VISTOS = 100  # IDs recordados por feed (el feed de YouTube solo trae los 15 últimos)

CANALES = {
    # --- Canales que avisan en Discord, Bluesky y Threads ---
    "UCLD3BqL4n2GKmitkEQGCoAQ": {
        "mensaje": "¡Nuevo vídeo en Mundos Pixelados!",
        "webhooks": ["DISCORD_WEBHOOK"],
        "incluirShorts": True,
        "bluesky": True,
        "threads": True,
    },
    "UCb3jFYgTbBLjDDOlZiD-2kg": {
        "mensaje": "¡Nuevo short en Mundos Pixelados Shorts!",
        "webhooks": ["DISCORD_WEBHOOK"],
        "incluirShorts": True,
        "bluesky": True,
        "threads": True,
    },
    # --- Canales solo para Discord ---
    "UCYk9AH19xF7dtzM9OY7obmA": {
        "mensaje": "¡Nuevo vídeo en el canal!",
        "mensajeMiembros": "¡Nuevo vídeo para miembros en el canal!",
        "webhooks": ["DISCORD_WEBHOOK_VRTX"],
        "incluirShorts": False,
        "bluesky": False,
        "threads": False,
    },
    "UCngXjqgH_-42BgtegyzI_-A": {
        "mensaje": "¡Nuevo vídeo en el canal secundario!",
        "webhooks": ["DISCORD_WEBHOOK_VRTX"],
        "incluirShorts": False,
        "bluesky": False,
        "threads": False,
    },
    "UC4MGzV7ahAN1khnzdjp3rkw": {
        "mensaje": "¡Nuevo vídeo en el canal de WarCraft 3!",
        "webhooks": ["DISCORD_WEBHOOK_VRTX"],
        "incluirShorts": False,
        "bluesky": False,
        "threads": False,
    },
}
