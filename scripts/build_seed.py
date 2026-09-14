"""
Convierte data/cie10_full.csv (id, code, description, ...) a
data/cie10_full.json, calculando el capítulo CIE-10 de cada código para
que MongoDB no tenga que recalcularlo en cada consulta.

El id de cada documento es un UUID5 determinístico derivado del código: si
este script se corre de nuevo sobre un CSV actualizado, cada código
conserva siempre el mismo UUID (no rompe referencias que ya usen ese id
como llave foránea en otros sistemas).

Uso:
    python scripts/build_seed.py
"""

import csv
import json
import re
import uuid
from pathlib import Path

SRC = Path(__file__).parent.parent / "data" / "cie10_full.csv"
DST = Path(__file__).parent.parent / "data" / "cie10_full.json"

# Namespace fijo de esta app (generado una sola vez, no cambiar).
APP_NAMESPACE = uuid.UUID("6f1b1a6a-9c2e-4b8a-9e2a-2f7b6d4c9a10")

CHAPTERS = [
    ("A", 0, "B", 99, "Ciertas enfermedades infecciosas y parasitarias"),
    ("C", 0, "D", 48, "Neoplasias"),
    ("D", 50, "D", 89, "Enfermedades de la sangre y de los órganos hematopoyéticos"),
    ("E", 0, "E", 90, "Enfermedades endocrinas, nutricionales y metabólicas"),
    ("F", 0, "F", 99, "Trastornos mentales y del comportamiento"),
    ("G", 0, "G", 99, "Enfermedades del sistema nervioso"),
    ("H", 0, "H", 59, "Enfermedades del ojo y sus anexos"),
    ("H", 60, "H", 95, "Enfermedades del oído y de la apófisis mastoides"),
    ("I", 0, "I", 99, "Enfermedades del sistema circulatorio"),
    ("J", 0, "J", 99, "Enfermedades del sistema respiratorio"),
    ("K", 0, "K", 95, "Enfermedades del sistema digestivo"),
    ("L", 0, "L", 99, "Enfermedades de la piel y del tejido subcutáneo"),
    ("M", 0, "M", 99, "Enfermedades del sistema osteomuscular y del tejido conjuntivo"),
    ("N", 0, "N", 99, "Enfermedades del sistema genitourinario"),
    ("O", 0, "O", 99, "Embarazo, parto y puerperio"),
    ("P", 0, "P", 96, "Ciertas afecciones originadas en el período perinatal"),
    ("Q", 0, "Q", 99, "Malformaciones congénitas, deformidades y anomalías cromosómicas"),
    ("R", 0, "R", 99, "Síntomas, signos y hallazgos anormales clínicos y de laboratorio"),
    ("S", 0, "T", 98, "Traumatismos, envenenamientos y otras consecuencias de causas externas"),
    ("U", 0, "U", 99, "Códigos para situaciones especiales"),
    ("V", 1, "Y", 98, "Causas externas de morbilidad y mortalidad"),
    ("Z", 0, "Z", 99, "Factores que influyen en el estado de salud y contacto con los servicios de salud"),
]

CODE_RE = re.compile(r"^([A-Z])(\d{1,3})")


def get_chapter(code: str) -> str:
    match = CODE_RE.match(code.strip().upper())
    if not match:
        return "Sin clasificar"
    letter, digits = match.group(1), match.group(2)
    num = int(digits[:2].ljust(2, "0")) if len(digits) >= 2 else int(digits)

    for start_letter, start_num, end_letter, end_num, name in CHAPTERS:
        if (letter, num) >= (start_letter, start_num) and (letter, num) <= (end_letter, end_num):
            return name
    return "Sin clasificar"


def main():
    with open(SRC, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        docs = []
        for row in reader:
            code = row["code"].strip()
            docs.append({
                "id": str(uuid.uuid5(APP_NAMESPACE, code)),
                "code": code,
                "description": row["description"].strip(),
                "chapter": get_chapter(code),
            })

    with open(DST, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)

    print(f"{len(docs)} documentos escritos en {DST}")


if __name__ == "__main__":
    main()
