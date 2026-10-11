"""Publicadores compartidos por los avisos de vídeos y las noticias.

Cada publicador implementa la misma interfaz: recibe una `Publicacion` y devuelve
True si ha publicado y False si ha fallado (nunca lanza excepciones). Para añadir
una red nueva basta con crear otra clase con un método `publicar`.
"""
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol

import requests
from atproto import Client, client_utils, models


@dataclass
class Publicacion:
    texto: str                              # texto principal del post
    enlace: str                             # enlace al vídeo o a la noticia
    titulo_tarjeta: str = ""                # título de la tarjeta de enlace (Bluesky)
    url_imagen: Optional[str] = None        # miniatura de la tarjeta (Bluesky)
    hashtags: list = field(default_factory=list)  # etiquetas clicables (Bluesky)


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
            r = requests.post(url, json={"content": f"{p.texto}\n\n{p.enlace}"}, timeout=15)
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
        """Texto del post con los hashtags añadidos como etiquetas clicables."""
        builder = client_utils.TextBuilder().text(p.texto)
        elegidos = []
        largo = len(p.texto) + 2
        for h in p.hashtags or []:
            h = str(h).strip()
            if not re.fullmatch(r"#\w+", h):
                continue
            if largo + len(h) + 1 > self.LIMITE_TEXTO:
                break
            elegidos.append(h)
            largo += len(h) + 1
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

    def __init__(self, tema="videojuegos", espera=5):
        self.tema = tema
        self.espera = espera  # segundos entre crear el contenedor y publicarlo

    def publicar(self, p):
        try:
            user_id = os.environ["THREADS_USER_ID"]
            token = os.environ["THREADS_ACCESS_TOKEN"]
            datos = {
                "media_type": "TEXT",
                "text": p.texto,
                "link_attachment": p.enlace,
                "topic_tag": self.tema,
                "access_token": token,
            }
            r = requests.post(f"{self.BASE}/{user_id}/threads", data=datos, timeout=20)
            r.raise_for_status()
            contenedor = r.json()["id"]
            time.sleep(self.espera)
            r = requests.post(
                f"{self.BASE}/{user_id}/threads_publish",
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
