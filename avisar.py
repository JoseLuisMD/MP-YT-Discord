import feedparser, requests, json, os, re, time
from atproto import Client, client_utils, models

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
ARCHIVO = "vistos.json"

_bsky = None


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
        elegidos = []
        largo = len(v.title) + 2
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
            if url_img:
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

        time.sleep(5) # margen entre crear y publicar

        r = requests.post(
            f"{base}/{user_id}/threads_publish",
            data={"creation_id": contenedor, "access_token": token},
            timeout=20,
        )
        r.raise_for_status()
    except requests.HTTPError as e:
        print(f"Error publicando en Threads: {e} | {e.response.text if e.response is not None else ''}")
    except Exception as e:
        print(f"Error publicando en Threads: {e}")


def publicar_discord(nombre_secreto, mensaje, link, incluirShorts):
    if not incluirShorts and "shorts" in link.lower():
        return # este canal no quiere shorts en Discord
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


def cargar_estado():
    try:
        with open(ARCHIVO, encoding="utf-8") as f:
            datos = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        datos = {}
    estado = {}
    for canal, contenido in datos.items():
        # Compatibilidad con el formato antiguo: "CANAL": ["video1", "video2"]
        if isinstance(contenido, list):
            estado[canal] = {
                "normal": set(contenido),
                "miembros": set(),
                "normal_inicializado": True,
                "miembros_inicializado": False,
            }
        # Formato nuevo: "CANAL": {"normal": [...], "miembros": [...]}
        elif isinstance(contenido, dict):
            estado[canal] = {
                "normal": set(contenido.get("normal", [])),
                "miembros": set(contenido.get("miembros", [])),
                "normal_inicializado": "normal" in contenido,
                "miembros_inicializado": "miembros" in contenido,
            }
    return estado


def procesar_feed(canal, cfg, estado, miembros=False):
    if miembros:
        # Solo se llama si existe mensajeMiembros.
        playlist_id = "UUMF" + canal[2:]
        url_feed = f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
        clave = "miembros"
        mensaje = cfg["mensajeMiembros"]
    else:
        url_feed = f"https://www.youtube.com/feeds/videos.xml?channel_id={canal}"
        clave = "normal"
        mensaje = cfg["mensaje"]

    print(f"Consultando feed {'de miembros' if miembros else 'normal'}: {canal}")
    feed = feedparser.parse(url_feed)

    # No modificar el estado si el feed no devuelve entradas.
    if not feed.entries:
        print(f"Feed vacío o sin entradas: {url_feed}")
        return

    vistos = estado[canal][clave]
    # Cada feed tiene su propia primera ejecución.
    inicializado = estado[canal][f"{clave}_inicializado"]

    for v in reversed(feed.entries):
        video_id = v.get("yt_videoid")
        if not video_id:
            continue
        if video_id in vistos:
            continue
        # Registrar el vídeo incluso en la primera ejecución.
        vistos.add(video_id)
        if not inicializado:
            continue
        if miembros:
            # Los vídeos exclusivos se notifican únicamente por Discord.
            for webhook in cfg["webhooks"]:
                publicar_discord(webhook, mensaje, v.link, cfg["incluirShorts"])
        else:
            # Comportamiento habitual para vídeos públicos.
            for webhook in cfg["webhooks"]:
                publicar_discord(webhook, mensaje, v.link, cfg["incluirShorts"])
            if cfg["bluesky"]:
                publicar_bluesky(v)
            if cfg.get("threads"):
                publicar_threads(v)

    estado[canal][f"{clave}_inicializado"] = True


estado = cargar_estado()

for canal, cfg in CANALES.items():
    if canal not in estado:
        estado[canal] = {
            "normal": set(),
            "miembros": set(),
            "normal_inicializado": False,
            "miembros_inicializado": False,
        }
    # Procesar siempre el feed público.
    procesar_feed(canal, cfg, estado, miembros=False)
    # Consultar el feed de miembros solo si hay mensaje configurado.
    if cfg.get("mensajeMiembros"):
        procesar_feed(canal, cfg, estado, miembros=True)

# Guardar ambos historiales en el mismo archivo.
estado_guardar = {}
for canal, datos in estado.items():
    cfg = CANALES.get(canal, {})
    contenido = {"normal": sorted(datos["normal"])}
    if cfg.get("mensajeMiembros"):
        contenido["miembros"] = sorted(datos["miembros"])
    estado_guardar[canal] = contenido

with open(ARCHIVO, "w", encoding="utf-8") as f:
    json.dump(estado_guardar, f, indent=2, ensure_ascii=False)
