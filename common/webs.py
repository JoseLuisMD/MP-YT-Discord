"""Webs que hay que reconstruir tras publicar algo nuevo (las lanza el workflow con `gh workflow run`)."""
import os


def anunciar_webs(webs):
    """Muestra las webs y, en GitHub Actions, las deja en la salida `webs` del paso (separadas por espacios)."""
    print(f"Webs que reconstruir: {', '.join(webs) or 'ninguna'}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"webs={' '.join(webs)}\n")
