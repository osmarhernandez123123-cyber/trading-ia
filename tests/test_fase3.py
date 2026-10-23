"""Regresiones sintéticas; ninguna prueba usa mercado real ni credenciales."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
import pandas as pd
import pytest
from trading_ia.backtest import Configuracion, simular
from trading_ia.calendario import minutos_esperados
from trading_ia.calidad_datos import validar_ohlcv
from trading_ia.eventos import Evento
from trading_ia.investigacion import ejecutar, sha256
from trading_ia.transformaciones import calcular_indicadores, analizar, preparar


def dataset():
    ts = minutos_esperados('2026-01-05')
    return pd.DataFrame({'symbol': 'TEST', 'timestamp': ts, 'open': 100., 'high': 100.1,
                         'low': 99.9, 'close': 100., 'volume': 1000})


def candidatas(df):
    return pd.DataFrame([{'symbol': 'TEST', 'timestamp': df.timestamp.iloc[0],
                          'entrada_timestamp': df.timestamp.iloc[1], 'SENAL': 'LONG',
                          'stop_loss': 99., 'take_profit': 102.}])


def test_sin_operaciones_es_resultado_valido():
    df = dataset()
    c = candidatas(df).iloc[:0]
    operaciones, rechazos, capital = simular(df, c)
    assert operaciones.empty and rechazos.empty
    assert capital.patrimonio.eq(100000).all()
    assert capital.drawdown_pct.eq(0).all()


def test_capital_insuficiente_no_falla():
    df = dataset()
    operaciones, rechazos, curva = simular(df, candidatas(df), replace(Configuracion(), CAPITAL_INICIAL=1))
    assert operaciones.empty
    assert rechazos.motivo.tolist() == ['CAPITAL_O_RIESGO_INSUFICIENTE']
    assert curva.patrimonio.eq(1).all()


def test_motor_no_muta_y_es_determinista():
    df = dataset()
    original = df.copy(deep=True)
    c = candidatas(df)
    a = simular(df, c)
    b = simular(df, c)
    for x, y in zip(a, b):
        pd.testing.assert_frame_equal(x, y, check_exact=True)
    pd.testing.assert_frame_equal(df, original)


def test_candidata_huerfana_no_desaparece():
    df = dataset()
    c = candidatas(df)
    c['symbol'] = 'AUSENTE'
    with pytest.raises(ValueError, match='sin vela'):
        simular(df, c)


def test_candidata_no_contigua_no_desaparece():
    df = dataset()
    c = candidatas(df)
    c['entrada_timestamp'] += pd.Timedelta(minutes=1)
    with pytest.raises(ValueError, match='continuidad'):
        simular(df, c)


def test_prefijo_no_usa_futuro():
    df = dataset()
    df['fecha'] = df.timestamp.dt.date
    prefijo = analizar(calcular_indicadores(df.iloc[:100]))
    completo = analizar(calcular_indicadores(df))
    pd.testing.assert_frame_equal(prefijo, completo.iloc[:100])
    # Candidatos usan solo el open siguiente; nunca high/low/close futuro.
    completo['SENAL'] = 'NO TRADE'
    completo.loc[90, 'SENAL'] = 'LONG'
    assert len(preparar(completo)) == 1
    cambiado = completo.copy()
    cambiado.loc[100:, ['high', 'low', 'close']] = 500
    pd.testing.assert_frame_equal(preparar(completo), preparar(cambiado))


def test_pipeline_local_y_hash(tmp_path):
    archivo = tmp_path / 'sintetico.parquet'
    dataset().to_parquet(archivo, index=False)
    salida = tmp_path / 'run'
    meta = {'tipo': 'sintetico', 'fuente': 'fixture', 'licencia': 'pruebas', 'ajuste': 'no aplica', 'dataset_id': 'test'}
    assert ejecutar(archivo, sha256(archivo), salida, meta) == 0
    reporte = json.loads((salida / 'ejecucion.json').read_text())
    assert reporte['estado'] == 'OK'
    assert reporte['artefactos']['operaciones']['filas'] == 0
    assert ejecutar(archivo, '0' * 64, tmp_path / 'error', meta) == 2
    assert json.loads((tmp_path / 'error' / 'ejecucion.json').read_text())['etapa'] == 'identidad'
    with pytest.raises(FileExistsError):
        ejecutar(archivo, sha256(archivo), salida, meta)


def test_eventos_revision_no_disponible_antes_de_recepcion():
    publicado = datetime(2026, 1, 5, tzinfo=timezone.utc)
    recibido = publicado + timedelta(minutes=3)
    evento = Evento('id', 'macro', 'fixture', 'a' * 64, publicado, publicado, recibido, 'v2')
    assert not evento.disponible(publicado)
    assert evento.disponible(recibido)
    with pytest.raises(ValueError):
        replace(evento, recibido_en=publicado - timedelta(seconds=1))


def test_split_overnight_se_audita():
    primero = dataset()
    segundo = dataset()
    segundo['timestamp'] += pd.Timedelta(days=1)
    segundo[['open', 'high', 'low', 'close']] /= 4
    reporte = validar_ohlcv(pd.concat([primero, segundo], ignore_index=True))
    assert 'SALTO_ENTRE_SESIONES' in {i.codigo for i in reporte.incidencias}


@pytest.mark.parametrize('simbolo', [None, ''])
def test_simbolo_invalido(simbolo):
    df = dataset()
    df.loc[0, 'symbol'] = simbolo
    assert not validar_ohlcv(df).valido


def test_dataset_vacio_invalido():
    assert not validar_ohlcv(dataset().iloc[:0]).valido


def test_pipeline_rechaza_duplicados_sin_artefactos(tmp_path):
    df = dataset()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    path = tmp_path / 'duplicado.parquet'
    df.to_parquet(path)
    salida = tmp_path / 'run'
    assert ejecutar(path, sha256(path), salida, {'tipo': 'sintetico'}) == 2
    assert not list(salida.glob('*.parquet'))
    reporte = json.loads((salida / 'ejecucion.json').read_text())
    assert reporte['etapa'] == 'calidad_original'


def test_pipeline_con_operaciones_y_repeticion(tmp_path):
    import numpy as np
    df = dataset()
    x = np.arange(len(df))
    precio = 100 + .015 * x + .3 * np.sin(x / 4)
    df['open'] = df['close'] = precio
    df['high'] = precio + .1
    df['low'] = precio - .1
    df['volume'] = 1000 + (x % 30) * 100
    path = tmp_path / 'onda_sintetica.parquet'
    df.to_parquet(path, index=False)
    meta = {'tipo': 'sintetico', 'dataset_id': 'onda-prueba', 'fuente': 'formula', 'licencia': 'test', 'ajuste': 'no aplica'}
    for nombre in ['a', 'b']:
        assert ejecutar(path, sha256(path), tmp_path / nombre, meta) == 0
    for nombre in ['indicadores', 'senales', 'candidatas', 'operaciones', 'rechazos', 'capital']:
        a = pd.read_parquet(tmp_path / 'a' / f'{nombre}.parquet')
        b = pd.read_parquet(tmp_path / 'b' / f'{nombre}.parquet')
        pd.testing.assert_frame_equal(a, b, check_exact=True)
    operaciones = pd.read_parquet(tmp_path / 'a' / 'operaciones.parquet')
    assert len(operaciones) > 0
    assert (operaciones.entrada_timestamp > operaciones.senal_timestamp).all()


def test_actualizacion_fallida_conserva_snapshot(tmp_path, monkeypatch):
    import runpy
    from pathlib import Path
    import alpaca.data.historical
    import dotenv
    original = dataset().set_index(['symbol', 'timestamp'])
    archivo = tmp_path / 'datos_acciones_30dias.parquet'
    original.to_parquet(archivo)
    hash_original = sha256(archivo)
    script = tmp_path / 'actualizar_datos.py'
    script.write_text((Path(__file__).parents[1] / 'actualizar_datos.py').read_text())
    class ClienteFallido:
        def __init__(self, *args):
            pass
        def get_stock_bars(self, request):
            raise ConnectionError('fallo sintético de proveedor')
    monkeypatch.setattr(alpaca.data.historical, 'StockHistoricalDataClient', ClienteFallido)
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda: None)
    monkeypatch.setenv('ALPACA_API_KEY', 'sintetico-no-valido')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 'sintetico-no-valido')
    with pytest.raises(RuntimeError, match='snapshot anterior conservado'):
        runpy.run_path(str(script))
    assert sha256(archivo) == hash_original
