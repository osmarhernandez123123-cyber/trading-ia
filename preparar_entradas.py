
import pandas as pd
from pathlib import Path

from trading_ia.calidad_datos import exigir_apto_para_indicadores

ORIGEN = Path("datos_senales.parquet")
DESTINO = Path("entradas_candidatas.parquet")

df = pd.read_parquet(ORIGEN)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
exigir_apto_para_indicadores(df, "preparar_entradas.py")
df = df.sort_values(["symbol", "timestamp"]).copy()

from trading_ia.transformaciones import preparar

entradas = pd.concat(
    [preparar(g) for _, g in df.groupby("symbol", sort=False)],
    ignore_index=True
)

entradas.to_parquet(DESTINO, index=False)

print("\n=== ENTRADAS CANDIDATAS ===")
print(
    entradas.groupby(["symbol", "SENAL"])
    .size()
    .unstack(fill_value=0)
)

print("\n=== EJEMPLOS ===")
print(
    entradas[[
        "symbol", "entrada_timestamp",
        "SENAL", "entrada_precio",
        "stop_loss", "take_profit"
    ]].tail(9).to_string(index=False)
)

print("\nArchivo creado:", DESTINO)
