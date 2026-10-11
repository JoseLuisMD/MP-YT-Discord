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
    return registro


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
