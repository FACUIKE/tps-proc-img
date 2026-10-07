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
(`app/routers/`) con los endpoints declarados, que por ahora responden ejemplos vacíos. Falta el
core `docscan` (detección del documento, corrección de perspectiva, mejoras de color y la CLI), el
almacenamiento, el manejo de errores y completar cada endpoint. En el estado inicial los tests dan
`60 failed, 19 passed`; el trabajo del equipo es lograr que pasen todos.

## Integrantes

- _completar_
