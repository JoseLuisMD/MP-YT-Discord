import json

import pytest
import requests

from common.publicadores import Publicacion
from tests.conftest import Respuesta
from videos.avisador import ejecutar
from videos.canales import EMOJIS_AVISO

CANAL = "UCYk9AH19xF7dtzM9OY7obmA"
FEED_CANAL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CANAL}"
FEED_MIEMBROS = f"https://www.youtube.com/feeds/videos.xml?playlist_id=UUMF{CANAL[2:]}"

# Vídeos del fixture youtube_canal.xml, de más nuevo a más antiguo
VIDEO_NUEVO, SHORT_1, VIDEO_2, SHORT_2 = "XX6h-So_bSA", "lgBi27X5LiY", "07SY2-66Vzk", "Zy_4SytrVlA"
TODOS = [VIDEO_NUEVO, SHORT_1, VIDEO_2, SHORT_2]


def config(**cambios):
    cfg = {"mensaje": "¡Nuevo vídeo!", "webhooks": ["DISCORD_TEST"], "incluirShorts": True,
           "bluesky": False, "threads": False}
    cfg.update(cambios)
    return {CANAL: cfg}


class Registro:
    """Anota lo que se publica en cada red."""

    def __init__(self):
        self.discord, self.bluesky, self.threads = [], [], []

    class _Red:
        def __init__(self, lista):
            self.lista = lista

        def publicar(self, p):
            self.lista.append(p)
            return True


@pytest.fixture
def entorno(monkeypatch, cargar, tmp_path):
    monkeypatch.setenv("DISCORD_TEST", "https://discord.test/h")
    registro = Registro()
    monkeypatch.setattr(requests, "post", lambda url, **kw: (registro.discord.append(kw["json"]["content"]), Respuesta(204))[1])
    feeds = {FEED_CANAL: cargar("youtube_canal.xml"), FEED_MIEMBROS: cargar("youtube_miembros.xml")}
    ruta = tmp_path / "vistos.json"

    def correr(cfg, estado=None, max_vistos=100):
        if estado is not None:
            ruta.write_text(json.dumps(estado), encoding="utf-8")
        ejecutar(canales=cfg, ruta_estado=str(ruta), parse=lambda url: feeds[url],
                 bluesky=Registro._Red(registro.bluesky), threads=Registro._Red(registro.threads), max_vistos=max_vistos)
        return json.loads(ruta.read_text(encoding="utf-8"))

    return registro, correr, feeds


def test_la_primera_ejecucion_solo_registra_sin_avisar(entorno):
    registro, correr, _ = entorno
    estado = correr(config(mensajeMiembros="Miembros"))
    assert registro.discord == []
    assert sorted(estado[CANAL]["normal"]) == sorted(TODOS)
    assert sorted(estado[CANAL]["miembros"]) == ["Cbm0tNFJdho", "IeKToohx5kc"]


def test_un_video_nuevo_se_avisa_por_discord(entorno):
    registro, correr, _ = entorno
    correr(config(), {CANAL: {"normal": TODOS[1:]}})
    assert registro.discord == [f"¡Nuevo vídeo!\n\nhttps://www.youtube.com/watch?v={VIDEO_NUEVO}"]
    assert registro.bluesky == [] and registro.threads == []


def test_no_se_vuelve_a_avisar_de_lo_ya_visto(entorno):
    registro, correr, _ = entorno
    correr(config(), {CANAL: {"normal": TODOS}})
    assert registro.discord == []


def test_shorts_desactivados_no_se_avisan_pero_se_registran(entorno):
    registro, correr, _ = entorno
    estado = correr(config(incluirShorts=False), {CANAL: {"normal": [VIDEO_NUEVO, VIDEO_2, SHORT_2]}})
    assert registro.discord == []
    assert SHORT_1 in estado[CANAL]["normal"]


def test_shorts_activados_si_se_avisan(entorno):
    registro, correr, _ = entorno
    correr(config(incluirShorts=True), {CANAL: {"normal": [VIDEO_NUEVO, VIDEO_2, SHORT_2]}})
    assert registro.discord == [f"¡Nuevo vídeo!\n\nhttps://www.youtube.com/shorts/{SHORT_1}"]


def test_video_nuevo_tambien_va_a_bluesky_y_threads_si_el_canal_los_tiene(entorno):
    registro, correr, _ = entorno
    correr(config(bluesky=True, threads=True), {CANAL: {"normal": TODOS[1:]}})
    assert len(registro.bluesky) == 1 and len(registro.threads) == 1
    b = registro.bluesky[0]
    emoji, resto = b.texto.split(" ", 1)
    assert emoji in EMOJIS_AVISO
    assert resto == "¡Nuevo vídeo!\n\nREVELAN TODO sobre VIKINGOS en Age of Empires 4"
    assert b.hashtags == ["#ageofempires", "#aoe4", "#vortix"]
    assert b.url_imagen == "https://i1.ytimg.com/vi/XX6h-So_bSA/hqdefault.jpg"
    assert b.titulo_tarjeta == ""
    assert registro.threads[0].texto == b.texto


