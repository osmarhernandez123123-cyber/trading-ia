
from pathlib import Path
import pandas as pd

CARPETA = Path(__file__).resolve().parent

df = pd.read_parquet(
    CARPETA / "datos_indicadores.parquet"
)

columnas = [
    "EMA_9", "EMA_21",
    "RSI_14", "ATR_14",
    "VWAP", "VOL_REL"
]

print("\n=== DIAGNOSTICO DE INDICADORES ===")

for simbolo in ["AAPL", "MSFT", "NVDA"]:

    datos = df[
        df["symbol"] == simbolo
    ].sort_values("timestamp").copy()

    print(f"\n=== {simbolo} ===")
    print("Total registros:", len(datos))

    for columna in columnas:

        faltantes = datos[columna].isna().sum()

        print(
            f"{columna}: {faltantes} valores NaN"
        )

        if faltantes > 0:
            fechas = datos.loc[
                datos[columna].isna(),
                "timestamp"
            ]

            print("Primer NaN:", fechas.min())
            print("Ultimo NaN:", fechas.max())

    print("\nUltimos 3 registros:")
    print(
        datos[
            ["timestamp"] + columnas
        ].tail(3).to_string(index=False)
    )

print("\nDiagnostico completado.")
