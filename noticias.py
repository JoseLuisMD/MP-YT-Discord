import feedparser, requests, json, os, re, time, calendar, random, html, unicodedata
from atproto import Client, client_utils, models
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

FEEDS = {
    "Vandal": "https://vandal.elespanol.com/xml.cgi",
    "3DJuegos": "https://www.3djuegos.com/feedburner.xml",
    "Hobby Consolas": "https://www.hobbyconsolas.com/rss",
    "VidaExtra": "https://www.vidaextra.com/feedburner.xml",
    "Eurogamer.es": "https://www.eurogamer.es/feed",
    "GenerationAmiga": "https://www.generationamiga.com/{aaaa}/{mm}/feed/",
}
FUENTES_EN_INGLES = {"GenerationAmiga"}  # el mismo nombre que uses en FEEDS
RUTAS_EXCLUIDAS = ("/tv-series/", "/manga-anime/", "/3djuegos-trivia/", "/streamers/") # no son de videojuegos
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
    "kojima"
]
ARCHIVO = "noticias_publicadas.json"
MAX_EDAD_HORAS = 24      # solo noticias publicadas en las últimas horas
MAX_POR_EJECUCION = 1    # cuántas noticias se publican en cada ejecución
MAX_HISTORIAL = 500      # enlaces recordados para no repetir
MODELOS_LLM = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]
PROMPT = (
    "Analiza esta noticia de videojuegos y responde exclusivamente con un JSON válido "
    "con dos campos: resumen y hashtags. "
    "El resumen debe estar escrito en español de España (castellano) y tener un máximo de 200 caracteres. "
    "Usa 1 o 2 frases, tono neutro y solo información del texto, sin inventar datos ni emojis. "
    "Conserva los nombres originales de juegos, sagas, consolas y empresas. "
    "Genera exactamente 5 hashtags relevantes, específicos y sin duplicados, "
    "con el prefijo # y sin espacios ni tildes. "
    "Los hashtags deben ser breves y adecuados para Twitter o Bluesky. "
    "No incluyas hashtags dentro del resumen. "
    'Formato: {{"resumen":"...","hashtags":["#...","#...","#...","#...","#..."]}}'
    "\n\nTítulo: {titulo}\n\nTexto: {texto}"
)

feedparser.USER_AGENT = "Mozilla/5.0 (compatible; MundosPixeladosBot/1.0)"


cliente_bsky = None


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


def imagen_del_feed(e):
    """Busca la imagen de una entrada en los sitios habituales de un feed."""
    # 1. Campos estándar: media:thumbnail, media:content y enclosures de tipo imagen
    for campo in ("media_thumbnail", "media_content"):
        for m in e.get(campo) or []:
            if m.get("url"):
                return m["url"]
    for enc in e.get("enclosures") or []:
        if "image" in (enc.get("type") or "") and enc.get("href"):
            return enc["href"]
    # 2. Imágenes dentro del HTML (algunas webs, como Vandal, solo las ponen ahí)
    texto = e.get("summary", "")
    if e.get("content"):
        texto += " " + e["content"][0].get("value", "")
    # 2a. Vandal marca su imagen principal con el enlace "#imagen1"
    m = re.search(r'#imagen1["\'][^>]*>\s*<img[^>]+src=["\']([^"\']+)', texto)
    if m:
        return html.unescape(m.group(1))
    # 2b. En el resto, la primera imagen que no sea un icono o un píxel
    for src in re.findall(r'<img[^>]+src=["\']([^"\']+)', texto):
        if src.startswith("http") and not re.search(r"pixel|1x1|spacer|\.gif", src, re.I):
            return html.unescape(src)
    return None


def imagen_og(link):
    """Último recurso: la imagen que la propia web declara para compartir (og:image)."""
    try:
        r = requests.get(link, headers={"User-Agent": "Mozilla/5.0 (compatible; MundosPixeladosBot/1.0)"}, timeout=15)
        r.raise_for_status()
        cabecera = r.text[:200_000]
        for patron in (
            r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)',
        ):
            m = re.search(patron, cabecera, re.I)
            if m:
                return urljoin(link, html.unescape(m.group(1)))
    except Exception as ex:
        print(f"No se pudo leer la imagen de la página ({link}): {ex}")
    return None


def contenido(e):
    if e.get("content"):
        return e["content"][0].get("value", "")
    return e.get("summary", "")


