#!/usr/bin/env bash
# Los archivos de estado del bot (vistos, noticias publicadas y recientes, palabras clave, noticias de la web y cola de X)
# viven en la rama «estado», para que sus commits automáticos no se mezclen con el código de main.
#
#   bash .github/estado.sh traer              deja la rama en la carpeta estado/ (el bot se ejecuta dentro)
#   bash .github/estado.sh guardar "mensaje"  sube a la rama los cambios de estado/
#
# Si la rama no existe, se crea con los archivos de estado que haya en main (solo pasa la primera vez).
set -euo pipefail

RAMA=estado
CARPETA=estado
ARCHIVOS="vistos.json noticias_publicadas.json palabras_clave.json noticias_web.json noticias_recientes.json cola_x.json"

git config user.name "github-actions"
git config user.email "github-actions@users.noreply.github.com"

existe_rama() {
  git ls-remote --exit-code --heads origin "$RAMA" >/dev/null
}

case "${1:-}" in
  traer)
    if existe_rama; then
      git fetch -q origin "$RAMA"
      git worktree add -q --detach "$CARPETA" FETCH_HEAD
    else
      echo "No existe la rama $RAMA: se crea con los archivos de estado de main"
      git worktree add -q --detach "$CARPETA"
      cd "$CARPETA"
      git checkout -q --orphan "$RAMA"
      git rm -rqf .
      for archivo in $ARCHIVOS; do
        if [ -f "../$archivo" ]; then cp "../$archivo" .; fi
      done
    fi
    ;;
  guardar)
    cd "$CARPETA"
    git add -A
    if git diff --staged --quiet; then
      echo "El estado no ha cambiado"
      exit 0
    fi
    git commit -qm "${2:-Actualizar estado}"
    if existe_rama; then
      # Por si alguien ha cambiado la rama entre medias (p. ej. palabras clave a mano)
      git fetch -q origin "$RAMA"
      git rebase -q FETCH_HEAD
    fi
    git push -q origin "HEAD:refs/heads/$RAMA"
    ;;
  *)
    echo "Uso: $0 traer | guardar \"mensaje\"" >&2
    exit 2
    ;;
esac
