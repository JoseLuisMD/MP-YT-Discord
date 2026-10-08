import feedparser, requests, json, os, re, time
from atproto import Client, client_utils, models

CANALES = {
    # --- Canales que avisan en Discord, Bluesky y Threads ---
    "UCLD3BqL4n2GKmitkEQGCoAQ": {
        "mensaje": "¡Nuevo vídeo en Mundos Pixelados!",
        "webhooks": ["DISCORD_WEBHOOK"],
        "bluesky": True,
        "threads": True,
    },
    "UCb3jFYgTbBLjDDOlZiD-2kg": {
        "mensaje": "¡Nuevo short en Mundos Pixelados Shorts!",
        "webhooks": ["DISCORD_WEBHOOK"],
        "bluesky": True,
        "threads": True,
    },
    # --- Canales solo para Discord ---
    "UCYk9AH19xF7dtzM9OY7obmA": {
        "mensaje": "¡Nuevo vídeo en el canal!",
        "webhooks": ["DISCORD_WEBHOOK_VRTX"],
        "bluesky": False,
        "threads": False,
    },
    "UCngXjqgH_-42BgtegyzI_-A": {
        "mensaje": "¡Nuevo vídeo en el canal secundario!",
        "webhooks": ["DISCORD_WEBHOOK_VRTX"],
        "bluesky": False,
        "threads": False,
    },
    "UC4MGzV7ahAN1khnzdjp3rkw": {
        "mensaje": "¡Nuevo vídeo en el canal de WarCraft 3!",
        "webhooks": ["DISCORD_WEBHOOK_VRTX"],
        "bluesky": False,
        "threads": False,
    },
}
ARCHIVO = "vistos.json"

_bsky = None  # se inicia solo cuando hace falta


def extraer_hashtags(descripcion):
    vistos, lista = set(), []
    for h in re.findall(r"#\w+", descripcion or ""):
        if h[1:].isdigit() or h.lower() in vistos:
            continue
        vistos.add(h.lower())
        lista.append(h)
    return lista


def publicar_bluesky(v):
    global _bsky
    try:
        if _bsky is None:
            _bsky = Client()
            _bsky.login(os.environ["BSKY_HANDLE"], os.environ["BSKY_APP_PASSWORD"])

        # Texto: título + hashtags (Bluesky admite hasta 300 caracteres)
        elegidos, largo = [], len(v.title) + 2
        for h in extraer_hashtags(v.get("summary", "")):
            if largo + len(h) + 1 > 295:
                break
            elegidos.append(h)
            largo += len(h) + 1

        texto = client_utils.TextBuilder().text(v.title)
        if elegidos:
            texto.text("\n\n")
            for i, h in enumerate(elegidos):
                if i:
                    texto.text(" ")
                texto.tag(h, h[1:])

        # Miniatura que enlaza al vídeo (tarjeta sin título ni descripción)
        thumb = None
        try:
            url_img = v.get("media_thumbnail", [{}])[0].get("url")
            img = requests.get(url_img, timeout=15)
            img.raise_for_status()
            thumb = _bsky.upload_blob(img.content).blob
        except Exception as e:
            print(f"No se pudo subir la miniatura: {e}")

        embed = models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                uri=v.link,
                title="",
                description="",
                thumb=thumb,
            )
        )
        _bsky.send_post(texto, embed=embed)
    except Exception as e:
        print(f"Error publicando en Bluesky: {e}")


def publicar_threads(v):
    base = "https://graph.threads.net/v1.0"
    try:
        user_id = os.environ["THREADS_USER_ID"]
        token = os.environ["THREADS_ACCESS_TOKEN"]

        datos = {
            "media_type": "TEXT",
            "text": v.title,
            "link_attachment": v.link,
            "topic_tag": "videojuegos",
            "access_token": token,
        }

        r = requests.post(f"{base}/{user_id}/threads", data=datos, timeout=20)
        r.raise_for_status()
        contenedor = r.json()["id"]

        time.sleep(5)  # margen entre crear y publicar

        r = requests.post(
            f"{base}/{user_id}/threads_publish",
            data={"creation_id": contenedor, "access_token": token},
            timeout=20,
        )
        r.raise_for_status()
    except requests.HTTPError as e:
        print(f"Error publicando en Threads: {e} | {e.response.text}")
    except Exception as e:
        print(f"Error publicando en Threads: {e}")


def publicar_discord(nombre_secreto, mensaje, link):
    url = os.environ.get(nombre_secreto)
    if not url:
        print(f"Falta el secreto {nombre_secreto}")
        return
    try:
        r = requests.post(url, json={"content": f"{mensaje}\n\n{link}"}, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        codigo = e.response.status_code if e.response is not None else "sin respuesta"
        print(f"Error enviando a {nombre_secreto} (código: {codigo})")


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
            publicar_bluesky(v)
        if cfg.get("threads"):
            publicar_threads(v)
    estado[canal] = sorted(vistos)

with open(ARCHIVO, "w") as f:
    json.dump(estado, f, indent=2)
