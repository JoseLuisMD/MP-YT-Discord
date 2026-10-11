import json

import pytest
import requests

from noticias import resumen
from noticias.config import MODELOS_LLM
from tests.conftest import Respuesta


def gemini(texto):
    return Respuesta(200, {"candidates": [{"content": {"parts": [{"text": texto}]}}]})


def gemini_json(resumen_="Resumen.", hashtags=("#uno", "#dos", "#tres", "#cuatro", "#cinco")):
    return gemini(json.dumps({"resumen": resumen_, "hashtags": list(hashtags)}))


@pytest.fixture
def llamadas(monkeypatch):
    """Sustituye la API de Gemini: `respuestas(modelo)` decide qué se devuelve y se anotan las llamadas."""
    monkeypatch.setenv("GEMINI_API_KEY", "clave")
    monkeypatch.setattr(resumen.time, "sleep", lambda s: None)
    registro = {"modelos": [], "respuesta": lambda modelo: gemini_json()}

    def falso(url, **kw):
        modelo = url.split("models/")[1].split(":")[0]
        registro["modelos"].append(modelo)
        return registro["respuesta"](modelo)

    monkeypatch.setattr(requests, "post", falso)
    # Por defecto la lista de modelos falla y se usa la de respaldo (MODELOS_LLM)
    registro["lista"] = lambda: Respuesta(500)
    monkeypatch.setattr(requests, "get", lambda url, **kw: registro["lista"]())
    return registro


def lista_modelos(*nombres, metodos=("generateContent",)):
    return Respuesta(200, {"models": [{"name": f"models/{n}", "supportedGenerationMethods": list(metodos)}
                                      for n in nombres]})


def test_resumen_y_hashtags(llamadas):
    assert resumen.resumir("Título", "Texto") == ("Resumen.", ["#uno", "#dos", "#tres", "#cuatro", "#cinco"])
    assert llamadas["modelos"] == [MODELOS_LLM[0]]


def test_acepta_json_con_vallas_de_codigo(llamadas):
    llamadas["respuesta"] = lambda m: gemini('```json\n{"resumen":"Con vallas.","hashtags":["#a"]}\n```')
    assert resumen.resumir("T", "x") == ("Con vallas.", ["#a"])


def test_limpia_los_hashtags(llamadas):
    sucios = ["#a b", "c", "#ñandú", "#x", "#x", "#6", "#7", "#8"]
    llamadas["respuesta"] = lambda m: gemini_json(hashtags=sucios)
    assert resumen.resumir("T", "x")[1] == ["#ab", "#x", "#6", "#7", "#8"]


def test_el_resumen_se_recorta_a_200_caracteres(llamadas):
    llamadas["respuesta"] = lambda m: gemini_json("palabra " * 50)
    assert len(resumen.resumir("T", "x")[0]) <= 200


def test_si_un_modelo_no_existe_se_prueba_el_siguiente(llamadas):
    llamadas["respuesta"] = lambda m: Respuesta(404) if m == MODELOS_LLM[0] else gemini_json("Del segundo.")
    assert resumen.resumir("T", "x")[0] == "Del segundo."
    assert llamadas["modelos"] == [MODELOS_LLM[0], MODELOS_LLM[1]]


def test_errores_transitorios_se_reintentan_y_luego_se_pasa_al_siguiente(llamadas):
    llamadas["respuesta"] = lambda m: Respuesta(429) if m == MODELOS_LLM[0] else gemini_json("Del segundo.")
    assert resumen.resumir("T", "x")[0] == "Del segundo."
    assert llamadas["modelos"] == [MODELOS_LLM[0]] * 3 + [MODELOS_LLM[1]]


def test_si_gemini_falla_en_una_fuente_en_espanol_se_usa_el_titulo(llamadas):
    llamadas["respuesta"] = lambda m: Respuesta(500)
    assert resumen.resumir("Un título", "x") == ("Un título", [])


def test_si_gemini_falla_en_otro_idioma_no_se_publica(llamadas):
    llamadas["respuesta"] = lambda m: Respuesta(500)
    assert resumen.resumir("A title", "x", otro_idioma=True) is None


