# MP-YT-Discord

Automatizaciones de Mundos Pixelados que se ejecutan en GitHub Actions (disparadas desde cron-job.org):

- **`videos`**: avisa en Discord, Bluesky y Threads de los vídeos nuevos de los canales de YouTube.
- **`noticias`**: cada hora publica una noticia de videojuegos (resumida con Gemini) en Discord, Bluesky y Threads.

## Estructura

```
common/                 código compartido
  publicadores.py       Discord, Bluesky y Threads (misma interfaz: publicar(Publicacion) -> bool)
  texto.py              normalizar, limpiar_html, recortar, extraer_hashtags
  estado.py             leer y guardar los JSON de «ya publicado»
videos/
  canales.py            SOLO DATOS: canales, mensajes, webhooks y opciones
  avisador.py           lógica de los avisos      estado.py  formato de vistos.json
noticias/
  config.py             palabras clave, límites, modelos y prompt de Gemini
  fuentes.py            lista de webs (clase Fuente): nombre, URL, idioma, secciones excluidas
  imagenes.py           cómo se encuentra la imagen de cada web (+ og:image como último recurso)
  seleccion.py          coincidencias con palabras clave, elección y recencia
  resumen.py            resumen y hashtags con Gemini
  proceso.py            orquestación
tests/                  pruebas y copias de feeds reales (tests/fixtures)
```

## Ejecutar

```bash
pip install -r requirements.txt
python -m videos      # avisos de vídeos
python -m noticias    # noticias
```

Las variables de entorno son las mismas de siempre (`DISCORD_WEBHOOK`, `BSKY_HANDLE`, `GEMINI_API_KEY`...).
Los estados siguen en la raíz: `vistos.json` y `noticias_publicadas.json`.

## Pruebas

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Cómo se añade…

- **Un canal de YouTube**: una entrada en `videos/canales.py`.
- **Una web de noticias**: una `Fuente` en `noticias/fuentes.py`. Si su feed pone la imagen en un sitio raro,
  se escribe un extractor en `noticias/imagenes.py` y se pasa como `extraer_imagen=`.
  Si Threads muestra su tarjeta sin imagen, pon `imagen_en_threads=True`: se publica con la imagen adjunta
  y el enlace en el texto (si la imagen falla, se vuelve a la tarjeta normal).
  Después, guarda una copia de su feed en `tests/fixtures/` y añade una prueba.
- **Una red social nueva**: una clase con un método `publicar(self, p: Publicacion) -> bool` en
  `common/publicadores.py` y añadirla a la lista de publicadores en `noticias/proceso.py` o `videos/avisador.py`.