def test_video_de_miembros_solo_se_avisa_por_discord_con_su_mensaje(entorno):
    registro, correr, _ = entorno
    cfg = config(mensajeMiembros="¡Vídeo para miembros!", bluesky=True, threads=True)
    correr(cfg, {CANAL: {"normal": TODOS, "miembros": ["Cbm0tNFJdho"]}})
    assert registro.discord == ["¡Vídeo para miembros!\n\nhttps://www.youtube.com/watch?v=IeKToohx5kc"]
    assert registro.bluesky == [] and registro.threads == []


def test_el_feed_de_miembros_tiene_su_propia_primera_ejecucion(entorno):
    registro, correr, _ = entorno
    estado = correr(config(mensajeMiembros="Miembros"), {CANAL: {"normal": TODOS}})
    assert registro.discord == []  # solo se registran los de miembros
    assert sorted(estado[CANAL]["miembros"]) == ["Cbm0tNFJdho", "IeKToohx5kc"]


def test_sin_mensaje_de_miembros_no_se_consulta_ese_feed(entorno):
    _, correr, feeds = entorno
    del feeds[FEED_MIEMBROS]  # si se consultara, la prueba fallaría con KeyError
    estado = correr(config(), {CANAL: {"normal": TODOS}})
    assert "miembros" not in estado[CANAL]


def test_el_formato_antiguo_del_estado_se_entiende(entorno):
    registro, correr, _ = entorno
    estado = correr(config(), {CANAL: TODOS[1:]})   # antes: una lista de IDs
    assert registro.discord == [f"¡Nuevo vídeo!\n\nhttps://www.youtube.com/watch?v={VIDEO_NUEVO}"]
    assert sorted(estado[CANAL]["normal"]) == sorted(TODOS)


def test_un_feed_vacio_no_cambia_el_estado(entorno):
    registro, correr, feeds = entorno

    class Vacio:
        entries = []
    feeds[FEED_CANAL] = Vacio()
    estado = correr(config(), {CANAL: {"normal": ["a"]}})
    assert estado[CANAL]["normal"] == ["a"] and registro.discord == []


def test_si_falta_el_secreto_del_webhook_no_se_rompe(entorno, monkeypatch):
    registro, correr, _ = entorno
    monkeypatch.delenv("DISCORD_TEST")
    estado = correr(config(), {CANAL: {"normal": TODOS[1:]}})
    assert registro.discord == [] and VIDEO_NUEVO in estado[CANAL]["normal"]


def test_se_guardan_en_orden_de_llegada_con_el_mas_nuevo_al_final(entorno):
    _, correr, _ = entorno
    estado = correr(config(), {CANAL: {"normal": []}})
    assert estado[CANAL]["normal"] == list(reversed(TODOS))


def test_solo_se_recuerdan_los_ultimos_y_nunca_los_que_siguen_en_el_feed(entorno):
    registro, correr, _ = entorno
    antiguos = [f"viejo{i}" for i in range(10)]
    # Estado heredado en orden alfabético: los del feed están mezclados con los antiguos
    estado = correr(config(), {CANAL: {"normal": sorted(antiguos + TODOS)}}, max_vistos=6)
    assert registro.discord == []
    assert len(estado[CANAL]["normal"]) == 6
    assert estado[CANAL]["normal"][-4:] == list(reversed(TODOS))   # los del feed se conservan


def test_tras_recortar_no_se_repite_ningun_aviso(entorno):
    registro, correr, _ = entorno
    correr(config(), {CANAL: {"normal": [f"viejo{i}" for i in range(50)] + TODOS}}, max_vistos=5)
    correr(config(), max_vistos=5)
    assert registro.discord == []


def test_el_emoji_de_aviso_cambia_entre_videos(entorno):
    registro, correr, _ = entorno
    correr(config(bluesky=True), {CANAL: {"normal": []}})   # 4 vídeos nuevos de golpe
    correr(config(bluesky=True), {CANAL: {"normal": []}})
    emojis = {p.texto.split(" ", 1)[0] for p in registro.bluesky}
    assert len(registro.bluesky) == 8 and len(emojis) > 1 and emojis <= set(EMOJIS_AVISO)


def test_discord_no_lleva_emoji_ni_titulo(entorno):
    registro, correr, _ = entorno
    correr(config(bluesky=True, threads=True), {CANAL: {"normal": TODOS[1:]}})
    assert registro.discord == [f"¡Nuevo vídeo!\n\nhttps://www.youtube.com/watch?v={VIDEO_NUEVO}"]


def test_los_shorts_en_threads_adjuntan_la_portada_vertical(entorno):
    registro, correr, _ = entorno
    correr(config(bluesky=True, threads=True), {CANAL: {"normal": [VIDEO_NUEVO, VIDEO_2, SHORT_2]}})
    t = registro.threads[0]
    assert t.imagen_en_threads is True and t.enlace == f"https://www.youtube.com/shorts/{SHORT_1}"
    assert t.url_imagen == (f"https://images.weserv.nl/?url=i.ytimg.com/vi/{SHORT_1}/maxresdefault.jpg"
                            "&w=405&h=720&fit=cover&a=center&output=jpg")
    assert registro.bluesky[0].imagen_en_threads is False   # Bluesky sigue igual


def test_los_videos_normales_en_threads_siguen_con_la_tarjeta(entorno):
    registro, correr, _ = entorno
    correr(config(threads=True), {CANAL: {"normal": TODOS[1:]}})
    assert registro.threads[0].imagen_en_threads is False and registro.threads[0].url_imagen is None
