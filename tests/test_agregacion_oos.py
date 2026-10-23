"""Pruebas con operaciones sintéticas; sin red ni broker."""
from datetime import date, timedelta
from dataclasses import replace

import pandas as pd
import pytest

from trading_ia.agregacion_oos import agregar_pruebas
from trading_ia.validacion_temporal import crear_ventanas


def ventanas():
    sesiones = [date(2026, 1, 1) + timedelta(days=i) for i in range(15)]
    return crear_ventanas(sesiones, entrenamiento=3, validacion=2,
                          prueba=2, embargo=1)[:2]


def operacion(dia, minuto, pnl, riesgo=100, simbolo="TEST"):
    return dict(
        symbol=simbolo,
        entrada_timestamp=f"2026-01-{dia:02d}T15:{minuto:02d}:00Z",
        salida_timestamp=f"2026-01-{dia:02d}T15:{minuto + 1:02d}:00Z",
        pnl_usd=float(pnl), riesgo_total=float(riesgo), R=float(pnl / riesgo),
    )


def bloques():
    # Primer bloque: 2 operaciones, +1R y -0.5R; segundo: 1, +2R.
    return [
        pd.DataFrame([operacion(8, 30, 100), operacion(9, 30, -50)]),
        pd.DataFrame([operacion(10, 30, 200)]),
    ]


def test_agregacion_pondera_por_trade_y_no_suma_retornos():
    v = ventanas()
    b = bloques()
    copia = [df.copy(deep=True) for df in b]
    resultado = agregar_pruebas(v, b)
    assert resultado["ventanas"] == 2
    assert resultado["operaciones"] == 3
    assert resultado["ganadoras"] == 2
    assert resultado["pnl_realizado_suma_usd"] == 250
    assert resultado["expectativa_r_ponderada"] == pytest.approx(2.5 / 3)
    assert resultado["tasa_acierto_pct"] == pytest.approx(200 / 3)
    inferior, superior = resultado["intervalo_wilson_95_pct"]
    assert 0 <= inferior < resultado["tasa_acierto_pct"] < superior <= 100
    assert "retorno_realizado_pct" not in resultado
    assert "drawdown_realizado_pct" not in resultado
    assert "No se suman" in resultado["advertencia"]
    for original, despues in zip(copia, b):
        pd.testing.assert_frame_equal(original, despues)


def test_ventanas_vacias_sin_tasa_artificial():
    v = ventanas()
    vacio = pd.DataFrame(columns=bloques()[0].columns)
    r = agregar_pruebas(v, [vacio.copy(), vacio.copy()])
    assert r["operaciones"] == 0
    assert r["expectativa_r_ponderada"] is None
    assert r["tasa_acierto_pct"] is None
    assert r["intervalo_wilson_95_pct"] is None
    assert r["ventanas_con_operaciones"] == 0


def test_sin_operaciones_en_un_bloque_no_distorsiona_ponderacion():
    v = ventanas()
    b = bloques()
    b[0] = b[0].iloc[:0].copy()
    r = agregar_pruebas(v, b)
    assert r["operaciones"] == 1
    assert r["expectativa_r_ponderada"] == 2.0
    assert r["ventanas_con_operaciones"] == 1


def test_rechaza_ventanas_repetidas_y_desordenadas():
    v = ventanas()
    b = bloques()
    with pytest.raises(ValueError, match="solapadas"):
        agregar_pruebas([v[0], v[0]], [b[0], b[0]])
    with pytest.raises(ValueError, match="desordenadas"):
        agregar_pruebas([v[1], v[0]], [b[1], b[0]])


def test_rechaza_trades_de_entrenamiento_o_bloque_equivocado():
    v = ventanas()
    b = bloques()
    with pytest.raises(ValueError, match="fuera del bloque"):
        agregar_pruebas(v, [b[1], b[0]])


def test_rechaza_naive_y_trade_duplicado_en_bloque():
    v = ventanas()
    b = bloques()
    b[0].loc[0, "entrada_timestamp"] = "2026-01-08 15:30:00"
    with pytest.raises(ValueError, match="zona horaria"):
        agregar_pruebas(v, b)
    b = bloques()
    b[0] = pd.concat([b[0], b[0].iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicadas"):
        agregar_pruebas(v, b)


def test_rechaza_bloques_incompletos_o_parametros_invalidos():
    v = ventanas()
    b = bloques()
    with pytest.raises(ValueError, match="pareados"):
        agregar_pruebas(v, b[:1])
    with pytest.raises(ValueError, match="pareados"):
        agregar_pruebas([], [])
    with pytest.raises(ValueError, match="capital_inicial"):
        agregar_pruebas(v, b, capital_inicial=-1)


def test_rechaza_fechas_duplicadas_dentro_de_ventana():
    v = ventanas()
    bad = replace(v[0], prueba=(v[0].prueba[0], v[0].prueba[0]))
    with pytest.raises(ValueError, match="duplicadas"):
        agregar_pruebas([bad], [bloques()[0]])
