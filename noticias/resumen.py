"""Resumen y hashtags de una noticia con Gemini (plan gratuito)."""
import json
import os
import re
import time

import requests

from common.texto import limpiar_html, recortar

from .config import MODELOS_LLM, PROMPT

URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
ERRORES_TRANSITORIOS = {429, 500, 502, 503, 504}


def _limpiar_hashtags(crudos):
    if not isinstance(crudos, list):
        return []
    limpios = (re.sub(r"[^#\w]", "", str(x).replace(" ", "")) for x in crudos)
    return list(dict.fromkeys(h for h in limpios if re.fullmatch(r"#[A-Za-z0-9_]+", h)))[:5]


def _interpretar(contenido, modelo):
    """Convierte el texto de Gemini en (resumen, hashtags), o None si no sirve."""
    try:
        contenido = re.sub(r"^```(?:json)?\s*|\s*```$", "", contenido, flags=re.I)
        resultado = json.loads(contenido)
        resumen = limpiar_html(resultado.get("resumen", ""))
        hashtags = _limpiar_hashtags(resultado.get("hashtags", []))
    except (ValueError, TypeError, AttributeError) as e:
        print(f"Respuesta JSON inválida de Gemini ({modelo}): {e}")
        return None
    if not resumen:
        print(f"Gemini devolvió un resumen vacío ({modelo}).")
        return None
    return recortar(resumen, 200), hashtags


def _probar_modelo(modelo, clave, prompt):
    """Hasta 3 intentos con un modelo. None significa «prueba con el siguiente»."""
    url = URL_GEMINI.format(modelo=modelo)
    for intento in range(3):
        try:
            respuesta = requests.post(
                url,
                headers={"x-goog-api-key": clave, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
                },
                timeout=45,
            )

            if respuesta.status_code == 404:
                print(f"Modelo {modelo} no disponible (404). Probando el siguiente.")
                return None

            if respuesta.status_code in ERRORES_TRANSITORIOS:
                if intento < 2:
                    espera = min(2 ** (intento + 1), 16)
                    print(f"Gemini HTTP {respuesta.status_code} ({modelo}). Reintento en {espera}s.")
                    time.sleep(espera)
                    continue
                print(f"Gemini sigue fallando con HTTP {respuesta.status_code} ({modelo}).")
                return None

            if respuesta.status_code != 200:
                print(f"Error Gemini HTTP {respuesta.status_code} ({modelo}): {respuesta.text[:500]}")
                return None

            candidatos = respuesta.json().get("candidates") or []
            if not candidatos:
                print(f"Gemini no devolvió candidatos ({modelo}).")
                return None

            partes = candidatos[0].get("content", {}).get("parts", [])
            contenido = "".join(p.get("text", "") for p in partes).strip()
            return _interpretar(contenido, modelo)

        except requests.RequestException as e:
            print(f"Error de conexión con Gemini ({modelo}, intento {intento + 1}): {e}")
            if intento < 2:
                time.sleep(min(2 ** (intento + 1), 16))

        except (ValueError, KeyError, TypeError) as e:
            print(f"Respuesta inesperada de Gemini ({modelo}): {e}")
            return None
    return None


def resumir(titulo, texto, otro_idioma=False):
    """Devuelve (resumen, hashtags). Si Gemini falla, el título y sin hashtags;
    y si la noticia no está en español, None (no se publica en otro idioma)."""
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        print("Falta la variable GEMINI_API_KEY")
        return None if otro_idioma else (recortar(titulo, 270), [])

    prompt = PROMPT.format(titulo=titulo, texto=(texto or "")[:1500])
    for modelo in MODELOS_LLM:
        resultado = _probar_modelo(modelo, clave, prompt)
        if resultado is not None:
            return resultado

    if otro_idioma:
        print("No se pudo resumir la noticia en otro idioma; se omite.")
        return None
    print("Gemini no disponible. Se utiliza el título original.")
    return recortar(titulo, 270), []
