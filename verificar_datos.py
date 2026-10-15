
import pandas as pd

df = pd.read_parquet("datos_acciones.parquet")

print("=== AUDITORIA DE DATOS ===")
print("Total de registros:", len(df))
print("Columnas:", list(df.columns))

if isinstance(df.index, pd.MultiIndex):
    print("\nVelas por accion:")
    print(df.groupby(level="symbol").size())

    print("\nRango de fechas por accion:")
    for simbolo, datos in df.groupby(level="symbol"):
        fechas = datos.index.get_level_values("timestamp")
        print(simbolo)
        print("  Inicio:", fechas.min())
        print("  Fin:", fechas.max())

    print("\nRegistros duplicados:", df.index.duplicated().sum())
else:
    print("Revisar estructura del indice")

print("\nValores faltantes por columna:")
print(df.isna().sum())
