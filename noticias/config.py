"""Ajustes del bot de noticias. Aquí se cambia lo que se publica y cómo se resume.
Qué proyectos publican noticias, con qué webs y dónde se define en proyectos.py."""

MAX_EDAD_HORAS = 24      # solo noticias publicadas en las últimas horas
MAX_POR_EJECUCION = 1    # cuántas noticias se publican en cada ejecución
MAX_HISTORIAL = 500      # enlaces recordados para no repetir
MAX_WEB = 30             # noticias que se guardan para la web (archivo `web` de las noticias del proyecto)
# Noticias repetidas: la misma noticia publicada por otra web. Se comparan las palabras significativas de los
# títulos con los de las noticias publicadas en las últimas HORAS_RECIENTES. Se considera la misma si comparten
# al menos MIN_PALABRAS_COMUNES y esas son al menos MIN_PROPORCION_COMUN de las del título más corto.
# Están altos a propósito para no descartar noticias distintas del mismo juego: bájalos si se cuelan repetidas.
HORAS_RECIENTES = 48
MIN_PALABRAS_COMUNES = 5
MIN_PROPORCION_COMUN = 0.5
USER_AGENT = "Mozilla/5.0 (compatible; MundosPixeladosBot/1.0)"

TEMA_THREADS = "videojuegos"

# Emojis que acompañan al nombre de la web; en cada publicación se elige uno al azar
EMOJIS_FUENTE = ["📰", "🗞️", "📝", "✍️", "✏️", "🖊️", "🖋️", "✒️", "📖", "📓", "📔", "📒", "📑", "📄", "📃", "🗒️"]

# Modelos de Gemini: al empezar se piden a la API los Flash-Lite estables (sin preview ni exp) y se prueban
# del más nuevo al más antiguo. Esta lista es el respaldo: se prueba después, o sola si la consulta falla.
MODELOS_LLM = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]
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
