"""Métricas descriptivas de operaciones cerradas en una ventana de prueba.

No entrena, selecciona parámetros, consulta datos ni ejecuta órdenes.
El drawdown usa exclusivamente PnL realizado al cierre, NO mark-to-market.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .validacion_temporal import VentanaTemporal


COLUMNAS = {
    "symbol", "entrada_timestamp", "salida_timestamp",
    "pnl_usd", "riesgo_total", "R",
}
ADVERTENCIA = (
    "Solo operaciones cerradas de la ventana de prueba; PnL neto según "
    "costes ya incluidos en el backtest. El drawdown realizado no mide "
    "excursiones intrabar, posiciones abiertas ni drawdown mark-to-market. "
    "No demuestra ventaja estadística ni rentabilidad futura."
)


def evaluar_prueba(
    operaciones: pd.DataFrame,
    ventana: VentanaTemporal,
    *,
    capital_inicial: float = 100_000.0,
) -> dict:
    """Resume exclusivamente operaciones intradía del bloque OOS indicado.

    Rechaza explícitamente operaciones de entrenamiento/validación, fechas
    naive, duplicados, R incompatible con PnL/riesgo y valores no finitos.
    La selección de estrategia y parámetros debe cerrarse ANTES de esta
    evaluación; esta función no evita por sí misma el sobreajuste.
    """
    if not isinstance(ventana, VentanaTemporal) or not ventana.prueba:
        raise ValueError("Se requiere una ventana temporal con prueba")
    if isinstance(capital_inicial, bool) or not isinstance(
        capital_inicial, (int, float)
    ) or not math.isfinite(capital_inicial) or capital_inicial <= 0:
        raise ValueError("capital_inicial debe ser finito y positivo")
    if not isinstance(operaciones, pd.DataFrame):
        raise ValueError("operaciones debe ser un DataFrame")
    faltantes = COLUMNAS - set(operaciones.columns)
    if faltantes:
        raise ValueError(f"Columnas de operaciones faltantes: {sorted(faltantes)}")

    df = operaciones.copy()
    base = {
        "schema_version": 1,
        "inicio_prueba": ventana.inicio_prueba.isoformat(),
        "fin_prueba": ventana.fin_prueba.isoformat(),
        "capital_inicial_usd": float(capital_inicial),
        "advertencia": ADVERTENCIA,
    }
    if df.empty:
        return {
            **base, "operaciones": 0, "ganadoras": 0, "perdedoras": 0,
            "neutras": 0, "pnl_realizado_usd": 0.0,
            "retorno_realizado_pct": 0.0, "tasa_acierto_pct": None,
            "expectativa_r": None, "drawdown_realizado_pct": 0.0,
        }

    if not df["symbol"].map(
        lambda s: isinstance(s, str) and bool(s.strip())
    ).all():
        raise ValueError("Símbolo de operación inválido")

    for campo in ("entrada_timestamp", "salida_timestamp"):
        try:
            timestamps = [pd.Timestamp(valor) for valor in df[campo]]
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError(f"{campo} ilegible") from exc
        if any(pd.isna(t) or t.tzinfo is None for t in timestamps):
            raise ValueError(f"{campo} requiere zona horaria explícita")
        df[campo] = pd.to_datetime(timestamps, utc=True)

    if df.duplicated(["symbol", "entrada_timestamp"]).any():
        raise ValueError("Operaciones duplicadas por símbolo y entrada")
    if (df["salida_timestamp"] < df["entrada_timestamp"]).any():
        raise ValueError("Salida anterior a entrada")

    entrada_fecha = df["entrada_timestamp"].dt.tz_convert(
        "America/New_York"
    ).dt.date
    salida_fecha = df["salida_timestamp"].dt.tz_convert(
        "America/New_York"
    ).dt.date
    fechas_prueba = set(ventana.prueba)
    if (not entrada_fecha.isin(fechas_prueba).all()
            or not salida_fecha.isin(fechas_prueba).all()):
        raise ValueError("Operación fuera del bloque de prueba")
    if not entrada_fecha.equals(salida_fecha):
        raise ValueError("Operación nocturna no permitida en evaluación intradía")

    for campo in ("pnl_usd", "riesgo_total", "R"):
        # No convertir texto numérico o booleanos a resultados aparentemente
        # válidos: las métricas deben proceder de un esquema numérico explícito.
        if not df[campo].map(
            lambda v: isinstance(v, (int, float, np.integer, np.floating))
            and not isinstance(v, (bool, np.bool_))
        ).all():
            raise ValueError(f"{campo} requiere valores numéricos, no texto o booleanos")
        try:
            df[campo] = pd.to_numeric(df[campo], errors="raise").astype("float64")
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError(f"{campo} no se puede representar como float64") from exc
        if not np.isfinite(df[campo].to_numpy(dtype=float)).all():
            raise ValueError(f"{campo} debe contener valores finitos")
    if not df["riesgo_total"].gt(0).all():
        raise ValueError("riesgo_total debe ser positivo")
    if not np.allclose(
        df["R"].to_numpy(dtype=float),
        (df["pnl_usd"] / df["riesgo_total"]).to_numpy(dtype=float),
        rtol=1e-6, atol=1e-8,
    ):
        raise ValueError("R no coincide con pnl_usd / riesgo_total")

    n = len(df)
    pnl = float(df["pnl_usd"].sum())
    expectativa = float(df["R"].mean())
    retorno = 100 * pnl / float(capital_inicial)
    # Agrupar salidas simultáneas: el orden arbitrario entre símbolos no
    # debe crear máximos o caídas ficticias.
    pnl_por_salida = df.groupby("salida_timestamp", sort=True)["pnl_usd"].sum()
    capital_realizado = float(capital_inicial) + pnl_por_salida.cumsum()
    picos = capital_realizado.cummax().clip(lower=float(capital_inicial))
    drawdown = float((capital_realizado / picos - 1).min() * 100)
    # Una suma/media puede desbordar aunque cada operación sea finita.
    if not (all(math.isfinite(x) for x in (pnl, expectativa, retorno, drawdown))
            and np.isfinite(pnl_por_salida.to_numpy(dtype=float)).all()
            and np.isfinite(capital_realizado.to_numpy(dtype=float)).all()):
        raise ValueError("Métricas OOS agregadas no finitas")

    return {
        **base,
        "operaciones": n,
        "ganadoras": int(df["pnl_usd"].gt(0).sum()),
        "perdedoras": int(df["pnl_usd"].lt(0).sum()),
        "neutras": int(df["pnl_usd"].eq(0).sum()),
        "pnl_realizado_usd": pnl,
        "retorno_realizado_pct": retorno,
        "tasa_acierto_pct": 100 * float(df["pnl_usd"].gt(0).sum()) / n,
        "expectativa_r": expectativa,
        "drawdown_realizado_pct": drawdown,
    }
