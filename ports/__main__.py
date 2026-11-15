import os
import sys

from .avisador import ejecutar
from .github import GitHub

# SIMULAR=true (o --simular): muestra el mensaje sin enviarlo, sin marcar notificaciones y sin guardar el estado
simular = "--simular" in sys.argv or os.environ.get("SIMULAR", "").lower() == "true"
sys.exit(0 if ejecutar(GitHub(), simular=simular) else 1)
