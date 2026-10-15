
import pandas as pd
from pathlib import Path

ORIGEN = Path("datos_senales.parquet")
DESTINO = Path("entradas_candidatas.parquet")

df = pd.read_parquet(ORIGEN)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.sort_values(["symbol", "timestamp"]).copy()

def preparar(g):
    g = g.copy()

    anterior = g["SENAL"].shift(1)

    nueva = (
        g["SENAL"].isin(["LONG", "SHORT"])
        & g["SENAL"].ne(anterior)
    )

    # Se ejecutaria en la apertura de la siguiente vela
    g["entrada_timestamp"] = g["timestamp"].shift(-1)
    g["entrada_precio"] = g["open"].shift(-1)

    g["distancia_sl"] = g["ATR_14"] * 1.5

    g["stop_loss"] = float("nan")
    g["take_profit"] = float("nan")

    long = nueva & g["SENAL"].eq("LONG")
    short = nueva & g["SENAL"].eq("SHORT")

    g.loc[long, "stop_loss"] = (
        g.loc[long, "entrada_precio"]
        - g.loc[long, "distancia_sl"]
    )
    g.loc[long, "take_profit"] = (
        g.loc[long, "entrada_precio"]
        + 2 * g.loc[long, "distancia_sl"]
    )

    g.loc[short, "stop_loss"] = (
        g.loc[short, "entrada_precio"]
        + g.loc[short, "distancia_sl"]
    )
    g.loc[short, "take_profit"] = (
        g.loc[short, "entrada_precio"]
        - 2 * g.loc[short, "distancia_sl"]
    )

    # No cruzar dias ni huecos temporales
    diferencia = (
        g["entrada_timestamp"] - g["timestamp"]
    ).dt.total_seconds()

    entradas = g[
        nueva
        & diferencia.eq(60)
        & g["distancia_sl"].gt(0)
        & g["entrada_precio"].notna()
    ].copy()

    return entradas

entradas = pd.concat(
    [preparar(g) for _, g in df.groupby("symbol", sort=False)],
    ignore_index=True
)

entradas.to_parquet(DESTINO, index=False)

print("\n=== ENTRADAS CANDIDATAS ===")
print(
    entradas.groupby(["symbol", "SENAL"])
    .size()
    .unstack(fill_value=0)
)

print("\n=== EJEMPLOS ===")
print(
    entradas[[
        "symbol", "entrada_timestamp",
        "SENAL", "entrada_precio",
        "stop_loss", "take_profit"
    ]].tail(9).to_string(index=False)
)

print("\nArchivo creado:", DESTINO)
