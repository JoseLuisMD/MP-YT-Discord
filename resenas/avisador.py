"""Avisa de las reseñas nuevas del Conservador de Steam de cada proyecto en Discord, Bluesky y Threads
(y las apunta para X). Se lanza una vez al día (workflow resenas.yml), a la hora que diga cron-job.org."""
import random
import re

from common.estado import cargar_json, guardar_json
from common.publicadores import COLA_X, Bluesky, ColaX, Discord, Publicacion, Threads
from common.texto import recortar
from proyectos import PROYECTOS
from videos.canales import EMOJIS_AVISO

from .steam import cargar_resenas

ARCHIVO = "resenas_vistas.json"   # {proyecto: [appids ya avisados]}
MAX_VISTAS = 200                  # Steam devuelve las 24 últimas
LIMITE_TEXTO = Bluesky.LIMITE_TEXTO


def textos(resena, mensaje, rng=random):
    """(texto para Bluesky, Threads y X, texto para Discord). El de las redes se recorta para que quepa en Bluesky;
    el de Discord va completo y con el enlace al vídeo de la reseña."""
    cabecera = f"{rng.choice(EMOJIS_AVISO)} {mensaje}\n\n{resena.icono} {resena.juego} · {resena.veredicto_texto}\n\n"
    corto = cabecera + f"«{recortar(resena.texto, LIMITE_TEXTO - len(cabecera) - 2)}»"
    largo = cabecera + f"«{resena.texto}»"
    if resena.video:
        largo += f"\n\n🎬 Reseña en vídeo: <{resena.video}>"   # <...>: Discord no le añade otra vista previa
    return corto, largo


def hashtags(resena):
    """#Steam, #Reseña y el nombre del juego: «Infinity: HexaDome Tactics» → #InfinityHexaDomeTactics."""
    juego = "".join(p[:1].upper() + p[1:] for p in re.findall(r"[^\W_]+", re.sub(r"['’]", "", resena.juego)))
    return ["#Steam", "#Reseña"] + ([f"#{juego}"] if juego and not juego.isdigit() else [])


def avisar(resena, cfg, proyecto, bluesky, threads, rng=random, ruta_cola_x=COLA_X):
    """Publica la reseña. True si al menos una red la ha publicado."""
    corto, largo = textos(resena, cfg["mensaje"], rng)
    resultados = [Discord(w).publicar(Publicacion(texto=largo, enlace=resena.tienda)) for w in cfg["webhooks"]]
    p = Publicacion(texto=corto, enlace=resena.tienda, titulo_tarjeta=resena.juego, url_imagen=resena.imagen,
                    hashtags=hashtags(resena))
    if cfg.get("bluesky"):
        resultados.append(bluesky.publicar(p))
    if cfg.get("threads"):
        resultados.append(threads.publicar(p))
    publicada = any(resultados)
    if publicada and cfg.get("x"):
        ColaX("resena", proyecto, ruta_cola_x).publicar(p)
    return publicada


def config_de(proyecto):
    """Ajustes de las reseñas de un proyecto: los de su bloque `resenas` y, si no los pone, los del proyecto."""
    cfg = proyecto["resenas"]
    return {
        "conservador": cfg["conservador"],
        "mensaje": cfg["mensaje"],
        **{clave: cfg.get(clave, proyecto.get(clave, por_defecto))
           for clave, por_defecto in (("webhooks", []), ("bluesky", False), ("threads", False), ("x", False), ("web", None))},
    }


def ejecutar(proyectos=None, ruta=ARCHIVO, get=None, bluesky=None, threads=None, rng=random, ruta_cola_x=COLA_X):
    """Avisa de las reseñas nuevas de cada proyecto. Devuelve los repos de las webs que hay que reconstruir.

    La primera vez de cada proyecto solo se apuntan las reseñas que ya hay, sin avisar. Si todas las redes fallan
    con una reseña, no se apunta: se reintentará en la próxima ejecución."""
    proyectos = PROYECTOS if proyectos is None else proyectos
    bluesky = bluesky or Bluesky()
    threads = threads or Threads()
    estado = cargar_json(ruta, {})
    webs = set()
    for nombre, proyecto in proyectos.items():
        if not proyecto.get("resenas"):
            continue
        cfg = config_de(proyecto)
        print(f"--- Reseñas de Steam de {nombre}")
        resenas = cargar_resenas(cfg["conservador"], **({"get": get} if get else {}))
        if resenas is None:
            continue
        inicializado = nombre in estado
        vistas = estado.setdefault(nombre, [])
        for r in reversed(resenas):   # de la más antigua a la más nueva
            if r.appid in vistas:
                continue
            if inicializado:
                print(f"Reseña nueva: {r.juego} ({r.veredicto_texto})")
                if not avisar(r, cfg, nombre, bluesky, threads, rng, ruta_cola_x):
                    continue
                if cfg["web"]:
                    webs.add(cfg["web"])
            vistas.append(r.appid)
        if not inicializado:
            print(f"Primera ejecución: {len(vistas)} reseñas apuntadas sin avisar")
        estado[nombre] = vistas[-MAX_VISTAS:]
    guardar_json(ruta, estado)
    return sorted(webs)
