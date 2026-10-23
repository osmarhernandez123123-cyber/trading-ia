"""Registro determinista de un plan OOS predefinido (sin datos de mercado).

La huella permite comparar el plan guardado antes de abrir el conjunto de
prueba con el plan usado después. NO acredita por sí sola la fecha de registro,
ni impide que alguien consulte OOS antes de guardar el compromiso.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Mapping
from datetime import date


CAMPOS = frozenset({
    "schema_version", "dataset_sha256", "baseline_id", "candidata_id",
    "baseline_parametros_sha256", "candidata_parametros_sha256",
    "universo", "inicio_prueba", "fin_prueba", "coste_bps_por_lado",
    "ventanas", "hipotesis",
})
VENTANAS = frozenset({
    "entrenamiento", "validacion", "prueba", "embargo",
    "horizonte_etiqueta", "paso",
})
ADVERTENCIA = (
    "La huella SHA-256 identifica este plan, pero no demuestra que se "
    "registró antes de observar los resultados OOS. Guardar y fechar el "
    "plan y su huella externamente ANTES de evaluar; no incluir secretos. "
    "Un registro no demuestra rentabilidad ni elimina sesgos históricos."
)


def _sha256(valor: object, campo: str) -> str:
    if not isinstance(valor, str) or not re.fullmatch(r"[0-9a-f]{64}", valor):
        raise ValueError(f"{campo} debe ser SHA-256 hexadecimal en minúsculas")
    return valor


def _identificador(valor: object, campo: str) -> str:
    if not isinstance(valor, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", valor
    ):
        raise ValueError(f"{campo} debe ser un identificador no ambiguo")
    return valor


def _fecha(valor: object, campo: str) -> str:
    if not isinstance(valor, str):
        raise ValueError(f"{campo} debe ser una fecha ISO YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(valor)
    except ValueError as exc:
        raise ValueError(f"{campo} debe ser una fecha ISO YYYY-MM-DD") from exc
    if parsed.isoformat() != valor:
        raise ValueError(f"{campo} debe ser una fecha ISO YYYY-MM-DD")
    return valor


def registrar_plan_oos(plan: Mapping[str, object]) -> dict:
    """Valida, normaliza y calcula huella estable de un plan sin resultados.

    Rechaza campos desconocidos (por ejemplo, métricas OOS) y exige hashes
    de los parámetros de ambas estrategias. No lee archivos ni escribe
    datos, ni verifica la veracidad de hashes declarados por el usuario.
    """
    if not isinstance(plan, Mapping) or set(plan) != CAMPOS:
        raise ValueError("Campos de plan OOS incompletos o desconocidos")
    if type(plan["schema_version"]) is not int or plan["schema_version"] != 1:
        raise ValueError("schema_version debe ser 1")

    base = _identificador(plan["baseline_id"], "baseline_id")
    candidata = _identificador(plan["candidata_id"], "candidata_id")
    if base.casefold() == candidata.casefold():
        raise ValueError("baseline_id y candidata_id deben ser distintos")

    universo = plan["universo"]
    if not isinstance(universo, (list, tuple)) or not universo:
        raise ValueError("universo debe ser una lista no vacía de símbolos")
    if any(not isinstance(s, str) or not re.fullmatch(
        r"[A-Z][A-Z0-9.]{0,9}", s
    ) for s in universo) or len(set(universo)) != len(universo):
        raise ValueError("universo contiene símbolos inválidos o duplicados")

    inicio = _fecha(plan["inicio_prueba"], "inicio_prueba")
    fin = _fecha(plan["fin_prueba"], "fin_prueba")
    if inicio > fin:
        raise ValueError("Rango de prueba invertido")

    coste = plan["coste_bps_por_lado"]
    if type(coste) not in (int, float) or not math.isfinite(coste) or coste < 0:
        raise ValueError("coste_bps_por_lado debe ser finito y no negativo")
    coste = float(coste)
    if coste == 0:
        coste = 0.0

    ventanas = plan["ventanas"]
    if not isinstance(ventanas, Mapping) or set(ventanas) != VENTANAS:
        raise ValueError("Parámetros de ventanas incompletos o desconocidos")
    if any(type(ventanas[k]) is not int or ventanas[k] < 1 for k in VENTANAS):
        raise ValueError("Los parámetros de ventanas deben ser enteros positivos")
    if ventanas["embargo"] < ventanas["horizonte_etiqueta"]:
        raise ValueError("Embargo menor al horizonte de etiqueta")
    if ventanas["paso"] < ventanas["prueba"]:
        raise ValueError("Paso menor al bloque de prueba: OOS solapado")

    hipotesis = plan["hipotesis"]
    if not isinstance(hipotesis, str):
        raise ValueError("hipotesis debe ser texto no vacío")
    hipotesis = unicodedata.normalize("NFC", hipotesis.strip())
    if not hipotesis or len(hipotesis) > 500:
        raise ValueError("hipotesis debe tener entre 1 y 500 caracteres")

    normalizado = {
        "schema_version": 1,
        "dataset_sha256": _sha256(plan["dataset_sha256"], "dataset_sha256"),
        "baseline_id": base,
        "candidata_id": candidata,
        "baseline_parametros_sha256": _sha256(
            plan["baseline_parametros_sha256"], "baseline_parametros_sha256"
        ),
        "candidata_parametros_sha256": _sha256(
            plan["candidata_parametros_sha256"], "candidata_parametros_sha256"
        ),
        "universo": sorted(universo),
        "inicio_prueba": inicio,
        "fin_prueba": fin,
        "coste_bps_por_lado": coste,
        "ventanas": {k: ventanas[k] for k in sorted(VENTANAS)},
        "hipotesis": hipotesis,
    }
    canonical = json.dumps(
        normalizado, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return {
        "schema_version": 1,
        "plan": normalizado,
        "plan_sha256": hashlib.sha256(canonical).hexdigest(),
        "advertencia": ADVERTENCIA,
    }
