"""Resumen, hashtags y título en español de una noticia con Gemini (plan gratuito)."""
import json
import os
import re
import time
from typing import NamedTuple

import requests

from common.texto import limpiar_html, recortar

from .config import MODELOS_EXCLUIDOS, MODELOS_LLM, PROMPT

URL_MODELOS = "https://generativelanguage.googleapis.com/v1beta/models"
URL_GEMINI = URL_MODELOS + "/{modelo}:generateContent"
ERRORES_TRANSITORIOS = {429, 500, 502, 503, 504}
PATRON_MODELO = re.compile(r"gemini-(\d+(?:\.\d+)*)-flash-lite")   # solo estables: sin -preview, -exp, -001...


class Resumen(NamedTuple):
    texto: str              # resumen en español (máximo 200 caracteres)
    hashtags: list
    titulo: str = ""        # título en español; se usa en las noticias de webs en otro idioma ("" si no lo hay)


def descubrir_modelos(clave):
    """Flash-Lite estables que ofrece la API para esta clave, del más nuevo al más antiguo. [] si falla."""
    encontrados, pagina = [], None
    try:
        for _ in range(5):
            params = {"pageSize": 1000, **({"pageToken": pagina} if pagina else {})}
            r = requests.get(URL_MODELOS, headers={"x-goog-api-key": clave}, params=params, timeout=15)
            r.raise_for_status()
            datos = r.json()
            for m in datos.get("models", []):
                nombre = m.get("name", "").removeprefix("models/")
                version = PATRON_MODELO.fullmatch(nombre)
                if (version and nombre not in MODELOS_EXCLUIDOS
                        and "generateContent" in m.get("supportedGenerationMethods", [])):
                    encontrados.append((tuple(int(x) for x in version.group(1).split(".")), nombre))
            pagina = datos.get("nextPageToken")
            if not pagina:
                break
    except (requests.RequestException, ValueError, AttributeError) as e:
        print(f"No se pudo consultar la lista de modelos de Gemini: {e}")
        return []
    return [nombre for _, nombre in sorted(set(encontrados), reverse=True)]


def modelos_a_probar(clave):
    """Los descubiertos y, detrás, los de la lista de respaldo que no estén ya."""
    descubiertos = descubrir_modelos(clave)
    print(f"Modelos de Gemini descubiertos: {descubiertos or 'ninguno (se usa la lista de respaldo)'}")
    return list(dict.fromkeys(descubiertos + MODELOS_LLM))


def _sin_cuota_gratuita(respuesta):
    """429 con «limit: 0»: el modelo no tiene cuota en el plan gratuito, no sirve de nada reintentar."""
    return respuesta.status_code == 429 and "limit: 0" in (respuesta.text or "")


def _limpiar_hashtags(crudos):
    if not isinstance(crudos, list):
        return []
    limpios = (re.sub(r"[^#\w]", "", str(x).replace(" ", "")) for x in crudos)
    return list(dict.fromkeys(h for h in limpios if re.fullmatch(r"#[A-Za-z0-9_]+", h)))[:5]


def _interpretar(contenido, modelo):
    """Convierte el texto de Gemini en un `Resumen`, o None si no sirve."""
    try:
        contenido = re.sub(r"^```(?:json)?\s*|\s*```$", "", contenido, flags=re.I)
        resultado = json.loads(contenido)
        resumen = limpiar_html(resultado.get("resumen", ""))
        hashtags = _limpiar_hashtags(resultado.get("hashtags", []))
        titulo = limpiar_html(str(resultado.get("titulo") or ""))
    except (ValueError, TypeError, AttributeError) as e:
        print(f"Respuesta JSON inválida de Gemini ({modelo}): {e}")
        return None
    if not resumen:
        print(f"Gemini devolvió un resumen vacío ({modelo}).")
        return None
    return Resumen(recortar(resumen, 200), hashtags, recortar(titulo, 150))


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
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400},
                },
                timeout=45,
            )

            if respuesta.status_code == 404:
                print(f"Modelo {modelo} no disponible (404). Probando el siguiente.")
                return None

            if _sin_cuota_gratuita(respuesta):
                print(f"Modelo {modelo} sin cuota en el plan gratuito. Probando el siguiente.")
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
    """Devuelve un `Resumen` (resumen, hashtags y título en español). Si Gemini falla, el título como resumen y sin
    hashtags; y si la noticia no está en español, None (no se publica en otro idioma)."""
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        print("Falta la variable GEMINI_API_KEY")
        return None if otro_idioma else Resumen(recortar(titulo, 270), [])

    prompt = PROMPT.format(titulo=titulo, texto=(texto or "")[:1500])
    for modelo in modelos_a_probar(clave):
        resultado = _probar_modelo(modelo, clave, prompt)
        if resultado is not None:
            print(f"Resumen generado con {modelo}")
            return resultado

    if otro_idioma:
        print("No se pudo resumir la noticia en otro idioma; se omite.")
        return None
    print("Gemini no disponible. Se utiliza el título original.")
    return Resumen(recortar(titulo, 270), [])
