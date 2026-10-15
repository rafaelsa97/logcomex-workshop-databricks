#!/usr/bin/env python3
"""Gera dist/notebooks: copia os notebooks e embute os apps (base64) no Lab 4 e na demo React do instrutor.

A demo React exige o frontend compilado antes: (cd src/app_react/frontend && npm install && npm run build).
"""
import base64
import io
import shutil
import zipfile
from pathlib import Path

RAIZ = Path(__file__).parent
DIST = RAIZ / "dist" / "LogComex Workshop"
BACKEND_REACT = RAIZ / "src/app_react/backend"


def pacote_react() -> str:
    """Zip (base64) com app.py + static/ do app React."""
    assert (BACKEND_REACT / "static/index.html").exists(), "Compile o frontend: cd src/app_react/frontend && npm run build"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(BACKEND_REACT / "app.py", "app.py")
        for arquivo in sorted((BACKEND_REACT / "static").rglob("*")):
            if arquivo.is_file():
                z.write(arquivo, arquivo.relative_to(BACKEND_REACT).as_posix())
    return base64.b64encode(buffer.getvalue()).decode()


if DIST.exists():
    shutil.rmtree(DIST)
DIST.mkdir(parents=True)
for nb in sorted((RAIZ / "src" / "notebooks").glob("*.py")):
    texto = nb.read_text()
    if nb.name == "04_Databricks_Apps.py":
        texto = (texto.replace("__APP_PY_B64__", base64.b64encode((RAIZ / "src/app/app.py").read_bytes()).decode())
                      .replace("__LOGO_B64__", base64.b64encode((RAIZ / "assets/logcomex-logotipo-branco.svg").read_bytes()).decode()))
    if nb.name == "05_Demo_Instrutor_App_React.py":
        texto = texto.replace("__APP_REACT_ZIP_B64__", pacote_react())
    (DIST / nb.name).write_text(texto)
    print("✔", nb.name)
