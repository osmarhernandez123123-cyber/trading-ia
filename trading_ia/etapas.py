"""Transformaciones en memoria; mismos parámetros que los scripts V3.1."""

import numpy as np

import pandas as pd

from .calendario import anotar_sesion

from .calidad_datos import exigir_integridad_original, exigir_apto_para_indicadores

def wilder(s, periodo=14):
    """Media de Wilder con inicializacion SMA."""
    s = s.astype(float)
    resultado = np.full(len(s), np.nan)

    if len(s) < periodo:
        return pd.Series(resultado, index=s.index)

    valores = s.to_numpy()
    validos = np.flatnonzero(~np.isnan(valores))

    if len(validos) < periodo:
        return pd.Series(resultado, index=s.index)

    inicio = validos[periodo - 1]
    resultado[inicio] = valores[
        validos[:periodo]
    ].mean()

    for j in range(inicio + 1, len(s)):
        if np.isnan(valores[j]):
            continue

        resultado[j] = (
            resultado[j - 1] * (periodo - 1)
            + valores[j]
        ) / periodo

    return pd.Series(resultado, index=s.index)

def calcular_indicadores(g):
    g = g.copy().sort_values("timestamp")

    cierre = g["close"]

    # Medias exponenciales
    g["EMA_9"] = cierre.ewm(
        span=9, adjust=False
    ).mean()

    g["EMA_21"] = cierre.ewm(
        span=21, adjust=False
    ).mean()

    # RSI Wilder
    delta = cierre.diff()

    ganancias = delta.clip(lower=0)
    perdidas = -delta.clip(upper=0)

    mg = wilder(ganancias, 14)
    mp = wilder(perdidas, 14)

    rsi = 100 - 100 / (
        1 + mg / mp.replace(0, np.nan)
    )

    rsi = rsi.mask((mp == 0) & (mg > 0), 100)
    rsi = rsi.mask((mg == 0) & (mp > 0), 0)
    rsi = rsi.mask((mg == 0) & (mp == 0), 50)

    g["RSI_14"] = rsi

    # ATR Wilder
    anterior = cierre.shift(1)

    tr = pd.concat([
        g["high"] - g["low"],
        (g["high"] - anterior).abs(),
        (g["low"] - anterior).abs()
    ], axis=1).max(axis=1)

    g["ATR_14"] = wilder(tr, 14)

    # VWAP diario
    tipico = (
        g["high"] + g["low"] + cierre
    ) / 3

    volumen_acum = (
        g.groupby("fecha")["volume"].cumsum()
    )

    pv_acum = (
        (tipico * g["volume"])
        .groupby(g["fecha"])
        .cumsum()
    )

    g["VWAP"] = (
        pv_acum /
        volumen_acum.replace(0, np.nan)
    )

    # Volumen relativo de 20 velas
    promedio = g["volume"].rolling(
        20, min_periods=20
    ).mean()

    g["VOL_REL"] = (
        g["volume"] /
        promedio.replace(0, np.nan)
    )

    return g

def analizar(g):
    g = g.copy()

    g["SENAL"] = "NO TRADE"
    g["MOTIVO"] = "Condiciones insuficientes"

    # Detectar continuidad temporal
    diferencia = g["timestamp"].diff().dt.total_seconds()

    misma_sesion = (
        g["timestamp"]
        .dt.tz_convert("America/New_York")
        .dt.date
        ==
        g["timestamp"]
        .shift(1)
        .dt.tz_convert("America/New_York")
        .dt.date
    )

    continua = misma_sesion & diferencia.eq(60)

    # Exigir indicadores completos
    columnas = [
        "EMA_9", "EMA_21", "RSI_14",
        "ATR_14", "VWAP", "VOL_REL"
    ]

    validos = g[columnas].notna().all(axis=1)

    # Condiciones alcistas
    long = (
        continua
        & validos
        & (g["EMA_9"] > g["EMA_21"])
        & (g["close"] > g["VWAP"])
        & g["RSI_14"].between(50, 70)
        & (g["VOL_REL"] >= 1)
        & (g["ATR_14"] > 0)
    )

    # Condiciones bajistas
    short = (
        continua
        & validos
        & (g["EMA_9"] < g["EMA_21"])
        & (g["close"] < g["VWAP"])
        & g["RSI_14"].between(30, 50)
        & (g["VOL_REL"] >= 1)
        & (g["ATR_14"] > 0)
    )

    g.loc[long, "SENAL"] = "LONG"
    g.loc[short, "SENAL"] = "SHORT"

    g.loc[long, "MOTIVO"] = "Confluencia alcista"
    g.loc[short, "MOTIVO"] = "Confluencia bajista"

    return g

def preparar(g):
    g = g.copy()

    anterior = g["SENAL"].shift(1)

    nueva = (
        g["SENAL"].isin(["LONG", "SHORT"])
        & g["SENAL"].ne(anterior)
    )

    # Se ejecutaria en la apertura de la siguiente vela
    g["entrada_timestamp"] = g["timestamp"].shift(-1)
    g["entrada_precio"] = g["open"].shift(-1)

    g["distancia_sl"] = g["ATR_14"] * 1.5

    g["stop_loss"] = float("nan")
    g["take_profit"] = float("nan")

    long = nueva & g["SENAL"].eq("LONG")
    short = nueva & g["SENAL"].eq("SHORT")

    g.loc[long, "stop_loss"] = (
        g.loc[long, "entrada_precio"]
        - g.loc[long, "distancia_sl"]
    )
    g.loc[long, "take_profit"] = (
        g.loc[long, "entrada_precio"]
        + 2 * g.loc[long, "distancia_sl"]
    )

    g.loc[short, "stop_loss"] = (
        g.loc[short, "entrada_precio"]
        + g.loc[short, "distancia_sl"]
    )
    g.loc[short, "take_profit"] = (
        g.loc[short, "entrada_precio"]
        - 2 * g.loc[short, "distancia_sl"]
    )

    # No cruzar dias ni huecos temporales
    diferencia = (
        g["entrada_timestamp"] - g["timestamp"]
    ).dt.total_seconds()

    entradas = g[
        nueva
        & diferencia.eq(60)
        & g["distancia_sl"].gt(0)
        & g["entrada_precio"].notna()
    ].copy()

    return entradas


def indicadores(datos):
    df = datos.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    exigir_integridad_original(df, 'indicadores')
    sesiones = anotar_sesion(df.timestamp, 'XNYS')
    df = df[sesiones.en_horario.to_numpy()].copy()
    exigir_apto_para_indicadores(df, 'indicadores')
    df = df.sort_values(['symbol', 'timestamp'])
    df['timestamp'] = df.timestamp.dt.tz_convert('America/New_York')
    df['fecha'] = df.timestamp.dt.date
    return pd.concat([calcular_indicadores(g) for _, g in df.groupby('symbol', sort=True)], ignore_index=True)


def senales(datos):
    exigir_apto_para_indicadores(datos, 'senales')
    return pd.concat([analizar(g) for _, g in datos.sort_values(['symbol', 'timestamp']).groupby('symbol', sort=True)], ignore_index=True)


def candidatas(datos):
    exigir_apto_para_indicadores(datos, 'candidatas')
    return pd.concat([preparar(g) for _, g in datos.sort_values(['symbol', 'timestamp']).groupby('symbol', sort=True)], ignore_index=True)
