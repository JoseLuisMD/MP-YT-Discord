import os

from .avisador import ejecutar

webs = ejecutar()
print(f"Webs que reconstruir: {', '.join(webs) or 'ninguna'}")
# En GitHub Actions, el workflow lee esta salida para lanzar el workflow de cada web
if os.environ.get("GITHUB_OUTPUT"):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write(f"webs={' '.join(webs)}\n")
