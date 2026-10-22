import json
import random

import pytest
import requests

from proyectos import PROYECTOS
from resenas import avisador
from resenas.steam import cargar_resenas
from tests.conftest import FIXTURES, Respuesta

CONSERVADOR = "46111642"
STEAM = json.loads((FIXTURES / "steam_resenas.json").read_text(encoding="utf-8"))   # guardado tal cual de Steam
# Las dos reseñas más nuevas del fixture
INFINITY, HUNDRED_LINE = "1498550", "3014080"


def steam(datos=STEAM, status=200):
    return lambda url, **kw: Respuesta(status, datos)


# ---------------- Lectura de Steam ----------------

def test_lee_todas_las_resenas_del_conservador():
    resenas = cargar_resenas(CONSERVADOR, get=steam())
    assert len(resenas) == 18
    r = resenas[0]
    assert (r.appid, r.juego, r.veredicto, r.veredicto_texto, r.icono) == (
        INFINITY, "Infinity: HexaDome Tactics", "informational", "Informativa", "ℹ️")
    assert r.texto.startswith("La idea del juego es bastante interesante.") and "<" not in r.texto
    assert r.tienda == f"https://store.steampowered.com/app/{INFINITY}/Infinity_HexaDome_Tactics/?curator_clanid={CONSERVADOR}"
    assert r.imagen.endswith("/header.jpg")   # la cabecera grande, no la miniatura de 292×136
    assert r.video == "https://www.youtube.com/watch?v=0PvyyBY6RYw"
    assert resenas[1].veredicto == "recommended" and resenas[1].icono == "👍"


@pytest.mark.parametrize("get", [
    steam(status=503),
    steam({"success": 2}),
    lambda url, **kw: (_ for _ in ()).throw(requests.ConnectionError("sin red")),
])
def test_si_steam_falla_devuelve_none(get):
    assert cargar_resenas(CONSERVADOR, get=get) is None


def test_textos_caben_en_bluesky_y_discord_lleva_el_video():
    for r in cargar_resenas(CONSERVADOR, get=steam()):
        corto, largo = avisador.textos(r, "¡Nueva reseña!", random.Random(1))
        assert len(corto) <= avisador.LIMITE_TEXTO
        assert f"{r.icono} {r.juego} · {r.veredicto_texto}" in corto
        assert r.video in largo and r.video not in corto


def test_hashtags_con_el_nombre_del_juego():
    resenas = {r.appid: r for r in cargar_resenas(CONSERVADOR, get=steam())}
    assert avisador.hashtags(resenas[INFINITY]) == ["#Steam", "#Reseña", "#InfinityHexaDomeTactics"]
    assert avisador.hashtags(resenas["2989180"])[-1] == "#DarwinsParadox"   # «Darwin's Paradox!»


# ---------------- Avisos ----------------

class Red:
    def __init__(self, resultado=True):
        self.publicaciones, self.resultado = [], resultado

    def publicar(self, p):
        self.publicaciones.append(p)
        return self.resultado


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("DISCORD_TEST", "https://discord.test/h")
    discord = []

    def post(url, **kw):
        discord.append(kw["json"]["content"])
        return Respuesta(204)
    monkeypatch.setattr(requests, "post", post)
    ruta, cola = tmp_path / "resenas_vistas.json", tmp_path / "cola_x.json"
    proyectos = {"mp": {"webhooks": ["DISCORD_TEST"], "bluesky": True, "threads": True, "x": True, "web": "yo/web",
                        "resenas": {"conservador": CONSERVADOR, "mensaje": "¡Nueva reseña!"}}}

    def correr(estado=None, datos=STEAM, bluesky=None, threads=None, proyectos=proyectos):
        if estado is not None:
            ruta.write_text(json.dumps(estado), encoding="utf-8")
        bluesky, threads = bluesky or Red(), threads or Red()
        webs = avisador.ejecutar(proyectos=proyectos, ruta=str(ruta), get=steam(datos), bluesky=bluesky,
                                 threads=threads, rng=random.Random(1), ruta_cola_x=str(cola))
        return {"webs": webs, "discord": discord, "bluesky": bluesky.publicaciones, "threads": threads.publicaciones,
                "estado": json.loads(ruta.read_text(encoding="utf-8")),
                "cola": json.loads(cola.read_text(encoding="utf-8")) if cola.exists() else []}
    return correr


