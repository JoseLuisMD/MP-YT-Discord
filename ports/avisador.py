"""Avisa por Discord (canal privado) de los ports que han llegado a la versión 1.0 por primera vez, y de las
versiones nuevas de los que ya estaban en 1.0 o más. Se lanza los sábados por la mañana (workflow ports.yml).

Lee las notificaciones de releases de la cuenta de GitHub (las de los repos que se siguen en «Custom → Releases»;
los ignorados no generan notificaciones), mira el historial de releases de cada repo para saber si es su primera
versión estable ≥1.0, envía el resumen y marca las notificaciones como hechas («Done»). Si el envío falla, no se
marca ni se guarda nada, y la siguiente ejecución lo vuelve a intentar.
"""
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from common.estado import cargar_json, guardar_json

from .versiones import texto_version, version, version_estable

ARCHIVO = "ports_vistos.json"   # {"ultima_ejecucion": ISO, "releases_vistas": [ids], "avisados": {repo: versión}}
MAX_VISTAS = 5000               # ids de releases que se recuerdan (unas 250 por semana)
MARGEN = timedelta(days=1)      # se releen las notificaciones de un día antes de la última ejecución, por si acaso
PRIMERA_ESTABLE = (1, 0, 0)
ZONA = ZoneInfo("Europe/Madrid")
LIMITE_DISCORD = 1900           # Discord admite 2000 caracteres por mensaje; dejamos margen
SIN_VISTAS_PREVIAS = 4          # flags de Discord: SUPPRESS_EMBEDS (sin tarjetas de enlace)


@dataclass
class Port:
    repo: str
    version: str          # la última versión estable de la semana, como la pone el tag («1.3.2», «4.2-E2»…)
    fecha: datetime       # cuándo salió esa versión
    enlace: str           # página de la release
    nuevo: bool           # True si es su primera versión estable ≥1.0
    fecha_1_0: datetime = None   # nuevo: cuándo salió su primera estable ≥1.0
    anterior: str = ""    # no nuevo: la versión estable anterior


