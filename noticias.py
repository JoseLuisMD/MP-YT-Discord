import feedparser, requests, json, os, re, time, calendar, random, html, unicodedata
from atproto import Client, models
from datetime import datetime, timedelta, timezone

FEEDS = {
    "Vandal": "https://vandal.elespanol.com/xml.cgi",
    "3DJuegos": "https://www.3djuegos.com/feedburner.xml",
    "Hobby Consolas": "https://www.hobbyconsolas.com/rss",
    "VidaExtra": "https://www.vidaextra.com/feedburner.xml",
    "Eurogamer.es": "https://www.eurogamer.es/feed",
    "GenerationAmiga": "https://www.generationamiga.com/{aaaa}/{mm}/feed/",
}
FUENTES_EN_INGLES = {"GenerationAmiga"}  # el mismo nombre que uses en FEEDS
PALABRAS_CLAVE = [
    "zelda",
    "sonic",
    "mario",
    "metroid",
    "resident evil",
    "castlevania",
    "final fantasy",
    "dragon quest",
    "silent hill",
    "nintendo",
    "xbox",
    "playstation",
    "steam",
    "kojima"
]
ARCHIVO = "noticias_publicadas.json"
MAX_EDAD_HORAS = 24      # solo noticias publicadas en las últimas horas
MAX_POR_EJECUCION = 1    # cuántas noticias se publican en cada ejecución
MAX_HISTORIAL = 500      # enlaces recordados para no repetir
MODELOS_LLM = ["gemini-flash-latest", "gemini-1.5-flash"]
PROMPT = (
    "Resume esta noticia de videojuegos en 1 o 2 frases (máximo 250 caracteres). "
    "Escribe SIEMPRE en español de España (castellano), aunque el texto original esté en inglés u otro idioma. "
    "Deja en su idioma original los nombres de juegos, sagas, consolas y empresas. "
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


def urls_del_feed(url):
    """Si la URL lleva {aaaa} y {mm}, se sustituyen por el año y el mes (y el mes anterior a primeros de mes)."""
    if "{aaaa}" not in url:
        return [url]
    ahora = datetime.now(timezone.utc)
    antes = ahora - timedelta(hours=MAX_EDAD_HORAS)
    meses = sorted({(ahora.year, ahora.month), (antes.year, antes.month)})
    return [url.format(aaaa=a, mm=f"{m:02d}") for a, m in meses]


def contenido(e):
    if e.get("content"):
        return e["content"][0].get("value", "")
    return e.get("summary", "")


def resumir(titulo, texto, ingles=False):
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
                        },
                    },
                    timeout=30,
                )
                # Si da un error 404, r.raise_for_status() lanzará la excepción, 
                # pero antes imprimiremos la respuesta exacta de Google
                if r.status_code != 200:
                    print(f"Error de la API de Gemini (Código {r.status_code}) para {modelo}: {r.text}")
                
                r.raise_for_status()
                resumen = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if resumen:
                    return recortar(resumen, 270)
            except Exception as e:
                print(f"El modelo {modelo} ha fallado: {e}")
    if ingles:
        print("Sin resumen del LLM y la fuente está en inglés: no se publica")
        return None
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


def publicar_bluesky(texto, titulo, link, url_imagen=None):
    try:
        cliente = Client()
        cliente.login(os.environ["BSKY_HANDLE"], os.environ["BSKY_APP_PASSWORD"])
        
        blob = None
        # Si el feed nos dio una imagen de portada, la descargamos y subimos a Bluesky
        if url_imagen:
            try:
                resp_img = requests.get(url_imagen, timeout=10)
                if resp_img.status_code == 200:
                    # Subimos el archivo binario de la imagen a los servidores de Bluesky
                    blob = cliente.upload_blob(resp_img.content).blob
            except Exception as img_err:
                print(f"No se pudo procesar la imagen para Bluesky: {img_err}")

        # Configuramos la tarjeta externa
        external_builder = models.AppBskyEmbedExternal.External(
            uri=link,
            title=titulo,
            description="Haz clic para leer la noticia completa."
        )
        
        # SI logramos subir el blob de la imagen, se lo asignamos a la tarjeta
        if blob:
            external_builder.thumb = blob
            
        embed = models.AppBskyEmbedExternal.Main(external=external_builder)
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
    entradas = []
    for u in urls_del_feed(url):
        entradas += feedparser.parse(u).entries
    if not entradas:
        print(f"Sin entradas en {fuente}")
        continue
    for e in entradas:
        link = (e.get("link") or "").split("#")[0]
        titulo = limpiar_html(e.get("title", ""))
        if not link or not titulo or link in ya_publicadas or link in enlaces_vistos or not es_reciente(e):
            continue
        enlaces_vistos.add(link)
        url_imagen = None
        if e.get("enclosure"):
            url_imagen = e["enclosure"].get("url")
        elif e.get("media_content"):
            url_imagen = e["media_content"][0].get("url")
        elif e.get("links"):
            # Buscar en los enlaces adjuntos si hay alguna imagen
            for l in e["links"]:
                if "image" in l.get("type", ""):
                    url_imagen = l.get("href")
                    break
        candidatas.append({
            "fuente": fuente,
            "titulo": titulo,
            "link": link,
            "texto": limpiar_html(contenido(e)),
            "fecha": fecha_entrada(e) or 0,
            "url_imagen": url_imagen,
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
        ingles = c["fuente"] in FUENTES_EN_INGLES
        resumen = resumir(c["titulo"], c["texto"], ingles)
        if resumen is None:
            continue
        texto = f"{resumen}\n\n📰 {c['fuente']}"
        resultados = [
            publicar_discord(texto, c["link"]),
            publicar_bluesky(texto, c["titulo"], c["link"], c.get("url_imagen")),
            publicar_threads(texto, c["link"]),
        ]
        if any(resultados):
            publicadas.append(c["link"])

with open(ARCHIVO, "w", encoding="utf-8") as f:
    json.dump(publicadas[-MAX_HISTORIAL:], f, indent=2, ensure_ascii=False)
