"""Auditoría sintética de riesgo OOS: sin brokers, claves ni históricos."""
from datetime import date, timedelta

import pandas as pd
import pytest

from trading_ia.auditoria_riesgo_oos import auditar_riesgo_oos
from trading_ia.validacion_temporal import crear_ventanas


def ventana():
    fechas = [date(2026, 1, 1) + timedelta(days=i) for i in range(12)]
    return crear_ventanas(
        fechas, entrenamiento=3, validacion=2, prueba=2, embargo=1
    )[0]


def operaciones(n=3, *, riesgo=1000.0):
    return pd.DataFrame([
        {
            "symbol": f"TEST{i}",
            "entrada_timestamp": "2026-01-08T15:00:00Z",
            "salida_timestamp": "2026-01-08T15:05:00Z",
            "pnl_usd": 100.0,
            "riesgo_total": riesgo,
            "R": 100.0 / riesgo,
        }
        for i in range(n)
    ])


def test_tres_posiciones_al_uno_por_ciento_permitidas_sin_mutacion():
    datos = operaciones()
    original = datos.copy(deep=True)
    resultado = auditar_riesgo_oos(datos, ventana())
    assert resultado["operaciones"] == 3
    assert resultado["pico_riesgo_simultaneo_usd"] == 3000.0
    assert resultado["pico_riesgo_simultaneo_pct"] == 3.0
    assert "capital inicial fijo" in resultado["advertencia"]
    pd.testing.assert_frame_equal(datos, original)
    assert auditar_riesgo_oos(datos.iloc[::-1], ventana()) == resultado


def test_rechaza_cuarta_posicion_simultanea():
    with pytest.raises(ValueError, match="simultáneo supera"):
        auditar_riesgo_oos(operaciones(4), ventana())


def test_rechaza_riesgo_individual_superior_al_uno_por_ciento():
    with pytest.raises(ValueError, match="por operación supera"):
        auditar_riesgo_oos(operaciones(1, riesgo=1001), ventana())


def test_salida_libera_riesgo_antes_de_entrada_en_mismo_instante():
    datos = operaciones(4)
    datos.loc[3, "entrada_timestamp"] = "2026-01-08T15:05:00Z"
    datos.loc[3, "salida_timestamp"] = "2026-01-08T15:10:00Z"
    resultado = auditar_riesgo_oos(datos, ventana())
    assert resultado["pico_riesgo_simultaneo_usd"] == 3000.0


def test_intervalo_de_duracion_cero_no_consume_presupuesto_simultaneo():
    datos = operaciones(4)
    datos.loc[3, "salida_timestamp"] = datos.loc[3, "entrada_timestamp"]
    assert auditar_riesgo_oos(datos, ventana())[
        "pico_riesgo_simultaneo_usd"
    ] == 3000.0


def test_bloque_vacio_reporta_cero_sin_inventar_exposicion():
    resultado = auditar_riesgo_oos(operaciones().iloc[:0], ventana())
    assert resultado["operaciones"] == 0
    assert resultado["pico_riesgo_simultaneo_pct"] == 0.0


@pytest.mark.parametrize("limite", [0, -1, True, "1", float("nan"), 101])
def test_rechaza_limite_individual_invalido(limite):
    with pytest.raises(ValueError, match="limite_operacion_pct"):
        auditar_riesgo_oos(
            operaciones(1), ventana(), limite_operacion_pct=limite
        )


def test_rechaza_limite_simultaneo_inferior_al_individual():
    with pytest.raises(ValueError, match="menor al individual"):
        auditar_riesgo_oos(
            operaciones(1), ventana(),
            limite_operacion_pct=2, limite_simultaneo_pct=1,
        )


def test_no_omite_validaciones_oos_anteriores():
    datos = operaciones(1)
    datos.loc[0, "R"] = 999.0
    with pytest.raises(ValueError, match="R no coincide"):
        auditar_riesgo_oos(datos, ventana())
