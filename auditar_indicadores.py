
from pathlib import Path
import numpy as np
import pandas as pd

CARPETA = Path(__file__).resolve().parent

precios = pd.read_parquet(
    CARPETA / "datos_acciones_30dias.parquet"
)

indicadores = pd.read_parquet(
    CARPETA / "datos_indicadores.parquet"
)

precios = precios.reset_index()
precios["timestamp"] = pd.to_datetime(
    precios["timestamp"], utc=True
)

indicadores["timestamp"] = pd.to_datetime(
    indicadores["timestamp"], utc=True
)

COLUMNAS = [
    "EMA_9", "EMA_21", "RSI_14",
    "ATR_14", "VWAP", "VOL_REL"
]

print("\n=== AUDITORIA DE INDICADORES ===")

for simbolo in ["AAPL", "MSFT", "NVDA"]:
    p = precios[
        precios["symbol"] == simbolo
    ].sort_values("timestamp").copy()

    i = indicadores[
        indicadores["symbol"] == simbolo
    ].sort_values("timestamp").copy()

    print(f"\n=== {simbolo} ===")
    print("Velas:", len(p))
    print("Indicadores:", len(i))

    if p["timestamp"].duplicated().any():
        print("ERROR: velas duplicadas")
        continue

    if i["timestamp"].duplicated().any():
        print("ERROR: indicadores duplicados")
        continue

    datos = p.merge(
        i[["timestamp"] + COLUMNAS],
        on="timestamp",
        how="inner",
        validate="one_to_one"
    )

    print("Registros coincidentes:", len(datos))

    if len(datos) != len(p) or len(datos) != len(i):
        print("ADVERTENCIA: faltan registros")

    if datos.empty:
        continue

    # Comprobar integridad OHLC
    ohlc_valido = (
        (datos["high"] >= datos["low"]) &
        (datos["high"] >= datos["open"]) &
        (datos["high"] >= datos["close"]) &
        (datos["low"] <= datos["open"]) &
        (datos["low"] <= datos["close"])
    )

    print("OHLC incorrectos:", (~ohlc_valido).sum())

    # Comprobar rangos matematicos
    pruebas = {
        "EMA_9 positiva": datos["EMA_9"] > 0,
        "EMA_21 positiva": datos["EMA_21"] > 0,
        "RSI entre 0 y 100": datos["RSI_14"].between(0, 100),
        "ATR no negativo": datos["ATR_14"] >= 0,
        "VWAP positivo": datos["VWAP"] > 0,
        "Volumen relativo no negativo":
            datos["VOL_REL"] >= 0
    }

    for nombre, condicion in pruebas.items():
        fallos = (~condicion & datos[
            nombre.split()[0]
            if nombre.split()[0] in datos.columns
            else "close"
        ].notna()).sum()

        print(f"{nombre}: {int(fallos)} posibles fallos")

    # Comparacion independiente de EMA
    for periodo in [9, 21]:
        columna = f"EMA_{periodo}"

        referencia = datos["close"].ewm(
            span=periodo,
            adjust=False
        ).mean()

        diferencia = (
            datos[columna] - referencia
        ).abs()

        print(
            f"{columna} diferencia maxima:",
            round(float(diferencia.max()), 8)
        )

    print(
        "Ultima vela:",
        datos["timestamp"].max()
    )

print("\nAuditoria preliminar completada.")
