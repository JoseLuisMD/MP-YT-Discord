from datetime import datetime, timezone

import pytest

from ports import avisador
from ports.avisador import Port, analizar, ejecutar, mensajes
from ports.versiones import version, version_estable


def rel(id_, tag, fecha, name="", prerelease=False, draft=False, repo="dueño/juego"):
    return {"id": id_, "tag_name": tag, "name": name, "prerelease": prerelease, "draft": draft,
            "published_at": fecha, "html_url": f"https://github.com/{repo}/releases/tag/{tag}"}


# ---------------- Versiones (tags reales de las notificaciones) ----------------

@pytest.mark.parametrize("tag, name, esperada", [
    ("v1.3.2", "007: Everything or Nothing PC port 1.3.2", (1, 3, 2)),
    ("v1.0.0", "FF7Recomp 1.0", (1, 0, 0)),
    ("1.3", "1.3", (1, 3, 0)),
    ("2.0.1", "2.0.1", (2, 0, 1)),
    ("v1.0.0", "v 1.0.0", (1, 0, 0)),
    ("v4.2-E2", "v4.2-E2", (4, 2, 0)),
    ("v0.10.61", "v0.10.61 — Board Super Sonic grinds rails", (0, 10, 61)),
    ("knack2-Version-0.18.3", "Knack II PC - 0.18.3 - Unverified versions", None),   # «Unverified»
    ("knack2-Version-0.18.4", "Knack II PC - 0.18.4", (0, 18, 4)),                     # el 2 de «knack2» no cuenta
    ("v1.0.0-rc.1", "1.0.0-rc.1", None),
    ("v1.2-beta3", "Gran Turismo 6 PC v1.2 (Beta 3)", None),
    ("testing-build", "The Simpsons testing (V1.0.1-TEST13)", None),
    ("v1.1.7-test4", "Snap64 Recomp 1.1.7-test4 (test build for issue 36)", None),
    ("v0.7.14-alpha", "v0.7.14-alpha", None),
    ("launcher-v1.6.2", "Launcher v1.6.2", None),
    ("v2026.11.11", "Demon's Souls PC port — 2026-11-11", None),
    ("nightly", "Nightly", None),
    ("build-365", "Build 365 (e8a6f85)", None),
    ("v0.1.0-preview5.1", "0.1.0-preview5.1 (test build)", None),
    ("v1.1.2", "OpenRaven v1.1.2 – Hotfix 2", (1, 1, 2)),
    ("1.6.0", "1.6.0 My Friends are my Power", (1, 6, 0)),
    ("v1.0", "Latest stable build", (1, 0, 0)),   # «latest» no es «test»
])
def test_version_estable(tag, name, esperada):
    assert version_estable(rel(1, tag, "2026-11-14T10:00:00Z", name)) == esperada


def test_prerelease_y_borrador_no_son_estables():
    assert version_estable(rel(1, "v1.0.0", "2026-11-14T10:00:00Z", prerelease=True)) is None
    assert version_estable(rel(1, "v1.0.0", "2026-11-14T10:00:00Z", draft=True)) is None


def test_version_del_nombre_si_el_tag_no_tiene():
    assert version_estable(rel(1, "release", "2026-11-14T10:00:00Z", "Mi port 1.2")) == (1, 2, 0)
    assert version("sin versión") is None


# ---------------- Análisis de un repo ----------------

FF7 = [  # la más nueva primero, como la API
    rel(9, "v1.1.5", "2026-11-15T09:17:12Z"),
    rel(8, "v1.0.0", "2026-11-14T22:44:58Z"),
    rel(2, "v0.1.4", "2026-11-09T23:22:49Z", prerelease=True),
    rel(1, "v0.1.0", "2026-11-09T20:55:44Z", prerelease=True),
]


def test_primera_vez_en_1_0():
    p = analizar("bhuiyah/ff7-recomp-android", FF7, {8, 9}, {})
    assert (p.nuevo, p.version, p.fecha_1_0.day, p.fecha.day) == (True, "1.1.5", 14, 15)


def test_ya_estaba_en_1_0():
    releases = [rel(5, "v1.3.2", "2026-11-15T09:17:32Z"), rel(4, "v1.3.1", "2026-11-11T16:18:09Z"),
                rel(3, "v1.0.0", "2026-06-01T10:00:00Z")]
    p = analizar("hk21x/007eon-recomp", releases, {5}, {})
    assert (p.nuevo, p.version, p.anterior) == (False, "1.3.2", "1.3.1")


def test_ya_avisado_antes_no_es_nuevo():
    """Aunque la release anterior se haya borrado, si ya se avisó del repo no vuelve a salir como nuevo."""
    p = analizar("dueño/juego", [rel(5, "v1.1.0", "2026-11-15T09:00:00Z")], {5}, {"dueño/juego": "1.0.0"})
    assert (p.nuevo, p.anterior) == (False, "1.0.0")


def test_sin_estables_de_la_semana_no_sale():
    releases = [rel(5, "v1.2-beta3", "2026-11-15T06:59:47Z"), rel(4, "v1.1.0", "2026-10-01T10:00:00Z")]
    assert analizar("Mabec-games/Gran-Turismo-6-PC", releases, {5}, {}) is None
    assert analizar("dueño/juego", [rel(5, "v0.10.61", "2026-11-15T07:42:14Z")], {5}, {}) is None


# ---------------- Mensajes ----------------

def port(repo, version, dia, nuevo, **kw):
    return Port(repo=repo, version=version, fecha=datetime(2026, 11, dia, 12, tzinfo=timezone.utc),
                enlace=f"https://github.com/{repo}/releases/tag/v{version}", nuevo=nuevo, **kw)


