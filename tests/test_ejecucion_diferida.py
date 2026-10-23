"""Pruebas del modelo causal diferido; no usan datos de mercado reales."""
from dataclasses import replace
import json

import pandas as pd
import pytest

from trading_ia.backtest import Configuracion, simular
from trading_ia.calendario import minutos_esperados
from trading_ia.ejecucion import preparar_diferido
from trading_ia.investigacion import ejecutar, sha256
from trading_ia.transformaciones import preparar


def muestra():
    minutos = minutos_esperados("2026-01-05")
    df = pd.DataFrame({
        "symbol": "TEST", "timestamp": minutos,
        "open": 100.0, "high": 100.1, "low": 99.9,
        "close": 100.0, "volume": 1000,
        "ATR_14": 1.0, "SENAL": "NO TRADE",
    })
    df.loc[20, "SENAL"] = "LONG"
    return df


def test_referencia_se_congela_al_cierre_de_senal():
    df = muestra()
    original = preparar_diferido(df)
    assert len(original) == 1
    assert original.entrada_timestamp.iloc[0] == df.timestamp.iloc[22]
    assert original.precio_referencia_senal.iloc[0] == 100
    assert original.stop_loss.iloc[0] == 98.5
    assert original.take_profit.iloc[0] == 103.0

    # Los niveles ex ante no pueden cambiar al alterar precios posteriores.
    cambiado = df.copy(deep=True)
    cambiado.loc[21, "open"] = 110
    cambiado.loc[22, ["open", "high", "low", "close"]] = [125, 126, 124, 125]
    nuevo = preparar_diferido(cambiado)
    pd.testing.assert_frame_equal(original, nuevo, check_exact=True)

    # V3.1, como referencia, sí recalcula sus niveles con el open siguiente.
    baseline = preparar(df)
    baseline_cambiada = preparar(cambiado)
    assert baseline.stop_loss.iloc[0] != baseline_cambiada.stop_loss.iloc[0]


def test_no_cruza_barras_ausentes_o_sesiones():
    df = muestra()
    assert preparar_diferido(df.drop(index=21)).empty
    final = df.copy()
    final["SENAL"] = "NO TRADE"
    final.loc[len(final) - 2, "SENAL"] = "LONG"
    assert preparar_diferido(final).empty


def test_configuracion_diferida_respetada_por_motor():
    df = muestra()
    candidatas = preparar_diferido(df)
    with pytest.raises(ValueError, match="continuidad"):
        simular(df, candidatas)
    operaciones, rechazos, curva = simular(
        df, candidatas, replace(Configuracion(), LATENCIA_VELAS=1)
    )
    assert len(operaciones) == 1
    assert rechazos.empty
    assert operaciones.entrada_timestamp.iloc[0] == df.timestamp.iloc[22]
    assert not curva.empty


def test_motor_no_acepta_barra_intermedia_ausente():
    df = muestra()
    candidatas = preparar_diferido(df)
    incompleto = df.drop(index=21)
    with pytest.raises(ValueError, match="intermedia"):
        simular(
            incompleto,
            candidatas,
            replace(Configuracion(), LATENCIA_VELAS=1),
            exigir_calidad=False,
        )


def test_modelo_invalido_y_entrada_por_gap_rechazada():
    df = muestra()
    with pytest.raises(ValueError, match="latencia_velas"):
        preparar_diferido(df, latencia_velas=2)
    c = preparar_diferido(df)
    with pytest.raises(ValueError, match="LATENCIA_VELAS"):
        simular(df, c, replace(Configuracion(), LATENCIA_VELAS=2))

    # Se conoce el gap únicamente en el minuto de entrada. Los niveles de
    # stop/TP no se recalculan con ese dato, y la operación se rechaza.
    df.loc[22, ["open", "high", "low", "close"]] = [106, 106.1, 99.9, 100]
    operaciones, rechazos, _ = simular(
        df, c, replace(Configuracion(), LATENCIA_VELAS=1)
    )
    assert operaciones.empty
    assert rechazos.motivo.tolist() == ["NIVELES_INVALIDOS_TRAS_SLIPPAGE"]


def test_pipeline_local_diferido_reproducible(tmp_path):
    origen = tmp_path / "dataset.parquet"
    muestra().drop(columns=["ATR_14", "SENAL"]).to_parquet(origen, index=False)
    meta = {
        "tipo": "sintetico", "fuente": "fixture", "licencia": "pruebas",
        "ajuste": "sin ajuste", "dataset_id": "prueba-diferida",
    }
    salida = tmp_path / "diferido"
    assert ejecutar(origen, sha256(origen), salida, meta, "diferido_1m") == 0
    reporte = json.loads((salida / "ejecucion.json").read_text())
    assert reporte["estado"] == "OK"
    assert reporte["modelo_ejecucion"] == "diferido_1m"
    assert reporte["parametros"]["LATENCIA_VELAS"] == 1
    assert (salida / "candidatas.parquet").exists()


@pytest.mark.parametrize("simbolo", [None, "", "   "])
def test_diferido_no_descarta_simbolos_invalidos(simbolo):
    datos = muestra()
    datos.loc[20, "symbol"] = simbolo
    with pytest.raises(ValueError, match="Símbolo inválido"):
        preparar_diferido(datos)


@pytest.mark.parametrize("senal", [None, "", "BUY", "DESCONOCIDA"])
def test_diferido_rechaza_categorias_desconocidas(senal):
    datos = muestra()
    datos.loc[20, "SENAL"] = senal
    with pytest.raises(ValueError, match="Categoría de señal inválida"):
        preparar_diferido(datos)


@pytest.mark.parametrize("atr", [None, float("nan"), 0.0, -1.0, float("inf")])
def test_diferido_rechaza_atr_invalido_en_nueva_senal(atr):
    datos = muestra()
    datos.loc[20, "ATR_14"] = atr
    with pytest.raises(ValueError, match="Distancia ATR inválida"):
        preparar_diferido(datos)


@pytest.mark.parametrize("cierre", [None, float("nan"), 0.0, -5.0, float("inf")])
def test_diferido_rechaza_precio_invalido_en_nueva_senal(cierre):
    datos = muestra()
    datos.loc[20, "close"] = cierre
    with pytest.raises(ValueError, match="Precio de señal inválido"):
        preparar_diferido(datos)


def test_diferido_acepta_calentamiento_sin_atr():
    datos = muestra()
    datos.loc[0, "ATR_14"] = float("nan")
    assert len(preparar_diferido(datos)) == 1


def test_diferido_rechaza_timestamp_sin_zona_horaria():
    datos = muestra()
    datos["timestamp"] = datos["timestamp"].dt.tz_localize(None)
    with pytest.raises(ValueError, match="zona horaria"):
        preparar_diferido(datos)


def test_diferido_rechaza_timestamps_duplicados():
    datos = muestra()
    datos = pd.concat([datos, datos.iloc[[20]]], ignore_index=True)
    with pytest.raises(ValueError, match="Timestamps duplicados"):
        preparar_diferido(datos)
