import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from trading_ia.calendario import minutos_esperados
from trading_ia.calidad_datos import (
    crear_manifiesto,
    escribir_json,
    sha256_archivo,
    validar_ohlcv,
)


def dataset_sesion(fecha="2026-11-27", symbol="AAPL"):
    timestamps = minutos_esperados(fecha)
    base = np.arange(len(timestamps), dtype=float) / 100 + 100
    return pd.DataFrame({
        "symbol": symbol,
        "timestamp": timestamps,
        "open": base,
        "high": base + 0.2,
        "low": base - 0.2,
        "close": base + 0.1,
        "volume": 1_000,
    })


def codigos(reporte):
    return {incidencia.codigo for incidencia in reporte.incidencias}


def test_dataset_completo_de_cierre_anticipado_es_valido():
    reporte = validar_ohlcv(dataset_sesion())
    assert reporte.valido
    assert reporte.sesiones[0]["estado"] == "completa_cierre_anticipado"


def test_detecta_duplicados_desorden_hueco_y_valores_invalidos():
    datos = dataset_sesion()
    datos = datos.drop(index=10).reset_index(drop=True)
    duplicada = datos.iloc[[20]].copy()
    datos = pd.concat([datos, duplicada], ignore_index=True)
    datos.loc[5, "high"] = datos.loc[5, "low"] - 1
    datos.loc[6, "volume"] = -1
    datos.loc[7, "open"] = np.inf
    datos.loc[[0, 1]] = datos.loc[[1, 0]].to_numpy()
    reporte = validar_ohlcv(datos)
    assert not reporte.valido
    assert {"DUPLICADO", "DESORDENADO", "HUECOS_DE_SESION", "OHLC_INCONSISTENTE",
            "VOLUMEN_NEGATIVO", "VALOR_NO_FINITO"} <= codigos(reporte)


def test_detecta_festivo_y_salto_anomalo():
    datos = dataset_sesion("2026-11-30").iloc[:3].copy()
    datos.loc[1, ["open", "high", "low", "close"]] = [200, 201, 199, 200]
    festivo = datos.iloc[[0]].copy()
    festivo["timestamp"] = pd.Timestamp("2026-12-25 15:00", tz="UTC")
    datos = pd.concat([datos, festivo], ignore_index=True)
    reporte = validar_ohlcv(datos, comprobar_cobertura=False)
    assert "FUERA_DE_SESION" in codigos(reporte)
    assert "SALTO_PRECIO" in codigos(reporte)


def test_columnas_obligatorias():
    with pytest.raises(ValueError, match="volume"):
        validar_ohlcv(dataset_sesion().drop(columns="volume"))


def test_hash_manifiesto_y_json_son_verificables(tmp_path):
    datos = dataset_sesion()
    ruta = tmp_path / "historico.parquet"
    datos.to_parquet(ruta, index=False)
    esperado = hashlib.sha256(ruta.read_bytes()).hexdigest()
    assert sha256_archivo(ruta) == esperado
    manifiesto = crear_manifiesto(
        ruta, datos, "acciones-iex", "2026.10.1", "Alpaca IEX",
        "Uso autorizado por el propietario del dataset",
    )
    assert manifiesto["artifact"]["sha256"] == esperado
    assert manifiesto["data"]["rows"] == 210
    assert manifiesto["market"]["calendar"] == "XNYS"
    destino = tmp_path / "manifest.json"
    escribir_json(manifiesto, destino)
    assert json.loads(destino.read_text())["dataset_version"] == "2026.10.1"


def test_manifiesto_exige_procedencia_y_licencia(tmp_path):
    datos = dataset_sesion()
    ruta = tmp_path / "historico.parquet"
    datos.to_parquet(ruta, index=False)
    with pytest.raises(ValueError, match="obligatorios"):
        crear_manifiesto(ruta, datos, "id", "v1", "", "")
