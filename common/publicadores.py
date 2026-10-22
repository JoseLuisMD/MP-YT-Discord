"""Publicadores compartidos por los avisos de vídeos y las noticias.

Cada publicador implementa la misma interfaz: recibe una `Publicacion` y devuelve
True si ha publicado y False si ha fallado (nunca lanza excepciones). Para añadir
una red nueva basta con crear otra clase con un método `publicar`.
"""
import hashlib
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol

import requests
from atproto import Client, client_utils, models

from common.estado import cargar_json, guardar_json

COLA_X = "cola_x.json"   # publicaciones pendientes de publicar a mano en X (ver ColaX)
MAX_COLA_X = 50          # entradas que se guardan de cada tipo (vídeos y noticias)


@dataclass
class Publicacion:
    texto: str                              # texto principal del post
    enlace: str                             # enlace al vídeo o a la noticia
    titulo_tarjeta: str = ""                # título de la tarjeta de enlace (Bluesky)
    url_imagen: Optional[str] = None        # miniatura de la tarjeta (Bluesky)
    hashtags: list = field(default_factory=list)  # etiquetas clicables (Bluesky)
    imagen_en_threads: bool = False         # Threads: adjuntar url_imagen en vez de usar la tarjeta del enlace
    imagen_en_discord: bool = False         # Discord: enviar url_imagen como imagen del mensaje
    # Discord, Threads con imagen y X: escribir `enlace` al final del texto. False si no se quiere a la vista
    # (p. ej. las reseñas: solo se ve el enlace al Mentor de Steam, que va en enlaces_extra)
    enlace_en_texto: bool = True
    # Otros enlaces, al final del texto: [(etiqueta, url)]. En Bluesky la etiqueta es el enlace (no cuenta la URL);
    # en el resto se escribe «etiqueta: url»
    enlaces_extra: list = field(default_factory=list)

    def texto_con_enlaces(self, plantilla="{etiqueta}: {url}"):
        """El texto con los enlaces extra debajo, cada uno en su párrafo."""
        return "\n\n".join([self.texto] + [plantilla.format(etiqueta=e, url=u) for e, u in self.enlaces_extra])


class Publicador(Protocol):
    nombre: str

    def publicar(self, publicacion: Publicacion) -> bool: ...


class Discord:
    nombre = "Discord"

    def __init__(self, secreto):
        self.secreto = secreto  # nombre de la variable de entorno con la URL del webhook

    def publicar(self, p):
        url = os.environ.get(self.secreto)
        if not url:
            print(f"Falta el secreto {self.secreto}")
            return False
        try:
            # <url>: Discord no genera vista previa de los enlaces extra, solo del principal
            texto = p.texto_con_enlaces("{etiqueta}: <{url}>")
            mensaje = {"content": f"{texto}\n\n{p.enlace}" if p.enlace_en_texto else texto}
            if p.imagen_en_discord and p.url_imagen:
                mensaje["embeds"] = [{"image": {"url": p.url_imagen}}]
            r = requests.post(url, json=mensaje, timeout=15)
            r.raise_for_status()
            return True
        except requests.RequestException as e:
            codigo = e.response.status_code if e.response is not None else "sin respuesta"
            print(f"Error enviando a {self.secreto} (código: {codigo})")
            return False


