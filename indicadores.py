
from pathlib import Path
import numpy as np
import pandas as pd

from trading_ia.calendario import anotar_sesion
from trading_ia.calidad_datos import (
    exigir_apto_para_indicadores,
    exigir_integridad_original,
)

CARPETA = Path(__file__).resolve().parent

df = pd.read_parquet(
    CARPETA / "datos_acciones_30dias.parquet"
).reset_index()

df["timestamp"] = pd.to_datetime(
    df["timestamp"], utc=True
)

exigir_integridad_original(df, "indicadores.py")
sesiones = anotar_sesion(df["timestamp"], "XNYS")
df = df[sesiones["en_horario"].to_numpy()].copy()
exigir_apto_para_indicadores(df, "indicadores.py")
df = df.sort_values(["symbol", "timestamp"]).copy()
df["timestamp"] = df["timestamp"].dt.tz_convert("America/New_York")

df["fecha"] = df["timestamp"].dt.date


from trading_ia.etapas import wilder


from trading_ia.etapas import calcular_indicadores


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
