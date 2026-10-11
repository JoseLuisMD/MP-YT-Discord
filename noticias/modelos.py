from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Noticia:
    fuente: str
    titulo: str
    enlace: str
    texto: str
    fecha: Optional[float] = None       # marca de tiempo UTC; None si el feed no la trae
    url_imagen: Optional[str] = None
    idioma: str = "es"
    imagen_en_threads: bool = False     # ver Fuente.imagen_en_threads
    coincide: list = field(default_factory=list)  # palabras clave que coinciden
