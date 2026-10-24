"""Estrés de costes incrementales en operaciones OOS sintéticas o autorizadas.

No altera la estrategia, no selecciona parámetros y no ejecuta órdenes.
El PnL de entrada YA debe incluir los costes del backtest; se añade una
penalización adversa hipotética, nunca se reemplazan los costes existentes.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .metricas_oos import evaluar_prueba
from .validacion_temporal import VentanaTemporal


ADVERTENCIA_COSTES = (
    "Estrés descriptivo fuera de muestra, NO optimización. El coste adicional "
    "se aproxima como dos lados por el nocional de entrada (igual nocional "
    "supuesto a la salida), sin libro de órdenes, impacto, borrow ni "
    "comisiones específicas del broker. El PnL original ya incorpora los "
    "costes del backtest; este cálculo solo añade una penalización. "
    "No demuestra rentabilidad ni ventaja estadística."
)


def evaluar_estres_costes(
    operaciones: pd.DataFrame,
    ventana: VentanaTemporal,
    *,
    coste_extra_bps_lado: float,
    capital_inicial: float = 100_000.0,
) -> dict:
    """Compara OOS fijo antes/después de una penalización adversa por trade.

    `coste_extra_bps_lado`: puntos básicos ADICIONALES por lado; entrada y
    salida se aproximan usando el nocional de entrada. No reoptimiza señales.
    """
    if (isinstance(coste_extra_bps_lado, bool)
            or not isinstance(coste_extra_bps_lado, (int, float))
            or not math.isfinite(coste_extra_bps_lado)
            or coste_extra_bps_lado < 0):
        raise ValueError("coste_extra_bps_lado debe ser finito y no negativo")

    # Primero se validan las operaciones OOS originales: fechas, riesgo, R,
    # duplicados y consistencia contable. Un escenario no puede arreglar
    # registros defectuosos ni convertir in-sample en out-of-sample.
    base = evaluar_prueba(
        operaciones, ventana, capital_inicial=capital_inicial
    )
    if "nocional" not in operaciones.columns:
        raise ValueError("Falta columna nocional para estrés de costes")
    # Evitar coerción silenciosa: "1000" y True no son nocionales válidos.
    if not operaciones["nocional"].map(
        lambda v: isinstance(v, (int, float, np.integer, np.floating))
        and not isinstance(v, (bool, np.bool_))
    ).all():
        raise ValueError("nocional requiere valores numéricos, no texto o booleanos")
    try:
        nocional = pd.to_numeric(operaciones["nocional"], errors="raise").to_numpy(
            dtype=float
        )
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("nocional inválido") from exc
    if not np.isfinite(nocional).all() or (nocional <= 0).any():
        raise ValueError("nocional debe ser finito y positivo")

    # Calcular primero el factor evita desbordar en 2*nocional aunque el
    # coste final sí sea representable. Validar también la suma agregada.
    factor = 2 * (float(coste_extra_bps_lado) / 10_000)
    if not math.isfinite(factor):
        raise ValueError("Coste incremental no finito")
    with np.errstate(over="ignore", invalid="ignore"):
        ajuste = nocional * factor
        coste_total = float(np.sum(ajuste, dtype=np.float64))
    if not np.isfinite(ajuste).all():
        raise ValueError("Coste incremental no finito")
    if not math.isfinite(coste_total):
        raise ValueError("Coste incremental agregado no finito")

    ajustadas = operaciones.copy(deep=True)
    pnl = pd.to_numeric(ajustadas["pnl_usd"], errors="coerce").to_numpy(dtype=float)
    riesgo = pd.to_numeric(
        ajustadas["riesgo_total"], errors="coerce"
    ).to_numpy(dtype=float)
    pnl_ajustado = pnl - ajuste
    if not np.isfinite(pnl_ajustado).all():
        raise ValueError("PnL tras costes no finito")
    ajustadas["pnl_usd"] = pnl_ajustado
    ajustadas["R"] = pnl_ajustado / riesgo
    estresado = evaluar_prueba(
        ajustadas, ventana, capital_inicial=capital_inicial
    )
    return {
        "schema_version": 1,
        "coste_extra_bps_lado": float(coste_extra_bps_lado),
        "coste_extra_total_usd": coste_total,
        "baseline": base,
        "estresado": estresado,
        "advertencia": ADVERTENCIA_COSTES,
    }
