
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent

OPERACIONES = BASE / "resultados_backtesting_v3_1.parquet"
ENTRENAMIENTO = BASE / "datos_entrenamiento.parquet"

ops = pd.read_parquet(OPERACIONES)
train = pd.read_parquet(ENTRENAMIENTO)

ops["entrada_timestamp"] = pd.to_datetime(
    ops["entrada_timestamp"], utc=True
)

train["timestamp"] = pd.to_datetime(
    train["timestamp"], utc=True
)

# Solo operaciones cuyo inicio pertenece al
# periodo de entrenamiento.
inicio = train["timestamp"].min()
fin = train["timestamp"].max()

ops = ops[
    ops["entrada_timestamp"].between(inicio, fin)
].copy()

# Excluir operaciones que salen del periodo.
ops["salida_timestamp"] = pd.to_datetime(
    ops["salida_timestamp"], utc=True
)

ops = ops[ops["salida_timestamp"] <= fin].copy()

if ops.empty:
    raise RuntimeError("No hay operaciones de entrenamiento")

ops["hora"] = (
    ops["entrada_timestamp"]
    .dt.tz_convert("America/New_York")
    .dt.hour
)

def resumen(g):
    return pd.Series({
        "operaciones": len(g),
        "win_rate": round((g["R"] > 0).mean() * 100, 2),
        "R_promedio": round(g["R"].mean(), 4),
        "R_total": round(g["R"].sum(), 2)
    })

print("\n=== DIAGNOSTICO V4 ===")
print("Operaciones:", len(ops))

print("\n=== POR ACCION Y DIRECCION ===")
print(
    ops.groupby(["symbol", "direccion"])
    .apply(resumen, include_groups=False)
    .to_string()
)

print("\n=== POR HORARIO ===")
print(
    ops.groupby("hora")
    .apply(resumen, include_groups=False)
    .to_string()
)

print("\n=== POR MOTIVO DE SALIDA ===")
print(
    ops.groupby("motivo_salida")
    .apply(resumen, include_groups=False)
    .to_string()
)

print("\nDiagnostico completado.")
