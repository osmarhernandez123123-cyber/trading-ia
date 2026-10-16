"""Acceso exclusivamente de lectura a Alpaca Paper Trading.

Este módulo nunca construye peticiones de envío de órdenes.
La integración de ejecución simulada se añade por separado tras pruebas
de riesgo, idempotencia, reconciliación y apagado de emergencia.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Callable, Mapping
import os


PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
KEY_NAME = "ALPACA_PAPER_API_KEY"
SECRET_NAME = "ALPACA_PAPER_SECRET_KEY"


@dataclass(frozen=True, repr=False)
class CredencialesPaper:
    api_key: str = field(repr=False)
    secret_key: str = field(repr=False)

    def __post_init__(self):
        if not self.api_key or not self.secret_key:
            raise ValueError("Faltan credenciales específicas de Alpaca PAPER")

    def __repr__(self):
        return "CredencialesPaper(api_key=<oculto>, secret_key=<oculto>)"


@dataclass(frozen=True)
class ResumenCuentaPaper:
    estado: str
    moneda: str
    patrimonio: Decimal
    efectivo: Decimal
    poder_compra: Decimal


def leer_credenciales_paper(entorno: Mapping[str, str] | None = None) -> CredencialesPaper:
    """Usa únicamente claves con nombres explícitos PAPER; no usa claves live."""
    entorno = os.environ if entorno is None else entorno
    api_key = entorno.get(KEY_NAME, "").strip()
    secret_key = entorno.get(SECRET_NAME, "").strip()
    if not api_key or not secret_key:
        raise ValueError(
            f"Configura solo {KEY_NAME} y {SECRET_NAME} en un gestor seguro; "
            "no las publiques en GitHub ni en el chat"
        )
    return CredencialesPaper(api_key=api_key, secret_key=secret_key)


def _monto(valor, nombre):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Campo monetario inválido: {nombre}") from exc
    if not numero.is_finite():
        raise ValueError(f"Campo monetario no finito: {nombre}")
    return numero


class LectorAlpacaPaper:
    """Solo expone lectura de cuenta. Sin API de envío/cancelación de órdenes."""

    def __init__(self, cliente):
        self._cliente = cliente

    def resumen(self) -> ResumenCuentaPaper:
        cuenta = self._cliente.get_account()
        return ResumenCuentaPaper(
            estado=str(getattr(cuenta.status, "value", cuenta.status)),
            moneda=str(getattr(cuenta, "currency", "USD")),
            patrimonio=_monto(cuenta.equity, "patrimonio"),
            efectivo=_monto(cuenta.cash, "efectivo"),
            poder_compra=_monto(cuenta.buying_power, "poder_compra"),
        )


def crear_lector_alpaca_paper(
    entorno: Mapping[str, str] | None = None,
    fabrica_cliente: Callable | None = None,
) -> LectorAlpacaPaper:
    """La única factoría permite paper=True y URL paper, nunca live.

    fabrica_cliente sirve exclusivamente para pruebas sin red.
    """
    credenciales = leer_credenciales_paper(entorno)
    if fabrica_cliente is None:
        from alpaca.trading.client import TradingClient
        fabrica_cliente = TradingClient

    cliente = fabrica_cliente(
        api_key=credenciales.api_key,
        secret_key=credenciales.secret_key,
        paper=True,
        url_override=PAPER_ENDPOINT,
    )
    return LectorAlpacaPaper(cliente)
