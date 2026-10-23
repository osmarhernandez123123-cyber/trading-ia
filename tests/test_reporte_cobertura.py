"""Pruebas sintéticas sin acceso a red ni precios reales."""

import json

import pandas as pd
import pytest

from trading_ia.calendario import minutos_esperados
from trading_ia.reporte_cobertura import crear_reporte_cobertura, main


def barras(symbol, minutos):
    return pd.DataFrame({"symbol": symbol, "timestamp": minutos})


def test_cobertura_por_simbolo_y_sesiones_totalmente_ausentes():
    dia1 = minutos_esperados("2026-01-05")
    dia2 = minutos_esperados("2026-01-06")
    datos = pd.concat([
        barras("AAPL", dia1),
        barras("MSFT", dia1.delete(30)),
        barras("MSFT", dia2),
    ], ignore_index=True)
    reporte = crear_reporte_cobertura(
        datos, fuente="IEX", inicio="2026-01-05", fin="2026-01-06"
    )
    assert reporte["resumen"] == {
        "simbolos": 2, "sesiones_por_simbolo": 2,
        "minutos_esperados": 1560, "minutos_presentes": 1169,
        "minutos_faltantes": 391, "fraccion_cobertura": round(1169 / 1560, 6),
    }
    sesiones = {(r["symbol"], r["fecha"]): r for r in reporte["sesiones"]}
    assert sesiones[("AAPL", "2026-01-06")]["estado"] == "sin_datos"
    assert sesiones[("AAPL", "2026-01-06")]["minutos_faltantes"] == 390
    assert sesiones[("MSFT", "2026-01-05")]["minutos_faltantes"] == 1
    assert reporte["filas_fuera_regular"] == 0
    assert "no prueban un fallo" in reporte["advertencia"]


def test_cierre_anticipado_y_fuera_de_sesion_no_cuentan_como_cobertura():
    minutos = minutos_esperados("2026-11-27")
    assert len(minutos) == 210
    fuera = pd.DatetimeIndex([minutos[0] - pd.Timedelta(minutes=1)])
    datos = barras("AAPL", minutos.append(fuera))
    reporte = crear_reporte_cobertura(datos, fuente="SIP")
    assert reporte["filas_fuera_regular"] == 1
    assert reporte["sesiones"][0]["estado"] == "completa_cierre_anticipado"
    assert reporte["sesiones"][0]["minutos_faltantes"] == 0


@pytest.mark.parametrize("simbolo", [None, "", "  ", 42])
def test_rechaza_simbolos_invalidos(simbolo):
    datos = barras("AAPL", minutos_esperados("2026-01-05")[:2])
    datos["symbol"] = datos["symbol"].astype(object)
    datos.loc[0, "symbol"] = simbolo
    with pytest.raises(ValueError, match="Símbolo"):
        crear_reporte_cobertura(datos, fuente="IEX")


def test_rechaza_naive_y_duplicados_y_fuera_de_rango():
    datos = barras("AAPL", minutos_esperados("2026-01-05")[:2])
    naive = datos.copy()
    naive["timestamp"] = naive["timestamp"].dt.tz_localize(None)
    with pytest.raises(ValueError, match="zona horaria"):
        crear_reporte_cobertura(naive, fuente="IEX")
    duplicado = pd.concat([datos, datos.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicadas"):
        crear_reporte_cobertura(duplicado, fuente="IEX")
    with pytest.raises(ValueError, match="fuera del rango"):
        crear_reporte_cobertura(datos, fuente="IEX", inicio="2026-01-06", fin="2026-01-06")


def test_cli_csv_local_sin_credenciales(tmp_path):
    datos = barras("AAPL", minutos_esperados("2026-01-05")[:2])
    entrada = tmp_path / "datos.csv"
    salida = tmp_path / "reportes" / "cobertura.json"
    datos.to_csv(entrada, index=False)
    assert main([str(entrada), "--fuente", "IEX", "--salida", str(salida)]) == 0
    reporte = json.loads(salida.read_text(encoding="utf-8"))
    assert reporte["resumen"]["minutos_faltantes"] == 388
    assert reporte["fuente"] == "IEX"
    assert "ALPACA" not in salida.read_text(encoding="utf-8")
