"""Regresiones sintéticas del estrés de costes OOS; sin red ni órdenes."""
from datetime import date, timedelta

import pandas as pd
import pytest

from trading_ia.estres_costes_oos import evaluar_estres_costes
from trading_ia.validacion_temporal import crear_ventanas


def ventana():
    fechas = [date(2026, 1, 1) + timedelta(days=i) for i in range(12)]
    return crear_ventanas(
        fechas, entrenamiento=3, validacion=2, prueba=2, embargo=1
    )[0]


def operaciones():
    return pd.DataFrame([
        {
            "symbol": "AAPL", "entrada_timestamp": "2026-01-08T15:30:00Z",
            "salida_timestamp": "2026-01-08T15:35:00Z",
            "pnl_usd": 100.0, "riesgo_total": 100.0, "R": 1.0,
            "nocional": 1000.0,
        },
        {
            "symbol": "MSFT", "entrada_timestamp": "2026-01-09T15:30:00Z",
            "salida_timestamp": "2026-01-09T15:35:00Z",
            "pnl_usd": -50.0, "riesgo_total": 100.0, "R": -0.5,
            "nocional": 2000.0,
        },
        {
            "symbol": "NVDA", "entrada_timestamp": "2026-01-09T15:40:00Z",
            "salida_timestamp": "2026-01-09T15:45:00Z",
            "pnl_usd": 0.0, "riesgo_total": 100.0, "R": 0.0,
            "nocional": 3000.0,
        },
    ])


def test_penalizacion_por_dos_lados_sin_modificar_operaciones():
    original = operaciones()
    copia = original.copy(deep=True)
    r = evaluar_estres_costes(original, ventana(), coste_extra_bps_lado=10)
    assert r["coste_extra_total_usd"] == pytest.approx(12.0)
    assert r["baseline"]["pnl_realizado_usd"] == 50.0
    assert r["estresado"]["pnl_realizado_usd"] == pytest.approx(38.0)
    assert r["estresado"]["expectativa_r"] == pytest.approx((.98 - .54 - .06) / 3)
    assert r["estresado"]["ganadoras"] == 1
    assert r["estresado"]["perdedoras"] == 2
    assert "NO optimización" in r["advertencia"]
    pd.testing.assert_frame_equal(original, copia)


def test_cero_coste_reproduce_baseline():
    r = evaluar_estres_costes(operaciones(), ventana(), coste_extra_bps_lado=0)
    assert r["coste_extra_total_usd"] == 0
    assert r["baseline"] == r["estresado"]


def test_sin_operaciones_no_inventa_resultados():
    df = operaciones().iloc[:0]
    r = evaluar_estres_costes(df, ventana(), coste_extra_bps_lado=20)
    assert r["estresado"]["operaciones"] == 0
    assert r["estresado"]["expectativa_r"] is None
    assert r["coste_extra_total_usd"] == 0


@pytest.mark.parametrize("coste", [-1, True, None, float("nan"), float("inf"), "10"])
def test_rechaza_costes_invalidos(coste):
    with pytest.raises(ValueError, match="coste_extra_bps_lado"):
        evaluar_estres_costes(operaciones(), ventana(), coste_extra_bps_lado=coste)


@pytest.mark.parametrize("nocional", [0, -1, None, float("nan"), float("inf")])
def test_rechaza_nocional_invalido(nocional):
    df = operaciones()
    df.loc[0, "nocional"] = nocional
    with pytest.raises(ValueError, match="nocional"):
        evaluar_estres_costes(df, ventana(), coste_extra_bps_lado=10)



@pytest.mark.parametrize("nocional", ["1000.0", True, False])
def test_rechaza_nocional_convertible_pero_no_numerico(nocional):
    df = operaciones()
    df["nocional"] = pd.Series(
        [nocional, 2000.0, 3000.0], dtype="object"
    )
    with pytest.raises(ValueError, match="valores numéricos"):
        evaluar_estres_costes(df, ventana(), coste_extra_bps_lado=10)


def test_nocional_grande_no_desborda_en_multiplicacion_intermedia():
    df = operaciones().iloc[:1].copy()
    df["nocional"] = 1e308
    resultado = evaluar_estres_costes(df, ventana(), coste_extra_bps_lado=1)
    assert resultado["coste_extra_total_usd"] == pytest.approx(2e304)
    assert resultado["estresado"]["operaciones"] == 1


def test_rechaza_desbordamiento_de_coste_agregado():
    df = operaciones()
    df["nocional"] = 1e308
    # Cada coste individual es finito (8e307), pero la suma no.
    with pytest.raises(ValueError, match="agregado no finito"):
        evaluar_estres_costes(df, ventana(), coste_extra_bps_lado=4000)


def test_rechaza_falta_nocional():
    with pytest.raises(ValueError, match="nocional"):
        evaluar_estres_costes(
            operaciones().drop(columns=["nocional"]), ventana(),
            coste_extra_bps_lado=10,
        )


def test_rechaza_fechas_fuera_de_prueba_y_r_incoherente():
    df = operaciones()
    df.loc[0, "entrada_timestamp"] = "2026-01-06T15:30:00Z"
    with pytest.raises(ValueError, match="fuera del bloque"):
        evaluar_estres_costes(df, ventana(), coste_extra_bps_lado=10)
    df = operaciones()
    df.loc[0, "R"] = 3
    with pytest.raises(ValueError, match="no coincide"):
        evaluar_estres_costes(df, ventana(), coste_extra_bps_lado=10)
