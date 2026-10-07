import feedparser, requests, json, os
from atproto import Client, client_utils

CANALES = {
    # --- Canales que avisan en Discord y en Bluesky ---
    "UCLD3BqL4n2GKmitkEQGCoAQ": {
        "mensaje": "¡Nuevo vídeo en Mundos Pixelados!",
        "webhooks": ["DISCORD_WEBHOOK"],
        "bluesky": True,
    },
    "UCb3jFYgTbBLjDDOlZiD-2kg": {
        "mensaje": "¡Nuevo short en Mundos Pixelados Shorts!",
        "webhooks": ["DISCORD_WEBHOOK"],
        "bluesky": True,
    },
    # --- Canales solo para Discord ---
    "UCYk9AH19xF7dtzM9OY7obmA": {
        "mensaje": "¡Nuevo vídeo en el canal!",
        "webhooks": ["DISCORD_WEBHOOK_VRTX"],
        "bluesky": False,
    },
    "UCngXjqgH_-42BgtegyzI_-A": {
        "mensaje": "¡Nuevo vídeo en el canal secundario!",
        "webhooks": ["DISCORD_WEBHOOK_VRTX"],
        "bluesky": False,
    },
    "UC4MGzV7ahAN1khnzdjp3rkw": {
        "mensaje": "¡Nuevo vídeo en el canal de WarCraft 3!",
        "webhooks": ["DISCORD_WEBHOOK_VRTX"],
        "bluesky": False,
    },
}
ARCHIVO = "vistos.json"

_bsky = None  # se inicia solo cuando hace falta


def publicar_bluesky(mensaje, link):
    global _bsky
    try:
        if _bsky is None:
            _bsky = Client()
            _bsky.login(os.environ["BSKY_HANDLE"], os.environ["BSKY_APP_PASSWORD"])
        texto = client_utils.TextBuilder().text(f"{mensaje}\n\n").link(link, link)
        _bsky.send_post(texto)
    except Exception as e:
        print(f"Error publicando en Bluesky: {e}")


def publicar_discord(nombre_secreto, mensaje, link):
    url = os.environ.get(nombre_secreto)
    if not url:
        print(f"Falta el secreto {nombre_secreto}")
        return
    try:
        r = requests.post(url, json={"content": f"{mensaje}\n\n{link}"}, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Error enviando a {nombre_secreto}: {e}")


try:
    with open(ARCHIVO) as f:
        estado = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    estado = {}

for canal, cfg in CANALES.items():
    feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={canal}")
    if not feed.entries:
        continue  # fallo temporal del feed: no tocamos nada
    primera_vez = canal not in estado
    vistos = set(estado.get(canal, []))
    for v in reversed(feed.entries):  # del más antiguo al más nuevo
        if v.yt_videoid in vistos:
            continue
        vistos.add(v.yt_videoid)
        if primera_vez:
            continue
        for nombre in cfg["webhooks"]:
            publicar_discord(nombre, cfg["mensaje"], v.link)
        if cfg["bluesky"]:
            publicar_bluesky(cfg["mensaje"], v.link)
    estado[canal] = sorted(vistos)

with open(ARCHIVO, "w") as f:
    json.dump(estado, f, indent=2)
