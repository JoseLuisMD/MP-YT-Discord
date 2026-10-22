import json

import pytest
import requests
from atproto_client.models.blob_ref import BlobRef, IpldLink
from atproto_core.cid import CID

from common import publicadores
from common.publicadores import Bluesky, ColaX, Discord, Publicacion, Threads
from tests.conftest import Respuesta


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK", "https://discord.test/hook")
    monkeypatch.setenv("BSKY_HANDLE", "yo.bsky.social")
    monkeypatch.setenv("BSKY_APP_PASSWORD", "clave")
    monkeypatch.setenv("THREADS_USER_ID", "42")
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "token")
    monkeypatch.setattr(publicadores.time, "sleep", lambda s: None)


# ---------------- Discord ----------------
def test_discord_envia_texto_y_enlace(monkeypatch):
    enviados = []
    monkeypatch.setattr(requests, "post", lambda url, **kw: (enviados.append((url, kw["json"])), Respuesta(204))[1])
    assert Discord("DISCORD_WEBHOOK").publicar(Publicacion("¡Nuevo vídeo!", "https://y/1")) is True
    assert enviados == [("https://discord.test/hook", {"content": "¡Nuevo vídeo!\n\nhttps://y/1"})]


def test_discord_sin_secreto_devuelve_false(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK")
    assert Discord("DISCORD_WEBHOOK").publicar(Publicacion("a", "b")) is False


def test_discord_con_error_http_devuelve_false_sin_mostrar_la_url(monkeypatch, capsys):
    monkeypatch.setattr(requests, "post", lambda url, **kw: Respuesta(500))
    assert Discord("DISCORD_WEBHOOK").publicar(Publicacion("a", "b")) is False
    salida = capsys.readouterr().out
    assert "500" in salida and "discord.test" not in salida


# ---------------- Bluesky ----------------
BLOB = BlobRef(mime_type="image/jpeg", size=10,
               ref=IpldLink(link=str(CID.decode("bafkreibme22gw2h7y2h7tg2fhqotaqjucnbc24deqo72b6mkl2egezxhvy"))))


class ClienteFalso:
    publicaciones = []
    subidas = []
    login_falla = False

    def login(self, handle, clave):
        if ClienteFalso.login_falla:
            raise RuntimeError("login rechazado")

    def upload_blob(self, datos):
        ClienteFalso.subidas.append(datos)
        return type("Subida", (), {"blob": BLOB})()

    def send_post(self, text, embed):
        ClienteFalso.publicaciones.append((text, embed))


@pytest.fixture
def bsky(monkeypatch):
    ClienteFalso.publicaciones, ClienteFalso.subidas, ClienteFalso.login_falla = [], [], False
    monkeypatch.setattr(publicadores, "Client", ClienteFalso)
    monkeypatch.setattr(requests, "get", lambda url, **kw: Respuesta(
        200, cabeceras={"Content-Type": "image/jpeg; charset=binary"}, contenido=b"imagen"))
    return ClienteFalso


def etiquetas(builder):
    return [f.features[0].tag for f in builder.build_facets()]


def test_bluesky_publica_texto_hashtags_clicables_y_tarjeta_con_miniatura(bsky):
    p = Publicacion("Título del vídeo", "https://y/1", titulo_tarjeta="", url_imagen="https://i/x.jpg",
                    hashtags=["#aoe4", "#vortix"])
    assert Bluesky().publicar(p) is True
    texto, embed = bsky.publicaciones[0]
    assert texto.build_text() == "Título del vídeo\n\n#aoe4 #vortix"
    assert etiquetas(texto) == ["aoe4", "vortix"]
    assert embed.external.uri == "https://y/1" and embed.external.thumb == BLOB
    assert bsky.subidas == [b"imagen"]


def test_bluesky_la_tarjeta_lleva_el_titulo_que_se_le_pasa(bsky):
    Bluesky().publicar(Publicacion("Resumen", "https://n/1", titulo_tarjeta="Título de la noticia"))
    assert bsky.publicaciones[0][1].external.title == "Título de la noticia"


def test_bluesky_respeta_el_limite_de_caracteres(bsky):
    p = Publicacion("x" * 250, "https://n/1", hashtags=["#" + "a" * 20] * 5)
    Bluesky().publicar(p)
    assert len(bsky.publicaciones[0][0].build_text()) <= 300


def test_bluesky_ignora_hashtags_invalidos(bsky):
    Bluesky().publicar(Publicacion("Texto", "https://n/1", hashtags=["sin-almohadilla", "#con espacio", "#ok"]))
    assert etiquetas(bsky.publicaciones[0][0]) == ["ok"]


def test_bluesky_si_la_imagen_pesa_mas_de_1mb_publica_sin_miniatura(bsky, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, **kw: Respuesta(
        200, cabeceras={"Content-Type": "image/jpeg"}, contenido=b"x" * 1_100_000))
    assert Bluesky().publicar(Publicacion("T", "https://n/1", url_imagen="https://i/grande.jpg")) is True
    assert bsky.publicaciones[0][1].external.thumb is None and bsky.subidas == []


def test_bluesky_si_la_url_no_es_una_imagen_publica_sin_miniatura(bsky, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, **kw: Respuesta(200, cabeceras={"Content-Type": "text/html"}))
    Bluesky().publicar(Publicacion("T", "https://n/1", url_imagen="https://i/pagina"))
    assert bsky.publicaciones[0][1].external.thumb is None


def test_bluesky_sin_imagen_no_descarga_nada(bsky, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: pytest.fail("no debería descargar"))
    assert Bluesky().publicar(Publicacion("T", "https://n/1")) is True


def test_bluesky_si_falla_el_login_devuelve_false(bsky):
    bsky.login_falla = True
    assert Bluesky().publicar(Publicacion("T", "https://n/1")) is False


def test_bluesky_sin_credenciales_devuelve_false(bsky, monkeypatch):
    monkeypatch.delenv("BSKY_HANDLE")
    assert Bluesky().publicar(Publicacion("T", "https://n/1")) is False


# ---------------- Threads ----------------
def test_threads_crea_el_contenedor_y_lo_publica(monkeypatch):
    llamadas = []

    def falso(url, **kw):
        llamadas.append((url, kw["data"]))
        return Respuesta(200, {"id": "contenedor-1"})
    monkeypatch.setattr(requests, "post", falso)
    assert Threads(tema="videojuegos").publicar(Publicacion("Resumen", "https://n/1")) is True
    (url1, datos1), (url2, datos2) = llamadas
    assert url1 == "https://graph.threads.net/v1.0/42/threads"
    assert datos1 == {"media_type": "TEXT", "text": "Resumen", "link_attachment": "https://n/1",
                      "topic_tag": "videojuegos", "access_token": "token"}
    assert url2 == "https://graph.threads.net/v1.0/42/threads_publish"
    assert datos2 == {"creation_id": "contenedor-1", "access_token": "token"}


def test_threads_con_error_devuelve_false(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda url, **kw: Respuesta(400))
    assert Threads().publicar(Publicacion("a", "b")) is False


def test_threads_sin_credenciales_devuelve_false(monkeypatch):
    monkeypatch.delenv("THREADS_ACCESS_TOKEN")
    assert Threads().publicar(Publicacion("a", "b")) is False


def _threads_falso(monkeypatch, estados=("FINISHED",), falla_imagen=False):
    llamadas = {"post": [], "get": []}
    estados = list(estados)

    def post(url, **kw):
        llamadas["post"].append((url, kw["data"]))
        if falla_imagen and kw["data"].get("media_type") == "IMAGE":
            return Respuesta(400, texto="formato de imagen no admitido")
        return Respuesta(200, {"id": "contenedor-1"})

    def get(url, **kw):
        llamadas["get"].append(url)
        return Respuesta(200, {"status": estados.pop(0) if len(estados) > 1 else estados[0]})
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    return llamadas


def test_threads_con_imagen_adjunta_la_imagen_y_pone_el_enlace_en_el_texto(monkeypatch):
    llamadas = _threads_falso(monkeypatch, estados=("IN_PROGRESS", "FINISHED"))
    p = Publicacion("Resumen\n\n📰 Vandal", "https://n/1", url_imagen="https://i/x.jpg", imagen_en_threads=True)
    assert Threads().publicar(p) is True
    (_, datos1), (url2, _) = llamadas["post"]
    assert datos1 == {"media_type": "IMAGE", "image_url": "https://i/x.jpg", "text": "Resumen\n\n📰 Vandal\n\n👉 https://n/1",
                      "topic_tag": "videojuegos", "access_token": "token"}
    assert url2.endswith("/threads_publish")
    assert llamadas["get"] == ["https://graph.threads.net/v1.0/contenedor-1"] * 2


def test_threads_si_falla_la_imagen_publica_con_la_tarjeta_del_enlace(monkeypatch):
    llamadas = _threads_falso(monkeypatch, falla_imagen=True)
    p = Publicacion("Resumen", "https://n/1", url_imagen="https://i/x.webp", imagen_en_threads=True)
    assert Threads().publicar(p) is True
    tipos = [d.get("media_type") for _, d in llamadas["post"]]
    assert tipos == ["IMAGE", "TEXT", None]
    assert llamadas["post"][1][1]["link_attachment"] == "https://n/1"


def test_threads_si_la_imagen_da_error_al_procesarse_publica_con_la_tarjeta(monkeypatch):
    llamadas = _threads_falso(monkeypatch, estados=("ERROR",))
    p = Publicacion("Resumen", "https://n/1", url_imagen="https://i/x.jpg", imagen_en_threads=True)
    assert Threads().publicar(p) is True
    assert [d.get("media_type") for _, d in llamadas["post"]] == ["IMAGE", "TEXT", None]


def test_threads_sin_url_de_imagen_usa_la_tarjeta_aunque_la_fuente_lo_pida(monkeypatch):
    llamadas = _threads_falso(monkeypatch)
    assert Threads().publicar(Publicacion("Resumen", "https://n/1", imagen_en_threads=True)) is True
    assert llamadas["post"][0][1]["media_type"] == "TEXT" and llamadas["get"] == []


def test_threads_sin_la_opcion_no_adjunta_imagen(monkeypatch):
    llamadas = _threads_falso(monkeypatch)
    assert Threads().publicar(Publicacion("Resumen", "https://n/1", url_imagen="https://i/x.jpg")) is True
    assert llamadas["post"][0][1]["media_type"] == "TEXT"


# ---------------- Cola de X ----------------
@pytest.fixture
def cola(tmp_path):
    ruta = tmp_path / "cola_x.json"
    return ruta, lambda: json.loads(ruta.read_text(encoding="utf-8"))


def test_cola_x_apunta_el_texto_de_bluesky_con_el_enlace_al_final(cola):
    ruta, leer = cola
    p = Publicacion("Resumen\n\n📰 Vandal", "https://n/1", titulo_tarjeta="Título", url_imagen="https://i/x.jpg",
                    hashtags=["#uno", "no-vale", "#dos"])
    assert ColaX("noticia", "mundospixelados", str(ruta)).publicar(p) is True
    [e] = leer()
    assert e["texto"] == "Resumen\n\n📰 Vandal\n\n#uno #dos\n\nhttps://n/1"
    assert {k: e[k] for k in ("tipo", "proyecto", "titulo", "enlace", "imagen")} == {
        "tipo": "noticia", "proyecto": "mundospixelados", "titulo": "Título", "enlace": "https://n/1",
        "imagen": "https://i/x.jpg"}
    assert len(e["id"]) == 12 and e["fecha"].endswith("+00:00")


def test_cola_x_sin_hashtags_no_deja_lineas_en_blanco_de_mas(cola):
    ruta, leer = cola
    ColaX("video", "p", str(ruta)).publicar(Publicacion("Texto", "https://y/1"))
    assert leer()[0]["texto"] == "Texto\n\nhttps://y/1"


def test_cola_x_usa_los_mismos_hashtags_que_caben_en_bluesky(cola, bsky):
    ruta, leer = cola
    p = Publicacion("x" * 250, "https://n/1", hashtags=["#" + "a" * 20] * 5)
    ColaX("noticia", "p", str(ruta)).publicar(p)
    Bluesky().publicar(p)
    assert leer()[0]["texto"] == bsky.publicaciones[0][0].build_text() + "\n\nhttps://n/1"


def test_cola_x_no_repite_un_enlace_ya_apuntado(cola):
    ruta, leer = cola
    c = ColaX("video", "p", str(ruta))
    assert c.publicar(Publicacion("A", "https://y/1")) is True
    assert c.publicar(Publicacion("B", "https://y/1")) is True
    assert [e["texto"] for e in leer()] == ["A\n\nhttps://y/1"]


def test_cola_x_la_mas_nueva_primero_y_recorta_cada_tipo_por_separado(cola):
    ruta, leer = cola
    videos, noticias = ColaX("video", "p", str(ruta), maximo=2), ColaX("noticia", "p", str(ruta), maximo=2)
    videos.publicar(Publicacion("v", "https://y/v0"))
    for i in range(4):
        noticias.publicar(Publicacion("n", f"https://n/{i}"))
    assert [e["enlace"] for e in leer()] == ["https://n/3", "https://n/2", "https://y/v0"]


def test_cola_x_si_no_puede_escribir_devuelve_false(tmp_path):
    assert ColaX("video", "p", str(tmp_path / "no-existe" / "cola_x.json")).publicar(Publicacion("a", "b")) is False


# ---------------- Enlaces extra ----------------
VIDEO = ("🎬 Reseña en vídeo", "https://youtu.be/abc")


def test_discord_pone_los_enlaces_extra_sin_vista_previa(monkeypatch):
    enviados = []
    monkeypatch.setattr(requests, "post", lambda url, **kw: (enviados.append(kw["json"]["content"]), Respuesta(204))[1])
    Discord("DISCORD_WEBHOOK").publicar(Publicacion("Reseña", "https://s/1", enlaces_extra=[VIDEO]))
    assert enviados == ["Reseña\n\n🎬 Reseña en vídeo: <https://youtu.be/abc>\n\nhttps://s/1"]


def test_bluesky_los_enlaces_extra_son_clicables_y_solo_cuenta_la_etiqueta(bsky):
    Bluesky().publicar(Publicacion("Reseña", "https://s/1", hashtags=["#steam"], enlaces_extra=[VIDEO]))
    texto, embed = bsky.publicaciones[0]
    assert texto.build_text() == "Reseña\n\n🎬 Reseña en vídeo\n\n#steam"
    [enlace, etiqueta] = texto.build_facets()
    assert enlace.features[0].uri == "https://youtu.be/abc" and etiqueta.features[0].tag == "steam"
    assert embed.external.uri == "https://s/1"


def test_bluesky_los_enlaces_extra_cuentan_para_el_limite_de_hashtags(bsky):
    Bluesky().publicar(Publicacion("x" * 270, "https://s/1", hashtags=["#steam"], enlaces_extra=[VIDEO]))
    assert "#steam" not in bsky.publicaciones[0][0].build_text()   # 270 + 2 + 17 + 2 + 6 > 295


def test_threads_pone_los_enlaces_extra_antes_del_principal(monkeypatch):
    llamadas = _threads_falso(monkeypatch)
    Threads().publicar(Publicacion("Reseña", "https://s/1", url_imagen="https://i/x.jpg", imagen_en_threads=True,
                                   enlaces_extra=[VIDEO]))
    assert llamadas["post"][0][1]["text"] == "Reseña\n\n🎬 Reseña en vídeo: https://youtu.be/abc\n\n👉 https://s/1"


def test_cola_x_incluye_los_enlaces_extra(cola):
    ruta, leer = cola
    ColaX("resena", "mp", str(ruta)).publicar(Publicacion("Reseña", "https://s/1", hashtags=["#steam"],
                                                          enlaces_extra=[VIDEO]))
    assert leer()[0]["texto"] == "Reseña\n\n🎬 Reseña en vídeo: https://youtu.be/abc\n\n#steam\n\nhttps://s/1"


def test_threads_con_imagen_puede_ir_sin_el_enlace_principal(monkeypatch):
    llamadas = _threads_falso(monkeypatch)
    Threads().publicar(Publicacion("Reseña", "https://s/1", url_imagen="https://i/x.jpg", imagen_en_threads=True,
                                   enlace_en_texto=False, enlaces_extra=[VIDEO]))
    assert llamadas["post"][0][1]["text"] == "Reseña\n\n🎬 Reseña en vídeo: https://youtu.be/abc"


def test_discord_con_imagen_y_sin_el_enlace_principal(monkeypatch):
    enviados = []
    monkeypatch.setattr(requests, "post", lambda url, **kw: (enviados.append(kw["json"]), Respuesta(204))[1])
    Discord("DISCORD_WEBHOOK").publicar(Publicacion("Reseña", "https://s/1", url_imagen="https://i/x.jpg",
                                                    imagen_en_discord=True, enlace_en_texto=False,
                                                    enlaces_extra=[VIDEO]))
    assert enviados == [{"content": "Reseña\n\n🎬 Reseña en vídeo: <https://youtu.be/abc>",
                         "embeds": [{"image": {"url": "https://i/x.jpg"}}]}]


def test_discord_sin_la_opcion_no_envia_imagen(monkeypatch):
    enviados = []
    monkeypatch.setattr(requests, "post", lambda url, **kw: (enviados.append(kw["json"]), Respuesta(204))[1])
    Discord("DISCORD_WEBHOOK").publicar(Publicacion("Noticia", "https://n/1", url_imagen="https://i/x.jpg"))
    assert enviados == [{"content": "Noticia\n\nhttps://n/1"}]


def test_cola_x_sin_el_enlace_principal(cola):
    ruta, leer = cola
    ColaX("resena", "mp", str(ruta)).publicar(Publicacion("Reseña", "https://s/1", enlace_en_texto=False,
                                                          enlaces_extra=[VIDEO]))
    [e] = leer()
    assert e["texto"] == "Reseña\n\n🎬 Reseña en vídeo: https://youtu.be/abc" and e["enlace"] == "https://s/1"
