"""Comparación descriptiva de dos estrategias PREDEFINIDAS en las mismas ventanas OOS.

No selecciona modelos, optimiza hiperparámetros, usa datos de entrenamiento
ni calcula significancia estadística. Las operaciones pueden ser sintéticas.
"""
from __future__ import annotations

from math import isfinite
from typing import Sequence

import pandas as pd

from .agregacion_oos import agregar_pruebas
from .validacion_temporal import VentanaTemporal


ADVERTENCIA_COMPARACION = (
    "Comparación descriptiva, no prueba de superioridad ni de rentabilidad. "
    "Los modelos, universo, costes y parámetros deben fijarse antes de abrir "
    "la prueba OOS; esta función no puede verificar ese compromiso externo. "
    "Una diferencia de medias R no es un estimador pareado de alpha: las "
    "estrategias pueden tener distinto número de operaciones, exposición, "
    "riesgo y dependencia temporal. No usar la prueba para elegir o ajustar "
    "la estrategia; no se calculan p-valores ni rankings."
)


def comparar_baseline_oos(
    ventanas: Sequence[VentanaTemporal],
    baseline_por_ventana: Sequence[pd.DataFrame],
    candidata_por_ventana: Sequence[pd.DataFrame],
    *,
    id_baseline: str,
    id_candidata: str,
    capital_inicial: float = 100_000.0,
) -> dict:
    """Evalúa dos planes ya fijados; nunca escoge el ganador en OOS.

    Cada secuencia de operaciones debe alinearse posicionalmente con las
    mismas ventanas disjuntas. Un bloque vacío no equivale a una tasa de
    acierto o expectativa R de cero.
    """
    if (not isinstance(id_baseline, str) or not id_baseline.strip()
            or not isinstance(id_candidata, str) or not id_candidata.strip()
            or id_baseline.strip() == id_candidata.strip()):
        raise ValueError("Se requieren identificadores distintos y no vacíos")

    ventanas = tuple(ventanas)
    base = agregar_pruebas(
        ventanas, tuple(baseline_por_ventana), capital_inicial=capital_inicial
    )
    candidata = agregar_pruebas(
        ventanas, tuple(candidata_por_ventana), capital_inicial=capital_inicial
    )

    comparacion = []
    for b, c in zip(base["por_ventana"], candidata["por_ventana"]):
        # No interpretar una ventana sin trades como expectativa cero.
        delta = (
            c["expectativa_r"] - b["expectativa_r"]
            if b["operaciones"] and c["operaciones"] else None
        )
        # Las medias individuales pueden ser finitas y su resta desbordar.
        # No emitir inf como si fuese una diferencia descriptiva válida.
        if delta is not None and not isfinite(delta):
            raise ValueError("Diferencia media R descriptiva no finita")
        comparacion.append({
            "inicio_prueba": b["inicio_prueba"],
            "fin_prueba": b["fin_prueba"],
            "operaciones_baseline": b["operaciones"],
            "operaciones_candidata": c["operaciones"],
            "expectativa_r_baseline": b["expectativa_r"],
            "expectativa_r_candidata": c["expectativa_r"],
            "diferencia_media_r_descriptiva": delta,
        })

    return {
        "schema_version": 1,
        "id_baseline": id_baseline.strip(),
        "id_candidata": id_candidata.strip(),
        "baseline": base,
        "candidata": candidata,
        "por_ventana": comparacion,
        "advertencia": ADVERTENCIA_COMPARACION,
    }
