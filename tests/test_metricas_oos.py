"""Regresiones sintéticas de métricas OOS; no consulta mercado ni broker."""
from datetime import date, timedelta

import pandas as pd
import pytest

from trading_ia.metricas_oos import evaluar_prueba
from trading_ia.validacion_temporal import crear_ventanas


def ventana():
    sesiones = [date(2026, 1, 1) + timedelta(days=i) for i in range(12)]
    return crear_ventanas(
        sesiones, entrenamiento=3, validacion=2, prueba=2, embargo=1,
    )[0]


def operaciones():
    # Fechas NY: 8 y 9 de enero; todos los timestamps son UTC explícitos.
    return pd.DataFrame([
        {
            "symbol": "AAPL", "entrada_timestamp": "2026-01-08T15:30:00Z",
            "salida_timestamp": "2026-01-08T15:35:00Z",
            "pnl_usd": 100.0, "riesgo_total": 100.0, "R": 1.0,
        },
        {
            "symbol": "MSFT", "entrada_timestamp": "2026-01-09T15:30:00Z",
            "salida_timestamp": "2026-01-09T15:35:00Z",
            "pnl_usd": -50.0, "riesgo_total": 100.0, "R": -0.5,
        },
        {
            "symbol": "NVDA", "entrada_timestamp": "2026-01-09T15:40:00Z",
            "salida_timestamp": "2026-01-09T15:45:00Z",
            "pnl_usd": 0.0, "riesgo_total": 100.0, "R": 0.0,
        },
    ])


def test_resumen_neto_oos_y_drawdown_solo_realizado():
    original = operaciones()
    copia = original.copy(deep=True)
    resultado = evaluar_prueba(original, ventana())
    assert resultado["inicio_prueba"] == "2026-01-08"
    assert resultado["fin_prueba"] == "2026-01-09"
    assert resultado["operaciones"] == 3
    assert (resultado["ganadoras"], resultado["perdedoras"], resultado["neutras"]) == (1, 1, 1)
    assert resultado["pnl_realizado_usd"] == 50.0
    assert resultado["retorno_realizado_pct"] == pytest.approx(0.05)
    assert resultado["tasa_acierto_pct"] == pytest.approx(100 / 3)
    assert resultado["expectativa_r"] == pytest.approx(1 / 6)
    assert resultado["drawdown_realizado_pct"] == pytest.approx(
        (100050 / 100100 - 1) * 100
    )
    assert "no mide" in resultado["advertencia"]
    pd.testing.assert_frame_equal(original, copia)
    assert evaluar_prueba(original.iloc[::-1], ventana()) == resultado


def test_sin_operaciones_no_inventa_tasa_acierto_ni_expectativa():
    resultado = evaluar_prueba(operaciones().iloc[:0], ventana())
    assert resultado["operaciones"] == 0
    assert resultado["tasa_acierto_pct"] is None
    assert resultado["expectativa_r"] is None
    assert resultado["pnl_realizado_usd"] == 0.0
    assert resultado["drawdown_realizado_pct"] == 0.0


@pytest.mark.parametrize("columna,valor,patron", [
    ("entrada_timestamp", "2026-01-06T15:30:00Z", "fuera del bloque"),
    ("salida_timestamp", "2026-01-10T15:35:00Z", "fuera del bloque"),
    ("entrada_timestamp", "2026-01-08 15:30:00", "zona horaria"),
    ("salida_timestamp", "2026-01-08 15:35:00", "zona horaria"),
    ("entrada_timestamp", "2026-01-08T15:36:00Z", "anterior"),
    ("pnl_usd", float("nan"), "finitos"),
    ("pnl_usd", float("inf"), "finitos"),
    ("riesgo_total", 0, "positivo"),
    ("riesgo_total", -1, "positivo"),
    ("R", 10.0, "no coincide"),
    ("symbol", None, "Símbolo"),
])
def test_rechaza_datos_invalidos_y_leakage(columna, valor, patron):
    df = operaciones()
    df.loc[0, columna] = valor
    with pytest.raises(ValueError, match=patron):
        evaluar_prueba(df, ventana())


def test_no_acepta_operacion_nocturna_entre_dos_fechas_de_prueba():
    df = operaciones().iloc[[0]].copy()
    df.loc[0, "salida_timestamp"] = "2026-01-09T15:35:00Z"
    with pytest.raises(ValueError, match="nocturna"):
        evaluar_prueba(df, ventana())


def test_rechaza_operaciones_duplicadas():
    df = pd.concat([operaciones(), operaciones().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicadas"):
        evaluar_prueba(df, ventana())


@pytest.mark.parametrize("capital", [0, -1, True, float("inf"), float("nan")])
def test_capital_inicial_invalido(capital):
    with pytest.raises(ValueError, match="capital_inicial"):
        evaluar_prueba(operaciones(), ventana(), capital_inicial=capital)


def test_salida_simultanea_se_agrega_sin_drawdown_artificial():
    df = operaciones().iloc[:2].copy()
    df.loc[1, "entrada_timestamp"] = "2026-01-08T15:31:00Z"
    df.loc[1, "salida_timestamp"] = "2026-01-08T15:35:00Z"
    df.loc[1, "pnl_usd"] = -200.0
    df.loc[1, "R"] = -2.0
    resultado = evaluar_prueba(df, ventana())
    assert resultado["pnl_realizado_usd"] == -100.0
    assert resultado["drawdown_realizado_pct"] == pytest.approx(-0.1)


def test_rechaza_columnas_faltantes():
    with pytest.raises(ValueError, match="Columnas"):
        evaluar_prueba(operaciones().drop(columns=["R"]), ventana())