class Bluesky:
    nombre = "Bluesky"
    LIMITE_TEXTO = 295        # Bluesky admite 300 caracteres; dejamos margen
    LIMITE_IMAGEN = 1_000_000  # Bluesky rechaza imágenes de más de ~1 MB

    def __init__(self):
        self._cliente = None

    def _conectar(self):
        if self._cliente is None:
            cliente = Client()
            cliente.login(os.environ["BSKY_HANDLE"], os.environ["BSKY_APP_PASSWORD"])
            self._cliente = cliente
        return self._cliente

    def _texto(self, p):
        """Texto del post con los enlaces extra y los hashtags como enlaces y etiquetas clicables."""
        builder = client_utils.TextBuilder().text(p.texto)
        for etiqueta, url in p.enlaces_extra:
            builder.text("\n\n")
            builder.link(etiqueta, url)
        elegidos = hashtags_de(p, self.LIMITE_TEXTO)
        if elegidos:
            builder.text("\n\n")
            for i, h in enumerate(elegidos):
                if i:
                    builder.text(" ")
                builder.tag(h, h[1:])
        return builder

    def _subir_imagen(self, cliente, url_imagen):
        """Descarga la imagen y la sube a Bluesky. Devuelve el blob o None."""
        if not url_imagen:
            return None
        try:
            img = requests.get(url_imagen, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            img.raise_for_status()
            tipo = img.headers.get("Content-Type", "").split(";")[0].lower()
            if not tipo.startswith("image/"):
                raise ValueError(f"La URL no devuelve una imagen: {tipo or 'tipo desconocido'}")
            if len(img.content) > self.LIMITE_IMAGEN:
                raise ValueError("La imagen supera el límite de 1 MB")
            return cliente.upload_blob(img.content).blob
        except Exception as e:
            print(f"No se pudo subir la miniatura ({url_imagen}): {e}")
            return None

    def publicar(self, p):
        try:
            cliente = self._conectar()
            builder = self._texto(p)
            thumb = self._subir_imagen(cliente, p.url_imagen)
            embed = models.AppBskyEmbedExternal.Main(
                external=models.AppBskyEmbedExternal.External(
                    uri=p.enlace, title=p.titulo_tarjeta, description="", thumb=thumb
                )
            )
            cliente.send_post(text=builder, embed=embed)
            print(f"Publicado en Bluesky: {p.titulo_tarjeta or p.texto[:60]}")
            return True
        except Exception as e:
            print(f"Error publicando en Bluesky: {e}")
            return False


class Threads:
    nombre = "Threads"
    BASE = "https://graph.threads.net/v1.0"

    def __init__(self, tema="videojuegos", espera=5, intentos_imagen=6):
        self.tema = tema
        self.espera = espera  # segundos entre crear el contenedor y publicarlo
        self.intentos_imagen = intentos_imagen  # comprobaciones del estado de un contenedor con imagen

    def _esperar_imagen(self, contenedor, token):
        """Threads procesa la imagen antes de poder publicarla: espera a que el contenedor esté FINISHED."""
        for _ in range(self.intentos_imagen):
            time.sleep(self.espera)
            r = requests.get(f"{self.BASE}/{contenedor}", params={"fields": "status,error_message", "access_token": token}, timeout=20)
            r.raise_for_status()
            estado = r.json().get("status")
            if estado == "FINISHED":
                return
            if estado in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Threads no pudo procesar la imagen: {r.json().get('error_message', estado)}")
        raise RuntimeError("Threads no terminó de procesar la imagen a tiempo")

    def _publicar(self, user_id, token, datos):
        r = requests.post(f"{self.BASE}/{user_id}/threads", data={**datos, "topic_tag": self.tema, "access_token": token}, timeout=20)
        r.raise_for_status()
        contenedor = r.json()["id"]
        if datos["media_type"] == "IMAGE":
            self._esperar_imagen(contenedor, token)
        else:
            time.sleep(self.espera)
        r = requests.post(f"{self.BASE}/{user_id}/threads_publish", data={"creation_id": contenedor, "access_token": token}, timeout=20)
        r.raise_for_status()

    def publicar(self, p):
        try:
            user_id = os.environ["THREADS_USER_ID"]
            token = os.environ["THREADS_ACCESS_TOKEN"]
            texto = p.texto_con_enlaces()
            if p.imagen_en_threads and p.url_imagen:
                # Imagen adjuntada por nosotros y enlace simple en el texto (sin tarjeta); la imagen no es
                # clicable, así que una mano señala el enlace
                con_enlace = f"{texto}\n\n👉 {p.enlace}" if p.enlace_en_texto else texto
                try:
                    self._publicar(user_id, token, {"media_type": "IMAGE", "image_url": p.url_imagen, "text": con_enlace})
                    return True
                except Exception as e:
                    print(f"Threads con imagen falló ({_detalle(e)}); se publica con la tarjeta del enlace")
            self._publicar(user_id, token, {"media_type": "TEXT", "text": texto, "link_attachment": p.enlace})
            return True
        except Exception as e:
            print(f"Error publicando en Threads: {_detalle(e)}")
            return False


class ColaX:
    """No publica: apunta la publicación en cola_x.json para publicarla a mano en X desde el panel
    (repo MP-Backend), porque la API de X es de pago. No cuenta como publicación real."""
    nombre = "Cola de X"

    def __init__(self, tipo, proyecto, ruta=COLA_X, maximo=MAX_COLA_X):
        self.tipo = tipo          # "video", "noticia" o "resena"
        self.proyecto = proyecto
        self.ruta = ruta
        self.maximo = maximo      # entradas que se guardan de cada tipo

    @staticmethod
    def texto(p):
        """El texto de Bluesky (texto, enlaces extra y hashtags) con el enlace al final. No se recorta: si no cabe
        en X, se recorta a mano antes de publicar."""
        partes = [p.texto_con_enlaces()]
        hashtags = hashtags_de(p, Bluesky.LIMITE_TEXTO)
        if hashtags:
            partes.append(" ".join(hashtags))
        if p.enlace_en_texto:
            partes.append(p.enlace)
        return "\n\n".join(partes)

    def publicar(self, p):
        try:
            cola = cargar_json(self.ruta, [])   # la más nueva primero
            id_ = hashlib.sha1(p.enlace.encode("utf-8")).hexdigest()[:12]
            if any(e.get("id") == id_ for e in cola):
                return True   # ya estaba apuntada
            cola.insert(0, {
                "id": id_,
                "tipo": self.tipo,
                "proyecto": self.proyecto,
                "titulo": p.titulo_tarjeta,
                "enlace": p.enlace,
                "imagen": p.url_imagen,
                "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "texto": self.texto(p),
            })
            vistas, recortada = Counter(), []
            for e in cola:
                vistas[e.get("tipo")] += 1
                if vistas[e.get("tipo")] <= self.maximo:
                    recortada.append(e)
            guardar_json(self.ruta, recortada)
            print(f"Apuntado para X: {p.titulo_tarjeta or p.texto[:60]}")
            return True
        except Exception as e:
            print(f"Error apuntando en la cola de X: {e}")
            return False


def hashtags_de(p, limite):
    """Hashtags válidos de la publicación que caben tras el texto (y una línea en blanco) sin pasar de `limite`."""
    elegidos = []
    largo = len(p.texto) + sum(2 + len(etiqueta) for etiqueta, _ in p.enlaces_extra) + 2
    for h in p.hashtags or []:
        h = str(h).strip()
        if not re.fullmatch(r"#\w+", h):
            continue
        if largo + len(h) + 1 > limite:
            break
        elegidos.append(h)
        largo += len(h) + 1
    return elegidos


def _detalle(e):
    if isinstance(e, requests.HTTPError) and e.response is not None:
        return f"{e} | {e.response.text}"
    return str(e)
