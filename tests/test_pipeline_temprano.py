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


def datos_regulares_completos():
    timestamps = minutos_esperados("2026-11-27")
    return pd.DataFrame({
        "symbol": "AAPL", "timestamp": timestamps,
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
        "volume": 1_000,
    })


def ejecutar_indicadores(monkeypatch, datos, escrituras):
    monkeypatch.setattr(pd, "read_parquet", lambda *args, **kwargs: datos.copy())
    monkeypatch.setattr(
        pd.DataFrame, "to_parquet",
        lambda self, *args, **kwargs: escrituras.append(self.copy()),
    )
    monkeypatch.setattr(Path, "replace", lambda self, target: target)
    runpy.run_path("indicadores.py", run_name="__pipeline_test__")


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


def test_duplicado_extendido_no_puede_ocultarse_al_filtrar(monkeypatch):
    datos = datos_regulares_completos()
    premarket = datos.iloc[[0]].copy()
    premarket["timestamp"] = pd.Timestamp(
        "2026-11-27 08:00", tz="America/New_York"
    ).tz_convert("UTC")
    datos = pd.concat([premarket, premarket, datos], ignore_index=True)
    escrituras = []
    monkeypatch.setattr(pd, "read_parquet", lambda *args, **kwargs: datos.copy())
    monkeypatch.setattr(
        pd.DataFrame, "to_parquet",
        lambda self, *args, **kwargs: escrituras.append(self.copy()),
    )
    with pytest.raises(ValueError, match="DUPLICADO"):
        runpy.run_path("indicadores.py", run_name="__pipeline_test__")
    assert escrituras == []


def test_extendido_legitimo_se_valida_y_luego_se_excluye(monkeypatch):
    regulares = datos_regulares_completos()
    premarket = regulares.iloc[[0]].copy()
    premarket["timestamp"] = pd.Timestamp(
        "2026-11-27 08:00", tz="America/New_York"
    ).tz_convert("UTC")
    escrituras = []
    ejecutar_indicadores(
        monkeypatch, pd.concat([premarket, regulares], ignore_index=True), escrituras
    )
    assert len(escrituras) == 1
    salida = escrituras[0]
    assert len(salida) == len(regulares)
    horas = salida["timestamp"].dt.tz_convert("America/New_York").dt.hour
    assert horas.min() >= 9


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