def _fecha(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _dia(fecha):
    return fecha.astimezone(ZONA).strftime("%d/%m")


def _id_release(notificacion):
    """El id de la release a la que apunta una notificación (subject.url acaba en /releases/{id})."""
    url = notificacion["subject"].get("url") or ""
    m = re.search(r"/releases/(\d+)$", url)
    return int(m.group(1)) if m else None


def _version_mostrada(release, v):
    """La versión tal como la escribe el tag («v1.3.2» → «1.3.2»), o la reconocida si el tag no la tiene."""
    tag = (release.get("tag_name") or "").strip()
    return re.sub(r"^[vV]\s?", "", tag) if version(tag) else texto_version(v)


def analizar(repo, releases, ids_semana, avisados):
    """El Port de un repo si alguna de sus releases de la semana (`ids_semana`) es estable y ≥1.0, o None."""
    estables = []
    for r in releases:
        v = version_estable(r)
        if v and v >= PRIMERA_ESTABLE and r.get("published_at"):
            estables.append((_fecha(r["published_at"]), v, r))
    estables.sort(key=lambda e: e[0])
    semana = [e for e in estables if e[2]["id"] in ids_semana]
    if not semana:
        return None
    primera_semana = semana[0][0]
    anteriores = [e for e in estables if e[2]["id"] not in ids_semana and e[0] < primera_semana]
    fecha, v, release = semana[-1]
    nuevo = not anteriores and repo not in avisados
    return Port(
        repo=repo, version=_version_mostrada(release, v), fecha=fecha, enlace=release.get("html_url", ""),
        nuevo=nuevo, fecha_1_0=primera_semana if nuevo else None,
        anterior="" if nuevo else (_version_mostrada(anteriores[-1][2], anteriores[-1][1]) if anteriores
                                   else avisados.get(repo, "")),
    )


def mensajes(ports, inicio, fin):
    """Los mensajes de Discord (cada uno de menos de 2000 caracteres): primero los que llegan a la 1.0 por primera
    vez y después las actualizaciones, cada grupo del más reciente al más antiguo."""
    nuevos = sorted((p for p in ports if p.nuevo), key=lambda p: p.fecha, reverse=True)
    otros = sorted((p for p in ports if not p.nuevo), key=lambda p: p.fecha, reverse=True)
    lineas = [f"🎮 **Ports en versión 1.0 o superior** · del {_dia(inicio)} al {_dia(fin)}", ""]
    if not ports:
        lineas.append("Esta semana no ha salido ninguna versión estable 1.0 o superior.")
    if nuevos:
        lineas += [f"🆕 **Llegan a la 1.0 por primera vez ({len(nuevos)})**"]
        for p in nuevos:
            desde = f" · la 1.0 salió el {_dia(p.fecha_1_0)}" if _dia(p.fecha_1_0) != _dia(p.fecha) else ""
            lineas.append(f"• {_dia(p.fecha)} · [{p.repo}]({p.enlace}) → **{p.version}**{desde}")
        lineas.append("")
    if otros:
        lineas += [f"🔄 **Ya estaban en 1.0 o más y han sacado versión nueva ({len(otros)})**"]
        for p in otros:
            antes = f" (antes {p.anterior})" if p.anterior and p.anterior != p.version else ""
            lineas.append(f"• {_dia(p.fecha)} · [{p.repo}]({p.enlace}) → **{p.version}**{antes}")
    return _trocear(lineas)


def _trocear(lineas):
    trozos, actual = [], ""
    for linea in lineas:
        if actual and len(actual) + len(linea) + 1 > LIMITE_DISCORD:
            trozos.append(actual.rstrip())
            actual = ""
        actual += linea + "\n"
    if actual.strip():
        trozos.append(actual.rstrip())
    return trozos


def enviar_discord(textos, post=requests.post):
    """Envía los mensajes al webhook DISCORD_WEBHOOK_PORTS. Devuelve True si se han enviado todos."""
    url = os.environ.get("DISCORD_WEBHOOK_PORTS")
    if not url:
        print("Falta el secreto DISCORD_WEBHOOK_PORTS")
        return False
    for texto in textos:
        try:
            r = post(url, json={"content": texto, "flags": SIN_VISTAS_PREVIAS}, timeout=15)
            r.raise_for_status()
        except requests.RequestException as e:
            codigo = e.response.status_code if e.response is not None else "sin respuesta"
            print(f"Error enviando a DISCORD_WEBHOOK_PORTS (código: {codigo})")
            return False
    return True


def ejecutar(gh, enviar=enviar_discord, simular=False, ahora=None, ruta=ARCHIVO):
    """Una ejecución completa. Devuelve True si ha ido bien (o si se ha simulado)."""
    ahora = ahora or datetime.now(timezone.utc)
    estado = cargar_json(ruta, {})
    ultima = estado.get("ultima_ejecucion")
    vistas = set(estado.get("releases_vistas", []))
    avisados = estado.get("avisados", {})

    desde = (_fecha(ultima) - MARGEN).isoformat().replace("+00:00", "Z") if ultima else None
    notificaciones = gh.notificaciones_de_releases(desde)
    print(f"Notificaciones de releases leídas: {len(notificaciones)}" + (f" (desde {desde})" if desde else ""))

    por_repo = {}
    for n in notificaciones:
        id_ = _id_release(n)
        if id_ and id_ not in vistas:
            por_repo.setdefault(n["repository"]["full_name"], set()).add(id_)

    ports, ids_ok, repos_ok = [], set(), set()
    for repo, ids in sorted(por_repo.items()):
        try:
            releases = gh.releases(repo)
        except requests.RequestException as e:
            print(f"No se pudieron leer las releases de {repo}: {e}")
            continue
        repos_ok.add(repo)
        ids_ok |= ids
        port = analizar(repo, releases, ids, avisados)
        if port:
            ports.append(port)

    inicio = _fecha(ultima) if ultima else min((_fecha(n["updated_at"]) for n in notificaciones), default=ahora)
    textos = mensajes(ports, inicio, ahora)
    print("\n\n".join(textos))
    if simular:
        print(f"\n(Simulación: no se envía nada, no se marcan notificaciones ni se guarda el estado)")
        return True
    if not enviar(textos):
        return False

    hechas = sum(gh.marcar_hecha(n["id"]) for n in notificaciones
                 if n["repository"]["full_name"] in repos_ok or _id_release(n) in vistas)
    print(f"Notificaciones marcadas como hechas: {hechas}")

    for p in ports:
        avisados[p.repo] = p.version
    estado = {
        "ultima_ejecucion": ahora.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "releases_vistas": (sorted(vistas | ids_ok, reverse=True))[:MAX_VISTAS],
        "avisados": dict(sorted(avisados.items())),
    }
    guardar_json(ruta, estado)
    return True
