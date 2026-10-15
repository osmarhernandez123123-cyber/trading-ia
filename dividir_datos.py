
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
ORIGEN = BASE / "datos_senales.parquet"

ENTRENAMIENTO = BASE / "datos_entrenamiento.parquet"
PRUEBA = BASE / "datos_prueba.parquet"

PORCENTAJE_ENTRENAMIENTO = 0.70
ZONA = "America/New_York"

df = pd.read_parquet(ORIGEN).copy()

requeridas = {"symbol", "timestamp", "SENAL"}
faltantes = requeridas - set(df.columns)

if faltantes:
    raise ValueError(
        f"Faltan columnas: {faltantes}"
    )

df["timestamp"] = pd.to_datetime(
    df["timestamp"], utc=True
)

df = df.sort_values(
    ["timestamp", "symbol"]
).reset_index(drop=True)

if df.duplicated(["symbol", "timestamp"]).any():
    raise ValueError("Existen velas duplicadas")

df["fecha"] = (
    df["timestamp"]
    .dt.tz_convert(ZONA)
    .dt.date
)

# Dividir por sesiones completas, no por filas.
fechas = sorted(df["fecha"].unique())

if len(fechas) < 4:
    raise ValueError(
        "Historial insuficiente para dividir"
    )

corte = int(
    len(fechas) * PORCENTAJE_ENTRENAMIENTO
)

corte = max(1, min(corte, len(fechas) - 1))

fechas_entrenamiento = set(fechas[:corte])
fechas_prueba = set(fechas[corte:])

train = df[
    df["fecha"].isin(fechas_entrenamiento)
].copy()

test = df[
    df["fecha"].isin(fechas_prueba)
].copy()

# Eliminar columna auxiliar.
train = train.drop(columns=["fecha"])
test = test.drop(columns=["fecha"])

train.to_parquet(
    ENTRENAMIENTO, index=False
)

test.to_parquet(
    PRUEBA, index=False
)

print("\n=== DIVISION HISTORICA ===")

print("Sesiones totales:", len(fechas))
print("Sesiones entrenamiento:", corte)
print("Sesiones prueba:", len(fechas) - corte)

print("\n=== ENTRENAMIENTO ===")
print("Registros:", len(train))
print("Inicio:", train["timestamp"].min())
print("Final:", train["timestamp"].max())
print(train.groupby("symbol").size())

print("\n=== PRUEBA ===")
print("Registros:", len(test))
print("Inicio:", test["timestamp"].min())
print("Final:", test["timestamp"].max())
print(test.groupby("symbol").size())

assert (
    train["timestamp"].max()
    < test["timestamp"].min()
), "Error: periodos superpuestos"

print("\nSeparacion temporal correcta.")
print("Archivos creados correctamente.")