def resumir(titulo, texto, ingles=False):
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        print("Falta la variable GEMINI_API_KEY")
        return None if ingles else (recortar(titulo, 270), [])

    errores_transitorios = {429, 500, 502, 503, 504}
    prompt = PROMPT.format(titulo=titulo, texto=(texto or "")[:1500])

    for modelo in MODELOS_LLM:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

        for intento in range(3):
            try:
                respuesta = requests.post(
                    url,
                    headers={"x-goog-api-key": clave, "Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
                    },
                    timeout=45,
                )

                if respuesta.status_code == 404:
                    print(f"Modelo {modelo} no disponible (404). Probando el siguiente.")
                    break

                if respuesta.status_code in errores_transitorios:
                    if intento < 2:
                        espera = min(2 ** (intento + 1), 16)
                        print(f"Gemini HTTP {respuesta.status_code} ({modelo}). Reintento en {espera}s.")
                        time.sleep(espera)
                        continue
                    print(f"Gemini sigue fallando con HTTP {respuesta.status_code} ({modelo}).")
                    break

                if respuesta.status_code != 200:
                    print(f"Error Gemini HTTP {respuesta.status_code} ({modelo}): {respuesta.text[:500]}")
                    break

                datos = respuesta.json()
                candidatos = datos.get("candidates") or []
                if not candidatos:
                    print(f"Gemini no devolvió candidatos ({modelo}).")
                    break
                
                partes = candidatos[0].get("content", {}).get("parts", [])
                contenido = "".join(p.get("text", "") for p in partes).strip()
                
                try:
                    contenido = re.sub(r"^```(?:json)?\s*|\s*```$", "", contenido, flags=re.I)
                    resultado = json.loads(contenido)
                    resumen = limpiar_html(resultado.get("resumen", ""))
                    hashtags = resultado.get("hashtags", [])
                
                    if not isinstance(hashtags, list):
                        hashtags = []
                
                    hashtags = list(dict.fromkeys(
                        h for h in (
                            re.sub(r"[^#\w]", "", str(x).replace(" ", ""))
                            for x in hashtags
                        )
                        if re.fullmatch(r"#[A-Za-z0-9_]+", h)
                    ))[:5]
                
                    if resumen:
                        return recortar(resumen, 200), hashtags
                
                    print(f"Gemini devolvió un resumen vacío ({modelo}).")
                    break
                
                except (ValueError, TypeError, AttributeError) as e:
                    print(f"Respuesta JSON inválida de Gemini ({modelo}): {e}")
                    break

                print(f"Gemini devolvió una respuesta sin texto ({modelo}).")
                break

            except requests.RequestException as e:
                print(f"Error de conexión con Gemini ({modelo}, intento {intento + 1}): {e}")
                if intento < 2:
                    time.sleep(min(2 ** (intento + 1), 16))

            except (ValueError, KeyError, TypeError) as e:
                print(f"Respuesta inesperada de Gemini ({modelo}): {e}")
                break

    if ingles:
        print("No se pudo resumir la noticia en inglés; se omite.")
        return None

    print("Gemini no disponible. Se utiliza el título original.")
    return recortar(titulo, 270), []


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



def publicar_bluesky(texto, titulo, link, url_imagen=None, hashtags=None):
    global cliente_bsky
    
    try:
        if cliente_bsky is None:
            cliente_bsky = Client()
            cliente_bsky.login(os.environ["BSKY_HANDLE"], os.environ["BSKY_APP_PASSWORD"])
        # Construir el texto y añadir hashtags como etiquetas clicables.
        builder = client_utils.TextBuilder().text(texto)
        elegidos = []
        largo = len(texto)

        for h in hashtags or []:
            h = str(h).strip()
            if not re.fullmatch(r"#[A-Za-z0-9_]+", h):
                continue
            if largo + len(h) + 1 > 295:
                break
            elegidos.append(h)
            largo += len(h) + 1

        if elegidos:
            builder.text("\n\n")
            for i, h in enumerate(elegidos):
                if i:
                    builder.text(" ")
                builder.tag(h, h[1:])
        # Descargar y subir la imagen para la tarjeta del enlace.
        thumb = None
        
        if url_imagen:
            try:
                img = requests.get(url_imagen, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
                img.raise_for_status()
                tipo = img.headers.get("Content-Type", "").split(";")[0].lower()
    
                if not tipo.startswith("image/"):
                    raise ValueError(f"La URL no devuelve una imagen: {tipo or 'tipo desconocido'}")

                if len(img.content) > 1_000_000:
                    raise ValueError("La imagen supera el límite de 1 MB")
                    
                thumb = cliente_bsky.upload_blob(img.content).blob
                
            except Exception as e:
                print(f"No se pudo subir la miniatura ({url_imagen}): {e}")
        # Crear la tarjeta del enlace, con miniatura si se ha podido subir.
        embed = models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(uri=link, title=titulo, description="", thumb=thumb)
        )
        # Publicar en Bluesky.
        cliente_bsky.send_post(text=builder, embed=embed)
        print(f"Publicado en Bluesky: {titulo}")
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
        if not link or not titulo or link in ya_publicadas or link in enlaces_vistos or not es_reciente(e) or any(r in link for r in RUTAS_EXCLUIDAS):
            continue
        enlaces_vistos.add(link)
        url_imagen = imagen_del_feed(e)
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
        resultado = resumir(c["titulo"], c["texto"], ingles)
        if resultado is None:
            continue
        resumen, hashtags = resultado
        texto = f"{resumen}\n\n📰 {c['fuente']}"
        url_imagen = c.get("url_imagen") or imagen_og(c["link"])
        resultados = [
            publicar_discord(texto, c["link"]),
            publicar_bluesky(texto, c["titulo"], c["link"], url_imagen, hashtags),
            publicar_threads(texto, c["link"]),
        ]
        if any(resultados):
            publicadas.append(c["link"])

with open(ARCHIVO, "w", encoding="utf-8") as f:
    json.dump(publicadas[-MAX_HISTORIAL:], f, indent=2, ensure_ascii=False)