def test_mensaje_ordenado_del_mas_reciente_al_mas_antiguo():
    ports = [
        port("a/viejo", "1.0.0", 8, True, fecha_1_0=datetime(2026, 11, 8, 12, tzinfo=timezone.utc)),
        port("b/reciente", "1.1.5", 15, True, fecha_1_0=datetime(2026, 11, 14, 12, tzinfo=timezone.utc)),
        port("c/update", "1.3.2", 15, False, anterior="1.3.1"),
        port("d/update", "2.1.3", 9, False),
    ]
    texto = "\n".join(mensajes(ports, datetime(2026, 11, 7, tzinfo=timezone.utc),
                               datetime(2026, 11, 15, tzinfo=timezone.utc)))
    assert "del 07/11 al 15/11" in texto
    assert texto.index("b/reciente") < texto.index("a/viejo") < texto.index("c/update") < texto.index("d/update")
    assert "→ **1.1.5** · la 1.0 salió el 14/11" in texto
    assert "→ **1.3.2** (antes 1.3.1)" in texto
    assert "🆕 **Llegan a la 1.0 por primera vez (2)**" in texto


def test_mensaje_sin_novedades():
    (texto,) = mensajes([], datetime(2026, 11, 14, tzinfo=timezone.utc), datetime(2026, 11, 21, tzinfo=timezone.utc))
    assert "no ha salido ninguna versión estable" in texto


def test_mensajes_largos_se_trocean():
    ports = [port(f"dueño/port-con-un-nombre-largo-{i}", "1.0.0", 10, False) for i in range(60)]
    trozos = mensajes(ports, datetime(2026, 11, 7, tzinfo=timezone.utc), datetime(2026, 11, 15, tzinfo=timezone.utc))
    assert len(trozos) > 1 and all(len(t) <= 2000 for t in trozos)
    assert sum(l.startswith("• ") for t in trozos for l in t.splitlines()) == 60


# ---------------- Ejecución completa ----------------

def notif(id_hilo, repo, id_release, fecha):
    return {"id": str(id_hilo), "updated_at": fecha, "repository": {"full_name": repo},
            "subject": {"type": "Release", "url": f"https://api.github.com/repos/{repo}/releases/{id_release}"}}


class GitHubFalso:
    def __init__(self, notificaciones, releases):
        self.notificaciones, self._releases = notificaciones, releases
        self.hechas, self.desde = [], None

    def notificaciones_de_releases(self, desde=None):
        self.desde = desde
        return self.notificaciones

    def releases(self, repo):
        return self._releases[repo]

    def marcar_hecha(self, id_hilo):
        self.hechas.append(id_hilo)
        return True


AHORA = datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc)


def gh_de_prueba():
    return GitHubFalso(
        [notif(1, "bhuiyah/ff7-recomp-android", 9, "2026-11-15T09:17:12Z"),
         notif(2, "bhuiyah/ff7-recomp-android", 8, "2026-11-14T22:44:58Z"),
         notif(3, "YuutaTsubasa/Free-Riders-Recompiled", 50, "2026-11-15T07:42:14Z")],
        {"bhuiyah/ff7-recomp-android": FF7,
         "YuutaTsubasa/Free-Riders-Recompiled": [rel(50, "v0.10.61", "2026-11-15T07:42:14Z")]},
    )


def test_primera_ejecucion_avisa_marca_y_guarda(tmp_path):
    ruta, enviados = tmp_path / "ports_vistos.json", []
    gh = gh_de_prueba()
    assert ejecutar(gh, enviar=lambda t: enviados.extend(t) or True, ahora=AHORA, ruta=ruta)
    assert gh.desde is None                                      # la primera vez se lee todo
    assert "bhuiyah/ff7-recomp-android" in enviados[0] and "Free-Riders" not in enviados[0]
    assert "del 14/11 al 21/11" in enviados[0]                   # desde la notificación más antigua
    assert sorted(gh.hechas) == ["1", "2", "3"]
    estado = avisador.cargar_json(ruta, {})
    assert estado["ultima_ejecucion"] == "2026-11-21T09:00:00Z"
    assert set(estado["releases_vistas"]) == {8, 9, 50}
    assert estado["avisados"] == {"bhuiyah/ff7-recomp-android": "1.1.5"}


def test_segunda_ejecucion_no_repite(tmp_path):
    ruta = tmp_path / "ports_vistos.json"
    ejecutar(gh_de_prueba(), enviar=lambda t: True, ahora=AHORA, ruta=ruta)
    enviados, gh = [], gh_de_prueba()   # la API sigue devolviendo las mismas notificaciones (ya hechas)
    ejecutar(gh, enviar=lambda t: enviados.extend(t) or True, ahora=datetime(2026, 11, 28, 9, tzinfo=timezone.utc),
             ruta=ruta)
    assert gh.desde == "2026-11-20T09:00:00Z"                    # última ejecución menos un día de margen
    assert "ff7-recomp-android" not in enviados[0] and "no ha salido ninguna" in enviados[0]


def test_si_falla_discord_no_marca_ni_guarda(tmp_path):
    ruta, gh = tmp_path / "ports_vistos.json", gh_de_prueba()
    assert not ejecutar(gh, enviar=lambda t: False, ahora=AHORA, ruta=ruta)
    assert gh.hechas == [] and not ruta.exists()


def test_simular_no_envia_ni_marca(tmp_path):
    ruta, gh = tmp_path / "ports_vistos.json", gh_de_prueba()
    assert ejecutar(gh, enviar=lambda t: pytest.fail("no debe enviar"), simular=True, ahora=AHORA, ruta=ruta)
    assert gh.hechas == [] and not ruta.exists()
