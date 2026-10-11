"""Ajustes del bot de noticias. Aquí se cambia lo que se publica y cómo se resume."""

ARCHIVO = "noticias_publicadas.json"
MAX_EDAD_HORAS = 24      # solo noticias publicadas en las últimas horas
MAX_POR_EJECUCION = 1    # cuántas noticias se publican en cada ejecución
MAX_HISTORIAL = 500      # enlaces recordados para no repetir
USER_AGENT = "Mozilla/5.0 (compatible; MundosPixeladosBot/1.0)"

WEBHOOK_NOTICIAS = "DISCORD_WEBHOOK_NOTICIAS"  # secreto con el webhook de Discord
TEMA_THREADS = "videojuegos"

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
    "kojima",
    "konami",
    "capcom",
    "xenoblade",
    "monolith",
    "fire emblem",
    "trails",
    "metroidvania",
    "starcraft",
    "warcraft",
    "diablo"
]

MODELOS_LLM = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]  # se prueban en orden
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
