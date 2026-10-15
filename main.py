
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

# Cargar credenciales
load_dotenv()

api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")

if not api_key or not secret_key:
    raise ValueError("Faltan las credenciales en .env")

# Conectar exclusivamente a Paper Trading
client = TradingClient(
    api_key=api_key,
    secret_key=secret_key,
    paper=True
)

# Consultar la cuenta sin realizar operaciones
account = client.get_account()

print("=== SISTEMA TRADING IA ===")
print("Conexion exitosa con Alpaca Paper Trading")
print("Estado:", account.status)
print("Capital:", account.equity, "USD")
print("Efectivo:", account.cash, "USD")
print("Poder de compra:", account.buying_power, "USD")
