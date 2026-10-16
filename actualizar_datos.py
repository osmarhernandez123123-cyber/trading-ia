
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

from trading_ia.calidad_datos import exigir_integridad_original

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

if not API_KEY or not SECRET_KEY:
    raise ValueError("Faltan credenciales en .env")

client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

BASE = Path(__file__).resolve().parent
ARCHIVO = BASE / "datos_acciones_30dias.parquet"
TEMPORAL = BASE / "datos_acciones_30dias.tmp.parquet"
BLOQUEO = BASE / ".actualizar_datos.lock"

SIMBOLOS = ["AAPL", "MSFT", "NVDA"]

if not ARCHIVO.exists():
    raise FileNotFoundError(f"No existe {ARCHIVO}")

# Evitar ejecuciones simultaneas
import fcntl

with open(BLOQUEO, "w") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)

    historico = pd.read_parquet(ARCHIVO)

    if not isinstance(historico.index, pd.MultiIndex):
        raise ValueError("Se esperaba indice symbol/timestamp")

    historico.index = historico.index.set_names(
        ["symbol", "timestamp"]
    )
    historico = historico.sort_index()

    ahora = datetime.now(timezone.utc)

    # Esperar 10 segundos tras el cierre de la vela
    fin = ahora.replace(second=0, microsecond=0)

    if ahora.second < 10:
        fin -= timedelta(minutes=1)

    resultados = [historico]
    errores = []

    for simbolo in SIMBOLOS:
        print(f"\nActualizando {simbolo}...")

        try:
            try:
                anterior = historico.xs(
                    simbolo, level="symbol"
                )
                ultimo = anterior.index.max()
                inicio = ultimo.to_pydatetime() - timedelta(
                    minutes=5
                )
            except KeyError:
                inicio = fin - timedelta(days=30)

            if inicio >= fin:
                print("Sin nuevas velas disponibles")
                continue

            request = StockBarsRequest(
                symbol_or_symbols=simbolo,
                timeframe=TimeFrame.Minute,
                start=inicio,
                end=fin,
                feed=DataFeed.IEX
            )

            nuevos = client.get_stock_bars(request).df

            if nuevos.empty:
                print("Alpaca no devolvio nuevas velas")
                continue

            tiempos = nuevos.index.get_level_values(
                "timestamp"
            )
            nuevos = nuevos[
                tiempos < pd.Timestamp(fin)
            ]

            if nuevos.empty:
                print("Sin velas cerradas disponibles")
                continue

            resultados.append(nuevos)
            print(f"Velas recibidas: {len(nuevos)}")

        except Exception as error:
            errores.append(simbolo)
            print(f"Error en {simbolo}: {error}")

    actualizado = pd.concat(resultados)

    actualizado = actualizado[
        ~actualizado.index.duplicated(keep="last")
    ].sort_index()

    exigir_integridad_original(actualizado.reset_index(), "actualizar_datos.py")

    if errores:
        raise RuntimeError(f"Actualizacion abortada sin reemplazar historico. Fallaron: {errores}")

    actualizado.to_parquet(TEMPORAL)
    TEMPORAL.replace(ARCHIVO)

    print("\n=== ACTUALIZACION COMPLETADA ===")
    print(actualizado.groupby(level="symbol").size())
    print("Duplicados:", actualizado.index.duplicated().sum())
    print("Archivo actualizado:", ARCHIVO)
