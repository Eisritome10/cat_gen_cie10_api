"""
API general de consulta del catálogo CIE-10 completo (~12,424 códigos),
organizado por los 22 capítulos oficiales, con búsqueda por texto y
paginación.

Los datos viven en MongoDB (colección poblada desde data/cie10_full.json
la primera vez que arranca, si la colección está vacía).

Variables de entorno:
    MONGO_URI          cadena de conexión (default: mongodb://localhost:27017)
    MONGO_DB           nombre de la base de datos (default: cie10)
    MONGO_COLLECTION   nombre de la colección (default: codes)

Ejecutar localmente:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Documentación interactiva (Swagger):
    http://127.0.0.1:8000/docs
"""

import json
import os
import re
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient

SEED_PATH = Path(__file__).parent / "data" / "cie10_full.json"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "cie10")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "codes")

app = FastAPI(
    title="API CIE-10 - Catálogo general",
    description=(
        "Consulta del catálogo completo de códigos CIE-10, organizado por "
        "capítulos, con búsqueda por texto."
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Cie10Code(BaseModel):
    id: int
    code: str
    description: str
    chapter: str


class PaginatedCodes(BaseModel):
    total: int
    limit: int
    offset: int
    results: List[Cie10Code]


_client: MongoClient = None
_collection = None


def seed_if_empty():
    if _collection.count_documents({}) > 0:
        return
    if not SEED_PATH.exists():
        raise RuntimeError(f"No se encontró el archivo semilla: {SEED_PATH}")
    with open(SEED_PATH, encoding="utf-8") as f:
        docs = json.load(f)
    _collection.insert_many(docs)
    _collection.create_index("code")
    _collection.create_index("chapter")


@app.on_event("startup")
def startup_event():
    global _client, _collection
    _client = MongoClient(MONGO_URI)
    _collection = _client[MONGO_DB][MONGO_COLLECTION]
    seed_if_empty()


@app.on_event("shutdown")
def shutdown_event():
    if _client:
        _client.close()


@app.get("/", tags=["Info"])
def root():
    return {
        "mensaje": "API general de códigos CIE-10",
        "total_codigos": _collection.count_documents({}),
        "endpoints": ["/chapters", "/codes", "/codes/{code}"],
    }


@app.get("/chapters", tags=["Catálogo general"], response_model=List[str])
def get_chapters():
    """Lista de capítulos CIE-10 presentes en el catálogo (para el desplegable)."""
    return sorted(_collection.distinct("chapter"))


@app.get("/codes", tags=["Catálogo general"], response_model=PaginatedCodes)
def get_codes(
    q: Optional[str] = Query(
        None, description="Texto libre para buscar en código o descripción"
    ),
    chapter: Optional[str] = Query(
        None, description="Filtrar por capítulo exacto (ver /chapters)"
    ),
    limit: int = Query(20, ge=1, le=20, description="Cantidad de resultados por página (máx. 20)"),
    offset: int = Query(0, ge=0, description="Desde qué posición empezar"),
):
    """
    Lista códigos del catálogo completo con filtros opcionales y paginación
    (son ~12,400 registros, así que se devuelven de a 20 como máximo por página).
    """
    filters = {}

    if chapter:
        filters["chapter"] = {"$regex": f"^{re.escape(chapter)}$", "$options": "i"}

    if q:
        q_re = re.escape(q)
        filters["$or"] = [
            {"code": {"$regex": q_re, "$options": "i"}},
            {"description": {"$regex": q_re, "$options": "i"}},
        ]

    total = _collection.count_documents(filters)
    docs = (
        _collection.find(filters, {"_id": 0})
        .sort("id", 1)
        .skip(offset)
        .limit(limit)
    )

    return PaginatedCodes(total=total, limit=limit, offset=offset, results=list(docs))


@app.get("/codes/{code}", tags=["Catálogo general"], response_model=Cie10Code)
def get_code(code: str):
    """Obtiene el detalle de un código CIE-10 puntual (ej: A000, O95, J189)."""
    doc = _collection.find_one({"code": {"$regex": f"^{re.escape(code)}$", "$options": "i"}}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Código '{code}' no encontrado en el catálogo")
    return doc
