"""Modelo alternativo de ejecución para investigación, sin órdenes reales.

V3.1 sigue en trading_ia.transformaciones.preparar.
Este modelo fija SL/TP con el cierre de la vela de señal, conocido al
terminar esa vela, y espera una vela completa antes de entrar en la apertura
posterior. No asume conocer el precio de ejecución al fijar niveles.

Nota: el cierre de señal es una referencia, NO una ejecución garantizada.
"""
import numpy as np
import pandas as pd


def preparar_diferido(datos, latencia_velas=1):
    """Devuelve candidatas con niveles ex-ante y entrada dos barras después.

    Por diseño solo admite latencia_velas=1; simular necesita Configuracion
    LATENCIA_VELAS=1. Se descartan cruces de sesión y barras no contiguas.
    """
    if latencia_velas != 1:
        raise ValueError("El modelo diferido actualmente admite latencia_velas=1")
    requeridas = {"symbol", "timestamp", "SENAL", "close", "ATR_14"}
    faltantes = requeridas - set(datos.columns)
    if faltantes:
        raise ValueError(f"Columnas faltantes: {sorted(faltantes)}")

    # Validar antes de groupby: los símbolos nulos se omitirían en silencio.
    if datos["symbol"].isna().any() or not datos["symbol"].map(
        lambda s: isinstance(s, str) and bool(s.strip())
    ).all():
        raise ValueError("Símbolo inválido en señales")
    if datos["SENAL"].isna().any() or not datos["SENAL"].isin(
        ["LONG", "SHORT", "NO TRADE"]
    ).all():
        raise ValueError("Categoría de señal inválida")
    if any(pd.isna(t) or pd.Timestamp(t).tzinfo is None for t in datos["timestamp"]):
        raise ValueError("Timestamps requieren zona horaria explícita")
    datos = datos.copy()
    datos["timestamp"] = pd.to_datetime(datos["timestamp"], utc=True)
    if datos.duplicated(["symbol", "timestamp"]).any():
        raise ValueError("Timestamps duplicados")

    partes = []
    for _, original in datos.groupby("symbol", sort=True):
        g = original.copy().sort_values("timestamp").reset_index(drop=True)
        proxima = g["timestamp"].shift(-1)
        dos_barras = g["timestamp"].shift(-2)
        entrada = g["timestamp"] + pd.Timedelta(minutes=2)
        contigua = (
            proxima.eq(g["timestamp"] + pd.Timedelta(minutes=1))
            & dos_barras.eq(entrada)
        )
        misma_sesion = (
            g["timestamp"].dt.tz_convert("America/New_York").dt.date
            == dos_barras.dt.tz_convert("America/New_York").dt.date
        )
        nueva = (
            g["SENAL"].isin(["LONG", "SHORT"])
            & g["SENAL"].ne(g["SENAL"].shift(1))
        )
        g["entrada_timestamp"] = entrada
        # Conservamos el campo V3.1 para su métrica R nominal, pero aquí
        # contiene el cierre conocido de señal, no el precio de fill.
        g["entrada_precio"] = pd.to_numeric(g["close"], errors="coerce")
        g["precio_referencia_senal"] = g["entrada_precio"]
        g["distancia_sl"] = pd.to_numeric(g["ATR_14"], errors="coerce") * 1.5
        g["stop_loss"] = float("nan")
        g["take_profit"] = float("nan")
        largo = nueva & g["SENAL"].eq("LONG")
        corto = nueva & g["SENAL"].eq("SHORT")
        g.loc[largo, "stop_loss"] = (
            g.loc[largo, "precio_referencia_senal"] - g.loc[largo, "distancia_sl"]
        )
        g.loc[largo, "take_profit"] = (
            g.loc[largo, "precio_referencia_senal"] + 2 * g.loc[largo, "distancia_sl"]
        )
        g.loc[corto, "stop_loss"] = (
            g.loc[corto, "precio_referencia_senal"] + g.loc[corto, "distancia_sl"]
        )
        g.loc[corto, "take_profit"] = (
            g.loc[corto, "precio_referencia_senal"] - 2 * g.loc[corto, "distancia_sl"]
        )
        # No permitir que un ATR/precio inválido desaparezca con el filtro.
        if not (np.isfinite(g.loc[nueva, "distancia_sl"]) &
                g.loc[nueva, "distancia_sl"].gt(0)).all():
            raise ValueError("Distancia ATR inválida para nueva señal")
        if not (np.isfinite(g.loc[nueva, "precio_referencia_senal"]) &
                g.loc[nueva, "precio_referencia_senal"].gt(0)).all():
            raise ValueError("Precio de señal inválido")
        validas = nueva & contigua & misma_sesion
        partes.append(g.loc[validas].copy())

    if not partes:
        return datos.iloc[:0].copy()
    return pd.concat(partes, ignore_index=True)
