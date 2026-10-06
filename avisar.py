import feedparser, requests, json, os

CANALES = {
    "UCLD3BqL4n2GKmitkEQGCoAQ": "¡Nuevo vídeo en Mundos Pixelados!",
    "UCb3jFYgTbBLjDDOlZiD-2kg": "¡Nuevo short en Mundos Pixelados Shorts!",
}
WEBHOOK = os.environ["DISCORD_WEBHOOK"]
ARCHIVO = "vistos.json"

try:
    with open(ARCHIVO) as f:
        estado = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    estado = {}

for canal, mensaje in CANALES.items():
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
        r = requests.post(
            WEBHOOK,
            json={"content": f"{mensaje}\n\n{v.link}"},
            timeout=15,
        )
        r.raise_for_status()
    estado[canal] = sorted(vistos)

with open(ARCHIVO, "w") as f:
    json.dump(estado, f, indent=2)
