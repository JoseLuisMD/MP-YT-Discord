import pytest

from noticias import proceso
from noticias.fuentes import FUENTES
from proyectos import PROYECTOS
from videos.canales import CANALES, canales_de

MP, VORTIX = "JoseLuisMD/MP-Website", None


def test_cada_canal_queda_con_la_misma_configuracion_que_antes_de_los_proyectos():
    # La lista de canales tal como estaba en videos/canales.py antes de agruparlos por proyecto
    antes = {
        "UCLD3BqL4n2GKmitkEQGCoAQ": {"mensaje": "¡Nuevo vídeo en Mundos Pixelados!", "webhooks": ["DISCORD_WEBHOOK"],
                                     "incluirShorts": True, "bluesky": True, "threads": True, "x": True, "web": MP},
        "UCb3jFYgTbBLjDDOlZiD-2kg": {"mensaje": "¡Nuevo short en Mundos Pixelados Shorts!", "webhooks": ["DISCORD_WEBHOOK"],
                                     "incluirShorts": True, "bluesky": True, "threads": True, "x": True, "web": MP},
        "UCYk9AH19xF7dtzM9OY7obmA": {"mensaje": "¡Nuevo vídeo en el canal!",
                                     "mensajeMiembros": "¡Nuevo vídeo para miembros en el canal!",
                                     "webhooks": ["DISCORD_WEBHOOK_VRTX"], "incluirShorts": False,
                                     "bluesky": False, "threads": False, "x": False, "web": VORTIX},
        "UCngXjqgH_-42BgtegyzI_-A": {"mensaje": "¡Nuevo vídeo en el canal secundario!", "webhooks": ["DISCORD_WEBHOOK_VRTX"],
                                     "incluirShorts": False, "bluesky": False, "threads": False, "x": False, "web": VORTIX},
        "UC4MGzV7ahAN1khnzdjp3rkw": {"mensaje": "¡Nuevo vídeo en el canal de WarCraft 3!", "webhooks": ["DISCORD_WEBHOOK_VRTX"],
                                     "incluirShorts": False, "bluesky": False, "threads": False, "x": False, "web": VORTIX},
    }
    assert {canal: {k: v for k, v in cfg.items() if k != "proyecto"} for canal, cfg in CANALES.items()} == antes


def test_cada_canal_sabe_a_que_proyecto_pertenece():
    assert CANALES["UCLD3BqL4n2GKmitkEQGCoAQ"]["proyecto"] == "mundospixelados"
    assert CANALES["UCYk9AH19xF7dtzM9OY7obmA"]["proyecto"] == "vortix"


def test_un_canal_puede_cambiar_una_clave_de_su_proyecto():
    canales = canales_de({"p": {"incluirShorts": True, "canales": {"A": {"mensaje": "a", "incluirShorts": False},
                                                                   "B": {"mensaje": "b"}}}})
    assert canales["A"]["incluirShorts"] is False and canales["B"]["incluirShorts"] is True


def test_un_canal_no_puede_estar_en_dos_proyectos():
    with pytest.raises(ValueError, match="dos proyectos"):
        canales_de({"p1": {"canales": {"A": {"mensaje": "a"}}}, "p2": {"canales": {"A": {"mensaje": "a"}}}})


# --- Noticias por proyecto ---

@pytest.fixture
def llamadas(monkeypatch):
    """Sustituye la publicación de noticias: anota cada llamada y dice si se ha publicado."""
    registro = {"llamadas": [], "publica": True}

    def ejecutar(**kw):
        registro["llamadas"].append(kw)
        return registro["publica"]

    monkeypatch.setattr(proceso, "ejecutar", ejecutar)
    return registro


def noticias(**cambios):
    datos = {"fuentes": ["Vandal", "3DJuegos"], "discord": "DISCORD_X", "historial": "h.json", "palabras": "p.json",
             "web": "w.json"}
    datos.update(cambios)
    return datos


def test_solo_publican_noticias_los_proyectos_que_las_tienen(llamadas):
    webs = proceso.ejecutar_proyectos({"con": {"web": "u/web", "noticias": noticias()}, "sin": {"web": "u/otra"}})
    assert len(llamadas["llamadas"]) == 1 and webs == ["u/web"]
    llamada = llamadas["llamadas"][0]
    assert [f.nombre for f in llamada["fuentes"]] == ["Vandal", "3DJuegos"]
    assert (llamada["ruta"], llamada["ruta_palabras"], llamada["ruta_web"]) == ("h.json", "p.json", "w.json")


def test_si_no_se_publica_ninguna_noticia_no_se_reconstruye_la_web(llamadas):
    llamadas["publica"] = False
    assert proceso.ejecutar_proyectos({"con": {"web": "u/web", "noticias": noticias()}}) == []


def test_las_noticias_van_a_las_redes_del_proyecto(llamadas):
    proceso.ejecutar_proyectos({"solo_discord": {"bluesky": False, "threads": False, "noticias": noticias()},
                                "todas": {"bluesky": True, "threads": True, "noticias": noticias()}})
    nombres = [[p.nombre for p in ll["publicadores"]] for ll in llamadas["llamadas"]]
    assert nombres == [["Discord"], ["Discord", "Bluesky", "Threads"]]


def test_una_web_de_noticias_con_errata_da_error():
    with pytest.raises(ValueError, match="Vandall"):
        proceso.fuentes_de(["Vandal", "Vandall"])


def test_mundos_pixelados_usa_los_archivos_de_noticias_de_siempre_y_vortix_no_tiene_noticias():
    n = PROYECTOS["mundospixelados"]["noticias"]
    assert (n["historial"], n["palabras"], n["web"]) == ("noticias_publicadas.json", "palabras_clave.json", "noticias_web.json")
    assert n["discord"] == "DISCORD_WEBHOOK_NOTICIAS"
    assert proceso.fuentes_de(n["fuentes"]) == FUENTES   # las mismas webs que antes, en el mismo orden
    assert "noticias" not in PROYECTOS["vortix"]


def test_solo_los_proyectos_con_x_apuntan_sus_noticias_para_x(llamadas):
    proceso.ejecutar_proyectos({"con_x": {"x": True, "noticias": noticias()}, "sin_x": {"noticias": noticias()}})
    con_x, sin_x = (ll["cola_x"] for ll in llamadas["llamadas"])
    assert (con_x.tipo, con_x.proyecto, con_x.ruta) == ("noticia", "con_x", "cola_x.json")
    assert sin_x is None
    assert [p.nombre for p in llamadas["llamadas"][0]["publicadores"]] == ["Discord"]   # la cola no es una red


def test_solo_mundos_pixelados_tiene_x():
    assert PROYECTOS["mundospixelados"]["x"] is True and PROYECTOS["vortix"]["x"] is False
