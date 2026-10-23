"""Agregación descriptiva de bloques OOS sin reutilizar sesiones de prueba.

No combina curvas de capital ni supone independencia entre operaciones.
Cada ventana se evalúa con el validador OOS existente antes de agregar.
"""
from __future__ import annotations

from datetime import date
from math import sqrt
from typing import Sequence

import pandas as pd

from .metricas_oos import evaluar_prueba
from .validacion_temporal import VentanaTemporal


ADVERTENCIA_AGREGADA = (
    "Resumen descriptivo de bloques de prueba disjuntos. No se suman "
    "retornos porcentuales ni drawdowns de capital reiniciado. El intervalo "
    "Wilson supone observaciones Bernoulli independientes; la correlación "
    "temporal y entre símbolos puede invalidar su cobertura. No prueba "
    "ventaja estadística ni rentabilidad futura."
)


def _intervalo_wilson(ganadoras: int, n: int) -> tuple[float, float] | None:
    """Intervalo Wilson nominal 95% para proporción de operaciones ganadoras."""
    if n == 0:
        return None
    z = 1.959963984540054
    p = ganadoras / n
    z2 = z * z
    centro = (p + z2 / (2 * n)) / (1 + z2 / n)
    radio = z * sqrt((p * (1 - p) + z2 / (4 * n)) / n) / (1 + z2 / n)
    return (100 * max(0.0, centro - radio), 100 * min(1.0, centro + radio))


def agregar_pruebas(
    ventanas: Sequence[VentanaTemporal],
    operaciones_por_ventana: Sequence[pd.DataFrame],
    *,
    capital_inicial: float = 100_000.0,
) -> dict:
    """Valida y resume pruebas cronológicas sin duplicar trades ni sesiones.

    Las operaciones de cada DataFrame deben corresponder EXACTAMENTE a la
    ventana en la misma posición. El capital es una referencia por ventana,
    no una simulación continua: no se infiere retorno compuesto del conjunto.
    """
    ventanas = tuple(ventanas)
    bloques = tuple(operaciones_por_ventana)
    if not ventanas or len(ventanas) != len(bloques):
        raise ValueError("Se requieren ventanas y bloques OOS no vacíos y pareados")

    resumenes = []
    ultimo_fin: date | None = None
    claves_vistas = set()
    for ventana, operaciones in zip(ventanas, bloques):
        if not isinstance(ventana, VentanaTemporal) or not ventana.prueba:
            raise ValueError("Cada ventana debe tener sesiones de prueba")
        fechas = ventana.prueba
        if any(type(d) is not date for d in fechas) or any(
            a >= b for a, b in zip(fechas, fechas[1:])
        ):
            raise ValueError("Sesiones de prueba inválidas o duplicadas")
        if ultimo_fin is not None and fechas[0] <= ultimo_fin:
            raise ValueError("Ventanas de prueba solapadas o desordenadas")
        ultimo_fin = fechas[-1]

        # evaluar_prueba valida el DataFrame completo: zonas horarias,
        # fechas de entrada/salida, duplicados, R, PnL y riesgo finitos.
        resumen = evaluar_prueba(operaciones, ventana, capital_inicial=capital_inicial)
        if not operaciones.empty:
            claves = set(zip(
                operaciones["symbol"],
                pd.to_datetime(operaciones["entrada_timestamp"], utc=True),
            ))
            if claves_vistas.intersection(claves):
                raise ValueError("Operación duplicada entre ventanas")
            claves_vistas.update(claves)
        resumenes.append(resumen)

    n = sum(r["operaciones"] for r in resumenes)
    ganadoras = sum(r["ganadoras"] for r in resumenes)
    pnl = sum(r["pnl_realizado_usd"] for r in resumenes)
    suma_r = sum(
        r["expectativa_r"] * r["operaciones"]
        for r in resumenes if r["operaciones"]
    )
    return {
        "schema_version": 1,
        "ventanas": len(resumenes),
        "ventanas_con_operaciones": sum(r["operaciones"] > 0 for r in resumenes),
        "operaciones": n,
        "ganadoras": ganadoras,
        "perdedoras": sum(r["perdedoras"] for r in resumenes),
        "neutras": sum(r["neutras"] for r in resumenes),
        "pnl_realizado_suma_usd": float(pnl),
        "expectativa_r_ponderada": float(suma_r / n) if n else None,
        "tasa_acierto_pct": 100 * ganadoras / n if n else None,
        "intervalo_wilson_95_pct": _intervalo_wilson(ganadoras, n),
        "min_operaciones_ventana": min(r["operaciones"] for r in resumenes),
        "max_operaciones_ventana": max(r["operaciones"] for r in resumenes),
        "por_ventana": resumenes,
        "advertencia": ADVERTENCIA_AGREGADA,
    }
