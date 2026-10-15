
import pandas as pd

archivo = "datos_acciones_30dias.parquet"
df = pd.read_parquet(archivo).reset_index()

# Convertir los horarios a Nueva York
df["timestamp"] = pd.to_datetime(
    df["timestamp"], utc=True
).dt.tz_convert("America/New_York")

hora = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute

df["sesion"] = "FUERA_DE_HORARIO"
df.loc[(hora >= 240) & (hora < 570), "sesion"] = "PRE_MARKET"
df.loc[(hora >= 570) & (hora < 960), "sesion"] = "REGULAR"
df.loc[(hora >= 960) & (hora < 1200), "sesion"] = "AFTER_HOURS"

df["fecha"] = df["timestamp"].dt.date

print("\n=== VELAS POR ACCION Y SESION ===")
print(pd.crosstab(df["symbol"], df["sesion"]))

print("\n=== COBERTURA DIARIA REGULAR ===")
regular = df[df["sesion"] == "REGULAR"]
conteo = regular.groupby(["symbol", "fecha"]).size()
print(conteo.to_string())

print("\n=== RESUMEN REGULAR ===")
print(conteo.groupby(level="symbol").agg(
    ["count", "min", "max", "mean"]
).round(2))

print("\nAuditoria completada.")
