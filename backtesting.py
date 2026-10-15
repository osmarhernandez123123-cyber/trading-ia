
import pandas as pd
from pathlib import Path

DATOS = Path("datos_senales.parquet")
ENTRADAS = Path("entradas_candidatas.parquet")

velas = pd.read_parquet(DATOS)
candidatas = pd.read_parquet(ENTRADAS)

for df in (velas, candidatas):
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

candidatas["entrada_timestamp"] = pd.to_datetime(
    candidatas["entrada_timestamp"], utc=True
)

velas = velas.sort_values(["symbol", "timestamp"])
candidatas = candidatas.sort_values(
    ["symbol", "entrada_timestamp"]
)

operaciones = []

for simbolo, grupo in velas.groupby("symbol"):
    grupo = grupo.reset_index(drop=True).copy()

    entradas = candidatas[
        candidatas["symbol"] == simbolo
    ].set_index("entrada_timestamp")

    posicion = None

    for _, vela in grupo.iterrows():
        momento = vela["timestamp"]
        fecha = momento.tz_convert("America/New_York").date()

        # Cerrar una posición que cruza de sesión
        if posicion is not None and fecha != posicion["fecha"]:
            posicion["salida"] = posicion["ultimo_close"]
            posicion["salida_timestamp"] = posicion["ultimo_timestamp"]
            posicion["motivo_salida"] = "FIN_SESION"
            operaciones.append(posicion)
            posicion = None

        # Evaluar una posición abierta
        if posicion is not None:
            sl = posicion["stop_loss"]
            tp = posicion["take_profit"]

            if posicion["direccion"] == "LONG":
                toca_sl = vela["low"] <= sl
                toca_tp = vela["high"] >= tp
            else:
                toca_sl = vela["high"] >= sl
                toca_tp = vela["low"] <= tp

            if toca_sl or toca_tp:
                # Si ambos se tocan, asumir SL
                salida = sl if toca_sl else tp

                posicion["salida"] = salida
                posicion["salida_timestamp"] = momento
                posicion["motivo_salida"] = (
                    "STOP_LOSS" if toca_sl else "TAKE_PROFIT"
                )

                operaciones.append(posicion)
                posicion = None

        # Nueva entrada solamente si no hay posición
        if posicion is None and momento in entradas.index:
            candidata = entradas.loc[momento]

            if isinstance(candidata, pd.DataFrame):
                candidata = candidata.iloc[0]

            posicion = {
                "symbol": simbolo,
                "fecha": fecha,
                "direccion": candidata["SENAL"],
                "entrada_timestamp": momento,
                "entrada": candidata["entrada_precio"],
                "stop_loss": candidata["stop_loss"],
                "take_profit": candidata["take_profit"],
            }

        if posicion is not None:
            posicion["ultimo_close"] = vela["close"]
            posicion["ultimo_timestamp"] = momento

    if posicion is not None:
        posicion["salida"] = posicion["ultimo_close"]
        posicion["salida_timestamp"] = posicion["ultimo_timestamp"]
        posicion["motivo_salida"] = "FIN_DATOS"
        operaciones.append(posicion)

resultado = pd.DataFrame(operaciones)

if resultado.empty:
    raise RuntimeError("No se generaron operaciones")

direccion = resultado["direccion"].map({
    "LONG": 1,
    "SHORT": -1
})

riesgo = (
    resultado["entrada"] - resultado["stop_loss"]
).abs()

resultado["R"] = (
    direccion * (resultado["salida"] - resultado["entrada"])
) / riesgo

resultado.to_parquet(
    "resultados_backtesting.parquet",
    index=False
)

print("\n=== RESULTADOS DEL BACKTESTING ===")
print("Operaciones:", len(resultado))
print("Ganadoras:", (resultado["R"] > 0).sum())
print("Perdedoras:", (resultado["R"] < 0).sum())
print("Win rate:", round((resultado["R"] > 0).mean() * 100, 2), "%")
print("R promedio:", round(resultado["R"].mean(), 4))
print("R acumulado:", round(resultado["R"].sum(), 2))

print("\n=== RESULTADOS POR ACCION ===")
print(resultado.groupby("symbol")["R"].agg(
    ["count", "mean", "sum"]
))

print("\n=== MOTIVOS DE SALIDA ===")
print(resultado["motivo_salida"].value_counts())

print("\nArchivo resultados_backtesting.parquet creado.")
