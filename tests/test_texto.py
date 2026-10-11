from common.texto import extraer_hashtags, limpiar_html, normalizar, recortar


def test_normalizar_quita_tildes_y_mayusculas():
    assert normalizar("PlayStation Él Ñandú") == "playstation el nandu"


def test_limpiar_html_quita_etiquetas_y_decodifica_entidades():
    assert limpiar_html("<p>Command &amp; Conquer&#8230;</p>  <b>ya</b>") == "Command & Conquer… ya"
    assert limpiar_html(None) == ""


def test_recortar_corta_en_palabra_completa():
    assert recortar("uno dos tres", 20) == "uno dos tres"
    assert recortar("uno dos tres cuatro", 12) == "uno dos…"


def test_extraer_hashtags_sin_repetidos_ni_numeros():
    texto = "Mira #AgeOfEmpires y #aoe4. También #ageofempires y el #1 del ranking #psx"
    assert extraer_hashtags(texto) == ["#AgeOfEmpires", "#aoe4", "#psx"]
    assert extraer_hashtags(None) == []
