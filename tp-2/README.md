# TP 2 — Escáner de documentos

La consigna completa está en [`enunciado.html`](enunciado.html) (abrilo en el navegador).

## Cómo correrlo

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8765
```

- Frontend: http://localhost:8765
- Documentación de la API: http://localhost:8765/docs

## Línea de comandos

```bash
cd backend
python -m docscan foto.jpg escaneo.png --color-mode grayscale --soften-colors 0.5
```

## Tests de aceptación

```bash
cd backend
pytest tests/test_contract.py -v
```

Se entregan el frontend, los tests, los schemas (`app/schemas.py`) y los routers
(`app/routers/`) con los endpoints declarados, que por ahora responden ejemplos vacíos. También
viene resuelto todo lo de abrir imágenes y validar: `docscan/imageio.py` (abre la foto con EXIF,
convierte Pillow ↔ OpenCV, codifica el PNG), `docscan/exceptions.py`, `app/uploads.py` (validación
del archivo subido) y `app/errors.py` (traducción de excepciones a HTTP). Falta la detección del
documento, la corrección de perspectiva, los filtros, la CLI, el almacenamiento y completar cada
endpoint. En el estado inicial los tests dan `48 failed, 31 passed`; el trabajo del equipo es lograr
que pasen todos.

## Integrantes

- _completar_
