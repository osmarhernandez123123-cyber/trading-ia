
import pandas as pd
from datetime import time

# Cargar datos históricos
df = pd.read_parquet("datos_acciones.parquet")
df = df.reset_index()

# Convertir las fechas a horario de Nueva York
df["timestamp"] = pd.to_datetime(
    df["timestamp"], utc=True
)
df["hora_ny"] = df["timestamp"].dt.tz_convert(
    "America/New_York"
)

def clasificar_sesion(fecha):
    hora = fecha.time()

    if time(4, 0) <= hora < time(9, 30):
        return "PRE_MARKET"
    elif time(9, 30) <= hora < time(16, 0):
        return "REGULAR"
    elif time(16, 0) <= hora < time(20, 0):
        return "AFTER_HOURS"
    else:
        return "OVERNIGHT"

df["sesion"] = df["hora_ny"].apply(
    clasificar_sesion
)

print("=== VELAS POR ACCION Y SESION ===")
print(pd.crosstab(df["symbol"], df["sesion"]))

print("\n=== RANGO DE FECHAS ===")
for simbolo, datos in df.groupby("symbol"):
    print(simbolo)
    print("Inicio:", datos["hora_ny"].min())
    print("Fin:", datos["hora_ny"].max())

# Guardar archivo con sesiones clasificadas
df.to_parquet("datos_clasificados.parquet", index=False)

print("\nClasificacion completada")
