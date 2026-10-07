import feedparser, requests, json, os

CANALES = {
    "UCLD3BqL4n2GKmitkEQGCoAQ": {
        "mensaje": "¡Nuevo vídeo en Mundos Pixelados!",
        "webhooks": ["DISCORD_WEBHOOK"],
    },
    "UCb3jFYgTbBLjDDOlZiD-2kg": {
        "mensaje": "¡Nuevo short en Mundos Pixelados Shorts!",
        "webhooks": ["DISCORD_WEBHOOK"],
    },
    # Ejemplo de un canal nuevo avisando a dos servidores:
    # "UC_ID_DEL_NUEVO_CANAL": {
    #     "mensaje": "¡Nuevo vídeo en NOMBRE!",
    #     "webhooks": ["DISCORD_WEBHOOK", "DISCORD_WEBHOOK_SERVIDOR2"],
    # },
}
ARCHIVO = "vistos.json"

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
            url = os.environ.get(nombre)
            if not url:
                print(f"Falta el secreto {nombre}")
                continue
            try:
                r = requests.post(
                    url,
                    json={"content": f"{cfg['mensaje']}\n\n{v.link}"},
                    timeout=15,
                )
                r.raise_for_status()
            except requests.RequestException as e:
                print(f"Error enviando a {nombre}: {e}")
    estado[canal] = sorted(vistos)

with open(ARCHIVO, "w") as f:
    json.dump(estado, f, indent=2)
