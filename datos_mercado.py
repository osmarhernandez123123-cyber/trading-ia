
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

load_dotenv()

api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")

if not api_key or not secret_key:
    raise ValueError("Faltan credenciales en .env")

client = StockHistoricalDataClient(api_key, secret_key)

simbolos = ["AAPL", "MSFT", "NVDA"]

# Primer periodo de prueba: 5 dias
fin = datetime.now(timezone.utc) - timedelta(days=1)
inicio = fin - timedelta(days=30)

resultados = []

for simbolo in simbolos:
    print(f"Descargando {simbolo}...")

    request = StockBarsRequest(
        symbol_or_symbols=simbolo,
        timeframe=TimeFrame.Minute,
        start=inicio,
        end=fin,
        feed=DataFeed.IEX
    )

    # El SDK recupera las paginas de resultados
    bars = client.get_stock_bars(request)
    df = bars.df

    if df.empty:
        print(f"Sin datos para {simbolo}")
        continue

    resultados.append(df)
    print(f"{simbolo}: {len(df)} velas descargadas")

if not resultados:
    raise RuntimeError("No se descargaron datos")

datos = pd.concat(resultados).sort_index()

print("\n=== RESUMEN ===")
print(datos.groupby(level="symbol").size())

print("\nDuplicados:", datos.index.duplicated().sum())
print("Valores faltantes:", datos.isna().sum().sum())

datos.to_parquet("datos_acciones_30dias.parquet")
print("\nArchivo actualizado correctamente")
