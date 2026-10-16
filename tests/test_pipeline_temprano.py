from pathlib import Path
import runpy

import pandas as pd
import pytest

from trading_ia.calendario import minutos_esperados


def datos_con_hueco():
    timestamps = minutos_esperados("2026-11-27").delete(10)
    datos = pd.DataFrame({
        "symbol": "AAPL", "timestamp": timestamps,
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
        "volume": 1_000,
    })
    return datos


def test_indicadores_no_escribe_salida_si_hay_hueco(monkeypatch):
    datos = datos_con_hueco()
    escrituras = []
    monkeypatch.setattr(pd, "read_parquet", lambda *args, **kwargs: datos.copy())
    monkeypatch.setattr(
        pd.DataFrame, "to_parquet",
        lambda self, *args, **kwargs: escrituras.append(args[0]),
    )
    with pytest.raises(ValueError, match="datos no aptos"):
        runpy.run_path("indicadores.py", run_name="__pipeline_test__")
    assert escrituras == []


@pytest.mark.parametrize(
    ("script", "extras"),
    [
        ("motor_analisis.py", {"EMA_9": 100, "EMA_21": 100, "RSI_14": 50,
                               "ATR_14": 1, "VWAP": 100, "VOL_REL": 1}),
        ("preparar_entradas.py", {"SENAL": "NO TRADE"}),
    ],
)
def test_etapas_posteriores_revalidan_artefactos_defectuosos(
    monkeypatch, script, extras
):
    datos = datos_con_hueco().assign(**extras)
    escrituras = []
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(pd, "read_parquet", lambda *args, **kwargs: datos.copy())
    monkeypatch.setattr(
        pd.DataFrame, "to_parquet",
        lambda self, *args, **kwargs: escrituras.append(args[0]),
    )
    with pytest.raises(ValueError, match="datos no aptos"):
        runpy.run_path(script, run_name="__pipeline_test__")
    assert escrituras == []
