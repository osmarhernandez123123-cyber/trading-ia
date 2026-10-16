"""Las pruebas no acceden a Internet ni a credenciales de usuario."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from trading_ia.alpaca_paper import (
    CredencialesPaper,
    KEY_NAME,
    PAPER_ENDPOINT,
    SECRET_NAME,
    crear_lector_alpaca_paper,
    leer_credenciales_paper,
)


class ClienteFalso:
    def get_account(self):
        return SimpleNamespace(
            status="ACTIVE",
            currency="USD",
            equity="100000.50",
            cash="90000.10",
            buying_power="180000.20",
            account_number="NO_REGISTRAR",
        )

    def submit_order(self, *args, **kwargs):
        raise AssertionError("Nunca debe llamarse submit_order")


def test_cuenta_de_papel_solo_lectura_y_endpoint_forzado():
    captura = {}

    def fabrica_cliente(**kwargs):
        captura.update(kwargs)
        return ClienteFalso()

    lector = crear_lector_alpaca_paper(
        {KEY_NAME: "clave-ficticia", SECRET_NAME: "secreto-ficticio"},
        fabrica_cliente,
    )
    assert captura["paper"] is True
    assert captura["url_override"] == PAPER_ENDPOINT
    assert PAPER_ENDPOINT == "https://paper-api.alpaca.markets"
    assert lector.resumen().patrimonio == Decimal("100000.50")
    assert lector.resumen().efectivo == Decimal("90000.10")
    assert "account_number" not in lector.resumen().__dict__
    assert not hasattr(lector, "submit_order")
    assert not hasattr(lector, "cancel_order")


def test_credenciales_paper_son_obligatorias_y_no_hay_fallback_live():
    with pytest.raises(ValueError, match="PAPER"):
        leer_credenciales_paper({
            "ALPACA_API_KEY": "solo-live",
            "ALPACA_SECRET_KEY": "solo-live",
        })
    with pytest.raises(ValueError, match="PAPER"):
        leer_credenciales_paper({KEY_NAME: "parcial"})
    with pytest.raises(ValueError, match="PAPER"):
        leer_credenciales_paper({})
    credenciales = leer_credenciales_paper({
        KEY_NAME: " clave-papel ",
        SECRET_NAME: " secreto-papel ",
    })
    assert credenciales.api_key == "clave-papel"
    assert credenciales.secret_key == "secreto-papel"
    assert "secreto-papel" not in repr(credenciales)
    assert "clave-papel" not in repr(credenciales)


def test_montos_invalidos_rechazados():
    class ClienteNaN:
        def get_account(self):
            return SimpleNamespace(
                status="ACTIVE", currency="USD", equity="NaN",
                cash="1", buying_power="2",
            )
    lector = crear_lector_alpaca_paper(
        {KEY_NAME: "prueba", SECRET_NAME: "prueba"},
        lambda **kwargs: ClienteNaN(),
    )
    with pytest.raises(ValueError, match="no finito"):
        lector.resumen()
