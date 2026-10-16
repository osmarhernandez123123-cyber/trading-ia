import json
import subprocess
import sys

import numpy as np
import pandas as pd

from trading_ia.calendario import minutos_esperados


def test_cli_genera_reporte_y_manifiesto_sin_servicios_externos(tmp_path):
    tiempos = minutos_esperados("2026-11-27")
    base = np.linspace(100, 101, len(tiempos))
    datos = pd.DataFrame({
        "symbol": "AAPL", "timestamp": tiempos, "open": base,
        "high": base + 0.2, "low": base - 0.2, "close": base + 0.1,
        "volume": 1_000,
    })
    parquet = tmp_path / "datos.parquet"
    reporte = tmp_path / "calidad.json"
    manifiesto = tmp_path / "manifiesto.json"
    datos.to_parquet(parquet, index=False)
    proceso = subprocess.run([
        sys.executable, "validar_dataset.py", str(parquet),
        "--reporte", str(reporte), "--manifiesto", str(manifiesto),
        "--dataset-id", "sintetico", "--version", "1",
        "--fuente", "fixture local", "--licencia", "sintético",
    ], capture_output=True, text=True, check=False)
    assert proceso.returncode == 0, proceso.stderr
    assert json.loads(reporte.read_text())["valido"]
    assert json.loads(manifiesto.read_text())["artifact"]["sha256"]


def test_cli_iex_clasifica_hueco_sin_aprobar_indicadores(tmp_path):
    tiempos = minutos_esperados("2026-11-27").delete(10)
    datos = pd.DataFrame({
        "symbol": "AAPL", "timestamp": tiempos, "open": 100.0,
        "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1_000,
    })
    parquet = tmp_path / "datos.parquet"
    reporte = tmp_path / "calidad.json"
    manifiesto = tmp_path / "manifiesto.json"
    datos.to_parquet(parquet, index=False)
    proceso = subprocess.run([
        sys.executable, "validar_dataset.py", str(parquet),
        "--reporte", str(reporte), "--manifiesto", str(manifiesto),
        "--dataset-id", "iex-incompleto", "--version", "1",
        "--fuente", "fixture IEX", "--licencia", "sintético",
        "--politica-huecos", "iex-conservadora",
    ], capture_output=True, text=True, check=False)
    calidad = json.loads(reporte.read_text())
    assert proceso.returncode == 2
    assert calidad["valido"]
    assert not calidad["apto_indicadores"]
    assert calidad["politica_huecos"] == "iex_conservadora"
