
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent

df = pd.read_parquet(
    BASE / "resultados_backtesting_v3_1.parquet"
)

df["entrada_timestamp"] = pd.to_datetime(
    df["entrada_timestamp"], utc=True
)

hora_ny = df["entrada_timestamp"].dt.tz_convert(
    "America/New_York"
)

df["hora"] = hora_ny.dt.hour
df["dia"] = hora_ny.dt.day_name()

# Rentabilidad monetaria por operación
if "pnl" in df.columns:
    metrica = "pnl"
elif "PnL" in df.columns:
    metrica = "PnL"
elif "R" in df.columns:
    metrica = "R"
else:
    raise ValueError("No se encontró una métrica de resultado")

def analizar(columnas):
    print(
        df.groupby(columnas)[metrica]
        .agg(
            operaciones="count",
            promedio="mean",
            total="sum",
            win_rate=lambda x: (x > 0).mean() * 100
        )
        .round(3)
        .to_string()
    )

print("\n=== POR HORA DE NUEVA YORK ===")
analizar("hora")

print("\n=== POR DIA ===")
analizar("dia")

print("\n=== POR ACCION Y DIRECCION ===")
analizar(["symbol", "direccion"])

print("\n=== POR HORA Y DIRECCION ===")
analizar(["hora", "direccion"])
