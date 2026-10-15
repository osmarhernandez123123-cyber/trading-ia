
from pathlib import Path
import numpy as np
import pandas as pd

CARPETA = Path(__file__).resolve().parent

df = pd.read_parquet(
    CARPETA / "datos_acciones_30dias.parquet"
).reset_index()

df["timestamp"] = pd.to_datetime(
    df["timestamp"], utc=True
).dt.tz_convert("America/New_York")

df = df.sort_values(
    ["symbol", "timestamp"]
).copy()

hora = (
    df["timestamp"].dt.hour * 60
    + df["timestamp"].dt.minute
)

# Mercado regular de Nueva York
df = df[(hora >= 570) & (hora < 960)].copy()

df["fecha"] = df["timestamp"].dt.date


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


df = pd.concat(
    [
        calcular_indicadores(g)
        for _, g in df.groupby(
            "symbol", sort=False
        )
    ],
    ignore_index=True
)

# Guardado atomico
destino = CARPETA / "datos_indicadores.parquet"
temporal = CARPETA / "datos_indicadores.tmp.parquet"

df.to_parquet(temporal, index=False)
temporal.replace(destino)

print("\n=== INDICADORES CALCULADOS ===")
print(df.groupby("symbol").size())

print("\n=== VALORES FALTANTES ===")
print(
    df.groupby("symbol")[
        [
            "EMA_9", "EMA_21", "RSI_14",
            "ATR_14", "VWAP", "VOL_REL"
        ]
    ].apply(lambda x: x.isna().sum())
)

print("\n=== ULTIMOS REGISTROS ===")
print(
    df[
        [
            "symbol", "timestamp", "close",
            "EMA_9", "EMA_21", "RSI_14",
            "ATR_14", "VWAP", "VOL_REL"
        ]
    ].tail(9).to_string(index=False)
)

print("\nArchivo actualizado correctamente.")
