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
