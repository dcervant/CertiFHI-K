from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="FHIR Quiz Static")

# Sirve index.html, app.js, questions.json, etc.

app.mount("/", StaticFiles(directory="docs", html=True), name="docs")