def test_respuesta_que_no_es_json(llamadas):
    llamadas["respuesta"] = lambda m: gemini("esto no es json")
    assert resumen.resumir("Título", "x") == ("Título", [])
    assert llamadas["modelos"] == list(MODELOS_LLM)


def test_resumen_vacio_se_descarta(llamadas):
    llamadas["respuesta"] = lambda m: gemini_json("")
    assert resumen.resumir("Título", "x") == ("Título", [])


def test_sin_clave_no_se_llama_a_gemini(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert resumen.resumir("Título", "x") == ("Título", [])
    assert resumen.resumir("Title", "x", otro_idioma=True) is None


def test_el_prompt_pide_castellano(llamadas, monkeypatch):
    enviados = []

    def falso(url, **kw):
        enviados.append(kw["json"]["contents"][0]["parts"][0]["text"])
        return gemini_json()
    monkeypatch.setattr(requests, "post", falso)
    resumen.resumir("Título", "Texto")
    assert "español de España" in enviados[0] and "Título: Título" in enviados[0]


def test_se_usan_los_flash_lite_estables_descubiertos_del_mas_nuevo_al_mas_antiguo(llamadas):
    llamadas["lista"] = lambda: lista_modelos(
        "gemini-3.1-flash-lite", "gemini-10.0-flash-lite", "gemini-4.0-flash-lite-preview-01-2027",
        "gemini-3.8-flash", "gemini-3.5-pro", "gemini-2.0-flash-lite-001", "gemini-9.2-flash-lite")
    assert resumen.modelos_a_probar("clave")[:3] == ["gemini-10.0-flash-lite", "gemini-9.2-flash-lite",
                                                     "gemini-3.1-flash-lite"]


def test_la_lista_de_respaldo_va_detras_sin_repetir(llamadas):
    llamadas["lista"] = lambda: lista_modelos("gemini-9.0-flash-lite", MODELOS_LLM[0])
    assert resumen.modelos_a_probar("clave") == list(dict.fromkeys(["gemini-9.0-flash-lite"] + MODELOS_LLM))


def test_se_ignoran_los_modelos_que_no_generan_texto(llamadas):
    llamadas["lista"] = lambda: lista_modelos("gemini-9.0-flash-lite", metodos=("embedContent",))
    assert resumen.modelos_a_probar("clave") == MODELOS_LLM


def test_se_recorren_todas_las_paginas_de_la_lista(llamadas):
    paginas = [Respuesta(200, {"models": [{"name": "models/gemini-8.0-flash-lite",
                                           "supportedGenerationMethods": ["generateContent"]}], "nextPageToken": "p2"}),
               lista_modelos("gemini-9.0-flash-lite")]
    llamadas["lista"] = lambda: paginas.pop(0)
    assert resumen.modelos_a_probar("clave")[:2] == ["gemini-9.0-flash-lite", "gemini-8.0-flash-lite"]


def test_resumir_empieza_por_el_modelo_descubierto_mas_nuevo(llamadas):
    llamadas["lista"] = lambda: lista_modelos("gemini-9.0-flash-lite")
    resumen.resumir("T", "x")
    assert llamadas["modelos"] == ["gemini-9.0-flash-lite"]


def test_un_modelo_sin_cuota_gratuita_se_salta_sin_reintentar(llamadas):
    sin_cuota = Respuesta(429, texto="Quota exceeded for metric: generate_content_free_tier_requests, limit: 0")
    llamadas["respuesta"] = lambda m: sin_cuota if m == MODELOS_LLM[0] else gemini_json("Del segundo.")
    assert resumen.resumir("T", "x")[0] == "Del segundo."
    assert llamadas["modelos"] == [MODELOS_LLM[0], MODELOS_LLM[1]]


def test_se_muestra_el_modelo_que_ha_generado_el_resumen(llamadas, capsys):
    llamadas["respuesta"] = lambda m: Respuesta(404) if m == MODELOS_LLM[0] else gemini_json()
    resumen.resumir("T", "x")
    assert f"Resumen generado con {MODELOS_LLM[1]}" in capsys.readouterr().out
