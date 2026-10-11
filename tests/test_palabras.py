import json

from noticias.palabras import cargar_palabras, contar, guardar_palabras


def test_carga_los_niveles_en_orden_aunque_el_json_los_desordene(tmp_path):
    ruta = tmp_path / "p.json"
    ruta.write_text(json.dumps({"nivel_2": {"capcom": 3}, "nivel_10": {}, "nivel_1": {"sonic": 1}}), encoding="utf-8")
    assert cargar_palabras(ruta) == [{"sonic": 1}, {"capcom": 3}, {}]


def test_contar_suma_en_el_nivel_correcto():
    niveles = [{"sonic": 1, "mario": 0}, {"capcom": 0}]
    contar(niveles, 1, ["sonic", "mario"])
    contar(niveles, 2, ["capcom"])
    assert niveles == [{"sonic": 2, "mario": 1}, {"capcom": 1}]


def test_guarda_cada_nivel_en_orden_alfabetico_sin_tener_en_cuenta_tildes(tmp_path):
    ruta = tmp_path / "p.json"
    guardar_palabras(ruta, [{"zelda": 0, "Ético": 2, "mario": 1}, {"sega": 0, "capcom": 4}])
    texto = ruta.read_text(encoding="utf-8")
    assert list(json.loads(texto)["nivel_1"]) == ["Ético", "mario", "zelda"]
    assert list(json.loads(texto)["nivel_2"]) == ["capcom", "sega"]


def test_un_json_roto_no_se_sobrescribe(tmp_path):
    ruta = tmp_path / "p.json"
    ruta.write_text('{"nivel_1": {"sonic": 0,}}', encoding="utf-8")   # coma de más
    niveles = cargar_palabras(ruta)
    guardar_palabras(ruta, niveles)
    assert ruta.read_text(encoding="utf-8") == '{"nivel_1": {"sonic": 0,}}'
