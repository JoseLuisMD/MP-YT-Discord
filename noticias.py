import feedparser, requests, json, os, re, time, calendar, random, html, unicodedata
from atproto import Client, models

FEEDS = {
    "Vandal": "https://vandal.elespanol.com/xml.cgi",
    "3DJuegos": "https://www.3djuegos.com/feedburner.xml",
    "Hobby Consolas": "https://www.hobbyconsolas.com/rss",
    "VidaExtra": "https://www.vidaextra.com/feedburner.xml",
    "Eurogamer.es": "https://www.eurogamer.es/feed",
}
PALABRAS_CLAVE = [
    "zelda",
    "sonic",
    "mario",
    "resident evil",
    "castlevania",
    "final fantasy",
    "dragon quest",
    "silent hill",
    "nintendo",
    "xbox",
    "playstation",
    "kojima"
]
ARCHIVO = "noticias_publicadas.json"
MAX_EDAD_HORAS = 24      # solo noticias publicadas en las últimas horas
MAX_POR_EJECUCION = 1    # cuántas noticias se publican en cada ejecución
MAX_HISTORIAL = 500      # enlaces recordados para no repetir
MODELOS_LLM = ["gemini-2.5-flash-lite", "gemini-2.5-flash"]  # se prueban en orden
PROMPT = (
    "Resume esta noticia de videojuegos en español en 1 o 2 frases (máximo 250 caracteres). "
    "Usa solo la información del texto, sin inventar datos, sin emojis ni hashtags y con tono neutro. "
    "Responde solo con el resumen.\n\nTítulo: {titulo}\n\nTexto: {texto}"
)

feedparser.USER_AGENT = "Mozilla/5.0 (compatible; MundosPixeladosBot/1.0)"


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


PATRONES = [(k, re.compile(rf"(?<!\w){re.escape(normalizar(k))}(?!\w)")) for k in PALABRAS_CLAVE]


def limpiar_html(texto):
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return re.sub(r"\s+", " ", html.unescape(texto)).strip()


def recortar(texto, maximo):
    if len(texto) <= maximo:
        return texto
    return texto[: maximo - 1].rsplit(" ", 1)[0] + "…"


def fecha_entrada(e):
    t = e.get("published_parsed") or e.get("updated_parsed")
    return calendar.timegm(t) if t else None


def es_reciente(e):
    f = fecha_entrada(e)
    return f is None or time.time() - f <= MAX_EDAD_HORAS * 3600


def coincidencias(texto):
    t = normalizar(texto)
    return [k for k, patron in PATRONES if patron.search(t)]


def contenido(e):
    if e.get("content"):
        return e["content"][0].get("value", "")
    return e.get("summary", "")


def resumir(titulo, texto):
    clave = os.environ.get("GEMINI_API_KEY")
    if clave:
        for modelo in MODELOS_LLM:
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                    headers={"x-goog-api-key": clave, "Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": PROMPT.format(titulo=titulo, texto=texto[:1500])}]}],
                        "generationConfig": {
                            "temperature": 0.3,
                            "maxOutputTokens": 200,
                            "thinkingConfig": {"thinkingBudget": 0},
                        },
                    },
                    timeout=30,
                )
                r.raise_for_status()
                resumen = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if resumen:
                    return recortar(resumen, 270)
            except Exception as e:
                print(f"El modelo {modelo} ha fallado: {e}")
    print("Sin resumen del LLM: se usa el título")
    return recortar(titulo, 270)


def publicar_discord(texto, link):
    url = os.environ.get("DISCORD_WEBHOOK_NOTICIAS")
    if not url:
        print("Falta el secreto DISCORD_WEBHOOK_NOTICIAS")
        return False
    try:
        r = requests.post(url, json={"content": f"{texto}\n\n{link}"}, timeout=15)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        codigo = e.response.status_code if e.response is not None else "sin respuesta"
        print(f"Error enviando a Discord (código: {codigo})")
        return False


def publicar_bluesky(texto, titulo, link):
    try:
        cliente = Client()
        cliente.login(os.environ["BSKY_HANDLE"], os.environ["BSKY_APP_PASSWORD"])
        embed = models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(uri=link, title=titulo, description="")
        )
        cliente.send_post(texto, embed=embed)
        return True
    except Exception as e:
        print(f"Error publicando en Bluesky: {e}")
        return False


def publicar_threads(texto, link):
    base = "https://graph.threads.net/v1.0"
    try:
        user_id = os.environ["THREADS_USER_ID"]
        token = os.environ["THREADS_ACCESS_TOKEN"]
        datos = {
            "media_type": "TEXT",
            "text": texto,
            "link_attachment": link,
            "topic_tag": "videojuegos",
            "access_token": token,
        }
        r = requests.post(f"{base}/{user_id}/threads", data=datos, timeout=20)
        r.raise_for_status()
        contenedor = r.json()["id"]
        time.sleep(5)
        r = requests.post(
            f"{base}/{user_id}/threads_publish",
            data={"creation_id": contenedor, "access_token": token},
            timeout=20,
        )
        r.raise_for_status()
        return True
    except requests.HTTPError as e:
        print(f"Error publicando en Threads: {e} | {e.response.text if e.response is not None else ''}")
        return False
    except Exception as e:
        print(f"Error publicando en Threads: {e}")
        return False


try:
    with open(ARCHIVO, encoding="utf-8") as f:
        publicadas = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    publicadas = []
ya_publicadas = set(publicadas)

# 1. Recoger las noticias recientes y no publicadas de todos los feeds
candidatas, enlaces_vistos = [], set()
for fuente, url in FEEDS.items():
    feed = feedparser.parse(url)
    if not feed.entries:
        print(f"Sin entradas en {fuente}")
        continue
    for e in feed.entries:
        link = (e.get("link") or "").split("#")[0]
        titulo = limpiar_html(e.get("title", ""))
        if not link or not titulo or link in ya_publicadas or link in enlaces_vistos or not es_reciente(e):
            continue
        enlaces_vistos.add(link)
        candidatas.append({
            "fuente": fuente,
            "titulo": titulo,
            "link": link,
            "texto": limpiar_html(contenido(e)),
            "fecha": fecha_entrada(e) or 0,
        })

print(f"Noticias candidatas: {len(candidatas)}")

# 2. Elegir: primero las que coinciden con palabras clave, y si no hay, una al azar
if candidatas:
    for c in candidatas:
        c["coincide"] = coincidencias(c["titulo"] + " " + c["texto"])
    con_match = sorted(
        (c for c in candidatas if c["coincide"]),
        key=lambda c: (-len(c["coincide"]), -c["fecha"]),
    )
    if con_match:
        elegidas = con_match[:MAX_POR_EJECUCION]
    else:
        elegidas = random.sample(candidatas, min(MAX_POR_EJECUCION, len(candidatas)))

    # 3. Resumir y publicar
    for c in elegidas:
        motivo = f"coincide con {c['coincide']}" if c["coincide"] else "aleatoria (sin coincidencias)"
        print(f"Elegida [{c['fuente']}] {c['titulo']} -> {motivo}")
        resumen = resumir(c["titulo"], c["texto"])
        texto = f"{resumen}\n\n📰 {c['fuente']}"
        resultados = [
            publicar_discord(texto, c["link"]),
            publicar_bluesky(texto, c["titulo"], c["link"]),
            publicar_threads(texto, c["link"]),
        ]
        if any(resultados):
            publicadas.append(c["link"])

with open(ARCHIVO, "w", encoding="utf-8") as f:
    json.dump(publicadas[-MAX_HISTORIAL:], f, indent=2, ensure_ascii=False)
