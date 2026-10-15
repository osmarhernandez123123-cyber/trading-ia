
from pathlib import Path
import pandas as pd

carpeta = Path(__file__).resolve().parent

precios = pd.read_parquet(
    carpeta / "datos_acciones_30dias.parquet"
)

indicadores = pd.read_parquet(
    carpeta / "datos_indicadores.parquet"
)

print("\n=== VERIFICACION DE SINCRONIZACION ===")

for simbolo in ["AAPL", "MSFT", "NVDA"]:
    p = precios.xs(simbolo, level="symbol")
    i = indicadores[
        indicadores["symbol"] == simbolo
    ]

    ultimo_precio = p.index.max()
    ultimo_indicador = i["timestamp"].max()

    print(f"\n{simbolo}")
    print("Ultima vela:", ultimo_precio)
    print("Ultimo indicador:", ultimo_indicador)
    print(
        "Sincronizado:",
        ultimo_precio == ultimo_indicador
    )
