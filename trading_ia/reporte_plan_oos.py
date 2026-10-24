"""Vincula una comparación OOS a un plan congelado por huella externa.

No accede a datasets ni verifica cuándo se publicó el compromiso SHA-256.
La comparación es descriptiva y no valida rentabilidad.
"""
from __future__ import annotations

import hmac
import re
from collections.abc import Mapping, Sequence
from datetime import date

import pandas as pd

from .comparacion_baseline_oos import comparar_baseline_oos
from .registro_plan_oos import registrar_plan_oos
from .validacion_temporal import crear_ventanas


ADVERTENCIA_REPORTE = (
    "La huella del plan debe haberse comprometido externamente ANTES de "
    "observar OOS. Comprobarla aquí no acredita fecha de registro, "
    "autenticidad del dataset ni de los parámetros declarados. "
    "Las fechas suministradas deben proceder de sesiones bursátiles "
    "verificadas; no se valida el calendario de mercado en este módulo. "
    "Las métricas son descriptivas, no demuestran rentabilidad."
)


def comparar_plan_registrado_oos(
    plan: Mapping[str, object],
    *,
    plan_sha256_esperado: str,
    sesiones: Sequence[date],
    baseline_por_ventana: Sequence[pd.DataFrame],
    candidata_por_ventana: Sequence[pd.DataFrame],
    capital_inicial: float = 100_000.0,
) -> dict:
    """Comprueba compromiso, construye ventanas y evalúa dos planes fijos.

    La huella esperada debe proceder de un registro EXTERNO previo a OOS.
    Rechaza diferencias de plan, límites de prueba y símbolos fuera del
    universo declarado ANTES de calcular resultados. No lee ni escribe.
    """
    if not isinstance(plan_sha256_esperado, str) or not re.fullmatch(
        r"[0-9a-f]{64}", plan_sha256_esperado
    ):
        raise ValueError("plan_sha256_esperado debe ser SHA-256 en minúsculas")

    registro = registrar_plan_oos(plan)
    if not hmac.compare_digest(registro["plan_sha256"], plan_sha256_esperado):
        raise ValueError("La huella del plan no coincide con el compromiso")

    normalizado = registro["plan"]
    ventanas = crear_ventanas(sesiones, **normalizado["ventanas"])
    if (ventanas[0].inicio_prueba.isoformat() != normalizado["inicio_prueba"]
            or ventanas[-1].fin_prueba.isoformat() != normalizado["fin_prueba"]):
        raise ValueError("Los límites OOS no coinciden con el plan registrado")

    base = tuple(baseline_por_ventana)
    candidata = tuple(candidata_por_ventana)
    if len(base) != len(ventanas) or len(candidata) != len(ventanas):
        raise ValueError("Cantidad de bloques no coincide con las ventanas registradas")

    universo = set(normalizado["universo"])
    for nombre, bloques in (("baseline", base), ("candidata", candidata)):
        for bloque in bloques:
            if not isinstance(bloque, pd.DataFrame) or "symbol" not in bloque:
                raise ValueError(f"{nombre}: bloque de operaciones inválido")
            if not bloque["symbol"].map(
                lambda s: isinstance(s, str) and s in universo
            ).all():
                raise ValueError(f"{nombre}: símbolo fuera del universo registrado")

    resultado = comparar_baseline_oos(
        ventanas, base, candidata,
        id_baseline=normalizado["baseline_id"],
        id_candidata=normalizado["candidata_id"],
        capital_inicial=capital_inicial,
    )
    return {
        "schema_version": 1,
        "plan_sha256": registro["plan_sha256"],
        "plan": normalizado,
        "comparacion": resultado,
        "advertencia": ADVERTENCIA_REPORTE,
    }
