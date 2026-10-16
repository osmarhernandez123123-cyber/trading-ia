
import pandas as pd
from pathlib import Path

from trading_ia.calidad_datos import exigir_apto_para_indicadores

ARCHIVO = Path("datos_indicadores.parquet")

if not ARCHIVO.exists():
    raise FileNotFoundError("No existe datos_indicadores.parquet")

df = pd.read_parquet(ARCHIVO)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
exigir_apto_para_indicadores(df, "motor_analisis.py")
df = df.sort_values(["symbol", "timestamp"]).copy()

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

resultados = pd.concat(
    [analizar(g) for _, g in df.groupby("symbol", sort=False)],
    ignore_index=True
)

resultados.to_parquet(
    "datos_senales.parquet",
    index=False
)

print("\n=== RESUMEN DE SENALES ===")
print(
    resultados.groupby(["symbol", "SENAL"])
    .size()
    .unstack(fill_value=0)
)

print("\n=== ULTIMAS SENALES ===")
print(
    resultados[
        ["symbol", "timestamp", "close", "SENAL", "MOTIVO"]
    ].groupby("symbol").tail(3).to_string(index=False)
)

print("\nArchivo datos_senales.parquet creado.")
