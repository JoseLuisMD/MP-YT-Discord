# MP-YT-Discord

Automatizaciones de Mundos Pixelados y VortiX que se ejecutan en GitHub Actions (disparadas desde cron-job.org).
Cada **proyecto** (`proyectos.py`) tiene sus canales de YouTube, sus redes, su web y, si quiere, sus noticias:

- **`videos`**: avisa en Discord, Bluesky y Threads de los vídeos nuevos de los canales de YouTube.
- **`noticias`**: cada hora publica una noticia de videojuegos (resumida con Gemini) por cada proyecto con noticias.
- **`resenas`**: cada día a las 21:00 avisa en Discord, Bluesky y Threads de las reseñas nuevas del Conservador de
  Steam de cada proyecto que lo tenga.

## Estructura

```
proyectos.py            SOLO DATOS: proyectos, sus canales, redes, web y noticias
common/                 código compartido
  publicadores.py       Discord, Bluesky y Threads (misma interfaz: publicar(Publicacion) -> bool)
  texto.py              normalizar, limpiar_html, recortar, extraer_hashtags
  estado.py             leer y guardar los JSON de «ya publicado»
  webs.py               pasa al workflow las webs que hay que reconstruir
videos/
  canales.py            despliega los canales de proyectos.py (cada canal hereda lo de su proyecto)
  avisador.py           lógica de los avisos      estado.py  formato de vistos.json
noticias/
  config.py             límites, modelos y prompt de Gemini
  palabras.py           palabras clave por niveles y sus contadores
  fuentes.py            lista de webs (clase Fuente): nombre, URL, idioma, secciones excluidas
  imagenes.py           cómo se encuentra la imagen de cada web (+ og:image como último recurso)
  seleccion.py          coincidencias por niveles, elección, recencia y noticias repetidas
  resumen.py            resumen y hashtags con Gemini
  proceso.py            orquestación (una ejecución por proyecto con noticias)
resenas/
  steam.py              lee las reseñas del Conservador de Steam (el mismo JSON que usa la web)
  avisador.py           lógica de los avisos y formato de resenas_vistas.json
tests/                  pruebas; en tests/fixtures, los feeds de noticias guardados tal cual de cada web
```

## Ejecutar

```bash
pip install -r requirements.txt
python -m videos      # avisos de vídeos
python -m noticias    # noticias
python -m resenas     # reseñas de Steam
```

Las variables de entorno son las mismas de siempre (`DISCORD_WEBHOOK`, `BSKY_HANDLE`, `GEMINI_API_KEY`...).
Los estados viven en la rama **`estado`** (no en `main`), para que los commits automáticos del bot no se mezclen con
el código: `vistos.json` (vídeos de todos los canales), `resenas_vistas.json` (reseñas de Steam ya avisadas), `cola_x.json` (lo pendiente de publicar a mano en X desde el
panel de MP-Backend) y, por cada proyecto con noticias, los archivos que indica `proyectos.py` (Mundos Pixelados:
`noticias_publicadas.json`, `palabras_clave.json`, `noticias_web.json`, las últimas noticias con título, resumen e
imagen para su web, y `noticias_recientes.json`, los títulos de las últimas 48 h para no publicar la misma noticia
desde otra web). Los workflows traen esa rama a la carpeta `estado/`, ejecutan el bot dentro y suben los cambios
(`.github/estado.sh`). Para ejecutarlo a mano con el estado real, haz lo mismo: `bash .github/estado.sh traer` y
`cd estado && PYTHONPATH=.. python -m videos`.
Con un vídeo o una noticia nuevos se reconstruye la web del proyecto (clave `web`): se lanza su workflow `web.yml`
con el secreto `WEB_TOKEN`.
Las palabras clave tienen 3 niveles `{"palabra": veces}`, donde `veces` es cuántas noticias publicadas ha ayudado
a elegir. El bot ordena las palabras y actualiza los contadores en cada publicación.

## Pruebas

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Con [uv](https://docs.astral.sh/uv/) (descarga Python 3.12 si no lo tienes):

```bash
uv venv --python 3.12
uv pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest      # en Linux/macOS: .venv/bin/python -m pytest
```

## Dependencias

Las que usa el bot se escriben en `requirements.in` (y las de las pruebas en `requirements-dev.in`).
`requirements.txt` y `requirements-dev.txt` las fijan todas, también las indirectas, a una versión exacta:
no se editan a mano, se generan con uv. Para actualizarlas (o tras añadir una en un `.in`):

```bash
uv pip compile requirements.in --universal --python-version 3.12 -o requirements.txt --upgrade
uv pip compile requirements-dev.in --universal --python-version 3.12 -o requirements-dev.txt --upgrade
```

Después, pasar las pruebas y subir los `.txt`.

## Cómo se añade…

- **Una palabra clave**: una entrada `"palabra": 0` en su nivel del archivo de palabras del proyecto, en la rama
  `estado` (en GitHub: cambia a la rama `estado` y edita el archivo ahí). Mejor justo después de que publique una
  noticia, porque el bot actualiza los contadores cada hora.
- **Un canal de YouTube**: una entrada en los `canales` de su proyecto en `proyectos.py`.
- **Un proyecto**: un bloque en `proyectos.py`. Si usa secretos nuevos (otro webhook de Discord), añádelos al `env:`
  del workflow que los use. Para que se reconstruya su web, añade su repo al token guardado en `WEB_TOKEN`.
- **Una web de noticias**: una `Fuente` en `noticias/fuentes.py` y su nombre en las `fuentes` del proyecto.
  Si su feed pone la imagen en un sitio raro, se escribe un extractor en `noticias/imagenes.py` y se pasa como `extraer_imagen=`.
  Igual con el texto: si la noticia no está en el primer bloque de contenido, se pasa una función como `extraer_texto=`
  (p. ej. `texto_pcgamer` en `noticias/fuentes.py`).
  Si Threads muestra su tarjeta sin imagen, pon `imagen_en_threads=True`: se publica con la imagen adjunta
  y el enlace en el texto (si la imagen falla, se vuelve a la tarjeta normal).
  Después, guarda su feed completo desde el navegador (Ctrl+S) en `tests/fixtures/` y añade una prueba.
- **Una red social nueva**: una clase con un método `publicar(self, p: Publicacion) -> bool` en
  `common/publicadores.py` y añadirla a la lista de publicadores en `noticias/proceso.py` o `videos/avisador.py`.
