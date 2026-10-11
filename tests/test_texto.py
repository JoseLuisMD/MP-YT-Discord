from common.texto import (extraer_hashtags, limpiar_html, normalizar, quitar_bloques, quitar_lineas_de_enlaces,
                          recortar)


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


def test_quitar_bloques_elimina_el_bloque_entero_con_lo_que_lleva_dentro():
    html = ('<p>Antes <a href="x">enlace normal</a></p>'
            '<div class="asset"><div class="desvio-container"><div><img src="i.jpg"><a>Otra de Warcraft</a></div></div></div>'
            '<p>Después &amp; fin</p>')
    assert limpiar_html(quitar_bloques(html, ("desvio-container",))) == "Antes enlace normal Después & fin"


def test_quitar_bloques_quita_scripts_y_estilos():
    html = '<p>Hola</p><script type="application/json">{"title": "Zelda"}</script><style>.a{}</style><p>adiós</p>'
    assert limpiar_html(quitar_bloques(html)) == "Hola adiós"


def test_quitar_bloques_tolera_html_mal_cerrado():
    assert limpiar_html(quitar_bloques('<div class="quitar"><p>fuera</div><p>queda</p>', ("quitar",))) == "queda"


def test_quitar_lineas_de_enlaces_a_otros_articulos():
    html = ('<p>La noticia habla de <a href="x">guías</a> | y sigue.</p>'
            '<p>Imágenes | <a href="g">GameFAQs ASCII Art</a></p>'
            '<p>En VidaExtra |&nbsp;<a href="p">Cómo un señor cambió el mercado de las cartas Pokémon</a></p>')
    assert limpiar_html(quitar_lineas_de_enlaces(html)) == "La noticia habla de guías | y sigue."