def todas_menos(*appids):
    return [r.appid for r in cargar_resenas(CONSERVADOR, get=steam()) if r.appid not in appids]


def test_la_primera_vez_solo_apunta_las_resenas(entorno):
    r = entorno()
    assert r["discord"] == [] and r["bluesky"] == [] and r["threads"] == [] and r["webs"] == []
    assert sorted(r["estado"]["mp"]) == sorted(todas_menos())


def test_avisa_de_las_nuevas_de_la_mas_antigua_a_la_mas_nueva(entorno):
    r = entorno(estado={"mp": todas_menos(INFINITY, HUNDRED_LINE)})
    assert [p.titulo_tarjeta for p in r["bluesky"]] == ["The Hundred Line -Last Defense Academy-",
                                                        "Infinity: HexaDome Tactics"]
    assert len(r["threads"]) == 2 and len(r["discord"]) == 2
    p = r["bluesky"][1]
    assert p.enlace.endswith(f"?curator_clanid={CONSERVADOR}") and p.url_imagen.endswith("/header.jpg")
    assert "¡Nueva reseña!" in p.texto and "#InfinityHexaDomeTactics" in p.hashtags
    assert "Reseña en vídeo: <https://www.youtube.com/watch?v=0PvyyBY6RYw>" in r["discord"][1]
    assert r["discord"][1].endswith(p.enlace)
    assert [e["tipo"] for e in r["cola"]] == ["resena", "resena"]
    assert r["webs"] == ["yo/web"]
    assert INFINITY in r["estado"]["mp"] and HUNDRED_LINE in r["estado"]["mp"]


def test_sin_novedades_no_avisa_ni_reconstruye_la_web(entorno):
    r = entorno(estado={"mp": todas_menos()})
    assert r["discord"] == [] and r["bluesky"] == [] and r["webs"] == []


def test_si_fallan_todas_las_redes_se_reintentara(entorno, monkeypatch):
    monkeypatch.delenv("DISCORD_TEST")
    r = entorno(estado={"mp": todas_menos(INFINITY)}, bluesky=Red(False), threads=Red(False))
    assert INFINITY not in r["estado"]["mp"] and r["webs"] == [] and r["cola"] == []


def test_si_steam_falla_no_se_toca_el_estado(entorno):
    r = entorno(estado={"mp": ["1"]}, datos={"success": 2})
    assert r["estado"] == {"mp": ["1"]} and r["discord"] == []


def test_las_redes_desactivadas_no_publican(entorno):
    proyectos = {"mp": {"webhooks": ["DISCORD_TEST"], "bluesky": True, "threads": True,
                        "resenas": {"conservador": CONSERVADOR, "mensaje": "¡Nueva!", "threads": False}}}
    r = entorno(estado={"mp": todas_menos(INFINITY)}, proyectos=proyectos)
    assert len(r["discord"]) == 1 and len(r["bluesky"]) == 1 and r["threads"] == [] and r["cola"] == []


def test_los_proyectos_sin_resenas_no_consultan_steam(entorno):
    r = entorno(proyectos={"otro": {"webhooks": ["DISCORD_TEST"]}})
    assert r["estado"] == {} and r["discord"] == []


def test_mundos_pixelados_usa_su_conservador_y_avisa_donde_los_videos():
    cfg = avisador.config_de(PROYECTOS["mundospixelados"])
    assert cfg["conservador"] == CONSERVADOR
    assert cfg["webhooks"] == ["DISCORD_WEBHOOK"] and cfg["bluesky"] and cfg["threads"] and cfg["x"]
    assert cfg["web"] == "JoseLuisMD/MP-Website"
    assert not PROYECTOS["vortix"].get("resenas")
