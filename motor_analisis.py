
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

from trading_ia.transformaciones import analizar

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
